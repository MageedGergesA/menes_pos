# Part of the Mezze POS platform. See LICENSE (LGPL-3).
import json
import logging

import psycopg2

from odoo import api, fields, models
from odoo.sql_db import db_connect

_logger = logging.getLogger(__name__)


class MezzeAuditLog(models.Model):
    """Append-only audit trail for money-affecting and privileged actions.

    Every sale, void, refund, discount override, drawer open, cashier login, and
    price/config change writes one row here, attributed to the acting cashier,
    user, and terminal. Rows are create-only (the ACL denies write/unlink) so the
    trail cannot be altered after the fact. See ``docs/W1.md``.
    """
    _name = 'mezze.audit.log'
    _description = "Mezze Audit Log"
    _order = 'id desc'

    event = fields.Char(
        required=True, index=True,
        help="Event type, e.g. 'order.pay', 'order.void', 'refund', "
             "'discount.override', 'drawer.open', 'cashier.login', 'config.change'.")
    severity = fields.Selection(
        selection=[('info', "Info"), ('warning', "Warning"), ('critical', "Critical")],
        default='info', index=True)
    cashier_id = fields.Many2one('mezze.cashier', string="Cashier",
                                 ondelete='set null', index=True)
    user_id = fields.Many2one('res.users', string="User", ondelete='set null', index=True)
    terminal_id = fields.Many2one('mezze.terminal', string="Terminal",
                                  ondelete='set null', index=True)
    config_id = fields.Many2one('pos.config', string="Branch", ondelete='set null', index=True)
    res_model = fields.Char(string="Record Model", index=True)
    res_id = fields.Integer(string="Record ID", index=True)
    res_uuid = fields.Char(string="Record UUID", index=True)
    amount = fields.Float(string="Amount")
    detail = fields.Text(help="JSON context (before/after, reason code, approver).")
    # create_date / create_uid (ORM) are the immutable timestamp + author.

    @api.model
    def security_metrics(self, since=None):
        """Observability rollup for the authorization gate, from the append-only
        audit trail. Denials carry a ``reason_code`` in ``detail`` (capability,
        company/branch/terminal mismatch, replay, signature). Legacy-check count is
        structurally zero (the legacy auth model was removed)."""
        dom = [('event', '=', 'api.security_denied')]
        if since:
            dom.append(('create_date', '>=', since))
        self.env.cr.execute("""
            SELECT COALESCE(detail::json->>'reason_code','?') AS reason, count(*)
            FROM mezze_audit_log
            WHERE event='api.security_denied' %s
            GROUP BY reason
        """ % ("AND create_date >= %(s)s" if since else ""), {'s': since})
        by_reason = dict(self.env.cr.fetchall())
        return {
            'denials_total': sum(by_reason.values()),
            'by_reason': by_reason,
            'replay_count': by_reason.get('replayed_request', 0),
            'signature_failures': (by_reason.get('invalid_signature', 0)
                                   + by_reason.get('signature_required', 0)
                                   + by_reason.get('expired_signature', 0)),
            'legacy_check_count': 0,   # single mechanism: legacy auth removed
        }

    # Columns a fallback row may carry. Kept explicit so the out-of-band INSERT
    # below can never be widened by a caller passing an unexpected key.
    _FALLBACK_COLUMNS = ('event', 'severity', 'cashier_id', 'user_id', 'terminal_id',
                         'config_id', 'res_model', 'res_id', 'res_uuid', 'amount', 'detail')

    @api.model
    def log(self, event, **vals):
        """Append one audit row. Never raises into the caller's flow.

        The row is written in the CALLER's transaction, so it commits and rolls
        back with the action it describes.

        The exception is a read-only transaction. Odoo 19 serves ``auth='none'``
        routes on a read-only cursor by default (``odoo/http.py``: ``default_mode
        = ... get('readonly', default_auth == 'none')``), so Postgres refuses the
        INSERT. That used to be swallowed with everything else: the request
        returned 200 and the row was silently dropped -- the one failure mode an
        audit trail must not have, since the events reaching it on a read-only
        request are the security ones (break-glass use, denials).

        Those rows are now made DURABLE the same way ``_audit_security`` in
        ``controllers/main.py`` already does it: a self-committing INSERT on an
        independent connection. Such a row is deliberately not atomic with the
        caller -- it survives even if the caller's action rolls back, which for
        this trail is the right way round.
        """
        vals['event'] = event
        try:
            # A SAVEPOINT so a failed append never poisons the caller's
            # transaction: the security gate must still be able to deny or allow
            # the request cleanly even when its own audit row could not be kept.
            with self.env.cr.savepoint():
                return self.sudo().create(vals)
        except psycopg2.errors.ReadOnlySqlTransaction:
            self._log_durable(vals)
            return self.browse()
        except Exception:  # noqa: BLE001
            _logger.exception("Mezze audit append failed: %s", event)
            return self.browse()

    def _log_durable(self, vals):
        """Write one audit row on its own connection, and commit it there.

        Reached only from a read-only transaction, where the row would otherwise
        be lost outright. Uses ``db_connect`` rather than ``registry.cursor()``
        deliberately: the registry's cursor is patched under test to hand back a
        ``TestCursor``, and ``TestCursor._check_cursor_readonly`` refuses to open
        a read/write cursor while a read-only one is on the stack.

        Raw SQL, so this cannot re-enter the ORM (and its read-only cursor) on
        the way out. Never raises: an audit append must not decide whether a
        request succeeds.
        """
        cols = [c for c in self._FALLBACK_COLUMNS if vals.get(c) is not None]
        detail = vals.get('detail')
        if detail is not None and not isinstance(detail, str):
            vals = dict(vals, detail=json.dumps(detail, default=str))
        try:
            with db_connect(self.env.cr.dbname).cursor() as acr:
                acr.execute(
                    "INSERT INTO mezze_audit_log (%s, create_uid, create_date, "
                    "write_uid, write_date) VALUES (%s, 1, now(), 1, now())"
                    % (', '.join(cols), ', '.join(['%s'] * len(cols))),
                    tuple(vals[c] for c in cols))
                acr.commit()
        except Exception:  # noqa: BLE001 — durability is best-effort, never a gate
            _logger.warning("Mezze durable audit append failed: %s", vals.get('event'))
