"""P1 — go-live readiness: the config validator runs and returns a structured,
launch-blocking report; the hardened status-token lifecycle is enforced."""
from odoo.tests import common, tagged


@tagged('post_install', '-at_install', 'mezze_invariants')
class TestGoLiveValidator(common.TransactionCase):

    def test_validator_runs_structured(self):
        r = self.env['mezze.golive.validator'].run()
        self.assertIn(r['overall'], ('PASS', 'WARNING', 'FAIL'))
        self.assertGreaterEqual(r['total'], 10)
        names = {c['name'] for c in r['checks']}
        for expect in ('master_key_present', 'status_token_ttl', 'shared_admin_disabled',
                       'pos_config_present', 'payment_methods', 'settings_catalog'):
            self.assertIn(expect, names)
        for c in r['checks']:
            self.assertIn(c['status'], ('PASS', 'WARNING', 'FAIL', 'N/A'))

    def test_report_text(self):
        txt = self.env['mezze.golive.validator'].report_text()
        self.assertIn('MEZZE GO-LIVE CONFIG VALIDATOR', txt)
        self.assertIn('status_token_ttl', txt)


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestStatusTokenLifecycle(common.TransactionCase):

    def setUp(self):
        super().setUp()
        self.cfg = self.env['pos.config'].search([], limit=1)

    def _order(self):
        s = (self.env['pos.session'].sudo().search([('config_id', '=', self.cfg.id), ('state', '=', 'opened')], limit=1)
             or self.env['pos.session'].sudo().create({'config_id': self.cfg.id, 'user_id': self.env.uid}))
        p = self.env['product.product'].search([], limit=1)
        return self.env['pos.order'].sudo().create({
            'session_id': s.id, 'company_id': self.cfg.company_id.id,
            'lines': [(0, 0, {'product_id': p.id, 'qty': 1, 'price_unit': 10.0,
                              'price_subtotal': 10.0, 'price_subtotal_incl': 10.0, 'tax_ids': [(6, 0, [])]})],
            'amount_total': 10.0, 'amount_paid': 0.0, 'amount_tax': 0.0, 'amount_return': 0.0,
            'pricelist_id': self.cfg.pricelist_id.id or False, 'mezze_channel': 'pickup'})

    def test_hash_stored_not_raw(self):
        o = self._order()
        raw = o._mezze_ensure_status_token()
        self.assertEqual(len(raw), 32)
        self.assertNotEqual(o.mezze_status_token, raw)     # only the hash is stored
        self.assertTrue(self.env['pos.order']._mezze_resolve_status_token(raw))

    def test_expiry_and_revocation(self):
        from datetime import timedelta
        from odoo import fields
        o = self._order()
        raw = o._mezze_ensure_status_token()
        # expired token no longer resolves
        o.mezze_status_expiry = fields.Datetime.now() - timedelta(minutes=1)
        self.assertFalse(self.env['pos.order']._mezze_resolve_status_token(raw))
        # fresh token, then revoke
        o2 = self._order()
        raw2 = o2._mezze_ensure_status_token()
        self.assertTrue(self.env['pos.order']._mezze_resolve_status_token(raw2))
        o2.mezze_revoke_status_token()
        self.assertFalse(self.env['pos.order']._mezze_resolve_status_token(raw2))
