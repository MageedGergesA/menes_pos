"""Screen 01's guest panel — what a search RESULT carries (design v3).

The prototype shows points and a tag on every row (`{{ g.pts }}`, the tag chip),
not only after a guest is attached. That is the moment the information is worth
something: a cashier choosing between two regulars needs to tell them apart
BEFORE committing one to the check.

Also pinned here: a lookup must never MINT a loyalty card. `_loyalty_card()`
creates one by default, so searching with it would hand a card to everyone whose
name happened to match three typed letters.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestGuestPanel(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'gp-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.Partner = self.env['res.partner'].sudo()
        self.tag = self.env['res.partner.category'].sudo().create({'name': 'VIP'})
        self.guest = self.Partner.create({
            'name': 'Nadia Panel', 'phone': '01001234567', 'customer_rank': 1,
            'category_id': [(6, 0, [self.tag.id])]})
        self.plain = self.Partner.create({
            'name': 'Omar Panel', 'phone': '01007654321', 'customer_rank': 1})
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='gp-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def _row(self, res, partner):
        return next((c for c in res.get('customers', []) if c['id'] == partner.id), None)

    def test_01_a_result_carries_points_and_tags(self):
        code, res = self._post('/customer/search', {'query': 'Panel'})
        self.assertEqual(code, 200, res)
        row = self._row(res, self.guest)
        self.assertTrue(row, "the guest is not in the results: %s" % str(res)[:200])
        self.assertIn('points', row, "a cashier cannot tell two regulars apart")
        self.assertIn('tags', row, "the tag chip has nothing to read")
        self.assertEqual(row['tags'], ['VIP'])

    def test_02_a_guest_with_no_tags_returns_an_empty_list(self):
        """Not None, not absent — the template does `c.tags.length`."""
        _, res = self._post('/customer/search', {'query': 'Omar Panel'})
        row = self._row(res, self.plain)
        self.assertEqual(row['tags'], [])

    def test_03_the_balance_is_the_real_card_balance(self):
        prog = self.env['loyalty.program'].sudo().search(
            [('program_type', '=', 'loyalty')], limit=1)
        if not prog:
            self.skipTest("no loyalty programme on this fixture")
        self.env['loyalty.card'].sudo().create({
            'program_id': prog.id, 'partner_id': self.guest.id, 'points': 250.0})
        _, res = self._post('/customer/search', {'query': 'Nadia Panel'})
        self.assertEqual(self._row(res, self.guest)['points'], 250.0)

    def test_04_searching_never_mints_a_loyalty_card(self):
        """_loyalty_card() creates by default. Looking someone up must not hand
        a card to everyone whose name matched three typed letters."""
        Card = self.env['loyalty.card'].sudo()
        before = Card.search_count([('partner_id', '=', self.plain.id)])
        self._post('/customer/search', {'query': 'Panel'})
        self._post('/customer/search', {'query': 'Omar'})
        self.assertEqual(Card.search_count([('partner_id', '=', self.plain.id)]), before,
                         "a search created a loyalty card")

    def test_05_a_guest_with_no_card_reads_zero_not_missing(self):
        _, res = self._post('/customer/search', {'query': 'Omar Panel'})
        row = self._row(res, self.plain)
        self.assertEqual(row['points'], 0.0, "an absent card must read as 0, not None")

    def test_06_the_row_renders_all_three(self):
        with open(self.ROOT_XML, encoding='utf-8') as f:
            xml = f.read()
        for hook in ('mz-cust-row-tag', 'mz-cust-row-pts', 'dir="ltr"'):
            self.assertIn(hook, xml, "the result row is missing %r" % hook)

    @property
    def ROOT_XML(self):
        import os
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static/src/cashier/root.xml')
