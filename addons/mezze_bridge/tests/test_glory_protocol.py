# -*- coding: utf-8 -*-
"""Glory cash machines, driven from the server.

**This row was wrong on the report and the correction is the point.** It said Glory
was "welded to the native browser store, so Mezze cannot reuse it" — and separately
that Odoo's IoT hardware proxy "does not exist in Community". Checked at last:
``pos_glory_cash``, ``iot_base`` and ``iot_drivers`` are all in the Community tree
under LGPL-3. The DRIVER is browser-side JavaScript, so its code genuinely cannot be
reused by a product that drives hardware from the server. The PROTOCOL is fully
readable, which is not the same thing as "cannot" and should never have been written
as if it were.

Doing it server-side is not merely a port. A cash machine is the one device in a
shop that physically holds money, and the till that happens to have a browser tab
open is the worst possible authority over it: a refreshed page should not be able to
lose track of cash mid-transaction.

The classification is where the care goes. A machine that simply refused and a
machine that **took a note and could not give the right change back** are opposite
facts about a customer's money, and Glory distinguishes them by numeric code:

* ``SUCCESS`` settles;
* ``CANCEL``, ``RESET``, ``OCCUPIED_BY_OTHER`` and friends are harmless — nothing was
  taken, the bill stays payable, the cashier tries again;
* ``CHANGE_SHORTAGE`` and its relatives are **uncertain** and are never auto-retried,
  because a second attempt against a drawer that already swallowed a note takes it
  twice.

An unfamiliar code defaults to uncertain. An unknown answer about a machine holding
cash must not be read as "no money moved".
"""
from odoo.tests import TransactionCase, tagged

from ..domain import glory as G


@tagged('post_install', '-at_install', 'mezze_glory')
class TestGloryProtocol(TransactionCase):

    # ── requests ─────────────────────────────────────────────────────────
    def test_01_a_payment_request_carries_the_amount_in_minor_units(self):
        xml = G.build('pay', 7, 'S1', amount_minor=1250)
        self.assertIn('<ChangeRequest>', xml)
        self.assertIn('<Amount>1250</Amount>', xml)
        self.assertIn('<SessionID>S1</SessionID>', xml)

    def test_02_the_sequence_number_is_zero_padded_as_the_device_expects(self):
        self.assertIn('<SeqNo>00000000007</SeqNo>', G.build('status', 7, 'S1'))

    def test_03_the_trailing_nul_is_part_of_the_wire_format(self):
        # A device that never sees it waits for the rest of a message that has
        # already been sent.
        self.assertTrue(G.build('status', 1, 'S1').endswith('\x00'))

    def test_04_a_payment_with_no_amount_is_refused_before_it_is_sent(self):
        for bad in (None, 0, -5):
            with self.assertRaises(G.GloryError):
                G.build('pay', 1, 'S1', amount_minor=bad)

    def test_05_an_unknown_request_is_refused(self):
        with self.assertRaises(G.GloryError):
            G.build('teleport', 1, 'S1')

    # ── responses ────────────────────────────────────────────────────────
    def test_10_a_settled_payment_reads_as_settled(self):
        name, root = G.parse('<ChangeResponse result="0"><Amount>1250</Amount></ChangeResponse>')
        self.assertEqual(name, 'SUCCESS')
        self.assertEqual(G.amount_in(root), 1250)

    def test_11_a_cancelled_payment_took_nothing(self):
        with self.assertRaises(G.GloryError) as c:
            G.parse('<ChangeResponse result="1"/>')
        self.assertEqual(c.exception.name, 'CANCEL')
        self.assertFalse(c.exception.uncertain,
                         'a cancel was treated as money that might be held')

    def test_12_a_change_shortage_is_uncertain(self):
        """THE case. The machine took the money and could not give change back."""
        with self.assertRaises(G.GloryError) as c:
            G.parse('<ChangeResponse result="10"/>')
        self.assertEqual(c.exception.name, 'CHANGE_SHORTAGE')
        self.assertTrue(c.exception.uncertain,
                        'a machine holding cash was reported as a clean refusal')

    def test_13_every_uncertain_code_stays_uncertain(self):
        for code in (9, 10, 12, 13, 100, 11):
            with self.assertRaises(G.GloryError) as c:
                G.parse('<ChangeResponse result="%d"/>' % code)
            self.assertTrue(c.exception.uncertain,
                            '%s was not treated as uncertain' % c.exception.name)

    def test_14_a_code_nobody_has_seen_defaults_to_uncertain(self):
        # An unknown answer about a machine holding cash must not read as "no
        # money moved".
        with self.assertRaises(G.GloryError) as c:
            G.parse('<ChangeResponse result="777"/>')
        self.assertTrue(c.exception.uncertain)

    def test_15_something_that_is_not_a_glory_response_is_a_failure(self):
        # A captive portal or a proxy answers with SOMETHING.
        for junk in ('<html>login</html>', 'not xml', '', '<ChangeResponse/>'):
            with self.assertRaises(G.GloryError) as c:
                G.parse(junk)
            self.assertTrue(c.exception.uncertain)

    def test_16_device_padding_is_stripped_before_parsing(self):
        raw = '\x00\x02<ChangeResponse result="0"><Amount>500</Amount></ChangeResponse>\x00'
        name, root = G.parse(raw)
        self.assertEqual(name, 'SUCCESS')
        self.assertEqual(G.amount_in(root), 500)

    def test_17_the_result_table_matches_the_community_module(self):
        # Copied verbatim from pos_glory_cash; pinned so a divergence is loud.
        self.assertEqual(G.RESULT[0], 'SUCCESS')
        self.assertEqual(G.RESULT[10], 'CHANGE_SHORTAGE')
        self.assertEqual(G.RESULT[21], 'INVALID_SESSION')
        self.assertEqual(G.RESULT[100], 'DEVICE_ERROR')

    def test_18_the_three_outcome_sets_do_not_overlap(self):
        # A code that is both settled and uncertain would be a coin flip.
        self.assertFalse(G.SETTLED & G.HARMLESS)
        self.assertFalse(G.SETTLED & G.UNCERTAIN)
        self.assertFalse(G.HARMLESS & G.UNCERTAIN)
