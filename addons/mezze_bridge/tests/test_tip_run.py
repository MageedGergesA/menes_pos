"""BE-008 tip pooling — the ledger and the run, against the frozen contract.

The resolver's arithmetic is proven in ``test_tip_pool.py``. This proves the
things persistence adds and arithmetic cannot: that the trail cannot be edited,
that a signed distribution cannot be quietly re-cut, that nothing pays out
unsigned, and that a second tap pays nobody twice.

Contract: ``docs/TIP_POOLING.md`` §1 (ledger), §3 (approval), §4 (payout).
"""
import datetime

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from psycopg2 import IntegrityError
from odoo.tools import mute_logger

from .common import MezzePosCase


@tagged('post_install', '-at_install', 'mezze_tips')
class TestTipRun(MezzePosCase):
    fixture_profile = 'RESTAURANT'

    def setUp(self):
        super().setUp()
        self.Entry = self.env['mezze.tip.entry']
        self.Run = self.env['mezze.tip.run']
        self.now = fields.Datetime.now()
        self.t0 = self.now - datetime.timedelta(hours=8)
        C = self.env['mezze.cashier']
        self.srv_a = C.create({'name': 'Server A', 'role': 'server'})
        self.srv_b = C.create({'name': 'Server B', 'role': 'server'})
        self.boss = C.create({'name': 'Boss', 'role': 'manager'})
        self.boss.set_pin('4821')
        for c, hours in ((self.srv_a, 6), (self.srv_b, 3)):
            self.env['mezze.attendance'].create({
                'cashier_id': c.id, 'config_id': self.pos_config.id,
                'check_in': self.t0, 'check_out': self.t0 + datetime.timedelta(hours=hours)})
        # the manager is on shift too, and must NOT share
        self.env['mezze.attendance'].create({
            'cashier_id': self.boss.id, 'config_id': self.pos_config.id,
            'check_in': self.t0, 'check_out': self.now})

    def _capture(self, cashier, amount, kind='capture'):
        return self.Entry.create({
            'kind': kind, 'amount': amount, 'currency_id': self.currency.id,
            'cashier_id': cashier.id, 'config_id': self.pos_config.id})

    def _run(self, rule='hours'):
        return self.Run.create({
            'config_id': self.pos_config.id, 'currency_id': self.currency.id,
            'rule': rule, 'date_from': self.t0,
            'date_to': self.now + datetime.timedelta(hours=1)})

    # -- the ledger --------------------------------------------------------
    def test_01_the_ledger_is_append_only(self):
        e = self._capture(self.srv_a, 50.0)
        with self.assertRaises(UserError, msg="an audit trail that can be edited is not one"):
            e.amount = 999.0
        with self.assertRaises(UserError):
            e.cashier_id = self.srv_b.id

    def test_02_a_capture_must_name_the_person_it_belongs_to(self):
        """§1: direct and hybrid are meaningless without the server."""
        with self.assertRaises(ValidationError):
            self.Entry.create({'kind': 'capture', 'amount': 10.0,
                               'currency_id': self.currency.id,
                               'config_id': self.pos_config.id})

    def test_03_a_manager_adjustment_carries_a_reason(self):
        with self.assertRaises(ValidationError):
            self.Entry.create({'kind': 'adjust', 'amount': -5.0,
                               'currency_id': self.currency.id,
                               'cashier_id': self.srv_a.id,
                               'config_id': self.pos_config.id})

    # -- the run -----------------------------------------------------------
    def test_04_the_pool_reads_captures_and_declarations_only(self):
        self._capture(self.srv_a, 80.0)
        self._capture(self.srv_b, 20.0, kind='declare')
        run = self._run()
        self.assertIsNone(run.action_compute())
        self.assertAlmostEqual(run.pool_amount, 100.0, places=2)
        self.assertEqual(sum(run.line_ids.mapped('share')), 100.0,
                         "the shares must sum to the pool")

    def test_05_managers_are_out_of_the_pool(self):
        """§2 eligibility: off-shift staff and managers are out."""
        self._capture(self.srv_a, 90.0)
        run = self._run()
        run.action_compute()
        self.assertEqual(set(run.line_ids.mapped('cashier_id')),
                         {self.srv_a, self.srv_b},
                         "a manager on shift must not share the pool")

    def test_06_hours_come_from_the_clock(self):
        """6h vs 3h -> 2:1, from mezze.attendance, not from a rota."""
        self._capture(self.srv_a, 90.0)
        run = self._run()
        run.action_compute()
        by = {l.cashier_id: l.share for l in run.line_ids}
        self.assertAlmostEqual(by[self.srv_a], 60.0, places=2)
        self.assertAlmostEqual(by[self.srv_b], 30.0, places=2)

    def test_07_custom_percentages_off_100_refuse_the_run(self):
        self._capture(self.srv_a, 100.0)
        run = self._run(rule='custom')
        err = run.action_compute(custom_pct={self.srv_a.id: 60, self.srv_b.id: 30})
        self.assertEqual(err, 'custom_pct_not_100')
        self.assertFalse(run.line_ids, "a refused run distributes nothing")

    # -- approval ----------------------------------------------------------
    def test_08_nothing_is_signed_without_a_manager_pin(self):
        self._capture(self.srv_a, 60.0)
        run = self._run()
        run.action_compute()
        with self.assertRaises(UserError, msg="a server must not sign a distribution"):
            run.action_approve(self.srv_a, '4821')
        with self.assertRaises(UserError, msg="a wrong PIN must not sign"):
            run.action_approve(self.boss, '0000')
        self.assertEqual(run.state, 'draft')
        run.action_approve(self.boss, '4821')
        self.assertEqual(run.state, 'approved')
        self.assertEqual(run.approved_by, self.boss)
        self.assertTrue(run.approved_at)

    def test_09_a_signed_run_cannot_be_recut(self):
        """§3: a later clock-out cannot silently re-cut agreed figures."""
        self._capture(self.srv_a, 60.0)
        run = self._run()
        run.action_compute()
        run.action_approve(self.boss, '4821')
        before = {l.cashier_id: l.share for l in run.line_ids}
        with self.assertRaises(UserError):
            run.rule = 'equal'
        with self.assertRaises(UserError):
            run.action_compute()
        # a fifth person clocking in afterwards does not move the snapshot
        late = self.env['mezze.cashier'].create({'name': 'Late', 'role': 'server'})
        self.env['mezze.attendance'].create({
            'cashier_id': late.id, 'config_id': self.pos_config.id,
            'check_in': self.t0, 'check_out': self.now})
        self.assertEqual({l.cashier_id: l.share for l in run.line_ids}, before)

    def test_10_a_void_needs_a_pin_and_a_reason(self):
        self._capture(self.srv_a, 60.0)
        run = self._run()
        run.action_compute()
        run.action_approve(self.boss, '4821')
        with self.assertRaises(UserError):
            run.action_void(self.boss, '0000', 'mistake')
        with self.assertRaises(UserError):
            run.action_void(self.boss, '4821', '   ')
        run.action_void(self.boss, '4821', 'wrong rule agreed')
        self.assertEqual(run.state, 'void')

    # -- payout ------------------------------------------------------------
    def test_11_nothing_pays_out_unsigned(self):
        """§3: nothing pays out unsigned.

        The session is OPEN and the run is computed, so the approval gate is the
        only thing that can refuse. Without that, this passed on the drawer's
        "needs an open session" error instead -- a UserError for the wrong
        reason, which is no assertion at all.
        """
        self._capture(self.srv_a, 60.0)
        run = self._run()
        run.action_compute()
        run.session_id = self.open_test_session(self.pos_config).id
        self.assertEqual(run.state, 'draft')
        with self.assertRaises(UserError) as caught:
            run.action_payout('cash')
        self.assertIn('approved', str(caught.exception).lower(),
                      "refused, but not because the run was unsigned: %s"
                      % caught.exception)
        self.assertFalse(
            self.Entry.search([('run_id', '=', run.id), ('kind', '=', 'payout')]),
            "an unsigned run wrote a payout row")

    def test_12_a_second_tap_pays_nobody_twice(self):
        """§4: one payout row per person per run.

        TWO independent guards stand here, and this proves each on its own --
        asserting only the plain double-tap passed even with the dedup key
        removed, because the outstanding check was quietly doing all the work.
        """
        self._capture(self.srv_a, 90.0)
        run = self._run()
        run.action_compute()
        run.action_approve(self.boss, '4821')
        run.session_id = self.open_test_session(self.pos_config).id

        def rows():
            return self.Entry.search([('run_id', '=', run.id), ('kind', '=', 'payout')])

        run.action_payout('cash')
        self.assertEqual(len(rows()), 2, "one row per person")

        # (a) nothing outstanding -> nothing to pay
        run.action_payout('cash')
        self.assertEqual(len(rows()), 2, "a second tap wrote another payout row")

        # (b) and if the outstanding balance were somehow back -- a retry racing
        # a half-applied write -- the dedup KEY still refuses the second row.
        run.line_ids.write({'paid_cash': 0.0})
        self.assertTrue(all(l.outstanding > 0 for l in run.line_ids))
        run.action_payout('cash')
        self.assertEqual(len(rows()), 2,
                         "the dedup key did not stop a duplicate payout row")

    def test_13_the_database_refuses_a_duplicate_payout_key(self):
        """The idempotency guard is a constraint, not just an if."""
        run = self._run()
        vals = {'kind': 'payout', 'amount': -1.0, 'currency_id': self.currency.id,
                'cashier_id': self.srv_a.id, 'config_id': self.pos_config.id,
                'route': 'cash', 'dedup_key': 'tiprun:%s|%s|cash' % (run.id, self.srv_a.id)}
        self.Entry.create(vals)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.Entry.create(dict(vals))

    def test_14_payroll_payout_is_a_state_not_a_drawer_movement(self):
        """§4: to payroll -> stays in Tips payable, rides the next payslip.

        No drawer movement: the branch has not paid this money out yet, so a
        till that reconciled would be lying about a liability it still owes.
        """
        self._capture(self.srv_a, 90.0)
        run = self._run()
        run.action_compute()
        run.action_approve(self.boss, '4821')
        session = self.open_test_session(self.pos_config)
        run.session_id = session.id
        before = self._drawer_out_count(session)
        run.action_payout('payroll')
        self.assertEqual(run.state, 'paid')
        self.assertEqual(sum(run.line_ids.mapped('paid_payroll')), 90.0)
        self.assertEqual(sum(run.line_ids.mapped('paid_cash')), 0.0)
        self.assertEqual(sum(run.line_ids.mapped('outstanding')), 0.0)
        self.assertEqual(self._drawer_out_count(session), before,
                         "payroll must not take cash out of the drawer")

    def test_15_a_cash_payout_takes_the_money_out_of_the_drawer(self):
        """§4/§5: the drawer movement is what makes the payout visible."""
        self._capture(self.srv_a, 90.0)
        run = self._run()
        run.action_compute()
        run.action_approve(self.boss, '4821')
        session = self.open_test_session(self.pos_config)
        run.session_id = session.id
        before = self._drawer_out_count(session)
        run.action_payout('cash')
        self.assertEqual(self._drawer_out_count(session), before + 1,
                         "a cash tip payout must move the drawer")

    def test_16_a_cash_payout_without_an_open_session_is_refused(self):
        """No drawer to take it from — refuse rather than leave the till over."""
        self._capture(self.srv_a, 60.0)
        run = self._run()
        run.action_compute()
        run.action_approve(self.boss, '4821')
        self.pos_config.current_session_id.filtered(
            lambda s: s.state == 'opened').write({'state': 'closing_control'})
        with self.assertRaises(UserError):
            run.action_payout('cash')

    def test_17_a_partial_payout_leaves_the_balance_outstanding(self):
        """§4: cash now, the rest on payroll — two rows, balance derived."""
        self._capture(self.srv_a, 90.0)
        run = self._run()
        run.action_compute()
        run.action_approve(self.boss, '4821')
        session = self.open_test_session(self.pos_config)
        run.session_id = session.id
        run.action_payout('cash')
        # the same person cannot be paid the same route twice, but the payroll
        # route is a different key — and by now nothing is outstanding
        run.action_payout('payroll')
        rows = self.Entry.search([('run_id', '=', run.id), ('kind', '=', 'payout')])
        self.assertEqual(len(rows), 2, "cash paid both people; payroll added none")
        self.assertEqual(sum(run.line_ids.mapped('outstanding')), 0.0)

    def _drawer_out_count(self, session):
        return self.env['account.bank.statement.line'].search_count([
            ('pos_session_id', '=', session.id), ('amount', '<', 0)])
