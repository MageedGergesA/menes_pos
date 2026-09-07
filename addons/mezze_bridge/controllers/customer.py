"""S2C-6 — Customer Account cashier endpoints (search / summary / deposit / settle).

Customer selector + a SAFE account summary (native exposure/limit — no ledger/PII
dump), plus deposit and debt-settlement recorded as NATIVE inbound customer
account.payment against a real cash/bank journal (see models/mezze_customer_credit.py).
Authenticated (terminal token), branch-scoped; no customer balance is invented.
"""
from odoo import http

from .main import MezzeBridgeController, API_PREFIX, _reraise_if_retryable


class MezzeCustomerController(MezzeBridgeController):

    def _mask_phone(self, phone):
        p = (phone or '').strip()
        if len(p) <= 4:
            return p
        return '••••' + p[-4:]

    # ------------------------------------------------------------------ search
    @http.route(f'{API_PREFIX}/customer/search', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def customer_search(self, query=None, config_id=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        q = (query or '').strip()
        dom = [('customer_rank', '>', 0)]
        if q:
            # Odoo 19 dropped res.partner.mobile (folded into phone) — search name/phone.
            dom = ['|', ('name', 'ilike', q), ('phone', 'ilike', q)]
        partners = env['res.partner'].sudo().search(dom, limit=20)
        # Points and tags come back with the RESULTS, not only after attaching.
        # The design shows both on every row (`{{ g.pts }}`, the tag chip) because
        # a cashier picking between two regulars needs to tell them apart BEFORE
        # committing one to the check — afterwards is too late to be useful.
        #
        # Read through the same `_loyalty_card` every other loyalty path uses, and
        # with create=False: looking someone up must never mint a card as a side
        # effect of typing three letters into a search box.
        prog = self._loyalty_program(env)
        points = {}
        if prog:
            for card in env['loyalty.card'].sudo().search(
                    [('program_id', '=', prog.id), ('partner_id', 'in', partners.ids)]):
                points[card.partner_id.id] = card.points
        return {'ok': True, 'customers': [{
            'id': p.id, 'name': p.name, 'phone': self._mask_phone(p.phone),
            'is_company': p.is_company,
            'commercial': p.commercial_partner_id.name if p.commercial_partner_id != p else '',
            'points': points.get(p.id, 0.0),
            # Free-form partner tags (VIP, an allergy). Shown as a chip so a
            # server reads it before the guest has to say it again.
            'tags': p.category_id.mapped('name'),
        } for p in partners]}

    # ------------------------------------------------------------------ create
    @http.route(f'{API_PREFIX}/customer/create', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def customer_create(self, name=None, phone=None, email=None, config_id=None, **kw):
        """Create a walk-in customer from the till.

        The Register could only ever SEARCH partners, so a guest who had never been
        served before could not be attached to an order at all. This WRITES, hence
        readonly=False and ORDERS_WRITE rather than the ORDERS_READ that search uses.

        customer_rank=1 is what customer_search filters on, so a guest created here is
        findable afterwards instead of vanishing from the very list they came from.
        """
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        nm = (name or '').strip()
        if not nm:
            return self._json({'ok': False, 'error': 'name_required'}, status=400)
        ph = (phone or '').strip()
        em = (email or '').strip()
        # Don't silently mint a duplicate: the same name AND phone is the same guest.
        # Without a phone, a name alone is weak evidence, so the match is confined to
        # existing CUSTOMERS — otherwise a walk-in called "Ahmed Ali" could be attached
        # to a same-named supplier or employee contact and bill the wrong account.
        dom = (['&', ('name', '=ilike', nm), ('phone', '=', ph)] if ph
               else ['&', ('name', '=ilike', nm), ('customer_rank', '>', 0)])
        existing = env['res.partner'].sudo().search(dom, limit=1)
        if existing:
            partner = existing
            fill = {}
            if ph and not partner.phone:
                fill['phone'] = ph
            if em and not partner.email:
                fill['email'] = em
            if not partner.customer_rank:
                fill['customer_rank'] = 1
            if fill:
                partner.write(fill)
        else:
            vals = {'name': nm, 'customer_rank': 1}
            if ph:
                vals['phone'] = ph
            if em:
                vals['email'] = em
            partner = env['res.partner'].sudo().create(vals)
        return {'ok': True, 'existing': bool(existing), 'customer': {
            'id': partner.id, 'name': partner.name,
            'phone': self._mask_phone(partner.phone),
            'is_company': partner.is_company,
            'commercial': (partner.commercial_partner_id.name
                           if partner.commercial_partner_id != partner else ''),
        }}

    # ------------------------------------------------------------------ summary
    @http.route(f'{API_PREFIX}/customer/summary', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def customer_summary(self, partner_id=None, config_id=None, amount=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        partner = env['res.partner'].sudo().browse(int(partner_id)) if partner_id else None
        if not partner or not partner.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        config = self._resolve_config(env, config_id)
        pos = partner._mezze_credit_position(config.company_id, config, extra=float(amount or 0.0))
        return dict({'ok': True}, **pos)

    # ------------------------------------------------------------------ deposit
    @http.route(f'{API_PREFIX}/customer/deposit', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def customer_deposit(self, partner_id=None, amount=None, payment_method_id=None,
                         config_id=None, **kw):
        """Deposit money to a customer account via a REAL received tender (cash/bank).
        Records a native inbound account.payment → available credit. No sales revenue."""
        auth = self._authorize('customer/deposit')
        if auth:
            return auth
        return self._customer_payment(partner_id, amount, payment_method_id, config_id,
                                      settle=False, kw=kw)

    # ------------------------------------------------------------------ settle
    @http.route(f'{API_PREFIX}/customer/settle', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def customer_settle(self, partner_id=None, amount=None, payment_method_id=None,
                        config_id=None, **kw):
        """Settle a customer's outstanding due via a REAL tender (cash/bank). Native
        inbound account.payment reconciled against the receivable (partial or full)."""
        auth = self._authorize('customer/settle')
        if auth:
            return auth
        return self._customer_payment(partner_id, amount, payment_method_id, config_id,
                                      settle=True, kw=kw)

    def _customer_payment(self, partner_id, amount, payment_method_id, config_id, settle, kw):
        env = self._api_env()
        try:
            partner = env['res.partner'].sudo().browse(int(partner_id)) if partner_id else None
            if not partner or not partner.exists():
                return self._json({'ok': False, 'error': 'customer_required',
                                   'message': 'A customer is required.'}, status=400)
            config = self._resolve_config(env, config_id)
            amt = round(float(amount or 0.0), config.currency_id.decimal_places or 2)
            if amt <= 0:
                return self._json({'ok': False, 'error': 'invalid_amount',
                                   'message': 'Amount must be positive.'}, status=400)
            pm = env['pos.payment.method'].sudo().browse(int(payment_method_id)) if payment_method_id else None
            journal = pm.journal_id if pm else None
            if not journal or journal.type not in ('cash', 'bank'):
                return self._json({'ok': False, 'error': 'invalid_tender',
                                   'message': 'Deposits/settlements need a cash or bank method.'}, status=400)
            company = config.company_id
            env2 = env(context=dict(env.context, allowed_company_ids=[company.id], company_id=company.id))
            pay = partner.with_env(env2)._mezze_customer_payment(
                company, amt, journal.with_env(env2), memo=('Settlement' if settle else 'Account deposit'),
                settle=settle)
            pos = partner._mezze_credit_position(company, config)
            self._audit(env, 'customer.settle' if settle else 'customer.deposit', None,
                        **self._actor(env, kw),
                        detail='{"customer":%d,"amount":%s,"method":%r,"payment":%d}'
                               % (partner.commercial_partner_id.id, amt, pm.name, pay.id))
            return {'ok': True, 'payment_id': pay.id, 'kind': 'settle' if settle else 'deposit',
                    'amount': amt, 'method': pm.name, 'summary': pos}
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            return self._json({'ok': False, 'error': 'customer_payment_failed',
                               'message': str(exc)}, status=400)
