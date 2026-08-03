"""S2C-7 — Automated cash-machine orchestration endpoints (Cashdro/Cashmatic/Glory).

Source audit (docs/sell-ready/payments/cash-machine-audit.md): the only native cash
machine present in this Odoo 19 is Glory (pos_glory_cash), a BROWSER-DIRECT WebSocket
integration welded to the native PosStore. No adapter is safely reusable from the
standalone Mezze cashier yet, so a real device is refused here (adapter PENDING). Mezze
reimplements NO device protocol. These routes drive the Mezze ORCHESTRATION on the same
server-authoritative spine certified for L3 integrated terminals
(models/mezze_terminal_txn.py, kind='cash_machine'): the SERVER decides the outcome and
the money effect — a browser can never assert cash into a payment. A TEST-ONLY simulator
certifies the orchestration/idempotency/change/cancel software without hardware.
"""
from odoo import http

from .main import MezzeBridgeController, API_PREFIX, _reraise_if_retryable

_ROLE_RANK = {'cashier': 0, 'supervisor': 1, 'manager': 2}
# TEST-ONLY cash-machine simulator scenarios (mirrors _CASH_SIM_OUTCOME).
_CASH_SCENARIOS = {'success_exact', 'success_with_change', 'delayed_success',
                   'duplicate_success', 'cancel', 'connection_error', 'unknown'}


class MezzeCashMachineController(MezzeBridgeController):

    def _resolve_cm_order(self, env, uuid=None, order_id=None):
        if uuid:
            return env['pos.order'].search([('uuid', '=', uuid)], limit=1)
        return env['pos.order'].browse(int(order_id)) if order_id else env['pos.order']

    def _resolve_cm_txn(self, env, request_id):
        return env['mezze.terminal.transaction'].sudo().search(
            [('request_id', '=', str(request_id)), ('kind', '=', 'cash_machine')], limit=1)

    def _verify_cm_manager(self, env, code, pin):
        if not (code and pin):
            return None, 'manager_required'
        c = env['mezze.cashier'].sudo().search([('code', '=', code), ('active', '=', True)], limit=1)
        if not c or not c.check_pin(pin):
            return None, 'bad_credentials'
        if _ROLE_RANK.get(c.role, 0) < 2:
            return None, 'insufficient_role'
        return c, None

    # ------------------------------------------------------------------ start
    @http.route(f'{API_PREFIX}/cashmachine/start', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def cashmachine_start(self, uuid=None, order_id=None, payment_method_id=None,
                          device_id=None, amount=None, scenario=None, sim_inserted=None, **kw):
        """Open ONE cash-machine request. The amount is server-authoritative (remaining
        balance / partial ceiling); the browser cannot inflate the machine amount."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            order = self._resolve_cm_order(env, uuid, order_id)
            if not order.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            denied = self._security_gate(env, 'cashmachine/start', target_order=order)
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
            if not pm or pm.mezze_mode != 'cash_machine':
                return self._json({'ok': False, 'error': 'not_cash_machine',
                                   'message': 'This method is not a cash machine.'}, status=400)
            device = env['mezze.payment.device'].browse(int(device_id)) if device_id else None
            provider = pm.mezze_terminal_provider or ''
            # TEST-ONLY simulator exposure guard (§31): a method may only resolve to the
            # simulator when the operator has explicitly enabled it (never in production).
            sim_on = env['ir.config_parameter'].sudo().get_param(
                'mezze_bridge.cashmachine_simulator_enabled') in ('1', 'True', 'true', True)
            if provider == 'test' and not sim_on:
                return self._json({'ok': False, 'error': 'simulator_disabled',
                                   'message': 'The cash-machine simulator is not enabled here.'}, status=403)
            Txn = env['mezze.terminal.transaction']
            try:
                txn = Txn.mezze_start_cashmachine(order, pm, device, amount)
            except Exception as se:
                return self._json({'ok': False, 'error': 'cashmachine_start_rejected',
                                   'message': str(se)}, status=409)
            if provider == 'test':
                txn.sudo().sim_scenario = scenario if scenario in _CASH_SCENARIOS else 'success_exact'
                if sim_inserted is not None:
                    try:
                        txn.sudo().sim_inserted = float(sim_inserted)
                    except (TypeError, ValueError):
                        pass
            self._audit(env, 'cashmachine.start', order, **self._actor(env, kw))
            return dict({'ok': True}, **txn.mezze_payload())
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            return self._json({'ok': False, 'error': 'cashmachine_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------ complete
    @http.route(f'{API_PREFIX}/cashmachine/complete', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def cashmachine_complete(self, request_id=None, outcome=None, **kw):
        """Settle a live request. ``outcome`` is the browser CLAIM (advisory only) — the
        server decides. On approval exactly ONE pos.payment == the NET amount is created
        (idempotent on request_id); inserted cash is never revenue."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        txn = self._resolve_cm_txn(env, request_id)
        if not txn.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        denied = self._security_gate(env, 'cashmachine/complete', target_order=txn.pos_order_id)
        if denied:
            return denied
        try:
            txn.mezze_apply_result(claimed_outcome=outcome)
        except Exception as se:
            payload = txn.mezze_payload()
            return self._json(dict({'ok': False, 'error': 'cashmachine_not_completed',
                                    'message': str(se)}, **payload), status=409)
        return dict({'ok': True}, **txn.mezze_payload())

    # ------------------------------------------------------------------ cancel
    @http.route(f'{API_PREFIX}/cashmachine/cancel', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def cashmachine_cancel(self, request_id=None, **kw):
        """Cancel a live request (native cancel path for a real adapter). No payment."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        txn = self._resolve_cm_txn(env, request_id)
        if not txn.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        denied = self._security_gate(env, 'cashmachine/cancel', target_order=txn.pos_order_id)
        if denied:
            return denied
        try:
            txn.mezze_cancel()
        except Exception as se:  # noqa: BLE001
            return self._json({'ok': False, 'error': 'cancel_rejected', 'message': str(se)}, status=409)
        return dict({'ok': True}, **txn.mezze_payload())

    # ------------------------------------------------------------------ status
    @http.route(f'{API_PREFIX}/cashmachine/status', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def cashmachine_status(self, request_id=None, **kw):
        """Authoritative current state — recover after a lost response (§19): the
        cashier reloads and reads the DB truth instead of re-sending to the machine."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        txn = self._resolve_cm_txn(env, request_id)
        if not txn.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        denied = self._security_gate(env, 'cashmachine/status', target_order=txn.pos_order_id)
        if denied:
            return denied
        return dict({'ok': True}, **txn.mezze_payload())

    # ------------------------------------------------------------------ force done
    @http.route(f'{API_PREFIX}/cashmachine/force_done', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def cashmachine_force_done(self, request_id=None, manager_code=None, manager_pin=None,
                               manager_reason=None, **kw):
        """Manager-gated MANUAL OVERRIDE of an uncertain cash-machine result (§16/§24):
        the manager physically verifies the machine, then forces. Cashier can never
        self-force. One payment, force-done provenance + reconciliation flag."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        txn = self._resolve_cm_txn(env, request_id)
        if not txn.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        denied = self._security_gate(env, 'cashmachine/force_done', target_order=txn.pos_order_id)
        if denied:
            return denied
        manager, mgr_err = self._verify_cm_manager(env, manager_code, manager_pin)
        if not manager:
            status = 403 if mgr_err in ('bad_credentials', 'insufficient_role') else 401
            return self._json({'ok': False, 'error': mgr_err}, status=status)
        try:
            txn.mezze_force_done(manager, manager_reason)
        except Exception as se:
            return self._json(dict({'ok': False, 'error': 'force_done_rejected',
                                    'message': str(se)}, **txn.mezze_payload()), status=409)
        self._audit(env, 'cashmachine.force_done', txn.pos_order_id, **self._actor(env, kw))
        return dict({'ok': True}, **txn.mezze_payload())
