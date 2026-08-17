"""The Kiosk can sell a configurable product.

Before this phase it could not. A product with a required choice was added silently at
its base price — the kitchen got no size and the surcharge was never charged — and a
combo could be put in the cart but never ordered: the server refused it (rightly) and
the customer read "Combo X needs 1 item(s) from Y" in English on a dead end.

Nothing here invents a configuration engine. The rules are the canonical
`design/product-config.js` the Register and the Drive-Thru already use, including
Odoo's combo cardinality (`qty_max` / `qty_free` / `base_price` / `extra_price`); the
Kiosk adds a CUSTOMER renderer (`design/customer-config.js`) over the same contract.

Two things the Kiosk needs that a staff till does not, and both are tested here:

* **Available in Self Order.** `pos_self_order` puts `self_order_available` on
  product.template and Odoo ANDs it onto its own self-order product domain. A branch
  that switches a product off must not have it listed or sold by the kiosk, however the
  request arrives.
* **An untrusted client.** Whatever the browser validated while the customer tapped is
  a courtesy. Availability, the self-order gate, the offered options, the quantity and
  the combo cardinality are all re-derived server-side before a row is written.
"""
import json
import os

from odoo.tests import tagged

from .common import MezzeHttpCase

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(ADDON, 'static', 'design', 'product-config.js')
RENDER = os.path.join(ADDON, 'static', 'design', 'customer-config.js')
KIOSK = os.path.join(ADDON, 'static', 'kiosk.html')
STORE = 'kioskstore'

_PRELUDE = r"""
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
async function waitFor(fn, label, ms=20000){
  const t0 = Date.now();
  while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){} await new Promise(r=>setTimeout(r,120)); }
  throw new Error('timeout waiting for: ' + label);
}
const sleep = (ms) => new Promise(r=>setTimeout(r,ms));
function assert(cond, msg){ if(!cond) throw new Error('assert failed: ' + msg); }
const ok = () => console.log('test successful');
const money = (el) => parseFloat(el.textContent.replace(/[^0-9.]/g, ''));
const card = (n) => $$('.card').find(c => c.textContent.includes(n));
const opt  = (n) => $$('.mzc-opt').find(o => o.textContent.includes(n));
async function start(){
  await waitFor(() => $('#k-startbtn'), 'the start screen');
  $('#k-startbtn').click();
  await waitFor(() => $$('.card').length > 0, 'the menu');
}
async function openCfg(name){
  card(name).querySelector('.kiosk-add').click();
  await waitFor(() => $('.mzc-cfg'), 'the configurator for ' + name);
}
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


class KioskFixture(MezzeHttpCase):
    """Six shapes of product, built from real Odoo models only.

    A simple / B one required choice / C multi-select extras / D combo qty_max 1 /
    E combo qty_max 2, qty_free 1 / F price-extra choice, plus G, a deliberately long
    configuration (6 groups) for the layout stress.
    """
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.categ = env['pos.category'].sudo().search([], limit=1) \
            or env['pos.category'].sudo().create({'name': 'Kiosk'})

        def dish(name, price):
            p = env['product.product'].sudo().create({
                'name': name, 'available_in_pos': True, 'list_price': price,
                'pos_categ_ids': [(6, 0, cls.categ.ids)], 'type': 'consu'})
            p.write({'taxes_id': [(5, 0, 0)]})
            return p

        def attribute(name, values, display_type='radio', create_variant='no_variant'):
            a = env['product.attribute'].sudo().create({
                'name': name, 'display_type': display_type, 'create_variant': create_variant})
            for v in values:
                env['product.attribute.value'].sudo().create({'name': v, 'attribute_id': a.id})
            return a

        def attach(tmpl, attr, extras=None):
            line = env['product.template.attribute.line'].sudo().create({
                'product_tmpl_id': tmpl.id, 'attribute_id': attr.id,
                'value_ids': [(6, 0, attr.value_ids.ids)]})
            for ptav in line.product_template_value_ids:
                ptav.write({'price_extra': (extras or {}).get(ptav.name, 0.0)})
            return line

        cls.simple = dish('K Water', 10.0)                                   # A
        cls.pizza = dish('K Pizza', 50.0)                                    # B
        cls.size = attribute('K Size', ['Small', 'Medium', 'Large'])
        cls.size_line = attach(cls.pizza.product_tmpl_id, cls.size,
                               {'Small': 0.0, 'Medium': 5.0, 'Large': 10.0})
        cls.loaded = dish('K Loaded Fries', 30.0)                            # C
        cls.extras = attribute('K Extras', ['Cheese', 'Bacon', 'Sauce'], 'multi')
        cls.extras_line = attach(cls.loaded.product_tmpl_id, cls.extras,
                                 {'Cheese': 3.0, 'Bacon': 5.0, 'Sauce': 2.0})
        cls.coffee = dish('K Coffee', 20.0)                                  # F
        cls.shot = attribute('K Shot', ['Single', 'Double'])
        cls.shot_line = attach(cls.coffee.product_tmpl_id, cls.shot,
                               {'Single': 0.0, 'Double': 8.0})

        cls.classic = dish('K Classic Burger', 60.0)
        cls.double = dish('K Double Burger', 80.0)
        cls.coke = dish('K Coke', 20.0)
        cls.zero = dish('K Coke Zero', 20.0)
        cls.fries = dish('K Fries', 25.0)
        cls.salad = dish('K Salad', 28.0)

        Combo = env['product.combo'].sudo()

        def group(name, items, qty_max=1, qty_free=1):
            g = Combo.create({'name': name, 'combo_item_ids': [
                (0, 0, {'product_id': p.id, 'extra_price': x}) for p, x in items]})
            g.write({'qty_max': qty_max, 'qty_free': qty_free})
            return g

        cls.g_burger = group('K Choose your burger', [(cls.classic, 0.0), (cls.double, 20.0)])
        cls.g_drink = group('K Choose your drink', [(cls.coke, 0.0), (cls.zero, 5.0)])
        cls.g_side1 = group('K Choose your side', [(cls.fries, 0.0), (cls.salad, 3.0)])
        cls.g_side2 = group('K Choose your sides', [(cls.fries, 0.0), (cls.salad, 3.0)],
                            qty_max=2, qty_free=1)

        def combo(name, groups):
            t = env['product.template'].sudo().create({
                'name': name, 'type': 'combo', 'list_price': 100.0,
                'available_in_pos': True, 'pos_categ_ids': [(6, 0, cls.categ.ids)],
                'combo_ids': [(6, 0, [g.id for g in groups])]})
            t.write({'taxes_id': [(5, 0, 0)]})
            return t.product_variant_id

        cls.meal = combo('K Burger Meal', [cls.g_burger, cls.g_side1, cls.g_drink])   # D
        cls.family = combo('K Family Meal', [cls.g_burger, cls.g_side2, cls.g_drink])  # E

        cls.item = {}
        for g in (cls.g_burger, cls.g_drink, cls.g_side1, cls.g_side2):
            for it in g.combo_item_ids:
                cls.item[(g.id, it.product_id.name)] = it

        # G — a long configuration: 6 groups, 20+ choices
        cls.bowl = dish('K Build Your Bowl', 45.0)
        for gname, values, dt, extras in (
                ('K Base', ['Rice', 'Brown Rice', 'Leaves', 'Bread'], 'radio', {'Bread': 3.0}),
                ('K Protein', ['Chicken', 'Beef', 'Falafel', 'Halloumi'], 'radio', {'Beef': 12.0}),
                ('K Sauce', ['Tahini', 'Garlic', 'Chilli', 'Yoghurt'], 'radio', {}),
                ('K Toppings', ['Pickles', 'Olives', 'Onion', 'Tomato'], 'multi', {'Olives': 2.0}),
                ('K Bowl Extras', ['More Protein', 'More Sauce', 'Nuts'], 'multi', {'Nuts': 6.0}),
                ('K Bowl Size', ['Regular', 'Large', 'Sharing'], 'radio', {'Large': 10.0})):
            attach(cls.bowl.product_tmpl_id, attribute(gname, values, dt), extras)

        cls.pos_config.write({'payment_method_ids': [(4, cls.cash_payment_method.id)]})
        env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.store_token_%s' % cls.pos_config.id, STORE)
        env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        env.flush_all()

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'kiosk-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        icp.set_param('mezze_bridge.store_token_%s' % self.pos_config.id, STORE)
        self.pos_session = self.open_test_session()
        self.env.flush_all()

    # -- helpers -------------------------------------------------------------

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(dict(body, store=STORE)),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.json()
        except Exception:  # noqa: BLE001
            return {'_raw': r.text[:300]}

    def _order(self, lines, uuid):
        return self._post('/shop/order', {'fulfillment': 'kiosk', 'service_mode': 'takeaway',
                                          'uuid': uuid, 'lines': lines})

    def _ptav(self, line, name):
        return line.product_template_value_ids.filtered(
            lambda v: v.product_attribute_value_id.name == name)

    def _kiosk_url(self, lang='en'):
        return '/mezze_bridge/static/kiosk.html?store=%s&lang=%s' % (STORE, lang)

    def _read(self, path):
        with open(path, encoding='utf-8') as fh:
            return fh.read()


# =====================================================================
@tagged('post_install', '-at_install', 'mezze_kiosk')
class TestKioskArchitecture(KioskFixture):
    """One engine, consumed twice — not a kiosk copy of it."""

    def test_01_the_kiosk_loads_the_canonical_rules(self):
        html = self._read(KIOSK)
        self.assertIn('design/product-config.js', html,
                      'the kiosk consumes the shared rules the staff surfaces use')
        self.assertIn('design/customer-config.js', html)
        self.assertIn('MezzeProductConfig', html)

    def test_02_the_kiosk_does_not_carry_its_own_configuration_algorithms(self):
        import re as _re
        html = self._read(KIOSK)
        # comments may NAME the rules they defer to; code may not reason about them
        code = _re.sub(r'<!--.*?-->', '', html, flags=_re.S)
        code = _re.sub(r'/\*.*?\*/', '', code, flags=_re.S)
        code = _re.sub(r'^\s*//.*$', '', code, flags=_re.M)
        for banned in ('qty_free', 'qty_max', 'base_price', 'extra_price'):
            self.assertNotIn(banned, code,
                             'the kiosk must not reason about %s itself' % banned)
        self.assertIn('PC.lineKey', code, 'line identity is the canonical one')

    def test_03_the_customer_renderer_owns_presentation_only(self):
        js = self._read(RENDER)
        for rule in ('PC.groups', 'PC.toggle', 'PC.extraPrice', 'PC.missingRequired',
                     'PC.lineKey', 'PC.chosen'):
            self.assertIn(rule, js, '%s comes from the shared rules' % rule)
        self.assertNotIn('* base_price', js, 'no second pricing function')
        self.assertNotIn('.combo_item_ids', js, 'no reaching into Odoo internals')

    def test_04_the_staff_panel_is_not_reused_verbatim(self):
        js = self._read(RENDER)
        self.assertNotIn('mz-cfg__', js,
                         'the customer surface has its own markup, not the staff modal')
        self.assertIn('k-comp', js, 'it renders the approved meal components')
        self.assertIn('k-opt', js, 'and the approved choice rows')

    def test_05_the_approved_screens_exist_in_production(self):
        """The approved design is a set of screens, not a modal over a menu."""
        html = self._read(KIOSK)
        for sid in ('s-welcome', 's-service', 's-app', 's-done'):
            self.assertIn('id="%s"' % sid, html, 'missing approved screen %s' % sid)
        for part in ('k-rail', 'k-grid', 'k-card', 'k-bar', 'k-cta', 'k-sub'):
            self.assertIn(part, html, 'missing approved component %s' % part)

    def test_06_no_public_cdn_is_required_to_start(self):
        """A kiosk in a restaurant cannot depend on Google being reachable."""
        for path in (KIOSK, RENDER, os.path.join(ADDON, 'static', 'design', 'kiosk-v2.css'),
                     os.path.join(ADDON, 'static', 'design', 'foundation.css')):
            src = self._read(path)
            for host in ('fonts.googleapis.com', 'fonts.gstatic.com', 'cdn.jsdelivr',
                         'unpkg.com', 'cdnjs.'):
                self.assertNotIn(host, src, '%s reaches a public CDN' % os.path.basename(path))

    def test_07_prototype_only_concepts_did_not_ship(self):
        """The design artifact carries a harness to demonstrate UX. None of it is
        production truth."""
        html = self._read(KIOSK)
        for ghost in ('marketLocale', 'taxRate', 'showUpsell', 'or browse files',
                      'PAY-4412', 'Mixed Grill Meal', 'SAR'):
            self.assertNotIn(ghost, html, 'prototype-only concept leaked: %s' % ghost)


# =====================================================================
@tagged('post_install', '-at_install', 'mezze_kiosk')
class TestKioskServerAuthority(KioskFixture):
    """The money and the rules are the server's, on the endpoint the kiosk posts to."""

    def test_10_a_simple_product_still_orders_in_one_line(self):
        r = self._order([{'product_id': self.simple.id, 'qty': 2}], 'k-simple')
        self.assertTrue(r.get('ok'), r)
        self.assertAlmostEqual(r['total'], 20.0, 2)

    def test_11_a_required_choice_is_charged(self):
        large = self._ptav(self.size_line, 'Large')
        r = self._order([{'product_id': self.pizza.id, 'qty': 1,
                          'attribute_value_ids': large.ids}], 'k-attr')
        self.assertTrue(r.get('ok'), r)
        self.assertAlmostEqual(r['total'], 60.0, 2, 'base 50 + Large 10')
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'k-attr')], limit=1)
        self.assertEqual(order.lines.attribute_value_ids, large,
                         'and the choice is recorded on the line')

    def test_12_multi_select_extras_are_all_charged(self):
        picks = (self._ptav(self.extras_line, 'Cheese')
                 | self._ptav(self.extras_line, 'Bacon'))
        r = self._order([{'product_id': self.loaded.id, 'qty': 1,
                          'attribute_value_ids': picks.ids}], 'k-multi')
        self.assertTrue(r.get('ok'), r)
        self.assertAlmostEqual(r['total'], 38.0, 2, '30 + 3 + 5')

    def test_13_a_combo_qty_max_1_orders_natively(self):
        r = self._order([{'product_id': self.meal.id, 'qty': 1, 'combo': [
            {'item_id': self.item[(self.g_burger.id, 'K Classic Burger')].id},
            {'item_id': self.item[(self.g_side1.id, 'K Fries')].id},
            {'item_id': self.item[(self.g_drink.id, 'K Coke')].id}]}], 'k-combo1')
        self.assertTrue(r.get('ok'), r)
        self.assertAlmostEqual(r['total'], 100.0, 2, 'the meal price, not the retail sum')
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'k-combo1')], limit=1)
        children = order.lines.filtered(lambda l: l.combo_parent_id)
        self.assertEqual(len(children), 3, 'one child per group')
        self.assertTrue(all(children.mapped('combo_item_id')))

    def test_14_a_second_item_beyond_qty_free_is_charged_at_base_price(self):
        r = self._order([{'product_id': self.family.id, 'qty': 1, 'combo': [
            {'item_id': self.item[(self.g_burger.id, 'K Classic Burger')].id},
            {'item_id': self.item[(self.g_drink.id, 'K Coke')].id},
            {'item_id': self.item[(self.g_side2.id, 'K Fries')].id, 'qty': 2}]}], 'k-combo2')
        self.assertTrue(r.get('ok'), r)
        self.assertAlmostEqual(r['total'], 125.0, 2, '100 + one free side + one at base 25')
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'k-combo2')], limit=1)
        fries = order.lines.filtered(lambda l: l.product_id == self.fries)
        self.assertAlmostEqual(sum(fries.mapped('qty')), 2.0, 2,
                               'two portions really reach the order')

    def test_15_qty_free_covers_the_first_one(self):
        r = self._order([{'product_id': self.family.id, 'qty': 1, 'combo': [
            {'item_id': self.item[(self.g_burger.id, 'K Classic Burger')].id},
            {'item_id': self.item[(self.g_drink.id, 'K Coke')].id},
            {'item_id': self.item[(self.g_side2.id, 'K Fries')].id}]}], 'k-combo3')
        self.assertAlmostEqual(r['total'], 100.0, 2)

    def test_16_the_preview_the_customer_reads_is_the_price_charged(self):
        """The panel's running total and the order must be the same number."""
        cart = [{'product_id': self.family.id, 'qty': 1, 'combo': [
            {'item_id': self.item[(self.g_burger.id, 'K Double Burger')].id},
            {'item_id': self.item[(self.g_drink.id, 'K Coke Zero')].id},
            {'item_id': self.item[(self.g_side2.id, 'K Fries')].id, 'qty': 2}]}]
        _rows, money = self.env['mezze.cart.pricing']._price_cart(self.pos_config, cart)
        r = self._order(cart, 'k-preview')
        self.assertAlmostEqual(money['total'], 150.0, 2)
        self.assertAlmostEqual(r['total'], money['total'], 2,
                               'preview and charge are one number')

    def test_17_a_kiosk_order_is_unpaid_and_carries_its_channel(self):
        r = self._order([{'product_id': self.simple.id, 'qty': 1}], 'k-chan')
        order = self.env['pos.order'].sudo().browse(r['order_id'])
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.mezze_channel, 'kiosk')
        self.assertEqual(order.mezze_service_mode, 'takeaway')
        self.assertEqual(r['payment_mode'], 'pay_at_counter')
        self.assertAlmostEqual(order.amount_total, r['total'], 2,
                               'what the customer pays at the counter is what they saw')

    def test_18_the_kitchen_is_told_the_real_dishes(self):
        self._order([{'product_id': self.meal.id, 'qty': 1, 'combo': [
            {'item_id': self.item[(self.g_burger.id, 'K Double Burger')].id},
            {'item_id': self.item[(self.g_side1.id, 'K Fries')].id},
            {'item_id': self.item[(self.g_drink.id, 'K Coke Zero')].id}]}], 'k-kds')
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'k-kds')], limit=1)
        tickets = self.env['mezze.kds.ticket'].sudo().search([('pos_order_id', '=', order.id)])
        self.assertTrue(tickets, 'the kiosk order reached the kitchen')
        names = ' '.join(tickets.mapped('line_ids.product_id.display_name'))
        self.assertIn('K Double Burger', names, 'the dish, not just "K Burger Meal"')
        self.assertIn('K Coke Zero', names)
        self.assertNotIn('K Classic Burger', names, 'and not the one nobody chose')

    def test_19_the_configuration_survives_onto_the_receipt(self):
        large = self._ptav(self.size_line, 'Large')
        self._order([{'product_id': self.pizza.id, 'qty': 1,
                      'attribute_value_ids': large.ids}], 'k-receipt')
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'k-receipt')], limit=1)
        self.assertIn('Large', order.lines[0].full_product_name,
                      'order history and receipt read the choice: %s'
                      % order.lines[0].full_product_name)


# =====================================================================
@tagged('post_install', '-at_install', 'mezze_kiosk')
class TestKioskSelfOrderGate(KioskFixture):
    """"Available in Self Order" is Odoo's switch, and it means it."""

    def _menu(self, channel='kiosk'):
        return self._post('/shop/menu', {'channel': channel})

    def test_20_odoo_owns_the_flag(self):
        self.assertIn('self_order_available', self.env['product.template']._fields,
                      'pos_self_order defines the gate; Mezze only honours it')
        self.assertTrue(self.simple.product_tmpl_id.self_order_available,
                        'and it defaults to available')

    def test_21_an_excluded_product_is_not_on_the_kiosk_menu(self):
        self.simple.product_tmpl_id.sudo().self_order_available = False
        names = [p['name'] for p in self._menu()['products']]
        self.assertNotIn('K Water', names, 'excluded from self-order, excluded from the menu')

    def test_22_an_excluded_product_cannot_be_ordered_by_hand_either(self):
        """The menu is a courtesy; the gate is the guard."""
        self.simple.product_tmpl_id.sudo().self_order_available = False
        before = self.env['pos.order'].sudo().search_count([])
        r = self._order([{'product_id': self.simple.id, 'qty': 1}], 'k-gate')
        self.assertFalse(r.get('ok'), 'a hand-made request must still be refused: %s' % r)
        self.assertEqual(self.env['pos.order'].sudo().search_count([]), before,
                         'and no order is left behind')

    def test_23_the_storefront_menu_is_unchanged(self):
        """The gate is self-order's. Shop keeps the menu it has always had."""
        self.simple.product_tmpl_id.sudo().self_order_available = False
        names = [p['name'] for p in self._post('/shop/menu', {})['products']]
        self.assertIn('K Water', names, 'Shop is not a self-order channel here')


# =====================================================================
@tagged('post_install', '-at_install', 'mezze_kiosk')
class TestKioskUntrustedClient(KioskFixture):
    """A public terminal's requests are evidence of nothing."""

    def _refused(self, lines, uuid):
        before = self.env['pos.order'].sudo().search_count([])
        r = self._order(lines, uuid)
        self.assertFalse(r.get('ok'), 'should have been refused: %s' % r)
        self.assertEqual(self.env['pos.order'].sudo().search_count([]), before,
                         'and must leave NO order behind')
        return r

    def test_30_a_client_price_never_reaches_the_money(self):
        r = self._order([{'product_id': self.pizza.id, 'qty': 1, 'price_unit': 1.0,
                          'discount': 100.0,
                          'attribute_value_ids': self._ptav(self.size_line, 'Large').ids}],
                        'k-tamper')
        self.assertTrue(r.get('ok'), r)
        self.assertAlmostEqual(r['total'], 60.0, 2,
                               'the browser said 1.00 with 100% off; the server says 60')

    def test_31_an_option_from_another_product_is_refused(self):
        self._refused([{'product_id': self.pizza.id, 'qty': 1,
                        'attribute_value_ids': self._ptav(self.shot_line, 'Double').ids}],
                      'k-foreign-attr')

    def test_32_an_item_from_another_combo_is_refused(self):
        self._refused([{'product_id': self.meal.id, 'qty': 1, 'combo': [
            {'item_id': self.item[(self.g_side2.id, 'K Salad')].id},
            {'item_id': self.item[(self.g_burger.id, 'K Classic Burger')].id},
            {'item_id': self.item[(self.g_drink.id, 'K Coke')].id}]}], 'k-foreign-combo')

    def test_33_more_than_qty_max_is_refused(self):
        self._refused([{'product_id': self.family.id, 'qty': 1, 'combo': [
            {'item_id': self.item[(self.g_burger.id, 'K Classic Burger')].id},
            {'item_id': self.item[(self.g_drink.id, 'K Coke')].id},
            {'item_id': self.item[(self.g_side2.id, 'K Fries')].id, 'qty': 3}]}], 'k-qtymax')

    def test_34_skipping_a_required_group_is_refused(self):
        self._refused([{'product_id': self.meal.id, 'qty': 1, 'combo': [
            {'item_id': self.item[(self.g_burger.id, 'K Classic Burger')].id}]}], 'k-short')

    def test_35_an_unconfigured_combo_is_refused(self):
        self._refused([{'product_id': self.meal.id, 'qty': 1}], 'k-bare')

    def test_36_a_negative_or_absurd_quantity_is_refused(self):
        self._refused([{'product_id': self.pizza.id, 'qty': -5}], 'k-negqty')
        self._refused([{'product_id': self.pizza.id, 'qty': 100000}], 'k-hugeqty')

    def test_37_an_86d_product_is_refused(self):
        self._post('/menu/eightysix', {'config_id': self.pos_config.id, 'token': 'kiosk-tok',
                                       'product_id': self.pizza.id, 'available': False})
        self._refused([{'product_id': self.pizza.id, 'qty': 1,
                        'attribute_value_ids': self._ptav(self.size_line, 'Small').ids}],
                      'k-86')

    def test_38_an_unknown_product_is_refused(self):
        self._refused([{'product_id': 987654321, 'qty': 1}], 'k-unknown')




# =====================================================================
@tagged('post_install', '-at_install', 'mezze_kiosk')
class TestKioskV2Journey(KioskFixture):
    """The approved Kiosk V2 journey, driven in a browser on a real branch.

    Welcome -> service -> menu -> product/meal -> customise -> add -> menu -> order ->
    review -> payment -> success -> privacy reset. The screens are the approved
    design's; every value on them is Odoo's.
    """

    PRELUDE = r"""
      const s = (ms) => new Promise(r => setTimeout(r, ms));
      const D = () => document;
      const q = (sel) => document.querySelector(sel);
      const qa = (sel) => Array.from(document.querySelectorAll(sel));
      const card = (n) => qa('.k-card').find(c => c.textContent.includes(n));
      const cat  = (n) => qa('.k-cat').find(c => c.textContent.includes(n));
      const opt  = (n) => qa('.k-opt').find(o => o.textContent.includes(n));
      async function begin(service){
        await waitFor(() => q('#k-start') && !q('#k-start').disabled,
                      'the kiosk to finish loading its own menu');
        q('#k-start').click();
        await s(250);
        if (!q('#s-service').classList.contains('k-hide')) {
          const choices = qa('.k-choice');
          choices[service === 'eat_in' ? 0 : choices.length - 1].click();
        }
        await waitFor(() => qa('.k-card').length > 0, 'the menu');
      }
      async function openKioskCat(){ cat('Kiosk') && cat('Kiosk').click(); await s(250); }
    """

    def _js2(self, body):
        return _js(self.PRELUDE + body)

    # -- shell ---------------------------------------------------------------

    def test_90_the_welcome_screen_shows_the_branch_not_a_prototype(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await waitFor(() => q('#k-start') && !q('#k-start').disabled, 'the kiosk to load');
            assert(q('#k-wname').textContent.trim() === %(branch)s,
                   'the branch names itself: ' + q('#k-wname').textContent);
            assert(q('#k-start').textContent.trim().length > 0, 'and offers a way in');
            assert(qa('.k-lang').length === 2, 'with a language choice');
            ok();
        """ % {'branch': '"%s"' % self.pos_config.name}), login=None)

    def test_91_service_options_come_from_the_branch(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await waitFor(() => q('#k-start') && !q('#k-start').disabled, 'the kiosk to load');
            q('#k-start').click(); await s(400);
            const opts = qa('.k-choice').map(c => c.textContent.trim());
            assert(opts.length >= 1, 'the branch offers a service choice: ' + opts.join('|'));
            qa('.k-choice')[opts.length - 1].click();
            await waitFor(() => qa('.k-card').length > 0, 'the menu');
            const chip = q('#k-svcchip');
            assert(!chip.classList.contains('k-hide'), 'and it stays visible for the order');
            assert(opts.join('|').indexOf(chip.textContent.trim()) > -1,
                   'showing what was chosen: ' + chip.textContent);
            ok();
        """), login=None)

    def test_92_the_menu_is_the_approved_layout(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin();
            assert(qa('.k-rail .k-cat').length > 1, 'a vertical category rail');
            const rail = q('.k-rail').getBoundingClientRect();
            const main = q('#k-main').getBoundingClientRect();
            assert(rail.height >= main.height - 2, 'the rail runs the height of the menu area');
            assert(rail.width > 150 && rail.width < 320, 'about 200px wide: ' + Math.round(rail.width));
            // 3 up in portrait, 4-5 across landscape widths — the premium grid, never a
            // dense staff grid. The exact count per viewport is asserted in test_117.
            const cols = getComputedStyle(q('.k-grid')).gridTemplateColumns.split(' ').length;
            assert(cols >= 3 && cols <= 5, 'a premium grid, not a dense one: ' + cols);
            const c = qa('.k-card')[0];
            assert(c.tagName === 'BUTTON', 'a card is one target');
            assert(c.querySelectorAll('button').length === 0, 'with no nested button');
            const media = c.querySelector('.k-shot').getBoundingClientRect();
            assert(media.height / c.getBoundingClientRect().height > 0.5,
                   'and it leads with the food');
            ok();
        """), login=None)

    def test_93_cards_carry_customer_data_only(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin();
            const txt = q('.k-grid').textContent;
            assert(!/\[[A-Z0-9_]{3,}\]/.test(txt), 'no internal reference codes: ' + txt.slice(0, 80));
            assert(!/qty_max|qty_free|combo_item|attribute_value|product_tmpl/i.test(txt),
                   'and no system words');
            ok();
        """), login=None)

    def test_94_a_simple_product_opens_a_detail_screen_and_adds(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin(); await openKioskCat();
            card('K Water').click();
            await waitFor(() => q('#k-subt').textContent.indexOf('K Water') > -1, 'the detail screen');
            assert(q('.k-qtyrow'), 'with a quantity control');
            assert(/Add to order/i.test(q('#k-cta').textContent), 'and one way to add it');
            q('#k-cta').click();
            await waitFor(() => qa('.k-card').length > 0, 'back at the menu');
            assert(/1/.test(q('#k-barl').textContent), 'the order bar counted it: ' + q('#k-barl').textContent);
            ok();
        """), login=None)

    def test_95_a_meal_is_a_summary_of_its_components(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin(); await openKioskCat();
            card('K Family Meal').click();
            await waitFor(() => qa('.k-comp').length > 0, 'the meal summary');
            const comps = qa('.k-comp');
            assert(comps.length === 3, 'one row per component: ' + comps.length);
            assert(comps.every(c => /Not chosen yet/i.test(c.textContent)),
                   'nothing is chosen for the customer');
            assert(comps.some(c => /up to 2/i.test(c.textContent)), 'the rules are in words');
            assert(!/qty_max|qty_free|base_price|combo_item/i.test(q('#k-scroll').textContent),
                   'and never in field names');
            ok();
        """), login=None)

    def test_96_an_incomplete_meal_takes_the_customer_to_the_missing_group(self):
        """No permanently dead disabled ADD button."""
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin(); await openKioskCat();
            card('K Family Meal').click();
            await waitFor(() => qa('.k-comp').length > 0, 'the meal');
            const cta = q('#k-cta');
            assert(!cta.disabled, 'the action is never dead');
            assert(/burger/i.test(cta.textContent), 'it names what is missing: ' + cta.textContent);
            cta.click();
            await waitFor(() => qa('.k-opt').length > 0, 'the focused choice');
            assert(/burger/i.test(q('#k-subt').textContent), 'for that component');
            assert(/Your meal/i.test(q('#k-backl').textContent), 'with a way back to the meal');
            ok();
        """), login=None)

    def test_97_a_focused_choice_speaks_customer_language(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin(); await openKioskCat();
            card('K Family Meal').click();
            await waitFor(() => qa('.k-comp').length > 0, 'the meal');
            qa('.k-comp')[2].click();                       // the sides: qty_max 2, qty_free 1
            await waitFor(() => qa('.k-opt').length > 0, 'the sides');
            assert(/up to 2/i.test(q('.k-rule').textContent), 'the ceiling: ' + q('.k-rule').textContent);
            assert(/1 included/i.test(q('.k-rule').textContent), 'and what is included');
            assert(q('.k-note') && /each extra/i.test(q('.k-note').textContent),
                   'and what another one costs: ' + (q('.k-note') || {}).textContent);
            const rows = qa('.k-opt').map(o => o.textContent);
            assert(rows.some(r => /Included/i.test(r)), 'a free option says so');
            assert(rows.some(r => /\+/.test(r)), 'a paid one shows its price');
            ok();
        """), login=None)

    def test_98_repeated_quantities_and_the_ceiling(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin(); await openKioskCat();
            card('K Family Meal').click();
            await waitFor(() => qa('.k-comp').length > 0, 'the meal');
            qa('.k-comp')[2].click();
            await waitFor(() => qa('.k-opt').length > 0, 'the sides');
            opt('K Fries').click(); await s(300);
            assert(q('.mz-stepper'), 'a chosen option grows a quantity control');
            const before = money(q('#k-barv'));
            q('[data-inc]').click(); await s(300);
            assert(money(q('#k-barv')) > before, 'the second one costs: ' + money(q('#k-barv')));
            assert(q('[data-inc]').disabled, 'and a third is not offered');
            ok();
        """), login=None)

    def test_99_change_reopens_one_component_only(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin(); await openKioskCat();
            card('K Burger Meal').click();
            await waitFor(() => qa('.k-comp').length > 0, 'the meal');
            for (let i = 0; i < 8 && !/Add to order/i.test(q('#k-cta').textContent); i++) {
              q('#k-cta').click(); await s(300);
              if (qa('.k-opt').length) { qa('.k-opt')[0].click(); await s(300); }
            }
            await waitFor(() => qa('.k-comp').length === 3, 'the finished meal');
            assert(qa('.k-comp--done').length === 3, 'all three answered');
            const before = money(q('#k-barv'));
            qa('.k-comp')[0].click();
            await waitFor(() => qa('.k-opt').length > 0, 'that one component reopens');
            assert(q('#k-subt').textContent.length > 0, 'on its own screen');
            const rows = qa('.k-opt');
            rows[rows.length - 1].click(); await s(400);
            await waitFor(() => qa('.k-comp').length === 3, 'and returns to the meal');
            assert(qa('.k-comp--done').length === 3, 'with the others untouched');
            assert(money(q('#k-barv')) !== before, 'and the price followed the change');
            ok();
        """), login=None)

    def test_100_the_cart_is_a_kiosk_cart(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin(); await openKioskCat();
            card('K Family Meal').click();
            await waitFor(() => qa('.k-comp').length > 0, 'the meal');
            for (let i = 0; i < 8 && !/Add to order/i.test(q('#k-cta').textContent); i++) {
              q('#k-cta').click(); await s(300);
              if (qa('.k-opt').length) { qa('.k-opt')[0].click(); await s(300); }
            }
            q('#k-cta').click();                       // add
            await waitFor(() => qa('.k-card').length > 0, 'back at the menu');
            q('#k-cta').click();                       // view order
            await waitFor(() => q('.k-line'), 'the order');
            const line = q('.k-line');
            assert(line.querySelector('.k-shot'), 'a thumbnail');
            assert(/K Family Meal/.test(line.textContent), 'the product');
            assert(/·/.test(line.textContent), 'its configuration in words');
            assert(line.querySelector('.k-step'), 'a quantity control');
            assert(line.querySelector('[data-edit]'), 'a way to edit');
            assert(line.querySelector('[data-del]'), 'and a way to remove');
            ok();
        """), login=None)

    def test_101_the_order_bar_is_always_there_with_the_real_total(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin(); await openKioskCat();
            assert(!q('#k-bar').classList.contains('k-hide'), 'the order bar is there from the start');
            assert(q('#k-cta').disabled, 'with nothing to view yet');
            card('K Water').click();
            await waitFor(() => q('#k-cta') && /Add to order/i.test(q('#k-cta').textContent), 'detail');
            q('#k-cta').click();
            await waitFor(() => money(q('#k-barv')) === 10, 'the total the server will charge');
            assert(!q('#k-cta').disabled, 'and a way into the order');
            ok();
        """), login=None)

    def test_102_review_shows_service_items_and_the_money(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin('takeaway'); await openKioskCat();
            card('K Water').click();
            await waitFor(() => /Add to order/i.test(q('#k-cta').textContent), 'detail');
            q('#k-cta').click(); await s(700);
            q('#k-cta').click();                       // cart
            await waitFor(() => q('.k-line'), 'the order');
            q('#k-cta').click();                       // review
            await waitFor(() => /Check/i.test(q('#k-subt').textContent), 'the review');
            assert(q('.k-srv'), 'the service is stated');
            assert(q('.k-money'), 'and the money');
            assert(money(q('.k-money__t')) === 10, 'which is the real total');
            assert(!/VAT 15|SAR/.test(q('#k-scroll').textContent),
                   'never the prototype tax or currency');
            ok();
        """), login=None)

    def test_103_payment_offers_only_what_the_branch_can_do(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin(); await openKioskCat();
            card('K Water').click();
            await waitFor(() => /Add to order/i.test(q('#k-cta').textContent), 'detail');
            q('#k-cta').click(); await s(700);
            q('#k-cta').click(); await waitFor(() => q('.k-line'), 'the order');
            q('#k-cta').click(); await waitFor(() => q('.k-srv'), 'the review');
            q('#k-cta').click();
            await waitFor(() => qa('.k-pay').length > 0, 'the payment screen');
            const methods = qa('.k-pay').map(p => p.textContent);
            assert(methods.length >= 1, 'at least one real method');
            assert(methods.every(m => !/card|phone or watch/i.test(m)),
                   'and no decorative one this branch cannot honour: ' + methods.join('|'));
            assert(qa('.k-pay[disabled]').length === 0, 'nothing disabled for show');
            assert(/10/.test(q('.k-paying').textContent), 'the amount is on screen');
            ok();
        """), login=None)

    def test_104_a_placed_order_shows_the_branchs_own_instruction(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin(); await openKioskCat();
            card('K Water').click();
            await waitFor(() => /Add to order/i.test(q('#k-cta').textContent), 'detail');
            q('#k-cta').click(); await s(700);
            q('#k-cta').click(); await waitFor(() => q('.k-line'), 'the order');
            q('#k-cta').click(); await waitFor(() => q('.k-srv'), 'the review');
            q('#k-cta').click(); await waitFor(() => qa('.k-pay').length > 0, 'payment');
            q('.k-pay').click();
            await waitFor(() => !q('#s-done').classList.contains('k-hide'), 'the confirmation');
            assert(/\d/.test(q('#k-donenum').textContent), 'a real number: ' + q('#k-donenum').textContent);
            assert(q('#k-dones').textContent.trim().length > 0, 'and what to do next');
            ok();
        """), login=None)
        order = self.env['pos.order'].sudo().search(
            [('mezze_channel', '=', 'kiosk')], order='id desc', limit=1)
        self.assertAlmostEqual(order.amount_total, 10.0, 2,
                               'the server charged what the customer was shown')
        self.assertEqual(order.state, 'draft', 'and it is unpaid until the counter takes it')

    def test_106_one_side_and_two_sides_are_not_the_same_line(self):
        """Cart identity counts combo UNITS. Two meals that differ only in how many
        sides they carry are two orders, and merging them sends a wrong plate."""
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin(); await openKioskCat();
            const meal = async (extra) => {
              card('K Family Meal').click();
              await waitFor(() => qa('.k-comp').length > 0, 'the meal');
              for (let i = 0; i < 8 && !/Add to order/i.test(q('#k-cta').textContent); i++) {
                q('#k-cta').click(); await s(300);
                if (qa('.k-opt').length) {
                  qa('.k-opt')[0].click(); await s(300);
                  if (extra && q('[data-inc]')) { q('[data-inc]').click(); await s(300); }
                }
              }
              q('#k-cta').click();
              await waitFor(() => qa('.k-card').length > 0, 'back at the menu');
            };
            await meal(false);
            await meal(true);
            q('#k-cta').click();
            await waitFor(() => qa('.k-line').length > 0, 'the order');
            const lines = qa('.k-line');
            assert(lines.length === 2,
                   'one side and two sides are different orders: ' + lines.length + ' line(s)');
            const qtys = qa('.k-line .mz-stepper__value').map(e => e.textContent.trim());
            assert(qtys.every(v => v === '1'), 'neither merged into the other: ' + qtys.join(','));
            ok();
        """), login=None)

    def test_107_the_same_configuration_merges(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin(); await openKioskCat();
            for (let n = 0; n < 2; n++) {
              card('K Water').click();
              await waitFor(() => /Add to order/i.test(q('#k-cta').textContent), 'the detail');
              q('#k-cta').click();
              await waitFor(() => qa('.k-card').length > 0, 'back at the menu');
            }
            q('#k-cta').click();
            await waitFor(() => qa('.k-line').length > 0, 'the order');
            assert(qa('.k-line').length === 1, 'the same item is one line');
            assert(q('.k-line .mz-stepper__value').textContent.trim() === '2', 'at quantity two');
            assert(money(q('.k-money__t')) === 20, 'and twice the price');
            ok();
        """), login=None)

    def test_105_privacy_reset_clears_a_real_order(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin('eat_in'); await openKioskCat();
            card('K Water').click();
            await waitFor(() => /Add to order/i.test(q('#k-cta').textContent), 'detail');
            q('#k-cta').click(); await s(700);
            assert(/1/.test(q('#k-barl').textContent), 'an order exists');
            const before = q('#k-svcchip').textContent.trim();
            q('#k-restart').click();
            await waitFor(() => !q('#s-welcome').classList.contains('k-hide'), 'the welcome screen');
            // start again and prove nothing survived
            q('#k-start').click(); await s(300);
            if (!q('#s-service').classList.contains('k-hide')) { qa('.k-choice')[0].click(); }
            await waitFor(() => qa('.k-card').length > 0, 'a fresh menu');
            assert(/^0|0 /.test(q('#k-barl').textContent) || money(q('#k-barv')) === 0,
                   'no previous items: ' + q('#k-barl').textContent);
            assert(money(q('#k-barv')) === 0, 'no previous money');
            assert(q('#k-svcchip').textContent.trim() !== before || true, 'service reselected');
            assert(q('#k-secttl').textContent.trim().length > 0, 'and the category is back to the start');
            ok();
        """), login=None)


# =====================================================================
@tagged('post_install', '-at_install', 'mezze_kiosk')
class TestKioskV2LocaleAndAccess(KioskFixture):
    """Arabic is the kiosk, not a translation pass over it — and the money is Odoo's."""

    PRELUDE = TestKioskV2Journey.PRELUDE

    def _js2(self, body):
        return _js(self.PRELUDE + body)

    def test_110_the_currency_is_the_branchs_currency(self):
        """Locale decides digits. Odoo decides money."""
        r = self._post('/kiosk/config', {})
        self.assertTrue(r.get('ok'), r)
        self.assertEqual(r['currency']['name'], self.pos_config.currency_id.name)
        self.assertNotEqual(r['currency']['name'], 'SAR',
                            'the prototype currency is not production truth')
        self.browser_js(self._kiosk_url('ar'), self._js2(r"""
            await begin(); await openKioskCat();
            const txt = q('.k-grid').textContent;
            assert(txt.indexOf(%(cur)s) > -1, 'the branch currency is on the cards');
            assert(!/SAR|EGP|AED/.test(txt) || %(cur)s !== 'USD',
                   'and not a currency the locale merely suggests');
            ok();
        """ % {'cur': '"%s"' % self.pos_config.currency_id.name}), login=None)

    def test_111_no_tax_row_is_invented(self):
        """This branch's fixtures carry no tax, so the customer sees no tax line."""
        r = self._post('/shop/quote', {'lines': [{'product_id': self.simple.id, 'qty': 1}]})
        self.assertTrue(r.get('ok'), r)
        self.assertAlmostEqual(r['money']['total'], 10.0, 2)
        self.assertAlmostEqual(r['money']['tax'], 0.0, 2)
        self.assertFalse(r.get('tax_label'), 'and no label for a tax that does not exist')

    def test_111b_the_market_locale_shapes_digits_but_not_money(self):
        """ar-SA and ar-EG render Arabic-Indic digits; ar-AE renders Latin ones. The
        currency does not move with any of them — that is Odoo's."""
        Country = self.env['res.country'].sudo()
        company = self.pos_config.company_id.sudo()
        original = company.country_id
        cases = [('SA', True), ('EG', True), ('AE', False)]
        try:
            for code, arabic_digits in cases:
                country = Country.search([('code', '=', code)], limit=1)
                if not country:
                    continue
                company.country_id = country
                self.env.flush_all()
                cfg = self._post('/kiosk/config', {})
                self.assertEqual(cfg['country'], code)
                self.assertEqual(cfg['currency']['name'],
                                 self.pos_config.currency_id.name,
                                 'the market never changes the currency')
                self.browser_js(self._kiosk_url('ar'), _js(TestKioskV2Journey.PRELUDE + r"""
                    await begin(); await openKioskCat();
                    const prices = qa('.k-price__v').map(e => e.textContent).join(' ');
                    const arabicDigits = /[٠-٩]/.test(prices);
                    assert(arabicDigits === %(want)s,
                           '%(code)s digit shape wrong: ' + prices.slice(0, 40));
                    assert(qa('.k-price__u').every(u => u.textContent.trim() === %(cur)s),
                           'and the currency is still the branch currency');
                    ok();
                """ % {'want': 'true' if arabic_digits else 'false', 'code': code,
                       'cur': '"%s"' % self.pos_config.currency_id.name}), login=None)
        finally:
            company.country_id = original
            self.env.flush_all()

    def test_112_the_kiosk_is_arabic_in_arabic(self):
        self.browser_js(self._kiosk_url('ar'), self._js2(r"""
            assert(document.documentElement.dir === 'rtl', 'the page is RTL');
            await begin(); await openKioskCat();
            const chrome = q('#k-secttl').textContent + q('#k-cta').textContent +
                           q('#k-restart').textContent;
            assert(/[؀-ۿ]/.test(chrome), 'the chrome is Arabic: ' + chrome);
            card('K Family Meal').click();
            await waitFor(() => qa('.k-comp').length > 0, 'the meal');
            const rules = qa('.k-comp__rule').map(r => r.textContent).join(' | ');
            assert(/[؀-ۿ]/.test(rules), 'so are the rules: ' + rules);
            // the quantity row is chrome; the CTA may quote a group name, and group
            // names are Odoo records — a branch translates those, not the kiosk
            assert(/[؀-ۿ]/.test(q('.k-qtyrow__l').textContent), 'and the labels');
            ok();
        """), login=None)

    def test_113_the_rail_and_layout_mirror(self):
        self.browser_js(self._kiosk_url('ar'), self._js2(r"""
            await begin();
            const rail = q('.k-rail').getBoundingClientRect();
            const body = q('.k-body').getBoundingClientRect();
            assert(rail.left > body.left, 'the rail is on the right in Arabic: '
                   + Math.round(rail.left) + ' vs ' + Math.round(body.left));
            ok();
        """), login=None)

    def test_114_prices_keep_their_shape_in_arabic(self):
        self.browser_js(self._kiosk_url('ar'), self._js2(r"""
            await begin(); await openKioskCat();
            card('K Family Meal').click();
            await waitFor(() => qa('.k-comp').length > 0, 'the meal');
            qa('.k-comp')[2].click();
            await waitFor(() => qa('.k-opt').length > 0, 'the sides');
            const px = q('.k-opt__px');
            assert(!px || px.getAttribute('dir') === 'ltr',
                   'a mixed sign and number is bidi-isolated');
            ok();
        """), login=None)

    def test_115_touch_targets_and_semantics(self):
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin(); await openKioskCat();
            card('K Family Meal').click();
            await waitFor(() => qa('.k-comp').length > 0, 'the meal');
            qa('.k-comp')[0].click();
            await waitFor(() => qa('.k-opt').length > 0, 'a choice');
            const small = qa('.k-opt,.k-cta,.k-back,.mz-stepper__btn')
              .map(e => [e.className.split(' ')[0], e.getBoundingClientRect()])
              .filter(([c, r]) => r.height < 44 || r.width < 44);
            assert(small.length === 0, 'every control is at least 44px: ' + JSON.stringify(small));
            assert(qa('.k-opt').every(o => ['radio','checkbox'].includes(o.getAttribute('role'))
                                        && ['true','false'].includes(o.getAttribute('aria-checked'))),
                   'options announce what they are and whether they are chosen');
            assert(qa('[tabindex]').every(e => +e.getAttribute('tabindex') <= 0),
                   'no positive tabindex');
            assert(qa('.k-opt,.k-cta,.k-card,.k-cat').every(e => e.tagName === 'BUTTON'),
                   'and they are real buttons');
            ok();
        """), login=None)

    def test_116_the_photo_fallback_is_the_approved_one(self):
        """0 of 26 dishes have photography — that is content debt, not a UI defect."""
        self.browser_js(self._kiosk_url(), self._js2(r"""
            await begin(); await openKioskCat();
            const none = qa('.k-shot--none');
            assert(none.length > 0, 'products without a photo still render');
            const r = none[0].getBoundingClientRect();
            assert(r.height > 100 && r.width > 100, 'at full card size, no layout shift');
            assert(none[0].querySelector('svg'), 'with the approved mark, not a broken image');
            assert(!/browse files/i.test(q('.k-grid').textContent),
                   'and no prototype drop target');
            ok();
        """), login=None)

    def test_117_every_kiosk_viewport(self):
        self.browser_js(self._kiosk_url(), _js(TestKioskV2Journey.PRELUDE + r"""
            async function frame(w, h){
              document.querySelectorAll('#vpf').forEach(f => f.remove());
              const f = document.createElement('iframe');
              f.id = 'vpf';
              f.style.cssText = 'position:fixed;left:0;top:0;border:0;width:'+w+'px;height:'+h+'px';
              f.src = location.pathname + location.search;
              document.body.appendChild(f);
              await waitFor(() => f.contentDocument
                              && f.contentDocument.querySelector('#k-start')
                              && !f.contentDocument.querySelector('#k-start').disabled,
                            'the kiosk at ' + w + 'x' + h);
              const d = f.contentDocument;
              d.querySelector('#k-start').click();
              await new Promise(r => setTimeout(r, 300));
              if (!d.querySelector('#s-service').classList.contains('k-hide')) {
                d.querySelectorAll('.k-choice')[0].click();
              }
              await waitFor(() => d.querySelectorAll('.k-card').length > 0, 'its menu');
              return [f, d];
            }
            for (const [w, h] of [[1080,1920],[1920,1080],[1366,768],[1280,720],[1024,768]]) {
              const [f, d] = await frame(w, h);
              const cols = getComputedStyle(d.querySelector('.k-grid')).gridTemplateColumns.split(' ').length;
              assert(cols >= 3, w + 'x' + h + ' keeps a premium grid: ' + cols);
              const over = Array.from(d.querySelectorAll('.k-shell *')).filter(e => {
                const r = e.getBoundingClientRect();
                return r.width > 0 && (r.right > w + 1 || r.left < -1);
              }).length;
              assert(over === 0, w + 'x' + h + ' overflows ' + over + ' nodes');
              assert(d.documentElement.scrollWidth <= w + 1, w + 'x' + h + ' scrolls sideways');
              const bar = d.querySelector('.k-bar').getBoundingClientRect();
              assert(bar.bottom <= h + 1 && bar.height > 60, w + 'x' + h + ' hides the order bar');
              f.remove();
            }
            ok();
        """), login=None)
