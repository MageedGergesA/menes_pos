# -*- coding: utf-8 -*-
"""Counting the drawer, note by note.

The close endpoint accepted a counted TOTAL and nothing else, so the count itself
happened outside the software — on a scrap of paper beside the till — and what
Mezze recorded was somebody's arithmetic rather than the drawer.

Two properties are worth the code:

* **the total is derived from the notes, never typed alongside them.** When a client
  sends both they must agree; a total that does not match the notes behind it is not
  a count, and trusting either one silently hides whichever is wrong;
* **the breakdown is kept.** "Short by 50" is a mystery. "One 50 note missing" is
  somewhere to start, and it is the difference between recording a variance and being
  able to investigate one.

``pos.bill`` is core's model for denominations and this uses core's own rule for
which ones apply to a branch — the ones attached to the config, plus the global ones.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_denoms')
class TestDenominationCount(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'dn-tok')
        Bill = env['pos.bill'].sudo()
        cls.bills = Bill.create([
            {'name': '50', 'value': 50.0, 'pos_config_ids': [(6, 0, cls.pos_config.ids)]},
            {'name': '20', 'value': 20.0, 'pos_config_ids': [(6, 0, cls.pos_config.ids)]},
            {'name': '5', 'value': 5.0, 'pos_config_ids': [(6, 0, cls.pos_config.ids)]},
        ])
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='dn-tok')),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _preview(self):
        return self._post('/sessions/%s/close/preview' % self.pos_sess.id, {})

    def _close(self, **kw):
        return self._post('/sessions/%s/close' % self.pos_sess.id, kw)

    # -- the denominations reach the till --------------------------------
    def test_01_the_branch_denominations_are_offered(self):
        d = self._preview()
        self.assertTrue(d.get('ok'), d)
        values = [row['value'] for row in d.get('denominations') or []]
        self.assertTrue(values, 'the till is given nothing to count with')
        for v in (50.0, 20.0, 5.0):
            self.assertIn(v, values)

    def test_02_they_are_ordered_largest_first(self):
        # The order a drawer is actually counted in.
        values = [r['value'] for r in self._preview()['denominations']]
        self.assertEqual(values, sorted(values, reverse=True))

    # -- the count -------------------------------------------------------
    def test_10_a_breakdown_sets_the_counted_cash(self):
        d = self._close(denominations=[{'value': 50.0, 'count': 2},
                                       {'value': 20.0, 'count': 1}])
        self.assertTrue(d.get('ok'), d)
        self.pos_sess.invalidate_recordset()
        self.assertAlmostEqual(self.pos_sess.cash_register_balance_end_real, 120.0,
                               places=2,
                               msg='the notes counted did not become the drawer figure')

    def test_11_a_total_that_disagrees_with_the_notes_is_refused(self):
        # THE property. Trusting either one would hide whichever is wrong.
        d = self._close(counted_cash=200.0,
                        denominations=[{'value': 50.0, 'count': 2}])
        self.assertFalse(d.get('ok'))
        self.assertEqual(d.get('error'), 'count_mismatch')
        self.assertAlmostEqual(d.get('from_notes'), 100.0, places=2)
        self.pos_sess.invalidate_recordset()
        self.assertEqual(self.pos_sess.state, 'opened',
                         'a session closed on a count that did not add up')

    def test_12_a_total_that_agrees_is_accepted(self):
        d = self._close(counted_cash=100.0,
                        denominations=[{'value': 50.0, 'count': 2}])
        self.assertTrue(d.get('ok'), d)

    def test_13_a_malformed_breakdown_is_refused(self):
        d = self._close(denominations=[{'value': 'fifty', 'count': 'two'}])
        self.assertEqual(d.get('error'), 'bad_denominations')

    def test_14_counting_nothing_still_closes(self):
        # A branch that does not count by denomination must not be blocked by a
        # feature it did not ask for.
        d = self._close()
        self.assertTrue(d.get('ok'), d)

    # -- the breakdown survives ------------------------------------------
    def test_20_the_notes_are_recorded_for_the_audit(self):
        self._close(denominations=[{'value': 50.0, 'count': 2},
                                   {'value': 5.0, 'count': 3}])
        row = self.env['mezze.audit.log'].sudo().search(
            [('event', '=', 'session.close')], order='id desc', limit=1)
        self.assertTrue(row, 'the close was not audited at all')
        detail = json.loads(row.detail or '{}')
        notes = detail.get('cash_denominations')
        self.assertTrue(notes,
                        'the breakdown was discarded — a variance cannot be '
                        'investigated from a total alone')
        self.assertEqual({n['value']: n['count'] for n in notes},
                         {50.0: 2, 5.0: 3})

    def test_21_zero_counts_are_not_recorded(self):
        # Fifteen denominations of nothing is noise in an audit row.
        self._close(denominations=[{'value': 50.0, 'count': 2},
                                   {'value': 20.0, 'count': 0}])
        row = self.env['mezze.audit.log'].sudo().search(
            [('event', '=', 'session.close')], order='id desc', limit=1)
        notes = json.loads(row.detail or '{}').get('cash_denominations') or []
        self.assertEqual([n['value'] for n in notes], [50.0])
