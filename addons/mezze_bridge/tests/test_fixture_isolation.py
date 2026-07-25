"""Fixture-isolation + no-arbitrary-discovery proofs (RC2 / D-2).

Guards the hermetic fixture layer against regressions: forbidden ambient-discovery
patterns must not creep back into the suite, and fixtures for different configs /
companies / roles must stay independent.
"""
import os
import re

from odoo.tests import tagged

from .common import MezzePosCase, MezzeTransactionCase

# Forbidden ambient-fixture-discovery patterns (config/session/product) in test bodies.
_FORBIDDEN = [
    re.compile(r"pos\.config'\]\s*\.\s*search\(\s*\[\s*\]\s*,\s*limit\s*=\s*[12]\b"),
    re.compile(r"pos\.session'\]\s*\.\s*(sudo\(\)\s*\.\s*)?search\(\s*\[\s*\(\s*'state'"),
]
# Files allowed to reference such strings: the fixture layer itself + this guard test.
_ALLOWED_FILES = {'common.py', 'factories.py', 'profiles.py', 'test_fixture_isolation.py'}


@tagged('post_install', '-at_install', 'mezze_invariants')
class TestNoArbitraryDiscovery(MezzeTransactionCase):
    fixture_profile = 'CORE'

    def test_no_forbidden_discovery_in_migrated_tests(self):
        here = os.path.dirname(__file__)
        offenders = []
        for fname in os.listdir(here):
            if not fname.startswith('test_') or not fname.endswith('.py'):
                continue
            if fname in _ALLOWED_FILES:
                continue
            with open(os.path.join(here, fname), encoding='utf-8') as fh:
                body = fh.read()
            for rx in _FORBIDDEN:
                if rx.search(body):
                    offenders.append('%s :: %s' % (fname, rx.pattern))
        self.assertFalse(offenders, 'forbidden ambient-discovery patterns remain: %s' % offenders)


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestFixtureIsolation(MezzePosCase):
    fixture_profile = 'POS'

    def test_second_config_is_independent(self):
        cfg2 = self.make_second_pos_config()
        self.assertNotEqual(cfg2, self.pos_config)
        self.assertNotEqual(cfg2.name, self.pos_config.name)
        # both belong to the fixture company; both carry payment methods + pricelist
        self.assertEqual(cfg2.company_id, self.company)
        self.assertTrue(cfg2.payment_method_ids)
        self.assertTrue(cfg2.pricelist_id)

    def test_session_isolation_two_configs(self):
        cfg2 = self.make_second_pos_config()
        s1 = self.open_test_session(self.pos_config)
        s2 = self.open_test_session(cfg2)
        # each config manages its OWN session — no "another session already open" collision
        self.assertEqual(s1.config_id, self.pos_config)
        self.assertEqual(s2.config_id, cfg2)
        self.assertNotEqual(s1, s2)
        self.assertNotEqual(s1.state, 'closed')
        self.assertNotEqual(s2.state, 'closed')

    def test_payment_methods_belong_to_fixture_company(self):
        for pm in self.pos_config.payment_method_ids:
            self.assertIn(pm.company_id, (self.company, self.env['res.company']),
                          'payment method scoped to fixture company (or company-agnostic)')

    def test_role_users_are_distinct(self):
        users = [self.host_user, self.server_user, self.cashier_user,
                 self.kitchen_user, self.manager_user, self.auditor_user]
        logins = [u.login for u in users]
        self.assertEqual(len(set(logins)), len(logins), 'each role has a unique login')
        self.assertEqual(len(set(users)), len(users), 'each role is a distinct user record')

    def test_no_demo_pos_config(self):
        # the fixture config is created by the fixture, not sourced from a demo XML id
        self.assertEqual(self.pos_config.name, 'Mezze Test POS')
        demo = self.env['ir.model.data'].search_count(
            [('model', '=', 'pos.config'), ('res_id', '=', self.pos_config.id)])
        self.assertEqual(demo, 0, 'fixture POS config is not an XML-data (demo) record')
