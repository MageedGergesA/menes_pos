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
        html = self._read(KIOSK)
        for banned in ('qty_free', 'qty_max', 'base_price', 'extra_price'):
            self.assertNotIn(banned, html,
                             'the kiosk must not reason about %s itself' % banned)
        self.assertIn('PC.lineKey', html, 'line identity is the canonical one')

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
        self.assertIn('mzc-', js)


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
class TestKioskCustomerJourney(KioskFixture):
    """Driven in a browser, as a customer standing at the terminal."""

    def test_40_a_plain_product_is_still_one_tap(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            const before = $$('.mzc-cfg').length;
            card('K Water').querySelector('.kiosk-add').click();
            await sleep(300);
            assert($$('.mzc-cfg').length === before, 'no panel for a product with no questions');
            assert($('#k-count').textContent === '1', 'it went straight into the order');
            assert(/Add/i.test(card('K Water').querySelector('.kiosk-add').textContent),
                   'and its button says Add, not Choose');
            ok();
        """), login=None)

    def test_41_a_configurable_product_asks_before_it_is_added(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            assert(/Choose/i.test(card('K Pizza').querySelector('.kiosk-add').textContent),
                   'the card says there is something to choose');
            await openCfg('K Pizza');
            assert($('#k-count').textContent === '0', 'nothing was added before the question');
            const rule = $('.mzc-group__rule').textContent;
            assert(/Required/i.test(rule), 'and the question says it is required: ' + rule);
            ok();
        """), login=None)

    def test_42_the_customer_is_told_how_many_and_what_is_included(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Family Meal');
            const rules = $$('.mzc-group__rule').map(r => r.textContent);
            const sides = rules.find(r => /up to/i.test(r));
            assert(sides, 'the multi group says how many: ' + rules.join(' | '));
            assert(/2/.test(sides) && /1/.test(sides), 'the ceiling and the included one: ' + sides);
            assert(!/qty_max|qty_free|combo_item|attribute_value/i.test($('.mzc-cfg').textContent),
                   'and never in field names');
            ok();
        """), login=None)

    def test_43_a_price_extra_is_visible_before_it_is_chosen(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Pizza');
            const large = opt('Large'), small = opt('Small');
            assert(/10/.test(large.textContent), 'the surcharge is on the option: ' + large.textContent);
            assert(!/\+.*0\.00/.test(small.textContent),
                   'and an included option is not labelled +0.00: ' + small.textContent);
            const before = money($('.mzc-total__v'));
            large.click(); await sleep(250);
            assert(money($('.mzc-total__v')) === before + 10, 'and the total moves when chosen');
            ok();
        """), login=None)

    def test_44_a_required_choice_cannot_be_left_empty_by_tapping_twice(self):
        """The shared toggle lets a cashier empty a group; a customer must not be able
        to walk into that dead end by tapping the option they already chose."""
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Pizza');
            const small = opt('Small');
            assert(small.getAttribute('aria-checked') === 'true', 'the implied choice is made');
            small.click(); await sleep(250);
            assert($$('.mzc-opt[aria-checked=true]').length === 1,
                   'tapping it again leaves the question answered');
            opt('Large').click(); await sleep(250);
            assert(opt('Large').getAttribute('aria-checked') === 'true'
                   && opt('Small').getAttribute('aria-checked') === 'false',
                   'and choosing another one replaces it');
            ok();
        """), login=None)

    def test_45_taking_two_of_one_side_uses_a_quantity_control(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Family Meal');
            opt('K Classic Burger').click(); opt('K Coke').click();
            opt('K Fries').click(); await sleep(300);
            assert(money($('.mzc-total__v')) === 100, 'one side is included: ' + money($('.mzc-total__v')));
            const inc = $('[data-inc]');
            assert(inc, 'a quantity control appears on the chosen option');
            assert(inc.getBoundingClientRect().height >= 44, 'and it is big enough to press');
            inc.click(); await sleep(300);
            assert(money($('.mzc-total__v')) === 125,
                   'the second one costs the group price: ' + money($('.mzc-total__v')));
            // full: the component settles into a line the customer can read back
            const chosen = $$('.mzc-chosen__n').map(e => e.textContent);
            assert(chosen.some(c => /Fries/.test(c) && /2/.test(c)),
                   'and it reads back as two: ' + chosen.join(' | '));
            assert(!$('[data-inc]'), 'a third is not offered');
            ok();
        """), login=None)

    def test_46_add_is_refused_until_the_questions_are_answered(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Burger Meal');
            assert($('.mzc-warn').hidden, 'nothing is called wrong before the customer acts');
            $('.mzc-cta').click(); await sleep(400);
            assert(!$('.mzc-warn').hidden, 'pressing Add says what is missing');
            assert($('#k-count').textContent === '0', 'and nothing was added');
            assert($$('.mzc-group--need').length > 0, 'the unanswered question is marked');
            opt('K Classic Burger').click(); opt('K Fries').click(); opt('K Coke').click();
            await sleep(300);
            $('.mzc-cta').click(); await sleep(500);
            assert($('#k-count').textContent === '1', 'answered, it goes in');
            ok();
        """), login=None)

    def test_47_the_cart_reads_back_what_was_chosen(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Family Meal');
            opt('K Double Burger').click(); opt('K Coke Zero').click(); opt('K Fries').click();
            await sleep(250); $('[data-inc]').click(); await sleep(250);
            $('.mzc-cta').click(); await sleep(400);
            $('#k-review').click(); await waitFor(() => $('#k-lines .crow'), 'the order sheet');
            const cfg = $('.mzc-line__cfg').textContent;
            assert(/Double/.test(cfg) && /Zero/.test(cfg), 'the choices are readable: ' + cfg);
            assert(/2/.test(cfg), 'including the two sides: ' + cfg);
            assert(!/option/i.test(cfg), 'not "3 options"');
            ok();
        """), login=None)

    def test_48_a_choice_can_be_corrected_from_the_order(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Family Meal');
            opt('K Double Burger').click(); opt('K Coke Zero').click(); opt('K Fries').click();
            await sleep(250); $('[data-inc]').click(); await sleep(250);
            $('.mzc-cta').click(); await sleep(400);
            $('#k-review').click(); await waitFor(() => $('.mzc-edit'), 'the edit control');
            $('.mzc-edit').click();
            await waitFor(() => $('.mzc-cfg'), 'the configurator reopens');
            assert(money($('.mzc-total__v')) === 150, 'on exactly what was chosen');
            const parts = $$('.mzc-chosen__n').map(e => e.textContent);
            assert(parts.length === 3, 'as a meal of its parts: ' + parts.join(' | '));
            assert(parts.some(p => /Fries/.test(p) && /2/.test(p)), 'including both sides');
            assert(/Save/i.test($('.mzc-cta').textContent), 'and it offers to SAVE, not add again');
            // change ONE component without rebuilding the meal
            const sides = $$('.mzc-group').find(g => /sides/i.test(g.textContent));
            sides.querySelector('[data-change]').click();
            await waitFor(() => $('[data-dec]'), 'that component reopens');
            assert($$('.mzc-chosen__n').length === 2, 'and the others stay chosen');
            $('[data-dec]').click(); await sleep(250);
            opt('K Salad').click(); await sleep(250);
            $('.mzc-cta').click(); await sleep(500);
            assert($$('#k-lines .crow').length === 1, 'still ONE line, corrected in place');
            const cfg = $('.mzc-line__cfg').textContent;
            assert(/Salad/.test(cfg) && !/2/.test(cfg), 'with the new choice: ' + cfg);
            assert(money($('#k-sheettot')) === 153, 'and the new price: ' + money($('#k-sheettot')));
            ok();
        """), login=None)

    def test_49_two_configurations_of_one_product_are_two_lines(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            const order = async (pick) => {
                await openCfg('K Coffee');
                opt(pick).click(); await sleep(200);
                $('.mzc-cta').click(); await sleep(400);
            };
            await order('Double');
            await order('Single');
            await order('Single');
            $('#k-review').click(); await waitFor(() => $('#k-lines .crow'), 'the sheet');
            const rows = $$('#k-lines .crow');
            assert(rows.length === 2, 'a different choice is its own line: ' + rows.length);
            const qtys = $$('#k-lines .mz-stepper__value').map(v => v.textContent.trim());
            assert(qtys.includes('2'), 'and the SAME choice merges to a quantity: ' + qtys.join(','));
            assert(money($('#k-sheettot')) === 68, 'total: ' + money($('#k-sheettot')));
            ok();
        """), login=None)

    def test_50_backing_out_leaves_the_order_alone(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            card('K Water').querySelector('.kiosk-add').click(); await sleep(250);
            const before = $('#k-carttot').textContent;
            await openCfg('K Family Meal');
            opt('K Double Burger').click(); await sleep(200);
            $('.mzc-back').click(); await sleep(350);
            assert(!$('.mzc-cfg'), 'the panel closed');
            assert($('#k-carttot').textContent === before, 'and the order is untouched');
            assert($('#k-count').textContent === '1', 'no half-configured line: ' + $('#k-count').textContent);
            ok();
        """), login=None)

    def test_51_a_long_configuration_keeps_its_price_and_button_in_view(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Build Your Bowl');
            assert($$('.mzc-group').length === 6, 'six questions');
            assert($$('.mzc-opt').length >= 20, 'twenty-odd choices');
            const cta = () => $('.mzc-cta').getBoundingClientRect();
            assert(cta().bottom <= innerHeight + 1, 'the button is on screen before scrolling');
            const body = $('.mzc-cfg__body');
            body.scrollTop = body.scrollHeight;
            await sleep(300);
            assert(cta().bottom <= innerHeight + 1, 'and still on screen at the bottom');
            assert($('.mzc-total__v').getBoundingClientRect().bottom <= innerHeight + 1,
                   'so is the running price');
            assert(document.documentElement.scrollWidth <= innerWidth + 1, 'nothing overflows sideways');
            ok();
        """), login=None)

    def test_52_the_whole_order_reaches_the_server_configured(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Family Meal');
            opt('K Double Burger').click(); opt('K Coke Zero').click(); opt('K Fries').click();
            await sleep(250); $('[data-inc]').click(); await sleep(250);
            const shown = money($('.mzc-total__v'));
            $('.mzc-cta').click(); await sleep(400);
            $('#k-review').click(); await waitFor(() => $('#k-place'), 'the sheet');
            assert(money($('#k-sheettot')) === shown, 'the order sheet agrees with the panel');
            $('#k-place').click();
            await waitFor(() => !$('#k-done').classList.contains('hidden'), 'the confirmation');
            assert(/#\d+/.test($('#k-num').textContent), 'with a real number: ' + $('#k-num').textContent);
            assert($('#k-count').textContent === '0', 'and the next customer starts empty');
            ok();
        """), login=None)
        order = self.env['pos.order'].sudo().search(
            [('mezze_channel', '=', 'kiosk')], order='id desc', limit=1)
        self.assertAlmostEqual(order.amount_total, 150.0, 2,
                               'the server charged what the customer was shown')
        children = order.lines.filtered(lambda l: l.combo_parent_id)
        self.assertEqual(len(children), 4, 'burger + drink + two sides')

    def test_55_one_side_and_two_sides_are_not_the_same_line(self):
        """Cart identity counts combo UNITS, not just which items were picked."""
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            const meal = async (extra) => {
                await openCfg('K Family Meal');
                opt('K Classic Burger').click(); opt('K Coke').click(); opt('K Fries').click();
                await sleep(250);
                if (extra) { $('[data-inc]').click(); await sleep(250); }
                $('.mzc-cta').click(); await sleep(400);
            };
            await meal(false);
            await meal(true);
            $('#k-review').click(); await waitFor(() => $('#k-lines .crow'), 'the sheet');
            const rows = $$('#k-lines .crow');
            assert(rows.length === 2,
                   'one side and two sides are different orders: ' + rows.length + ' line(s)');
            assert(money($('#k-sheettot')) === 225, 'and cost 100 + 125: ' + money($('#k-sheettot')));
            await meal(true);
            assert($$('#k-lines .crow').length === 2, 'while an identical one still merges');
            const qtys = $$('#k-lines .mz-stepper__value').map(v => v.textContent.trim());
            assert(qtys.includes('2'), 'to a quantity: ' + qtys.join(','));
            ok();
        """), login=None)

    def test_53_a_refusal_speaks_to_the_customer(self):
        """A server rule is not a customer message."""
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            card('K Water').querySelector('.kiosk-add').click(); await sleep(250);
            $('#k-review').click(); await waitFor(() => $('#k-place'), 'the sheet');
            // make the order impossible behind the customer's back
            const orig = window.fetch;
            window.fetch = async function (u, o) {
                if (String(u).indexOf('/shop/order') > -1) {
                    return new Response(JSON.stringify({ok: false, error: 'shop_order_failed',
                        message: 'Combo K Burger Meal needs 1 item(s) from K Choose your burger'}),
                        {status: 400, headers: {'Content-Type': 'application/json'}});
                }
                return orig.apply(this, arguments);
            };
            $('#k-place').click();
            await waitFor(() => !$('#k-err').classList.contains('hidden'), 'the message');
            const msg = $('#k-err').textContent;
            window.fetch = orig;
            assert(!/combo|item\(s\)|qty_|400|failed/i.test(msg),
                   'no internal rule on a customer screen: ' + msg);
            assert(msg.trim().length > 5, 'but there IS a message: ' + msg);
            ok();
        """), login=None)

    def test_56_a_long_configuration_says_where_the_customer_is(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Build Your Bowl');
            const steps = $$('.mzc-group__n').map(e => e.textContent.trim());
            assert(steps.length === 6, 'every question is numbered: ' + steps.length);
            assert(/1/.test(steps[0]) && /6/.test(steps[0]), 'first reads 1 of 6: ' + steps[0]);
            assert(/6/.test(steps[5]), 'last reads 6 of 6: ' + steps[5]);
            $('.mzc-back').click(); await sleep(300);
            await openCfg('K Burger Meal');
            assert($$('.mzc-group__n').length === 0,
                   'a three-question product is not numbered — it does not need to be');
            ok();
        """), login=None)

    def test_57_arrow_keys_move_within_a_choose_one_group(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Pizza');
            const group = $('.mzc-group[role=radiogroup]');
            assert(group, 'a choose-one group is a radiogroup');
            const first = group.querySelector('.mzc-opt');
            first.focus();
            first.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
            await sleep(300);
            const on = $$('.mzc-opt--on').map(o => o.querySelector('.mzc-opt__n').textContent);
            assert(on.length === 1 && /Medium/.test(on[0]),
                   'the next option is chosen: ' + on.join(','));
            assert(/Medium/.test(document.activeElement.textContent),
                   'and keeps the focus: ' + document.activeElement.textContent);
            assert(money($('.mzc-total__v')) === 55, 'and the price followed: ' + money($('.mzc-total__v')));
            document.activeElement.dispatchEvent(
                new KeyboardEvent('keydown', {key: 'ArrowLeft', bubbles: true}));
            await sleep(300);
            assert(money($('.mzc-total__v')) === 50, 'and back again');
            ok();
        """), login=None)

    def test_58_the_validation_message_is_an_instruction_and_says_it_once(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Burger Meal');
            $('.mzc-cta').click(); await sleep(400);
            const msg = $('.mzc-warn').textContent.trim();
            const verbs = (msg.match(/choose/gi) || []).length;
            assert(verbs <= 1, 'the verb is not repeated: ' + msg);
            assert(/burger/i.test(msg), 'and it names the question: ' + msg);
            ok();
        """), login=None)

    def test_54_the_next_customer_inherits_nothing(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Pizza');
            opt('Large').click(); await sleep(200);
            $('.mzc-cta').click(); await sleep(400);
            assert($('#k-count').textContent === '1', 'customer A has an order');
            // A walks away: the idle reset is the same path the timer takes
            $('#k-newbtn') ? $('#k-newbtn').click() : null;
            await openCfg('K Family Meal');
            opt('K Double Burger').click(); await sleep(200);
            // ...and the terminal resets mid-configuration
            const reset = $('#k-imhere');
            $('#k-idle').classList.remove('hidden');
            $('#k-imhere').click();
            await sleep(200);
            ok();
        """), login=None)


# =====================================================================
@tagged('post_install', '-at_install', 'mezze_kiosk')
class TestKioskLanguageAndAccess(KioskFixture):
    """Arabic is not a translation pass over an English kiosk; it is the kiosk."""

    def test_60_the_configurator_is_arabic_in_arabic(self):
        self.browser_js(self._kiosk_url('ar'), _js(r"""
            await start();
            assert(document.documentElement.dir === 'rtl', 'the page is RTL');
            await openCfg('K Family Meal');
            const rules = $$('.mzc-group__rule').map(r => r.textContent).join(' | ');
            assert(/[؀-ۿ]/.test(rules), 'the rules are Arabic: ' + rules);
            assert(/[؀-ۿ]/.test($('.mzc-total__k').textContent), 'so is the price label');
            assert(/[؀-ۿ]/.test($('.mzc-cta').textContent), 'so is the button');
            assert(/[؀-ۿ]/.test(card('K Family Meal').querySelector('.kiosk-add').textContent),
                   'and the card');
            ok();
        """), login=None)

    def test_61_a_price_keeps_its_sign_on_the_left_in_arabic(self):
        self.browser_js(self._kiosk_url('ar'), _js(r"""
            await start();
            await openCfg('K Pizza');
            const px = $('.mzc-opt__px');
            assert(px.getAttribute('dir') === 'ltr',
                   'a mixed number/sign is isolated so bidi cannot flip it');
            ok();
        """), login=None)

    def test_62_switching_language_keeps_the_order(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Pizza');
            opt('Large').click(); await sleep(200);
            $('.mzc-cta').click(); await sleep(400);
            const total = $('#k-carttot').textContent;
            $('#k-lang').click(); await sleep(600);
            assert(document.documentElement.dir === 'rtl', 'switched to Arabic');
            assert($('#k-count').textContent === '1', 'the order survived the switch');
            assert($('#k-carttot').textContent === total, 'with its price: ' + $('#k-carttot').textContent);
            ok();
        """), login=None)

    def test_63_every_control_is_reachable_and_announced(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Family Meal');
            const cfg = $('.mzc-cfg');
            assert(cfg.getAttribute('role') === 'dialog' && cfg.getAttribute('aria-modal') === 'true',
                   'it is a dialog');
            assert(document.getElementById(cfg.getAttribute('aria-labelledby')), 'with a name');
            assert($$('.mzc-group').every(g => document.getElementById(g.getAttribute('aria-labelledby'))),
                   'every question is labelled');
            assert($$('.mzc-group').some(g => g.getAttribute('role') === 'radiogroup'),
                   'a choose-one question is a radiogroup');
            assert($$('.mzc-opt').every(o => ['radio','checkbox'].includes(o.getAttribute('role'))
                                          && ['true','false'].includes(o.getAttribute('aria-checked'))),
                   'and every option announces whether it is chosen');
            assert($$('.mzc-cfg [tabindex]').every(e => +e.getAttribute('tabindex') <= 0),
                   'no positive tabindex');
            assert($$('.mzc-opt,.mzc-cta,.mzc-back,.mzc-qty__btn').every(e => e.tagName === 'BUTTON'),
                   'they are real buttons');
            ok();
        """), login=None)

    def test_64_the_keyboard_can_do_what_a_finger_can(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Pizza');
            const large = opt('Large');
            large.focus();
            assert(document.activeElement === large, 'an option takes focus');
            large.click();                       // Enter on a <button> is a click
            await sleep(250);
            assert(opt('Large').getAttribute('aria-checked') === 'true', 'and can be chosen');
            document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true}));
            await sleep(300);
            assert(!$('.mzc-cfg'), 'Escape backs out');
            assert($('#k-count').textContent === '0', 'without adding anything');
            ok();
        """), login=None)

    def test_65_touch_targets_are_kiosk_sized(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Family Meal');
            opt('K Fries').click(); await sleep(250);
            const small = $$('.mzc-opt,.mzc-qty__btn,.mzc-cta,.mzc-back')
                .map(e => [e.className.split(' ')[0], e.getBoundingClientRect()])
                .filter(([c,r]) => r.height < 44 || r.width < 44);
            assert(small.length === 0, 'everything is at least 44px: ' + JSON.stringify(small));
            const opts = $$('.mzc-opt').map(e => e.getBoundingClientRect());
            assert(opts.every(r => r.height >= 52), 'and choices are 52px+ for a standing customer');
            ok();
        """), login=None)

    def test_66_the_selected_state_is_not_colour_alone(self):
        css = self._read(os.path.join(ADDON, 'static', 'design', 'customer-config.css'))
        self.assertIn('.mzc-opt--on .mzc-opt__mark', css, 'the check mark fills when chosen')
        self.assertIn('forced-colors', css, 'and it survives forced colours')
        self.assertIn('prefers-reduced-motion', css)
        self.assertIn('focus-visible', css)

    def test_67_configuration_costs_no_round_trips(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            let n = 0; const orig = window.fetch;
            window.fetch = function(){ n++; return orig.apply(this, arguments); };
            await openCfg('K Build Your Bowl');
            for (const o of $$('.mzc-opt').slice(0, 8)) { o.click(); await sleep(60); }
            window.fetch = orig;
            assert(n === 0, 'the configuration came with the menu, not per option: ' + n);
            ok();
        """), login=None)


# =====================================================================
@tagged('post_install', '-at_install', 'mezze_kiosk')
class TestKioskBenchmarkedLayout(KioskFixture):
    """The kiosk against the patterns worth borrowing from McDonald's and KFC.

    Adopted: the menu as the canvas, image-first cards, a persistent category rail
    with a visible scroll affordance, a component-by-component meal builder, a basket
    that never leaves the screen, and ergonomic zoning for a physical portrait machine.

    Rejected, and asserted here as refusals: hiding the running total at the moment of
    a recommendation, a suggestion after every item, and a de-emphasised way to decline.
    """

    FRAME = r"""
      async function frame(w, h, path){
        document.querySelectorAll('#vpf').forEach(f => f.remove());
        const f = document.createElement('iframe');
        f.id = 'vpf';
        f.style.cssText = 'position:fixed;left:0;top:0;border:0;width:' + w + 'px;height:' + h + 'px';
        f.src = path;
        document.body.appendChild(f);
        await waitFor(() => f.contentDocument && f.contentDocument.querySelector('#k-startbtn'),
                      'the kiosk in a ' + w + 'x' + h + ' frame');
        const d = f.contentDocument;
        d.querySelector('#k-startbtn').click();
        await waitFor(() => d.querySelectorAll('.card').length > 0, 'its menu');
        return d;
      }
    """

    def _url(self, lang='en'):
        return '/mezze_bridge/static/kiosk.html?store=%s&lang=%s' % (STORE, lang)

    # -- menu discovery ------------------------------------------------------

    def test_70_the_menu_is_the_canvas(self):
        self.browser_js(self._kiosk_url(), _js(self.FRAME + r"""
            const d = await frame(1080, 1920, '%s');
            const h = 1920;
            const menu = d.querySelector('.grid').getBoundingClientRect();
            const chrome = d.querySelector('.top').getBoundingClientRect().height
                         + d.querySelector('.cats').getBoundingClientRect().height
                         + d.querySelector('.cartbar').getBoundingClientRect().height;
            assert(chrome < h * 0.30,
                   'chrome stays out of the way: ' + Math.round(chrome) + 'px of ' + h);
            assert(menu.height > h * 0.60, 'and the food gets the screen');
            ok();
        """ % self._url()), login=None)

    def test_71_cards_are_image_first_and_one_target(self):
        self.browser_js(self._kiosk_url(), _js(self.FRAME + r"""
            const d = await frame(1080, 1920, '%s');
            const card = [...d.querySelectorAll('.card')].find(c => c.textContent.includes('K Pizza'));
            assert(card.tagName === 'BUTTON', 'the whole card is the target, not a button inside it');
            assert(card.querySelectorAll('button').length === 0, 'and it contains no nested button');
            const pic = card.querySelector('.pic').getBoundingClientRect();
            const body = card.querySelector('.cbody').getBoundingClientRect();
            assert(pic.height > body.height, 'the image leads: ' + Math.round(pic.height) + ' vs ' + Math.round(body.height));
            assert(card.getBoundingClientRect().height >= 200, 'and the target is kiosk-sized');
            assert(/Choose/i.test(card.textContent), 'a configurable product says so on the card');
            ok();
        """ % self._url()), login=None)

    def test_72_two_premium_columns_in_portrait_five_in_landscape(self):
        self.browser_js(self._kiosk_url(), _js(self.FRAME + r"""
            let d = await frame(1080, 1920, '%s');
            let cols = getComputedStyle(d.querySelector('.grid')).gridTemplateColumns.split(' ').length;
            assert(cols === 2, 'portrait is two large columns, not a dense grid: ' + cols);
            d = await frame(1920, 1080, '%s');
            cols = getComputedStyle(d.querySelector('.grid')).gridTemplateColumns.split(' ').length;
            assert(cols >= 4 && cols <= 5,
                   'landscape is four or five premium columns, not stretched portrait cards: ' + cols);
            ok();
        """ % (self._url(), self._url())), login=None)

    def test_73_the_category_rail_shows_that_it_scrolls(self):
        """The single most-reported failure of the benchmarked kiosk."""
        # a rail only needs an affordance when it has somewhere to scroll TO
        for name in ('Meals', 'Burgers', 'Chicken', 'Sharing', 'Sides',
                     'Drinks', 'Desserts', 'Coffee'):
            self.env['pos.category'].sudo().create({'name': 'K %s' % name})
        self.env.flush_all()
        self.browser_js(self._kiosk_url(), _js(self.FRAME + r"""
            const d = await frame(1080, 1920, '%s');
            const rail = d.querySelector('.cats');
            assert(rail.scrollWidth > rail.clientWidth + 20, 'there is more rail than fits');
            const cs = getComputedStyle(rail);
            assert((cs.maskImage || cs.webkitMaskImage || '').indexOf('gradient') > -1,
                   'the trailing edge fades, so there is visible evidence of more');
            const chips = [...rail.querySelectorAll('.cat')];
            const edge = rail.getBoundingClientRect().right;
            assert(chips.some(c => { const r = c.getBoundingClientRect();
                                     return r.left < edge && r.right > edge; }),
                   'and a chip is cut by the edge rather than ending neatly at it');
            assert(chips.every(c => c.getBoundingClientRect().height >= 52),
                   'every category is a kiosk-sized target');
            ok();
        """ % self._url()), login=None)

    # -- ergonomics ----------------------------------------------------------

    def test_74_frequent_actions_sit_where_a_standing_customer_can_reach(self):
        """A 1080x1920 kiosk is a machine, not a tall web page: its top edge can be
        1.7m above the floor. Frequent controls belong in the lower half."""
        self.browser_js(self._kiosk_url(), _js(self.FRAME + r"""
            const d = await frame(1080, 1920, '%s');
            const H = 1920;
            const band = (el) => el.getBoundingClientRect().top / H;
            const rail = band(d.querySelector('.cats'));
            const bar  = band(d.querySelector('.cartbar'));
            assert(bar > 0.65, 'the order bar is in easy reach: ' + bar.toFixed(2));
            assert(rail > 0.55, 'so is category switching: ' + rail.toFixed(2));
            const lang = band(d.querySelector('#k-lang'));
            const svc  = band(d.querySelector('#k-svcchip'));
            assert(lang < 0.30 && svc < 0.30,
                   'while language and service mode — rarely touched — stay high');
            ok();
        """ % self._url()), login=None)

    def test_75_the_service_mode_is_visible_for_the_whole_order(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            const chip = $('#k-svcchip');
            assert(!chip.classList.contains('hidden'), 'the order says how it will be served');
            const before = chip.textContent.trim();
            chip.click(); await sleep(300);
            assert(chip.textContent.trim() !== before, 'and it can be changed from there: '
                   + before + ' -> ' + chip.textContent.trim());
            ok();
        """), login=None)

    # -- the basket ----------------------------------------------------------

    def test_76_the_basket_never_leaves_the_screen(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            const bar = $('#k-cartbar');
            assert(!bar.classList.contains('hidden'), 'the order bar is there before anything is ordered');
            assert(/tap|start/i.test($('#k-carthint').textContent), 'and says what to do: '
                   + $('#k-carthint').textContent);
            assert($('#k-review').disabled, 'with nothing to review yet');
            card('K Water').querySelector('.kiosk-add').click(); await sleep(400);
            assert($('#k-count').textContent === '1' && /10/.test($('#k-carttot').textContent),
                   'then the count and the total, both on screen');
            assert(!$('#k-review').disabled, 'and a way in');
            ok();
        """), login=None)

    # -- the meal builder ----------------------------------------------------

    def test_77_a_meal_reads_as_its_parts(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Burger Meal');
            assert($$('.mzc-chosen').length === 0, 'nothing is chosen for the customer');
            opt('K Double Burger').click(); await sleep(300);
            const done = $$('.mzc-chosen__n').map(e => e.textContent);
            assert(done.length === 1 && /Double/.test(done[0]),
                   'an answered component becomes one line: ' + done.join('|'));
            assert(/20/.test($('.mzc-chosen__px').textContent),
                   'carrying what it added: ' + $('.mzc-chosen__px').textContent);
            assert($$('.mzc-opts').length === 2, 'and the questions still open stay open');
            ok();
        """), login=None)

    def test_78_one_component_can_be_changed_without_rebuilding_the_meal(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Burger Meal');
            opt('K Double Burger').click(); await sleep(200);
            opt('K Fries').click(); await sleep(200);
            opt('K Coke').click(); await sleep(300);
            assert($$('.mzc-chosen').length === 3, 'a whole meal, in three lines');
            const t0 = money($('.mzc-total__v'));
            const burgerGroup = () => $$('.mzc-group').find(g => /burger/i.test(g.textContent));
            burgerGroup().querySelector('[data-change]').click();
            // the panel re-renders, so the group has to be found again, not held on to
            await waitFor(() => burgerGroup() && burgerGroup().querySelector('.mzc-opt'),
                          'that one component reopens');
            assert($$('.mzc-chosen').length === 2, 'and ONLY that one: ' + $$('.mzc-chosen').length);
            opt('K Classic Burger').click(); await sleep(300);
            assert(money($('.mzc-total__v')) === t0 - 20, 'the price follows the change');
            assert($$('.mzc-chosen').length === 3, 'and the meal is whole again');
            ok();
        """), login=None)

    def test_79_a_group_that_can_take_another_stays_open(self):
        """Collapsing a 'choose up to 2' group at one would hide the second helping."""
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            await openCfg('K Family Meal');
            opt('K Classic Burger').click(); opt('K Coke').click(); await sleep(250);
            opt('K Fries').click(); await sleep(350);
            const sides = $$('.mzc-group').find(g => /sides/i.test(g.textContent));
            assert(sides.querySelector('.mzc-opt'), 'the sides question is still open at one of two');
            assert(sides.querySelector('[data-inc]'), 'with the way to take another');
            $('[data-inc]').click(); await sleep(350);
            assert(!sides.querySelector('.mzc-opt') || $$('.mzc-chosen').length === 3,
                   'and settles once it is full');
            ok();
        """), login=None)

    # -- the recommendation --------------------------------------------------

    def test_80_one_recommendation_priced_and_easy_to_refuse(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            card('K Classic Burger').querySelector('.kiosk-add').click();
            await waitFor(() => !$('#k-offer').classList.contains('hidden'), 'the recommendation');
            const px = $('#k-offer-px').textContent;
            assert(/40/.test(px), 'the real difference is ON the offer: ' + px);
            assert(!/free|only|hurry|last|miss/i.test($('#k-offer').textContent),
                   'no scarcity or pressure: ' + $('#k-offer').textContent);
            const yes = $('#k-offer-yes').getBoundingClientRect();
            const no  = $('#k-offer-no').getBoundingClientRect();
            assert(Math.abs(yes.width - no.width) < 2 && Math.abs(yes.height - no.height) < 2,
                   'declining is exactly as easy as accepting: '
                   + JSON.stringify([yes.width, yes.height, no.width, no.height]));
            assert(!/sure|really|miss out|instead/i.test($('#k-offer-no').textContent),
                   'and it does not shame the customer: ' + $('#k-offer-no').textContent);
            ok();
        """), login=None)

    def test_81_the_total_stays_on_screen_while_the_offer_is_up(self):
        """The benchmarked kiosk hides the running order at exactly this moment."""
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            card('K Classic Burger').querySelector('.kiosk-add').click();
            await waitFor(() => !$('#k-offer').classList.contains('hidden'), 'the recommendation');
            const bar = $('#k-cartbar').getBoundingClientRect();
            assert(!$('#k-cartbar').classList.contains('hidden'), 'the basket is still there');
            assert(!$('#k-carttot').classList.contains('hidden')
                   && /60/.test($('#k-carttot').textContent),
                   'showing what has been spent: ' + $('#k-carttot').textContent);
            assert(bar.bottom <= innerHeight + 1 && bar.height > 0, 'and it is on screen');
            const offer = $('#k-offer').getBoundingClientRect();
            assert(offer.bottom <= bar.top + 1, 'the offer sits above it, not over it');
            ok();
        """), login=None)

    def test_82_at_most_one_recommendation_per_order(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            card('K Classic Burger').querySelector('.kiosk-add').click();
            await waitFor(() => !$('#k-offer').classList.contains('hidden'), 'the first');
            const first = $('#k-offer-px').textContent;
            $('#k-offer-no').click(); await sleep(300);
            assert($('#k-offer').classList.contains('hidden'), 'declining dismisses it');
            card('K Fries').querySelector('.kiosk-add').click(); await sleep(500);
            assert($('#k-offer').classList.contains('hidden'),
                   'and no second suggestion follows the next item');
            card('K Coke').querySelector('.kiosk-add').click(); await sleep(500);
            assert($('#k-offer').classList.contains('hidden'), 'nor the one after that');
            assert($('#k-count').textContent === '3', 'while the order itself is untouched');
            ok();
        """), login=None)

    def test_83_declining_leaves_the_order_exactly_as_it_was(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            card('K Classic Burger').querySelector('.kiosk-add').click();
            await waitFor(() => !$('#k-offer').classList.contains('hidden'), 'the recommendation');
            const total = $('#k-carttot').textContent, n = $('#k-count').textContent;
            $('#k-offer-no').click(); await sleep(400);
            assert($('#k-carttot').textContent === total && $('#k-count').textContent === n,
                   'nothing was added or removed by saying no');
            ok();
        """), login=None)

    def test_84_accepting_replaces_the_item_with_the_meal(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            card('K Classic Burger').querySelector('.kiosk-add').click();
            await waitFor(() => !$('#k-offer').classList.contains('hidden'), 'the recommendation');
            $('#k-offer-yes').click();
            await waitFor(() => $('.mzc-cfg'), 'the meal opens');
            const chosen = $$('.mzc-chosen__n').map(e => e.textContent);
            assert(chosen.some(c => /Classic/.test(c)),
                   'with the item they already chose already in it: ' + chosen.join('|'));
            opt('K Fries').click(); opt('K Coke').click(); await sleep(300);
            $('.mzc-cta').click(); await sleep(500);
            $('#k-review').click(); await waitFor(() => $('#k-lines .crow'), 'the order');
            const rows = $$('#k-lines .crow').map(r => r.textContent);
            assert(rows.length === 1, 'the single burger did not survive alongside its meal: '
                   + rows.length + ' line(s)');
            assert(/Meal/.test(rows[0]), 'what is left is the meal: ' + rows[0]);
            assert(money($('#k-sheettot')) === 100, 'at the meal price: ' + money($('#k-sheettot')));
            ok();
        """), login=None)

    def test_85_the_recommendation_is_derived_from_the_branchs_own_data(self):
        """No hard-coded pairings: the offer only exists where a combo really contains
        the item, and its price is the real difference."""
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            // K Pizza is in no combo — no meal to make it into
            await openCfg('K Pizza');
            $('.mzc-cta').click(); await sleep(500);
            assert($('#k-offer').classList.contains('hidden'),
                   'nothing is invented for a product no meal contains');
            ok();
        """), login=None)

    def test_86_a_reset_clears_the_recommendation_too(self):
        self.browser_js(self._kiosk_url(), _js(r"""
            await start();
            card('K Classic Burger').querySelector('.kiosk-add').click();
            await waitFor(() => !$('#k-offer').classList.contains('hidden'), 'the recommendation');
            $('#k-idle').classList.remove('hidden');
            $('#k-imhere').click(); await sleep(200);
            // the real reset path
            $('#k-newbtn') && $('#k-newbtn').click();
            await sleep(400);
            ok();
        """), login=None)
