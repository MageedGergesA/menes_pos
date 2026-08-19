# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""WS-1 — the staff session a device-authenticated station opens for a person.

A station proves itself with its key (WS-0). That gets it an API session, and
nothing more: the staff surfaces are ``auth='user'``, so somebody still has to be
accountable for the money. This model is that accountability, and it is the thing
an operator can kill.

Three deliberate choices worth stating, because each rules out an easier design:

* **The session is a record, not just a cookie.** A cookie alone cannot be
  revoked from a console, cannot be listed, and cannot die when a device is
  revoked. Every request re-reads this row, so ending a shift is immediate
  everywhere rather than eventual.
* **The person is a ``mezze.cashier``, not a ``res.users``.** Front-of-house
  staff do not get Odoo accounts (that is the existing design and the right one);
  they get a PIN. The Odoo user underneath is a shared, least-privilege service
  identity, and attribution stays with the cashier, in the audit log, per person.
* **Confinement lives on the server.** The service user is limited by groups,
  and the session is limited by path (``domain/station_surface.py``). Hiding a
  menu would not have been authorization.
"""
import logging

from odoo import SUPERUSER_ID, api, fields, models
from odoo.sql_db import db_connect

from ..domain import station_surface

_logger = logging.getLogger(__name__)


class MezzeStationSurfaceSession(models.Model):
    """One signed-in shift on one station."""
    _name = 'mezze.station.surface.session'
    _description = "Mezze Station Staff Session"
    _order = 'started_at desc, id desc'

    terminal_id = fields.Many2one('mezze.terminal', required=True, ondelete='cascade', index=True)
    cashier_id = fields.Many2one('mezze.cashier', required=True, ondelete='restrict', index=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='restrict',
                              help="The least-privilege service identity this session runs as. "
                                   "Never the cashier's own account.")
    branch_id = fields.Many2one('pos.config', string="Branch", ondelete='set null', index=True)
    station_role = fields.Char(index=True)
    surface = fields.Char(help="The path this session was opened for.")

    started_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    expires_at = fields.Datetime(required=True, index=True,
                                 help="Absolute ceiling. A shift, not a day.")
    last_seen_at = fields.Datetime(index=True,
                                   help="Written at most once a minute; drives the idle cut-off.")
    ended_at = fields.Datetime(index=True)
    end_reason = fields.Char(help="clocked_out / expired / idle / device_revoked / "
                                  "staff_disabled / operator")
    remote_addr = fields.Char()
    is_live = fields.Boolean(default=True, index=True, string="Open",
                             help="Deliberately NOT named 'active'. Odoo's active flag means "
                                  "archived, and default searches hide archived rows — a shift "
                                  "history that disappears the moment it ends would be useless "
                                  "to the console and would silently break the sweeper.")

    # ------------------------------------------------------------------ opening
    @api.model
    def open_for(self, terminal, cashier, user, surface=None, remote_addr=None):
        """Start a shift. The caller has already proven the device AND the PIN."""
        now = fields.Datetime.now()
        # One live session per station: signing in replaces whoever was there,
        # which is what actually happens at a counter during a handover.
        self.sudo().search([
            ('terminal_id', '=', terminal.id), ('is_live', '=', True),
        ]).end('handover')
        return self.sudo().create({
            'terminal_id': terminal.id,
            'cashier_id': cashier.id,
            'user_id': user.id,
            'branch_id': terminal.branch_id.id or False,
            'station_role': terminal.station_role or '',
            'surface': surface or '',
            'started_at': now,
            'expires_at': fields.Datetime.add(
                now, seconds=station_surface.SURFACE_TTL_SECONDS),
            'last_seen_at': now,
            'remote_addr': remote_addr or '',
            'is_live': True,
        })

    # ------------------------------------------------------------------ reading
    @api.model
    def resolve(self, session_id):
        """Return the live session for ``session_id``, or an empty recordset.

        Every reason a session should stop working is checked here, in one place,
        so no caller can forget one: expiry, idleness, the shift being ended, the
        DEVICE being revoked, and the PERSON being deactivated.
        """
        if not session_id:
            return self.browse()
        rec = self.sudo().browse(int(session_id)).exists()
        if not rec or not rec.is_live or rec.ended_at:
            return self.browse()

        now = fields.Datetime.now()
        if rec.expires_at and rec.expires_at <= now:
            rec.end('expired')
            return self.browse()

        idle_cut = fields.Datetime.subtract(
            now, seconds=station_surface.SURFACE_IDLE_SECONDS)
        if rec.last_seen_at and rec.last_seen_at <= idle_cut:
            rec.end('idle')
            return self.browse()

        # A revoked device must not keep a shift alive: WS-0 kills its API
        # session, and this is the same rule for the human surface.
        term = rec.terminal_id.sudo().with_context(active_test=False)
        if not term or not term.active or term.station_revoked_at:
            rec.end('device_revoked')
            return self.browse()

        if not rec.cashier_id.sudo().with_context(active_test=False).active:
            rec.end('staff_disabled')
            return self.browse()

        return rec

    # ------------------------------------------------------------------ touching
    def touch(self):
        """Record activity, at most once a minute, on its own connection.

        Two problems this avoids, both discovered by running it. A write per
        request would be a write per asset load — hence the once-a-minute floor.
        And a heartbeat fires on GET requests, which Odoo serves in a READ-ONLY
        transaction: writing there raises, Odoo retries the whole request in
        read-write mode, and every page load silently costs double. So the
        heartbeat goes to its own cursor and commits, exactly as mezze.rate.limit
        already does for the same reason.

        It is also correct for the heartbeat to survive a request that later
        rolls back: the till WAS active, whatever became of the transaction.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        if self.last_seen_at:
            since = (now - self.last_seen_at).total_seconds()
            if since < station_surface.SURFACE_TOUCH_SECONDS:
                return False
        try:
            with db_connect(self.env.cr.dbname).cursor() as cr:
                cr.execute(
                    "UPDATE mezze_station_surface_session SET last_seen_at = %s "
                    "WHERE id = %s AND is_live = true", (now, self.id))
                cr.commit()
        except Exception:  # noqa: BLE001 — a missed heartbeat must never 500 a till
            _logger.debug('station shift heartbeat failed', exc_info=True)
            return False
        self.invalidate_recordset(['last_seen_at'])
        return True

    # ------------------------------------------------------------------ ending
    def end(self, reason='clocked_out'):
        """Close a shift. Idempotent, so callers never have to check first."""
        live = self.sudo().filtered(lambda r: r.is_live and not r.ended_at)
        if not live:
            return False
        live.write({
            'is_live': False,
            'ended_at': fields.Datetime.now(),
            'end_reason': reason,
        })
        for rec in live:
            try:
                self.env['mezze.audit.log'].sudo().log(
                    'station.shift_ended', severity='info',
                    cashier_id=rec.cashier_id.id,
                    config_id=rec.branch_id.id or False,
                    detail='station=%s reason=%s' % (rec.terminal_id.device_uuid or '', reason))
            except Exception:  # noqa: BLE001 — auditing must never block a sign-out
                _logger.debug('shift-end audit failed', exc_info=True)
        return True

    # ------------------------------------------------------------------ sweeping
    @api.model
    def _cron_gc(self):
        """Close sessions the clock has already ended, and prune ancient rows.

        Resolution already refuses an expired session on the next request; this
        exists so the console never shows a shift as open when it is not, even
        on a station that has gone quiet.
        """
        now = fields.Datetime.now()
        idle_cut = fields.Datetime.subtract(
            now, seconds=station_surface.SURFACE_IDLE_SECONDS)
        stale = self.sudo().search([
            ('is_live', '=', True),
            '|', ('expires_at', '<=', now), ('last_seen_at', '<=', idle_cut),
        ])
        for rec in stale:
            rec.end('expired' if rec.expires_at <= now else 'idle')

        keep_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'mezze_bridge.surface_session_retention_days', 90) or 90)
        cutoff = fields.Datetime.subtract(now, days=keep_days)
        self.sudo().search([('is_live', '=', False), ('ended_at', '<', cutoff)]).unlink()
        return True

    # ----------------------------------------------------- the service identity
    @api.model
    def _service_user_for(self, company):
        """The least-privilege Odoo user a station's shift runs as, per company.

        One identity per company rather than one globally: a station in company A
        must never end up holding a session whose user can see company B. The
        user carries no password, so it cannot be signed into from ``/web/login``
        — the only way to obtain a session as this identity is to prove a device
        key and then a staff PIN.
        """
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        login = 'mezze.station.service@%d' % company.id
        user = Users.search([('login', '=', login)], limit=1)
        if user:
            if not user.active:
                user.active = True
            return user

        group = self.env.ref('mezze_bridge.group_station_service', raise_if_not_found=False)
        # NOTE: 'password' is deliberately never written. Passing False would be
        # handed to passlib as a bool; leaving the column null is what actually
        # makes this identity unusable at /web/login, which is the property we
        # want — the only route to a session as this user is a device key plus a
        # staff PIN.
        #
        # This create only works because the caller has given the request a real
        # acting user (see the controller's _staff_env). Creating a res.users
        # schedules avatar and tracking recomputes that run at flush, and a flush
        # with no acting user fails far from here, as an unrelated singleton
        # error on res.users().
        return Users.create({
            'name': "Mezze Station Service (%s)" % (company.name or company.id),
            'login': login,
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
            'group_ids': [(6, 0, [group.id])] if group else False,
            'active': True,
        })

    # ------------------------------------------------- branch authority (WS-2)
    @api.model
    def branch_for_request(self):
        """The branch a station-bound web session is confined to, else empty.

        This is the SERVER's answer to "which register is this?", and it has to
        outrank the URL. A station is enrolled to one branch by the manager who
        cut its activation code; letting ``?config_id=`` override that would mean
        anyone at the till could point it at another branch's register and sell
        into that branch's session, stock and cash.

        Returns an empty recordset for an ordinary browser, which then falls back
        to the usual ``?config_id=`` / default-branch resolution.
        """
        try:
            from odoo.http import request
            session = getattr(request, 'session', None)
            shift_id = session and session.get('mezze_surface_id')
        except Exception:  # noqa: BLE001
            return self.env['pos.config'].browse()
        if not shift_id:
            return self.env['pos.config'].browse()
        shift = self.sudo().browse(int(shift_id)).exists()
        if not shift or not shift.is_live:
            return self.env['pos.config'].browse()
        return shift.terminal_id.sudo().branch_id
