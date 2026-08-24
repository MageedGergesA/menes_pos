# -*- coding: utf-8 -*-
"""Order types, and what they cost.

``pos.preset`` is v19's order type — eat-in, takeaway, delivery — and each one may
carry its OWN pricelist and fiscal position. Mezze read presets in the kiosk path
only and rebuilt order type on the till as a two-value field plus free text, so a
branch that priced its order types through Odoo got the eat-in price on every till
order. That is a pricing bug wearing a labelling bug's clothes.

The decision worth recording: the till names the **preset**, and the server turns
that into a pricelist. A client able to name a pricelist directly is a client able to
name a cheaper one, and the guest-facing choice ("takeaway") is the only thing the
till actually knows.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_presets')
class TestPresets(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'ps-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.dish = env['product.product'].sudo().create({
            'name': 'PS Plate', 'available_in_pos': True, 'list_price': 100.0,
            'type': 'consu'})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        # A takeaway pricelist that halves the price — the kind of difference a
        # branch actually configures, and large enough that a wrong one is obvious.
        cls.cheap = env['product.pricelist'].sudo().create({
            'name': 'PS Takeaway',
            'currency_id': cls.pos_config.currency_id.id,
            'item_ids': [(0, 0, {'applied_on': '3_global',
                                 'compute_price': 'percentage',
                                 'percent_price': 50.0})],
        })
        Preset = env['pos.preset'].sudo()
        cls.eat_in = Preset.create({'name': 'PS Eat in'})
        cls.takeaway = Preset.create({'name': 'PS Takeaway',
                                      'pricelist_id': cls.cheap.id})
        cls.pos_config.sudo().write({
            'use_presets': True,
            'default_preset_id': cls.eat_in.id,
            'available_preset_ids': [(6, 0, (cls.eat_in | cls.takeaway).ids)],
        })
        env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='ps-tok')),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _sync(self, uuid, preset_id=None):
        body = {'uuid': uuid, 'session_id': self.pos_sess.id, 'draft': True,
                'lines': [{'product_id': self.dish.id, 'qty': 1}]}
        if preset_id:
            body['preset_id'] = preset_id
        return self._post('/orders/sync', body)

    def _total(self, uuid):
        self.env.invalidate_all()
        order = self.env['pos.order'].sudo().search([('uuid', '=', uuid)], limit=1)
        return order.amount_total

    # -- the till is told about them ---------------------------------------
    def test_01_presets_reach_the_till(self):
        cfg = self._post('/bootstrap', {})['config']
        self.assertTrue(cfg.get('use_presets'))
        names = [p['name'] for p in cfg['presets']]
        self.assertIn('PS Eat in', names)
        self.assertIn('PS Takeaway', names)

    def test_02_the_branch_default_is_marked(self):
        # So an order always HAS an order type, rather than acquiring one only if the
        # cashier remembers to choose.
        cfg = self._post('/bootstrap', {})['config']
        default = [p for p in cfg['presets'] if p.get('default')]
        self.assertEqual(len(default), 1)
        self.assertEqual(default[0]['name'], 'PS Eat in')

    def test_03_a_branch_not_using_presets_is_offered_none(self):
        self.pos_config.sudo().write({'use_presets': False})
        self.env.flush_all()
        cfg = self._post('/bootstrap', {})['config']
        self.assertFalse(cfg.get('use_presets'))
        self.assertFalse(cfg.get('presets'))

    def test_09_the_resolver_finds_the_presets_pricelist(self):
        # Split from test_10 on purpose: if repricing fails, this says whether the
        # preset was not resolved or the pricelist was not applied.
        from ..controllers.main import MezzeBridgeController
        pl, fp = MezzeBridgeController()._preset_pricing(
            self.env, self.pos_config, self.takeaway.id)
        self.assertEqual(pl, self.cheap.id,
                         'the preset resolver did not find its pricelist')
        self.assertAlmostEqual(
            self.cheap._get_product_price(self.dish, 1), 50.0, places=2,
            msg='the fixture pricelist does not actually halve the price')

    # -- and they actually price ------------------------------------------
    def test_10_a_preset_pricelist_changes_the_total(self):
        # THE property. Without it a preset is a label on an unchanged price.
        self._sync('ps-eatin', self.eat_in.id)
        self._sync('ps-away', self.takeaway.id)
        self.assertAlmostEqual(self._total('ps-eatin'), 100.0, places=2)
        self.assertAlmostEqual(self._total('ps-away'), 50.0, places=2,
                               msg='the takeaway pricelist was ignored')

    def test_11_no_preset_leaves_the_branch_price(self):
        self._sync('ps-none')
        self.assertAlmostEqual(self._total('ps-none'), 100.0, places=2)

    def test_12_an_explicit_pricelist_still_wins(self):
        # A caller that names one is being deliberate; the preset is the default, not
        # an override of an override.
        self._post('/orders/sync', {
            'uuid': 'ps-explicit', 'session_id': self.pos_sess.id, 'draft': True,
            'preset_id': self.takeaway.id,
            'pricelist_id': self.pos_config.pricelist_id.id,
            'lines': [{'product_id': self.dish.id, 'qty': 1}]})
        self.assertAlmostEqual(self._total('ps-explicit'), 100.0, places=2)

    # -- and cannot be abused ---------------------------------------------
    def test_13_a_preset_the_branch_does_not_offer_is_ignored(self):
        # Not an error worth failing a sale over — but it must not price the order
        # either, or a client could quote any preset id in the database.
        other = self.env['pos.preset'].sudo().create(
            {'name': 'PS Foreign', 'pricelist_id': self.cheap.id})
        self._sync('ps-foreign', other.id)
        self.assertAlmostEqual(self._total('ps-foreign'), 100.0, places=2,
                               msg="a preset this branch does not offer priced the order")

    def test_14_presets_off_means_no_preset_pricing(self):
        self.pos_config.sudo().write({'use_presets': False})
        self.env.flush_all()
        self._sync('ps-off', self.takeaway.id)
        self.assertAlmostEqual(self._total('ps-off'), 100.0, places=2)
