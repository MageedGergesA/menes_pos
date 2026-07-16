# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Mezze Bridge API controller.

Design contract
---------------
* The external Mezze frontend speaks ONLY this JSON HTTP API. It never touches
  Odoo ORM-RPC / JSON-RPC.
* Reads reuse the ``pos.load.mixin`` field lists via curated ``search_read``.
* Writes reuse ``pos.order.sync_from_ui`` so real ``stock`` moves and (on session
  close) ``account`` entries are produced by Odoo's own POS flow. We never
  reinvent order creation or the session close.
* Idempotency piggybacks on the native ``pos.order.uuid`` (``sync_from_ui``
  upserts by uuid); we add a ``mezze.sync.log`` audit row on top.

v19 notes (verified against odoo/odoo/http.py):
* ``type='json'`` is now a DEPRECATED ALIAS for ``type='jsonrpc'`` (JSON-RPC 2.0
  envelope in/out). The task wants a clean REST-JSON contract (bare body in,
  bare JSON out) reachable by plain ``curl``/``fetch`` -> that is the new
  ``type='json2'`` dispatcher. We use ``json2`` for the API routes and keep
  ``/health`` on ``type='http'``.
* CORS preflight ``Access-Control-Allow-Headers`` is HARD-CODED in the framework
  and does NOT include ``X-Mezze-Token``. A browser cross-origin call carrying
  that custom header is therefore blocked at preflight. So ``_authenticate``
  accepts the token from the ``X-Mezze-Token`` header (curl path) OR from a
  ``token`` field in the JSON body / query string (browser path).
"""
import base64
import datetime
import hashlib
import json
import logging
import os
from urllib.parse import quote

import psycopg2

from odoo import SUPERUSER_ID, fields, http
from odoo.http import request
from odoo.tools import float_round

from . import approval

_logger = logging.getLogger(__name__)

API_PREFIX = '/mezze/api/v1'
TOKEN_PARAM = 'mezze_bridge.api_token'
USER_PARAM = 'mezze_bridge.api_user_id'

# Postgres concurrency errors Odoo's request-level retrying() re-runs on a fresh
# snapshot. Our broad handlers must let these propagate instead of swallowing
# them into a JSON error (which would also poison the aborted transaction).
_RETRYABLE_PG = (
    psycopg2.errors.SerializationFailure,
    psycopg2.errors.DeadlockDetected,
    psycopg2.errors.LockNotAvailable,
)


def _reraise_if_retryable(exc):
    """Re-raise ``exc`` unchanged if it (or any error it wraps) is a Postgres
    concurrency failure, so ``service_model.retrying`` can re-run the request."""
    cur = exc
    seen = 0
    while cur is not None and seen < 8:
        if isinstance(cur, _RETRYABLE_PG):
            raise exc
        cur = cur.__cause__ or cur.__context__
        seen += 1


class MezzeBridgeController(http.Controller):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _json(self, payload, status=200):
        """Return a bare JSON response with an explicit HTTP status."""
        return request.make_json_response(payload, status=status)

    def _authenticate(self):
        """Validate the shared token.

        :return: ``None`` when authenticated, otherwise a ready-to-return 401
                 JSON response. Callers must ``return`` a truthy result.
        """
        expected = request.env['ir.config_parameter'].sudo().get_param(TOKEN_PARAM)
        provided = request.httprequest.headers.get('X-Mezze-Token')
        if not provided:
            # Browser path: custom headers are blocked by CORS preflight, so the
            # frontend may pass the token in the JSON body / query string.
            provided = request.params.get('token')
        if not expected:
            return self._json({
                'ok': False,
                'error': 'server_token_unset',
                'message': "No API token configured. Set ir.config_parameter "
                           "'%s' on the server." % TOKEN_PARAM,
            }, status=503)
        if not provided or provided != expected:
            return self._json({
                'ok': False,
                'error': 'unauthorized',
                'message': "Missing or invalid token (X-Mezze-Token header or "
                           "'token' body field).",
            }, status=401)
        return None

    def _api_env(self):
        """Return an env bound to the configured API user.

        Runs as a real internal user (config param ``mezze_bridge.api_user_id``,
        else Mitchell Admin, else the first internal user). This user carries POS
        rights, so we avoid ``sudo`` superuser edge cases (e.g. ``open_ui``'s
        SUPERUSER guard) while still reusing core flows unchanged.
        """
        su = request.env(user=SUPERUSER_ID)
        uid_param = su['ir.config_parameter'].get_param(USER_PARAM)
        if uid_param and str(uid_param).isdigit():
            uid = int(uid_param)
        else:
            api_user = su.ref('base.user_admin', raise_if_not_found=False)
            if not api_user:
                api_user = su['res.users'].search(
                    [('share', '=', False), ('active', '=', True)], limit=1)
            uid = api_user.id
        return request.env(user=uid)

    def _resolve_config(self, env, config_id=None):
        Config = env['pos.config']
        config = Config.browse(int(config_id)) if config_id else Config
        if not config or not config.exists():
            config = Config.search([], limit=1)
        return config

    def _ensure_open_session(self, env, config):
        """Return an open ``pos.session`` for ``config``, opening one if needed.

        Reuses core session lifecycle: ``pos.session.create`` -> auto
        ``action_pos_session_open`` -> ``set_opening_control`` -> state 'opened'.
        We intentionally do NOT call ``pos.config.open_ui`` because it raises for
        SUPERUSER and returns a client action rather than a record.
        """
        session = config.current_session_id
        if session and session.state in ('opened', 'opening_control'):
            if session.state == 'opening_control':
                session.set_opening_control(0, None)
            return session
        session = env['pos.session'].create({
            'config_id': config.id,
            'user_id': env.uid,
        })
        session.set_opening_control(0, None)
        return session

    def _audit(self, env, event, order=None, **extra):
        """Best-effort append to the immutable ``mezze.audit.log`` trail.

        Never raises into the caller's money flow — a failed audit write must not
        roll back a completed sale (it is logged server-side for follow-up). When
        an ``order`` is given, its model/id/uuid/branch/amount are attached
        automatically so every money event is attributable.
        """
        try:
            vals = dict(extra)
            if order is not None and order:
                vals.setdefault('res_model', 'pos.order')
                vals.setdefault('res_id', order.id)
                vals.setdefault('res_uuid', order.uuid or '')
                vals.setdefault('config_id', order.config_id.id or False)
                vals.setdefault('amount', order.amount_total)
            env['mezze.audit.log'].log(event, **vals)
        except Exception:  # noqa: BLE001
            _logger.exception("Mezze audit wiring failed for event %s", event)

    def _actor(self, env, kw):
        """Resolve the acting cashier/terminal from the request body for
        attribution. Only sets a value when the record actually exists, so a
        stale/bad id never drops the whole audit row (a missing FK would make the
        best-effort append silently fail). ``terminal_id`` may be the DB id or the
        terminal's string ``identifier``.
        """
        out = {}
        cid = kw.get('cashier_id')
        if cid and str(cid).isdigit():
            cashier = env['mezze.cashier'].browse(int(cid))
            if cashier.exists():
                out['cashier_id'] = cashier.id
        tid = kw.get('terminal_id')
        if tid:
            term = None
            if str(tid).isdigit():
                term = env['mezze.terminal'].browse(int(tid))
                term = term if term.exists() else None
            else:
                term = env['mezze.terminal'].search([('identifier', '=', tid)], limit=1)
            if term:
                out['terminal_id'] = term.id
        return out

    # -- terminal-scoped receipt reference -------------------------------------
    # Two OFFLINE terminals each running a local Odoo would otherwise mint the
    # same pos_reference sequence ("Order 0001"), colliding when they sync up.
    # We namespace the receipt number with THIS node's terminal identity so it
    # is globally unique; the sync apply-path preserves it. See docs/SYNC.md.
    def _node_terminal(self, env):
        """This node's own terminal identity (config param, set per install /
        bundled .exe). ``None`` on a plain single-node cloud → references keep
        Odoo's default sequence (opt-in, so existing behaviour is unchanged)."""
        return env['ir.config_parameter'].sudo().get_param('mezze_bridge.terminal_id') or None

    def _terminal_ref(self, config, ident, tail):
        """Globally-unique, human-readable receipt ref: ``M<config>-<term>-<tail>``."""
        return 'M%s-%s-%s' % (config.id, str(ident)[-8:], tail)

    def _stamp_ref(self, env, order, ident, tail):
        """Stamp a terminal-scoped pos_reference on a fresh order when this node
        has a terminal identity. No-op otherwise."""
        if ident and order:
            order.sudo().write({'pos_reference': self._terminal_ref(order.config_id, ident, tail)})

    def _tip_product(self, env, config):
        """The tip product — reuse Odoo's native POS tip product
        (``pos.config.tip_product_id`` / the ``TIPS`` product) so tips reconcile
        through the standard `pos.order.tip_amount`/`is_tipped` path. Created on
        first use if the config has none."""
        p = config.tip_product_id
        if p:
            return p
        Product = env['product.product'].sudo()
        p = Product.search([('default_code', '=', 'TIPS')], limit=1)
        if not p:
            p = Product.create({
                'name': 'Tips', 'default_code': 'TIPS', 'type': 'service',
                'available_in_pos': True, 'taxes_id': [(6, 0, [])], 'list_price': 0.0})
        config.sudo().tip_product_id = p.id
        return p

    # ------------------------------------------------------------------
    # Health (no auth) — connectivity probe
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/health', type='http', auth='none',
                methods=['GET'], csrf=False, cors='*')
    def health(self, **kw):
        return request.make_json_response({
            'ok': True,
            'odoo': '19.0',
            'module': 'mezze_bridge',
        })

    # ------------------------------------------------------------------
    # Bootstrap — catalog + config + open session
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/bootstrap', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def bootstrap(self, config_id=None, **kw):
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            config = self._resolve_config(env, config_id)
            if not config:
                return self._json({
                    'ok': False,
                    'error': 'no_pos_config',
                    'message': "No pos.config found. Create a Point of Sale first.",
                }, status=404)
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            config = config.with_env(env)
            session = self._ensure_open_session(env, config)

            # Payment methods bound to this config.
            payment_methods = config.payment_method_ids.read(['id', 'name'])

            # Taxes available in the config's company.
            taxes = env['account.tax'].search_read(
                [('type_tax_use', '=', 'sale'),
                 ('company_id', '=', config.company_id.id)],
                ['id', 'name', 'amount'])

            # POS categories.
            categories = env['pos.category'].search_read([], ['id', 'name'])

            # Products available in POS (curated projection of the pos.load.mixin
            # field set — we return only what the Mezze frontend needs).
            products = env['product.product'].search_read(
                self._menu_domain(env),
                ['id', 'display_name', 'list_price', 'barcode', 'default_code',
                 'taxes_id', 'pos_categ_ids', 'uom_id', 'type'])
            blocked86 = self._eightysix_ids(env, config.id)
            catname = {c['id']: (c['name'] or '') for c in categories}
            # eligible halves = pizzas (a POS category named "pizza"), minus the
            # half-&-half base itself (default_code HALFHALF)
            half_options = []
            for p in products:
                # Normalise display_name -> name for the frontend.
                p['name'] = p.pop('display_name')
                prod = env['product.product'].browse(p['id'])
                p['modifiers'] = self._product_modifiers(env, prod)
                p['combos'] = self._product_combos(env, prod)
                p['is_combo'] = p['type'] == 'combo'
                p['available'] = p['id'] not in blocked86     # False => 86'd on this branch
                p['half_base'] = (p.get('default_code') == 'HALFHALF')
                is_pizza = any('pizza' in catname.get(cid, '').lower()
                               for cid in (p.get('pos_categ_ids') or []))
                if is_pizza and not p['half_base'] and p['available']:
                    half_options.append({'id': p['id'], 'name': p['name'],
                                         'price': p['list_price']})

            return {
                'ok': True,
                'session_id': session.id,
                'config': {
                    'id': config.id,
                    'name': config.name,
                    'currency_id': config.currency_id.id,
                    'company_id': config.company_id.id,
                    'pricelist_id': config.pricelist_id.id or False,
                },
                'payment_methods': payment_methods,
                'taxes': taxes,
                'categories': categories,
                'products': products,
                'quick_keys': self._quickkeys(env, config.id),
                'half_options': half_options,
                'gift_sale_product_id': self._giftcard_sale_product(env).id,
            }
        except Exception as exc:  # noqa: BLE001 - never leak a 500 traceback
            _logger.exception("Mezze bootstrap failed")
            return self._json({
                'ok': False,
                'error': 'bootstrap_failed',
                'message': str(exc),
            }, status=400)

    # ------------------------------------------------------------------
    # Order sync — idempotent, reuses pos.order.sync_from_ui
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/orders/sync', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def order_sync(self, uuid=None, session_id=None, lines=None, payments=None,
                   partner_id=None, amount_total=None, table_id=None,
                   discount=None, discount_product_id=None, tip=None,
                   gift_card_code=None, gift_card_amount=None, **kw):
        auth = self._authenticate()
        if auth:
            return auth

        payload_hash = hashlib.sha256(
            json.dumps({
                'uuid': uuid, 'session_id': session_id, 'lines': lines,
                'payments': payments, 'partner_id': partner_id,
            }, sort_keys=True, default=str).encode()
        ).hexdigest()

        if not uuid:
            return self._json({'ok': False, 'error': 'missing_uuid',
                               'message': "'uuid' is required."}, status=400)

        env = self._api_env()
        Log = env['mezze.sync.log'].sudo()
        log = Log.create({
            'name': 'Mezze %s' % uuid,
            'uuid': uuid,
            'status': 'received',
            'payload_hash': payload_hash,
        })

        try:
            # ---- Idempotency: native pos.order.uuid ----
            existing = env['pos.order'].search([('uuid', '=', uuid)], limit=1)
            if existing:
                log.write({
                    'status': 'ok',
                    'pos_order_id': existing.id,
                    'session_id': existing.session_id.id,
                    'message': 'Idempotent hit: order already exists, not duplicated.',
                })
                return {
                    'ok': True,
                    'duplicate': True,
                    'order_id': existing.id,
                    'pos_reference': existing.pos_reference,
                    'uuid': existing.uuid,
                    'amount_total': existing.amount_total,
                    'amount_paid': existing.amount_paid,
                }

            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            session = session.with_env(env)
            config = config.with_env(env)
            currency = session.currency_id
            pricelist = config.pricelist_id

            partner = env['res.partner'].browse(int(partner_id)) if partner_id else env['res.partner']
            fiscal_position = (partner.property_account_position_id
                               or config.default_fiscal_position_id)

            # Combos and half-&-half are built as parent+child lines AFTER the
            # order exists (the child→parent link needs real ids), so split them
            # out of the flat line loop and graft them onto a draft.
            plain_lines, combo_carts, half_carts = self._split_combos(env, lines)

            # ---- Build order lines server-side (do NOT trust client totals) ----
            AccountTax = env['account.tax']
            order_lines = []
            total_base = 0.0
            total_incl = 0.0
            for line in plain_lines:
                product = env['product.product'].browse(int(line['product_id']))
                if not product.exists():
                    raise ValueError("Unknown product_id %s" % line.get('product_id'))
                self._assert_available(env, config, product)      # reject 86'd items
                qty = float(line.get('qty', 1.0))
                line_disc = float(line.get('discount', 0.0))   # per-line %, not the loyalty redeem
                # price_unit: honour client override, else pricelist price.
                if line.get('price_unit') is not None:
                    price_unit = float(line['price_unit'])
                else:
                    price_unit = pricelist._get_product_price(product, qty) if pricelist \
                        else product.lst_price

                # tax_ids: honour client override, else product taxes through FP.
                if line.get('tax_ids'):
                    tax_ids = AccountTax.browse([int(t) for t in line['tax_ids']])
                else:
                    company_taxes = product.taxes_id.filtered_domain(
                        AccountTax._check_company_domain(env.company))
                    tax_ids = fiscal_position.map_tax(company_taxes)

                price_after_disc = price_unit * (1 - line_disc / 100.0)
                if tax_ids:
                    tv = tax_ids.compute_all(price_after_disc, currency, qty,
                                             product=product, partner=partner or None)
                    subtotal = tv['total_excluded']
                    subtotal_incl = tv['total_included']
                else:
                    subtotal = price_after_disc * qty
                    subtotal_incl = subtotal

                total_base += subtotal
                total_incl += subtotal_incl
                order_lines.append((0, 0, {
                    'product_id': product.id,
                    'qty': qty,
                    'price_unit': price_unit,
                    'discount': line_disc,
                    'tax_ids': [(6, 0, tax_ids.ids)],
                    'price_subtotal': subtotal,
                    'price_subtotal_incl': subtotal_incl,
                    'pack_lot_ids': [],
                }))

            # ---- Tip / gratuity: a tax-free line on the native tip product, so
            # it reconciles through pos.order.tip_amount + is_tipped. Added to the
            # total so the tender covers it. ----
            tip_amt = round(float(tip or 0.0), 2)
            if tip_amt > 0:
                tip_product = self._tip_product(env, config)
                order_lines.append((0, 0, {
                    'product_id': tip_product.id, 'qty': 1, 'price_unit': tip_amt,
                    'discount': 0.0, 'tax_ids': [(6, 0, [])],
                    'price_subtotal': tip_amt, 'price_subtotal_incl': tip_amt,
                    'pack_lot_ids': []}))
                total_base += tip_amt
                total_incl += tip_amt

            # ---- Gift card tender: validate the card and reserve the amount it
            # covers as its OWN pos.payment (on the Gift Card method); the rest of
            # the bill is settled by the client's other tenders. The card is
            # decremented only AFTER the order is confirmed paid (below). ----
            gift_card = None
            gc_applied = 0.0
            if gift_card_code:
                gift_card = self._giftcard_by_code(env, gift_card_code)
                if not gift_card:
                    raise ValueError("Gift card %s not found" % gift_card_code)
                if gift_card.expiration_date and gift_card.expiration_date < fields.Date.today():
                    raise ValueError("Gift card %s has expired" % gift_card.code)
                gc_req = round(float(gift_card_amount), 2) if gift_card_amount else gift_card.points
                gc_applied = min(gc_req, gift_card.points, round(total_incl, 2))
                if gc_applied <= 0:
                    raise ValueError("Gift card %s has no balance" % gift_card.code)

            # ---- Build payments. When the client sends several tenders (a
            # split bill, or mixed cash+card), record ONE pos.payment per tender
            # so the split is faithful; the LAST tender absorbs any rounding drift
            # so the payments always sum to the SERVER-computed tax-inclusive total
            # (the order can never disagree with the displayed bill). ----
            pay_target = round(total_incl - gc_applied, 2)     # what non-gift tenders cover
            plist = [p for p in (payments or [])
                     if p.get('payment_method_id') and float(p.get('amount', 0) or 0) > 0]
            order_payments = []
            if pay_target > 0:
                if len(plist) >= 2:
                    running = 0.0
                    for i, p in enumerate(plist):
                        amt = (round(pay_target - running, 2) if i == len(plist) - 1
                               else round(float(p['amount']), 2))
                        running += amt
                        order_payments.append((0, 0, {'amount': amt, 'name': fields.Datetime.now(),
                                                       'payment_method_id': int(p['payment_method_id'])}))
                else:
                    pmid = int(plist[0]['payment_method_id']) if plist \
                        else (config.payment_method_ids[:1].id)
                    order_payments.append((0, 0, {'amount': pay_target, 'name': fields.Datetime.now(),
                                                  'payment_method_id': pmid}))
            if gc_applied > 0:
                gc_pm = self._giftcard_pm(env, config)
                order_payments.append((0, 0, {'amount': gc_applied, 'name': fields.Datetime.now(),
                                              'payment_method_id': gc_pm.id}))
            pmid = order_payments[0][2]['payment_method_id'] if order_payments \
                else (config.payment_method_ids[:1].id)
            paid_total = total_incl

            # Loyalty redemption needs a discount LINE, which
            # sync_from_ui strips (it wants reward-line metadata). So for a
            # redeemed order we create a DRAFT, add the discount line via ORM,
            # then finalise the (discounted) payment ourselves. Combos likewise
            # need their parent/child lines grafted on after create, so both
            # take the draft-then-finalise path.
            redeeming = bool(discount and discount_product_id)
            needs_draft = redeeming or bool(combo_carts) or bool(half_carts)
            # Gift-card tender flows through the direct (paid) sync; combining it
            # with a combo/comp/loyalty order in one ticket isn't wired yet.
            if gift_card and needs_draft:
                raise ValueError("Gift-card payment can't yet combine with "
                                 "combos, comp, or loyalty redemption in one order")

            # ---- Assemble the exact dict pos.order.sync_from_ui expects ----
            # (shape mirrors point_of_sale/tests/common.py::create_ui_order_data)
            order_dict = {
                'uuid': uuid,
                'session_id': session.id,
                'company_id': config.company_id.id,
                'user_id': env.uid,
                'partner_id': partner.id or False,
                'pricelist_id': pricelist.id or False,
                'fiscal_position_id': fiscal_position.id or False,
                'name': 'Mezze %s' % uuid,
                'date_order': fields.Datetime.to_string(fields.Datetime.now()),
                'lines': order_lines,
                'payment_ids': [] if needs_draft else order_payments,
                'amount_tax': total_incl - total_base,
                'amount_total': total_incl,
                'amount_paid': 0.0 if needs_draft else paid_total,
                'amount_return': 0.0,
                'last_order_preparation_change': '{}',
                'to_invoice': False,
            }
            if needs_draft:
                order_dict['state'] = 'draft'      # finalise after grafting lines
            # else: no 'state' key -> _process_order finalises it as paid.

            if table_id and 'table_id' in env['pos.order']._fields:
                order_dict['table_id'] = int(table_id)
            result = env['pos.order'].sync_from_ui([order_dict])
            synced = (result or {}).get('pos.order') or []
            order = env['pos.order'].search([('uuid', '=', uuid)], limit=1)
            if not order:
                raise ValueError("sync_from_ui did not persist the order")

            combo_kds = []
            if needs_draft:
                # (a) graft native combo + half-&-half parent/child lines.
                if combo_carts:
                    _cb, _ci, combo_kds = self._combo_apply(env, config, partner,
                                                            order, combo_carts)
                if half_carts:
                    _hb, _hi, half_kds = self._halfhalf_apply(env, config, partner,
                                                              order, half_carts)
                    combo_kds += half_kds
                # (b) graft the loyalty discount line.
                if redeeming:
                    d = float(discount)
                    dp = env['product.product'].browse(int(discount_product_id))
                    # carry the same taxes as the menu so the discount reduces the
                    # taxed total pre-tax, consistent with the displayed bill.
                    dtax = dp.taxes_id
                    tv = dtax.compute_all(-d, config.currency_id, 1, product=dp) if dtax else None
                    dsub = tv['total_excluded'] if tv else -d
                    dincl = tv['total_included'] if tv else -d
                    order.write({'lines': [(0, 0, {
                        'product_id': dp.id, 'qty': 1, 'price_unit': -d,
                        'discount': 0.0, 'tax_ids': [(6, 0, dtax.ids)],
                        'price_subtotal': dsub, 'price_subtotal_incl': dincl, 'pack_lot_ids': []})]})
                # (c) recompute the total across ALL lines, then (d) settle once.
                tot_base = sum(order.lines.mapped('price_subtotal'))
                tot_incl = sum(order.lines.mapped('price_subtotal_incl'))
                order.write({'amount_tax': tot_incl - tot_base, 'amount_total': tot_incl})
                pm = (env['pos.payment.method'].browse(int(payments[0]['payment_method_id']))
                      if payments else config.payment_method_ids[:1])
                order.add_payment({'amount': order.amount_total, 'payment_method_id': pm.id,
                                   'name': fields.Datetime.now(), 'pos_order_id': order.id})
                order.action_pos_order_paid()

            # ---- café counter order → put its drinks/food on the KDS/BDS queue.
            # Table orders arrive via /orders/fire; counter orders come here, so
            # this is where a coffee-shop sale enters the barista queue. Its
            # native tracking_number becomes the customer pickup number. The
            # combo PARENT line (a section, no station) is skipped; its real
            # child dishes ride in via combo_kds. ----
            tickets = self._make_station_tickets(
                env, order,
                [(l.product_id, l.qty,
                  ', '.join(l.attribute_value_ids.mapped('product_attribute_value_id.name')))
                 for l in order.lines
                 if l.product_id.type != 'combo' and not l.combo_parent_id] + combo_kds,
                'sync:%s' % uuid, 1)
            tickets._broadcast()

            # ---- terminal-scoped receipt number (offline collision-safety) ----
            self._stamp_ref(env, order, self._node_terminal(env), order.id)

            # ---- record the tip on the native pos.order fields ----
            if tip_amt > 0 and order:
                order.sudo().write({'is_tipped': True, 'tip_amount': tip_amt})

            # ---- gift card: decrement the balance now the order is paid ----
            gc_balance = None
            if gift_card and gc_applied > 0:
                self._giftcard_decrement(env, gift_card, gc_applied,
                                         order.pos_reference or order.id)
                gc_balance = gift_card.points
                self._audit(env, 'giftcard.redeem', order, **self._actor(env, kw),
                            detail=json.dumps({'code': gift_card.code, 'applied': gc_applied,
                                               'balance': gc_balance}, default=str))

            # ---- gift card SALE: selling the GIFTCARD product mints a card for
            # the line amount (the money was just collected on this order) ----
            issued_cards = []
            gc_sale = self._giftcard_sale_product(env)
            for l in order.lines.filtered(lambda x: x.product_id.id == gc_sale.id and x.price_subtotal_incl > 0):
                prog = self._giftcard_program(env)
                card = env['loyalty.card'].sudo().create({
                    'program_id': prog.id, 'points': round(l.price_subtotal_incl, 2),
                    'partner_id': order.partner_id.id or False})
                issued_cards.append({'code': card.code, 'amount': card.points})
                self._audit(env, 'giftcard.issue', order, **self._actor(env, kw),
                            detail=json.dumps({'code': card.code, 'amount': card.points,
                                               'via': 'sale'}, default=str))

            # ---- loyalty: award real points if a customer is attached ----
            earned, balance = self._loyalty_earn(env, order)

            log.write({
                'status': 'ok',
                'pos_order_id': order.id,
                'session_id': order.session_id.id,
                'message': 'Order synced (%d queue tickets).' % len(tickets),
            })
            self._audit(env, 'order.pay', order, **self._actor(env, kw),
                        detail=json.dumps({'via': 'order_sync', 'tickets': len(tickets),
                                           'partner_id': partner_id}, default=str))
            return {
                'ok': True,
                'duplicate': False,
                'order_id': order.id,
                'pos_reference': order.pos_reference,
                'tracking_number': order.tracking_number or '',
                'uuid': order.uuid,
                'amount_total': order.amount_total,
                'amount_paid': order.amount_paid,
                'synced_records': len(synced),
                'tickets': len(tickets),
                'gift_card_applied': gc_applied or 0.0, 'gift_card_balance': gc_balance,
                'issued_gift_cards': issued_cards,
                'loyalty_earned': earned, 'loyalty_balance': balance,
            }
        except Exception as exc:  # noqa: BLE001 - clean JSON, never a 500
            _logger.exception("Mezze order sync failed for uuid=%s", uuid)
            try:
                log.write({'status': 'error', 'message': str(exc)})
            except Exception:  # noqa: BLE001
                pass
            return self._json({
                'ok': False,
                'error': 'sync_failed',
                'uuid': uuid,
                'message': str(exc),
            }, status=400)

    # ------------------------------------------------------------------
    # Table service: fire a DRAFT order (deferred payment) + pay it later
    # ------------------------------------------------------------------
    def _line_attr_values(self, env, product, line):
        """Validated ``product.template.attribute.value`` recordset for a line's
        chosen modifiers, filtered to THIS product's template so a client cannot
        inject another product's options (or arbitrary ids)."""
        ids = line.get('attribute_value_ids') or []
        if not ids:
            return env['product.template.attribute.value']
        ptav = env['product.template.attribute.value'].browse([int(i) for i in ids]).exists()
        return ptav.filtered(lambda v: v.product_tmpl_id == product.product_tmpl_id)

    def _line_note(self, env, product, line):
        """Kitchen note for a line — its chosen modifiers, else any free text."""
        ptavs = self._line_attr_values(env, product, line)
        if ptavs:
            return ', '.join(ptavs.mapped('product_attribute_value_id.name'))
        return line.get('note') or line.get('mod') or ''

    def _menu_domain(self, env):
        """POS-available products for the customer menu, EXCLUDING loyalty
        reward/discount products (which are POS-available only so their discount
        lines survive order sync — they must never appear on the menu)."""
        rewards = env['loyalty.reward'].sudo().search([])
        rules = env['loyalty.rule'].sudo().search([])
        hidden = set(rewards.mapped('discount_line_product_id').ids)
        hidden |= set(rewards.mapped('reward_product_id').ids)
        hidden |= set(rules.mapped('product_ids').ids)     # gift-card / ewallet triggers
        # A real menu item carries a POS category; loyalty utility products
        # (discount lines, gift-card, e-wallet top-up) do not — filter them out.
        dom = [('available_in_pos', '=', True),
               ('product_tmpl_id.available_in_pos', '=', True),
               ('pos_categ_ids', '!=', False)]
        if hidden:
            dom.append(('id', 'not in', list(hidden)))
        return dom

    def _product_modifiers(self, env, product):
        """Modifier groups for a product from its POS-time (no_variant) attribute
        lines. Empty for plain products. Prices are the real ``price_extra``."""
        groups = []
        for al in product.product_tmpl_id.attribute_line_ids:
            if al.attribute_id.create_variant != 'no_variant':
                continue
            groups.append({
                'line_id': al.id,
                'attribute': al.attribute_id.name,
                'display_type': al.attribute_id.display_type,   # radio / multi / select / color
                'multi': al.attribute_id.display_type == 'multi',
                'values': [{'id': v.id, 'name': v.product_attribute_value_id.name,
                            'price_extra': v.price_extra}
                           for v in al.product_template_value_ids],
            })
        return groups

    def _product_combos(self, env, product):
        """Combo groups for a combo-type product: each group and its selectable
        items (real ``product.combo`` / ``product.combo.item``). Empty for
        non-combo products. The frontend renders one picker per group; the
        server re-prices on sync so the client's choice can't move the money."""
        if product.type != 'combo':
            return []
        groups = []
        for combo in product.product_tmpl_id.combo_ids:
            groups.append({
                'combo_id': combo.id,
                'name': combo.name,
                'items': [{'item_id': it.id, 'product_id': it.product_id.id,
                           'name': it.product_id.display_name,
                           'extra_price': it.extra_price}
                          for it in combo.combo_item_ids],
            })
        return groups

    def _build_lines(self, env, config, partner, lines):
        """Server-side, tax-correct order-line builder shared by fire/pay/qr.
        Applies modifier ``price_extra`` server-side (never trusts the client's
        total) and records the chosen ``attribute_value_ids`` on the line.
        Returns (line commands, total_excl, total_incl)."""
        currency = config.currency_id
        pricelist = config.pricelist_id
        fiscal_position = partner.property_account_position_id or config.default_fiscal_position_id
        AccountTax = env['account.tax']
        order_lines, base, incl = [], 0.0, 0.0
        for line in (lines or []):
            product = env['product.product'].browse(int(line['product_id']))
            if not product.exists():
                raise ValueError("Unknown product_id %s" % line.get('product_id'))
            self._assert_available(env, config, product)      # reject 86'd items
            qty = float(line.get('qty', 1.0))
            discount = float(line.get('discount', 0.0))
            # Modifiers: sum the real price_extra of the chosen attribute values.
            ptavs = self._line_attr_values(env, product, line)
            price_extra = sum(ptavs.mapped('price_extra'))
            # Client sends the BASE unit price (or none); the server adds the
            # modifier surcharge so totals can't be tampered with.
            if line.get('price_unit') is not None:
                base_price = float(line['price_unit'])
            else:
                base_price = pricelist._get_product_price(product, qty) if pricelist else product.lst_price
            price_unit = base_price + price_extra
            if line.get('tax_ids'):
                tax_ids = AccountTax.browse([int(t) for t in line['tax_ids']])
            else:
                company_taxes = product.taxes_id.filtered_domain(AccountTax._check_company_domain(env.company))
                tax_ids = fiscal_position.map_tax(company_taxes)
            price_after = price_unit * (1 - discount / 100.0)
            if tax_ids:
                tv = tax_ids.compute_all(price_after, currency, qty, product=product, partner=partner or None)
                subtotal, subtotal_incl = tv['total_excluded'], tv['total_included']
            else:
                subtotal = subtotal_incl = price_after * qty
            base += subtotal
            incl += subtotal_incl
            vals = {
                'product_id': product.id, 'qty': qty, 'price_unit': price_unit,
                'discount': discount, 'tax_ids': [(6, 0, tax_ids.ids)],
                'price_subtotal': subtotal, 'price_subtotal_incl': subtotal_incl,
                'pack_lot_ids': [],
            }
            if ptavs:
                vals['attribute_value_ids'] = [(6, 0, ptavs.ids)]
                vals['price_extra'] = price_extra
                vals['full_product_name'] = '%s (%s)' % (
                    product.display_name, ', '.join(ptavs.mapped('product_attribute_value_id.name')))
            order_lines.append((0, 0, vals))
        return order_lines, base, incl

    # ------------------------------------------------------------------
    # Combos / meal deals — native reuse (product.combo + pos.order.line
    # combo_parent_id/combo_item_id). A combo is a PARENT line on the combo
    # product priced 0, plus one priced CHILD line per chosen item. The child
    # prices are the native proration of the combo's list price across the
    # groups' base_price (see point_of_sale compute_combo_items.js) so the
    # customer pays exactly the combo price + item extras, and each child keeps
    # its own product/tax/BoM — so the live food-cost moat survives per-item.
    # ------------------------------------------------------------------
    def _combo_child_vals(self, env, config, partner, combo_product, chosen):
        """Native-faithful child-line values for one combo.

        ``chosen`` is a ``product.combo.item`` recordset, exactly one per group
        of ``combo_product``. Returns a list of per-child dicts (product, taxes,
        price_unit, subtotals, combo_item_id). Money matches native to the cent:
        Σ child prices == combo list price + Σ chosen extra_price.
        """
        currency = config.currency_id
        pp_digits = env['decimal.precision'].precision_get('Product Price')
        parent_lst = combo_product.lst_price
        fiscal_position = (partner.property_account_position_id
                           or config.default_fiscal_position_id)
        AccountTax = env['account.tax']
        original_total = sum(it.combo_id.base_price for it in chosen)   # qty 1 each
        if original_total <= 0:
            raise ValueError("Combo %s has no priceable groups" % combo_product.display_name)
        remaining = parent_lst
        out = []
        chosen = list(chosen)
        for i, item in enumerate(chosen):
            price_unit = float_round(item.combo_id.base_price * parent_lst / original_total,
                                     precision_digits=pp_digits)
            remaining -= price_unit                      # qty 1
            if i == len(chosen) - 1:                     # last child absorbs the rounding
                price_unit += remaining
            price_unit += item.extra_price
            child = item.product_id
            taxes = child.taxes_id.filtered_domain(AccountTax._check_company_domain(env.company))
            taxes = fiscal_position.map_tax(taxes)
            if taxes:
                tv = taxes.compute_all(price_unit, currency, 1, product=child,
                                       partner=partner or None)
                sub, sub_incl = tv['total_excluded'], tv['total_included']
            else:
                sub = sub_incl = price_unit
            out.append({'product': child, 'taxes': taxes, 'price_unit': price_unit,
                        'subtotal': sub, 'subtotal_incl': sub_incl,
                        'combo_item_id': item.id})
        return out

    def _resolve_combo(self, env, combo_product, cart):
        """Validate a cart's combo selection against the product's real groups.

        Enforces exactly one pick per group and that every picked item belongs
        to THIS combo (a client can't smuggle a cheaper item from another
        combo). Returns the ordered ``product.combo.item`` recordset.
        """
        if combo_product.type != 'combo':
            raise ValueError("Product %s is not a combo" % combo_product.display_name)
        groups = combo_product.product_tmpl_id.combo_ids
        picks = cart.get('combo') or []
        item_ids = [int(p['item_id']) for p in picks if p.get('item_id')]
        chosen = env['product.combo.item'].browse(item_ids).exists()
        if len(chosen) != len(item_ids):
            raise ValueError("Unknown combo item in %s" % combo_product.display_name)
        for it in chosen:
            if it.combo_id not in groups:
                raise ValueError("Item %s is not part of combo %s"
                                 % (it.product_id.display_name, combo_product.display_name))
        picked_groups = chosen.mapped('combo_id')
        if len(picked_groups) != len(groups) or len(chosen) != len(groups):
            raise ValueError("Combo %s needs exactly one choice per group"
                             % combo_product.display_name)
        return chosen

    def _combo_apply(self, env, config, partner, order, combo_carts):
        """ORM-create native combo parent+child lines on an existing ``order``.

        Returns ``(base, incl, kds_items)`` where ``kds_items`` is a list of
        ``(child_product, qty, note)`` tuples so the caller can route the combo's
        real dishes to the kitchen. The combo PARENT line is priced 0 (children
        carry the money); each CHILD carries its product's own taxes.
        """
        Line = env['pos.order.line']
        add_base = add_incl = 0.0
        kds_items = []
        for cart in (combo_carts or []):
            combo_product = env['product.product'].browse(int(cart['product_id']))
            if not combo_product.exists():
                raise ValueError("Unknown combo product %s" % cart.get('product_id'))
            chosen = self._resolve_combo(env, combo_product, cart)
            # a 86'd combo, or a combo whose chosen item is 86'd, can't be sold
            self._assert_available(env, config, combo_product)
            self._assert_available(env, config, chosen.mapped('product_id'))
            child_vals = self._combo_child_vals(env, config, partner, combo_product, chosen)
            parent = Line.create({
                'order_id': order.id, 'product_id': combo_product.id, 'qty': 1,
                'price_unit': 0.0, 'discount': 0.0, 'tax_ids': [(6, 0, [])],
                'price_subtotal': 0.0, 'price_subtotal_incl': 0.0, 'pack_lot_ids': [],
            })
            for cv in child_vals:
                Line.create({
                    'order_id': order.id, 'product_id': cv['product'].id, 'qty': 1,
                    'price_unit': cv['price_unit'], 'discount': 0.0,
                    'tax_ids': [(6, 0, cv['taxes'].ids)],
                    'price_subtotal': cv['subtotal'], 'price_subtotal_incl': cv['subtotal_incl'],
                    'combo_parent_id': parent.id, 'combo_item_id': cv['combo_item_id'],
                    'pack_lot_ids': [],
                })
                add_base += cv['subtotal']
                add_incl += cv['subtotal_incl']
                kds_items.append((cv['product'], 1.0, combo_product.display_name))
        return add_base, add_incl, kds_items

    # ------------------------------------------------------------------
    # Half-and-half — one base, two halves, each priced/cost-tracked
    # ------------------------------------------------------------------
    # Modelled like a combo: the PARENT line (the half-&-half base) carries the
    # charged price + tax; two CHILD "half" lines carry qty 0.5 of the real pizza
    # products at price 0, so each half books HALF its BoM food cost — the moat
    # holds even on a split pizza. The kitchen sees ONE ticket "½ A / ½ B".
    def _halfhalf_price(self, env, a, b):
        """Charge for a split pizza. 'max' (default) = the pricier half sets the
        price; 'avg' = mean of the two. Per-branch via mezze_bridge.halfhalf_pricing."""
        rule = (env['ir.config_parameter'].sudo().get_param(
            'mezze_bridge.halfhalf_pricing', 'max') or 'max').strip().lower()
        pa, pb = a.lst_price, b.lst_price
        if rule == 'avg':
            return round((pa + pb) / 2.0, 2)
        return max(pa, pb)

    def _halfhalf_apply(self, env, config, partner, order, half_carts):
        """ORM-create the parent + two half child lines on ``order``. Returns
        ``(base, incl, kds_items)``; the KDS gets one labelled pizza per split."""
        Line = env['pos.order.line']
        currency = config.currency_id
        fp = (partner.property_account_position_id or config.default_fiscal_position_id)
        AccountTax = env['account.tax']
        add_base = add_incl = 0.0
        kds_items = []
        for cart in (half_carts or []):
            base_product = env['product.product'].browse(int(cart['product_id']))
            if not base_product.exists():
                raise ValueError("Unknown half-&-half base %s" % cart.get('product_id'))
            hids = [int(h) for h in (cart.get('halves') or [])]
            if len(hids) != 2:
                raise ValueError("Half-&-half needs exactly two halves")
            a = env['product.product'].browse(hids[0])
            b = env['product.product'].browse(hids[1])
            if not (a.exists() and b.exists()):
                raise ValueError("Unknown half product")
            self._assert_available(env, config, base_product)
            self._assert_available(env, config, a | b)
            price = self._halfhalf_price(env, a, b)
            taxes = (base_product.taxes_id or a.taxes_id).filtered_domain(
                AccountTax._check_company_domain(env.company))
            taxes = fp.map_tax(taxes)
            if taxes:
                tv = taxes.compute_all(price, currency, 1, product=base_product,
                                       partner=partner or None)
                sub, sub_incl = tv['total_excluded'], tv['total_included']
            else:
                sub = sub_incl = price
            name = '½ %s / ½ %s' % (a.display_name, b.display_name)
            parent = Line.create({
                'order_id': order.id, 'product_id': base_product.id, 'qty': 1,
                'price_unit': price, 'discount': 0.0, 'tax_ids': [(6, 0, taxes.ids)],
                'price_subtotal': sub, 'price_subtotal_incl': sub_incl,
                'pack_lot_ids': [], 'full_product_name': name,
            })
            for half in (a, b):
                Line.create({
                    'order_id': order.id, 'product_id': half.id, 'qty': 0.5,
                    'price_unit': 0.0, 'discount': 0.0, 'tax_ids': [(6, 0, [])],
                    'price_subtotal': 0.0, 'price_subtotal_incl': 0.0,
                    'combo_parent_id': parent.id, 'pack_lot_ids': [],
                })
            add_base += sub
            add_incl += sub_incl
            kds_items.append((base_product, 1.0, name))
        return add_base, add_incl, kds_items

    @staticmethod
    def _split_combos(env, lines):
        """Partition a cart into (plain_lines, combo_carts, half_carts). A cart
        line is a COMBO when its product is ``type=='combo'`` (or it carries a
        ``combo`` selection); a HALF-AND-HALF when it carries a ``halves`` list
        of two products. Both build parent+child lines after the order exists."""
        plain, combos, halves = [], [], []
        for line in (lines or []):
            product = env['product.product'].browse(int(line['product_id']))
            if line.get('halves'):
                halves.append(line)
            elif line.get('combo') or product.type == 'combo':
                combos.append(line)
            else:
                plain.append(line)
        return plain, combos, halves

    def _station_of(self, product):
        """Route a product to a prep station by name/category keywords. Real
        deployments would drive this off a category→station config table."""
        hay = (product.display_name or '').lower()
        if 'pos_categ_ids' in product._fields:
            hay += ' ' + ' '.join(product.pos_categ_ids.mapped('name')).lower()
        def has(*ws):
            return any(w in hay for w in ws)
        if has('espresso', 'latte', 'cappuccino', 'coffee', 'flat white', 'cortado', 'americano', 'mocha', 'macchiato'):
            return 'Barista'
        if has('tea', 'juice', 'soda', 'cola', 'water', 'drink', 'mojito', 'smoothie', 'shake', 'lemonade'):
            return 'Bar'
        if has('croissant', 'cake', 'pastry', 'dessert', 'cookie', 'cheesecake', 'muffin', 'brownie', 'tart', 'pain'):
            return 'Pastry'
        if has('pizza'):
            return 'Pizza'
        if has('salad'):
            return 'Salad'
        return 'Kitchen'

    # Stations a customer physically waits at / picks up from — the beverage
    # queue (BDS / coffee shop) is exactly these.
    _BEVERAGE_STATIONS = ('Barista', 'Bar')

    def _make_station_tickets(self, env, order, items, fire_uuid, course, server_override=None):
        """Create one ``mezze.kds.ticket`` per station from ``items`` — a list of
        ``(product, qty, note)`` tuples. Shared by table fire (/orders/fire),
        café counter sync (/orders/sync) and customer QR order (/qr/order) so all
        feed the same KDS/BDS boards. ``server_override`` labels the ticket's
        origin (e.g. a QR self-order). Returns the created tickets (caller
        broadcasts)."""
        Ticket = env['mezze.kds.ticket']
        table_label = None
        if 'table_id' in order._fields and order.table_id:
            tbl = order.table_id
            table_label = 'T%s' % (tbl.table_number if 'table_number' in tbl._fields else tbl.id)
        server_name = server_override or (order.user_id.name if order.user_id else None)
        guest_n = order.customer_count if 'customer_count' in order._fields else 0
        by_station = {}
        for (p, qty, note) in items:
            if qty <= 0:
                continue
            by_station.setdefault(self._station_of(p), []).append((p, qty, note))
        tickets = Ticket.browse()
        for st, its in by_station.items():
            tickets |= Ticket.create({
                'pos_order_id': order.id, 'station': st, 'state': 'fired',
                'fire_uuid': fire_uuid, 'table_label': table_label,
                'server_name': server_name, 'guests': guest_n, 'course': course,
                'line_ids': [(0, 0, {'product_id': p.id, 'name': p.display_name,
                                     'qty': q, 'note': n}) for (p, q, n) in its],
            })
        return tickets

    # Advisory-lock namespace so our keys never collide with other apps'.
    _FIRE_LOCK_NS = 27749

    def _do_fire(self, env, uuid, session, config, table_id, lines,
                 partner_id, guests, fire_uuid, server_override=None):
        """Concurrency-safe append-fire CORE, shared by the waiter (/orders/fire)
        and customer QR (/qr/order) paths. Advisory-lock on the table → idempotent
        (by fire_uuid) → find-or-create the table's single open draft → APPEND the
        new items → one KDS ticket per station → broadcast. Caller must have set
        the company context on ``env``. Returns the result dict."""
        Order = env['pos.order']
        Ticket = env['mezze.kds.ticket']

        # ---- serialize concurrent fires to the same table / order ----
        if table_id:
            lock_key = int(table_id)
        else:
            lock_key = int(hashlib.sha1(uuid.encode()).hexdigest(), 16) % (2 ** 31)
        env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)", (self._FIRE_LOCK_NS, lock_key))

        # ---- idempotency: has this exact fire already been processed? ----
        done = Ticket.search([('fire_uuid', '=', fire_uuid)])
        if done:
            order = done[0].pos_order_id
            return {
                'ok': True, 'idempotent': True, 'order_id': order.id,
                'pos_reference': order.pos_reference, 'state': order.state,
                'tracking': order.tracking_number or order.pos_reference,
                'amount_total': order.amount_total,
                'table_id': order.table_id.id if order.table_id else None,
                'fire_uuid': fire_uuid,
                'tickets': [t._payload() for t in done],
                'fired_now': [i for t in done for i in
                              [{'product_id': l.product_id.id, 'name': l.name,
                                'qty': l.qty, 'station': t.station} for l in t.line_ids]],
            }

        partner = env['res.partner'].browse(int(partner_id)) if partner_id else env['res.partner']
        # Combos + half-&-half become parent/child lines grafted on after the
        # order exists; keep them out of the flat plain-line build.
        plain_lines, combo_carts, half_carts = self._split_combos(env, lines)
        order_lines, base, incl = self._build_lines(env, config, partner, plain_lines)

        # ---- find the table's open draft (append target), else create ----
        order = Order.browse()
        if table_id and 'table_id' in Order._fields:
            order = Order.search([('table_id', '=', int(table_id)),
                                  ('state', '=', 'draft'),
                                  ('session_id', '=', session.id)], limit=1)
        if not order:
            order = Order.search([('uuid', '=', uuid), ('state', '=', 'draft')], limit=1)
        already = Order.search([('uuid', '=', uuid)], limit=1)
        if already and already.state != 'draft':
            raise ValueError("Order %s is already %s — cannot re-fire"
                             % (already.pos_reference, already.state))

        if order:
            # APPEND the new items to the existing draft, then recompute the
            # totals across ALL lines (old + new) so nothing is clobbered.
            vals = {'lines': order_lines, 'amount_paid': 0.0}
            if guests and 'customer_count' in order._fields:
                vals['customer_count'] = int(guests)
            if partner.id:
                vals['partner_id'] = partner.id
            order.write(vals)
            tot_base = sum(order.lines.mapped('price_subtotal'))
            tot_incl = sum(order.lines.mapped('price_subtotal_incl'))
            order.write({'amount_tax': tot_incl - tot_base, 'amount_total': tot_incl})
        else:
            order_dict = {
                'uuid': uuid, 'session_id': session.id, 'company_id': config.company_id.id,
                'user_id': env.uid, 'partner_id': partner.id or False,
                'pricelist_id': config.pricelist_id.id or False,
                'name': 'Mezze %s' % uuid,
                'date_order': fields.Datetime.to_string(fields.Datetime.now()),
                'lines': order_lines, 'payment_ids': [],
                'amount_tax': incl - base, 'amount_total': incl,
                'amount_paid': 0.0, 'amount_return': 0.0,
                'last_order_preparation_change': '{}', 'to_invoice': False,
                'state': 'draft',                   # <- keeps it unpaid/open
            }
            if table_id and 'table_id' in Order._fields:
                order_dict['table_id'] = int(table_id)
            if guests and 'customer_count' in Order._fields:
                order_dict['customer_count'] = int(guests)
            Order.sync_from_ui([order_dict])
            order = Order.search([('uuid', '=', uuid)], limit=1)

        # ---- graft combo + half-&-half parent/child lines, then re-total ----
        combo_kds = []
        if combo_carts:
            _cb, _ci, combo_kds = self._combo_apply(env, config, partner, order, combo_carts)
        if half_carts:
            _hb, _hi, half_kds = self._halfhalf_apply(env, config, partner, order, half_carts)
            combo_kds += half_kds
        if combo_carts or half_carts:
            tot_base = sum(order.lines.mapped('price_subtotal'))
            tot_incl = sum(order.lines.mapped('price_subtotal_incl'))
            order.write({'amount_tax': tot_incl - tot_base, 'amount_total': tot_incl})

        # ---- create one KDS ticket per station from the NEW items ----
        # (the combo parent line is a priced-0 section, so its real child dishes
        # are routed via combo_kds rather than the parent product.)
        course = len(set(Ticket.search([('pos_order_id', '=', order.id)]).mapped('fire_uuid'))) + 1
        items, fired_now = [], []
        for line in plain_lines:
            p = env['product.product'].browse(int(line['product_id']))
            qty = float(line.get('qty', 1.0))
            note = self._line_note(env, p, line)
            items.append((p, qty, note))
            fired_now.append({'product_id': p.id, 'name': p.display_name,
                              'qty': qty, 'station': self._station_of(p), 'note': note})
        for cp, cq, cnote in combo_kds:
            items.append((cp, cq, cnote))
            fired_now.append({'product_id': cp.id, 'name': cp.display_name,
                              'qty': cq, 'station': self._station_of(cp), 'note': cnote})
        tickets = self._make_station_tickets(env, order, items, fire_uuid, course,
                                             server_override=server_override)
        tickets._broadcast()

        # keep the cumulative fired snapshot fresh for /orders/get resume
        current = {}
        for l in order.lines:
            if l.qty > 0:
                current[str(l.product_id.id)] = current.get(str(l.product_id.id), 0.0) + l.qty
        order.sudo().write({'mezze_fired': json.dumps(current)})

        return {
            'ok': True, 'order_id': order.id, 'pos_reference': order.pos_reference,
            'tracking': order.tracking_number or order.pos_reference,
            'state': order.state, 'amount_total': order.amount_total,
            'table_id': order.table_id.id if order.table_id else None,
            'course': course, 'fire_uuid': fire_uuid,
            'fired_now': fired_now,
            'tickets': [t._payload() for t in tickets],
        }

    @http.route(f'{API_PREFIX}/orders/fire', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def order_fire(self, uuid=None, session_id=None, table_id=None, lines=None,
                   partner_id=None, guests=None, fire_uuid=None, **kw):
        """Fire a course to the kitchen with APPEND semantics.

        ``lines`` is the set of items being added *now* (not the whole cart), so
        two waiters firing to the same table both add their items instead of
        clobbering each other. Delegates to the shared ``_do_fire`` core.
        """
        auth = self._authenticate()
        if auth:
            return auth
        if not uuid:
            return self._json({'ok': False, 'error': 'missing_uuid'}, status=400)
        if not lines:
            return self._json({'ok': False, 'error': 'no_lines'}, status=400)
        env = self._api_env()
        if not fire_uuid:
            sig = hashlib.sha1(json.dumps(lines, sort_keys=True).encode()).hexdigest()[:12]
            fire_uuid = '%s:%s' % (uuid, sig)
        log = env['mezze.sync.log'].sudo().create({'name': 'Fire %s' % uuid, 'uuid': uuid, 'status': 'received'})
        try:
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            session = session.with_env(env)
            config = config.with_env(env)
            result = self._do_fire(env, uuid, session, config, table_id, lines,
                                   partner_id, guests, fire_uuid)
            log.write({'status': 'ok', 'pos_order_id': result.get('order_id'),
                       'session_id': session.id,
                       'message': 'idempotent replay' if result.get('idempotent')
                                  else 'Fired course %s (%d tickets)' % (result.get('course'), len(result.get('tickets', [])))})
            return result
        except Exception as exc:  # noqa: BLE001
            # Let PG concurrency errors bubble up so Odoo re-runs the whole fire
            # on a fresh snapshot (the advisory lock already serialized us; this
            # just handles the stale REPEATABLE-READ snapshot on the loser).
            _reraise_if_retryable(exc)
            _logger.exception("Mezze fire failed for uuid=%s", uuid)
            try:
                log.write({'status': 'error', 'message': str(exc)})
            except Exception:  # noqa: BLE001
                pass
            return self._json({'ok': False, 'error': 'fire_failed', 'uuid': uuid, 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/orders/pay', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def order_pay(self, uuid=None, order_id=None, payment_method_id=None,
                  partner_id=None, discount=None, discount_product_id=None, **kw):
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            order = (env['pos.order'].search([('uuid', '=', uuid)], limit=1)
                     if uuid else env['pos.order'].browse(int(order_id)))
            if not order.exists():
                raise ValueError("Unknown order")
            if order.state != 'draft':
                return {'ok': True, 'already': True, 'order_id': order.id,
                        'pos_reference': order.pos_reference, 'state': order.state,
                        'amount_total': order.amount_total}
            config = order.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            order = order.with_env(env)
            if partner_id and not order.partner_id:
                order.partner_id = int(partner_id)
            # loyalty redemption: append a tax-consistent discount line, refresh totals
            if discount and discount_product_id:
                d = float(discount)
                dp = env['product.product'].browse(int(discount_product_id))
                dtax = dp.taxes_id
                tv = dtax.compute_all(-d, config.currency_id, 1, product=dp) if dtax else None
                order.write({'lines': [(0, 0, {
                    'product_id': dp.id, 'qty': 1, 'price_unit': -d,
                    'price_subtotal': tv['total_excluded'] if tv else -d,
                    'price_subtotal_incl': tv['total_included'] if tv else -d,
                    'tax_ids': [(6, 0, dtax.ids)], 'pack_lot_ids': []})]})
                tot_base = sum(order.lines.mapped('price_subtotal'))
                tot_incl = sum(order.lines.mapped('price_subtotal_incl'))
                order.write({'amount_tax': tot_incl - tot_base, 'amount_total': tot_incl})
            pm = (env['pos.payment.method'].browse(int(payment_method_id))
                  if payment_method_id else config.payment_method_ids[:1])
            order.add_payment({
                'amount': order.amount_total,
                'payment_method_id': pm.id,
                'name': fields.Datetime.now(),
                'pos_order_id': order.id,
            })
            order.action_pos_order_paid()
            earned, balance = self._loyalty_earn(env, order)
            self._audit(env, 'order.pay', order, **self._actor(env, kw),
                        detail=json.dumps({'via': 'order_pay'}))
            return {'ok': True, 'order_id': order.id, 'pos_reference': order.pos_reference,
                    'state': order.state, 'amount_total': order.amount_total,
                    'amount_paid': order.amount_paid,
                    'loyalty_earned': earned, 'loyalty_balance': balance}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze pay failed")
            return self._json({'ok': False, 'error': 'pay_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/orders/get', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def order_get(self, uuid=None, order_id=None, **kw):
        """Fetch one order's lines — used to resume an open table into the cart."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            order = (env['pos.order'].search([('uuid', '=', uuid)], limit=1)
                     if uuid else env['pos.order'].browse(int(order_id)))
            if not order.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            has_count = 'customer_count' in order._fields
            return {
                'ok': True, 'order_id': order.id, 'uuid': order.uuid,
                'pos_reference': order.pos_reference, 'state': order.state,
                'table_id': order.table_id.id if ('table_id' in order._fields and order.table_id) else None,
                'guests': order.customer_count if has_count else 0,
                'amount_total': order.amount_total,
                'lines': [{
                    'product_id': l.product_id.id, 'name': l.product_id.display_name,
                    'qty': l.qty, 'price_unit': l.price_unit,
                } for l in order.lines if l.qty > 0],
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze order_get failed")
            return self._json({'ok': False, 'error': 'get_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # QR ordering — public, per-table scoped self-service
    # ------------------------------------------------------------------
    def _qr_resolve(self, env, table_id, qr):
        """Validate a customer QR request. The (table_id, qr) pair is the ONLY
        credential the phone holds — it authorizes reading the menu and firing to
        THIS table, nothing else. Returns the table or raises."""
        if not table_id or not qr:
            raise ValueError("Missing table or QR token")
        table = env['restaurant.table'].sudo().browse(int(table_id))
        if not table.exists() or not table.mezze_qr_token or table.mezze_qr_token != qr:
            raise ValueError("Invalid QR token for this table")
        return table

    def _qr_config(self, env, table):
        """The pos.config a QR order for ``table`` should land in."""
        cfg = table.floor_id.pos_config_ids[:1] if 'pos_config_ids' in table.floor_id._fields else env['pos.config']
        return cfg or env['pos.config'].search([], limit=1)

    def _asset_version(self, filename):
        """Cache-busting stamp for a static front-end file: its mtime. Stable
        between deploys so browsers still cache the page, but it changes the
        moment the file is updated — a returning client then fetches the fresh
        build instead of a stale cached one. Falls back to '0' if not stat'able."""
        try:
            path = os.path.join(os.path.dirname(__file__), '..', 'static', filename)
            return str(int(os.path.getmtime(path)))
        except OSError:
            return '0'

    def _qr_asset_version(self):
        return self._asset_version('qr.html')

    @http.route('/mezze/pos', type='http', auth='user', methods=['GET'], csrf=False)
    def pos_launcher(self, **kw):
        """AUTHENTICATED entry to the POS front-end. Requires an Odoo login
        (staff), then hands the current shared API token to the front-end via a
        same-origin, path-scoped, SameSite=Strict **cookie** and redirects to a
        CLEAN url (no token in the query string). This keeps the token out of the
        URL bar / browser history / Referer header — closing the token-in-URL
        residual — while still gating access to authenticated users only (the
        token is never hardcoded in the frontend nor served to anonymous users,
        killing the old public 'test123'). The direct static URL keeps its
        ``?token=`` fallback for offline terminals. See docs/W1.md."""
        token = request.env['ir.config_parameter'].sudo().get_param(TOKEN_PARAM, '')
        parts = []
        if kw.get('base'):
            parts.append('base=%s' % quote(str(kw['base']), safe=''))
        parts.append('v=%s' % self._asset_version('pos.html'))
        url = '/mezze_bridge/static/pos.html?' + '&'.join(parts)
        resp = request.redirect(url, local=True)
        resp.set_cookie(
            'mezze_pos_token', token,
            max_age=12 * 3600, path='/mezze_bridge/static',
            samesite='Strict', httponly=False,
            secure=request.httprequest.is_secure)
        return resp

    @http.route(f'{API_PREFIX}/qr/table_link', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def qr_table_link(self, table_id=None, **kw):
        """Staff-only: mint (if needed) + return a table's customer QR link so the
        POS can show/print the code. The frontend builds the absolute URL and the
        QR image (via Odoo's /report/barcode) from location.origin."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            table = env['restaurant.table'].sudo().browse(int(table_id))
            if not table.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            token = table._mezze_ensure_qr_token()
            return {
                'ok': True, 'table_id': table.id, 'table_number': table.table_number,
                'qr_token': token,
                'path': '/mezze_bridge/static/qr.html?table=%s&qr=%s&v=%s' % (
                    table.id, token, self._qr_asset_version()),
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze qr_table_link failed")
            return self._json({'ok': False, 'error': 'link_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/qr/menu', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def qr_menu(self, table_id=None, qr=None, **kw):
        """Public: the customer menu for one table (scoped by its QR token)."""
        try:
            env = self._api_env()
            table = self._qr_resolve(env, table_id, qr)
            config = self._qr_config(env, table)
            if not config:
                return self._json({'ok': False, 'error': 'no_pos_config'}, status=404)
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            config = config.with_env(env)
            session = self._ensure_open_session(env, config)
            categories = env['pos.category'].search_read([], ['id', 'name'])
            products = env['product.product'].search_read(
                self._menu_domain(env),
                ['id', 'display_name', 'list_price', 'pos_categ_ids', 'type'])
            # customers never see 86'd items — hide them outright on the QR menu
            blocked86 = self._eightysix_ids(env, config.id)
            products = [p for p in products if p['id'] not in blocked86]
            for p in products:
                p['name'] = p.pop('display_name')
                prod = env['product.product'].browse(p['id'])
                p['modifiers'] = self._product_modifiers(env, prod)
                p['combos'] = self._product_combos(env, prod)
                p['is_combo'] = p['type'] == 'combo'
            return {
                'ok': True, 'session_id': session.id, 'config_id': config.id,
                'currency_id': config.currency_id.id,
                'table_id': table.id, 'table_number': table.table_number,
                'floor': table.floor_id.name,
                'categories': categories, 'products': products,
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze qr_menu failed")
            return self._json({'ok': False, 'error': 'qr_menu_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/qr/order', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def qr_order(self, table_id=None, qr=None, lines=None, uuid=None,
                 fire_uuid=None, guests=None, **kw):
        """Public: a customer fires a course to their table. Reuses the exact same
        concurrency-safe ``_do_fire`` core as the waiter path, so a customer and a
        waiter ringing the same table at once both land (no lost order). We fire
        to the VALIDATED table only — a spoofed table_id/config is ignored."""
        try:
            env = self._api_env()
            table = self._qr_resolve(env, table_id, qr)
            if not lines:
                return self._json({'ok': False, 'error': 'no_lines'}, status=400)
            config = self._qr_config(env, table)
            if not config:
                return self._json({'ok': False, 'error': 'no_pos_config'}, status=404)
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            config = config.with_env(env)
            session = self._ensure_open_session(env, config)
            uuid = uuid or 'qr-t%s-%s' % (table.id, session.id)
            if not fire_uuid:
                sig = hashlib.sha1(json.dumps(lines, sort_keys=True).encode()).hexdigest()[:12]
                fire_uuid = 'qr:%s:%s' % (uuid, sig)
            result = self._do_fire(env, uuid, session, config, table.id, lines,
                                   None, guests, fire_uuid, server_override='QR self-order')
            result['table_number'] = table.table_number
            return result
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            _logger.exception("Mezze qr_order failed")
            return self._json({'ok': False, 'error': 'qr_order_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Online storefront — public menu + pickup/delivery ordering
    # ------------------------------------------------------------------
    # A PUBLIC front-end (shop.html) reachable off-premise. The shopper's browser
    # holds a per-branch STORE TOKEN (like the QR table token) — enough to read
    # the menu and place a pickup/delivery order for THIS branch, nothing else.
    # Pickup fires a draft to the kitchen (paid at the counter on collection);
    # delivery reuses the paid-cash delivery flow (pay-on-delivery). Real online
    # CARD payment is the deliberately-excluded, externally-gated part.
    def _store_token(self, env, config, create=True):
        key = 'mezze_bridge.store_token_%s' % config.id
        Param = env['ir.config_parameter'].sudo()
        tok = Param.get_param(key)
        if not tok and create:
            tok = os.urandom(12).hex()
            Param.set_param(key, tok)
        return tok

    def _store_config(self, env, store):
        """Resolve a store token to its pos.config (raises if unknown)."""
        if not store:
            raise ValueError("Missing store token")
        Param = env['ir.config_parameter'].sudo()
        for cfg in env['pos.config'].sudo().search([]):
            if Param.get_param('mezze_bridge.store_token_%s' % cfg.id) == store:
                return cfg
        raise ValueError("Unknown store")

    @http.route(f'{API_PREFIX}/shop/link', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def shop_link(self, config_id=None, **kw):
        """Staff-only: get (or mint) the branch's public storefront URL."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, config_id)
            tok = self._store_token(env, config)
            return {'ok': True, 'config_id': config.id, 'branch': config.name,
                    'store': tok,
                    'url': '/mezze_bridge/static/shop.html?store=%s' % tok}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze shop_link failed")
            return self._json({'ok': False, 'error': 'shop_link_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/shop/config', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def shop_config(self, store=None, **kw):
        """Public: the store's identity, open/closed status, fulfillment options
        and delivery zones — everything the storefront needs to render."""
        env = self._api_env()
        try:
            config = self._store_config(env, store)
            session = env['pos.session'].search(
                [('config_id', '=', config.id), ('state', '=', 'opened')], limit=1)
            zones = env['mezze.delivery.zone'].search(
                ['&', ('active', '=', True), '|', ('config_id', '=', config.id),
                 ('config_id', '=', False)])
            return {
                'ok': True, 'branch': config.name, 'open': bool(session),
                'currency': config.currency_id.name,
                'fulfillment': ['pickup', 'delivery'],
                'zones': [self._zone_payload(z) for z in zones],
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze shop_config failed")
            return self._json({'ok': False, 'error': 'shop_config_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/shop/menu', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def shop_menu(self, store=None, **kw):
        """Public: the branch menu (products + modifiers + combos + half-&-half),
        86'd items excluded."""
        env = self._api_env()
        try:
            config = self._store_config(env, store)
            categories = env['pos.category'].search_read([], ['id', 'name'])
            catname = {c['id']: (c['name'] or '') for c in categories}
            products = env['product.product'].search_read(
                self._menu_domain(env),
                ['id', 'display_name', 'list_price', 'default_code',
                 'pos_categ_ids', 'type'])
            blocked = self._eightysix_ids(env, config.id)
            products = [p for p in products if p['id'] not in blocked]
            half_options = []
            for p in products:
                p['name'] = p.pop('display_name')
                prod = env['product.product'].browse(p['id'])
                p['modifiers'] = self._product_modifiers(env, prod)
                p['combos'] = self._product_combos(env, prod)
                p['is_combo'] = p['type'] == 'combo'
                p['half_base'] = (p.get('default_code') == 'HALFHALF')
                p['has_image'] = bool(prod.image_256)
                is_pizza = any('pizza' in catname.get(cid, '').lower()
                               for cid in (p.get('pos_categ_ids') or []))
                if is_pizza and not p['half_base']:
                    half_options.append({'id': p['id'], 'name': p['name'],
                                         'price': p['list_price']})
            return {'ok': True, 'branch': config.name,
                    'currency': config.currency_id.name,
                    'categories': categories, 'products': products,
                    'half_options': half_options}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze shop_menu failed")
            return self._json({'ok': False, 'error': 'shop_menu_failed', 'message': str(exc)}, status=400)

    @http.route([f'{API_PREFIX}/shop/image',
                 f'{API_PREFIX}/shop/image/<string:store>/<int:product>'],
                type='http', auth='none', methods=['GET'], csrf=False)
    def shop_image(self, store=None, product=None, **kw):
        """Public: stream a menu product's photo (store-token gated).

        Serves the native ``product.product`` image so the storefront can show
        real food photography. Only products actually available in POS are
        served; anything else (or a missing image) 404s so the front-end falls
        back to its illustrated tile. Cached for an hour."""
        try:
            env = self._api_env()
            config = self._store_config(env, store)     # validates the store token
            prod = env['product.product'].sudo().browse(int(product or 0))
            if not prod.exists() or not prod.available_in_pos:
                return request.not_found()
            data = prod.image_512 or prod.image_256 or prod.image_1920
            if not data:
                return request.not_found()
            img = base64.b64decode(data)
            return request.make_response(img, headers=[
                ('Content-Type', 'image/png'),
                ('Content-Length', str(len(img))),
                ('Cache-Control', 'public, max-age=3600'),
            ])
        except Exception:  # noqa: BLE001 - a broken image must never 500 the card
            return request.not_found()

    @http.route(f'{API_PREFIX}/shop/order', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def shop_order(self, store=None, lines=None, customer=None, phone=None,
                   fulfillment='pickup', address=None, zone_id=None, note=None,
                   uuid=None, **kw):
        """Public: place an online order. ``pickup`` fires a draft to the kitchen
        (settled at the counter); ``delivery`` creates a pay-on-delivery order +
        a delivery record. Returns a tracking number."""
        env = self._api_env()
        try:
            config = self._store_config(env, store)
            if not lines:
                return self._json({'ok': False, 'error': 'no_lines'}, status=400)
            session = env['pos.session'].search(
                [('config_id', '=', config.id), ('state', '=', 'opened')], limit=1)
            if not session:
                return self._json({'ok': False, 'error': 'store_closed',
                                   'message': 'The store is currently closed'}, status=409)
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            session = session.with_env(env)
            config = config.with_env(env)
            uuid = uuid or 'shop-%s-%s' % (config.id, os.urandom(4).hex())
            who = (customer or '').strip() or 'Online'

            if fulfillment == 'delivery':
                if not address:
                    return self._json({'ok': False, 'error': 'missing_address'}, status=400)
                partner = env['res.partner']
                order_lines, base, incl = self._build_lines(env, config, partner, lines)
                zone = env['mezze.delivery.zone'].browse(int(zone_id)) if zone_id \
                    else env['mezze.delivery.zone']
                if zone and zone.exists():
                    if zone.min_order and incl < zone.min_order:
                        raise ValueError("Order EGP %.2f is below the %s minimum of EGP %.2f"
                                         % (incl, zone.name, zone.min_order))
                    fee = zone.fee
                else:
                    fee = 0.0
                if fee > 0:
                    fp = self._delivery_fee_product(env)
                    order_lines.append((0, 0, {
                        'product_id': fp.id, 'qty': 1, 'price_unit': fee, 'discount': 0.0,
                        'tax_ids': [(6, 0, [])], 'price_subtotal': fee,
                        'price_subtotal_incl': fee, 'pack_lot_ids': []}))
                    incl += fee
                    base += fee
                pmid = config.payment_method_ids[:1].id
                order_dict = {
                    'uuid': uuid, 'session_id': session.id, 'company_id': config.company_id.id,
                    'user_id': env.uid, 'pricelist_id': config.pricelist_id.id or False,
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
                fee_pid = self._delivery_fee_product(env).id
                tickets = self._make_station_tickets(
                    env, order, [(l.product_id, l.qty, self._line_note(env, l.product_id, {}))
                                 for l in order.lines if l.product_id.id != fee_pid and l.qty > 0],
                    'shop:%s' % uuid, 1)
                tickets._broadcast()
                dlv = env['mezze.delivery'].create({
                    'pos_order_id': order.id, 'customer_name': who, 'phone': phone or False,
                    'address': address, 'fee': fee,
                    'zone_id': (zone.id if zone and zone.exists() else False),
                    'note': note or False, 'state': 'preparing'})
                self._audit(env, 'shop.order', order,
                            detail=json.dumps({'fulfillment': 'delivery', 'zone': dlv.zone_id.name}, default=str))
                return {'ok': True, 'fulfillment': 'delivery', 'order_id': order.id,
                        'tracking': order.tracking_number or order.pos_reference,
                        'total': round(order.amount_total, 2), 'fee': fee,
                        'eta_minutes': (zone.eta_minutes if zone and zone.exists() else 45)}

            # pickup: draft fires to the kitchen; paid at the counter on collect
            fire_uuid = 'shop:%s' % uuid
            result = self._do_fire(env, uuid, session, config, None, lines,
                                   None, None, fire_uuid, server_override='Online pickup')
            self._audit(env, 'shop.order', env['pos.order'].browse(result.get('order_id')),
                        detail=json.dumps({'fulfillment': 'pickup', 'who': who,
                                           'phone': phone}, default=str))
            return {'ok': True, 'fulfillment': 'pickup', 'order_id': result.get('order_id'),
                    'tracking': result.get('tracking') or result.get('pos_reference'),
                    'total': result.get('amount_total'), 'eta_minutes': 20}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze shop_order failed")
            return self._json({'ok': False, 'error': 'shop_order_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Customer feedback — post-order rating + comment (mezze.feedback)
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/feedback/submit', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def feedback_submit(self, store=None, rating=None, comment=None, customer=None,
                        phone=None, order_ref=None, **kw):
        """Public (store-token gated): a shopper rates their order 1–5 with an
        optional comment. Optionally links to the order by its receipt/tracking."""
        env = self._api_env()
        try:
            config = self._store_config(env, store)
            r = int(rating or 0)
            if not (1 <= r <= 5):
                return self._json({'ok': False, 'error': 'bad_rating',
                                   'message': 'Rating must be between 1 and 5'}, status=400)
            order = env['pos.order']
            if order_ref:
                order = env['pos.order'].search(
                    ['|', ('pos_reference', '=', str(order_ref)),
                     ('tracking_number', '=', str(order_ref))], limit=1)
            fb = env['mezze.feedback'].create({
                'config_id': config.id, 'pos_order_id': order.id or False, 'rating': r,
                'comment': (comment or '').strip() or False,
                'customer_name': (customer or '').strip() or False,
                'phone': (phone or '').strip() or False})
            self._audit(env, 'feedback.submit',
                        detail=json.dumps({'rating': r, 'config_id': config.id}, default=str))
            return {'ok': True, 'id': fb.id, 'rating': r}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze feedback submit failed")
            return self._json({'ok': False, 'error': 'feedback_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/feedback/list', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def feedback_list(self, config_id=None, limit=40, **kw):
        """Manager: recent feedback + average rating + star distribution."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, config_id)
            allfb = env['mezze.feedback'].search([('config_id', '=', config.id)])
            n = len(allfb)
            avg = round(sum(allfb.mapped('rating')) / n, 2) if n else 0.0
            dist = {i: 0 for i in range(1, 6)}
            for f in allfb:
                dist[f.rating] = dist.get(f.rating, 0) + 1
            recent = allfb.sorted(lambda f: (f.create_date or fields.Datetime.now()),
                                  reverse=True)[:int(limit or 40)]
            return {'ok': True, 'count': n, 'avg': avg, 'distribution': dist,
                    'items': [{
                        'id': f.id, 'rating': f.rating, 'comment': f.comment or '',
                        'who': f.customer_name or 'Guest',
                        'order': f.pos_order_id.pos_reference or None,
                        'date': fields.Datetime.to_string(f.create_date) if f.create_date else None,
                    } for f in recent]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze feedback list failed")
            return self._json({'ok': False, 'error': 'feedback_list_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Marketing — customer campaigns over email / SMS / WhatsApp
    # ------------------------------------------------------------------
    SEGMENTS = ['all', 'loyalty', 'recent']

    def _mkt_field(self, channel):
        return 'email' if channel == 'email' else 'phone'   # sms/whatsapp → phone

    def _mkt_audience(self, env, segment, channel):
        """Reachable partners for a segment on a channel (must have the channel's
        contact field). Segments: all customers · loyalty members · recent diners."""
        field = self._mkt_field(channel)
        dom = [(field, '!=', False)]
        if segment == 'loyalty':
            cards = env['loyalty.card'].sudo().search([])
            dom.append(('id', 'in', cards.mapped('partner_id').ids))
        elif segment == 'recent':
            since = fields.Datetime.to_string(
                fields.Datetime.now() - datetime.timedelta(days=30))
            orders = env['pos.order'].sudo().search(
                [('date_order', '>=', since), ('partner_id', '!=', False)])
            dom.append(('id', 'in', orders.mapped('partner_id').ids))
        else:
            dom.append(('customer_rank', '>', 0))
        return env['res.partner'].sudo().search(dom)

    @http.route(f'{API_PREFIX}/marketing/segments', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def marketing_segments(self, config_id=None, channel='email', **kw):
        """Audience size per segment for a channel — so the composer previews reach."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            out = {}
            for seg in self.SEGMENTS:
                out[seg] = len(self._mkt_audience(env, seg, channel))
            return {'ok': True, 'channel': channel, 'counts': out,
                    'whatsapp_ready': bool(env['ir.config_parameter'].sudo()
                                           .get_param('mezze_bridge.whatsapp_token'))}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze marketing_segments failed")
            return self._json({'ok': False, 'error': 'segments_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/marketing/send', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def marketing_send(self, config_id=None, channel='email', segment='all',
                       subject=None, body=None, name=None, **kw):
        """Dispatch a campaign to a segment. Email → native mail.mail; SMS → native
        sms.sms (queued; needs a gateway to leave); WhatsApp → queued pending a
        Meta Cloud token. Records a mezze.campaign for the back-office history."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            if channel not in ('email', 'sms', 'whatsapp'):
                raise ValueError("Unknown channel %s" % channel)
            if not (body or '').strip():
                raise ValueError("Message body is required")
            config = self._resolve_config(env, config_id)
            partners = self._mkt_audience(env, segment, channel)
            sent, state = 0, 'sent'
            if channel == 'email':
                for p in partners:
                    env['mail.mail'].sudo().create({
                        'subject': (subject or 'Mezze').strip(),
                        'body_html': '<p>%s</p>' % (body or '').strip(),
                        'email_to': p.email, 'auto_delete': False})
                    sent += 1
                state = 'sent'                          # queued to Odoo outbox
            elif channel == 'sms':
                for p in partners:
                    env['sms.sms'].sudo().create({'number': p.phone, 'body': (body or '').strip()})
                    sent += 1
                state = 'queued'                        # needs SMS gateway / IAP
            else:                                       # whatsapp — gated on Meta Cloud token
                sent, state = 0, 'queued'
            camp = env['mezze.campaign'].sudo().create({
                'name': (name or '').strip() or '%s · %s' % (channel.title(), segment),
                'config_id': config.id, 'channel': channel, 'segment': segment,
                'subject': (subject or '').strip() or False, 'body': (body or '').strip(),
                'state': state, 'audience_count': len(partners), 'sent_count': sent})
            self._audit(env, 'marketing.send', **self._actor(env, kw),
                        detail=json.dumps({'channel': channel, 'segment': segment,
                                           'audience': len(partners), 'sent': sent}, default=str))
            return {'ok': True, 'campaign_id': camp.id, 'channel': channel,
                    'audience': len(partners), 'sent': sent, 'state': state,
                    'note': ('Queued — needs a live gateway to leave' if state == 'queued'
                             else 'Queued to the Odoo mail outbox')}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze marketing_send failed")
            return self._json({'ok': False, 'error': 'marketing_send_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/marketing/campaigns', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def marketing_campaigns(self, config_id=None, limit=30, **kw):
        """Recent campaigns for the back-office history."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, config_id)
            camps = env['mezze.campaign'].sudo().search(
                [('config_id', '=', config.id)], order='create_date desc', limit=int(limit or 30))
            return {'ok': True, 'items': [{
                'id': c.id, 'name': c.name, 'channel': c.channel, 'segment': c.segment,
                'state': c.state, 'audience': c.audience_count, 'sent': c.sent_count,
                'date': fields.Datetime.to_string(c.create_date) if c.create_date else None,
            } for c in camps]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze marketing_campaigns failed")
            return self._json({'ok': False, 'error': 'campaigns_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Session close — reuse core close so accounting posts
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/sessions/<int:session_id>/close', type='json2',
                auth='none', methods=['POST'], csrf=False, cors='*')
    def session_close(self, session_id, **kw):
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                return self._json({'ok': False, 'error': 'unknown_session',
                                   'message': "Unknown session_id %s" % session_id},
                                  status=404)
            env = env(context=dict(env.context, allowed_company_ids=[session.config_id.company_id.id], company_id=session.config_id.company_id.id))
            session = session.with_env(env)

            if session.state != 'closed':
                # Core close entry point: closing_control -> validate ->
                # _create_account_move -> post. Produces the journal entry.
                session.action_pos_session_closing_control()

            move = session.move_id
            return {
                'ok': True,
                'session': session.name,
                'session_id': session.id,
                'state': session.state,
                'account_move_ids': move.ids,
                'account_move_names': move.mapped('name'),
                'balance': sum(move.line_ids.mapped('balance')) if move else 0.0,
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze session close failed for session_id=%s", session_id)
            return self._json({
                'ok': False,
                'error': 'close_failed',
                'session_id': session_id,
                'message': str(exc),
            }, status=400)

    # ------------------------------------------------------------------
    # Recent orders — for the Refund flow's order picker
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/orders/recent', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def orders_recent(self, session_id=None, limit=20, **kw):
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            dom = [('state', 'in', ('paid', 'done', 'invoiced')), ('amount_total', '>', 0)]
            if session_id:
                dom.append(('session_id', '=', int(session_id)))
            orders = env['pos.order'].search(dom, order='date_order desc', limit=int(limit or 20))
            return {'ok': True, 'orders': [{
                'id': o.id, 'pos_reference': o.pos_reference, 'uuid': o.uuid,
                'amount_total': o.amount_total, 'session_id': o.session_id.id,
                'date_order': fields.Datetime.to_string(o.date_order),
                'partner': o.partner_id.name or '',
                'tender': ', '.join(o.payment_ids.mapped('payment_method_id.name')) or 'Cash',
                'lines': [{
                    'line_id': l.id, 'product_id': l.product_id.id,
                    'name': l.product_id.display_name, 'qty': l.qty,
                    'price': l.price_subtotal_incl,
                } for l in o.lines if l.qty > 0],
            } for o in orders]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze orders_recent failed")
            return self._json({'ok': False, 'error': 'recent_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Refund — a real negative pos.order via sync_from_ui
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/orders/refund', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def order_refund(self, uuid=None, session_id=None, original_order_id=None,
                     lines=None, reason=None, **kw):
        auth = self._authenticate()
        if auth:
            return auth
        if not uuid:
            return self._json({'ok': False, 'error': 'missing_uuid'}, status=400)
        env = self._api_env()
        log = env['mezze.sync.log'].sudo().create({'name': 'Refund %s' % uuid, 'uuid': uuid, 'status': 'received'})
        try:
            existing = env['pos.order'].search([('uuid', '=', uuid)], limit=1)
            if existing:
                return {'ok': True, 'duplicate': True, 'order_id': existing.id,
                        'pos_reference': existing.pos_reference, 'amount_total': existing.amount_total}
            # W2: optional manager approval for refunds (config-gated so small
            # shops aren't forced into it). approver_cashier_id is a supervisor+
            # verified on the client via /w1/approve.
            if str(env['ir.config_parameter'].sudo().get_param(
                    'mezze_bridge.require_approval_refund', '')).strip().lower() in ('1', 'true'):
                # W2-1: verify a signed approval TOKEN (minted by /w1/approve after
                # a PIN check), not a client-supplied id — the client can't forge it.
                approver_id = approval.verify(env, kw.get('approval_token'), 'refund')
                approver = (env['mezze.cashier'].browse(approver_id)
                            if approver_id else env['mezze.cashier'])
                if not approver.exists() or approver.role not in ('supervisor', 'manager'):
                    return self._json({'ok': False, 'error': 'approval_required',
                                       'message': 'Refund requires a valid supervisor/manager approval.'}, status=403)
                kw['approver_cashier_id'] = approver.id   # record the VERIFIED approver
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            session = session.with_env(env)
            config = config.with_env(env)
            orig = env['pos.order'].browse(int(original_order_id)) if original_order_id else env['pos.order']
            has_refund_link = 'refunded_orderline_id' in env['pos.order.line']._fields
            order_lines = []
            total = 0.0          # tax-INCLUSIVE refund total (what the customer gets back)
            total_base = 0.0     # tax-excluded, for amount_tax
            currency = session.currency_id
            fp = ((orig.partner_id.property_account_position_id if orig and orig.partner_id else False)
                  or config.default_fiscal_position_id)
            for line in (lines or []):
                product = env['product.product'].browse(int(line['product_id']))
                qty = -abs(float(line.get('qty', 1.0)))          # negative = refund
                price = float(line.get('price_unit', product.lst_price))
                company_taxes = product.taxes_id.filtered(lambda t: t.company_id == config.company_id)
                taxes = fp.map_tax(company_taxes) if fp else company_taxes
                if taxes:
                    tv = taxes.compute_all(price, currency, qty, product=product,
                                           partner=orig.partner_id if orig else False)
                    sub, sub_incl = tv['total_excluded'], tv['total_included']
                else:
                    sub = sub_incl = price * qty
                total += sub_incl                                 # refund the tax-inclusive amount paid
                total_base += sub
                vals = {'product_id': product.id, 'qty': qty, 'price_unit': price, 'discount': 0.0,
                        'tax_ids': [(6, 0, taxes.ids)], 'price_subtotal': sub,
                        'price_subtotal_incl': sub_incl, 'pack_lot_ids': []}
                if has_refund_link and line.get('line_id'):
                    vals['refunded_orderline_id'] = int(line['line_id'])
                order_lines.append((0, 0, vals))
            pm = config.payment_method_ids[:1]
            payments = [(0, 0, {'amount': total, 'name': fields.Datetime.now(),
                                'payment_method_id': pm.id})] if pm else []
            order_dict = {
                'uuid': uuid, 'session_id': session.id, 'company_id': config.company_id.id,
                'user_id': env.uid, 'partner_id': orig.partner_id.id or False,
                'pricelist_id': config.pricelist_id.id or False,
                'name': 'Refund of %s' % (orig.pos_reference or original_order_id or '-'),
                'date_order': fields.Datetime.to_string(fields.Datetime.now()),
                'lines': order_lines, 'payment_ids': payments,
                'amount_tax': round(total - total_base, 2),
                'amount_total': total, 'amount_paid': total, 'amount_return': 0.0,
                'last_order_preparation_change': '{}', 'to_invoice': False,
            }
            env['pos.order'].sync_from_ui([order_dict])
            order = env['pos.order'].search([('uuid', '=', uuid)], limit=1)
            log.write({'status': 'ok', 'pos_order_id': order.id, 'session_id': session.id,
                       'message': 'Refund (%s) via sync_from_ui' % (reason or 'n/a')})
            self._audit(env, 'order.refund', order, severity='warning',
                        **self._actor(env, kw),
                        detail=json.dumps({'reason': reason or '',
                                           'reason_code': kw.get('reason_code') or '',
                                           'original_order_id': original_order_id,
                                           'approver_cashier_id': kw.get('approver_cashier_id')}, default=str))
            return {'ok': True, 'order_id': order.id, 'pos_reference': order.pos_reference,
                    'amount_total': order.amount_total}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze refund failed for uuid=%s", uuid)
            try:
                log.write({'status': 'error', 'message': str(exc)})
            except Exception:  # noqa: BLE001
                pass
            return self._json({'ok': False, 'error': 'refund_failed', 'uuid': uuid, 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Comp — a manager-approved, 100%-off giveaway tracked apart from discounts
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/orders/comp', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def order_comp(self, session_id=None, order_uuid=None, order_id=None,
                   line_id=None, product_id=None, reason=None, reason_code=None, **kw):
        """Comp (make complimentary) a line on an OPEN order: a 100%-off,
        reason-coded giveaway recorded as its OWN ``order.comp`` audit event so
        it reports separately from ordinary discounts — comps are a classic
        shrinkage/theft vector, so a restaurant tracks (and caps) them apart.

        Distinct from a *void* (item never made) — a comp WAS made and served,
        just not charged, so the KDS ticket stands and only the money changes.
        Applied to the draft, it flows through /orders/pay at settle. Manager
        approval is required by DEFAULT (disable per-branch with the
        ``mezze_bridge.require_approval_comp=0`` config param)."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            # approval gate — default ON for comps (unlike refund, which is opt-in)
            gate = str(env['ir.config_parameter'].sudo().get_param(
                'mezze_bridge.require_approval_comp', '1')).strip().lower()
            if gate not in ('0', 'false', 'no', 'off'):
                approver_id = approval.verify(env, kw.get('approval_token'), 'comp')
                approver = (env['mezze.cashier'].browse(approver_id) if approver_id
                            else env['mezze.cashier'])
                if not approver.exists() or approver.role not in ('supervisor', 'manager'):
                    return self._json({'ok': False, 'error': 'approval_required',
                                       'message': 'Comp requires a valid supervisor/manager approval.'},
                                      status=403)
                kw['approver_cashier_id'] = approver.id
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            Order = env['pos.order']
            order = (Order.browse(int(order_id)) if order_id
                     else Order.search([('uuid', '=', order_uuid),
                                        ('session_id', '=', session.id)], limit=1))
            if not order.exists():
                raise ValueError("Order not found")
            if order.state != 'draft':
                raise ValueError("Only an open (unpaid) order can be comped")
            # resolve the target line (explicit line_id, else first un-comped
            # line of the product)
            if line_id:
                line = order.lines.filtered(lambda l: l.id == int(line_id))[:1]
            elif product_id:
                line = order.lines.filtered(
                    lambda l: l.product_id.id == int(product_id) and l.discount < 100)[:1]
            else:
                line = env['pos.order.line']
            if not line:
                raise ValueError("Comp target line not found on the order")
            comped_incl = line.price_subtotal_incl
            note = 'COMP' + ((': ' + reason) if reason else '')
            vals = {'discount': 100.0, 'price_subtotal': 0.0, 'price_subtotal_incl': 0.0}
            if 'customer_note' in line._fields:
                vals['customer_note'] = ((line.customer_note + ' · ') if line.customer_note else '') + note
            line.write(vals)
            # recompute the order total across all lines
            tot_base = sum(order.lines.mapped('price_subtotal'))
            tot_incl = sum(order.lines.mapped('price_subtotal_incl'))
            order.write({'amount_tax': tot_incl - tot_base, 'amount_total': tot_incl})
            self._audit(env, 'order.comp', order, severity='warning',
                        **self._actor(env, kw),
                        detail=json.dumps({'reason': reason or '', 'reason_code': reason_code or '',
                                           'product': line.product_id.display_name,
                                           'line_id': line.id, 'comped_amount': comped_incl,
                                           'approver_cashier_id': kw.get('approver_cashier_id')},
                                          default=str))
            return {'ok': True, 'order_id': order.id, 'pos_reference': order.pos_reference,
                    'line_id': line.id, 'comped_amount': round(comped_incl, 2),
                    'amount_total': order.amount_total}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze comp failed")
            return self._json({'ok': False, 'error': 'comp_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/orders/exchange', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def order_exchange(self, uuid=None, session_id=None, original_order_id=None,
                       return_lines=None, new_lines=None, payments=None,
                       partner_id=None, reason=None, **kw):
        """Exchange = refund the returned items + sell the replacement items, as
        two linked orders. Net cash movement = new_total − return_total (the
        replacement is paid in full; the return is refunded in full). Reuses the
        existing refund + sync flows verbatim, so tax/idempotency/audit all hold.
        Even exchange -> net ~0; price difference -> the payments settle the new
        side. The pair is linked by an 'order.exchange' audit row."""
        auth = self._authenticate()
        if auth:
            return auth
        if not uuid:
            return self._json({'ok': False, 'error': 'missing_uuid'}, status=400)
        out = {'ok': True, 'exchange_ref': uuid}
        if return_lines:
            r = self.order_refund(uuid='%s-ret' % uuid, session_id=session_id,
                                  original_order_id=original_order_id, lines=return_lines,
                                  reason=reason or 'exchange', reason_code='exchange', **kw)
            out['refund'] = r if isinstance(r, dict) else {'ok': False}
        if new_lines:
            s = self.order_sync(uuid='%s-new' % uuid, session_id=session_id,
                                lines=new_lines, payments=payments, partner_id=partner_id, **kw)
            out['sale'] = s if isinstance(s, dict) else {'ok': False}
        try:
            env = self._api_env()
            env['mezze.audit.log'].log('order.exchange', **self._actor(env, kw),
                detail=json.dumps({'exchange_ref': uuid, 'original_order_id': original_order_id,
                                   'refund_ref': (out.get('refund') or {}).get('pos_reference'),
                                   'sale_ref': (out.get('sale') or {}).get('pos_reference'),
                                   'reason': reason}, default=str))
        except Exception:  # noqa: BLE001
            _logger.exception("Mezze exchange audit failed")
        return out

    # ------------------------------------------------------------------
    # Floors + tables (pos_restaurant) — gracefully degrades if absent
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/floors', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def floors(self, config_id=None, **kw):
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            if 'restaurant.floor' not in env:
                return {'ok': True, 'available': False, 'floors': []}
            Table = env['restaurant.table']
            name_field = 'table_number' if 'table_number' in Table._fields else 'name'
            has_count = 'customer_count' in env['pos.order']._fields
            cfg_id = int(config_id) if config_id else None
            floor_dom = [('pos_config_ids', 'in', cfg_id)] if cfg_id else []
            # live occupancy: open (draft) orders grouped by table (this branch)
            draft_dom = [('state', '=', 'draft'), ('table_id', '!=', False)]
            if cfg_id:
                draft_dom.append(('config_id', '=', cfg_id))
            drafts = env['pos.order'].search(draft_dom)
            by_table = {}
            for o in drafts:
                by_table.setdefault(o.table_id.id, env['pos.order'])
                by_table[o.table_id.id] |= o
            now = fields.Datetime.now()
            # upcoming reservations "holding" a table right now (arriving soon,
            # not yet seated) — earliest per table
            res_by_table = {}
            if 'mezze.reservation' in env:
                soon = now + datetime.timedelta(minutes=self.RES_LEAD_MIN)
                res_dom = [('state', '=', 'booked'),
                           ('start', '>=', fields.Datetime.to_string(now - datetime.timedelta(minutes=20))),
                           ('start', '<=', fields.Datetime.to_string(soon))]
                if cfg_id:
                    res_dom.append(('config_id', '=', cfg_id))
                for r in env['mezze.reservation'].search(res_dom, order='start asc'):
                    res_by_table.setdefault(r.table_id.id, r)
            out = []
            for fl in env['restaurant.floor'].search(floor_dom):
                tables = []
                for t in fl.table_ids:
                    if not t.active:
                        continue
                    td = {
                        'id': t.id, 'name': str(t[name_field]),
                        'seats': t.seats, 'shape': t.shape,
                        'x': t.position_h, 'y': t.position_v,
                        'w': t.width, 'h': t.height,
                        'status': 'available', 'total': 0.0, 'guests': 0,
                        'minutes': 0, 'server': None, 'order_uuid': None,
                        'reservation': None,
                    }
                    dorders = by_table.get(t.id)
                    if dorders:
                        first = min(dorders.mapped('date_order'))
                        td.update({
                            'status': 'occupied',
                            'total': round(sum(dorders.mapped('amount_total')), 2),
                            'guests': sum(dorders.mapped('customer_count')) if has_count else 0,
                            'minutes': int((now - first).total_seconds() / 60),
                            'server': dorders[0].user_id.name or None,
                            'order_uuid': dorders[0].uuid,
                        })
                    elif res_by_table.get(t.id):
                        r = res_by_table[t.id]
                        td.update({
                            'status': 'reserved',
                            'guests': r.guests,
                            'reservation': {
                                'id': r.id, 'who': r._who(),
                                'start': fields.Datetime.to_string(r.start),
                                'time': fields.Datetime.to_string(r.start)[11:16],
                                'guests': r.guests, 'phone': r.phone or '',
                            },
                        })
                    tables.append(td)
                out.append({'id': fl.id, 'name': fl.name, 'tables': tables})
            return {'ok': True, 'available': True, 'floors': out}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze floors failed")
            return self._json({'ok': False, 'error': 'floors_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Table transfer / merge — full-service floor operations
    # ------------------------------------------------------------------
    def _open_table_order(self, env, session, table_id, order_uuid=None):
        """The single open (draft) order sitting on a table this session."""
        dom = [('table_id', '=', int(table_id)), ('state', '=', 'draft'),
               ('session_id', '=', session.id)]
        if order_uuid:
            dom.append(('uuid', '=', order_uuid))
        return env['pos.order'].search(dom, limit=1)

    def _lock_tables(self, env, *table_ids):
        """Advisory-lock a set of tables in a STABLE order (ascending id) so two
        transfers touching the same pair can never deadlock. Shares the fire
        lock namespace, so a move also serializes against concurrent fires/pays
        on those tables."""
        for k in sorted({int(t) for t in table_ids if t}):
            env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)", (self._FIRE_LOCK_NS, k))

    @staticmethod
    def _table_label(table):
        f = 'table_number' if 'table_number' in table._fields else 'name'
        return str(table[f])

    def _refire_snapshot(self, env, order):
        """Rebuild the cumulative fired-qty snapshot from the order's live lines
        (used after lines move between orders on a merge)."""
        current = {}
        for l in order.lines:
            if l.qty > 0:
                current[str(l.product_id.id)] = current.get(str(l.product_id.id), 0.0) + l.qty
        if 'mezze_fired' in order._fields:
            order.sudo().write({'mezze_fired': json.dumps(current)})

    @http.route(f'{API_PREFIX}/tables/transfer', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def table_transfer(self, session_id=None, from_table_id=None, to_table_id=None,
                       order_uuid=None, **kw):
        """Move an open order from one table to another. The destination must be
        FREE — a transfer onto an occupied table is rejected (use /tables/merge).
        KDS tickets follow the order; their table label is refreshed so the
        kitchen sees the new seat."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            session = session.with_env(env)
            src_id, dst_id = int(from_table_id), int(to_table_id)
            if src_id == dst_id:
                raise ValueError("Source and destination tables are the same")
            dst = env['restaurant.table'].browse(dst_id)
            if not dst.exists():
                raise ValueError("Unknown destination table %s" % dst_id)
            self._lock_tables(env, src_id, dst_id)
            order = self._open_table_order(env, session, src_id, order_uuid)
            if not order:
                raise ValueError("No open order on the source table")
            if self._open_table_order(env, session, dst_id):
                raise ValueError("Destination table is occupied — merge instead")
            order.write({'table_id': dst_id})
            label = self._table_label(dst)
            env['mezze.kds.ticket'].search([('pos_order_id', '=', order.id)]).write(
                {'table_label': label})
            self._audit(env, 'table.transfer', order, **self._actor(env, kw),
                        detail=json.dumps({'from': src_id, 'to': dst_id}))
            return {'ok': True, 'order_id': order.id, 'order_uuid': order.uuid,
                    'from_table_id': src_id, 'to_table_id': dst_id,
                    'table_label': label, 'amount_total': order.amount_total}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze table transfer failed")
            return self._json({'ok': False, 'error': 'transfer_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/tables/merge', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def table_merge(self, session_id=None, from_table_id=None, to_table_id=None, **kw):
        """Merge the open order on ``from_table`` INTO the open order on
        ``to_table``: all lines (combo parent+child links preserved, since they
        move together) and KDS tickets re-home onto the target, guest counts add
        up, the target keeps its own tracking number, and the emptied source
        draft is removed. If the target is free, this degrades to a transfer."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            session = session.with_env(env)
            src_id, dst_id = int(from_table_id), int(to_table_id)
            if src_id == dst_id:
                raise ValueError("Source and destination tables are the same")
            self._lock_tables(env, src_id, dst_id)
            src = self._open_table_order(env, session, src_id)
            if not src:
                raise ValueError("No open order on the source table")
            dst = self._open_table_order(env, session, dst_id)
            if not dst:
                # target free → this is really a transfer
                src.write({'table_id': dst_id})
                dtab = env['restaurant.table'].browse(dst_id)
                label = self._table_label(dtab)
                env['mezze.kds.ticket'].search([('pos_order_id', '=', src.id)]).write(
                    {'table_label': label})
                self._audit(env, 'table.transfer', src, **self._actor(env, kw),
                            detail=json.dumps({'from': src_id, 'to': dst_id, 'via': 'merge'}))
                return {'ok': True, 'merged': False, 'order_id': src.id,
                        'order_uuid': src.uuid, 'to_table_id': dst_id,
                        'table_label': label, 'amount_total': src.amount_total}
            # re-home the source's lines and KDS tickets onto the target
            src.lines.write({'order_id': dst.id})
            env['mezze.kds.ticket'].search([('pos_order_id', '=', src.id)]).write(
                {'pos_order_id': dst.id})
            label = self._table_label(env['restaurant.table'].browse(dst_id))
            env['mezze.kds.ticket'].search([('pos_order_id', '=', dst.id)]).write(
                {'table_label': label})
            if 'customer_count' in dst._fields:
                dst.customer_count = (dst.customer_count or 0) + (src.customer_count or 0)
            # recompute the target total across the combined lines
            tot_base = sum(dst.lines.mapped('price_subtotal'))
            tot_incl = sum(dst.lines.mapped('price_subtotal_incl'))
            dst.write({'amount_tax': tot_incl - tot_base, 'amount_total': tot_incl})
            self._refire_snapshot(env, dst)
            src_ref = src.pos_reference
            src.unlink()                     # emptied draft — safe to remove
            self._audit(env, 'table.merge', dst, **self._actor(env, kw),
                        detail=json.dumps({'from': src_id, 'to': dst_id,
                                           'source_ref': src_ref}))
            return {'ok': True, 'merged': True, 'order_id': dst.id,
                    'order_uuid': dst.uuid, 'to_table_id': dst_id,
                    'table_label': label, 'amount_total': dst.amount_total}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze table merge failed")
            return self._json({'ok': False, 'error': 'merge_failed',
                               'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # 86 — mark a menu item unavailable, live, per branch
    # ------------------------------------------------------------------
    # "86ing" is a temporary stockout ("we're out of the salmon"), not a permanent
    # catalog change — so we DON'T flip the global product.available_in_pos (that
    # would 86 the item across every branch). Instead we keep a per-config set of
    # 86'd product ids and broadcast it live, so one branch running out never
    # blanks the dish on another branch's menu.
    def _eightysix_key(self, config_id):
        return 'mezze_bridge.eightysix_%s' % int(config_id or 0)

    def _eightysix_ids(self, env, config_id):
        raw = env['ir.config_parameter'].sudo().get_param(self._eightysix_key(config_id), '[]')
        try:
            return set(int(i) for i in json.loads(raw))
        except Exception:  # noqa: BLE001
            return set()

    def _set_eightysix_ids(self, env, config_id, ids):
        env['ir.config_parameter'].sudo().set_param(
            self._eightysix_key(config_id), json.dumps(sorted(int(i) for i in ids)))

    def _assert_available(self, env, config, products):
        """Raise if any of ``products`` is currently 86'd on this config — a stale
        client can't push an order for an item the branch has run out of."""
        blocked = self._eightysix_ids(env, config.id)
        for p in products:
            if p.id in blocked:
                raise ValueError("'%s' is 86'd (out of stock) — remove it to continue"
                                 % p.display_name)

    @http.route(f'{API_PREFIX}/menu/eightysix', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def menu_eightysix(self, config_id=None, product_id=None, available=None, **kw):
        """One-tap 86 / restore for a menu item on THIS branch. ``available=false``
        86s it; ``available=true`` restores it. Broadcasts ``mezze_menu_86`` on the
        branch's waiter channel so every terminal greys (or un-greys) the tile
        instantly, and audits the call."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            cfg = int(config_id or 0)
            pid = int(product_id)
            product = env['product.product'].browse(pid)
            if not product.exists():
                raise ValueError("Unknown product_id %s" % product_id)
            ids = self._eightysix_ids(env, cfg)
            make_unavailable = str(available).strip().lower() in ('0', 'false', 'no', 'none', '')
            if make_unavailable:
                ids.add(pid)
            else:
                ids.discard(pid)
            self._set_eightysix_ids(env, cfg, ids)
            payload = {'product_id': pid, 'available': not make_unavailable,
                       'name': product.display_name}
            env['bus.bus'].sudo()._sendone('mezze_waiter_%s' % cfg, 'mezze_menu_86', payload)
            self._audit(env, 'menu.86', **self._actor(env, kw),
                        detail=json.dumps({'product': product.display_name, 'product_id': pid,
                                           'action': '86' if make_unavailable else 'restore',
                                           'config_id': cfg}, default=str))
            return {'ok': True, 'product_id': pid, 'available': not make_unavailable,
                    'count_86': len(ids)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze 86 failed")
            return self._json({'ok': False, 'error': 'eightysix_failed',
                               'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Customer-facing display (CFD) — a second screen mirroring the live cart
    # ------------------------------------------------------------------
    # The cashier terminal PUSHES a cart snapshot on every change; the snapshot
    # is stored per branch and broadcast on the CFD bus channel so a second
    # screen (cfd.html) reflects it instantly. No new model — the snapshot is a
    # small JSON blob in a config param, same pattern as 86 / quick keys.
    def _cfd_key(self, config_id):
        return 'mezze_bridge.cfd_%s' % int(config_id or 0)

    @http.route(f'{API_PREFIX}/cfd/push', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def cfd_push(self, config_id=None, lines=None, subtotal=0.0, tax=0.0,
                 total=0.0, state='building', change=0.0, **kw):
        """Cashier → CFD: store + broadcast the current cart snapshot."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            cfg = int(config_id or 0)
            snap = {
                'lines': [{'name': str(l.get('name', '')), 'qty': float(l.get('qty', 0) or 0),
                           'price': float(l.get('price', 0) or 0)} for l in (lines or [])],
                'subtotal': round(float(subtotal or 0), 2), 'tax': round(float(tax or 0), 2),
                'total': round(float(total or 0), 2), 'state': state,
                'change': round(float(change or 0), 2),
            }
            env['ir.config_parameter'].sudo().set_param(self._cfd_key(cfg), json.dumps(snap))
            env['bus.bus'].sudo()._sendone('mezze_cfd_%s' % cfg, 'mezze_cfd_update', snap)
            return {'ok': True}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze cfd_push failed")
            return self._json({'ok': False, 'error': 'cfd_push_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/cfd/state', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def cfd_state(self, config_id=None, **kw):
        """CFD screen → server: the last cart snapshot + branch identity + the bus
        channel to subscribe to for live updates."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, config_id)
            cfg = config.id
            raw = env['ir.config_parameter'].sudo().get_param(self._cfd_key(cfg), '{}')
            try:
                snap = json.loads(raw)
            except Exception:  # noqa: BLE001
                snap = {}
            return {'ok': True, 'snapshot': snap or None,
                    'branch': config.name, 'currency': config.currency_id.name,
                    'channel': 'mezze_cfd_%s' % cfg,
                    'last_bus_id': env['bus.bus'].sudo()._bus_last_id()}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze cfd_state failed")
            return self._json({'ok': False, 'error': 'cfd_state_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Time clock — staff attendance (mezze.attendance on mezze.cashier)
    # ------------------------------------------------------------------
    def _day_start(self, env):
        """Start-of-today (UTC, naive) for 'today' attendance queries."""
        return fields.Datetime.to_string(fields.Datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0))

    @http.route(f'{API_PREFIX}/clock/toggle', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def clock_toggle(self, code=None, pin=None, config_id=None, **kw):
        """Staff clock in / out with their OWN code + PIN (so nobody clocks a
        colleague). Toggles: an open record → clock OUT; none → clock IN."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            cashier = env['mezze.cashier'].sudo().search(
                [('code', '=', code), ('active', '=', True)], limit=1)
            if not cashier or not cashier.check_pin(pin):
                self._audit(env, 'clock.denied', severity='warning',
                            detail=json.dumps({'code': code}, default=str))
                return self._json({'ok': False, 'error': 'bad_credentials',
                                   'message': 'Wrong staff code or PIN'}, status=401)
            Att = env['mezze.attendance']
            openrec = Att._open_for(cashier)
            if openrec:
                openrec.write({'check_out': fields.Datetime.now()})
                action, rec = 'out', openrec
            else:
                rec = Att.create({'cashier_id': cashier.id,
                                  'config_id': int(config_id) if config_id else False})
                action = 'in'
            self._audit(env, 'clock.%s' % action, cashier_id=cashier.id,
                        detail=json.dumps({'name': cashier.name,
                                           'worked_hours': rec.worked_hours}, default=str))
            return {'ok': True, 'action': action, 'clocked_in': action == 'in',
                    'cashier': cashier.name, 'role': cashier.role,
                    'since': fields.Datetime.to_string(rec.check_in),
                    'worked_hours': round(rec.worked_hours, 2)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze clock toggle failed")
            return self._json({'ok': False, 'error': 'clock_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/clock/list', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def clock_list(self, config_id=None, **kw):
        """Today's attendance: who's on the clock now + hours worked per person."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            Att = env['mezze.attendance']
            now = fields.Datetime.now()
            recs = Att.search([('check_in', '>=', self._day_start(env))])
            by_cashier = {}
            for a in recs:
                c = a.cashier_id
                d = by_cashier.setdefault(c.id, {
                    'cashier_id': c.id, 'name': c.name, 'role': c.role,
                    'clocked_in': False, 'since': None, 'hours_today': 0.0})
                if a.check_out:
                    d['hours_today'] += a.worked_hours
                else:                        # open shift → count elapsed so far
                    d['clocked_in'] = True
                    d['since'] = fields.Datetime.to_string(a.check_in)
                    d['hours_today'] += (now - a.check_in).total_seconds() / 3600.0
            staff = sorted(by_cashier.values(),
                           key=lambda s: (not s['clocked_in'], s['name']))
            for s in staff:
                s['hours_today'] = round(s['hours_today'], 2)
            return {'ok': True, 'staff': staff,
                    'on_clock': sum(1 for s in staff if s['clocked_in']),
                    'hours_total': round(sum(s['hours_today'] for s in staff), 2)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze clock list failed")
            return self._json({'ok': False, 'error': 'clock_list_failed',
                               'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Quick keys — a manager-curated favourites strip, per branch
    # ------------------------------------------------------------------
    # Distinct from the AI "suggested" strip (which is data-driven market-basket):
    # these are hand-pinned fast movers a manager wants one tap away. Stored as an
    # ORDERED per-config list so the strip layout is stable.
    def _quickkeys_key(self, config_id):
        return 'mezze_bridge.quickkeys_%s' % int(config_id or 0)

    def _quickkeys(self, env, config_id):
        raw = env['ir.config_parameter'].sudo().get_param(self._quickkeys_key(config_id), '[]')
        try:
            return [int(i) for i in json.loads(raw)]
        except Exception:  # noqa: BLE001
            return []

    def _set_quickkeys(self, env, config_id, ids):
        env['ir.config_parameter'].sudo().set_param(
            self._quickkeys_key(config_id), json.dumps([int(i) for i in ids]))

    @http.route(f'{API_PREFIX}/menu/quickkeys', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def menu_quickkeys(self, config_id=None, product_id=None, pinned=None,
                       order=None, **kw):
        """Pin/unpin a product to this branch's quick-keys strip, or reorder it.

        - ``product_id`` + ``pinned`` (bool): add/remove that product.
        - ``order`` (list of product ids): replace the whole strip order.

        Returns the resulting ordered list. Broadcasts ``mezze_quickkeys`` so
        other terminals refresh their strip."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            cfg = int(config_id or 0)
            ids = self._quickkeys(env, cfg)
            if order is not None:
                ids = [int(i) for i in order]
            elif product_id is not None:
                pid = int(product_id)
                want = str(pinned).strip().lower() not in ('0', 'false', 'no', 'none', '')
                if want and pid not in ids:
                    ids.append(pid)
                elif not want and pid in ids:
                    ids = [i for i in ids if i != pid]
            self._set_quickkeys(env, cfg, ids)
            env['bus.bus'].sudo()._sendone('mezze_waiter_%s' % cfg, 'mezze_quickkeys',
                                           {'quick_keys': ids})
            self._audit(env, 'menu.quickkeys', **self._actor(env, kw),
                        detail=json.dumps({'config_id': cfg, 'count': len(ids),
                                           'product_id': product_id}, default=str))
            return {'ok': True, 'quick_keys': ids}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze quickkeys failed")
            return self._json({'ok': False, 'error': 'quickkeys_failed',
                               'message': str(exc)}, status=400)

    def _recipe_cost(self, product):
        """Live *theoretical* recipe cost per unit, exploded from the product's
        BoM using current component standard_prices (one level). This is the
        ERP-native food cost Odoo only reconciles at session close — we compute
        it per sale. Falls back to the product's own standard_price when no BoM
        exists, so non-recipe items still cost cleanly."""
        env = product.env
        if 'mrp.bom' not in env:
            return product.standard_price
        bom = env['mrp.bom'].search([
            '|', ('product_id', '=', product.id),
            '&', ('product_id', '=', False),
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
        ], limit=1)
        if bom and bom.product_qty:
            comp = sum(l.product_id.standard_price * l.product_qty for l in bom.bom_line_ids)
            return comp / bom.product_qty
        return product.standard_price

    # ------------------------------------------------------------------
    # Ops summary — real KPIs / top products / hourly sales / food-cost
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/ops/summary', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def ops_summary(self, config_id=None, **kw):
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            Order = env['pos.order']
            start = fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            dom = [('state', 'in', ('paid', 'done', 'invoiced')),
                   ('date_order', '>=', fields.Datetime.to_string(start))]
            if config_id:
                dom.append(('config_id', '=', int(config_id)))
            orders = Order.search(dom)
            net = sum(orders.mapped('amount_total'))
            tx = len(orders)
            rev = 0.0
            theo_cost = 0.0                    # live recipe (theoretical) COGS
            recipe_cache = {}
            bom_cache = {}
            comp_used = {}                     # component pid -> qty consumed today
            comp_prod = {}                     # component pid -> product record
            pstats = {}                        # pid -> live food-cost stats
            buckets = {}
            for o in orders:
                try:
                    hour = fields.Datetime.context_timestamp(o, o.date_order).hour
                except Exception:  # noqa: BLE001
                    hour = 0
                buckets[hour] = buckets.get(hour, 0.0) + o.amount_total
                for l in o.lines:
                    if l.qty <= 0:
                        continue
                    p = l.product_id
                    if p.id not in recipe_cache:
                        recipe_cache[p.id] = self._recipe_cost(p)
                    rc = recipe_cache[p.id]        # theoretical, per unit
                    bc = p.standard_price or 0.0   # actual booked, per unit
                    # explode the BoM to accumulate real component consumption
                    if p.id not in bom_cache:
                        bom_cache[p.id] = env['mrp.bom'].search([
                            '|', ('product_id', '=', p.id),
                            '&', ('product_id', '=', False),
                            ('product_tmpl_id', '=', p.product_tmpl_id.id),
                        ], limit=1) if 'mrp.bom' in env else env['pos.order'].browse()
                    bom = bom_cache[p.id]
                    if bom and bom.product_qty:
                        for bl in bom.bom_line_ids:
                            cid = bl.product_id.id
                            comp_used[cid] = comp_used.get(cid, 0.0) + (bl.product_qty / bom.product_qty) * l.qty
                            comp_prod[cid] = bl.product_id
                    sub = l.price_subtotal_incl
                    rev += sub
                    theo_cost += rc * l.qty
                    s = pstats.setdefault(p.id, {
                        'name': p.display_name, 'qty': 0.0, 'rev': 0.0,
                        'recipe': 0.0, 'booked': 0.0})
                    s['qty'] += l.qty
                    s['rev'] += sub
                    s['recipe'] += rc * l.qty
                    s['booked'] += bc * l.qty
            margin = ((rev - theo_cost) / rev * 100.0) if rev else 0.0
            top = sorted(pstats.values(), key=lambda x: -x['rev'])[:6]
            hourly = [{'h': h, 'v': round(buckets[h], 2)} for h in sorted(buckets)]
            # Burn-rate: project each ingredient's stock-out from real on-hand,
            # today's actual sales velocity, and the recipe consumption.
            now = fields.Datetime.now()
            first = min(orders.mapped('date_order')) if orders else now
            hours = max((now - first).total_seconds() / 3600.0, 0.5)
            burnrate = []
            for cid, used in comp_used.items():
                cp = comp_prod[cid]
                on_hand = cp.qty_available
                rate = used / hours                     # units consumed per hour
                if rate <= 0:
                    continue
                hto = on_hand / rate                    # hours to stock-out
                burnrate.append({
                    'name': cp.display_name, 'on_hand': round(on_hand, 1),
                    'used_today': round(used, 1), 'rate_per_hr': round(rate, 2),
                    'hours_to_out': round(hto, 1),
                })
            burnrate = sorted(burnrate, key=lambda x: x['hours_to_out'])
            foodcost = [{
                'name': s['name'], 'qty': s['qty'], 'revenue': round(s['rev'], 2),
                'theoretical': round(s['recipe'], 2),    # recipe cost, live
                'actual': round(s['booked'], 2),         # booked product cost
                'variance': round(s['booked'] - s['recipe'], 2),   # actual − theoretical
                'variance_pct': round((s['booked'] - s['recipe']) / s['recipe'] * 100, 1) if s['recipe'] else 0.0,
                'foodcost_pct': round(s['recipe'] / s['rev'] * 100, 1) if s['rev'] else 0.0,
            } for s in top]
            return {
                'ok': True,
                'net_sales': round(net, 2), 'tx': tx,
                'avg_ticket': round(net / tx, 2) if tx else 0.0,
                'margin': round(margin, 1),
                'theoretical_cost': round(theo_cost, 2),
                'top_products': [{'name': s['name'], 'revenue': round(s['rev'], 2)} for s in top],
                'hourly': hourly,
                'foodcost': foodcost,
                'burnrate': burnrate,
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ops_summary failed")
            return self._json({'ok': False, 'error': 'ops_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Manager dashboard — live shift command centre (real data)
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/manager/dashboard', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def manager_dashboard(self, config_id=None, sla_minutes=15, **kw):
        """A shift manager's command centre — everything the floor + kitchen +
        till say right now, from real Odoo records:

        * sales    — net / tx / avg ticket / live recipe margin (today, paid)
        * service  — open tabs (unpaid table drafts) + amount + oldest, occupancy
        * kitchen  — open tickets, avg prep time (fired→ready), oldest open,
                     SLA breaches, and a per-station breakdown, all from the
                     mezze.kds.ticket timestamps
        * servers  — today's paid orders grouped by user (sales + order count)
        * alerts   — derived exceptions ranked by urgency
        """
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            Order = env['pos.order']
            Ticket = env['mezze.kds.ticket']
            now = fields.Datetime.now()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            cfg_dom = [('config_id', '=', int(config_id))] if config_id else []

            # ---- Sales (today, finalised) ----
            paid = Order.search(cfg_dom + [
                ('state', 'in', ('paid', 'done', 'invoiced')),
                ('date_order', '>=', fields.Datetime.to_string(start))])
            net = sum(paid.mapped('amount_total'))
            tx = len(paid)
            rev = theo = 0.0
            rcache = {}
            servers = {}
            for o in paid:
                for l in o.lines:
                    if l.qty <= 0:
                        continue
                    p = l.product_id
                    if p.id not in rcache:
                        rcache[p.id] = self._recipe_cost(p)
                    rev += l.price_subtotal_incl
                    theo += rcache[p.id] * l.qty
                u = o.user_id
                s = servers.setdefault(u.id, {'name': u.name or '-', 'orders': 0, 'sales': 0.0})
                s['orders'] += 1
                s['sales'] += o.amount_total
            margin = ((rev - theo) / rev * 100.0) if rev else 0.0

            # ---- Service: open tabs (unpaid table drafts) + occupancy ----
            drafts = Order.search(cfg_dom + [('state', '=', 'draft')])
            table_drafts = drafts.filtered(lambda o: 'table_id' in o._fields and o.table_id)
            open_amount = sum(table_drafts.mapped('amount_total'))
            def _age_min(dt):
                return int((now - dt).total_seconds() / 60) if dt else 0
            oldest_tab = max((_age_min(o.date_order) for o in table_drafts), default=0)
            total_tables = env['restaurant.table'].search_count(
                [('active', '=', True)]) if 'restaurant.table' in env else 0
            occupied = len(table_drafts.mapped('table_id'))

            # ---- Kitchen performance from ticket timestamps ----
            tdom = cfg_dom + [('fired_at', '>=', fields.Datetime.to_string(start))]
            todays = Ticket.search(tdom)
            open_states = ('fired', 'accepted', 'preparing')
            open_tix = todays.filtered(lambda t: t.state in open_states)
            ready_waiting = todays.filtered(lambda t: t.state == 'ready')
            prep_samples = [(t.ready_at - t.fired_at).total_seconds()
                            for t in todays if t.ready_at and t.fired_at]
            avg_prep = sum(prep_samples) / len(prep_samples) if prep_samples else 0.0
            oldest_open = max((_age_min(t.fired_at) for t in open_tix), default=0)
            sla = int(sla_minutes or 15)
            breaches = open_tix.filtered(lambda t: _age_min(t.fired_at) >= sla)
            by_station = {}
            for t in todays:
                st = by_station.setdefault(t.station, {'station': t.station, 'open': 0, 'prep': [], 'breach': 0})
                if t.state in open_states:
                    st['open'] += 1
                    if _age_min(t.fired_at) >= sla:
                        st['breach'] += 1
                if t.ready_at and t.fired_at:
                    st['prep'].append((t.ready_at - t.fired_at).total_seconds())
            stations = [{
                'station': s['station'], 'open': s['open'], 'breach': s['breach'],
                'avg_prep_sec': int(sum(s['prep']) / len(s['prep'])) if s['prep'] else 0,
            } for s in sorted(by_station.values(), key=lambda x: (-x['open'], x['station']))]

            # ---- Derived alerts, most urgent first ----
            alerts = []
            for t in breaches.sorted(lambda t: t.fired_at)[:5]:
                alerts.append({'level': 'crit', 'kind': 'sla',
                               'label': '%s / %s' % (t.table_label or (t.pos_order_id.tracking_number or ''), t.station),
                               'minutes': _age_min(t.fired_at)})
            for o in table_drafts.sorted(lambda o: o.date_order)[:5]:
                mins = _age_min(o.date_order)
                if mins >= 45:
                    tbl = o.table_id
                    alerts.append({'level': 'warn', 'kind': 'long_tab',
                                   'label': 'T%s' % (tbl.table_number if 'table_number' in tbl._fields else tbl.id),
                                   'minutes': mins})
            alerts = sorted(alerts, key=lambda a: (0 if a['level'] == 'crit' else 1, -a['minutes']))[:6]

            return {
                'ok': True,
                'as_of': fields.Datetime.to_string(now),
                'sales': {'net': round(net, 2), 'tx': tx,
                          'avg_ticket': round(net / tx, 2) if tx else 0.0,
                          'margin': round(margin, 1)},
                'service': {'open_tabs': len(table_drafts), 'open_amount': round(open_amount, 2),
                            'occupied': occupied, 'total_tables': total_tables,
                            'oldest_tab_min': oldest_tab},
                'kitchen': {'open_tickets': len(open_tix), 'ready_waiting': len(ready_waiting),
                            'avg_prep_sec': int(avg_prep), 'oldest_open_min': oldest_open,
                            'sla_minutes': sla, 'sla_breaches': len(breaches),
                            'stations': stations},
                'servers': sorted(({'name': s['name'], 'orders': s['orders'],
                                    'sales': round(s['sales'], 2)} for s in servers.values()),
                                   key=lambda x: -x['sales']),
                'alerts': alerts,
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze manager_dashboard failed")
            return self._json({'ok': False, 'error': 'manager_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # AI upsell — market-basket recommender over real order history
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/ai/upsell', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def ai_upsell(self, config_id=None, cart=None, limit=3, **kw):
        """Suggest add-ons for the current cart from REAL sales history.

        Association mining over paid-order baskets: for a candidate Y and a cart
        item X we use the confidence P(Y|X) = (#baskets with X and Y)/(#baskets
        with X), and the lift P(Y|X)/P(Y) to favour genuinely-associated pairs
        over merely-popular ones. Items already in the cart are excluded. When the
        signal is thin (or the cart is empty) we fall back to overall popularity,
        so there's always a useful suggestion. Every suggestion is explainable.
        """
        try:
            env = self._api_env()
            cart_ids = set(int(x) for x in (cart or []))
            orders = env['pos.order'].search([('state', 'in', ('paid', 'done', 'invoiced'))])
            baskets, freq, pair = 0, {}, {}
            for o in orders:
                pset = {l.product_id.id for l in o.lines if l.qty > 0}
                if not pset:
                    continue
                baskets += 1
                for p in pset:
                    freq[p] = freq.get(p, 0) + 1
                for x in pset:
                    for y in pset:
                        if x != y:
                            pair[(x, y)] = pair.get((x, y), 0) + 1

            candidates = env['product.product'].search(self._menu_domain(env))
            prod_by_id = {p.id: p for p in candidates}
            cand_ids = [p.id for p in candidates if p.id not in cart_ids]

            scored = []
            for y in cand_ids:
                best_conf, driver = 0.0, None
                for x in cart_ids:
                    cx = freq.get(x, 0)
                    if cx:
                        conf = pair.get((x, y), 0) / cx
                        if conf > best_conf:
                            best_conf, driver = conf, x
                support_y = (freq.get(y, 0) / baskets) if baskets else 0.0
                lift = (best_conf / support_y) if support_y else 0.0
                if best_conf > 0:
                    scored.append({'y': y, 'kind': 'affinity', 'conf': best_conf,
                                   'lift': lift, 'driver': driver})
            scored.sort(key=lambda s: (-s['conf'], -s['lift']))

            # Fill (or fully seed, for an empty cart) with popular items.
            if len(scored) < int(limit):
                have = {s['y'] for s in scored}
                for y in sorted(cand_ids, key=lambda p: -freq.get(p, 0)):
                    if y in have or freq.get(y, 0) == 0:
                        continue
                    scored.append({'y': y, 'kind': 'popular',
                                   'conf': 0.0, 'lift': 0.0, 'driver': None})

            out = []
            for s in scored[:int(limit)]:
                p = prod_by_id.get(s['y'])
                if not p:
                    continue
                driver = prod_by_id.get(s['driver']) if s['driver'] else None
                out.append({
                    'product_id': p.id, 'name': p.display_name, 'price': p.lst_price,
                    'kind': s['kind'],
                    'with': driver.display_name if driver else None,
                    'confidence': round(s['conf'], 2), 'lift': round(s['lift'], 2),
                    'has_modifiers': bool(self._product_modifiers(env, p)),
                })
            return {'ok': True, 'baskets': baskets, 'suggestions': out}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ai_upsell failed")
            return self._json({'ok': False, 'error': 'upsell_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Loyalty — real Odoo loyalty.program / loyalty.card / loyalty.history
    # ------------------------------------------------------------------
    LOYALTY_PROGRAM = 'Mezze Rewards'

    def _loyalty_program(self, env):
        return env['loyalty.program'].sudo().search(
            [('name', '=', self.LOYALTY_PROGRAM), ('program_type', '=', 'loyalty')], limit=1)

    def _loyalty_card(self, env, partner, create=True):
        """The partner's loyalty card for the Mezze programme (minted on first
        use). Returns an empty recordset if there is no programme."""
        prog = self._loyalty_program(env)
        if not prog or not partner:
            return env['loyalty.card'].sudo()
        Card = env['loyalty.card'].sudo()
        card = Card.search([('program_id', '=', prog.id), ('partner_id', '=', partner.id)], limit=1)
        if not card and create:
            card = Card.create({'program_id': prog.id, 'partner_id': partner.id, 'points': 0.0})
        return card

    def _loyalty_rewards(self, env, prog):
        return [{'id': r.id, 'points': r.required_points,
                 'discount': r.discount, 'mode': r.discount_mode,
                 'name': 'EGP %s off' % int(r.discount) if r.reward_type == 'discount'
                         else (r.reward_product_id.display_name or 'Reward')}
                for r in prog.reward_ids if r.reward_type == 'discount']

    def _loyalty_earn(self, env, order):
        """Award loyalty points for a finalised order (real loyalty.history +
        card balance). 1 point per currency unit spent, per the programme rule.
        No-op when the order has no partner or no programme. Returns (earned,
        balance) or (0, None)."""
        partner = order.partner_id
        if not partner:
            return 0.0, None
        prog = self._loyalty_program(env)
        if not prog:
            return 0.0, None
        rule = prog.rule_ids[:1]
        amount = order.amount_total
        rate = rule.reward_point_amount if rule else 1.0
        mode = rule.reward_point_mode if rule else 'money'
        earned = float(int(amount * rate)) if mode == 'money' else (rate if mode == 'order' else 0.0)
        if earned <= 0:
            return 0.0, self._loyalty_card(env, partner).points
        card = self._loyalty_card(env, partner)
        card.sudo().write({'points': card.points + earned})
        env['loyalty.history'].sudo().create({
            'card_id': card.id, 'issued': earned, 'used': 0.0,
            'description': 'Mezze order %s' % (order.pos_reference or order.id),
        })
        return earned, card.points

    @http.route(f'{API_PREFIX}/loyalty/search', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def loyalty_search(self, q=None, limit=8, **kw):
        """Find customers by name/phone with their REAL loyalty points, plus the
        programme's rewards catalogue."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            prog = self._loyalty_program(env)
            domain = []
            if q:
                domain = ['|', ('name', 'ilike', q), ('phone', 'ilike', q)]
            else:
                # default: show customers who actually hold a card
                cards = env['loyalty.card'].sudo().search([('program_id', '=', prog.id)]) if prog else env['loyalty.card']
                domain = [('id', 'in', cards.mapped('partner_id').ids)] if prog else [('customer_rank', '>', 0)]
            partners = env['res.partner'].sudo().search(domain, limit=int(limit))
            bal = {}
            if prog:
                for c in env['loyalty.card'].sudo().search(
                        [('program_id', '=', prog.id), ('partner_id', 'in', partners.ids)]):
                    bal[c.partner_id.id] = c.points
            return {
                'ok': True,
                'program': prog.name if prog else None,
                'rewards': self._loyalty_rewards(env, prog) if prog else [],
                'customers': [{'id': p.id, 'name': p.name, 'phone': p.phone or '',
                               'points': bal.get(p.id, 0.0)} for p in partners],
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze loyalty_search failed")
            return self._json({'ok': False, 'error': 'loyalty_search_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/loyalty/redeem', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def loyalty_redeem(self, partner_id=None, reward_id=None, **kw):
        """Redeem a reward: deduct the required points (real loyalty.history
        'used' + card balance) and return the discount to apply to the order.
        The bridge applies the discount as a balanced order line at pay time."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            partner = env['res.partner'].sudo().browse(int(partner_id))
            reward = env['loyalty.reward'].sudo().browse(int(reward_id))
            if not partner.exists() or not reward.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            card = self._loyalty_card(env, partner)
            if not card:
                return self._json({'ok': False, 'error': 'no_card'}, status=400)
            need = reward.required_points
            if card.points < need:
                return self._json({'ok': False, 'error': 'insufficient_points',
                                   'message': 'Needs %d, has %d' % (need, card.points)}, status=400)
            card.sudo().write({'points': card.points - need})
            env['loyalty.history'].sudo().create({
                'card_id': card.id, 'issued': 0.0, 'used': need,
                'description': 'Redeemed %s' % ('EGP %s off' % int(reward.discount)),
            })
            return {
                'ok': True, 'partner_id': partner.id, 'points': card.points,
                'reward_id': reward.id, 'discount': reward.discount,
                'discount_product_id': reward.discount_line_product_id.id or False,
                'label': 'EGP %s off' % int(reward.discount),
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze loyalty_redeem failed")
            return self._json({'ok': False, 'error': 'loyalty_redeem_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Gift cards / store credit — native loyalty gift_card program + card
    # ------------------------------------------------------------------
    # A gift card is a real ``loyalty.card`` on a ``gift_card`` programme
    # (points == currency, 1:1) with an auto-generated ``code``. Issuing mints a
    # card with a balance; redeeming is a TENDER (a pos.payment on the Gift Card
    # payment method) that decrements the card — not a discount, because a gift
    # card is money owed, not a markdown.
    GIFTCARD_PROGRAM = 'Mezze Gift Card'

    def _giftcard_program(self, env, create=True):
        prog = env['loyalty.program'].sudo().search(
            [('program_type', '=', 'gift_card')], limit=1)
        if not prog and create:
            prog = env['loyalty.program'].sudo().create({
                'name': self.GIFTCARD_PROGRAM, 'program_type': 'gift_card'})
        return prog

    def _giftcard_by_code(self, env, code):
        prog = self._giftcard_program(env, create=False)
        if not prog or not code:
            return env['loyalty.card'].sudo()
        return env['loyalty.card'].sudo().search(
            [('program_id', '=', prog.id), ('code', '=', str(code).strip())], limit=1)

    def _giftcard_pm(self, env, config):
        """The Gift Card pos.payment.method for this company (find-or-create).

        We try to link it to the config, but Odoo forbids editing a config's
        payment methods while a session is OPEN — so during service we skip the
        link (the pos.payment references the method directly, which is enough).
        Link it once with sessions closed (or via setup) so it shows in the UI."""
        PM = env['pos.payment.method'].sudo()
        pm = PM.search([('name', '=', 'Gift Card'),
                        ('company_id', '=', config.company_id.id)], limit=1)
        if not pm:
            pm = PM.create({'name': 'Gift Card', 'company_id': config.company_id.id})
        if pm.id not in config.payment_method_ids.ids:
            has_open = env['pos.session'].sudo().search_count(
                [('config_id', '=', config.id), ('state', '!=', 'closed')])
            if not has_open:
                config.sudo().write({'payment_method_ids': [(4, pm.id)]})
        return pm

    def _giftcard_sale_product(self, env):
        """Tax-free product whose SALE funds a gift card (default_code GIFTCARD).
        Selling it mints a card for the line amount — a gift-card sale is a
        liability, not taxable revenue, so it carries no tax."""
        Product = env['product.product'].sudo()
        prod = Product.search([('default_code', '=', 'GIFTCARD')], limit=1)
        if not prod:
            tmpl = env['product.template'].sudo().create({
                'name': 'Gift Card', 'default_code': 'GIFTCARD', 'type': 'service',
                'available_in_pos': True, 'list_price': 0.0, 'taxes_id': [(6, 0, [])],
            })
            prod = tmpl.product_variant_id
        return prod

    def _giftcard_decrement(self, env, card, amount, ref):
        card.sudo().write({'points': card.points - amount})
        env['loyalty.history'].sudo().create({
            'card_id': card.id, 'issued': 0.0, 'used': amount,
            'description': 'Gift card %s spent on %s' % (card.code, ref)})

    @http.route(f'{API_PREFIX}/giftcard/issue', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def giftcard_issue(self, amount=None, partner_id=None, code=None,
                       expiration_date=None, **kw):
        """Mint a gift card with a starting balance. The cash for it is collected
        by the sale that sells the Gift Card product; this call creates the card
        and returns its printable code. Optionally attach to a customer."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            amt = round(float(amount or 0), 2)
            if amt <= 0:
                raise ValueError("Gift card amount must be positive")
            prog = self._giftcard_program(env)
            vals = {'program_id': prog.id, 'points': amt}
            if partner_id:
                vals['partner_id'] = int(partner_id)
            if code:
                vals['code'] = str(code).strip()
            if expiration_date:
                vals['expiration_date'] = expiration_date
            card = env['loyalty.card'].sudo().create(vals)
            self._audit(env, 'giftcard.issue', **self._actor(env, kw),
                        detail=json.dumps({'code': card.code, 'amount': amt,
                                           'partner_id': partner_id}, default=str))
            return {'ok': True, 'code': card.code, 'balance': card.points,
                    'partner_id': card.partner_id.id or None,
                    'expiration_date': str(card.expiration_date) if card.expiration_date else None}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze giftcard issue failed")
            return self._json({'ok': False, 'error': 'giftcard_issue_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/giftcard/balance', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def giftcard_balance(self, code=None, **kw):
        """Look up a gift card's live balance by code."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            card = self._giftcard_by_code(env, code)
            if not card:
                return self._json({'ok': False, 'error': 'not_found',
                                   'message': 'No gift card with that code'}, status=404)
            expired = bool(card.expiration_date and card.expiration_date < fields.Date.today())
            return {'ok': True, 'code': card.code, 'balance': card.points,
                    'partner': card.partner_id.name or None, 'expired': expired,
                    'expiration_date': str(card.expiration_date) if card.expiration_date else None}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze giftcard balance failed")
            return self._json({'ok': False, 'error': 'giftcard_balance_failed',
                               'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Waste / spoilage — native stock.scrap + reason tags, with cost impact
    # ------------------------------------------------------------------
    # Waste is a real ``stock.scrap`` (so on-hand stock drops and the loss books
    # through inventory), tagged with a native ``stock.scrap.reason.tag``. The
    # cost impact is the ingredient/dish cost (BoM-exploded when a recipe exists),
    # so a manager sees money lost, not just quantities.
    WASTE_REASONS = ['Spoilage', 'Expiry', 'Breakage', 'Over-prep', 'Dropped', 'Return']

    def _waste_reason_tag(self, env, name):
        Tag = env['stock.scrap.reason.tag'].sudo()
        name = (name or 'Spoilage').strip().title()
        tag = Tag.search([('name', '=', name)], limit=1)
        return tag or Tag.create({'name': name})

    def _stock_location(self, env, company):
        wh = env['stock.warehouse'].sudo().search(
            [('company_id', '=', company.id)], limit=1) or \
            env['stock.warehouse'].sudo().search([], limit=1)
        return wh.lot_stock_id

    @http.route(f'{API_PREFIX}/waste/log', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def waste_log(self, config_id=None, product_id=None, qty=None, reason=None, **kw):
        """Record waste against a real stock.scrap (executes the move, tagged with
        the reason). Returns the scrap reference + the money impact. Managers +
        supervisors only-ish: audited so shrinkage is attributable."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        # Bind the REQUEST env to the api user too: a scrap posts stock-valuation
        # rows that get flushed at request-end through the request's default env —
        # which under auth='none' has no user and fails the access check. (Other
        # endpoints don't hit this because they don't leave valuation rows dirty.)
        request.update_env(user=env.uid)
        try:
            config = (env['pos.config'].browse(int(config_id)) if config_id
                      else env['pos.config'].search([], limit=1))
            company = config.company_id or env.company
            product = env['product.product'].browse(int(product_id))
            if not product.exists():
                raise ValueError("Unknown product_id %s" % product_id)
            q = float(qty or 0)
            if q <= 0:
                raise ValueError("Waste quantity must be positive")
            tag = self._waste_reason_tag(env, reason)
            loc = self._stock_location(env, company)
            # Use the api_user env (has POS/stock rights) — NOT sudo: the scrap's
            # stock-move flush does access checks that trip on SUPERUSER.
            wenv = env(context=dict(env.context, allowed_company_ids=[company.id]))
            scrap = wenv['stock.scrap'].create({
                'product_id': product.id, 'product_uom_id': product.uom_id.id,
                'scrap_qty': q, 'location_id': loc.id,
                'scrap_reason_tag_ids': [(6, 0, tag.ids)],
                'company_id': company.id,
                'origin': 'Mezze POS waste',
            })
            # execute directly so it records even when tracked stock is short
            # (waste happened regardless); non-storable products just log. Run in a
            # savepoint so a valuation/move hiccup degrades to a draft record
            # (waste still tracked) rather than 500-ing the request.
            try:
                with env.cr.savepoint():
                    scrap.do_scrap()
                    env.cr.flush()
            except Exception:  # noqa: BLE001 - keep the waste record even if the move can't post
                _logger.exception("Waste scrap move failed for %s; kept as draft", product.display_name)
            unit_cost = self._recipe_cost(product)
            cost = round(unit_cost * q, 2)
            self._audit(env, 'waste.log', **self._actor(env, kw),
                        detail=json.dumps({'product': product.display_name, 'qty': q,
                                           'reason': tag.name, 'cost': cost,
                                           'scrap': scrap.name, 'config_id': company.id}, default=str))
            return {'ok': True, 'scrap_id': scrap.id, 'reference': scrap.name,
                    'state': scrap.state, 'product': product.display_name, 'qty': q,
                    'reason': tag.name, 'unit_cost': round(unit_cost, 2), 'cost': cost}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze waste log failed")
            return self._json({'ok': False, 'error': 'waste_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/waste/products', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def waste_products(self, q=None, limit=12, **kw):
        """Products a manager can waste: storable ingredients (the BoM components
        that are the real waste) UNION menu items (a dropped dish). Returns name +
        uom + live on-hand so the picker shows what's actually stockable."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            dom = ['|', ('is_storable', '=', True), ('available_in_pos', '=', True)]
            if q:
                dom = ['&'] + dom + ['|', ('name', 'ilike', q), ('default_code', 'ilike', q)]
            prods = env['product.product'].sudo().search(dom, limit=int(limit or 12))
            return {'ok': True, 'products': [{
                'id': p.id, 'name': p.display_name, 'uom': p.uom_id.name,
                'storable': p.is_storable, 'on_hand': p.qty_available if p.is_storable else None,
            } for p in prods]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze waste products failed")
            return self._json({'ok': False, 'error': 'waste_products_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/waste/list', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def waste_list(self, config_id=None, limit=30, **kw):
        """Recent waste with per-line cost + a day/total roll-up for the ops view."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            company = (env['pos.config'].browse(int(config_id)).company_id if config_id
                       else env.company)
            dom = [('origin', '=', 'Mezze POS waste')]
            if company:
                dom.append(('company_id', '=', company.id))
            scraps = env['stock.scrap'].sudo().search(dom, order='create_date desc',
                                                      limit=int(limit or 30))
            items, total = [], 0.0
            today = fields.Date.today()
            today_cost = 0.0
            for s in scraps:
                unit = self._recipe_cost(s.product_id)
                cost = round(unit * s.scrap_qty, 2)
                total += cost
                created = s.create_date.date() if s.create_date else None
                if created == today:
                    today_cost += cost
                items.append({
                    'id': s.id, 'reference': s.name or '(draft)',
                    'product': s.product_id.display_name, 'qty': s.scrap_qty,
                    'uom': s.product_uom_id.name, 'state': s.state,
                    'reason': ', '.join(s.scrap_reason_tag_ids.mapped('name')) or '—',
                    'cost': cost,
                    'date': fields.Datetime.to_string(s.create_date) if s.create_date else None,
                })
            return {'ok': True, 'items': items,
                    'total_cost': round(total, 2), 'today_cost': round(today_cost, 2),
                    'reasons': self.WASTE_REASONS}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze waste list failed")
            return self._json({'ok': False, 'error': 'waste_list_failed',
                               'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Reservations — mezze.reservation over real restaurant.table
    # ------------------------------------------------------------------
    # A booked reservation "holds" its table from ``lead`` minutes before the
    # start until the end of its window; the floor shows it reserved in that span.
    RES_LEAD_MIN = 90

    def _res_window(self, r):
        start = r.start
        end = start + datetime.timedelta(hours=r.duration or 1.5)
        return start, end

    def _res_conflict(self, env, table_id, start_dt, duration, exclude_id=None):
        """True if a live (booked/seated) reservation on the table overlaps the
        proposed [start, start+duration] window."""
        end_dt = start_dt + datetime.timedelta(hours=duration or 1.5)
        dom = [('table_id', '=', int(table_id)), ('state', 'in', ('booked', 'seated'))]
        if exclude_id:
            dom.append(('id', '!=', int(exclude_id)))
        for r in env['mezze.reservation'].search(dom):
            rs, re = self._res_window(r)
            if rs < end_dt and start_dt < re:      # windows intersect
                return r
        return False

    def _res_payload(self, r):
        start = r.start
        return {
            'id': r.id, 'state': r.state,
            'who': r._who(), 'phone': r.phone or (r.partner_id.phone or ''),
            'partner_id': r.partner_id.id or None,
            'table_id': r.table_id.id,
            'table': 'T%s' % (r.table_id.table_number if 'table_number' in r.table_id._fields else r.table_id.id),
            'start': fields.Datetime.to_string(start) if start else None,
            'time': fields.Datetime.to_string(start)[11:16] if start else '',
            'duration': r.duration, 'guests': r.guests, 'note': r.note or '',
            'order_id': r.pos_order_id.id or None,
        }

    @http.route(f'{API_PREFIX}/reservations/list', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def reservations_list(self, config_id=None, date=None, scope='today', **kw):
        """Reservations for a day (default today) or all upcoming."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            now = fields.Datetime.now()
            dom = []
            if config_id:
                dom.append(('config_id', '=', int(config_id)))
            if scope == 'upcoming':
                dom.append(('start', '>=', fields.Datetime.to_string(now - datetime.timedelta(hours=2))))
            else:
                day = fields.Datetime.to_datetime(date + ' 00:00:00') if date else \
                    now.replace(hour=0, minute=0, second=0, microsecond=0)
                dom += [('start', '>=', fields.Datetime.to_string(day)),
                        ('start', '<', fields.Datetime.to_string(day + datetime.timedelta(days=1)))]
            res = env['mezze.reservation'].search(dom)
            return {'ok': True, 'reservations': [self._res_payload(r) for r in res]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze reservations_list failed")
            return self._json({'ok': False, 'error': 'res_list_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/reservations/availability', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def reservations_availability(self, config_id=None, start=None, duration=1.5, guests=None, **kw):
        """Tables free at ``start`` (no overlapping reservation), seats permitting."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            start_dt = fields.Datetime.to_datetime(start)
            tdom = [('active', '=', True)]
            tables = env['restaurant.table'].search(tdom)
            free = []
            for t in tables:
                if guests and t.seats and t.seats < int(guests):
                    continue
                if self._res_conflict(env, t.id, start_dt, float(duration)):
                    continue
                free.append({'id': t.id,
                             'table': 'T%s' % (t.table_number if 'table_number' in t._fields else t.id),
                             'seats': t.seats, 'floor': t.floor_id.name})
            return {'ok': True, 'tables': free}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze reservations_availability failed")
            return self._json({'ok': False, 'error': 'res_avail_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/reservations/create', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def reservations_create(self, table_id=None, start=None, guests=2, duration=1.5,
                            name=None, phone=None, partner_id=None, note=None, config_id=None, **kw):
        """Book a table, rejecting a clash with an existing booking on it."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            if not table_id or not start:
                return self._json({'ok': False, 'error': 'missing_table_or_time'}, status=400)
            table = env['restaurant.table'].browse(int(table_id))
            if not table.exists():
                return self._json({'ok': False, 'error': 'table_not_found'}, status=404)
            start_dt = fields.Datetime.to_datetime(start)
            clash = self._res_conflict(env, table.id, start_dt, float(duration))
            if clash:
                return self._json({'ok': False, 'error': 'table_unavailable',
                                   'message': 'Table already booked for %s at %s'
                                   % (clash._who(), fields.Datetime.to_string(clash.start)[11:16])}, status=409)
            cfg = int(config_id) if config_id else (
                table.floor_id.pos_config_ids[:1].id if 'pos_config_ids' in table.floor_id._fields
                and table.floor_id.pos_config_ids else False)
            partner = env['res.partner'].browse(int(partner_id)) if partner_id else False
            res = env['mezze.reservation'].create({
                'table_id': table.id, 'config_id': cfg, 'start': start_dt,
                'duration': float(duration), 'guests': int(guests),
                'customer_name': name or (partner.name if partner else None),
                'phone': phone or (partner.phone if partner else None),
                'partner_id': partner.id if partner else False,
                'note': note or False,
            })
            return {'ok': True, 'reservation': self._res_payload(res)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze reservations_create failed")
            return self._json({'ok': False, 'error': 'res_create_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/reservations/state', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def reservations_state(self, reservation_id=None, action=None, **kw):
        """Advance a reservation: seat | no_show | cancel | done."""
        auth = self._authenticate()
        if auth:
            return auth
        MAP = {'seat': 'seated', 'no_show': 'no_show', 'cancel': 'cancelled', 'done': 'done'}
        try:
            env = self._api_env()
            res = env['mezze.reservation'].browse(int(reservation_id))
            if not res.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            if action not in MAP:
                return self._json({'ok': False, 'error': 'bad_action'}, status=400)
            res.write({'state': MAP[action]})
            return {'ok': True, 'reservation': self._res_payload(res)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze reservations_state failed")
            return self._json({'ok': False, 'error': 'res_state_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Waitlist — the host-stand walk-in queue (mezze.waitlist)
    # ------------------------------------------------------------------
    def _waitlist_payload(self, w):
        now = fields.Datetime.now()
        waited = int((now - w.create_date).total_seconds() / 60) if w.create_date else 0
        return {
            'id': w.id, 'who': w._who(), 'phone': w.phone or '',
            'party_size': w.party_size, 'quoted_wait': w.quoted_wait, 'waited': waited,
            'state': w.state, 'note': w.note or '',
            'table': (str(w.table_id.table_number) if w.table_id else None),
            'over': (w.state in ('waiting', 'notified') and w.quoted_wait
                     and waited > w.quoted_wait),
        }

    def _waitlist_quote(self, env, config, party_size=2):
        """A rough wait estimate (minutes): free tables now → 0, else ~12 min per
        party already ahead in the queue, nudged up when the floor is full."""
        Table = env['restaurant.table']
        floor_dom = [('pos_config_ids', 'in', config.id)] if config else []
        tables = env['restaurant.floor'].search(floor_dom).table_ids.filtered('active') \
            if 'restaurant.floor' in env else Table.search([('active', '=', True)])
        total = len(tables) or 1
        occ = env['pos.order'].search_count(
            [('state', '=', 'draft'), ('config_id', '=', config.id), ('table_id', '!=', False)])
        waiting = env['mezze.waitlist'].search_count(
            [('config_id', '=', config.id), ('state', 'in', ('waiting', 'notified'))])
        free = max(0, total - occ)
        if free > 0 and waiting == 0:
            return 0
        est = 10 + waiting * 12 + (10 if free <= 0 else 0)
        return int(min(est, 120))

    @http.route(f'{API_PREFIX}/waitlist/list', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def waitlist_list(self, config_id=None, **kw):
        """The live queue (waiting + notified) oldest-first, plus a next-party
        quote and simple stats for the host stand."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, config_id)
            parties = env['mezze.waitlist'].search(
                [('config_id', '=', config.id), ('state', 'in', ('waiting', 'notified'))],
                order='create_date asc')
            items = [self._waitlist_payload(w) for w in parties]
            covers = sum(w.party_size for w in parties)
            return {'ok': True, 'items': items, 'waiting': len(items), 'covers': covers,
                    'quote': self._waitlist_quote(env, config, 2)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze waitlist_list failed")
            return self._json({'ok': False, 'error': 'waitlist_list_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/waitlist/add', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def waitlist_add(self, config_id=None, name=None, party_size=2, phone=None,
                     quoted_wait=None, partner_id=None, note=None, **kw):
        """Add a walk-in party to the queue. Quotes the wait automatically when
        one isn't supplied."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, config_id)
            size = max(1, int(party_size or 1))
            quote = int(quoted_wait) if quoted_wait not in (None, '') \
                else self._waitlist_quote(env, config, size)
            vals = {'config_id': config.id, 'party_size': size, 'quoted_wait': quote,
                    'customer_name': (name or '').strip() or False,
                    'phone': (phone or '').strip() or False,
                    'note': (note or '').strip() or False, 'state': 'waiting'}
            if partner_id:
                vals['partner_id'] = int(partner_id)
            w = env['mezze.waitlist'].create(vals)
            self._audit(env, 'waitlist.add', **self._actor(env, kw),
                        detail=json.dumps({'who': w._who(), 'size': size,
                                           'quoted_wait': quote}, default=str))
            return {'ok': True, 'waitlist': self._waitlist_payload(w)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze waitlist_add failed")
            return self._json({'ok': False, 'error': 'waitlist_add_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/waitlist/state', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def waitlist_state(self, waitlist_id=None, action=None, table_id=None, **kw):
        """Advance a party: notify | seat | cancel | no_show. Seating records the
        table so the host can drop it into table-service on the floor."""
        auth = self._authenticate()
        if auth:
            return auth
        MAP = {'notify': 'notified', 'seat': 'seated',
               'cancel': 'cancelled', 'no_show': 'no_show'}
        env = self._api_env()
        try:
            w = env['mezze.waitlist'].browse(int(waitlist_id))
            if not w.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            if action not in MAP:
                return self._json({'ok': False, 'error': 'bad_action'}, status=400)
            vals = {'state': MAP[action]}
            if action == 'seat' and table_id:
                vals['table_id'] = int(table_id)
            w.write(vals)
            self._audit(env, 'waitlist.%s' % action, **self._actor(env, kw),
                        detail=json.dumps({'who': w._who(), 'table_id': table_id}, default=str))
            return {'ok': True, 'waitlist': self._waitlist_payload(w),
                    'table_id': w.table_id.id or None}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze waitlist_state failed")
            return self._json({'ok': False, 'error': 'waitlist_state_failed',
                               'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Delivery — mezze.delivery last-mile leg over a paid pos.order
    # ------------------------------------------------------------------
    def _delivery_fee_product(self, env):
        """The 'Delivery' fee product — a POS-available service with NO category
        so it's a valid order line but never shows on the menu (_menu_domain
        requires a pos category). Created on first use."""
        Product = env['product.product'].sudo()
        p = Product.search([('default_code', '=', 'MEZZE_DELIVERY_FEE')], limit=1)
        if not p:
            p = Product.create({
                'name': 'Delivery', 'default_code': 'MEZZE_DELIVERY_FEE',
                'type': 'service', 'available_in_pos': True,
                'taxes_id': [(6, 0, [])], 'list_price': 0.0,
            })
        return p

    def _delivery_payload(self, d):
        order = d.pos_order_id
        fee_pid = self._delivery_fee_product(d.env).id
        items = [{'name': l.product_id.display_name, 'qty': l.qty}
                 for l in order.lines if l.product_id.id != fee_pid and l.qty > 0]
        now = fields.Datetime.now()
        return {
            'id': d.id, 'state': d.state, 'who': d._who(), 'phone': d.phone or '',
            'address': d.address or '', 'fee': d.fee, 'rider': d.rider or '',
            'zone': d.zone_id.name if d.zone_id else None,
            'note': d.note or '', 'order_id': order.id,
            'tracking': order.tracking_number or order.pos_reference or '',
            'total': round(order.amount_total, 2), 'items': items,
            'kitchen_ready': d._kitchen_ready(),
            'placed_at': fields.Datetime.to_string(d.placed_at) if d.placed_at else None,
            'minutes': int((now - d.placed_at).total_seconds() / 60) if d.placed_at else 0,
        }

    def _zone_payload(self, z):
        return {'id': z.id, 'name': z.name, 'fee': z.fee, 'min_order': z.min_order,
                'eta_minutes': z.eta_minutes, 'active': z.active}

    @http.route(f'{API_PREFIX}/delivery/zones', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def delivery_zones(self, config_id=None, all=False, **kw):
        """Delivery zones for a branch (active only unless ``all``)."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, config_id)
            dom = ['|', ('config_id', '=', config.id), ('config_id', '=', False)]
            if not all:
                dom = ['&', ('active', '=', True)] + dom
            zones = env['mezze.delivery.zone'].search(dom)
            return {'ok': True, 'zones': [self._zone_payload(z) for z in zones]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze delivery_zones failed")
            return self._json({'ok': False, 'error': 'zones_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/delivery/zone/save', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def delivery_zone_save(self, zone_id=None, config_id=None, name=None, fee=None,
                           min_order=None, eta_minutes=None, active=None, **kw):
        """Create or update a delivery zone (manager back-office)."""
        auth = self._authenticate()
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, config_id)
            vals = {}
            if name is not None:
                vals['name'] = (name or '').strip()
            if fee is not None:
                vals['fee'] = float(fee)
            if min_order is not None:
                vals['min_order'] = float(min_order)
            if eta_minutes is not None:
                vals['eta_minutes'] = int(eta_minutes)
            if active is not None:
                vals['active'] = str(active).strip().lower() not in ('0', 'false', 'no')
            if zone_id:
                zone = env['mezze.delivery.zone'].browse(int(zone_id))
                if not zone.exists():
                    raise ValueError("Unknown zone %s" % zone_id)
                zone.write(vals)
            else:
                if not vals.get('name'):
                    raise ValueError("Zone name is required")
                vals.setdefault('config_id', config.id)
                zone = env['mezze.delivery.zone'].create(vals)
            self._audit(env, 'delivery.zone', **self._actor(env, kw),
                        detail=json.dumps({'zone': zone.name, 'fee': zone.fee,
                                           'min_order': zone.min_order}, default=str))
            return {'ok': True, 'zone': self._zone_payload(zone)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze delivery_zone_save failed")
            return self._json({'ok': False, 'error': 'zone_save_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/delivery/create', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def delivery_create(self, uuid=None, session_id=None, lines=None, fee=0.0,
                        customer=None, phone=None, address=None, partner_id=None,
                        note=None, payment_method_id=None, zone_id=None, **kw):
        """Create a delivery: a paid pos.order (food + delivery fee) that fires to
        the kitchen, plus the mezze.delivery tracking record."""
        auth = self._authenticate()
        if auth:
            return auth
        if not lines:
            return self._json({'ok': False, 'error': 'no_lines'}, status=400)
        if not address:
            return self._json({'ok': False, 'error': 'missing_address'}, status=400)
        env = self._api_env()
        try:
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            session = session.with_env(env)
            config = config.with_env(env)
            partner = env['res.partner'].browse(int(partner_id)) if partner_id else env['res.partner']
            order_lines, base, incl = self._build_lines(env, config, partner, lines)
            # Resolve the fee from the ZONE server-side (don't trust a client fee)
            # and enforce the zone's minimum order on the food subtotal.
            zone = env['mezze.delivery.zone'].browse(int(zone_id)) if zone_id \
                else env['mezze.delivery.zone']
            if zone and zone.exists():
                if zone.min_order and incl < zone.min_order:
                    raise ValueError("Order EGP %.2f is below the %s minimum of EGP %.2f"
                                     % (incl, zone.name, zone.min_order))
                fee = zone.fee
            else:
                fee = float(fee or 0.0)
            if fee > 0:
                fp = self._delivery_fee_product(env)
                order_lines.append((0, 0, {
                    'product_id': fp.id, 'qty': 1, 'price_unit': fee, 'discount': 0.0,
                    'tax_ids': [(6, 0, [])], 'price_subtotal': fee,
                    'price_subtotal_incl': fee, 'pack_lot_ids': []}))
                incl += fee
                base += fee
            uuid = uuid or 'dlv-%s' % session.id
            pmid = int(payment_method_id) if payment_method_id else (config.payment_method_ids[:1].id)
            order_dict = {
                'uuid': uuid, 'session_id': session.id, 'company_id': config.company_id.id,
                'user_id': env.uid, 'partner_id': partner.id or False,
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
                raise ValueError("delivery order did not persist")
            # fire the food to the kitchen (station tickets)
            fee_pid = self._delivery_fee_product(env).id
            tickets = self._make_station_tickets(
                env, order,
                [(l.product_id, l.qty, '') for l in order.lines if l.product_id.id != fee_pid],
                'dlv:%s' % uuid, 1)
            tickets._broadcast()
            dlv = env['mezze.delivery'].create({
                'pos_order_id': order.id, 'partner_id': partner.id or False,
                'customer_name': customer or (partner.name if partner else None),
                'phone': phone or (partner.phone if partner else None),
                'address': address, 'fee': fee, 'note': note or False,
                'zone_id': (zone.id if zone and zone.exists() else False),
                'state': 'preparing',
            })
            earned, balance = self._loyalty_earn(env, order)
            return {'ok': True, 'delivery': self._delivery_payload(dlv),
                    'loyalty_earned': earned, 'loyalty_balance': balance}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze delivery_create failed")
            return self._json({'ok': False, 'error': 'delivery_create_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/delivery/list', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def delivery_list(self, config_id=None, scope='active', done_minutes=30, **kw):
        """The delivery board. ``active`` = not delivered/failed + recently
        finished; ``all`` = everything today."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            dom = [('config_id', '=', int(config_id))] if config_id else []
            if scope == 'active':
                cutoff = fields.Datetime.now() - datetime.timedelta(minutes=int(done_minutes or 30))
                dom += ['|', ('state', 'not in', ('delivered', 'failed')),
                        ('placed_at', '>=', fields.Datetime.to_string(cutoff))]
            deliveries = env['mezze.delivery'].search(dom)
            return {'ok': True, 'deliveries': [self._delivery_payload(d) for d in deliveries]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze delivery_list failed")
            return self._json({'ok': False, 'error': 'delivery_list_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/delivery/state', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def delivery_state(self, delivery_id=None, action=None, rider=None, **kw):
        """Advance a delivery: ready | dispatch | delivered | failed."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            d = env['mezze.delivery'].browse(int(delivery_id))
            if not d.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            now = fields.Datetime.now()
            if action == 'ready':
                d.state = 'ready'
            elif action == 'dispatch':
                d.write({'state': 'dispatched', 'rider': rider or d.rider, 'dispatched_at': now})
            elif action == 'delivered':
                d.write({'state': 'delivered', 'delivered_at': now})
            elif action == 'failed':
                d.state = 'failed'
            else:
                return self._json({'ok': False, 'error': 'bad_action'}, status=400)
            return {'ok': True, 'delivery': self._delivery_payload(d)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze delivery_state failed")
            return self._json({'ok': False, 'error': 'delivery_state_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Multi-branch — each pos.config is a branch; HQ consolidates them
    # ------------------------------------------------------------------
    def _branch_stats(self, env, config, full=False):
        """Live snapshot for one branch (pos.config). ``full`` adds occupancy,
        open kitchen tickets and margin for the HQ view."""
        now = fields.Datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        Order = env['pos.order']
        paid = Order.search([('config_id', '=', config.id),
                             ('state', 'in', ('paid', 'done', 'invoiced')),
                             ('date_order', '>=', fields.Datetime.to_string(start))])
        net = sum(paid.mapped('amount_total'))
        tx = len(paid)
        drafts = Order.search([('config_id', '=', config.id), ('state', '=', 'draft')])
        table_drafts = drafts.filtered(lambda o: 'table_id' in o._fields and o.table_id)
        deliveries = env['mezze.delivery'].search(
            [('config_id', '=', config.id), ('state', 'not in', ('delivered', 'failed'))]) \
            if 'mezze.delivery' in env else env['pos.order'].browse()
        session = config.current_session_id
        stats = {
            'id': config.id, 'name': config.name,
            'company': config.company_id.name,
            'session_open': bool(session and session.state == 'opened'),
            'session_id': session.id if session else None,
            'net_sales': round(net, 2), 'tx': tx,
            'avg_ticket': round(net / tx, 2) if tx else 0.0,
            'open_tabs': len(table_drafts),
            'active_deliveries': len(deliveries),
        }
        if full:
            tables = env['restaurant.table'].search(
                [('floor_id.pos_config_ids', 'in', config.id), ('active', '=', True)]) \
                if 'restaurant.table' in env else env['pos.order'].browse()
            occ = len(table_drafts.mapped('table_id'))
            rev = theo = 0.0
            rcache = {}
            for o in paid:
                for l in o.lines:
                    if l.qty <= 0:
                        continue
                    p = l.product_id
                    if p.id not in rcache:
                        rcache[p.id] = self._recipe_cost(p)
                    rev += l.price_subtotal_incl
                    theo += rcache[p.id] * l.qty
            open_tix = env['mezze.kds.ticket'].search_count(
                [('config_id', '=', config.id),
                 ('state', 'in', ('fired', 'accepted', 'preparing'))]) if 'mezze.kds.ticket' in env else 0
            stats.update({
                'occupied': occ, 'total_tables': len(tables),
                'margin': round(((rev - theo) / rev * 100.0), 1) if rev else 0.0,
                'open_tickets': open_tix,
            })
        return stats

    @http.route(f'{API_PREFIX}/branches', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def branches(self, **kw):
        """List the chain's branches (pos.config) with light live status — used
        by the branch switcher."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            configs = env['pos.config'].search([], order='id asc')
            return {'ok': True, 'branches': [self._branch_stats(env, c) for c in configs]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze branches failed")
            return self._json({'ok': False, 'error': 'branches_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/hq/summary', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def hq_summary(self, **kw):
        """Consolidated chain view: full per-branch KPIs + chain totals."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            configs = env['pos.config'].search([], order='id asc')
            branches = [self._branch_stats(env, c, full=True) for c in configs]
            total = {
                'net_sales': round(sum(b['net_sales'] for b in branches), 2),
                'tx': sum(b['tx'] for b in branches),
                'open_tabs': sum(b['open_tabs'] for b in branches),
                'active_deliveries': sum(b['active_deliveries'] for b in branches),
                'open_tickets': sum(b.get('open_tickets', 0) for b in branches),
                'occupied': sum(b.get('occupied', 0) for b in branches),
                'total_tables': sum(b.get('total_tables', 0) for b in branches),
                'branches': len(branches),
                'open_branches': sum(1 for b in branches if b['session_open']),
            }
            total['avg_ticket'] = round(total['net_sales'] / total['tx'], 2) if total['tx'] else 0.0
            return {'ok': True, 'as_of': fields.Datetime.to_string(fields.Datetime.now()),
                    'total': total, 'branches': branches}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze hq_summary failed")
            return self._json({'ok': False, 'error': 'hq_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Central Kitchen — real mrp.production + stock.picking over branches
    # ------------------------------------------------------------------
    def _ck_warehouse(self, env):
        return env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1)

    def _ck_central(self, env):
        loc = env['stock.location'].search(
            [('name', '=', 'Central Kitchen'), ('usage', '=', 'internal')], limit=1)
        if not loc:
            loc = env['stock.location'].create({
                'name': 'Central Kitchen', 'usage': 'internal',
                'location_id': self._ck_warehouse(env).view_location_id.id})
        return loc

    def _ck_branch_location(self, env, config):
        name = 'Branch/%s' % config.name
        loc = env['stock.location'].search([('name', '=', name), ('usage', '=', 'internal')], limit=1)
        if not loc:
            loc = env['stock.location'].create({
                'name': name, 'usage': 'internal',
                'location_id': self._ck_warehouse(env).view_location_id.id})
        return loc

    def _ck_prep_products(self, env):
        return env['product.product'].search([('default_code', 'like', 'CK\\_%')])

    def _ck_stock(self, product, location):
        return product.with_context(location=location.id).qty_available

    def _ck_req_payload(self, r):
        return {
            'id': r.id, 'state': r.state, 'qty': r.qty,
            'branch_id': r.branch_id.id, 'branch': r.branch_id.name,
            'product_id': r.product_id.id,
            'product': r.product_id.display_name, 'code': r.product_id.default_code or '',
            'note': r.note or '',
            'mo': r.production_id.name if r.production_id else None,
            'picking': r.picking_id.name if r.picking_id else None,
            'requested_at': fields.Datetime.to_string(r.requested_at) if r.requested_at else None,
        }

    @http.route(f'{API_PREFIX}/ck/board', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def ck_board(self, **kw):
        """Central Kitchen board: prep stock (central + per branch) + live requests."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            central = self._ck_central(env)
            branches = env['pos.config'].search([], order='id asc')
            preps = self._ck_prep_products(env)
            stock = []
            for p in preps:
                stock.append({
                    'product_id': p.id, 'code': p.default_code or '', 'name': p.display_name,
                    'central': round(self._ck_stock(p, central), 1),
                    'branches': [{'branch_id': b.id, 'branch': b.name,
                                  'qty': round(self._ck_stock(p, self._ck_branch_location(env, b)), 1)}
                                 for b in branches],
                })
            reqs = env['mezze.ck.request'].search(
                ['|', ('state', 'not in', ('received', 'cancelled')),
                 ('requested_at', '>=', fields.Datetime.to_string(
                     fields.Datetime.now() - datetime.timedelta(hours=6)))])
            return {'ok': True,
                    'branches': [{'id': b.id, 'name': b.name} for b in branches],
                    'products': stock,
                    'requests': [self._ck_req_payload(r) for r in reqs]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ck_board failed")
            return self._json({'ok': False, 'error': 'ck_board_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/ck/request', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def ck_request(self, branch_id=None, product_id=None, qty=1, note=None, **kw):
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            if not branch_id or not product_id:
                return self._json({'ok': False, 'error': 'missing_fields'}, status=400)
            r = env['mezze.ck.request'].create({
                'branch_id': int(branch_id), 'product_id': int(product_id),
                'qty': float(qty), 'note': note or False, 'state': 'requested'})
            return {'ok': True, 'request': self._ck_req_payload(r)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ck_request failed")
            return self._json({'ok': False, 'error': 'ck_request_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/ck/produce', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def ck_produce(self, request_id=None, **kw):
        """Fulfil production with a REAL manufacturing order at the Central
        Kitchen (create → confirm → mark done), yielding real central stock."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            r = env['mezze.ck.request'].browse(int(request_id))
            if not r.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            central = self._ck_central(env)
            mo = env['mrp.production'].create({
                'product_id': r.product_id.id, 'product_qty': r.qty,
                'location_src_id': central.id, 'location_dest_id': central.id})
            mo.action_confirm()
            mo.qty_producing = r.qty
            mo.button_mark_done()
            r.write({'state': 'produced', 'production_id': mo.id})
            return {'ok': True, 'request': self._ck_req_payload(r),
                    'central_stock': round(self._ck_stock(r.product_id, central), 1)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ck_produce failed")
            return self._json({'ok': False, 'error': 'ck_produce_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/ck/dispatch', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def ck_dispatch(self, request_id=None, **kw):
        """Ship to the branch with a REAL internal transfer (Central Kitchen →
        the branch's stock location), moving real stock between locations."""
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            r = env['mezze.ck.request'].browse(int(request_id))
            if not r.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            central = self._ck_central(env)
            if self._ck_stock(r.product_id, central) < r.qty:
                return self._json({'ok': False, 'error': 'no_stock',
                                   'message': 'Produce it first'}, status=400)
            wh = self._ck_warehouse(env)
            dest = self._ck_branch_location(env, r.branch_id)
            pick = env['stock.picking'].create({
                'picking_type_id': wh.int_type_id.id,
                'location_id': central.id, 'location_dest_id': dest.id,
                'move_ids': [(0, 0, {'product_id': r.product_id.id, 'product_uom_qty': r.qty,
                                     'location_id': central.id, 'location_dest_id': dest.id})]})
            pick.action_confirm()
            pick.action_assign()
            for m in pick.move_ids:
                m.quantity = r.qty
            pick.button_validate()
            r.write({'state': 'dispatched', 'picking_id': pick.id})
            return {'ok': True, 'request': self._ck_req_payload(r),
                    'central_stock': round(self._ck_stock(r.product_id, central), 1),
                    'branch_stock': round(self._ck_stock(r.product_id, dest), 1)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ck_dispatch failed")
            return self._json({'ok': False, 'error': 'ck_dispatch_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/ck/receive', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def ck_receive(self, request_id=None, **kw):
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            r = env['mezze.ck.request'].browse(int(request_id))
            if not r.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            r.state = 'received'
            return {'ok': True, 'request': self._ck_req_payload(r)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ck_receive failed")
            return self._json({'ok': False, 'error': 'ck_receive_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # KDS — recent orders as kitchen tickets (read-only live view)
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/orders/kds', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def orders_kds(self, limit=12, **kw):
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            has_table = 'table_id' in env['pos.order']._fields
            # kitchen sees FIRED work: draft (fired) orders + recently paid
            orders = env['pos.order'].search(
                [('state', 'in', ('draft', 'paid', 'done', 'invoiced'))],
                order='date_order desc', limit=int(limit or 12))
            out = []
            for o in orders:
                tbl = ''
                if has_table and o.table_id:
                    t = o.table_id
                    tbl = str(t.table_number if 'table_number' in t._fields else t.id)
                # what has actually been fired: the mezze_fired snapshot for
                # draft orders; every line for finalized (café) orders.
                if o.state == 'draft':
                    snap = json.loads(o.mezze_fired or '{}')
                    fired = [(env['product.product'].browse(int(pid)), qty)
                             for pid, qty in snap.items() if qty > 0]
                else:
                    fired = [(l.product_id, l.qty) for l in o.lines if l.qty > 0]
                if not fired:
                    continue
                # route each item to its prep station
                stations = {}
                for product, qty in fired:
                    st = self._station_of(product)
                    stations.setdefault(st, []).append({'qty': qty, 'name': product.display_name})
                out.append({
                    'id': o.id, 'ref': o.pos_reference, 'table': tbl,
                    'server': o.user_id.name or '',
                    'state': o.state,
                    'date_order': fields.Datetime.to_string(o.date_order),
                    'stations': [{'station': s, 'items': its} for s, its in stations.items()],
                    'lines': [it for its in stations.values() for it in its],
                })
            return {'ok': True, 'tickets': out}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze orders_kds failed")
            return self._json({'ok': False, 'error': 'kds_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # KDS state-machine board — real mezze.kds.ticket records
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/kds/state', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def kds_state(self, config_id=None, done_minutes=10, **kw):
        """Full KDS board snapshot for a config.

        Returns every live ticket (fired/accepted/preparing/ready) plus tickets
        that went served/cancel within the last ``done_minutes`` (so the board
        shows what just cleared). Also returns ``last_bus_id`` so the client can
        seed its websocket/poll cursor and never miss an event between snapshot
        and subscribe. Waiter tablets read the same feed, filtering state==ready.
        """
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            Ticket = env['mezze.kds.ticket']
            domain = ['|',
                      ('state', 'in', ('fired', 'accepted', 'preparing', 'ready'))]
            cutoff = fields.Datetime.now() - datetime.timedelta(minutes=int(done_minutes or 10))
            domain += ['&', ('state', 'in', ('served', 'cancel')),
                       ('fired_at', '>=', fields.Datetime.to_string(cutoff))]
            if config_id:
                domain = [('config_id', '=', int(config_id))] + domain
            tickets = Ticket.search(domain)
            channel_cfg = int(config_id) if config_id else 0
            return {
                'ok': True,
                'last_bus_id': env['bus.bus'].sudo()._bus_last_id(),
                'kds_channel': 'mezze_kds_%s' % channel_cfg,
                'waiter_channel': 'mezze_waiter_%s' % channel_cfg,
                'tickets': [t._payload() for t in tickets],
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze kds_state failed")
            return self._json({'ok': False, 'error': 'kds_state_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # BDS / Coffee queue — the barista's beverage lane + pickup board
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/bds/queue', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def bds_queue(self, config_id=None, stations=None, **kw):
        """Barista beverage queue + customer pickup board.

        ``queue`` = live beverage-station tickets (Barista/Bar by default) in
        FIFO order — the barista makes them top-to-bottom. ``pickup`` groups the
        live tickets by order and reports each order's ``tracking`` number as
        ``ready`` (every beverage ticket ready) or ``preparing`` — that's the
        customer-facing "now serving / ready for pickup" display.
        """
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            Ticket = env['mezze.kds.ticket']
            bev = list(stations) if stations else list(self._BEVERAGE_STATIONS)
            domain = [('station', 'in', bev),
                      ('state', 'in', ('fired', 'accepted', 'preparing', 'ready'))]
            if config_id:
                domain = [('config_id', '=', int(config_id))] + domain
            tickets = Ticket.search(domain, order='fired_at asc, id asc')
            by_order = {}
            for t in tickets:
                o = t.pos_order_id
                e = by_order.setdefault(o.id, {
                    'order_id': o.id,
                    'tracking': o.tracking_number or o.pos_reference or str(o.id),
                    'table': next((tk.table_label for tk in tickets
                                   if tk.pos_order_id.id == o.id and tk.table_label), None),
                    'states': []})
                e['states'].append(t.state)
            pickup = [{
                'order_id': e['order_id'], 'tracking': e['tracking'], 'table': e['table'],
                'state': 'ready' if all(s == 'ready' for s in e['states']) else 'preparing',
            } for e in by_order.values()]
            channel_cfg = int(config_id) if config_id else 0
            return {
                'ok': True,
                'last_bus_id': env['bus.bus'].sudo()._bus_last_id(),
                'kds_channel': 'mezze_kds_%s' % channel_cfg,
                'waiter_channel': 'mezze_waiter_%s' % channel_cfg,
                'queue': [t._payload() for t in tickets],
                'pickup': pickup,
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze bds_queue failed")
            return self._json({'ok': False, 'error': 'bds_queue_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/kds/transition', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def kds_transition(self, ticket_id=None, action=None, **kw):
        """Advance / recall one KDS ticket. Persists + broadcasts on the bus.

        ``action`` in accept|preparing|ready|served|cancel|recall. The move is
        applied under a row lock so two KDS screens bumping the same ticket at
        once can't double-advance it.
        """
        auth = self._authenticate()
        if auth:
            return auth
        ACTIONS = {'accept': 'accepted', 'preparing': 'preparing', 'prepare': 'preparing',
                   'ready': 'ready', 'served': 'served', 'serve': 'served', 'cancel': 'cancel'}
        try:
            env = self._api_env()
            ticket = env['mezze.kds.ticket'].browse(int(ticket_id))
            if not ticket.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            if action == 'recall':
                changed, reason = ticket.action_recall()
            elif action in ACTIONS:
                changed, reason = ticket._set_state(ACTIONS[action])
            else:
                return self._json({'ok': False, 'error': 'bad_action', 'message': str(action)}, status=400)
            return {'ok': True, 'changed': changed, 'reason': reason,
                    'ticket': ticket._payload()}
        except Exception as exc:  # noqa: BLE001
            # Two KDS screens bumping the same ticket → let PG concurrency errors
            # retry rather than swallowing them (the FOR UPDATE lock serializes).
            _reraise_if_retryable(exc)
            _logger.exception("Mezze kds_transition failed")
            return self._json({'ok': False, 'error': 'transition_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/bus/poll', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def bus_poll(self, channels=None, last=0, **kw):
        """Poll-reconcile fallback: read the REAL Odoo bus since ``last``.

        The frontend prefers a live ``/websocket`` push, but polls this every few
        seconds as a safety net so a dropped socket never leaves the board stale.
        Consumes the same ``bus.bus`` notifications the websocket delivers.
        """
        auth = self._authenticate()
        if auth:
            return auth
        try:
            env = self._api_env()
            chans = channels or []
            notifs = env['bus.bus'].sudo()._poll(chans, last=int(last or 0))
            max_id = max([n['id'] for n in notifs], default=int(last or 0))
            return {'ok': True, 'last': max_id, 'notifications': notifs}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze bus_poll failed")
            return self._json({'ok': False, 'error': 'poll_failed', 'message': str(exc)}, status=400)
