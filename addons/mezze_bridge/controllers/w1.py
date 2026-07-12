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

    # -- payment intent (real PSP = TODO) --------------------------------------
    @http.route(f'{W1_PREFIX}/payment/intent', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def payment_intent(self, order_uuid=None, tender='card', amount=0.0,
                       config_id=None, **kw):
        auth = self._auth()
        if auth:
            return auth
        env = self._env()
        domain = [('tender', '=', tender), ('active', '=', True)]
        if config_id:
            domain.append(('config_id', 'in', (int(config_id), False)))
        provider = env['mezze.payment.provider'].search(domain, limit=1)
        if not provider:
            return {'ok': False, 'error': 'no_live_provider', 'tender': tender,
                    'note': 'No acquirer configured for this tender (docs/W1.md §2).'}
        txn = env['mezze.payment.transaction'].create({
            'provider_id': provider.id, 'order_uuid': order_uuid,
            'amount': float(amount or 0.0), 'kind': 'charge', 'state': 'pending',
        })
        # TODO(w1): drive the real acquirer (Paymob/Fawry/HyperPay): create the
        # intent, return the redirect/token, capture on the callback endpoint.
        return {'ok': True, 'transaction_id': txn.id, 'state': txn.state,
                'provider': provider.code}

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
