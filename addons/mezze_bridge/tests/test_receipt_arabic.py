# -*- coding: utf-8 -*-
"""Arabic on the PRINTED receipt.

Mezze's screens are fully bilingual. The paper was not, in two independent ways, and
fixing either one alone changes nothing a customer would see:

* the encoder was hardcoded to ``s.encode('cp437', 'replace')``, so every Arabic
  character became ``?`` — the product names, the customer's own name, everything;
* every label was an English literal, so even once the bytes could carry Arabic, an
  Arabic branch printed an Arabic product name under an English "Subtotal".

Both are asserted here, and the encoding is asserted at the BYTE level, because the
text preview is a Python string and will happily show Arabic that the printer will
never receive. That gap is exactly how this survived: the preview looked right.

WHAT THIS CANNOT PROVE: that a given printer renders those bytes as Arabic glyphs.
Code pages are selected with ``ESC t n`` and vendors do not agree on the numbers —
Arabic worst of all — so the number is configuration with a documented default rather
than a constant. The remaining risk is hardware and is settled with a self-test
printout, not with a test suite.
"""
from odoo.tests import tagged

from ..domain import escpos
from .common import MezzeHttpCase

ARABIC = 'شاورما دجاج'


@tagged('post_install', '-at_install', 'mezze_receipt_ar')
class TestReceiptArabicEncoding(MezzeHttpCase):
    """The bytes that reach the printer."""

    def test_01_cp437_cannot_carry_arabic(self):
        # The old behaviour, stated so the fix cannot be quietly reverted.
        tk = escpos.Ticket(32)
        tk.line(ARABIC)
        self.assertIn(b'?', tk.to_escpos(),
                      'cp437 is expected to substitute Arabic — if it does not, this '
                      'test no longer describes the default')

    def test_02_windows_1256_carries_arabic(self):
        tk = escpos.Ticket(32, 'cp1256')
        self.assertNotIn(b'?', tk.line(ARABIC).to_escpos(),
                         'cp1256 still substituted the Arabic')

    def test_02b_cp864_cannot_carry_ordinary_arabic(self):
        """Pinned because it is a trap, not because it is desirable.

        CP864 is the obvious-looking choice — it is literally the "Arabic" code page
        — but it maps the Arabic PRESENTATION forms (U+FE80…), not the letters as
        they are stored. ``'ﺵ'.encode('cp864')`` succeeds; ``'ش'.encode('cp864')``
        does not. So text taken from Odoo cannot be encoded into it without being
        shaped first, and selecting it produces a receipt full of '?' that looks
        exactly like the bug this work fixed.

        It stays in the list because some printers support nothing else, and the
        field help says plainly what it costs. Windows-1256 is the one to use.
        """
        tk = escpos.Ticket(32, 'cp864')
        self.assertIn(b'?', tk.line(ARABIC).to_escpos(),
                      'if cp864 now carries base-form Arabic, this trap is gone and '
                      'the field help should stop warning about it')

    def test_03_the_printer_is_told_which_page_to_use(self):
        # Encoding the bytes is half of it. Without ESC t n the printer decodes them
        # with whatever page it powered on with, and prints mojibake.
        tk = escpos.Ticket(32, 'cp1256')
        body = tk.line(ARABIC).to_escpos()
        self.assertIn(b'\x1b\x74', body, 'no code-page selection was emitted')
        expected = escpos.DEFAULT_CODEPAGE_ID['cp1256']
        self.assertIn(b'\x1b\x74' + bytes([expected]), body)

    def test_04_the_page_number_can_be_overridden(self):
        # Vendors disagree about these numbers, so a branch must be able to correct
        # one without a code change.
        tk = escpos.Ticket(32, 'cp1256', codepage_id=99)
        self.assertIn(b'\x1b\x74' + bytes([99]), tk.line(ARABIC).to_escpos())

    def test_05_the_selection_precedes_any_text(self):
        tk = escpos.Ticket(32, 'cp1256')
        body = tk.line(ARABIC).to_escpos()
        self.assertLess(body.index(b'\x1b\x74'), body.index(escpos.AL['l']),
                        'the code page must be selected before the first text')

    def test_06_an_unknown_encoding_still_prints(self):
        # A misconfigured printer must not cost the customer their receipt.
        tk = escpos.Ticket(32, 'not-a-codec')
        self.assertTrue(tk.line('Total 10.00').to_escpos())

    def test_07_latin_is_unchanged_by_default(self):
        # The default has to stay exactly what it was.
        tk = escpos.Ticket(32)
        self.assertIn(b'Total', tk.line('Total').to_escpos())
        self.assertIn(b'\x1b\x74\x00', tk.to_escpos())


@tagged('post_install', '-at_install', 'mezze_receipt_ar')
class TestReceiptArabicLabels(MezzeHttpCase):
    """The words printed around the numbers."""
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.env['res.lang'].sudo()._activate_lang('ar_001')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.partner = env['res.partner'].sudo().create({
            'name': 'عميل تجريبي', 'lang': 'ar_001'})
        cls.product = env['product.product'].sudo().create({
            'name': ARABIC, 'available_in_pos': True, 'list_price': 50.0,
            'type': 'consu'})
        cls.product.write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def _order(self, partner=None):
        o = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'partner_id': (partner or self.partner).id,
            'lines': [(0, 0, {'product_id': self.product.id, 'qty': 1,
                              'price_unit': 50.0, 'price_subtotal': 50.0,
                              'price_subtotal_incl': 50.0, 'tax_ids': [(6, 0, [])]})],
            'amount_total': 50.0, 'amount_paid': 50.0,
            'amount_tax': 0.0, 'amount_return': 0.0})
        self.env.flush_all()
        return o

    def test_10_labels_follow_the_customers_language(self):
        from ..models.hardware_render import receipt_ticket
        text = receipt_ticket(self._order()).to_text()
        self.assertIn('المجموع الفرعي', text,
                      'the receipt still says "Subtotal" to an Arabic customer:\n%s' % text)
        self.assertIn('الإجمالي', text, 'the total is still labelled in English')

    def test_11_the_product_name_is_arabic_too(self):
        from ..models.hardware_render import receipt_ticket
        self.assertIn(ARABIC, receipt_ticket(self._order()).to_text())

    def test_12_an_english_customer_still_gets_english(self):
        # The fallback must not have become "everything is Arabic now".
        en = self.env['res.partner'].sudo().create({'name': 'Plain Customer', 'lang': 'en_US'})
        from ..models.hardware_render import receipt_ticket
        text = receipt_ticket(self._order(en)).to_text()
        self.assertIn('Subtotal', text)
        self.assertNotIn('المجموع الفرعي', text)

    def test_13_an_arabic_receipt_survives_the_wire_on_an_arabic_printer(self):
        # End to end: Arabic labels AND Arabic content, encoded in a page that has
        # the glyphs. This is the thing the customer actually receives.
        from ..models.hardware_render import receipt_ticket
        tk = receipt_ticket(self._order(), encoding='cp1256')
        body = tk.to_escpos()
        self.assertNotIn(b'?', body,
                         'Arabic was substituted on the way to the printer')
        self.assertIn(b'\x1b\x74', body)
