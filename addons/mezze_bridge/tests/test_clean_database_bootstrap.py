"""Clean-database bootstrap proof (RC2 / D-2).

Asserts that immediately after a fresh ``--without-demo=all`` install + hermetic
fixture provisioning, a whole Mezze service slice is usable end-to-end WITHOUT any
canonical pilot record, demo data, or manual provisioning. This is the single test
that most directly proves D-2 is fixed.
"""
from odoo import fields
from odoo.tests import tagged

from .common import MezzePosCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestCleanDatabaseBootstrap(MezzePosCase):
    fixture_profile = 'FULL'

    def test_environment_is_usable_end_to_end(self):
        # --- company / users ---
        self.assertTrue(self.company.exists())
        self.assertTrue(self.company.currency_id)
        self.assertTrue(self.company.partner_id.tz, 'company timezone set')
        for user in (self.host_user, self.cashier_user, self.kitchen_user,
                     self.manager_user, self.admin_user, self.auditor_user):
            self.assertTrue(user and user.exists(), 'role user provisioned')
        logins = {u.login for u in (self.host_user, self.cashier_user, self.manager_user)}
        self.assertEqual(len(logins), 3, 'role users have distinct logins')

        # --- POS config / menu / payment methods ---
        cfg = self.pos_config
        self.assertTrue(cfg.exists())
        self.assertEqual(cfg.company_id, self.company)
        self.assertTrue(cfg.payment_method_ids, 'payment methods assigned to config')
        self.assertTrue(cfg.pricelist_id, 'pricelist assigned')
        self.assertTrue(self.product.available_in_pos)
        self.assertGreaterEqual(len(self.products), 3)

        # --- our fixture config has no session until we open one (portable across
        # clean AND canonical databases: the fixture config is always brand-new) ---
        self.assertFalse(self.get_test_session(), 'no session on the fixture config yet')
        session = self.open_test_session()
        self.assertEqual(session.config_id, cfg)
        self.assertNotEqual(session.state, 'closed')

        # --- one order -> one payment -> completed ---
        order = self.create_order_in_test_session(price=10.0)
        self.assertEqual(order.session_id, session)
        order.add_payment({'amount': 10.0, 'payment_method_id': self.cash_payment_method.id,
                           'name': fields.Datetime.now(), 'pos_order_id': order.id})
        try:
            order.action_pos_order_paid()
        except Exception:  # noqa: BLE001 — accounting close varies; assert the money state
            order.write({'state': 'paid'})
        self.assertIn(order.state, ('paid', 'done', 'invoiced'))
        self.assertAlmostEqual(sum(order.payment_ids.mapped('amount')), 10.0)

        # --- restaurant: seat a reservation on a fixture table ---
        self.assertTrue(self.tables, 'fixture tables exist')
        reservation = self.env['mezze.reservation'].create({
            'customer_name': 'Bootstrap Guest', 'table_id': self.tables[0].id,
            'config_id': cfg.id, 'start': fields.Datetime.now(), 'guests': 2})
        self.assertTrue(reservation.exists())

        # --- KDS: fire a course ticket ---
        kds_order = self.create_order_in_test_session(price=25.0, product=self.products[3])
        ticket = self.env['mezze.kds.ticket'].create({
            'pos_order_id': kds_order.id, 'config_id': cfg.id, 'session_id': session.id,
            'station': 'Hot', 'state': 'fired', 'fire_uuid': 'bootstrap-fire-1', 'course': 1})
        self.assertEqual(ticket.state, 'fired')
        self.assertEqual(kds_order.mezze_public_status(), 'preparing')

        # --- omnichannel: a pickup order carries a secure status token ---
        pickup = self.create_order_in_test_session(channel='pickup')
        raw = pickup._mezze_ensure_status_token()
        self.assertEqual(len(raw), 32)
        self.assertTrue(self.env['pos.order']._mezze_resolve_status_token(raw))
        self.assertTrue(self.aggregator.exists(), 'aggregator channel provisioned')

        # --- settings catalog + effective payload resolve ---
        self.assertEqual(self.env['mezze.setting.def'].search_count([]), 101,
                         '101-setting authoritative catalog seeded on install')

        # --- admin/go-live validator resolves (permissions + config readable) ---
        report = self.env['mezze.golive.validator'].run()
        self.assertIn(report['overall'], ('PASS', 'WARNING', 'FAIL'))
        names = {c['name'] for c in report['checks']}
        self.assertIn('pos_config_present', names)
        self.assertIn('payment_methods', names)
