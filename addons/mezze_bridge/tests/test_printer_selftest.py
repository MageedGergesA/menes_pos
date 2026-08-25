# -*- coding: utf-8 -*-
"""The diagnostic has to be diagnostic.

``/mezze/hardware/test`` is the first thing anyone runs against a new printer, and
it built its ticket with a bare ``Ticket(width)`` -- so it always encoded CP437,
while every other path here (receipt, bill, kitchen, Z) carried the printer's
configured code page.

On a printer set to Arabic that self-test came out as ``?`` and read as broken
hardware. It is the worst way for a diagnostic to fail: it accuses equipment that
works, and it sends whoever is holding the printer off to debug a fault that is
in the test.

Two things are pinned here. The first is that the endpoint uses the printer's own
settings. The second is that the ticket contains a sample of the script the code
page exists for -- because a test print encoded in CP1256 that only ever emits
ASCII proves nothing about whether the printer has CP1256 in ROM, which is the
single question the operator is asking.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase

ARABIC_LETTER = 'ق'


@tagged('post_install', '-at_install', 'mezze_hardware')
class TestPrinterSelfTest(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'st-tok')
        # No host: every case below reads the PREVIEW, so nothing dials out.
        cls.latin = env['mezze.printer'].sudo().create({
            'name': 'Front Latin', 'printer_type': 'receipt',
            'config_id': cls.pos_config.id, 'width': 48, 'codepage': 'cp437'})
        cls.arabic = env['mezze.printer'].sudo().create({
            'name': 'Front Arabic', 'printer_type': 'receipt',
            'config_id': cls.pos_config.id, 'width': 32, 'codepage': 'cp1256'})
        env.flush_all()

    def _test_print(self, printer=None):
        body = {'token': 'st-tok', 'preview': True}
        if printer:
            body['printer_id'] = printer.id
        r = self.url_open('/mezze/hardware/test', data=json.dumps(body),
                          headers={'Content-Type': 'application/json'})
        self.assertEqual(r.status_code, 200, r.text[:200])
        return r.json()

    # ── the printer's own settings ───────────────────────────────────────
    def test_01_the_code_page_is_the_printers_own(self):
        res = self._test_print(self.arabic)
        self.assertTrue(res.get('ok'), res)
        self.assertIn('cp1256', res['preview'],
                      'the self-test did not report the configured code page: %r'
                      % res.get('preview'))
        self.assertNotIn('cp437', res['preview'],
                         'the self-test fell back to CP437 on an Arabic printer')

    def test_02_the_width_is_the_printers_own(self):
        res = self._test_print(self.arabic)
        self.assertIn('32 chars', res['preview'], res['preview'])
        for line in res['preview'].splitlines():
            self.assertLessEqual(len(line), 32,
                                 'a line overran 58mm paper: %r' % line)

    def test_03_the_escpos_number_actually_sent_is_on_the_paper(self):
        """Vendors disagree about ESC t n, Arabic especially.

        The number that was really sent belongs next to the result it produced,
        so it can be read off the printout instead of deduced from a table.
        """
        res = self._test_print(self.arabic)
        self.assertIn('ESC t 50', res['preview'], res['preview'])

    def test_04_an_explicit_number_overrides_the_usual_one(self):
        self.arabic.sudo().write({'codepage_id': 22})
        res = self._test_print(self.arabic)
        self.assertIn('ESC t 22', res['preview'], res['preview'])

    # ── the sample is the point ──────────────────────────────────────────
    def test_10_an_arabic_printer_gets_arabic_on_the_paper(self):
        """THE finding. CP1256 that only ever emits ASCII proves nothing."""
        res = self._test_print(self.arabic)
        self.assertIn(ARABIC_LETTER, res['preview'],
                      'the self-test never emitted a byte of the script the code '
                      'page exists for: %r' % res['preview'])

    def test_11_the_sample_reaches_the_printer_as_that_code_page(self):
        # The real proof is in the bytes, not the preview: a '?' here is the
        # printer being asked for a character the page cannot carry.
        from ..domain.escpos import Ticket
        raw = Ticket(32, 'cp1256').line('قهوة عربية').to_escpos()
        self.assertNotIn(b'?', raw,
                         'Arabic was substituted away before it reached the printer')

    def test_12_a_latin_printer_gets_no_arabic(self):
        # A Latin site must not be handed a line it cannot read and did not ask
        # for. The rest of the ticket is already a Latin sample.
        res = self._test_print(self.latin)
        self.assertNotIn(ARABIC_LETTER, res['preview'], res['preview'])
        self.assertIn('cp437', res['preview'])

    def test_13_no_printer_still_previews(self):
        # The endpoint is also how you check the layout with nothing plugged in.
        res = self._test_print(None)
        self.assertTrue(res.get('ok'), res)
        self.assertFalse(res.get('sent'))
        self.assertIn('wired correctly', res['preview'])

    # ── the regression itself ────────────────────────────────────────────
    def test_20_the_self_test_agrees_with_the_receipt_path(self):
        """The two must not drift again.

        The bug was that one printing path knew about the printer and another did
        not. Pinned as a relationship rather than a constant: whatever the code
        page is, the diagnostic must be encoded the same way as the receipts it
        is diagnosing.
        """
        from ..models import hardware_render
        for printer in (self.latin, self.arabic):
            with self.subTest(printer=printer.name):
                receipt = hardware_render.receipt_ticket(
                    self.env['pos.order'], printer.width,
                    encoding=printer.codepage,
                    codepage_id=printer.codepage_id or None)
                res = self._test_print(printer)
                self.assertIn(receipt.encoding, res['preview'],
                              'the self-test and the receipt disagree about the '
                              'code page for %s' % printer.name)
                self.assertIn('ESC t %s' % receipt.codepage_id, res['preview'],
                              'the self-test and the receipt disagree about the '
                              'ESC t number for %s' % printer.name)
