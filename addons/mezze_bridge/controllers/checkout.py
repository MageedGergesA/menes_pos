"""S2C-5 — Online customer payment: channel → draft order → NATIVE pay page.

Public, tokenized customer endpoints that create a channel draft order with
SERVER-AUTHORITATIVE pricing + availability/zone revalidation, then hand the
customer to Odoo's NATIVE online-payment page (/pos/pay/<id>?access_token). Odoo
owns provider selection, redirect, HMAC/notification, and the exactly-once
tx→pos.payment finalization; Mezze fires the kitchen once on paid (pay-before-fire,
in models/mezze_online_payment.py) and exposes a safe status. No card fields, no
Mezze payment engine, no client-trusted amount.
"""
import secrets

import werkzeug.urls

from odoo import fields, http
from odoo.http import request

from .main import MezzeBridgeController, API_PREFIX, _reraise_if_retryable


class MezzeCheckoutController(MezzeBridgeController):

    # ------------------------------------------------------------------ helpers
    def _checkout_context(self, env, qr=None, store=None):
        """Resolve the customer's channel to (config, table|None). A spoofed
        table_id/config is never trusted — only the opaque QR/store token."""
        if qr:
            table = self._qr_resolve(env, None, qr)
            config = self._qr_config(env, table)
            if not config:
                raise ValueError("This table is not open for orders.")
            return config, table
        if store:
            return self._store_config(env, store), None
        raise ValueError("Missing table/store token.")

    def _revalidate_available(self, env, config, lines):
        """Reject if any line's product is 86'd / unavailable on this branch —
        BEFORE any order or payment is created (§10)."""
        blocked = self._eightysix_ids(env, config.id)
        for ln in (lines or []):
            pid = int(ln.get('product_id'))
            prod = env['product.product'].browse(pid)
            if not prod.exists() or not prod.active or not prod.available_in_pos or pid in blocked:
                raise ValueError("An item is no longer available. Please review your cart.")

    # ------------------------------------------------------------------ create
    @http.route(f'{API_PREFIX}/checkout/online/create', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def checkout_create(self, qr=None, store=None, fulfillment='pickup', lines=None,
                        guests=None, who=None, phone=None, address=None, zone_id=None, **kw):
        """Create a DRAFT customer order (no kitchen fire yet) with server-
        authoritative pricing + availability/zone revalidation, ready to be paid
        online. Returns a status token — never a raw order id."""
        env = self._api_env()
        try:
            config, table = self._checkout_context(env, qr, store)
            if not lines:
                return self._json({'ok': False, 'error': 'no_lines'}, status=400)
            lines = self._sanitize_customer_lines(lines)   # S4 §63 no client price/discount
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            config = config.with_env(env)
            self._revalidate_available(env, config, lines)
            session = self._ensure_open_session(env, config)
            channel = 'qr' if table else ('delivery' if fulfillment == 'delivery' else 'pickup')

            if channel in ('qr', 'pickup'):
                # A fresh order per checkout attempt (a deterministic cart hash would
                # collide with an earlier PAID order of the same items).
                uuid = 'chk-%s' % secrets.token_hex(8)
                fire_uuid = 'online:%s' % uuid
                result = self._do_fire(env, uuid, session, config, table.id if table else None,
                                       lines, None, guests, fire_uuid,
                                       server_override='Online %s' % channel, defer_fire=True)
                order = env['pos.order'].browse(result['order_id'])
            else:
                order = self._online_delivery_draft(env, config, session, lines, who, phone,
                                                    address, zone_id)

            order.sudo().write({'mezze_online': True, 'mezze_channel': channel})
            token = order._mezze_ensure_status_token() or ''
            prec = order.currency_id.decimal_places or 2
            self._audit(env, 'checkout.create', order, **self._actor(env, kw))
            return {'ok': True, 'status_token': token, 'channel': channel,
                    'amount_total': round(order.amount_total, prec),
                    'currency': order.currency_id.name}
        except ValueError as ve:
            return self._json({'ok': False, 'error': 'checkout_rejected', 'message': str(ve)}, status=400)
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            return self._json({'ok': False, 'error': 'checkout_failed', 'message': str(exc)}, status=400)

    def _online_delivery_draft(self, env, config, session, lines, who, phone, address, zone_id):
        """Build an UNPAID delivery draft (zone min + fee enforced server-side); no
        payment, no fire. Invalid zone / below-minimum ⇒ raises (no order created)."""
        if not address:
            raise ValueError("A delivery address is required.")
        order_lines, base, incl = self._build_lines(env, config, env['res.partner'], lines)
        zone = env['mezze.delivery.zone'].browse(int(zone_id)) if zone_id else env['mezze.delivery.zone']
        if not zone or not zone.exists():
            raise ValueError("Please choose a valid delivery zone.")
        if zone.min_order and incl < zone.min_order:
            raise ValueError("Order %.2f is below the %s minimum of %.2f"
                             % (incl, zone.name, zone.min_order))
        fee = zone.fee or 0.0
        if fee > 0:
            fp = self._delivery_fee_product(env)
            order_lines.append((0, 0, {'product_id': fp.id, 'qty': 1, 'price_unit': fee,
                                       'discount': 0.0, 'tax_ids': [(6, 0, [])],
                                       'price_subtotal': fee, 'price_subtotal_incl': fee,
                                       'pack_lot_ids': []}))
            incl += fee
            base += fee
        uuid = 'chk-dlv-%s' % secrets.token_hex(8)
        env['pos.order'].sync_from_ui([{
            'uuid': uuid, 'session_id': session.id, 'company_id': config.company_id.id,
            'user_id': env.uid, 'pricelist_id': config.pricelist_id.id or False,
            'name': 'Mezze %s' % uuid, 'state': 'draft',
            'date_order': fields.Datetime.to_string(fields.Datetime.now()),
            'lines': order_lines, 'amount_tax': incl - base, 'amount_total': incl,
            'amount_paid': 0.0, 'amount_return': 0.0,
            'last_order_preparation_change': '{}', 'to_invoice': False}])
        order = env['pos.order'].search([('uuid', '=', uuid)], limit=1)
        env['mezze.delivery'].create({
            'pos_order_id': order.id, 'customer_name': who or 'Online customer',
            'phone': phone or False, 'address': address, 'fee': fee,
            'zone_id': zone.id})
        return order

    # ------------------------------------------------------------------ pay
    @http.route(f'{API_PREFIX}/checkout/online/pay', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def checkout_pay(self, status_token=None, **kw):
        """Return the NATIVE online-payment page URL for the customer's order, after
        a final server-authoritative revalidation. No payment is taken here — Odoo's
        pay page owns provider selection / redirect / notification."""
        env = self._api_env()
        try:
            order = env['pos.order']._mezze_resolve_status_token(status_token)
            if not order:
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            if order.state != 'draft':
                # already paid/settled — nothing to pay
                return {'ok': True, 'already': True, 'status_token': status_token,
                        'status': order.mezze_online_status()}
            config = order.config_id
            env2 = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                    company_id=config.company_id.id))
            order = order.with_env(env2)
            # final availability revalidation just before payment
            self._revalidate_available(env2, config,
                                       [{'product_id': l.product_id.id} for l in order.lines
                                        if (l.price_unit or 0) > 0 and l.qty > 0])
            # Ensure/locate the config's online-payment method (native rule: it must
            # be on the config, provisioned when no session is open — see the model).
            try:
                env2['pos.payment.method']._mezze_get_or_create_online_method(config)
            except Exception:  # noqa: BLE001 — never crash the customer flow
                pass
            method = config.payment_method_ids.filtered('is_online_payment')[:1]
            providers = method._get_online_payment_providers(config.id, error_if_invalid=False) \
                if method else self.env['payment.provider']
            if not method or not providers:
                return self._json({'ok': False, 'error': 'online_not_configured',
                                   'message': 'Online payment is not available for this branch.'}, status=409)
            order.sudo()._ensure_access_token()
            exit_route = '/checkout/s/%s' % status_token
            pay_url = '/pos/pay/%s?%s' % (order.id, werkzeug.urls.url_encode({
                'access_token': order.sudo().access_token, 'exit_route': exit_route}))
            return {'ok': True, 'pay_url': pay_url, 'status_token': status_token,
                    'amount_due': round(order.amount_total - order.amount_paid,
                                        order.currency_id.decimal_places or 2),
                    'currency': order.currency_id.name}
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            return self._json({'ok': False, 'error': 'pay_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------ table pay
    @http.route(f'{API_PREFIX}/checkout/table/pay_online', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def checkout_table_pay(self, table_id=None, qr=None, **kw):
        """Pay a dine-in QR table's OPEN bill online. The table order already exists
        (and its kitchen already fired at order time — this is a settle, not
        pay-before-fire). Returns the native /pos/pay URL after revalidation."""
        env = self._api_env()
        try:
            table = self._qr_resolve(env, table_id, qr)
            config = self._qr_config(env, table)
            if not config:
                return self._json({'ok': False, 'error': 'no_pos_config'}, status=404)
            env2 = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                    company_id=config.company_id.id))
            config = config.with_env(env2)
            session = self._ensure_open_session(env2, config)
            order = self._qr_open_order(env2, table, session)
            if not order or order.state != 'draft':
                return self._json({'ok': False, 'error': 'no_open_bill',
                                   'message': 'There is nothing to pay for this table yet.'}, status=404)
            try:
                env2['pos.payment.method']._mezze_get_or_create_online_method(config)
            except Exception:  # noqa: BLE001
                pass
            method = config.payment_method_ids.filtered('is_online_payment')[:1]
            providers = method._get_online_payment_providers(config.id, error_if_invalid=False) \
                if method else self.env['payment.provider']
            if not method or not providers:
                return self._json({'ok': False, 'error': 'online_not_configured',
                                   'message': 'Online payment is not available for this branch.'}, status=409)
            order.sudo()._ensure_access_token()
            pay_url = '/pos/pay/%s?%s' % (order.id, werkzeug.urls.url_encode(
                {'access_token': order.sudo().access_token}))
            return {'ok': True, 'pay_url': pay_url, 'order_id': order.id,
                    'amount_due': round(order.amount_total - order.amount_paid,
                                        order.currency_id.decimal_places or 2),
                    'currency': order.currency_id.name}
        except ValueError as ve:
            return self._json({'ok': False, 'error': 'table_pay_rejected', 'message': str(ve)}, status=400)
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            return self._json({'ok': False, 'error': 'pay_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------ status page (HTML)
    @http.route('/checkout/s/<string:status_token>', type='http', auth='public',
                methods=['GET'], website=False, sitemap=False)
    def checkout_status_page(self, status_token=None, **kw):
        """Server-rendered customer status hub (native i18n → Arabic/RTL, mobile,
        dark). It only DISPLAYS the authoritative status polled from /checkout/status;
        it never decides payment. The card entry is Odoo's native /pos/pay page."""
        order = request.env['pos.order'].sudo()._mezze_resolve_status_token(status_token)
        if not order:
            return request.not_found()
        # allow the customer's language to carry over (?lang=ar_001) → native RTL/i18n
        lang = kw.get('lang')
        if lang and request.env['res.lang'].sudo().search_count(
                [('code', '=', lang), ('active', '=', True)]):
            request.update_context(lang=lang)
        return request.render('mezze_bridge.checkout_status', {'token': status_token})

    # ------------------------------------------------------------------ status
    @http.route(f'{API_PREFIX}/checkout/status', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def checkout_status(self, status_token=None, **kw):
        """Authoritative customer status (order + payment.transaction state). The
        browser return URL NEVER decides this. Rate-limited against guessing."""
        env = self._api_env()
        try:
            allowed, _retry, _c = env['mezze.rate.limit'].hit(
                'checkout_status:%s' % (status_token or '')[:16], 40, 60)
            if not allowed:
                return self._json({'ok': False, 'error': 'rate_limited'}, status=429)
        except Exception:  # noqa: BLE001
            pass
        order = env['pos.order']._mezze_resolve_status_token(status_token)
        if not order:
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        data = order.mezze_online_status()
        data['public_status'] = order.mezze_public_status()
        return dict({'ok': True}, **data)
