# -*- coding: utf-8 -*-
"""One tap, from the product screen, for a whole order.

Core's fast payment: a branch marks some methods as one-tap and the cashier settles
an order without opening the payment screen at all. Mezze had none of it.

Two decisions are worth pinning.

**The branch's choice is narrowed by what can actually work.** A method whose policy
REQUIRES a device or a reference cannot complete in one tap — the tender is refused
for a missing device, and the cashier is left holding a button that never works. Those
are filtered out server-side rather than offered and then apologised for.

**It goes through the ordinary tender path.** The ceilings, the duplicate policy, the
credit gate and the audit trail all still apply. A shortcut around the payment screen
must not become a shortcut around the controls, which is the obvious way to build this
and the reason to say so out loud.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_fastpay')
class TestFastPayment(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'fp-tok')
        cls.cash = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        cls.card = cls.pos_config.payment_method_ids.filtered(
            lambda m: not m.is_cash_count)[:1]
        env.flush_all()

    def _boot(self):
        r = self.url_open('/mezze/api/v1/bootstrap',
                          data=json.dumps({'token': 'fp-tok'}),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _enable(self, methods):
        self.pos_config.sudo().write({
            'use_fast_payment': True,
            'fast_payment_method_ids': [(6, 0, methods.ids)],
        })
        self.env.flush_all()

    # -- the branch's choice reaches the till ------------------------------
    def test_01_off_by_default_ships_nothing(self):
        cfg = self._boot()['config']
        self.assertFalse(cfg.get('use_fast_payment'))
        self.assertFalse(cfg.get('fast_payment_method_ids'))

    def test_02_an_enabled_method_reaches_the_till(self):
        if not self.cash:
            self.skipTest('no cash method on this config')
        self._enable(self.cash)
        cfg = self._boot()['config']
        self.assertTrue(cfg.get('use_fast_payment'))
        self.assertIn(self.cash.id, cfg['fast_payment_method_ids'])

    def test_03_turning_the_switch_off_withdraws_them(self):
        if not self.cash:
            self.skipTest('no cash method on this config')
        self._enable(self.cash)
        self.pos_config.sudo().write({'use_fast_payment': False})
        self.env.flush_all()
        self.assertFalse(self._boot()['config'].get('fast_payment_method_ids'),
                         'methods were still offered with the feature switched off')

    # -- and only methods that can actually complete ------------------------
    def test_10_a_method_needing_a_device_is_not_offered(self):
        # THE narrowing. The tender would be refused for a missing device, leaving a
        # button that never works.
        if not self.card:
            self.skipTest('no non-cash method on this config')
        self.card.sudo().write({'device_policy': 'required'})
        self._enable(self.cash | self.card)
        ids = self._boot()['config']['fast_payment_method_ids']
        self.assertNotIn(self.card.id, ids,
                         'a method that cannot complete in one tap was offered')
        if self.cash:
            self.assertIn(self.cash.id, ids, 'the usable method was withdrawn too')

    def test_11_a_method_needing_a_reference_is_not_offered(self):
        if not self.card:
            self.skipTest('no non-cash method on this config')
        self.card.sudo().write({'device_policy': 'optional',
                                'reference_policy': 'required'})
        self._enable(self.card)
        self.assertNotIn(self.card.id,
                         self._boot()['config']['fast_payment_method_ids'])

    def test_12_core_withdraws_a_method_removed_from_the_branch(self):
        # Core's own compute: a fast method that is no longer on the config stops
        # being a fast method. Asserted because Mezze reads that field directly.
        if not self.cash:
            self.skipTest('no cash method on this config')
        self._enable(self.cash)
        self.pos_config.invalidate_recordset()
        self.assertIn(self.cash, self.pos_config.fast_payment_method_ids)
