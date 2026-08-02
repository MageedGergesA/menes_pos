"""S2C-4 — Bank App (Payment) QR endpoints.

Generate a NATIVE Odoo bank-app QR for the order's authoritative remaining, then
record a manual cashier confirmation as ONE pos.payment (see
models/mezze_payment_qr.py). Server is authoritative for amount/currency/account/
payload; a browser cannot assert a payment. Completely separate from Table QR
(self-order /qr/menu,/qr/bill,/qr/pay in main.py).
"""
from odoo import http

from .main import MezzeBridgeController, API_PREFIX, _reraise_if_retryable


class MezzeQrController(MezzeBridgeController):

    def _resolve_order(self, env, uuid=None, order_id=None):
        if uuid:
            return env['pos.order'].search([('uuid', '=', uuid)], limit=1)
        return env['pos.order'].browse(int(order_id)) if order_id else env['pos.order']

    def _resolve_qr(self, env, token):
        return env['mezze.payment.qr'].sudo().search([('token', '=', str(token))], limit=1)

    # ------------------------------------------------------------------ generate
    @http.route(f'{API_PREFIX}/payment/qr/generate', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def qr_generate(self, uuid=None, order_id=None, payment_method_id=None, amount=None, **kw):
        """Generate a native bank-app QR for the (server-authoritative) amount."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            order = self._resolve_order(env, uuid, order_id)
            if not order.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            denied = self._security_gate(env, 'payment/qr/generate', target_order=order)
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
            if not pm or pm.mezze_mode != 'bank_qr':
                return self._json({'ok': False, 'error': 'not_qr',
                                   'message': 'This method is not a bank-app QR method.'}, status=400)
            try:
                rec = env['mezze.payment.qr'].mezze_generate(order, pm, amount)
                payload = rec.mezze_payload(include_image=True)
            except Exception as ge:  # UserError -> actionable
                return self._json({'ok': False, 'error': 'qr_generate_rejected',
                                   'message': str(ge)}, status=409)
            self._audit(env, 'qr.generate', order, **self._actor(env, kw))
            return dict({'ok': True}, **payload)
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            return self._json({'ok': False, 'error': 'qr_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------ confirm
    @http.route(f'{API_PREFIX}/payment/qr/confirm', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def qr_confirm(self, qr_token=None, **kw):
        """Manual cashier confirmation → ONE pos.payment (idempotent, stale-guarded)."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        rec = self._resolve_qr(env, qr_token)
        if not rec.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        denied = self._security_gate(env, 'payment/qr/confirm', target_order=rec.pos_order_id)
        if denied:
            return denied
        config = rec.pos_order_id.config_id
        env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                               company_id=config.company_id.id))
        rec = rec.with_env(env)
        try:
            rec.mezze_confirm(actor='user:%s' % env.uid)
        except Exception as ce:  # stale / cancelled
            return self._json(dict({'ok': False, 'error': 'qr_confirm_rejected',
                                    'message': str(ce)}, **rec.mezze_payload()), status=409)
        return dict({'ok': True}, **rec.mezze_payload())

    # ------------------------------------------------------------------ cancel
    @http.route(f'{API_PREFIX}/payment/qr/cancel', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def qr_cancel(self, qr_token=None, **kw):
        """Cancel a pending QR. No payment; order stays payable."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        rec = self._resolve_qr(env, qr_token)
        if not rec.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        denied = self._security_gate(env, 'payment/qr/cancel', target_order=rec.pos_order_id)
        if denied:
            return denied
        try:
            rec.mezze_cancel()
        except Exception as ce:  # noqa: BLE001
            return self._json({'ok': False, 'error': 'qr_cancel_rejected', 'message': str(ce)}, status=409)
        return dict({'ok': True}, **rec.mezze_payload())

    # ------------------------------------------------------------------ status
    # read-only recovery / stale re-check
    @http.route(f'{API_PREFIX}/payment/qr/status', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def qr_status(self, qr_token=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        rec = self._resolve_qr(env, qr_token)
        if not rec.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        denied = self._security_gate(env, 'payment/qr/status', target_order=rec.pos_order_id)
        if denied:
            return denied
        return dict({'ok': True}, **rec.mezze_payload())
