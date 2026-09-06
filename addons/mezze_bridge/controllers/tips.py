# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Tip pool endpoints (design BE-008 / TIP_POOLING.md §7).

Every figure these return is DERIVED from the ledger -- the design's whole
point is that one liability has one owner, so no total here is stored beside
the rows it comes from.
"""
import datetime
import logging

from odoo import fields, http
from odoo.exceptions import UserError

from ..domain import tip_pool as tp
from .main import API_PREFIX, MezzeBridgeController

_logger = logging.getLogger(__name__)


class MezzeTipsController(MezzeBridgeController):
    """Subclasses the bridge, like every other satellite controller here, so
    ``_authorize`` / ``_api_env`` / ``_resolve_config`` are the SAME ones the
    rest of the API uses rather than a second copy."""

    def _shift_window(self, config):
        """The current shift: the open session, else today."""
        session = config.current_session_id.filtered(lambda s: s.state == 'opened')
        if session and session.start_at:
            return session, session.start_at, fields.Datetime.now() + datetime.timedelta(hours=1)
        now = fields.Datetime.now()
        return session, now.replace(hour=0, minute=0, second=0), now + datetime.timedelta(hours=1)

    def _run_payload(self, run):
        cur = run.currency_id
        return {
            'id': run.id, 'rule': run.rule, 'state': run.state,
            'pool': run.pool_amount,
            'approved_by': run.approved_by.name or None,
            'approved_at': run.approved_at and str(run.approved_at) or None,
            'currency': cur.symbol or cur.name,
            'rows': [{
                'cashier_id': l.cashier_id.id, 'name': l.cashier_id.name,
                'role': l.cashier_id.role,
                'minutes': l.minutes, 'hours': round(l.minutes / 60.0, 2),
                'weight': round(l.weight, 4),
                'pct': round(100.0 * l.share / run.pool_amount, 1) if run.pool_amount else 0.0,
                'share': l.share,
                'paid_cash': l.paid_cash, 'paid_payroll': l.paid_payroll,
                'outstanding': l.outstanding,
            } for l in run.line_ids],
        }

    @http.route(f'{API_PREFIX}/tips/pool', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def tips_pool(self, config_id=None, **kw):
        """Composition, the six rules, and the current run if there is one."""
        gate = self._authorize()
        if gate:
            return gate
        env = self._api_env()
        config = self._resolve_config(env, config_id)
        if not config:
            return {'ok': False, 'error': 'no_pos_config'}
        session, start, end = self._shift_window(config)
        Entry = env['mezze.tip.entry'].sudo()
        dom = [('config_id', '=', config.id),
               ('create_date', '>=', start), ('create_date', '<', end)]
        card = sum(Entry.search(dom + [('kind', '=', 'capture')]).mapped('amount'))
        cash = sum(Entry.search(dom + [('kind', '=', 'declare')]).mapped('amount'))
        run = env['mezze.tip.run'].sudo().search(
            [('config_id', '=', config.id), ('state', '!=', 'void')],
            order='id desc', limit=1)
        cur = config.currency_id
        return {
            'ok': True,
            'currency': cur.symbol or cur.name,
            'composition': {'card': card, 'cash': cash, 'pool': card + cash},
            'rules': [{'id': r, 'label': _RULE_LABELS[r], 'note': _RULE_NOTES[r]}
                      for r in tp.RULES],
            'tip_out_pct': tp.TIP_OUT_PCT,
            'run': self._run_payload(run) if run else None,
            'session_open': bool(session),
        }

    @http.route(f'{API_PREFIX}/tips/compute', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def tips_compute(self, config_id=None, rule=None, custom_pct=None, **kw):
        gate = self._authorize()
        if gate:
            return gate
        env = self._api_env()
        config = self._resolve_config(env, config_id)
        if not config:
            return {'ok': False, 'error': 'no_pos_config'}
        if rule not in tp.RULES:
            return {'ok': False, 'error': 'unknown_rule'}
        session, start, end = self._shift_window(config)
        Run = env['mezze.tip.run'].sudo()
        run = Run.search([('config_id', '=', config.id), ('state', '=', 'draft')],
                         order='id desc', limit=1)
        if not run:
            run = Run.create({'config_id': config.id, 'currency_id': config.currency_id.id,
                              'session_id': session.id or False, 'rule': rule,
                              'date_from': start, 'date_to': end})
        else:
            run.rule = rule
        err = run.action_compute(custom_pct=custom_pct or None)
        if err:
            # Named, not coded: a rule that cannot be applied is something to
            # tell the manager, not a 500.
            return {'ok': False, 'error': err, 'run': self._run_payload(run)}
        return {'ok': True, 'run': self._run_payload(run)}

    @http.route(f'{API_PREFIX}/tips/approve', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def tips_approve(self, run_id=None, cashier_id=None, pin=None, **kw):
        gate = self._authorize()
        if gate:
            return gate
        env = self._api_env()
        run = env['mezze.tip.run'].sudo().browse(int(run_id or 0)).exists()
        cashier = env['mezze.cashier'].sudo().browse(int(cashier_id or 0)).exists()
        if not run:
            return {'ok': False, 'error': 'unknown_run'}
        try:
            run.action_approve(cashier, pin)
        except UserError as exc:
            return {'ok': False, 'error': str(exc)}
        return {'ok': True, 'run': self._run_payload(run)}

    @http.route(f'{API_PREFIX}/tips/payout', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def tips_payout(self, run_id=None, route=None, **kw):
        gate = self._authorize()
        if gate:
            return gate
        env = self._api_env()
        run = env['mezze.tip.run'].sudo().browse(int(run_id or 0)).exists()
        if not run:
            return {'ok': False, 'error': 'unknown_run'}
        try:
            paid = run.action_payout(route)
        except UserError as exc:
            return {'ok': False, 'error': str(exc)}
        return {'ok': True, 'paid': paid, 'run': self._run_payload(run)}


_RULE_LABELS = {
    tp.EQUAL: "Equal", tp.HOURS: "Hours worked", tp.ROLE: "Role-weighted",
    tp.CUSTOM: "Custom percentage", tp.DIRECT: "Direct to server", tp.HYBRID: "Hybrid",
}
# The design shows what each rule MEANS beside it, because this is the screen a
# team argues in front of.
_RULE_NOTES = {
    tp.EQUAL: "One share per eligible head — small teams, one job.",
    tp.HOURS: "Minutes actually worked, breaks excluded. The default.",
    tp.ROLE: "Hours × role weight — mixed front/back pools.",
    tp.CUSTOM: "Manager-set % per person. Must total 100 or the run refuses.",
    tp.DIRECT: "Each server keeps the tips captured on their own checks.",
    tp.HYBRID: "Direct, less a tip-out into a support pool split by hours × role.",
}
