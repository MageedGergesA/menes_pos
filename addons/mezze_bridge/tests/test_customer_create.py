"""Creating a customer from the till.

The Register could only ever SEARCH for a customer, so a first-time walk-in could
not be attached to an order at all — the cashier had to leave the POS and create the
partner in the back office. These tests cover the endpoint that closes that gap:
it must create a real res.partner the search can then find, must not require more
than a name, and must not quietly mint a duplicate every time the same guest walks
in.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestCustomerCreate(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'cn-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(dict(body, token='cn-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def test_create_makes_a_real_partner(self):
        code, res = self._post('/customer/create',
                               {'name': 'Walk In Nadia', 'phone': '+201000000123'})
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('ok'), res)
        pid = res['customer']['id']
        partner = self.env['res.partner'].browse(pid)
        self.assertTrue(partner.exists())
        self.assertEqual(partner.name, 'Walk In Nadia')
        self.assertEqual(partner.phone, '+201000000123')
        # customer_rank is what marks a partner as a customer — without it the till's
        # own search would not find the guest it just created.
        self.assertGreaterEqual(partner.customer_rank, 1)

    def test_created_customer_is_findable_by_search(self):
        _c, res = self._post('/customer/create', {'name': 'Findable Fady', 'phone': '0100999888'})
        pid = res['customer']['id']
        code, found = self._post('/customer/search', {'q': 'Findable'})
        self.assertEqual(code, 200, found)
        self.assertIn(pid, [c['id'] for c in found.get('customers', [])])

    def test_name_is_the_only_requirement(self):
        code, res = self._post('/customer/create', {'name': 'No Phone Nour'})
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('ok'), res)
        self.assertEqual(self.env['res.partner'].browse(res['customer']['id']).name, 'No Phone Nour')

    def test_blank_name_is_refused(self):
        code, res = self._post('/customer/create', {'name': '   ', 'phone': '0101'})
        self.assertEqual(code, 400)
        self.assertEqual(res.get('error'), 'name_required')

    def test_same_guest_twice_is_not_duplicated(self):
        # A cashier who does not find a guest often types the details again rather than
        # searching harder. Returning the existing partner keeps one ledger per guest.
        _a, first = self._post('/customer/create', {'name': 'Repeat Rana', 'phone': '01234567'})
        _b, second = self._post('/customer/create', {'name': 'Repeat Rana', 'phone': '01234567'})
        self.assertEqual(first['customer']['id'], second['customer']['id'])
        self.assertTrue(second.get('existing'))
        self.assertEqual(self.env['res.partner'].search_count(
            [('name', '=', 'Repeat Rana')]), 1)

    def test_same_name_different_phone_is_a_different_guest(self):
        _a, first = self._post('/customer/create', {'name': 'Ahmed Ali', 'phone': '0111'})
        _b, second = self._post('/customer/create', {'name': 'Ahmed Ali', 'phone': '0222'})
        self.assertNotEqual(first['customer']['id'], second['customer']['id'])

    def test_create_requires_authorisation(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.api_security', 'enforce')
        self.env.flush_all()
        r = self.url_open('/mezze/api/v1/customer/create',
                          data=json.dumps({'name': 'Unauthorised Umar'}),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        self.assertIn(r.status_code, (401, 403), r.text[:200])
        self.assertFalse(self.env['res.partner'].search([('name', '=', 'Unauthorised Umar')]))

    def test_a_same_named_supplier_is_not_reused_as_the_guest(self):
        # Name alone is weak evidence. Attaching the order to a same-named supplier
        # would bill the wrong account, so a nameless-phone match must not cross over.
        vendor = self.env['res.partner'].create(
            {'name': 'Hassan Kamal', 'supplier_rank': 1, 'customer_rank': 0})
        _c, res = self._post('/customer/create', {'name': 'Hassan Kamal'})
        self.assertNotEqual(res['customer']['id'], vendor.id)
        self.assertFalse(res.get('existing'))
        self.assertGreaterEqual(
            self.env['res.partner'].browse(res['customer']['id']).customer_rank, 1)
