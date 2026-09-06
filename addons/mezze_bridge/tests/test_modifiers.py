"""BE-010 Mezze modifier groups — the shape, the guard, and the migrated path.

``docs/MENU_ENGINE.md`` §2/§2a freezes what an order line records when a guest
picks Large / Extra spicy: a STRUCTURED array, never a joined label, with the
option's stable id rather than its display text.

The last group of tests exists because of a real regression caught by hand and
not by this suite: on a clean install nothing is migrated, so no product carries
Mezze groups and the guard that refuses a double-priced line never fires. Tests
were green while the Register could not add a configured migrated product at
all. Every test below that matters therefore MIGRATES a product first.
"""
import json

from odoo.tests import TransactionCase, tagged

from ..domain import modifiers as mods
from .common import MezzeHttpCase


def S(g, t, label='x', p=0.0):
    return mods.Selection(g=g, t=t, label=label, p=p)


@tagged('post_install', '-at_install', 'mezze_menu')
class TestModifierRules(TransactionCase):
    """The pure rules — no database needed to be sure of them."""

    def _groups(self, **kw):
        base = dict(key='size', required=True, min_select=1, max_select=1,
                    options={1: True, 2: True, 3: False})
        base.update(kw)
        return [mods.Group(**base)]

    def test_01_the_label_is_derived_never_stored(self):
        sel = [S('size', 1, 'Large', 25.0), S('spice', 4, 'Hot')]
        self.assertEqual(mods.render(sel), 'Large · Hot')
        self.assertTrue(mods.has(sel))
        self.assertFalse(mods.has([]))

    def test_02_equality_is_array_aware_and_order_insensitive(self):
        a = [S('size', 1, 'Large', 25.0), S('spice', 4, 'Hot')]
        b = [S('spice', 4, 'Hot'), S('size', 1, 'Large', 25.0)]
        self.assertTrue(mods.same(a, b), "same configuration, different click order")

    def test_03_a_price_change_makes_it_a_different_line(self):
        """Merging across a reprice would silently restate what a guest agreed."""
        self.assertFalse(mods.same([S('size', 1, 'Large', 25.0)],
                                   [S('size', 1, 'Large', 30.0)]))

    def test_04_a_required_group_must_be_answered(self):
        errs = mods.validate(self._groups(), [])
        self.assertEqual([e[0] for e in errs], [mods.ERR_REQUIRED])

    def test_05_an_unavailable_option_is_refused(self):
        """86 lives on the OPTION — one size gone, the dish still sellable."""
        errs = mods.validate(self._groups(), [S('size', 3)])
        self.assertIn(mods.ERR_UNAVAILABLE, [e[0] for e in errs])

    def test_06_min_and_max_picks_are_enforced(self):
        g = self._groups(key='addons', required=False, min_select=2, max_select=3,
                         options={1: True, 2: True, 3: True, 4: True})
        self.assertIn(mods.ERR_MIN,
                      [e[0] for e in mods.validate(g, [S('addons', 1)])])
        self.assertIn(mods.ERR_MAX, [e[0] for e in mods.validate(
            g, [S('addons', 1), S('addons', 2), S('addons', 3), S('addons', 4)])])
        self.assertEqual(mods.validate(g, [S('addons', 1), S('addons', 2)]), [])

    def test_07_an_untouched_optional_group_is_fine(self):
        g = self._groups(required=False, min_select=0)
        self.assertEqual(mods.validate(g, []), [])

    def test_08_unknown_groups_and_options_are_named(self):
        self.assertIn(mods.ERR_UNKNOWN_GROUP,
                      [e[0] for e in mods.validate(self._groups(), [S('nope', 1)])])
        self.assertIn(mods.ERR_UNKNOWN_OPTION,
                      [e[0] for e in mods.validate(self._groups(), [S('size', 99)])])

    def test_09_the_delta_is_summed_from_the_selections(self):
        self.assertAlmostEqual(
            mods.total_delta([S('size', 1, 'L', 25.0), S('addons', 2, 'Cheese', 15.0)]),
            40.0, 2)


@tagged('post_install', '-at_install', 'mezze_menu')
class TestMigratedProductOrdering(MezzeHttpCase):
    """A product ON Mezze groups, ordered through the real endpoint."""

    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.shared = 'modifiers-shared-token'
        ICP.set_param('mezze_bridge.api_token', self.shared)
        ICP.set_param('mezze_bridge.api_security', 'observe')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session(self.pos_config)

        G = self.env['mezze.modifier.group'].sudo()
        O = self.env['mezze.modifier.option'].sudo()
        self.size = G.create({'name': 'Size', 'code': 'size', 'required': True,
                              'min_select': 1, 'max_select': 1})
        self.o_reg = O.create({'group_id': self.size.id, 'name': 'Regular'})
        self.o_big = O.create({'group_id': self.size.id, 'name': 'Large',
                               'price_delta': 25.0})
        self.o_gone = O.create({'group_id': self.size.id, 'name': 'Family',
                                'price_delta': 60.0, 'available': False})
        self.prod = self.product
        self.prod.product_tmpl_id.mezze_modifier_group_ids = [(6, 0, [self.size.id])]
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(
            dict(body, token=self.shared)),
            headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def _sync(self, line, uuid):
        return self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'lines': [line], 'draft': True})

    def test_20_a_migrated_product_can_still_be_ordered(self):
        """THE regression: every surface echoes the ids it was given under
        `attribute_value_ids`. A migrated product must accept that, not refuse it."""
        code, res = self._sync({'product_id': self.prod.id, 'qty': 1,
                                'attribute_value_ids': [self.o_big.id]}, 'mod-1')
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('ok'), res)
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'mod-1')], limit=1)
        line = order.lines[0]
        self.assertEqual(len(line.mezze_modifier_ids), 1, "the selection is on the line")
        self.assertEqual(line.mezze_modifier_ids.option_id, self.o_big)
        self.assertAlmostEqual(line.price_unit, self.prod.lst_price + 25.0, 2,
                               "the SERVER priced the delta from the option record")

    def test_21_the_selection_snapshots_its_label_and_delta(self):
        self._sync({'product_id': self.prod.id, 'qty': 1,
                    'attribute_value_ids': [self.o_big.id]}, 'mod-2')
        line = self.env['pos.order'].sudo().search(
            [('uuid', '=', 'mod-2')], limit=1).lines[0]
        sel = line.mezze_modifier_ids
        self.o_big.write({'name': 'Extra Large', 'price_delta': 99.0})
        sel.invalidate_recordset()
        self.assertEqual(sel.label, 'Large', "a rename must not rewrite history")
        self.assertAlmostEqual(sel.price_delta, 25.0, 2,
                               "nor may a reprice restate what the guest agreed")

    def test_22_an_86d_option_is_refused_at_the_point_of_choice(self):
        code, res = self._sync({'product_id': self.prod.id, 'qty': 1,
                                'attribute_value_ids': [self.o_gone.id]}, 'mod-3')
        self.assertFalse(res.get('ok'), res)
        self.assertFalse(self.env['pos.order'].sudo().search([('uuid', '=', 'mod-3')]),
                         "no order may exist for a line that was refused")

    def test_23_a_required_group_cannot_be_skipped(self):
        code, res = self._sync({'product_id': self.prod.id, 'qty': 1}, 'mod-4')
        self.assertFalse(res.get('ok'), res)

    def test_24_a_line_quoting_both_systems_is_priced_once(self):
        """One system per product — proven by sending BOTH keys.

        Two earlier versions of this test could not fail: for a migrated product
        the server publishes OPTION ids, the client echoes those, and the
        attribute lookup then matches nothing, so there was never a second
        surcharge to find. The guard actually defends against a line that quotes
        both systems at once — a stale or hand-rolled client — so that is what
        this sends. With the guard removed the line is surcharged twice.
        """
        Attr = self.env['product.attribute'].sudo()
        Val = self.env['product.attribute.value'].sudo()
        attr = Attr.create({'name': 'Legacy size', 'create_variant': 'no_variant',
                            'display_type': 'radio'})
        vals = [Val.create({'name': n, 'attribute_id': attr.id}).id
                for n in ('Small', 'Huge')]
        tmpl = self.env['product.template'].sudo().create({
            'name': 'Both Systems', 'available_in_pos': True, 'list_price': 40.0})
        aline = self.env['product.template.attribute.line'].create({
            'product_tmpl_id': tmpl.id, 'attribute_id': attr.id,
            'value_ids': [(6, 0, vals)]})
        ptav = aline.product_template_value_ids.filtered(
            lambda v: v.product_attribute_value_id.name == 'Huge')
        ptav.price_extra = 7.0          # the surcharge that must NOT also apply

        G = self.env['mezze.modifier.group'].sudo()
        O = self.env['mezze.modifier.option'].sudo()
        grp = G.create({'name': 'New size', 'code': 'newsize', 'required': True,
                        'min_select': 1, 'max_select': 1})
        opt = O.create({'group_id': grp.id, 'name': 'Huge', 'price_delta': 12.0})
        tmpl.mezze_modifier_group_ids = [(6, 0, [grp.id])]
        prod = tmpl.product_variant_id
        self.env.flush_all()

        code, res = self._sync({'product_id': prod.id, 'qty': 1,
                                'mezze_modifiers': [opt.id],
                                'attribute_value_ids': [ptav.id]}, 'mod-both')
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('ok'), res)
        pl = self.env['pos.order'].sudo().search(
            [('uuid', '=', 'mod-both')], limit=1).lines[0]
        self.assertAlmostEqual(
            pl.price_unit, 52.0, 2,
            "40 + 12 ONCE — the attribute surcharge was applied as well")
        self.assertFalse(pl.attribute_value_ids,
                         "the attribute path also ran on a Mezze-group product")

    def test_25_the_menu_payload_keeps_the_key_three_surfaces_read(self):
        """shop.html / pos.html / qr.html key their selection map on `line_id`.
        Dropping it silently broke their rendering — 'shape-identical' has to
        mean identical."""
        # /bootstrap is what the Register reads its catalogue from.
        code, res = self._post('/bootstrap', {'config_id': self.pos_config.id})
        self.assertEqual(code, 200, res)
        prods = res.get('products') or res.get('items') or []
        row = next((p for p in prods if p.get('id') == self.prod.id), None)
        self.assertTrue(row, "the product is on the menu: %s" % str(res)[:200])
        groups = row.get('modifiers') or []
        self.assertTrue(groups, "its modifier groups are published")
        g = groups[0]
        for key in ('line_id', 'values', 'required', 'min', 'max'):
            self.assertIn(key, g, "the payload lost %r" % key)
        self.assertIn('price_extra', g['values'][0],
                      "five surfaces read values[].price_extra")


@tagged('post_install', '-at_install', 'mezze_menu')
class TestModifierMigration(TransactionCase):
    """The BE-010 data migration, exercised rather than trusted.

    It had only ever been run by hand. A migration nobody tests is one that
    breaks silently at the next version bump, and this one is the step that
    moves live restaurant menus off product attributes.
    """

    #: migrations/ is not an importable package (no __init__), so the script is
    #: loaded by path — the same way Odoo's own upgrade runner reaches it.
    MIGRATION = 'migrations/19.0.5.5.0/post-migration.py'

    def setUp(self):
        super().setUp()
        self.Attr = self.env['product.attribute'].sudo()
        self.Val = self.env['product.attribute.value'].sudo()
        self.Tmpl = self.env['product.template'].sudo()

    def _legacy_product(self, name, attr_name, values, display='radio'):
        attr = self.Attr.create({'name': attr_name, 'create_variant': 'no_variant',
                                 'display_type': display})
        vals = [self.Val.create({'name': v, 'attribute_id': attr.id}).id for v in values]
        tmpl = self.Tmpl.create({'name': name, 'available_in_pos': True, 'list_price': 40.0})
        self.env['product.template.attribute.line'].create({
            'product_tmpl_id': tmpl.id, 'attribute_id': attr.id, 'value_ids': [(6, 0, vals)]})
        return tmpl, attr

    def _run(self):
        import importlib.util
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, self.MIGRATION)
        self.assertTrue(os.path.exists(path), "the migration script moved: %s" % path)
        spec = importlib.util.spec_from_file_location('mezze_be010_migration', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # a truthy `version` means "upgrade", which is when it must run
        mod.migrate(self.env.cr, '19.0.5.4.4')
        self.env.invalidate_all()

    def test_30_a_legacy_product_gains_a_mezze_group(self):
        tmpl, attr = self._legacy_product('Legacy Grill', 'Doneness', ['Rare', 'Well done'])
        self._run()
        tmpl.invalidate_recordset()
        groups = tmpl.mezze_modifier_group_ids
        self.assertEqual(len(groups), 1, "the attribute line became one group")
        self.assertEqual(groups.code, 'attr_%s' % attr.id,
                         "the key is derived from the source id, not the label")
        self.assertEqual(sorted(groups.option_ids.mapped('name')), ['Rare', 'Well done'])

    def test_31_the_single_select_rule_is_carried_over_verbatim(self):
        """A radio attribute was required-exactly-one; a multi was optional-any.
        The migration must not quietly restate either."""
        radio, _ = self._legacy_product('R', 'Doneness R', ['A', 'B'], display='radio')
        multi, _ = self._legacy_product('M', 'Extras M', ['C', 'D'], display='multi')
        self._run()
        radio.invalidate_recordset(); multi.invalidate_recordset()
        g_radio = radio.mezze_modifier_group_ids
        g_multi = multi.mezze_modifier_group_ids
        self.assertTrue(g_radio.required)
        self.assertEqual((g_radio.min_select, g_radio.max_select), (1, 1))
        self.assertFalse(g_multi.required)
        self.assertEqual((g_multi.min_select, g_multi.max_select), (0, 0))

    def test_32_running_it_twice_converts_nothing_the_second_time(self):
        tmpl, _ = self._legacy_product('Twice', 'Spice T', ['Mild', 'Hot'])
        self._run()
        before = self.env['mezze.modifier.group'].sudo().search_count([])
        opts_before = self.env['mezze.modifier.option'].sudo().search_count([])
        self._run()
        self.assertEqual(self.env['mezze.modifier.group'].sudo().search_count([]), before,
                         "a second run created another group")
        self.assertEqual(self.env['mezze.modifier.option'].sudo().search_count([]),
                         opts_before, "a second run duplicated the options")
        tmpl.invalidate_recordset()
        self.assertEqual(len(tmpl.mezze_modifier_group_ids), 1, "nor attached it twice")

    def test_33_the_attribute_lines_are_left_in_place(self):
        """A half-finished migration must still serve a menu, so the old data
        stays until nothing reads it."""
        tmpl, _ = self._legacy_product('Keep', 'Size K', ['S', 'L'])
        self._run()
        tmpl.invalidate_recordset()
        self.assertTrue(tmpl.attribute_line_ids, "the source lines were deleted")

    def test_34_an_option_switched_off_does_not_come_back_available(self):
        tmpl, _ = self._legacy_product('Off', 'Size O', ['S', 'L'])
        ptav = tmpl.attribute_line_ids.product_template_value_ids
        ptav[0].ptav_active = False
        self._run()
        tmpl.invalidate_recordset()
        opt = tmpl.mezze_modifier_group_ids.option_ids.filtered(
            lambda o: o.name == ptav[0].product_attribute_value_id.name)
        self.assertFalse(opt.available,
                         "an option Odoo had switched off came back sellable")
