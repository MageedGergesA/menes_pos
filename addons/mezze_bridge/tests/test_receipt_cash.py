"""Wave 3 — the printed receipt, and reconciling the drawer.

Two areas where Mezze read almost nothing Odoo already knew.

**The receipt.** ``receipt_header``, ``receipt_footer`` and ``basic_receipt`` are
core config fields Mezze never read. The paper ticket carried no company address, no
tax-registration number, one blended ``Tax`` line where the screen showed a per-rate
split, no cashier, no change, and — because the ESC/POS layer had no barcode command
at all — no QR. A ZATCA or ETA receipt *is* a QR receipt, so that last one is not a
polish item; it is the reason the paper could not satisfy either authority.

**The drawer.** ``/sessions/<id>/close`` accepted no counted amount. It computed what
the drawer should hold and told the cashier to count it outside the software, so
Mezze could not reconcile its own till: ``cash_register_difference`` was only ever
READ, in one GL report, and ``set_maximum_difference`` was never read at all. There
was no cash in/out anywhere, and the close — the most consequential act of a shift —
wrote no audit row while eighty lesser events did.
"""
import json

from odoo.tests import TransactionCase, tagged

from ..domain import escpos
from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_receipt')
class TestEscposQr(TransactionCase):
    """The barcode command the layer did not have."""

    def test_01_a_qr_emits_real_gs_k_bytes(self):
        tk = escpos.Ticket(48)
        tk.qr('https://example.test/inv/1', 'Scan to verify')
        raw = tk.to_escpos()
        self.assertIn(b'\x1d\x28\x6b', raw,
                      'no GS ( k in the stream — this is not a QR')

    def test_02_the_payload_reaches_the_printer(self):
        tk = escpos.Ticket(48)
        tk.qr('TLV-PAYLOAD-XYZ')
        self.assertIn(b'TLV-PAYLOAD-XYZ', tk.to_escpos())

    def test_03_an_empty_payload_prints_nothing(self):
        tk = escpos.Ticket(48)
        tk.qr('')
        self.assertNotIn(b'\x1d\x28\x6b', tk.to_escpos())

    def test_04_the_text_preview_describes_the_qr_instead_of_dumping_it(self):
        # A preview cannot show a QR. Printing the signed payload as text would give
        # a cashier a wall of characters to try to read.
        tk = escpos.Ticket(48)
        tk.qr('SIGNED-TLV-DO-NOT-PRINT', 'Scan to verify')
        text = tk.to_text()
        self.assertIn('Scan to verify', text)
        self.assertNotIn('SIGNED-TLV-DO-NOT-PRINT', text)


@tagged('post_install', '-at_install', 'mezze_receipt')
class TestReceiptContent(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        self.session = self.open_test_session()
        self.company = self.pos_config.company_id
        self.company.write({'vat': 'EG123456789', 'street': '12 Nile St',
                            'city': 'Cairo', 'phone': '+20 100 000 0000'})
        self.pos_config.write({'receipt_header': 'Welcome to Mezze',
                               'receipt_footer': 'Keep this receipt'})
        self.env.flush_all()

    def _ticket(self, order, **kw):
        from ..models import hardware_render
        return hardware_render.receipt_ticket(order, 48, **kw).to_text()

    def test_10_the_header_and_footer_are_printed(self):
        order = self.create_order_in_test_session(session=self.session, price=10.0)
        text = self._ticket(order)
        self.assertIn('Welcome to Mezze', text, 'receipt_header was never read')
        self.assertIn('Keep this receipt', text, 'receipt_footer was never read')

    def test_11_the_tax_registration_number_is_on_the_paper(self):
        order = self.create_order_in_test_session(session=self.session, price=10.0)
        self.assertIn('EG123456789', self._ticket(order),
                      'no tax registration on the printed receipt')

    def test_12_the_company_address_is_on_the_paper(self):
        order = self.create_order_in_test_session(session=self.session, price=10.0)
        text = self._ticket(order)
        self.assertIn('12 Nile St', text)
        self.assertIn('Cairo', text)

    def test_13_a_gift_receipt_shows_no_prices(self):
        order = self.create_order_in_test_session(session=self.session, price=42.50)
        text = self._ticket(order, gift=True)
        self.assertNotIn('42.50', text, 'a gift receipt that shows the price is not one')
        self.assertIn('Gift receipt', text)

    def test_14_a_normal_receipt_does_show_the_price(self):
        order = self.create_order_in_test_session(session=self.session, price=42.50)
        self.assertIn('42.50', self._ticket(order))

    def test_15_a_tax_qr_reaches_the_paper(self):
        order = self.create_order_in_test_session(session=self.session, price=10.0)
        from ..models import hardware_render
        raw = hardware_render.receipt_ticket(
            order, 48, tax_qr='ZATCA-TLV-BLOB').to_escpos()
        self.assertIn(b'\x1d\x28\x6b', raw)
        self.assertIn(b'ZATCA-TLV-BLOB', raw)

    def test_16_the_line_note_is_printed(self):
        order = self.create_order_in_test_session(session=self.session, price=10.0)
        if 'customer_note' in order.lines._fields:
            order.lines[0].write({'customer_note': 'no ice'})
            self.assertIn('no ice', self._ticket(order),
                          'the kitchen instruction never reached the paper')

    def test_17_the_tax_label_follows_the_country(self):
        from ..models.hardware_render import _vat_label
        sa = self.env['res.country'].search([('code', '=', 'SA')], limit=1)
        eg = self.env['res.country'].search([('code', '=', 'EG')], limit=1)
        if sa:
            self.company.country_id = sa
            self.assertEqual(_vat_label(self.company), 'VAT No.')
        if eg:
            self.company.country_id = eg
            self.assertEqual(_vat_label(self.company), 'Tax Reg.')


@tagged('post_install', '-at_install', 'mezze_cash')
class TestCashControl(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'cash-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session()
        self.mgr = self.env['mezze.cashier'].create(
            {'name': 'Mona', 'code': 'CSH9', 'role': 'manager'})
        self.mgr.set_pin('4321')
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='cash-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def _audits(self, event):
        return self.env['mezze.audit.log'].sudo().search([('event', '=', event)])

    # ── counted cash ─────────────────────────────────────────────────────────
    def test_20_the_close_accepts_a_counted_amount(self):
        code, res = self._post('/sessions/%s/close' % self.session.id,
                               {'counted_cash': 100.0})
        self.assertEqual(code, 200, res)
        self.assertIsNotNone(res.get('cash_difference'),
                             'the drawer was never reconciled')

    def test_21_the_discrepancy_is_computed(self):
        expected_start = self.session.cash_register_balance_start or 0.0
        code, res = self._post('/sessions/%s/close' % self.session.id,
                               {'counted_cash': expected_start + 7.0})
        self.assertEqual(code, 200, res)
        self.assertAlmostEqual(res['cash_difference'], 7.0, places=2)

    def test_22_closing_without_a_count_still_works(self):
        # A branch that does not count must not be blocked from closing.
        code, res = self._post('/sessions/%s/close' % self.session.id, {})
        self.assertEqual(code, 200, res)
        self.assertIsNone(res.get('cash_difference'))

    def test_23_a_variance_over_the_ceiling_needs_a_manager(self):
        self.pos_config.write({'set_maximum_difference': True,
                               'amount_authorized_diff': 5.0})
        start = self.session.cash_register_balance_start or 0.0
        code, res = self._post('/sessions/%s/close' % self.session.id,
                               {'counted_cash': start + 50.0})
        self.assertEqual(code, 403, res)
        self.assertEqual(res.get('error'), 'variance_requires_approval')
        self.session.invalidate_recordset()
        self.assertNotEqual(self.session.state, 'closed',
                            'a refused close still closed the session')

    def test_24_a_manager_pin_clears_the_variance(self):
        self.pos_config.write({'set_maximum_difference': True,
                               'amount_authorized_diff': 5.0})
        start = self.session.cash_register_balance_start or 0.0
        code, res = self._post('/sessions/%s/close' % self.session.id,
                               {'counted_cash': start + 50.0,
                                'manager_code': 'CSH9', 'manager_pin': '4321'})
        self.assertEqual(code, 200, res)

    def test_25_a_small_variance_needs_nobody(self):
        self.pos_config.write({'set_maximum_difference': True,
                               'amount_authorized_diff': 50.0})
        start = self.session.cash_register_balance_start or 0.0
        code, res = self._post('/sessions/%s/close' % self.session.id,
                               {'counted_cash': start + 2.0})
        self.assertEqual(code, 200, res)

    def test_26_the_close_writes_an_audit_row(self):
        before = len(self._audits('session.close'))
        self._post('/sessions/%s/close' % self.session.id, {'counted_cash': 10.0})
        rows = self._audits('session.close')
        self.assertEqual(len(rows), before + 1,
                         'the most consequential act of a shift left no trail')
        detail = json.loads(rows[-1].detail or '{}')
        self.assertIn('cash_expected', detail)
        self.assertIn('cash_counted', detail)

    # ── cash in / out ────────────────────────────────────────────────────────
    def test_30_cash_can_be_taken_out_of_the_drawer(self):
        code, res = self._post('/sessions/%s/cash_move' % self.session.id,
                               {'direction': 'out', 'amount': 20.0,
                                'reason': 'paid the milk supplier'})
        self.assertEqual(code, 200, res)
        self.assertEqual(res['direction'], 'out')

    def test_31_cash_can_be_put_in(self):
        code, res = self._post('/sessions/%s/cash_move' % self.session.id,
                               {'direction': 'in', 'amount': 50.0,
                                'reason': 'float top-up'})
        self.assertEqual(code, 200, res)

    def test_32_a_cash_move_must_say_why(self):
        # Unexplained money leaving a till is what this record exists to prevent.
        code, res = self._post('/sessions/%s/cash_move' % self.session.id,
                               {'direction': 'out', 'amount': 20.0})
        self.assertEqual(code, 400, res)
        self.assertEqual(res.get('error'), 'reason_required')

    def test_33_a_cash_move_needs_a_positive_amount(self):
        for bad in (0, -5, 'x'):
            code, res = self._post('/sessions/%s/cash_move' % self.session.id,
                                   {'direction': 'out', 'amount': bad,
                                    'reason': 'nope'})
            self.assertEqual(code, 400, res)

    def test_34_the_direction_must_be_real(self):
        code, res = self._post('/sessions/%s/cash_move' % self.session.id,
                               {'direction': 'sideways', 'amount': 5.0,
                                'reason': 'nope'})
        self.assertEqual(code, 400, res)
        self.assertEqual(res.get('error'), 'bad_direction')

    def test_35_a_cash_move_is_audited(self):
        before = len(self._audits('session.cash_move'))
        self._post('/sessions/%s/cash_move' % self.session.id,
                   {'direction': 'out', 'amount': 15.0, 'reason': 'taxi for staff'})
        rows = self._audits('session.cash_move')
        self.assertEqual(len(rows), before + 1)
        detail = json.loads(rows[-1].detail or '{}')
        self.assertEqual(detail.get('reason'), 'taxi for staff')
        self.assertEqual(detail.get('direction'), 'out')

    def test_36_a_closed_session_takes_no_cash_moves(self):
        self.session.write({'state': 'closed'})
        code, res = self._post('/sessions/%s/cash_move' % self.session.id,
                               {'direction': 'in', 'amount': 5.0, 'reason': 'late'})
        self.assertEqual(code, 400, res)
        self.assertEqual(res.get('error'), 'session_closed')
