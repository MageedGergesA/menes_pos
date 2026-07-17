# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Delivery-aggregator webhooks (Talabat / Jahez / …).

Ingests prepaid aggregator orders as real paid ``pos.order`` + ``mezze.delivery``
+ KDS tickets, reusing the on-premise delivery path's helpers. See the models in
``models/aggregator.py`` for the data model and the normalised contract below.

Security model (money path — gated hard):
  * Each channel (``mezze.aggregator``) holds a per-aggregator ``secret``.
  * The webhook body is signed ``X-Mezze-Signature: <hex hmac-sha256(secret,
    raw_body)>``. Unsigned / mis-signed / secret-unset requests are refused.
  * Idempotent on (aggregator, external_id): a retry returns the first result,
    never a second order.
  * An item whose SKU isn't mapped REJECTS the whole order (state=rejected) —
    we never silently drop a line or guess a product.

Normalised webhook body (POST /mezze/aggregator/<code>/webhook):
  {"external_id","event":"order.new"|"order.cancel","config_id"?,
   "customer":{"name","phone","address"},
   "items":[{"sku","qty","price"?,"note"?}], "totals":{"gross"?}}
Each real aggregator's payload/signature is normalised to this by a thin shim
once its partner API spec + credentials exist (TODO, like the ETA/PSP legs).

The status-push-OUT leg (telling the aggregator accepted/ready/dispatched) needs
each aggregator's live API creds and is a documented scaffold — ``_notify`` logs
the intent and returns honestly rather than faking a call.
"""
import hashlib
import hmac
import json
import logging

from odoo import fields, http
from odoo.http import request

from .main import MezzeBridgeController

_logger = logging.getLogger(__name__)

AGG_PREFIX = '/mezze/aggregator'


class MezzeAggregatorController(http.Controller):

    # helpers from the main bridge controller (order building, tickets, audit…)
    _bridge = MezzeBridgeController()

    def _json(self, payload, status=200):
        return request.make_json_response(payload, status=status)

    def _resolve_channel(self, env, code, config_id=None):
        """Find the (active) aggregator channel for this code, disambiguated by
        branch when more than one exists. Returns (channel, error_response)."""
        dom = [('code', '=', code), ('active', '=', True)]
        channels = env['mezze.aggregator'].sudo().search(dom)
        if not channels:
            return None, self._json({'ok': False, 'error': 'unknown_aggregator'}, status=404)
        if config_id:
            ch = channels.filtered(lambda c: c.config_id.id == int(config_id))
            if not ch:
                return None, self._json({'ok': False, 'error': 'unknown_branch'}, status=404)
            return ch[:1], None
        if len(channels) > 1:
            return None, self._json({'ok': False, 'error': 'ambiguous_branch',
                                     'message': 'Multiple branches for this aggregator; send config_id.'}, status=400)
        return channels[:1], None

    def _verify(self, channel, raw):
        """Constant-time HMAC-SHA256 check of the raw body against the channel
        secret. Returns an error response, or None when valid."""
        if not channel.secret:
            return self._json({'ok': False, 'error': 'secret_unset'}, status=503)
        provided = (request.httprequest.headers.get('X-Mezze-Signature')
                    or request.params.get('sig') or '')
        expected = hmac.new(channel.secret.encode(), raw, hashlib.sha256).hexdigest()
        if not provided or not hmac.compare_digest(provided, expected):
            return self._json({'ok': False, 'error': 'bad_signature'}, status=401)
        return None

    def _notify(self, channel, agg_order, status):
        """Push a status back to the aggregator. SCAFFOLD: the real per-aggregator
        API call needs live creds/endpoint; we log the intent so the outbound leg
        is visible and never silently pretends to have notified."""
        _logger.info("Mezze aggregator %s: would notify order %s -> %s (API leg TODO)",
                     channel.code, agg_order.external_id, status)
        return False

    @http.route(f'{AGG_PREFIX}/<string:code>/webhook', type='http', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def webhook(self, code, **kw):
        raw = request.httprequest.get_data(as_text=False) or b''
        try:
            body = json.loads(raw.decode() or '{}')
        except (ValueError, UnicodeDecodeError):
            return self._json({'ok': False, 'error': 'bad_json'}, status=400)

        env = self._bridge._api_env()
        channel, err = self._resolve_channel(env, code, body.get('config_id'))
        if err:
            return err
        err = self._verify(channel, raw)
        if err:
            return err

        event = body.get('event') or 'order.new'
        external_id = body.get('external_id')
        if not external_id:
            return self._json({'ok': False, 'error': 'missing_external_id'}, status=400)

        if event == 'order.cancel':
            return self._cancel(env, channel, external_id)
        if event == 'order.new':
            return self._ingest(env, channel, external_id, body, raw)
        return self._json({'ok': False, 'error': 'unknown_event', 'event': event}, status=400)

    # -- order.new -------------------------------------------------------------
    def _ingest(self, env, channel, external_id, body, raw):
        AggOrder = env['mezze.aggregator.order'].sudo()
        existing = AggOrder._find(channel, external_id)
        if existing:  # idempotent replay — never create a second order
            return self._json({'ok': True, 'idempotent': True,
                               'state': existing.state,
                               'order_id': existing.pos_order_id.id or None,
                               'aggregator_order_id': existing.id})

        config = channel.config_id
        env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                               company_id=config.company_id.id))
        config = config.with_env(env)
        channel = channel.with_env(env)

        customer = body.get('customer') or {}
        items = body.get('items') or []

        # Map every SKU first — an unmapped item rejects the whole order.
        Map = env['mezze.aggregator.product.map'].sudo()
        lines, unmapped = [], []
        for it in items:
            sku = str(it.get('sku') or '')
            m = Map.search([('aggregator_id', '=', channel.id), ('external_sku', '=', sku)], limit=1)
            if not m:
                unmapped.append(sku)
                continue
            line = {'product_id': m.product_id.id, 'qty': float(it.get('qty', 1.0) or 1.0)}
            if it.get('price') is not None:
                line['price_unit'] = float(it['price'])
            lines.append(line)

        if unmapped or not lines:
            reason = 'unmapped_skus' if unmapped else 'no_items'
            agg = AggOrder.create({
                'aggregator_id': channel.id, 'external_id': external_id,
                'state': 'rejected', 'reject_reason': reason,
                'unmapped_skus': ','.join(unmapped) or False,
                'customer_name': customer.get('name'), 'phone': customer.get('phone'),
                'address': customer.get('address'),
                'raw_payload': raw.decode(errors='replace'),
            })
            self._bridge._audit(env, 'aggregator.reject', severity='warning',
                                config_id=config.id, res_model='mezze.aggregator.order',
                                res_id=agg.id, res_uuid=external_id,
                                detail=json.dumps({'aggregator': channel.code, 'reason': reason,
                                                   'unmapped_skus': unmapped}))
            return self._json({'ok': False, 'error': reason, 'unmapped_skus': unmapped,
                               'aggregator_order_id': agg.id}, status=422)

        try:
            order, dlv, incl = self._create_order(env, channel, config, external_id, lines, customer)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze aggregator ingest failed for %s/%s", channel.code, external_id)
            return self._json({'ok': False, 'error': 'ingest_failed', 'message': str(exc)}, status=400)

        gross = float((body.get('totals') or {}).get('gross') or incl)
        commission = round(gross * (channel.commission_pct or 0.0) / 100.0, 2)
        agg = AggOrder.create({
            'aggregator_id': channel.id, 'external_id': external_id,
            'pos_order_id': order.id, 'delivery_id': dlv.id, 'state': 'received',
            'customer_name': customer.get('name'), 'phone': customer.get('phone'),
            'address': customer.get('address'),
            'gross_total': gross, 'commission': commission,
            'net_payout': round(gross - commission, 2),
            'raw_payload': raw.decode(errors='replace'),
        })
        self._bridge._audit(env, 'aggregator.order', order=order, severity='info',
                            detail=json.dumps({'aggregator': channel.code, 'external_id': external_id,
                                               'gross': gross, 'commission': commission}))
        self._notify(channel, agg, 'accepted')
        return self._json({'ok': True, 'aggregator_order_id': agg.id,
                           'order_id': order.id, 'delivery_id': dlv.id,
                           'tracking': order.tracking_number or order.pos_reference or '',
                           'total': round(incl, 2)})

    def _create_order(self, env, channel, config, external_id, lines, customer):
        """Build a paid pos.order (aggregator = prepaid tender), fire the food,
        and open a mezze.delivery — mirrors delivery_create, reusing its helpers."""
        session = self._bridge._ensure_open_session(env, config)
        partner = env['res.partner']
        order_lines, base, incl = self._bridge._build_lines(env, config, partner, lines)
        uuid = 'agg:%s:%s' % (channel.code, external_id)
        pmid = (channel.payment_method_id.id if channel.payment_method_id
                else config.payment_method_ids[:1].id)
        if not pmid:
            raise ValueError("No payment method on branch %s" % config.display_name)
        order_dict = {
            'uuid': uuid, 'session_id': session.id, 'company_id': config.company_id.id,
            'user_id': env.uid, 'partner_id': False,
            'pricelist_id': config.pricelist_id.id or False,
            'name': 'Mezze %s' % uuid,
            'date_order': fields.Datetime.to_string(fields.Datetime.now()),
            'lines': order_lines,
            'payment_ids': [(0, 0, {'amount': incl, 'name': fields.Datetime.now(),
                                    'payment_method_id': pmid})],
            'amount_tax': incl - base, 'amount_total': incl, 'amount_paid': incl,
            'amount_return': 0.0, 'last_order_preparation_change': '{}', 'to_invoice': False,
        }
        env['pos.order'].sync_from_ui([order_dict])
        order = env['pos.order'].search([('uuid', '=', uuid)], limit=1)
        if not order:
            raise ValueError("aggregator order did not persist")
        tickets = self._bridge._make_station_tickets(
            env, order, [(l.product_id, l.qty, '') for l in order.lines if l.qty > 0],
            'agg:%s' % external_id, 1, server_override='%s order' % channel.name)
        if channel.auto_accept:
            tickets._broadcast()
        dlv = env['mezze.delivery'].create({
            'pos_order_id': order.id,
            'customer_name': customer.get('name') or channel.name,
            'phone': customer.get('phone'), 'address': customer.get('address'),
            'fee': 0.0, 'note': '%s · %s' % (channel.name, external_id),
            'state': 'preparing',
        })
        return order, dlv, incl

    # -- order.cancel ----------------------------------------------------------
    def _cancel(self, env, channel, external_id):
        AggOrder = env['mezze.aggregator.order'].sudo()
        agg = AggOrder._find(channel, external_id)
        if not agg:
            return self._json({'ok': False, 'error': 'unknown_order'}, status=404)
        if agg.state == 'cancelled':
            return self._json({'ok': True, 'idempotent': True, 'state': 'cancelled'})
        agg.state = 'cancelled'
        if agg.delivery_id:
            agg.delivery_id.state = 'failed'
            agg.delivery_id.note = (agg.delivery_id.note or '') + ' · CANCELLED by aggregator'
        # NOTE: the pos.order is already paid+fired. We flag rather than auto-void
        # — the refund/reversal of a prepaid, possibly-cooking order is a staff
        # decision (see the manager reversal queue / refund path).
        self._bridge._audit(env, 'aggregator.cancel', order=agg.pos_order_id, severity='warning',
                            config_id=agg.config_id.id, res_uuid=external_id,
                            detail=json.dumps({'aggregator': channel.code, 'external_id': external_id}))
        self._notify(channel, agg, 'cancelled')
        return self._json({'ok': True, 'state': 'cancelled',
                           'order_id': agg.pos_order_id.id or None,
                           'note': 'Order flagged cancelled; refund/void is a staff action.'})

    # -- staff-facing list (shared-token auth) ---------------------------------
    @http.route(f'{AGG_PREFIX}/orders', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def orders(self, config_id=None, limit=50, **kw):
        auth = self._bridge._authenticate()
        if auth:
            return auth
        env = self._bridge._api_env()
        dom = [('config_id', '=', int(config_id))] if config_id else []
        out = []
        for a in env['mezze.aggregator.order'].search(dom, limit=int(limit or 50)):
            order = a.pos_order_id
            out.append({
                'id': a.id, 'aggregator': a.aggregator_id.name,
                'code': a.aggregator_id.code, 'external_id': a.external_id,
                'state': a.state, 'reject_reason': a.reject_reason or None,
                'unmapped_skus': a.unmapped_skus or None,
                'who': a.customer_name or '', 'phone': a.phone or '',
                'order_id': order.id or None,
                'tracking': (order.tracking_number or order.pos_reference or '') if order else '',
                'gross': round(a.gross_total, 2), 'commission': round(a.commission, 2),
                'net_payout': round(a.net_payout, 2),
                'received_at': fields.Datetime.to_string(a.received_at) if a.received_at else None,
            })
        return {'ok': True, 'orders': out,
                'channels': [{'id': c.id, 'code': c.code, 'name': c.name,
                              'config_id': c.config_id.id, 'auto_accept': c.auto_accept,
                              'commission_pct': c.commission_pct}
                             for c in env['mezze.aggregator'].search(
                                 [('config_id', '=', int(config_id))] if config_id else [])]}
