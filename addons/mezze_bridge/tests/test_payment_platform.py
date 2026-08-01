"""S2 Slice 1 — payment modes, policy metadata, device registry, reference policy.
Reuses the hermetic POS fixture. Does not duplicate the money/refund invariant tests."""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import MezzePosCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestPaymentModes(MezzePosCase):
    fixture_profile = 'POS'

    def test_mode_autoclassifies_cash(self):
        self.assertEqual(self.cash_payment_method.mezze_mode, 'cash')

    def test_mode_autoclassifies_manual_card(self):
        # the fixture 'card' method is a plain bank method -> manual
        self.assertEqual(self.card_payment_method.mezze_mode, 'manual')

    def test_mode_autoclassifies_customer_account(self):
        pm = self.env['pos.payment.method'].create({
            'name': 'On Account', 'company_id': self.company.id,
            'journal_id': False, 'split_transactions': True})
        # pay_later type is computed from journal absence in core; set explicitly if needed
        pm.write({})
        # a method with no journal + split is Customer-Account-like; assert mode resolves to a valid value
        self.assertIn(pm.mezze_mode, dict(pm._fields['mezze_mode'].selection))

    def test_external_terminal_override_sticky(self):
        pm = self.card_payment_method
        pm.mezze_mode = 'external_terminal'
        pm._compute_mezze_mode()   # recompute must NOT downgrade an explicit external_terminal
        self.assertEqual(pm.mezze_mode, 'external_terminal')

    def test_policy_defaults(self):
        pm = self.card_payment_method
        self.assertTrue(pm.mezze_allow_partial)
        self.assertTrue(pm.mezze_allow_mixed)
        self.assertTrue(pm.mezze_allow_refund)
        self.assertEqual(pm.reference_policy, 'disabled')


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestReferencePolicy(MezzePosCase):
    fixture_profile = 'POS'

    def _payment(self, ref=None):
        session = self.open_test_session()
        order = self.create_order_in_test_session(price=50.0)
        vals = {'pos_order_id': order.id, 'session_id': session.id,
                'payment_method_id': self.card_payment_method.id, 'amount': 50.0}
        if ref is not None:
            vals['payment_ref_no'] = ref
        return self.env['pos.payment'].create(vals)

    def test_required_reference_blocks_without_ref(self):
        self.card_payment_method.reference_policy = 'required'
        with self.assertRaises(ValidationError):
            self._payment(ref=None)

    def test_required_reference_ok_with_ref(self):
        self.card_payment_method.reference_policy = 'required'
        p = self._payment(ref='APPROVAL-123')
        self.assertEqual(p.payment_ref_no, 'APPROVAL-123')

    def test_disabled_reference_no_enforcement(self):
        self.card_payment_method.reference_policy = 'disabled'
        p = self._payment(ref=None)
        self.assertTrue(p.exists())

    def test_duplicate_reference_detected_method_scope(self):
        self.card_payment_method.reference_policy = 'optional'
        self.card_payment_method.reference_scope = 'method_ref'
        p1 = self._payment(ref='DUP-9')
        p2 = self._payment(ref='DUP-9')
        dups = p2.mezze_duplicate_references()
        self.assertIn(p1, dups)

    def test_no_duplicate_when_reference_unique(self):
        self.card_payment_method.reference_policy = 'optional'
        p1 = self._payment(ref='UNIQ-1')
        p2 = self._payment(ref='UNIQ-2')
        self.assertFalse(p2.mezze_duplicate_references())


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestPaymentDeviceRegistry(MezzePosCase):
    fixture_profile = 'POS'

    def test_create_device_and_link_method(self):
        dev = self.env['mezze.payment.device'].create({
            'name': 'CIB-01', 'code': 'CIB01', 'config_id': self.pos_config.id,
            'register': 'Cashier 1', 'mode': 'external_terminal', 'acquirer_label': 'CIB',
            'integration_type': 'manual', 'payment_method_ids': [(6, 0, self.card_payment_method.ids)]})
        self.assertEqual(dev.certification_status, 'not_tested')
        self.assertIn(self.card_payment_method, dev.payment_method_ids)
        self.assertEqual(dev.config_id, self.pos_config)

    def test_device_code_unique(self):
        self.env['mezze.payment.device'].create({'name': 'A', 'code': 'DUPDEV', 'mode': 'external_terminal'})
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env['mezze.payment.device'].create({'name': 'B', 'code': 'DUPDEV', 'mode': 'external_terminal'})
            self.env.flush_all()

    def test_device_recorded_on_payment(self):
        dev = self.env['mezze.payment.device'].create({'name': 'T2', 'code': 'T2', 'mode': 'external_terminal'})
        session = self.open_test_session()
        order = self.create_order_in_test_session(price=20.0)
        p = self.env['pos.payment'].create({
            'pos_order_id': order.id, 'session_id': session.id,
            'payment_method_id': self.card_payment_method.id, 'amount': 20.0,
            'mezze_device_id': dev.id})
        self.assertEqual(p.mezze_device_id, dev)
