"""DT-UX7A — product customization on the drive-thru, end to end.

The drive-thru could not capture "no onion", so the customer board had nothing true
to show. The capability already existed on the server (Odoo's POS-time attributes,
already used by the Register); what was missing was the lane's configurator and the
plumbing for the chosen values.

These tests are about the two things that make customization worth having: the money
must be the same number everywhere, and a chosen option must be one the product
actually offers. A browser is not an authority on either.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime', 'mezze_dt_custom')
class TestDriveThruCustomization(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'cust-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session()
        self.plain = self.env['product.product'].search(
            [('available_in_pos', '=', True), ('pos_categ_ids', '!=', False)], limit=1)

        # A configurable product built from Odoo's own models: POS-time attributes
        # (create_variant='no_variant'), one required single-select and one optional
        # multi, with real price_extra. Nothing Mezze-specific.
        Attr = self.env['product.attribute']
        Val = self.env['product.attribute.value']
        self.portion = Attr.create({'name': 'DT Portion', 'create_variant': 'no_variant',
                                    'display_type': 'radio'})
        self.regular = Val.create({'name': 'Regular', 'attribute_id': self.portion.id})
        self.large = Val.create({'name': 'Large', 'attribute_id': self.portion.id})
        self.extras = Attr.create({'name': 'DT Extras', 'create_variant': 'no_variant',
                                   'display_type': 'multi'})
        self.cheese = Val.create({'name': 'Extra cheese', 'attribute_id': self.extras.id})
        self.onion = Val.create({'name': 'No onion', 'attribute_id': self.extras.id})

        # a POS category is required by the menu domain, and the taxes are cleared
        # explicitly after create because the company default is applied on create
        categ = self.env['pos.category'].search([], limit=1) \
            or self.env['pos.category'].create({'name': 'DT Test'})
        self.categ = categ
        self.burger = self.env['product.product'].create({
            'name': 'DT Test Burger', 'available_in_pos': True, 'list_price': 50.0,
            'pos_categ_ids': [(6, 0, categ.ids)]})
        tmpl = self.burger.product_tmpl_id
        tmpl.taxes_id = [(5, 0, 0)]
        self.env['product.template.attribute.line'].create({
            'product_tmpl_id': tmpl.id, 'attribute_id': self.portion.id,
            'value_ids': [(6, 0, [self.regular.id, self.large.id])]})
        self.env['product.template.attribute.line'].create({
            'product_tmpl_id': tmpl.id, 'attribute_id': self.extras.id,
            'value_ids': [(6, 0, [self.cheese.id, self.onion.id])]})
        self.env.flush_all()
        ptav = {v.product_attribute_value_id.name: v
                for v in tmpl.attribute_line_ids.mapped('product_template_value_ids')}
        ptav['Large'].price_extra = 5.0
        ptav['Extra cheese'].price_extra = 3.0
        self.ptav = ptav

        # a SECOND configurable product, so "another product's option" is a real thing
        self.other = self.env['product.product'].create({
            'name': 'DT Test Wrap', 'available_in_pos': True, 'list_price': 40.0,
            'pos_categ_ids': [(6, 0, self.categ.ids)]})
        self.other.product_tmpl_id.taxes_id = [(5, 0, 0)]
        self.env['product.template.attribute.line'].create({
            'product_tmpl_id': self.other.product_tmpl_id.id,
            'attribute_id': self.portion.id,
            'value_ids': [(6, 0, [self.regular.id, self.large.id])]})
        self.env.flush_all()
        self.other_large = self.other.product_tmpl_id.attribute_line_ids\
            .mapped('product_template_value_ids')\
            .filtered(lambda v: v.product_attribute_value_id == self.large)

        self.env.flush_all()
        self.burger.invalidate_recordset(); self.other.invalidate_recordset()
        self.assertFalse(self.burger.taxes_id,
                         'the money assertions below assume a tax-free fixture')
        self.assertFalse(self.other.taxes_id)

        Display = self.env['mezze.ocb.display']
        Display.sudo().search([]).unlink()
        self.display, self.dtok = Display._provision(self.pos_config, lane=1)
        self.env.flush_all()

    # ---- helpers ------------------------------------------------------------
    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='cust-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:                                        # noqa: BLE001
            return r.status_code, {'_raw': r.text[:200]}

    def _ocb(self):
        r = self.url_open('/mezze/api/v1/ocb/state',
                          data=json.dumps({'token': self.dtok}),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        return r.json()

    def _total(self, product, qty=1, avids=()):
        """What the SERVER says this configuration costs, through the real path."""
        line = {'product_id': product.id, 'qty': qty}
        if avids:
            line['attribute_value_ids'] = list(avids)
        self._publish([line])
        return self._ocb()['order']['lines'][0]['line_total']

    def _extra(self, product, avids, qty=1):
        """What a configuration ADDS. Absolute figures would be asserting the branch's
        pricelist and tax, neither of which price_extra is about — this branch marks
        up 15% and taxes on top. What price_extra promises is the increment, and the
        RATIO between two increments is immune to any uniform multiplier over both.
        """
        return self._total(product, qty, avids) - self._total(product, qty)

    def _publish(self, lines):
        return self._post('/ocb/publish', {'config_id': self.pos_config.id,
                                           'lane': 1, 'lines': lines})

    # ==================================================================
    # the configuration the board is given
    # ==================================================================
    def test_01_the_boot_payload_carries_real_attribute_groups(self):
        _code, res = self._post('/bootstrap', {})
        by_id = {p['id']: p for p in res['products']}
        burger = by_id[self.burger.id]
        groups = {g['attribute']: g for g in burger['modifiers']}
        self.assertIn('DT Portion', groups)
        self.assertIn('DT Extras', groups)
        self.assertTrue(groups['DT Portion']['required'],
                        'a single-select group must be answered')
        self.assertFalse(groups['DT Extras']['required'])
        self.assertTrue(groups['DT Extras']['multi'])
        large = [v for v in groups['DT Portion']['values'] if v['name'] == 'Large'][0]
        self.assertEqual(large['price_extra'], 5.0, 'the real price_extra, not a guess')

    def test_02_a_plain_product_offers_no_configuration(self):
        _code, res = self._post('/bootstrap', {})
        by_id = {p['id']: p for p in res['products']}
        self.assertFalse(by_id[self.plain.id]['modifiers'],
                         'a product with no attributes must not open a configurator')

    # ==================================================================
    # money — the same number everywhere
    # ==================================================================
    def test_03_the_server_prices_the_extras(self):
        large = self._extra(self.burger, [self.ptav['Large'].id])
        both = self._extra(self.burger, [self.ptav['Large'].id,
                                         self.ptav['Extra cheese'].id])
        self.assertGreater(large, 0, 'a +5 option must cost something')
        self.assertAlmostEqual(both / large, 8.0 / 5.0, 3,
                               'Large (+5) and Extra cheese (+3) are in the ratio the '
                               'product configuration declares (%s vs %s)' % (both, large))

    def test_04_quantity_multiplies_the_configured_price(self):
        one = self._extra(self.burger, [self.ptav['Large'].id], qty=1)
        three = self._extra(self.burger, [self.ptav['Large'].id], qty=3)
        self.assertAlmostEqual(three / one, 3.0, 3,
                               'the option is charged once per item (%s vs %s)'
                               % (three, one))
        order = self._ocb()['order']
        self.assertAlmostEqual(order['money']['total'],
                               order['lines'][0]['line_total'], 2)

    def test_05_the_lines_add_up_to_the_total(self):
        self._publish([
            {'product_id': self.burger.id, 'qty': 2,
             'attribute_value_ids': [self.ptav['Large'].id, self.ptav['Extra cheese'].id]},
            {'product_id': self.plain.id, 'qty': 1},
        ])
        order = self._ocb()['order']
        self.assertAlmostEqual(sum(l['line_total'] for l in order['lines']),
                               order['money']['total'], 2)

    def test_06_the_configured_price_survives_into_the_pos_order(self):
        # the parity that matters most: what the customer was shown and what the
        # business will actually charge
        code, res = self._post('/drivethru/create', {
            'session_id': self.session.id, 'lane': 1, 'vehicle': 'PARITY',
            'lines': [{'product_id': self.burger.id, 'qty': 2,
                       'attribute_value_ids': [self.ptav['Large'].id,
                                               self.ptav['Extra cheese'].id]}]})
        self.assertEqual(code, 200, res)
        order = self.env['pos.order'].browse(res['car']['order_id'])
        order.invalidate_recordset()
        line = order.lines[0]
        self.assertAlmostEqual(line.price_unit - self.burger.list_price, 8.0, 2,
                               'the extras land on the unit price (+5 +3), not bolted '
                               'on afterwards')
        self.assertAlmostEqual(order.amount_total, line.price_subtotal_incl, 2,
                               'and the order total is that line, taxed by Odoo')

    # ==================================================================
    # security — a browser is not an authority
    # ==================================================================
    def test_07_a_value_from_another_product_is_refused(self):
        # `Large` exists on both products, but THIS ptav belongs to the wrap.
        base = self._total(self.burger)
        self._publish([{'product_id': self.burger.id, 'qty': 1,
                        'attribute_value_ids': [self.other_large.id]}])
        line = self._ocb()['order']['lines'][0]
        self.assertAlmostEqual(line['line_total'], base, 2,
                               "another product's option must not price this one")
        self.assertEqual(line['modifiers'], [],
                         'and must not be named on the customer display')

    def test_08_an_invented_value_id_is_refused(self):
        base = self._total(self.burger)
        self._publish([{'product_id': self.burger.id, 'qty': 1,
                        'attribute_value_ids': [999999999]}])
        line = self._ocb()['order']['lines'][0]
        self.assertAlmostEqual(line['line_total'], base, 2)
        self.assertEqual(line['modifiers'], [])

    def test_09_a_client_supplied_price_is_ignored(self):
        honest = self._total(self.burger, 1, [self.ptav['Large'].id])
        self._publish([{'product_id': self.burger.id, 'qty': 1,
                        'price': 1.0, 'line_total': 1.0, 'price_extra': 999.0,
                        'attribute_value_ids': [self.ptav['Large'].id]}])
        line = self._ocb()['order']['lines'][0]
        self.assertAlmostEqual(line['line_total'], honest, 2,
                               'the server prices from the product and the values, '
                               'and ignores every number the browser sent')

    def test_10_a_foreign_value_cannot_reach_the_pos_order_either(self):
        code, res = self._post('/drivethru/create', {
            'session_id': self.session.id, 'lane': 1, 'vehicle': 'INJECT',
            'lines': [{'product_id': self.burger.id, 'qty': 1,
                       'attribute_value_ids': [self.other_large.id]}]})
        self.assertEqual(code, 200, res)
        order = self.env['pos.order'].browse(res['car']['order_id'])
        order.invalidate_recordset()
        self.assertAlmostEqual(order.lines[0].price_unit, self.burger.list_price, 2,
                               'the injected option changed nothing')
        self.assertNotIn(self.other_large, order.lines[0].attribute_value_ids)

    # ==================================================================
    # the customer's screen
    # ==================================================================
    def test_11_the_customer_sees_the_choices_by_their_real_names(self):
        self._publish([{'product_id': self.burger.id, 'qty': 2,
                        'attribute_value_ids': [self.ptav['Large'].id,
                                                self.ptav['No onion'].id]}])
        line = self._ocb()['order']['lines'][0]
        self.assertEqual(line['qty'], 2)
        self.assertEqual(sorted(line['modifiers']), ['Large', 'No onion'])

    def test_12_a_removed_modifier_disappears_from_the_customer_screen(self):
        self._publish([{'product_id': self.burger.id, 'qty': 1,
                        'attribute_value_ids': [self.ptav['Large'].id,
                                                self.ptav['Extra cheese'].id]}])
        self.assertIn('Extra cheese', self._ocb()['order']['lines'][0]['modifiers'])
        with_both = self._ocb()['order']['lines'][0]['line_total']
        self._publish([{'product_id': self.burger.id, 'qty': 1,
                        'attribute_value_ids': [self.ptav['Large'].id]}])
        line = self._ocb()['order']['lines'][0]
        self.assertEqual(line['modifiers'], ['Large'],
                         'no stale modifier survives an edit')
        self.assertLess(line['line_total'], with_both,
                        'and the price follows the removal')
        large_only = self._extra(self.burger, [self.ptav['Large'].id])
        both = self._extra(self.burger, [self.ptav['Large'].id,
                                         self.ptav['Extra cheese'].id])
        self.assertAlmostEqual((both - large_only) / large_only, 3.0 / 5.0, 3,
                               'by exactly what Extra cheese was worth')

    def test_13_two_configurations_of_one_product_stay_two_lines(self):
        self._publish([
            {'product_id': self.burger.id, 'qty': 1,
             'attribute_value_ids': [self.ptav['No onion'].id]},
            {'product_id': self.burger.id, 'qty': 1,
             'attribute_value_ids': [self.ptav['Extra cheese'].id]},
        ])
        lines = self._ocb()['order']['lines']
        self.assertEqual(len(lines), 2, 'never merge on product id alone')
        self.assertNotEqual(lines[0]['modifiers'], lines[1]['modifiers'])

    # ==================================================================
    # the kitchen
    # ==================================================================
    def test_14_the_kitchen_receives_the_choices_with_the_food(self):
        code, res = self._post('/drivethru/create', {
            'session_id': self.session.id, 'lane': 1, 'vehicle': 'KITCHEN',
            'lines': [{'product_id': self.burger.id, 'qty': 1,
                       'attribute_value_ids': [self.ptav['No onion'].id,
                                               self.ptav['Extra cheese'].id]}]})
        self.assertEqual(code, 200, res)
        tickets = self.env['mezze.kds.ticket'].search(
            [('pos_order_id', '=', res['car']['order_id'])])
        self.assertTrue(tickets, 'the order fired')
        notes = ' | '.join(tickets.mapped('line_ids.note')) if tickets.line_ids else ''
        blob = notes or ' | '.join(filter(None, tickets.mapped('line_ids.name')))
        self.assertIn('No onion', blob, 'the kitchen is told, as words: %s' % blob)
        self.assertIn('Extra cheese', blob)

    def test_15_the_configuration_survives_on_the_order_line(self):
        code, res = self._post('/drivethru/create', {
            'session_id': self.session.id, 'lane': 1, 'vehicle': 'HISTORY',
            'lines': [{'product_id': self.burger.id, 'qty': 1,
                       'attribute_value_ids': [self.ptav['Large'].id]}]})
        self.assertEqual(code, 200, res)
        line = self.env['pos.order'].browse(res['car']['order_id']).lines[0]
        self.assertIn(self.ptav['Large'], line.attribute_value_ids,
                      'an order must still be readable after the fact')

    # ==================================================================
    # the lane board itself
    # ==================================================================
    def test_16_the_board_keeps_the_configuration_it_is_given(self):
        # the whole defect this phase fixed was one line of JS discarding it
        path = __file__.rsplit('/tests/', 1)[0] + '/static/drivethru.html'
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        self.assertIn('mods:p.modifiers', src,
                      'the lane board must keep the attribute groups it boots with')
        self.assertIn('attribute_value_ids:it.avids', src,
                      'and send the chosen values on')

    def test_17_a_configured_line_is_keyed_by_its_configuration(self):
        """Line identity includes the configuration, not just the product.

        This asserted the drive-thru's own inline arithmetic until CONV-3 made the
        rule canonical. It now asserts the same property where the rule actually
        lives — and that the board really delegates to it, so the two cannot drift.
        """
        base = __file__.rsplit('/tests/', 1)[0]
        with open(base + '/static/drivethru.html', encoding='utf-8') as fh:
            src = fh.read()
        with open(base + '/static/design/product-config.js', encoding='utf-8') as fh:
            rules = fh.read()
        self.assertIn('function lineKey(', src)
        self.assertIn('PC.lineKey(id, avids)', src,
                      'the board delegates its line identity to the shared rule')
        self.assertIn('productId + "@" + ids.join("-")', rules,
                      'and the shared rule keys on product AND configuration')
        self.assertIn('.slice().sort(', rules,
                      'sorted, so tap order cannot change the identity')
