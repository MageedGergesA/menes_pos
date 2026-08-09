"""R2A CP12 — Pilot / go-live readiness (software-executed proofs).

Covers the readiness LOGIC changed/added for CP12:
  * the read-only DATA-integrity validator (mezze.golive.validator.integrity)
    detects the concrete CP1–CP11 anomalies and passes on clean data;
  * the go-live CONFIG validator passes a valid base config and FAILs an
    incomplete one (never green on an empty deployment);
  * a deterministic software shift reconciles (payments == completed totals);
  * the public health endpoint leaks no secret/internal config.

Install/upgrade/backup/restore/multi-worker are execution-level gates proven in
the CP12 report, not unit tests.
"""
import json
import re

from odoo import fields
from odoo.tests import tagged

from .common import MezzeHttpCase

_BOOT_RE = re.compile(r'<script[^>]*id="mezze-boot"[^>]*>(.*?)</script>', re.DOTALL)


@tagged('post_install', '-at_install', 'mezze_floor')
class TestPilotReadiness(MezzeHttpCase):
    fixture_profile = 'RESTAURANT'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product.write({'available_in_pos': True, 'list_price': 42.0, 'taxes_id': [(5, 0, 0)]})
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        sess = cls.pos_config.current_session_id
        if not sess or sess.state not in ('opened', 'opening_control'):
            sess = cls.env['pos.session'].create(
                {'config_id': cls.pos_config.id, 'user_id': cls.env.uid})
        if sess.state == 'opening_control':
            try:
                sess.set_opening_control(0, None)
            except Exception:  # noqa: BLE001
                pass
        cls.psession = sess
        cls.V = cls.env['mezze.golive.validator']

    # -- helpers -----------------------------------------------------------
    def _order(self, qty=1, table=None, channel=None, config=None, session=None):
        cfg = config or self.pos_config
        vals = {'session_id': (session or self.psession).id, 'config_id': cfg.id,
                'company_id': cfg.company_id.id, 'state': 'draft', 'amount_tax': 0.0,
                'amount_paid': 0.0, 'amount_return': 0.0, 'amount_total': 42.0 * qty,
                'pricelist_id': cfg.pricelist_id.id or False,
                'lines': [(0, 0, {'product_id': self.product.id, 'qty': qty, 'price_unit': 42.0,
                                  'price_subtotal': 42.0 * qty, 'price_subtotal_incl': 42.0 * qty,
                                  'tax_ids': [(6, 0, [])]})]}
        if table is not None:
            vals['table_id'] = table.id
        if channel:
            vals['mezze_channel'] = channel
        return self.env['pos.order'].sudo().create(vals)

    def _pay(self, order, amount, method):
        order.add_payment({'amount': amount, 'payment_method_id': method.id,
                           'pos_order_id': order.id, 'name': fields.Datetime.now()})

    def _status_of(self, result, name):
        return next((c['status'] for c in result['checks'] if c['name'] == name), None)

    # -- integrity validator ----------------------------------------------
    def test_integrity_clean_fixture_no_critical(self):
        r = self.V.integrity()
        self.assertIn(r['overall'], ('PASS', 'WARNING'),
                      'a clean fixture must not report a critical integrity failure: %s'
                      % [c for c in r['checks'] if c['status'] == 'FAIL'])

    def test_integrity_detects_two_drafts_on_one_table(self):
        self._order(1, table=self.tables[0])
        self._order(1, table=self.tables[0])   # a second live draft on the same table
        r = self.V.integrity()
        self.assertEqual(self._status_of(r, 'one_draft_per_table'), 'FAIL')
        self.assertEqual(r['overall'], 'FAIL')

    def test_integrity_detects_cross_branch_reservation_order(self):
        other = self.make_second_pos_config()
        osess = self.env['pos.session'].create({'config_id': other.id, 'user_id': self.env.uid})
        if osess.state == 'opening_control':
            osess.set_opening_control(0, None)
        foreign_order = self._order(1, config=other, session=osess)
        res = self.env['mezze.reservation'].sudo().create({
            'table_id': self.tables[0].id, 'config_id': self.pos_config.id,
            'start': fields.Datetime.now(), 'guests': 2, 'customer_name': 'X',
            'pos_order_id': foreign_order.id})   # link to another branch's order
        self.assertTrue(res)
        r = self.V.integrity()
        self.assertEqual(self._status_of(r, 'reservation_order_same_branch'), 'FAIL')

    def test_integrity_detects_orphan_delivery(self):
        self.env['mezze.delivery'].sudo().create({
            'customer_name': 'Orphan', 'payment_mode': 'cod', 'address': 'nowhere',
            'state': 'accepted'})   # no pos_order_id
        r = self.V.integrity()
        self.assertEqual(self._status_of(r, 'delivery_has_order'), 'FAIL')

    # -- go-live config validator -----------------------------------------
    def test_go_live_validator_valid_base_config_passes_required(self):
        r = self.V.run('counter')   # counter service: cash/card at the till
        for req in ('pos_config_present', 'payment_methods', 'journals'):
            self.assertEqual(self._status_of(r, req), 'PASS',
                             '%s must PASS on a valid base config' % req)

    def test_go_live_validator_rejects_incomplete_config(self):
        # archive every POS config -> an empty deployment must NOT be green
        self.env['pos.config'].sudo().search([]).write({'active': False})
        r = self.V.run('counter')
        self.assertEqual(self._status_of(r, 'pos_config_present'), 'FAIL')
        self.assertEqual(r['overall'], 'FAIL',
                         'validator must never report GO on a config-less deployment')

    # -- deterministic shift reconciliation -------------------------------
    def test_deterministic_shift_reconciles(self):
        o1 = self._order(2, table=self.tables[0])          # 84 cash
        self._pay(o1, 84.0, self.cash_payment_method)
        o1.action_pos_order_paid()
        o2 = self._order(1, channel='pickup')              # 42 card
        self._pay(o2, 42.0, self.card_payment_method)
        o2.action_pos_order_paid()
        o3 = self._order(2, table=self.tables[1])          # partial 20, stays draft
        self._pay(o3, 20.0, self.cash_payment_method)
        completed = self.env['pos.order'].sudo().search(
            [('session_id', '=', self.psession.id), ('state', 'in', ('paid', 'done', 'invoiced'))])
        gross = round(sum(completed.mapped('amount_total')), 2)
        tenders = round(sum(completed.mapped('payment_ids.amount')), 2)
        self.assertEqual(gross, 126.0, 'completed gross 84 + 42')
        self.assertEqual(tenders, 126.0, 'settled tenders reconcile to completed gross (no variance)')
        # the partial order is still open and NOT counted in the completed shift
        o3.invalidate_recordset()
        self.assertEqual(o3.state, 'draft')
        self.assertAlmostEqual(o3.amount_paid, 20.0, places=2)

    # -- public surface safety --------------------------------------------
    def test_public_health_exposes_no_secret(self):
        self.authenticate('admin', 'admin')
        resp = self.url_open('/mezze/api/v1/health')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(set(data.keys()), {'ok', 'odoo', 'module'},
                         'health must expose only liveness fields, no config/secret')
        blob = json.dumps(data).lower()
        for leak in ('token', 'secret', 'key', 'password', 'db_'):
            self.assertNotIn(leak, blob, 'health leaked %r' % leak)
