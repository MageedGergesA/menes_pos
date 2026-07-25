"""Runtime verification of the FSM lifecycle guard INSIDE a running Odoo server.

Converts the contract-level guard tests into runtime-observed evidence:
  * TestGuardRuntime (TransactionCase) — the real controller adapter runs against
    real pos.order records and writes real mezze.audit.log rows, for pay/refund/
    comp/fire across off/observe/enforce, with DB-level assertions.
  * TestGuardHttp (HttpCase) — a real HTTP POST to /mezze/api/v1/orders/pay drives
    the full stack (auth -> _api_env -> order_pay -> _fsm_guard -> audit).

Run:
  odoo-bin -d <db> -c <conf> -u mezze_bridge --test-enable \
           --test-tags mezze_runtime --stop-after-init

Tagged `mezze_runtime` so it does not run with the pure `mezze_invariants` suites.
"""

import json

from odoo.tests import tagged
from odoo.addons.mezze_bridge.controllers.main import MezzeBridgeController, FSM_GUARD_PARAM

from .common import MezzeHttpCase, MezzePosCase

ALLOWLIST = {
    "operation", "server_state", "mapped_event", "reason", "reason_code",
    "mode", "observe_proceeded", "endpoint", "order_id", "order_uuid",
    "branch_id", "company_id", "actor_uid", "correlation_id", "ts",
}


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestGuardRuntime(MezzePosCase):
    """The real controller adapter, exercised against real records + audit rows."""

    fixture_profile = 'POS'

    def _make_order(self, state):
        """Create a real pos.order in the requested lifecycle state."""
        session = self.open_test_session()
        cfg = self.pos_config
        order = self.env['pos.order'].create({
            'session_id': session.id, 'company_id': cfg.company_id.id,
            'amount_tax': 0.0, 'amount_total': 0.0, 'amount_paid': 0.0, 'amount_return': 0.0,
            'lines': [], 'pricelist_id': cfg.pricelist_id.id or False,
        })
        if order.state != state:
            order.write({'state': state})
        return order

    def setUp(self):
        super().setUp()
        self.ctrl = MezzeBridgeController()
        self.ICP = self.env['ir.config_parameter'].sudo()
        self.Audit = self.env['mezze.audit.log'].sudo()
        self.paid = self._make_order('paid')
        self.draft = self._make_order('draft')

    def _violations(self):
        return self.Audit.search_count([('event', '=', 'order.fsm_violation')])

    def _guard(self, mode, order, op):
        self.ICP.set_param(FSM_GUARD_PARAM, mode)
        n0 = self._violations()
        res = self.ctrl._fsm_guard(self.env, order, op, endpoint='orders/%s' % op)
        return res, self._violations() - n0

    # (op, forbidden_order, allowed_order) — sourced from the FSM, not restated.
    def _cases(self):
        return [
            ('pay', self.paid, self.draft),
            ('refund', self.draft, self.paid),   # refund forbidden on unpaid
            ('comp', self.paid, self.draft),
            ('fire', self.paid, self.draft),
        ]

    def test_off_mode_full_bypass(self):
        for op, forbidden, _ in self._cases():
            res, delta = self._guard('off', forbidden, op)
            self.assertIsNone(res, "off must not block %s" % op)
            self.assertEqual(delta, 0, "off must NOT write an audit row for %s" % op)

    def test_observe_records_but_does_not_block(self):
        for op, forbidden, _ in self._cases():
            res, delta = self._guard('observe', forbidden, op)
            self.assertIsNone(res, "observe must not block %s" % op)
            self.assertEqual(delta, 1, "observe must record exactly one violation for %s" % op)

    def test_enforce_blocks_forbidden_and_allows_valid(self):
        for op, forbidden, allowed in self._cases():
            res, delta = self._guard('enforce', forbidden, op)
            self.assertIsInstance(res, dict, "enforce must reject %s" % op)
            self.assertEqual(res.get('error'), 'forbidden_transition')
            self.assertFalse(res.get('ok'))
            self.assertEqual(delta, 1)
            # allowed transition must pass and write nothing
            res2, delta2 = self._guard('enforce', allowed, op)
            self.assertIsNone(res2, "enforce must allow valid %s" % op)
            self.assertEqual(delta2, 0)

    def test_audit_row_is_real_and_allowlisted(self):
        self._guard('observe', self.paid, 'pay')
        row = self.Audit.search([('event', '=', 'order.fsm_violation')], order='id desc', limit=1)
        self.assertTrue(row, "a real audit row must exist")
        self.assertEqual(row.severity, 'warning')
        self.assertEqual(row.res_model, 'pos.order')
        self.assertEqual(row.res_id, self.paid.id)
        detail = json.loads(row.detail)
        self.assertLessEqual(set(detail), ALLOWLIST, "telemetry escaped the allowlist")
        self.assertEqual(detail['server_state'], 'paid')
        self.assertEqual(detail['operation'], 'pay')
        self.assertEqual(detail['reason_code'], 'forbidden_transition')
        # no PAN-like value anywhere in the telemetry
        import re
        for v in detail.values():
            self.assertFalse(re.search(r'\d{12,19}', str(v)), "possible PAN in telemetry")

    def test_missing_order_does_not_crash(self):
        self.ICP.set_param(FSM_GUARD_PARAM, 'enforce')
        empty = self.env['pos.order']
        self.assertIsNone(self.ctrl._fsm_guard(self.env, empty, 'pay', endpoint='orders/pay'))

    def test_audit_write_persists_in_transaction(self):
        self.ICP.set_param(FSM_GUARD_PARAM, 'observe')
        n0 = self._violations()
        self.ctrl._fsm_guard(self.env, self.paid, 'pay', endpoint='orders/pay')
        self.env.flush_all()
        self.assertEqual(self._violations(), n0 + 1, "audit row must be part of the transaction")


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestGuardHttp(MezzeHttpCase):
    """Full HTTP stack: real POST to /orders/pay drives auth -> guard -> audit."""

    fixture_profile = 'POS'

    def _make_order(self, state):
        """Create a real pos.order in the requested lifecycle state."""
        session = self.open_test_session()
        cfg = self.pos_config
        order = self.env['pos.order'].create({
            'session_id': session.id, 'company_id': cfg.company_id.id,
            'amount_tax': 0.0, 'amount_total': 0.0, 'amount_paid': 0.0, 'amount_return': 0.0,
            'lines': [], 'pricelist_id': cfg.pricelist_id.id or False,
        })
        if order.state != state:
            order.write({'state': state})
        return order

    def setUp(self):
        super().setUp()
        self.token = 'runtime-test-token'
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', self.token)
        self.Audit = self.env['mezze.audit.log'].sudo()
        self.paid = self._make_order('paid')
        self.env.flush_all()

    def _post_pay(self, mode):
        self.env['ir.config_parameter'].sudo().set_param(FSM_GUARD_PARAM, mode)
        self.env.flush_all()
        n0 = self.Audit.search_count([('event', '=', 'order.fsm_violation')])
        resp = self.url_open(
            '/mezze/api/v1/orders/pay',
            data=json.dumps({'uuid': self.paid.uuid, 'token': self.token}),
            headers={'Content-Type': 'application/json', 'X-Mezze-Token': self.token},
            timeout=30,
        )
        try:
            body = resp.json()
        except Exception:
            body = {'_raw': resp.text[:300]}
        delta = self.Audit.search_count([('event', '=', 'order.fsm_violation')]) - n0
        return resp.status_code, body, delta

    def test_enforce_rejects_pay_of_paid_over_http(self):
        status, body, delta = self._post_pay('enforce')
        self.assertEqual(status, 200)
        self.assertFalse(body.get('ok'), body)
        self.assertEqual(body.get('error'), 'forbidden_transition', body)
        self.assertGreaterEqual(delta, 1, "a real audit row must be written")
        # no partial mutation: the order is unchanged (still paid, no new payment)
        self.assertEqual(self.paid.state, 'paid')
        self.assertFalse(self.paid.payment_ids)

    def test_observe_preserves_behavior_over_http(self):
        status, body, delta = self._post_pay('observe')
        self.assertEqual(status, 200)
        # legacy behavior preserved: an already-paid order returns already=True
        self.assertTrue(body.get('ok'), body)
        self.assertTrue(body.get('already'), body)
        self.assertGreaterEqual(delta, 1, "observe still records the violation")

    def test_off_writes_no_audit_over_http(self):
        status, body, delta = self._post_pay('off')
        self.assertEqual(status, 200)
        self.assertTrue(body.get('ok'), body)
        self.assertTrue(body.get('already'), body)
        self.assertEqual(delta, 0, "off mode must write NO audit row through the real endpoint")
