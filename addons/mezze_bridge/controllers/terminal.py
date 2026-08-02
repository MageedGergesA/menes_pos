"""S2C-3 — Integrated payment terminal orchestration endpoints.

The cashier drives ONE integrated-terminal request through these routes. The
SERVER is authoritative for the outcome and the money effect (see
models/mezze_terminal_txn.py): a browser can never assert a success into a
payment. Mezze reimplements NO provider protocol — real providers are supported
by Odoo but not yet wired to the standalone cashier (audit doc), so completion
for them is refused. The TEST-ONLY simulator lets us certify the Mezze
orchestration/idempotency/force-done software without physical hardware.
"""
from odoo import http

from .main import MezzeBridgeController, API_PREFIX, _reraise_if_retryable

# Manager rank for the Force Done gate (mirrors /orders/pay duplicate approval).
_ROLE_RANK = {'cashier': 0, 'supervisor': 1, 'manager': 2}


class MezzeTerminalController(MezzeBridgeController):

    def _resolve_order(self, env, uuid=None, order_id=None):
        if uuid:
            return env['pos.order'].search([('uuid', '=', uuid)], limit=1)
        return env['pos.order'].browse(int(order_id)) if order_id else env['pos.order']

    def _resolve_txn(self, env, request_id):
        return env['mezze.terminal.transaction'].sudo().search(
            [('request_id', '=', str(request_id))], limit=1)

    def _verify_manager(self, env, code, pin):
        """Return (manager_record | None, error | None). A cashier PIN can NEVER
        authorize (role rank < manager), so Force Done is not self-approvable."""
        if not (code and pin):
            return None, 'manager_required'
        c = env['mezze.cashier'].sudo().search(
            [('code', '=', code), ('active', '=', True)], limit=1)
        if not c or not c.check_pin(pin):
            return None, 'bad_credentials'
        if _ROLE_RANK.get(c.role, 0) < 2:
            return None, 'insufficient_role'
        return c, None

    # ------------------------------------------------------------------ start
    @http.route(f'{API_PREFIX}/terminal/start', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def terminal_start(self, uuid=None, order_id=None, payment_method_id=None,
                       device_id=None, amount=None, scenario=None, **kw):
        """Open ONE integrated-terminal request. The amount is server-authoritative
        (remaining balance / partial ceiling); the browser cannot inflate it."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            order = self._resolve_order(env, uuid, order_id)
            if not order.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            denied = self._security_gate(env, 'terminal/start', target_order=order)
            if denied:
                return denied
            if order.state != 'draft':
                return self._json({'ok': False, 'error': 'order_not_payable',
                                   'message': 'This order is not open for payment.'}, status=409)
            config = order.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            order = order.with_env(env)
            pm = env['pos.payment.method'].browse(int(payment_method_id)) if payment_method_id \
                else config.payment_method_ids[:1]
            if not pm or pm.mezze_mode != 'odoo_terminal':
                return self._json({'ok': False, 'error': 'not_integrated',
                                   'message': 'This method is not an integrated terminal.'}, status=400)
            device = env['mezze.payment.device'].browse(int(device_id)) if device_id else None
            provider = pm.mezze_terminal_provider or ''
            # TEST-ONLY simulator exposure guard (§40): a method may only resolve to
            # the simulator when the operator has explicitly enabled it (never in a
            # normal production config).
            sim_on = env['ir.config_parameter'].sudo().get_param(
                'mezze_bridge.terminal_simulator_enabled') in ('1', 'True', 'true', True)
            if provider == 'test' and not sim_on:
                return self._json({'ok': False, 'error': 'simulator_disabled',
                                   'message': 'The terminal simulator is not enabled here.'}, status=403)
            Txn = env['mezze.terminal.transaction']
            try:
                txn = Txn.mezze_start(order, pm, device, amount, provider)
            except Exception as se:  # UserError -> actionable 409
                return self._json({'ok': False, 'error': 'terminal_start_rejected',
                                   'message': str(se)}, status=409)
            # scenario is TEST-ONLY metadata; ignored server-side for real providers.
            if provider == 'test':
                allowed = {'success', 'delayed_success', 'duplicate_success', 'decline',
                           'cancel', 'error', 'timeout', 'unknown'}
                txn.sudo().sim_scenario = scenario if scenario in allowed else 'success'
            self._audit(env, 'terminal.start', order, **self._actor(env, kw))
            return dict({'ok': True}, **txn.mezze_payload())
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            return self._json({'ok': False, 'error': 'terminal_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------ complete
    @http.route(f'{API_PREFIX}/terminal/complete', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def terminal_complete(self, request_id=None, outcome=None, **kw):
        """Settle a live request. ``outcome`` is the browser's CLAIM and is advisory
        only — the server decides the authoritative result. On approval exactly ONE
        pos.payment is created (idempotent on request_id)."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        txn = self._resolve_txn(env, request_id)
        if not txn.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        denied = self._security_gate(env, 'terminal/complete', target_order=txn.pos_order_id)
        if denied:
            return denied
        try:
            txn.mezze_apply_result(claimed_outcome=outcome)
        except Exception as se:  # provider-pending or settlement error
            payload = txn.mezze_payload()
            return self._json(dict({'ok': False, 'error': 'terminal_not_completed',
                                    'message': str(se)}, **payload), status=409)
        return dict({'ok': True}, **txn.mezze_payload())

    # ------------------------------------------------------------------ cancel
    @http.route(f'{API_PREFIX}/terminal/cancel', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def terminal_cancel(self, request_id=None, **kw):
        """Cancel a live request (native cancel path for a real adapter). No payment."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        txn = self._resolve_txn(env, request_id)
        if not txn.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        denied = self._security_gate(env, 'terminal/cancel', target_order=txn.pos_order_id)
        if denied:
            return denied
        try:
            txn.mezze_cancel()
        except Exception as se:  # noqa: BLE001
            return self._json({'ok': False, 'error': 'cancel_rejected', 'message': str(se)}, status=409)
        return dict({'ok': True}, **txn.mezze_payload())

    # ------------------------------------------------------------------ status
    # read-only recovery endpoint (no state mutation)
    @http.route(f'{API_PREFIX}/terminal/status', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def terminal_status(self, request_id=None, **kw):
        """Authoritative current state — used to recover after a lost response
        (§16): the cashier reloads and reads the DB truth instead of re-charging."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        txn = self._resolve_txn(env, request_id)
        if not txn.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        denied = self._security_gate(env, 'terminal/status', target_order=txn.pos_order_id)
        if denied:
            return denied
        return dict({'ok': True}, **txn.mezze_payload())

    # ------------------------------------------------------------------ force done
    @http.route(f'{API_PREFIX}/terminal/force_done', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def terminal_force_done(self, request_id=None, manager_code=None, manager_pin=None,
                            manager_reason=None, **kw):
        """Manager-gated MANUAL OVERRIDE of an uncertain/failed request. Requires a
        manager PIN (cashier can never self-force), a reason, and an eligible state.
        Produces ONE payment with force-done provenance + reconciliation flag."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        txn = self._resolve_txn(env, request_id)
        if not txn.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        denied = self._security_gate(env, 'terminal/force_done', target_order=txn.pos_order_id)
        if denied:
            return denied
        manager, mgr_err = self._verify_manager(env, manager_code, manager_pin)
        if not manager:
            status = 403 if mgr_err in ('bad_credentials', 'insufficient_role') else 401
            return self._json({'ok': False, 'error': mgr_err}, status=status)
        try:
            txn.mezze_force_done(manager, manager_reason)
        except Exception as se:  # ineligible state / missing reason
            return self._json(dict({'ok': False, 'error': 'force_done_rejected',
                                    'message': str(se)}, **txn.mezze_payload()), status=409)
        self._audit(env, 'terminal.force_done', txn.pos_order_id, **self._actor(env, kw))
        return dict({'ok': True}, **txn.mezze_payload())
