# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Wave 1 — "can we legally sell it?" endpoints (SCAFFOLD).

See ``docs/W1.md``. Structure is live; the external-authority seams (ETA/ZATCA
submit, PSP charge/capture) are ``TODO`` and return honest "pending / not
cleared" so the UI can never print a fake cleared invoice or complete a fake
card sale.

  * /mezze/w1/cashier/login   — PIN auth, returns a cashier session (working)
  * /mezze/w1/audit/log       — append an audit row (working)
  * /mezze/w1/einvoice/submit — create + 'submit' an e-invoice (real ETA = TODO)
  * /mezze/w1/payment/intent  — open a card/wallet transaction (real PSP = TODO)
  * /mezze/w1/config/tax      — read the branch tax profile from config (working)
"""
import logging
from urllib.parse import urlencode

from odoo import SUPERUSER_ID, http
from odoo.http import request

_logger = logging.getLogger(__name__)

W1_PREFIX = '/mezze/w1'
TOKEN_PARAM = 'mezze_bridge.api_token'

_AUDIT_FIELDS = {'severity', 'cashier_id', 'user_id', 'terminal_id', 'config_id',
                 'res_model', 'res_id', 'res_uuid', 'amount', 'detail'}


class MezzeW1Controller(http.Controller):

    def _json(self, payload, status=200):
        return request.make_json_response(payload, status=status)

    def _auth(self):
        expected = request.env['ir.config_parameter'].sudo().get_param(TOKEN_PARAM)
        provided = (request.httprequest.headers.get('X-Mezze-Token')
                    or request.params.get('token'))
        if not expected:
            return self._json({'ok': False, 'error': 'server_token_unset'}, status=503)
        if not provided or provided != expected:
            return self._json({'ok': False, 'error': 'unauthorized'}, status=401)
        return None

    def _env(self):
        # Scaffold: superuser. Production must reuse the bridge's _api_env (a real
        # POS user) — see docs/W1.md §3.
        return request.env(user=SUPERUSER_ID)

    # -- cashier PIN login -----------------------------------------------------
    @http.route(f'{W1_PREFIX}/cashier/login', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def cashier_login(self, code=None, pin=None, config_id=None, **kw):
        auth = self._auth()
        if auth:
            return auth
        env = self._env()
        cashier = env['mezze.cashier'].search(
            [('code', '=', code), ('active', '=', True)], limit=1)
        if not cashier or not cashier.check_pin(pin):
            env['mezze.audit.log'].log('cashier.login_failed', severity='warning',
                                       detail='code=%s' % code)
            return self._json({'ok': False, 'error': 'bad_credentials'}, status=401)
        env['mezze.audit.log'].log('cashier.login', cashier_id=cashier.id,
                                   config_id=int(config_id) if config_id else False)
        return {'ok': True, 'cashier_id': cashier.id, 'name': cashier.name,
                'role': cashier.role}

    # -- audit append ----------------------------------------------------------
    @http.route(f'{W1_PREFIX}/audit/log', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def audit_log(self, event=None, **kw):
        auth = self._auth()
        if auth:
            return auth
        if not event:
            return self._json({'ok': False, 'error': 'missing_event'}, status=400)
        env = self._env()
        vals = {k: v for k, v in kw.items() if k in _AUDIT_FIELDS}
        rec = env['mezze.audit.log'].log(event, **vals)
        return {'ok': True, 'id': rec.id if rec else None}

    # -- e-invoice submit (real ETA/ZATCA = TODO) ------------------------------
    @http.route(f'{W1_PREFIX}/einvoice/submit', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def einvoice_submit(self, order_id=None, authority='eta', **kw):
        auth = self._auth()
        if auth:
            return auth
        env = self._env()
        inv = env['mezze.einvoice'].create({
            'order_id': int(order_id) if order_id else False,
            'authority': authority, 'state': 'draft',
        })
        # TODO(w1): real authority call here — ETA clearance (device/token signed
        # document, POST, poll) or ZATCA Phase-2 cryptographic stamp. On success:
        # set authority_uuid, qr_payload, cleared_at, state='cleared'. Until then
        # we return cleared=False so the receipt shows NO fake clearance badge.
        env['mezze.audit.log'].log('einvoice.submit', res_model='pos.order',
                                   res_id=inv.order_id.id, detail='authority=%s' % authority)
        return {'ok': True, 'einvoice_id': inv.id, 'state': inv.state,
                'cleared': False, 'note': 'authority integration pending (docs/W1.md §1)'}

    # -- payment intent (delegates to NATIVE payment_paymob) -------------------
    @http.route(f'{W1_PREFIX}/payment/intent', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def payment_intent(self, order_uuid=None, amount=0.0, partner_id=None,
                       config_id=None, **kw):
        """Open a card/wallet charge by REUSING Odoo's native Paymob acquirer
        (module ``payment_paymob``). We create a real ``payment.transaction`` and
        return its unified-checkout URL; Paymob's own HMAC-verified webhook
        (``/payment/paymob/webhook``) confirms capture. No hand-rolled crypto.
        See docs/PAYMOB.md."""
        auth = self._auth()
        if auth:
            return auth
        env = self._env()
        provider = env['payment.provider'].search(
            [('code', '=', 'paymob'), ('state', 'in', ('enabled', 'test'))], limit=1)
        if not provider:
            return {'ok': False, 'error': 'no_paymob_provider',
                    'note': 'Enable a Paymob provider in Odoo (Accounting → '
                            'Configuration → Payment Providers). See docs/PAYMOB.md.'}
        amount = float(amount or 0.0)
        if amount <= 0:
            return self._json({'ok': False, 'error': 'bad_amount'}, status=400)

        partner = (env['res.partner'].browse(int(partner_id))
                   if partner_id else env.company.partner_id)
        pm = provider.payment_method_ids[:1] or env['payment.method'].search(
            [('code', '=', 'card')], limit=1)
        ref = env['payment.transaction']._compute_reference(
            provider.code, prefix=(order_uuid or 'MEZZE'))
        tx = env['payment.transaction'].create({
            'provider_id': provider.id,
            'payment_method_id': pm.id,
            'reference': ref,
            'amount': amount,
            'currency_id': env.company.currency_id.id,
            'partner_id': partner.id,
            'operation': 'online_redirect',
        })
        # Link on the Mezze side for POS reconciliation (best-effort).
        try:
            env['mezze.payment.transaction'].create({
                'order_uuid': order_uuid, 'amount': amount,
                'currency': env.company.currency_id.name, 'kind': 'charge',
                'state': 'pending', 'provider_reference': ref,
                'payment_transaction_id': tx.id})
        except Exception:  # noqa: BLE001
            _logger.exception("Mezze payment link create failed")
        # Ask the native provider for the unified-checkout URL (hits Paymob; needs
        # real credentials configured on the provider).
        try:
            pv = tx._get_processing_values()
            api_url = pv.get('api_url')
            checkout = None
            if api_url:
                params = pv.get('url_params') or {}
                checkout = api_url + ('?' + urlencode(params) if params else '')
            return {'ok': True, 'reference': ref, 'transaction_id': tx.id,
                    'state': tx.state, 'checkout_url': checkout,
                    'rendered': bool(checkout)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Paymob rendering failed for %s", ref)
            return {'ok': True, 'reference': ref, 'transaction_id': tx.id,
                    'state': tx.state, 'checkout_url': None, 'rendered': False,
                    'note': 'transaction created; checkout needs valid Paymob '
                            'credentials on the provider: %s' % str(exc)[:150]}

    # -- payment status (poll the native transaction) --------------------------
    @http.route(f'{W1_PREFIX}/payment/status', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def payment_status(self, reference=None, transaction_id=None, **kw):
        auth = self._auth()
        if auth:
            return auth
        env = self._env()
        tx = (env['payment.transaction'].browse(int(transaction_id))
              if transaction_id
              else env['payment.transaction'].search([('reference', '=', reference)], limit=1))
        if not tx or not tx.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        return {'ok': True, 'reference': tx.reference, 'state': tx.state,
                'amount': tx.amount, 'provider_reference': tx.provider_reference or ''}

    # -- tax profile (config-driven; unhardcode 12/14) -------------------------
    @http.route(f'{W1_PREFIX}/config/tax', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def config_tax(self, config_id=None, **kw):
        auth = self._auth()
        if auth:
            return auth
        env = self._env()
        icp = env['ir.config_parameter'].sudo()

        def rate(tid):
            if tid and str(tid).isdigit():
                t = env['account.tax'].browse(int(tid))
                if t.exists():
                    return {'id': t.id, 'name': t.name, 'amount': t.amount}
            return None

        return {'ok': True,
                'service': rate(icp.get_param('mezze_bridge.tax_service_id')),
                'vat': rate(icp.get_param('mezze_bridge.tax_vat_id')),
                'note': 'Set ir.config_parameter mezze_bridge.tax_service_id / '
                        'tax_vat_id per company to unhardcode the 12/14 chain.'}
