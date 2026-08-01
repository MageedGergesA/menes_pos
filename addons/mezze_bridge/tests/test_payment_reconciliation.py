"""S2 Slice 2 — runtime payment policy, external refund provenance, and operational
settlement reconciliation. Deterministic, hermetic (no real payment provider)."""
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import MezzePosCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestRuntimePaymentPolicy(MezzePosCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        self.pm = self.card_payment_method
        self.dev = self.env['mezze.payment.device'].create({
            'name': 'CIB-01', 'code': 'CIB01', 'config_id': self.pos_config.id,
            'mode': 'external_terminal', 'integration_type': 'manual',
            'payment_method_ids': [(6, 0, self.pm.ids)]})

    def _validate(self, **kw):
        return self.pm.with_context(mezze_branch_id=self.pos_config.id).mezze_validate_payment(**kw)

    def test_device_required_missing_blocks(self):
        self.pm.device_policy = 'required'
        with self.assertRaises(UserError):
            self._validate(device=None, reference='R1')

    def test_device_required_ok(self):
        self.pm.device_policy = 'required'
        self._validate(device=self.dev, reference='R1')  # no raise

    def test_wrong_branch_device_blocked(self):
        cfg2 = self.make_second_pos_config()
        dev2 = self.env['mezze.payment.device'].create({
            'name': 'OtherBranch', 'code': 'OB1', 'config_id': cfg2.id, 'mode': 'external_terminal'})
        with self.assertRaises(UserError):
            self._validate(device=dev2)

    def test_incompatible_device_blocked(self):
        other = self.env['mezze.payment.device'].create({
            'name': 'CashOnly', 'code': 'CO1', 'mode': 'cash_machine',
            'payment_method_ids': [(6, 0, self.cash_payment_method.ids)]})
        with self.assertRaises(UserError):
            self._validate(device=other)

    def test_reference_required_missing_blocks(self):
        self.pm.reference_policy = 'required'
        with self.assertRaises(UserError):
            self._validate(reference=None)

    def test_reference_optional_ok(self):
        self.pm.reference_policy = 'optional'
        self._validate(reference=None)  # no raise

    def test_duplicate_block_policy(self):
        self.pm.reference_policy = 'optional'
        self.pm.duplicate_policy = 'block'
        # seed an existing payment with the ref
        s = self.open_test_session(); o = self.create_order_in_test_session(price=10.0)
        self.env['pos.payment'].create({'pos_order_id': o.id, 'session_id': s.id,
                                        'payment_method_id': self.pm.id, 'amount': 10.0,
                                        'payment_ref_no': 'DUPX'})
        with self.assertRaises(UserError):
            self._validate(reference='DUPX')

    def test_duplicate_block_override(self):
        self.pm.reference_policy = 'optional'; self.pm.duplicate_policy = 'block'
        s = self.open_test_session(); o = self.create_order_in_test_session(price=10.0)
        self.env['pos.payment'].create({'pos_order_id': o.id, 'session_id': s.id,
                                        'payment_method_id': self.pm.id, 'amount': 10.0,
                                        'payment_ref_no': 'DUPY'})
        r = self._validate(reference='DUPY', allow_duplicate=True)  # override -> no raise
        self.assertTrue(r['duplicates'])

    def test_duplicate_manager_approval_flag(self):
        self.pm.reference_policy = 'optional'; self.pm.duplicate_policy = 'manager_approval'
        s = self.open_test_session(); o = self.create_order_in_test_session(price=10.0)
        self.env['pos.payment'].create({'pos_order_id': o.id, 'session_id': s.id,
                                        'payment_method_id': self.pm.id, 'amount': 10.0,
                                        'payment_ref_no': 'DUPM'})
        r = self._validate(reference='DUPM')
        self.assertTrue(r['needs_manager'])


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestExternalRefundProvenance(MezzePosCase):
    fixture_profile = 'POS'

    def test_external_refund_status_lifecycle(self):
        s = self.open_test_session(); o = self.create_order_in_test_session(price=30.0)
        p = self.env['pos.payment'].create({'pos_order_id': o.id, 'session_id': s.id,
                                            'payment_method_id': self.card_payment_method.id,
                                            'amount': 30.0, 'mezze_external_refund_status': 'pending_external'})
        self.assertEqual(p.mezze_external_refund_status, 'pending_external')
        p.mezze_confirm_external_refund(reference='RFND-1')
        self.assertEqual(p.mezze_external_refund_status, 'confirmed_external')
        self.assertEqual(p.mezze_external_refund_ref, 'RFND-1')
        # idempotent re-confirm
        p.mezze_confirm_external_refund(reference='RFND-2')
        self.assertEqual(p.mezze_external_refund_ref, 'RFND-1')  # unchanged after first confirm

    def test_confirmation_source_default_manual(self):
        s = self.open_test_session(); o = self.create_order_in_test_session(price=10.0)
        p = self.env['pos.payment'].create({'pos_order_id': o.id, 'session_id': s.id,
                                            'payment_method_id': self.card_payment_method.id, 'amount': 10.0})
        self.assertEqual(p.mezze_confirmation_source, 'manual')


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestReconciliation(MezzePosCase):
    fixture_profile = 'POS'

    def _paid(self, amount, method, device=None, ref=None):
        s = self.open_test_session()
        o = self.create_order_in_test_session(price=amount)
        vals = {'pos_order_id': o.id, 'session_id': s.id, 'payment_method_id': method.id, 'amount': amount}
        if device:
            vals['mezze_device_id'] = device.id
        if ref:
            vals['payment_ref_no'] = ref
        self.env['pos.payment'].create(vals)
        o.write({'state': 'paid'})
        return s, o

    def test_build_expected_from_payments(self):
        s, _ = self._paid(100.0, self.card_payment_method)
        self._paid(50.0, self.card_payment_method, ref=None)   # same session via fixture config
        recon = self.env['mezze.payment.reconciliation'].build_for_session(s)
        line = recon.line_ids.filtered(lambda l: l.payment_method_id == self.card_payment_method)
        self.assertTrue(line)
        self.assertAlmostEqual(sum(line.mapped('expected_amount')), 150.0)

    def test_status_matched(self):
        s, _ = self._paid(80.0, self.card_payment_method)
        recon = self.env['mezze.payment.reconciliation'].build_for_session(s)
        line = recon.line_ids.filtered(lambda l: l.payment_method_id == self.card_payment_method)[:1]
        recon.record_settlement(line, 80.0, reference='SET-1', source='manual_terminal_settlement')
        self.assertEqual(line.status, 'matched')
        self.assertAlmostEqual(line.difference, 0.0)

    def test_status_short(self):
        s, _ = self._paid(80.0, self.card_payment_method)
        recon = self.env['mezze.payment.reconciliation'].build_for_session(s)
        line = recon.line_ids.filtered(lambda l: l.payment_method_id == self.card_payment_method)[:1]
        recon.record_settlement(line, 50.0, reference='S', source='manual_terminal_settlement')
        self.assertEqual(line.status, 'short')
        self.assertAlmostEqual(line.difference, -30.0)

    def test_status_over(self):
        s, _ = self._paid(80.0, self.card_payment_method)
        recon = self.env['mezze.payment.reconciliation'].build_for_session(s)
        line = recon.line_ids.filtered(lambda l: l.payment_method_id == self.card_payment_method)[:1]
        recon.record_settlement(line, 90.0, reference='S', source='manual_terminal_settlement')
        self.assertEqual(line.status, 'over')

    def test_status_missing_settlement(self):
        s, _ = self._paid(80.0, self.card_payment_method)
        recon = self.env['mezze.payment.reconciliation'].build_for_session(s)
        line = recon.line_ids.filtered(lambda l: l.payment_method_id == self.card_payment_method)[:1]
        self.assertEqual(line.status, 'missing_settlement')

    def test_finalize_requires_approval_over_tolerance(self):
        self.card_payment_method.reconciliation_tolerance = 5.0
        s, _ = self._paid(80.0, self.card_payment_method)
        recon = self.env['mezze.payment.reconciliation'].build_for_session(s)
        line = recon.line_ids[:1]
        recon.record_settlement(line, 50.0, reference='S')   # diff -30 > 5 tolerance
        with self.assertRaises(UserError):
            recon.finalize()
        recon.finalize(approved_by=self.manager_user.id)     # approved -> ok
        self.assertEqual(recon.state, 'finalized')

    def test_finalize_idempotent(self):
        s, _ = self._paid(40.0, self.card_payment_method)
        recon = self.env['mezze.payment.reconciliation'].build_for_session(s)
        line = recon.line_ids[:1]; recon.record_settlement(line, 40.0, reference='S')
        recon.finalize(); recon.finalize(); recon.finalize()   # idempotent
        self.assertEqual(recon.state, 'finalized')
        self.assertEqual(self.env['mezze.payment.reconciliation'].search_count([('session_id', '=', s.id)]), 1)

    def test_reconciliation_never_edits_payments(self):
        s, o = self._paid(80.0, self.card_payment_method)
        pay = o.payment_ids
        amt_before = sum(pay.mapped('amount'))
        recon = self.env['mezze.payment.reconciliation'].build_for_session(s)
        recon.record_settlement(recon.line_ids[:1], 50.0, reference='S')
        recon.finalize(approved_by=self.manager_user.id)
        self.assertAlmostEqual(sum(o.payment_ids.mapped('amount')), amt_before, msg='payments unchanged by reconciliation')

    def test_one_reconciliation_per_session(self):
        s, _ = self._paid(10.0, self.card_payment_method)
        r1 = self.env['mezze.payment.reconciliation'].build_for_session(s)
        r2 = self.env['mezze.payment.reconciliation'].build_for_session(s)
        self.assertEqual(r1, r2)
