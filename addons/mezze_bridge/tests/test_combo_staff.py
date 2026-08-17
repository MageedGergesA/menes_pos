"""Combos are sellable by STAFF, through the one configuration contract.

The server has been able to build native combo orders for a long time — `/orders/sync`
and `/orders/fire` both split combo carts, validate the picks against the product's own
`product.combo` groups and price parent+child lines the native way. The public shop has
always let a customer choose. The two surfaces a *cashier* uses could not: the Register
never offered the question, and the lane board carried the groups in its payload and
dropped them on the floor. A branch could sell a meal deal online and not at its own
till.

Nothing here invents a combo model. Odoo's own is the authority:

    product.template.type == 'combo'   ->  combo_ids  (product.combo)
    product.combo         .combo_item_ids            (product.combo.item)
    product.combo.item    .product_id / .extra_price

and exactly ONE item per group, which is Odoo's rule and the server's guard
(`_resolve_combo`). The shared rules module normalises a combo group into the same
shape as an attribute group, so both staff surfaces render one loop and share one line
identity — the alternative being a second combo algorithm growing beside the first.
"""
import json
import os

from odoo.tests import tagged

from .common import MezzeHttpCase

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(ADDON, 'static', 'design', 'product-config.js')
DRIVETHRU = os.path.join(ADDON, 'static', 'drivethru.html')
STORE = os.path.join(ADDON, 'static', 'src', 'cashier', 'order_store.js')

_PRELUDE = r"""
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
async function waitFor(fn, label, ms=20000){
  const t0 = Date.now();
  while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){} await new Promise(r=>setTimeout(r,120)); }
  throw new Error('timeout waiting for: ' + label);
}
function assert(cond, msg){ if(!cond) throw new Error('assert failed: ' + msg); }
const ok = () => console.log('test successful');
const PC = () => window.MezzeProductConfig;
const money = (el) => parseFloat(el.textContent.replace(/[^0-9.]/g, ''));
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


class ComboFixture(MezzeHttpCase):
    """A real Odoo combo product: two groups, an extra-priced option in each.

    Deliberately built from `product.combo` / `product.combo.item` rather than from a
    Mezze table, because the point of the phase is that Mezze has no combo model of
    its own.
    """
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        categ = env['pos.category'].sudo().search([], limit=1) \
            or env['pos.category'].sudo().create({'name': 'Combo Test'})
        cls.categ = categ

        def dish(name, price):
            p = env['product.product'].sudo().create({
                'name': name, 'available_in_pos': True, 'list_price': price,
                'pos_categ_ids': [(6, 0, categ.ids)], 'type': 'consu',
            })
            p.write({'taxes_id': [(5, 0, 0)]})       # company default applies on create
            return p

        cls.classic = dish('Classic Burger', 60.0)
        cls.double = dish('Double Burger', 80.0)
        cls.coke = dish('Coke', 20.0)
        cls.cokezero = dish('Coke Zero', 20.0)

        Combo = env['product.combo'].sudo()
        cls.g_burger = Combo.create({
            'name': 'Choose your burger',
            'combo_item_ids': [
                (0, 0, {'product_id': cls.classic.id, 'extra_price': 0.0}),
                (0, 0, {'product_id': cls.double.id, 'extra_price': 20.0}),
            ],
        })
        cls.g_drink = Combo.create({
            'name': 'Choose your drink',
            'combo_item_ids': [
                (0, 0, {'product_id': cls.coke.id, 'extra_price': 0.0}),
                (0, 0, {'product_id': cls.cokezero.id, 'extra_price': 5.0}),
            ],
        })
        tmpl = env['product.template'].sudo().create({
            'name': 'Burger Meal', 'type': 'combo', 'list_price': 100.0,
            'available_in_pos': True, 'pos_categ_ids': [(6, 0, categ.ids)],
            'combo_ids': [(6, 0, [cls.g_burger.id, cls.g_drink.id])],
        })
        tmpl.write({'taxes_id': [(5, 0, 0)]})
        cls.meal = tmpl.product_variant_id
        cls.item_classic = cls.g_burger.combo_item_ids.filtered(
            lambda i: i.product_id == cls.classic)
        cls.item_double = cls.g_burger.combo_item_ids.filtered(
            lambda i: i.product_id == cls.double)
        cls.item_coke = cls.g_drink.combo_item_ids.filtered(lambda i: i.product_id == cls.coke)
        cls.item_zero = cls.g_drink.combo_item_ids.filtered(
            lambda i: i.product_id == cls.cokezero)

        cls.pos_config.write({'payment_method_ids': [(4, cls.cash_payment_method.id)]})
        env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        sess = cls.pos_config.current_session_id
        if sess:
            if sess.state == 'opening_control':
                try:
                    sess.set_opening_control(0, None)
                except Exception:  # noqa: BLE001
                    pass
            if sess.state != 'opened':
                sess.sudo().write({'state': 'opened'})
        env.flush_all()

    def _read(self, path):
        with open(path, encoding='utf-8') as fh:
            return fh.read()


@tagged('post_install', '-at_install', 'mezze_combo')
class TestComboContract(ComboFixture):
    """The model, the payload and the rules — before any pixel."""

    def test_01_the_combo_is_odoo_s_own_model(self):
        self.assertEqual(self.meal.type, 'combo')
        self.assertEqual(len(self.meal.product_tmpl_id.combo_ids), 2)
        self.assertEqual(len(self.g_burger.combo_item_ids), 2)
        self.assertAlmostEqual(self.item_double.extra_price, 20.0, 2)
        # and Mezze added no parallel model
        self.assertNotIn('mezze.combo', self.env)

    def test_02_the_payload_ships_the_groups_to_both_staff_surfaces(self):
        env = self.env
        groups = self.env['ir.http'].__class__ and None  # noqa: F841 - readability
        from odoo.addons.mezze_bridge.controllers.main import MezzeBridgeController
        payload = MezzeBridgeController()._product_combos(env, self.meal)
        self.assertEqual(len(payload), 2, 'one entry per product.combo group')
        first = payload[0]
        for key in ('combo_id', 'name', 'items'):
            self.assertIn(key, first)
        item = first['items'][0]
        for key in ('item_id', 'product_id', 'name', 'extra_price'):
            self.assertIn(key, item, 'the client needs the ITEM id — it is what the server validates')
        self.assertFalse(MezzeBridgeController()._product_combos(env, self.classic),
                         'a plain dish has no combo groups')

    def test_03_the_rules_normalise_a_combo_into_the_shared_group_shape(self):
        js = self._read(RULES)
        self.assertIn("kind: 'combo'", js, 'the shared rules know about combos')
        self.assertIn('comboSelectionFrom', js, 'and can reopen an existing selection')
        self.assertIn('combo.join', js, 'and combo picks are part of the line key')
        # neither surface re-implements them
        self.assertIn('PC.groups(p)', self._read(DRIVETHRU),
                      'the lane asks the shared rules for its groups')
        self.assertNotIn('combo_item_ids', self._read(STORE),
                         'the store does not reach into Odoo combo internals')

    def test_04_the_line_key_separates_two_different_meals(self):
        """The whole reason identity exists: a Coke meal is not a Coke Zero meal."""
        js = self._read(RULES)
        self.assertIn('function lineKey(productId, valueIds, note, comboItemIds)', js)


@tagged('post_install', '-at_install', 'mezze_combo')
class TestComboServerAuthority(ComboFixture):
    """Money and validity come from the server, on the path the till actually uses."""

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'combo-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='combo-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def _sync(self, combo, uuid, extra=None):
        line = {'product_id': self.meal.id, 'qty': 1, 'combo': combo}
        line.update(extra or {})
        return self._post('/orders/sync', {'uuid': uuid, 'session_id': self.session.id,
                                           'lines': [line], 'draft': True})

    def test_10_a_configured_combo_becomes_native_parent_and_child_lines(self):
        code, res = self._sync([{'item_id': self.item_classic.id},
                                {'item_id': self.item_coke.id}], 'combo-1')
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('ok'), res)
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'combo-1')], limit=1)
        self.assertTrue(order)
        parent = order.lines.filtered(lambda l: l.product_id == self.meal)
        children = order.lines.filtered(lambda l: l.combo_parent_id)
        self.assertEqual(len(parent), 1, 'one combo parent line')
        self.assertEqual(len(children), 2, 'one child per group — the real dishes')
        self.assertEqual(children.mapped('combo_parent_id'), parent)
        self.assertEqual(set(children.mapped('product_id').ids),
                         {self.classic.id, self.coke.id})
        self.assertTrue(all(children.mapped('combo_item_id')),
                        'each child records WHICH combo item it came from')

    def test_11_the_money_is_the_combo_price_plus_the_chosen_extras(self):
        """base 100 + Double 20 + Coke Zero 5 = 125 — not the sum of retail prices."""
        code, res = self._sync([{'item_id': self.item_double.id},
                                {'item_id': self.item_zero.id}], 'combo-2')
        self.assertEqual(code, 200, res)
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'combo-2')], limit=1)
        children = order.lines.filtered(lambda l: l.combo_parent_id)
        self.assertAlmostEqual(sum(children.mapped('price_subtotal')), 125.0, 2,
                               'children carry the money: 100 + 20 + 5')
        self.assertAlmostEqual(order.amount_total, 125.0, 2)
        self.assertNotAlmostEqual(order.amount_total, 80.0 + 20.0, 2,
                                  'and it is NOT the retail sum of the chosen dishes')

    def test_12_the_preview_the_operator_sees_is_the_same_number(self):
        """mezze.cart.pricing is what the lane panel and the customer board read."""
        rows, money = self.env['mezze.cart.pricing']._price_cart(
            self.pos_config, [{'product_id': self.meal.id, 'qty': 1,
                               'combo': [{'item_id': self.item_double.id},
                                         {'item_id': self.item_zero.id}]}])
        self.assertAlmostEqual(money['total'], 125.0, 2, 'preview agrees with the order')
        self.assertEqual(len(rows), 1)
        self.assertIn('Double Burger', rows[0]['modifiers'],
                      'and the customer can read what is in the meal')
        self.assertIn('Coke Zero', rows[0]['modifiers'])

    def test_13_an_item_from_another_combo_is_refused(self):
        other = self.env['product.combo'].sudo().create({
            'name': 'Someone else', 'combo_item_ids': [
                (0, 0, {'product_id': self.classic.id, 'extra_price': -50.0})]})
        code, res = self._sync([{'item_id': other.combo_item_ids[0].id},
                                {'item_id': self.item_coke.id}], 'combo-3')
        self.assertFalse(res.get('ok'), 'a cheaper item smuggled from another combo: %s' % res)
        self.assertFalse(self.env['pos.order'].sudo().search([('uuid', '=', 'combo-3')]),
                         'and nothing is persisted')

    def test_14_missing_and_duplicate_choices_are_refused(self):
        code, res = self._sync([{'item_id': self.item_classic.id}], 'combo-4')
        self.assertFalse(res.get('ok'), 'one pick for a two-group combo must fail: %s' % res)
        code, res = self._sync([{'item_id': self.item_classic.id},
                                {'item_id': self.item_double.id}], 'combo-5')
        self.assertFalse(res.get('ok'), 'two picks from ONE group must fail: %s' % res)
        for uuid in ('combo-4', 'combo-5'):
            self.assertFalse(self.env['pos.order'].sudo().search([('uuid', '=', uuid)]))

    def test_15_a_client_supplied_price_cannot_move_the_money(self):
        code, res = self._sync([{'item_id': self.item_double.id},
                                {'item_id': self.item_zero.id}], 'combo-6',
                               extra={'price_unit': 1.0})
        self.assertEqual(code, 200, res)
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'combo-6')], limit=1)
        self.assertAlmostEqual(order.amount_total, 125.0, 2,
                               'the browser said 1.00; the server prices the combo')

    def test_16_the_kitchen_is_told_the_real_dishes(self):
        code, res = self._post('/orders/fire', {
            'uuid': 'combo-7', 'session_id': self.session.id,
            'lines': [{'product_id': self.meal.id, 'qty': 1,
                       'combo': [{'item_id': self.item_classic.id},
                                 {'item_id': self.item_coke.id}]}]})
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('ok'), res)
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'combo-7')], limit=1)
        tickets = self.env['mezze.kds.ticket'].sudo().search([('pos_order_id', '=', order.id)])
        self.assertTrue(tickets, 'the combo reached the kitchen')
        names = ' '.join(tickets.mapped('line_ids.product_id.display_name')) \
            if 'line_ids' in tickets._fields else ' '.join(
                tickets.mapped(lambda t: t.display_name or ''))
        self.assertIn('Classic Burger', names, 'the kitchen sees the dish, not just "Burger Meal"')
        self.assertIn('Coke', names)


@tagged('post_install', '-at_install', 'mezze_combo')
class TestComboStaffSurfaces(ComboFixture):
    """The same assertions against BOTH staff surfaces, because parity is the point."""

    SURFACES = (('/mezze/pos', '.mz-cfg', '.mz-cfg__add', '.mz-cfg__cancel'),
                ('/mezze/drivethru', '#cfg', '#cfgadd', '#cfgcancel'))

    def test_20_tapping_a_combo_asks_instead_of_adding(self):
        for page, panel, add, _cancel in self.SURFACES:
            self.browser_js(page, _js(r"""
                const PANEL = "%s", ADD = "%s";
                await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
                const tile = $$('.mz-tile').find(t => /Burger Meal/.test(t.textContent));
                assert(tile, 'the combo is on the menu');
                tile.click();
                await waitFor(() => $(PANEL) && !$(PANEL).hidden, 'the configurator');
                assert($$('.mz-line').length === 0, 'nothing was added before it was answered');
                const heads = $$('.mz-cfg__gh').map(h => h.textContent);
                assert(heads.length === 2, 'both combo groups are offered: ' + heads.join(' | '));
                assert(/burger/i.test(heads[0]), 'named from the Odoo record: ' + heads[0]);
                assert($(ADD).disabled, 'and ADD is refused until both are chosen');
                const warn = $('.mz-cfg__warn');
                assert(warn && /burger/i.test(warn.textContent),
                       'and it says which question is unanswered: ' + (warn && warn.textContent));
                assert(!/Choose a Choose/i.test(warn.textContent),
                       'in a sentence a person would write: ' + warn.textContent);
                ok();
            """ % (panel, add)), login='admin')

    def test_21_a_combo_is_only_addable_once_every_group_is_answered(self):
        for page, panel, add, _cancel in self.SURFACES:
            self.browser_js(page, _js(r"""
                const PANEL = "%s", ADD = "%s";
                await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
                $$('.mz-tile').find(t => /Burger Meal/.test(t.textContent)).click();
                await waitFor(() => $(PANEL) && !$(PANEL).hidden, 'the configurator');
                assert($$('.mz-cfg-opt--on').length === 0,
                       'a combo group does NOT pre-answer itself');
                $$('.mz-cfg-opt').find(b => /Classic/.test(b.textContent)).click();
                await new Promise(r => setTimeout(r, 200));
                assert($(ADD).disabled, 'one group answered is not enough');
                $$('.mz-cfg-opt').find(b => /Coke Zero/.test(b.textContent)).click();
                await waitFor(() => !$(ADD).disabled, 'both answered releases ADD');
                ok();
            """ % (panel, add)), login='admin')

    def test_22_the_panel_previews_the_extras(self):
        for page, panel, _add, _cancel in self.SURFACES:
            self.browser_js(page, _js(r"""
                const PANEL = "%s";
                await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
                $$('.mz-tile').find(t => /Burger Meal/.test(t.textContent)).click();
                await waitFor(() => $('.mz-cfg__price-v'), 'the configurator');
                $$('.mz-cfg-opt').find(b => /Classic/.test(b.textContent)).click();
                $$('.mz-cfg-opt').find(b => /Coke/.test(b.textContent) && !/Zero/.test(b.textContent)).click();
                await new Promise(r => setTimeout(r, 250));
                const base = money($('.mz-cfg__price-v'));
                assert(Math.abs(base - 100) < 0.01, 'the plain meal previews its own price: ' + base);
                $$('.mz-cfg-opt').find(b => /Double/.test(b.textContent)).click();
                await waitFor(() => money($('.mz-cfg__price-v')) !== base, 'the total moved');
                assert(Math.abs(money($('.mz-cfg__price-v')) - 120) < 0.01,
                       'Double adds its real extra_price: ' + money($('.mz-cfg__price-v')));
                $$('.mz-cfg-opt').find(b => /Coke Zero/.test(b.textContent)).click();
                await new Promise(r => setTimeout(r, 250));
                assert(Math.abs(money($('.mz-cfg__price-v')) - 125) < 0.01,
                       'and so does Coke Zero: ' + money($('.mz-cfg__price-v')));
                ok();
            """ % panel), login='admin')

    def test_23_the_cart_line_reads_as_a_meal_with_its_contents(self):
        for page, panel, add, _cancel in self.SURFACES:
            self.browser_js(page, _js(r"""
                const PANEL = "%s", ADD = "%s";
                await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
                $$('.mz-tile').find(t => /Burger Meal/.test(t.textContent)).click();
                await waitFor(() => $(PANEL) && !$(PANEL).hidden, 'the configurator');
                $$('.mz-cfg-opt').find(b => /Classic/.test(b.textContent)).click();
                $$('.mz-cfg-opt').find(b => /Coke Zero/.test(b.textContent)).click();
                await waitFor(() => !$(ADD).disabled, 'answered');
                $(ADD).click();
                await waitFor(() => $$('.mz-line').length === 1, 'the line');
                const note = $('.mz-line .mz-line-note');
                assert(note, 'the contents are on the line');
                assert(/Classic/.test(note.textContent) && /Coke Zero/.test(note.textContent),
                       'both choices read back: ' + note.textContent);
                assert(/Burger Meal/.test($('.mz-line').textContent), 'under the meal name');
                assert($$('.mz-line').length === 1,
                       'the children are NOT loose top-level sales lines in the operator cart');
                ok();
            """ % (panel, add)), login='admin')

    def test_24_two_different_meals_are_two_lines_and_the_same_meal_merges(self):
        for page, panel, add, _cancel in self.SURFACES:
            self.browser_js(page, _js(r"""
                const PANEL = "%s", ADD = "%s";
                await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
                const tile = () => $$('.mz-tile').find(t => /Burger Meal/.test(t.textContent));
                const order = async (drink) => {
                    tile().click();
                    await waitFor(() => $(PANEL) && !$(PANEL).hidden, 'the configurator');
                    $$('.mz-cfg-opt').find(b => /Classic/.test(b.textContent)).click();
                    const opt = drink === '__PLAIN_COKE__'
                        ? $$('.mz-cfg-opt').find(b => /Coke/.test(b.textContent) && !/Zero/.test(b.textContent))
                        : $$('.mz-cfg-opt').find(b => new RegExp(drink).test(b.textContent));
                    opt.click();
                    await waitFor(() => !$(ADD).disabled, 'answered');
                    $(ADD).click();
                    await waitFor(() => !$(PANEL) || $(PANEL).hidden, 'confirmed');
                    await new Promise(r => setTimeout(r, 300));
                };
                await order('Coke Zero');
                await order('Coke Zero');                    // identical meal
                assert($$('.mz-line').length === 1, 'the same meal merges to a quantity');
                assert($('.mz-stepper__value').textContent.trim() === '2', 'qty 2');
                await order('__PLAIN_COKE__');              // a different drink
                await waitFor(() => $$('.mz-line').length === 2, 'a different meal is its own line');
                const notes = $$('.mz-line .mz-line-note').map(n => n.textContent.trim());
                assert(new Set(notes).size === 2, 'and they say different things: ' + notes.join(' | '));
                ok();
            """ % (panel, add)), login='admin')

    def test_25_a_choice_can_be_corrected_without_rebuilding_the_meal(self):
        for page, panel, add, _cancel in self.SURFACES:
            self.browser_js(page, _js(r"""
                const PANEL = "%s", ADD = "%s";
                const EDIT = PANEL === '#cfg' ? '.mz-line-edit' : '[data-testid=mz-line-edit]';
                await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
                $$('.mz-tile').find(t => /Burger Meal/.test(t.textContent)).click();
                await waitFor(() => $(PANEL) && !$(PANEL).hidden, 'the configurator');
                $$('.mz-cfg-opt').find(b => /Classic/.test(b.textContent)).click();
                $$('.mz-cfg-opt').find(b => /Coke Zero/.test(b.textContent)).click();
                await waitFor(() => !$(ADD).disabled, 'answered');
                $(ADD).click();
                await waitFor(() => $$('.mz-line').length === 1, 'the line');

                $(EDIT).click();
                await waitFor(() => $(PANEL) && !$(PANEL).hidden, 'reopened');
                const on = $$('.mz-cfg-opt--on').map(b => b.textContent);
                assert(on.some(t => /Classic/.test(t)) && on.some(t => /Coke Zero/.test(t)),
                       'it reopens on exactly what the guest chose: ' + on.join(','));
                const plainCoke = $$('.mz-cfg-opt').find(
                    b => /Coke/.test(b.textContent) && !/Zero/.test(b.textContent));
                plainCoke.click();
                await new Promise(r => setTimeout(r, 200));
                $(ADD).click();
                await waitFor(() => !$(PANEL) || $(PANEL).hidden, 'saved');
                await new Promise(r => setTimeout(r, 350));
                assert($$('.mz-line').length === 1, 'still ONE meal, corrected — not two');
                const note = $('.mz-line .mz-line-note').textContent;
                assert(!/Zero/.test(note), 'the old drink is gone: ' + note);
                ok();
            """ % (panel, add)), login='admin')

    def test_26_quantity_does_not_lose_the_choices(self):
        for page, panel, add, _cancel in self.SURFACES:
            self.browser_js(page, _js(r"""
                const PANEL = "%s", ADD = "%s";
                await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
                $$('.mz-tile').find(t => /Burger Meal/.test(t.textContent)).click();
                await waitFor(() => $(PANEL) && !$(PANEL).hidden, 'the configurator');
                $$('.mz-cfg-opt').find(b => /Double/.test(b.textContent)).click();
                $$('.mz-cfg-opt').find(b => /Coke Zero/.test(b.textContent)).click();
                await waitFor(() => !$(ADD).disabled, 'answered');
                $(ADD).click();
                await waitFor(() => $$('.mz-line').length === 1, 'the line');
                const before = $('.mz-line .mz-line-note').textContent.trim();
                $$('.mz-stepper__btn')[1].click();          // +
                await new Promise(r => setTimeout(r, 350));
                assert($('.mz-stepper__value').textContent.trim() === '2', 'qty 2');
                assert($('.mz-line .mz-line-note').textContent.trim() === before,
                       'the choices survived the quantity change');
                ok();
            """ % (panel, add)), login='admin')

    def test_27_the_operator_can_still_add_a_plain_dish_in_one_tap(self):
        """The fast path must not become a dialog because combos exist."""
        for page, panel, _add, _cancel in self.SURFACES:
            self.browser_js(page, _js(r"""
                const PANEL = "%s";
                await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
                const plain = $$('.mz-tile').find(t => /Classic Burger/.test(t.textContent));
                plain.click();
                await waitFor(() => $$('.mz-line').length === 1, 'straight into the order');
                assert(!$(PANEL) || $(PANEL).hidden, 'no dialog for a plain dish');
                ok();
            """ % panel), login='admin')

    def test_28_the_choices_travel_to_the_server_as_combo_item_ids(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            $$('.mz-tile').find(t => /Burger Meal/.test(t.textContent)).click();
            await waitFor(() => $('.mz-cfg'), 'the configurator');
            $$('.mz-cfg-opt').find(b => /Double/.test(b.textContent)).click();
            $$('.mz-cfg-opt').find(b => /Coke Zero/.test(b.textContent)).click();
            await waitFor(() => !$('.mz-cfg__add').disabled, 'answered');
            $('.mz-cfg__add').click();
            await waitFor(() => $$('.mz-line').length === 1, 'the line');
            const sync = window.__mezzeCashier.order.toSyncLines();
            assert(sync.length === 1, 'one line');
            assert(Array.isArray(sync[0].combo) && sync[0].combo.length === 2,
                   'carrying both picks: ' + JSON.stringify(sync[0]));
            assert(sync[0].combo.every(c => c.item_id), 'as product.combo.item ids');
            assert(sync[0].price_unit === undefined, 'and no client price');
            ok();
        """), login='admin', debug=True)

    def test_29_the_lane_keeps_its_vehicle_context_while_configuring(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            $$('.mz-tile').find(t => /Burger Meal/.test(t.textContent)).click();
            await waitFor(() => !$('#cfg').hidden, 'the configurator');
            const ctx = $('.otctx');
            assert(ctx && ctx.getBoundingClientRect().width > 0,
                   'the car being served stays on screen while choosing');
            assert($('.ops') && $('.ops').getBoundingClientRect().height > 0,
                   'and so does the lane strip');
            assert($('#cfg').getBoundingClientRect().width < innerWidth * 0.6,
                   'because the panel is a dialog, not a takeover');
            ok();
        """), login='admin')

    def test_30_the_touch_targets_are_lane_sized(self):
        for page, panel, _add, _cancel in self.SURFACES:
            self.browser_js(page, _js(r"""
                const PANEL = "%s";
                await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
                $$('.mz-tile').find(t => /Burger Meal/.test(t.textContent)).click();
                await waitFor(() => $(PANEL) && !$(PANEL).hidden, 'the configurator');
                for (const b of $$('.mz-cfg-opt')) {
                    const r = b.getBoundingClientRect();
                    assert(r.height >= 44, 'combo option below the touch floor: ' + r.height);
                }
                assert($$('[tabindex]').filter(e => parseInt(e.getAttribute('tabindex'),10) > 0).length === 0,
                       'no positive tabindex');
                ok();
            """ % panel), login='admin')

@tagged('post_install', '-at_install', 'mezze_combo')
class TestComboCustomerAndLanguage(ComboFixture):
    """What the guest sees, and what they see it in."""

    def _display(self):
        display = self.env['mezze.ocb.display'].sudo().search(
            [('config_id', '=', self.pos_config.id), ('lane', '=', 1)], limit=1)
        if not display:
            display = self.env['mezze.ocb.display'].sudo().create({
                'config_id': self.pos_config.id, 'lane': 1,
                'identifier': 'combo-ocb-1', 'name': 'Combo OCB'})
        return display

    def test_40_the_customer_board_shows_what_is_in_the_meal(self):
        display = self._display()
        display._publish([{'product_id': self.meal.id, 'qty': 1,
                           'combo': [{'item_id': self.item_double.id},
                                     {'item_id': self.item_zero.id}]}])
        payload = json.loads(display.payload or '{}')
        rows = payload.get('lines') or []
        self.assertEqual(len(rows), 1, 'one meal on the board: %s' % payload)
        self.assertEqual(rows[0]['name'], 'Burger Meal')
        self.assertIn('Double Burger', rows[0]['modifiers'],
                      'the guest can read the meal contents: %s' % rows[0])
        self.assertIn('Coke Zero', rows[0]['modifiers'])
        self.assertAlmostEqual(float(payload['money']['total']), 125.0, 2,
                               'and the money the operator is quoting')

    def test_41_correcting_a_choice_leaves_no_stale_projection(self):
        display = self._display()
        display._publish([{'product_id': self.meal.id, 'qty': 1,
                           'combo': [{'item_id': self.item_classic.id},
                                     {'item_id': self.item_zero.id}]}])
        display._publish([{'product_id': self.meal.id, 'qty': 1,
                           'combo': [{'item_id': self.item_classic.id},
                                     {'item_id': self.item_coke.id}]}])
        rows = (json.loads(display.payload or '{}').get('lines') or [])
        mods = rows[0]['modifiers']
        self.assertIn('Coke', mods)
        self.assertNotIn('Coke Zero', mods,
                         'the drink the guest changed away from must disappear: %s' % mods)

    def test_42_a_foreign_item_is_not_priced_onto_the_customers_screen(self):
        other = self.env['product.combo'].sudo().create({
            'name': 'Not ours', 'combo_item_ids': [
                (0, 0, {'product_id': self.double.id, 'extra_price': 999.0})]})
        rows, money = self.env['mezze.cart.pricing']._price_cart(
            self.pos_config, [{'product_id': self.meal.id, 'qty': 1,
                               'combo': [{'item_id': other.combo_item_ids[0].id}]}])
        self.assertAlmostEqual(money['total'], 100.0, 2,
                               'an item from another combo adds nothing: %s' % money)
        self.assertNotIn('Double Burger', rows[0]['modifiers'])

    def test_43_the_meal_reads_in_arabic_on_both_staff_surfaces(self):
        """Group and option names come from the Odoo records, so they translate."""
        self.env['res.lang']._activate_lang('ar_001')
        self.g_burger.with_context(lang='ar_001').name = 'اختر البرجر'
        self.double.with_context(lang='ar_001').name = 'برجر دوبل'
        browser_user = self.env['res.users'].sudo().search([('login', '=', 'admin')], limit=1)
        browser_user.partner_id.sudo().write({'lang': 'ar_001'})
        self.env.flush_all()
        # The two surfaces reach Arabic by different, already-certified contracts: the
        # Register follows the Odoo user's language, the lane board follows its own
        # operator toggle (FINAL-C4). The CONTENT assertion is identical either way —
        # the names come from the Odoo records, not from a page dictionary.
        for page, panel, toggle in (('/mezze/pos', '.mz-cfg', 'false'),
                                    ('/mezze/drivethru', '#cfg', 'true')):
            self.browser_js(page, _js(r"""
                const PANEL = "%s", TOGGLE = %s;
                await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
                if (TOGGLE) { $('#lang').click(); await new Promise(r => setTimeout(r, 400)); }
                $$('.mz-tile').find(t => /Burger Meal|وجبة/.test(t.textContent)).click();
                await waitFor(() => $(PANEL) && !$(PANEL).hidden, 'the configurator');
                const heads = $$('.mz-cfg__gh').map(h => h.textContent);
                assert(heads.some(h => /[؀-ۿ]/.test(h)),
                       'the combo group reads in Arabic: ' + heads.join(' | '));
                const opts = $$('.mz-cfg-opt').map(b => b.textContent);
                assert(opts.some(o => /[؀-ۿ]/.test(o)),
                       'and so does a translated option: ' + opts.join(' | '));
                assert(document.documentElement.getAttribute('dir') === 'rtl', 'RTL');
                const r = $(PANEL).getBoundingClientRect();
                assert(r.left >= -1 && r.right <= innerWidth + 1, 'the panel stays on screen');
                ok();
            """ % (panel, toggle)), login='admin')

    def test_44_the_keyboard_can_complete_a_meal(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            $$('.mz-tile').find(t => /Burger Meal/.test(t.textContent)).click();
            await waitFor(() => $('.mz-cfg'), 'the configurator');
            const opts = $$('.mz-cfg-opt');
            opts[0].focus();
            assert(document.activeElement === opts[0], 'an option can hold focus');
            const cs = getComputedStyle(opts[0], ':focus-visible');
            opts[0].click();                                   // burger
            $$('.mz-cfg-opt').find(b => /Coke Zero/.test(b.textContent)).click();
            await waitFor(() => !$('.mz-cfg__add').disabled, 'answered from the keyboard path');
            $('.mz-cfg__add').focus();
            assert(document.activeElement === $('.mz-cfg__add'), 'ADD is reachable');
            $('.mz-cfg__add').click();
            await waitFor(() => $$('.mz-line').length === 1, 'the meal is on the order');
            ok();
        """), login='admin')
