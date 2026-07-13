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
import json
import logging
from urllib.parse import urlencode

from odoo import SUPERUSER_ID, fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

W1_PREFIX = '/mezze/w1'
TOKEN_PARAM = 'mezze_bridge.api_token'

_AUDIT_FIELDS = {'severity', 'cashier_id', 'user_id', 'terminal_id', 'config_id',
                 'res_model', 'res_id', 'res_uuid', 'amount', 'detail'}
ROLE_RANK = {'cashier': 0, 'supervisor': 1, 'manager': 2}


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
        # Bind to the configured API user (a real POS user), NOT SUPERUSER, so
        # record rules apply. Mirrors MezzeBridgeController._api_env.
        su = request.env(user=SUPERUSER_ID)
        uid_param = su['ir.config_parameter'].get_param('mezze_bridge.api_user_id')
        if uid_param and str(uid_param).isdigit():
            uid = int(uid_param)
        else:
            api_user = (su.ref('base.user_admin', raise_if_not_found=False)
                        or su['res.users'].search([('share', '=', False), ('active', '=', True)], limit=1))
            uid = api_user.id
        return request.env(user=uid)

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

    # -- manager approval for a high-risk action -------------------------------
    @http.route(f'{W1_PREFIX}/approve', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def approve(self, action=None, code=None, pin=None, min_role='supervisor',
                config_id=None, **kw):
        """Verify a supervisor/manager authorizes a high-risk action (void,
        refund, discount override, no-sale…). Checks the approver's PIN + role,
        records the decision in the audit trail, and returns the approver so the
        caller can attach it to the action. Every attempt is audited."""
        auth = self._auth()
        if auth:
            return auth
        env = self._env()
        approver = env['mezze.cashier'].search(
            [('code', '=', code), ('active', '=', True)], limit=1)
        cfg = int(config_id) if config_id else False
        if not approver or not approver.check_pin(pin):
            env['mezze.audit.log'].log('approval.denied', severity='warning',
                                       config_id=cfg, detail='action=%s bad_pin' % action)
            return self._json({'ok': False, 'error': 'bad_credentials'}, status=401)
        if ROLE_RANK.get(approver.role, 0) < ROLE_RANK.get(min_role, 1):
            env['mezze.audit.log'].log('approval.denied', severity='warning',
                                       cashier_id=approver.id, config_id=cfg,
                                       detail='action=%s role=%s<min=%s' % (action, approver.role, min_role))
            return {'ok': False, 'error': 'insufficient_role',
                    'role': approver.role, 'min_role': min_role}
        env['mezze.audit.log'].log('approval.granted', cashier_id=approver.id,
                                   config_id=cfg, detail='action=%s' % action)
        return {'ok': True, 'approver_id': approver.id, 'approver': approver.name,
                'role': approver.role, 'action': action}

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

    # -- e-invoice submit (invoice the order -> NATIVE l10n_eg_edi_eta) ---------
    def _eta_status(self, inv):
        """Read the native ETA state off an account.move. Fields only exist when
        l10n_eg_edi_eta is installed, so probe defensively (optional dependency)."""
        if not inv or 'l10n_eg_uuid' not in inv._fields:
            return {'eta_available': False, 'cleared': False, 'eta_uuid': None,
                    'submission_number': None, 'is_signed': False}
        uuid = inv.l10n_eg_uuid or None
        return {'eta_available': True, 'cleared': bool(uuid), 'eta_uuid': uuid,
                'submission_number': inv.l10n_eg_submission_number or None,
                'is_signed': bool(getattr(inv, 'l10n_eg_is_signed', False)),
                'qr_code': getattr(inv, 'l10n_eg_qr_code', None)}

    @http.route(f'{W1_PREFIX}/einvoice/submit', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def einvoice_submit(self, order_id=None, order_uuid=None, authority='eta', **kw):
        """Invoice a POS order and hand it to Odoo's native e-invoicing. For Egypt
        the invoice is signed + cleared by ``l10n_eg_edi_eta`` (USB token + ETA
        submission); we surface its real UUID/clearance. B2C walk-ins (no customer)
        can't be invoiced — those belong to the ETA e-receipt regime, not this."""
        auth = self._auth()
        if auth:
            return auth
        env = self._env()
        order = (env['pos.order'].browse(int(order_id)) if order_id
                 else env['pos.order'].search([('uuid', '=', order_uuid)], limit=1)
                 if order_uuid else env['pos.order'])
        if not order or not order.exists():
            return self._json({'ok': False, 'error': 'order_not_found'}, status=404)
        if order.state not in ('paid', 'done', 'invoiced'):
            return {'ok': False, 'error': 'order_not_paid', 'state': order.state}
        if not order.partner_id:
            return {'ok': False, 'error': 'no_customer',
                    'note': 'ETA e-invoice needs a customer on the order. Anonymous '
                            'B2C sales use the ETA e-receipt system instead.'}
        try:
            if not order.account_move:
                order.action_pos_order_invoice()   # creates + posts the account.move
            inv = order.account_move
        except Exception as exc:  # noqa: BLE001
            _logger.exception("POS invoice for ETA failed (order %s)", order.id)
            return self._json({'ok': False, 'error': 'invoice_failed',
                               'message': str(exc)[:200]}, status=400)

        status = self._eta_status(inv)
        rec = env['mezze.einvoice'].create({
            'order_id': order.id, 'invoice_id': inv.id, 'authority': authority,
            'authority_uuid': status['eta_uuid'] or False,
            'state': 'cleared' if status['cleared']
                     else ('submitted' if status['eta_available'] else 'draft'),
        })
        env['mezze.audit.log'].log('einvoice.submit', res_model='account.move',
                                   res_id=inv.id, res_uuid=order.uuid or '',
                                   detail='authority=%s cleared=%s' % (authority, status['cleared']))
        note = None
        if not status['eta_available']:
            note = ('invoice created; install l10n_eg_edi_eta + configure an EG '
                    'company/token to sign+clear it (docs/ETA.md)')
        elif not status['cleared']:
            note = 'invoice created + queued for ETA; sign via the thumb-drive token to clear'
        return {'ok': True, 'einvoice_id': rec.id, 'invoice_id': inv.id,
                'invoice': inv.name, 'state': rec.state, **status, 'note': note}

    @http.route(f'{W1_PREFIX}/einvoice/status', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def einvoice_status(self, invoice_id=None, order_uuid=None, **kw):
        auth = self._auth()
        if auth:
            return auth
        env = self._env()
        inv = (env['account.move'].browse(int(invoice_id)) if invoice_id
               else env['pos.order'].search([('uuid', '=', order_uuid)], limit=1).account_move
               if order_uuid else env['account.move'])
        if not inv or not inv.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        return {'ok': True, 'invoice': inv.name, 'move_state': inv.state,
                **self._eta_status(inv)}

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

    # -- compensating reversal (card captured but the sale couldn't finalize) --
    @http.route(f'{W1_PREFIX}/payment/void', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def payment_void(self, reference=None, transaction_id=None, reason=None, **kw):
        """Reverse a card capture whose order never got recorded (or whose charge
        we couldn't confirm), so money is never taken with no sale. ALWAYS writes
        a CRITICAL audit row first; auto-refunds when the acquirer supports it,
        otherwise flags for manual reversal. Safe to call on a non-captured tx
        (returns noop)."""
        auth = self._auth()
        if auth:
            return auth
        env = self._env()
        tx = (env['payment.transaction'].browse(int(transaction_id)) if transaction_id
              else env['payment.transaction'].search([('reference', '=', reference)], limit=1)
              if reference else env['payment.transaction'])
        if not tx or not tx.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        env['mezze.audit.log'].log(
            'payment.reversal', severity='critical', res_model='payment.transaction',
            res_id=tx.id, res_uuid=tx.reference or '', amount=tx.amount,
            detail=json.dumps({'reason': reason or 'order_finalize_failed',
                               'state': tx.state, 'provider': tx.provider_id.code}, default=str))
        if tx.state not in ('authorized', 'done'):
            return {'ok': True, 'action': 'noop', 'state': tx.state}   # nothing captured to reverse

        def _mkrev(state):
            return env['mezze.reversal'].create({
                'transaction_id': tx.id, 'reference': tx.reference, 'amount': tx.amount,
                'reason': reason or 'order_finalize_failed', 'provider': tx.provider_id.code,
                'config_id': tx.provider_id.config_id.id if 'config_id' in tx.provider_id._fields else False,
                'state': state}).id

        if (tx.provider_id.support_refund or 'none') != 'none':
            try:
                tx.sudo()._refund()
                _mkrev('reversed')
                return {'ok': True, 'action': 'reversed', 'reference': tx.reference}
            except Exception as exc:  # noqa: BLE001
                _logger.exception("Mezze auto-reverse failed for %s", tx.reference)
                rid = _mkrev('open')
                return {'ok': False, 'action': 'auto_reverse_failed', 'flagged': True,
                        'reversal_id': rid, 'reference': tx.reference, 'message': str(exc)[:200]}
        rid = _mkrev('open')
        return {'ok': True, 'action': 'flagged_manual', 'reversal_id': rid,
                'reference': tx.reference,
                'note': 'Acquirer has no auto-refund via Odoo — reverse manually in '
                        'its dashboard. Queued for reconciliation + recorded in the audit trail.'}

    # -- reversals reconciliation queue (manager) ------------------------------
    @http.route(f'{W1_PREFIX}/reversals', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def reversals(self, state='open', config_id=None, limit=50, **kw):
        """List payment reversals for the manager queue. Defaults to OPEN ones —
        card charges reversed/flagged whose sale never recorded and that need a
        manual reconciliation."""
        auth = self._auth()
        if auth:
            return auth
        env = self._env()
        dom = []
        if state and state != 'all':
            dom.append(('state', '=', state))
        if config_id:
            dom.append(('config_id', 'in', (int(config_id), False)))
        recs = env['mezze.reversal'].search(dom, limit=int(limit))
        return {'ok': True, 'open_count': env['mezze.reversal'].search_count([('state', '=', 'open')]),
                'reversals': [{
                    'id': r.id, 'reference': r.reference, 'amount': r.amount,
                    'reason': r.reason, 'provider': r.provider, 'state': r.state,
                    'created': fields.Datetime.to_string(r.create_date),
                } for r in recs]}

    @http.route(f'{W1_PREFIX}/reversals/resolve', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def reversals_resolve(self, reversal_id=None, note=None, cashier_id=None, **kw):
        """Mark an open reversal reconciled (a manager confirmed the manual
        acquirer-side reversal). Audited."""
        auth = self._auth()
        if auth:
            return auth
        env = self._env()
        rec = env['mezze.reversal'].browse(int(reversal_id)) if reversal_id else env['mezze.reversal']
        if not rec.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        who = None
        if cashier_id and str(cashier_id).isdigit():
            who = env['mezze.cashier'].browse(int(cashier_id))
            who = who.name if who.exists() else None
        rec.write({'state': 'resolved', 'resolved_by': who or 'staff', 'resolved_note': note or False})
        env['mezze.audit.log'].log('reversal.resolved', severity='warning',
                                   res_model='mezze.reversal', res_id=rec.id,
                                   amount=rec.amount, detail='ref=%s by=%s' % (rec.reference, who or 'staff'))
        return {'ok': True, 'id': rec.id, 'state': rec.state}

    # -- which tenders are actually live (an enabled acquirer backs them) ------
    @http.route(f'{W1_PREFIX}/payment/methods', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def payment_methods(self, **kw):
        """Tell the POS which non-cash tenders are backed by an enabled Odoo
        payment.provider, so the UI can gate dead buttons instead of faking a
        charge. Cash is always live."""
        auth = self._auth()
        if auth:
            return auth
        env = self._env()
        live = set()
        for p in env['payment.provider'].search([('state', 'in', ('enabled', 'test'))]):
            if p.code == 'paymob':
                live.update(['card', 'wallet'])   # Paymob aggregates card + wallets (incl. Fawry)
            else:
                live.add('card')
        return {'ok': True, 'live': sorted(live)}

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
