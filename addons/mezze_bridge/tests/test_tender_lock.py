"""S1-08 — a check the server will not accept edits for must SAY so.

`/orders/sync` correctly refuses to rewrite a check that already carries a
recorded tender: `_updatable_draft` requires `not existing.payment_ids`, so the
money side was never at risk. The defect was what the till was told about the
refusal — nothing.

The route answered ``{'ok': True, 'duplicate': True}`` and dropped the cart that
was sent. No cashier client has ever read `duplicate`, so `ok` was taken as
success: the cashier edited a line on a part-paid check, saw no complaint, and
handed the guest a bill the server had refused. The state is reachable and the
code says so — root.js: "CP9 partial recall: a resumed order may already carry
tenders."

That is the same defect as an unseen collision, in a different place, and the
design answers it the same way: the prototype locks the line and states the
reason (`L.tenderLocked` — "Covered by a recorded tender. Editing needs manager
approval.").

NOT built: the manager override the prototype's escalate button implies. There
is no endpoint that reverses a recorded tender on an OPEN check — `/orders/void`
is for unpaid orders and `/orders/refund` for completed ones — so a button
offering it would promise what the backend cannot do. Recorded as an open
decision in the gap register instead.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestTenderLock(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.shared = 'tenderlock-token'
        ICP.set_param('mezze_bridge.api_token', self.shared)
        ICP.set_param('mezze_bridge.api_security', 'observe')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session(self.pos_config)
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token=self.shared)),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def _sync(self, uuid, qty=2):
        return self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'draft': True,
            'lines': [{'product_id': self.product.id, 'qty': qty}]})

    def _part_pay(self, uuid, amount=1.0, key='tl-t1'):
        method = self.pos_config.payment_method_ids[:1]
        return self._post('/orders/pay', {
            'uuid': uuid, 'payment_method_id': method.id,
            'amount': amount, 'tender_key': key})

    def test_01_a_tendered_check_still_refuses_the_edit(self):
        """The money side, unchanged: this must keep being refused."""
        self._sync('tl-refuse')
        code, pay = self._part_pay('tl-refuse')
        self.assertEqual(code, 200, pay)
        code, res = self._sync('tl-refuse', qty=9)
        self.assertEqual(code, 200, res)
        order = self.env['pos.order'].search([('uuid', '=', 'tl-refuse')], limit=1)
        order.invalidate_recordset()
        self.assertEqual(sum(order.lines.mapped('qty')), 2,
                         'the tendered check was rewritten — a financial hole')

    def test_02_the_refusal_says_why(self):
        """`ok` alone reads as success. Without a reason the till cannot tell a
        harmless idempotent replay from its edit being thrown away."""
        self._sync('tl-why')
        self._part_pay('tl-why', key='tl-t2')
        _, res = self._sync('tl-why', qty=9)
        self.assertTrue(res.get('duplicate'), res)
        self.assertEqual(res.get('edits_refused'), 'tendered',
                         'the till is told nothing about why its cart was dropped')
        self.assertGreater(res.get('tendered_amount') or 0, 0,
                           'the notice cannot say what is covered')

    def test_03_an_untouched_check_is_not_reported_as_locked(self):
        """A guard that always fires tells the cashier nothing."""
        _, first = self._sync('tl-clean')
        self.assertIsNone(first.get('edits_refused'), first)
        _, second = self._sync('tl-clean', qty=5)
        self.assertIsNone(second.get('edits_refused'),
                          'an ordinary edit was reported as refused')
        order = self.env['pos.order'].search([('uuid', '=', 'tl-clean')], limit=1)
        order.invalidate_recordset()
        self.assertEqual(sum(order.lines.mapped('qty')), 5,
                         'an ordinary edit did not land')

    def test_04_a_settled_check_reports_its_own_reason(self):
        self._sync('tl-settled')
        method = self.pos_config.payment_method_ids[:1]
        code, res = self._post('/orders/pay', {
            'uuid': 'tl-settled', 'payment_method_id': method.id,
            'amount': self.env['pos.order'].search(
                [('uuid', '=', 'tl-settled')], limit=1).amount_total,
            'tender_key': 'tl-t4'})
        self.assertEqual(code, 200, res)
        _, out = self._sync('tl-settled', qty=9)
        self.assertIn(out.get('edits_refused'), ('settled', 'tendered'), out)

    def test_05_a_replay_that_edits_nothing_is_not_a_refusal(self):
        """draft=False on an existing uuid is the genuine idempotent replay this
        branch was written for. Reporting it as a refusal would put a lock on the
        cashier's screen for a check nobody is being stopped from editing."""
        self._sync('tl-replay')
        _, res = self._post('/orders/sync', {
            'uuid': 'tl-replay', 'session_id': self.session.id,
            'lines': [{'product_id': self.product.id, 'qty': 2}]})
        self.assertIsNone(res.get('edits_refused'), res)


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestTenderLockSurface(MezzeHttpCase):
    """The till half: a refusal the cashier cannot see is not a refusal."""
    fixture_profile = 'CORE'

    import os as _os
    ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))

    def _src(self, rel):
        import os
        with open(os.path.join(self.ROOT, rel), encoding='utf-8') as f:
            return f.read()

    def test_20_the_till_reads_the_refusal(self):
        src = self._src('static/src/cashier/root.js')
        self.assertIn('edits_refused', src,
                      'the till still cannot tell a refusal from a success')
        self.assertIn('editLock', src, 'nothing holds the refusal')

    def test_21_the_lock_is_shown_with_its_reason(self):
        xml = self._src('static/src/cashier/components/cart.xml')
        self.assertIn('mz-edit-lock', xml, 'the lock is never drawn')
        self.assertIn('props.editLockMessage', xml,
                      'the lock is drawn without saying why')
        js = self._src('static/src/cashier/root.js')
        self.assertIn('Covered by a recorded tender', js,
                      "the design's own words for this state are missing")

    def test_22_the_lock_is_translated(self):
        po = self._src('i18n/ar.po')
        for en in ('Covered by a recorded tender. This check can no longer be edited here.',
                   'This check is already settled, so it can no longer be edited.',
                   'This check has been split, so its items are managed on the split checks.'):
            self.assertIn('msgid "%s"' % en, po, '%r has no Arabic' % en[:40])

    def test_23_a_new_cart_does_not_inherit_the_lock(self):
        """Every place the till drops its order uuid starts a different check."""
        src = self._src('static/src/cashier/root.js')
        self.assertGreaterEqual(
            src.count('this.state.editLock = null;'),
            src.count('this.state.orderUuid = null;'),
            'a cart was cleared while still showing the previous check as locked')
