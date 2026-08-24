# -*- coding: utf-8 -*-
"""Printing to an Epson ePOS printer.

Mezze printed by opening a socket to port 9100. Epson's ePOS models — the TM-i
series and TM printers behind an ePOS interface board — do not listen there at all,
so a shop that already owned Epson hardware could not print at all.

Two decisions carry the weight here, and both are tested rather than asserted in a
comment.

**One renderer, two transports.** ePOS-Print XML can describe a receipt in its own
elements. Using them would give Mezze a second receipt renderer, and two renderers
drift — the Epson at the counter and the generic printer in the kitchen would
slowly stop matching, and nobody notices until a customer holds the two side by
side. So the ESC/POS stream Mezze already renders is carried in ``<command>``, and
``test_20`` proves the bytes on both transports are the same bytes.

**An ePOS printer answers 200 for a failure.** Out of paper, cover open, no such
device: HTTP 200, and the verdict is in the body. A caller that trusts the status
line reports every empty printer in the estate as printed.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase
from ..domain import epos
from ..models import hardware_render


def _reply(success='true', code='', status='7'):
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="%s"><s:Body>'
            '<response xmlns="%s" success="%s" code="%s" status="%s"/>'
            '</s:Body></s:Envelope>' % (epos.NS_SOAP, epos.NS_EPOS,
                                        success, code, status)).encode()


class _Resp:
    def __init__(self, body, status_code=200):
        self.content = body
        self.status_code = status_code

    @property
    def text(self):
        return self.content.decode('utf-8', 'replace')


class _FakeRequests:
    """Records what was sent and answers with whatever the test scripted."""

    def __init__(self):
        self.calls = []
        self.reply = _Resp(_reply())

    def post(self, url, data=None, timeout=None, allow_redirects=None, headers=None):
        self.calls.append({'url': url, 'data': data, 'headers': headers,
                           'timeout': timeout})
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@tagged('post_install', '-at_install', 'mezze_epos')
class TestEposPrinter(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'ep-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.cash = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        cls.dish = env['product.product'].sudo().create({
            'name': 'EP Plate', 'available_in_pos': True, 'list_price': 30.0,
            'type': 'consu'})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def setUp(self):
        super().setUp()
        self.fake = _FakeRequests()
        self._orig_requests = hardware_render.requests
        hardware_render.requests = self.fake
        self._raw_sends = []
        self._orig_raw = hardware_render.raw_send

        def fake_raw(host, port, data, timeout=4):
            self._raw_sends.append({'host': host, 'port': port, 'data': bytes(data)})
            return len(data)
        hardware_render.raw_send = fake_raw
        self.addCleanup(self._restore)

    def _restore(self):
        hardware_render.requests = self._orig_requests
        hardware_render.raw_send = self._orig_raw

    def _printer(self, transport='epos', **kw):
        vals = {'name': 'EP %s %s' % (transport, len(self._raw_sends)),
                'printer_type': 'receipt', 'config_id': self.pos_config.id,
                'host': '10.20.30.40', 'width': 48, 'transport': transport,
                'active': True}
        if transport == 'epos':
            vals['port'] = 0
        vals.update(kw)
        return self.env['mezze.printer'].sudo().create(vals)

    def _order(self):
        order = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': self.dish.id, 'qty': 1,
                              'price_unit': 30.0, 'price_subtotal': 30.0,
                              'price_subtotal_incl': 30.0, 'tax_ids': [(6, 0, [])]})],
            'amount_total': 30.0, 'amount_paid': 30.0, 'amount_tax': 0.0,
            'amount_return': 0.0})
        self.env['pos.payment'].sudo().create({
            'pos_order_id': order.id, 'amount': 30.0,
            'payment_method_id': self.cash.id})
        order.write({'state': 'paid'})
        self.env.flush_all()
        return order

    def _print(self, order, printer):
        r = self.url_open('/mezze/hardware/print/receipt',
                          data=json.dumps({'token': 'ep-tok', 'order_id': order.id,
                                           'printer_id': printer.id}),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    # ── the protocol, without a printer ───────────────────────────────────
    def test_01_the_endpoint_is_built_from_parts(self):
        url = epos.service_url('10.0.0.7', 0, device_id='local_printer')
        self.assertEqual(
            url, 'http://10.0.0.7/cgi-bin/epos/service.cgi'
                 '?devid=local_printer&timeout=10000')

    def test_02_a_printer_address_cannot_smuggle_a_url(self):
        # A stored URL is a request the server makes on behalf of whoever last
        # edited the field, and "printer address" is not reviewed like a webhook.
        for bad in ('evil.example.com/path', 'user@evil.example.com',
                    'host?x=1', ''):
            with self.assertRaises(ValueError, msg='accepted %r' % bad):
                epos.service_url(bad)

    def test_03_a_device_id_cannot_smuggle_a_query(self):
        with self.assertRaises(ValueError):
            epos.service_url('10.0.0.7', device_id='local_printer&x=1')

    def test_04_the_envelope_carries_the_bytes_unchanged(self):
        raw = b'\x1b\x40Hello\n\x1d\x56\x00'
        body = epos.build_envelope(raw).decode()
        self.assertIn('<command>%s</command>' % raw.hex(), body)
        self.assertIn(epos.NS_EPOS, body)

    # ── a printer that says no ────────────────────────────────────────────
    def test_10_out_of_paper_is_not_a_successful_print(self):
        # THE trap. HTTP 200, and the paper never moved.
        with self.assertRaises(epos.EposError) as caught:
            epos.parse_response(_reply('false', 'EPTR_REC_EMPTY'))
        self.assertEqual(caught.exception.code, 'EPTR_REC_EMPTY')
        self.assertFalse(caught.exception.permanent,
                         'a roll of paper is a transient problem')

    def test_11_a_malformed_envelope_is_permanent(self):
        # Retrying our own bug against the printer forever helps nobody.
        with self.assertRaises(epos.EposError) as caught:
            epos.parse_response(_reply('false', 'SchemaError'))
        self.assertTrue(caught.exception.permanent)

    def test_12_an_unknown_code_is_retried_rather_than_dropped(self):
        with self.assertRaises(epos.EposError) as caught:
            epos.parse_response(_reply('false', 'EPTR_SOMETHING_NEW'))
        self.assertFalse(caught.exception.permanent,
                         'an unfamiliar code should cost a retry, not a receipt')

    def test_13_a_page_that_is_not_epos_at_all_is_a_failure(self):
        # A login page or a proxy error document is not a print.
        with self.assertRaises(epos.EposError):
            epos.parse_response(b'<html><body>Sign in</body></html>')
        with self.assertRaises(epos.EposError):
            epos.parse_response(b'not xml at all')

    # ── the transport, end to end ─────────────────────────────────────────
    def test_20_both_transports_send_the_same_bytes(self):
        # One renderer. If this ever fails, Mezze has grown a second one.
        order = self._order()
        raw_printer = self._printer(transport='raw', port=9100)
        self.assertTrue(self._print(order, raw_printer).get('sent'))
        epos_printer = self._printer(transport='epos')
        self.assertTrue(self._print(order, epos_printer).get('sent'))

        self.assertEqual(len(self._raw_sends), 1, 'the raw path did not run')
        self.assertEqual(len(self.fake.calls), 1, 'the ePOS path did not run')
        body = self.fake.calls[0]['data'].decode()
        start = body.index('<command>') + len('<command>')
        sent_over_http = bytes.fromhex(body[start:body.index('</command>')])
        self.assertEqual(sent_over_http, self._raw_sends[0]['data'],
                         'the two transports printed different receipts')

    def test_21_a_raw_printer_never_touches_http(self):
        self._print(self._order(), self._printer(transport='raw', port=9100))
        self.assertFalse(self.fake.calls, 'a 9100 printer was sent an HTTP request')

    def test_22_an_epos_printer_never_touches_the_socket(self):
        self._print(self._order(), self._printer(transport='epos'))
        self.assertFalse(self._raw_sends, 'an ePOS printer was sent raw bytes')

    def test_23_the_request_goes_to_the_configured_device(self):
        self._print(self._order(), self._printer(transport='epos',
                                                 epos_device_id='kitchen_1'))
        self.assertIn('devid=kitchen_1', self.fake.calls[0]['url'])
        self.assertIn('10.20.30.40', self.fake.calls[0]['url'])

    def test_24_a_refusal_reaches_the_till_as_a_refusal(self):
        # "Unreachable" would send a cashier to check the network cable when the
        # drawer of paper is what is empty.
        self.fake.reply = _Resp(_reply('false', 'EPTR_COVER_OPEN'))
        res = self._print(self._order(), self._printer(transport='epos'))
        self.assertFalse(res.get('ok'), res)
        self.assertEqual(res.get('error'), 'printer_error')
        self.assertEqual(res.get('code'), 'EPTR_COVER_OPEN')
        self.assertFalse(res.get('sent'))

    def test_25_a_refusal_still_returns_the_paper_text(self):
        # Something has to be handed to the guest while the roll is changed.
        self.fake.reply = _Resp(_reply('false', 'EPTR_REC_EMPTY'))
        res = self._print(self._order(), self._printer(transport='epos'))
        self.assertIn('preview', res)
        self.assertIn('EP Plate', res['preview'])

    def test_26_an_unreachable_epos_printer_reads_as_unreachable(self):
        self.fake.reply = OSError('no route to host')
        res = self._print(self._order(), self._printer(transport='epos'))
        self.assertEqual(res.get('error'), 'printer_unreachable')

    def test_27_an_http_error_is_not_a_print(self):
        self.fake.reply = _Resp(b'<html>401</html>', status_code=401)
        res = self._print(self._order(), self._printer(transport='epos'))
        self.assertFalse(res.get('ok'), res)
        self.assertEqual(res.get('error'), 'printer_error')
