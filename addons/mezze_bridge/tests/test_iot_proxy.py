# -*- coding: utf-8 -*-
"""Talking to Odoo's own Hardware Proxy — which is in Community after all.

**The correction this file exists for.** The parity report said the IoT box "does
not exist in Community", and I repeated it many times. It is wrong: ``iot_base`` and
``iot_drivers`` — the latter literally named *Hardware Proxy* — are in the Community
tree under LGPL-3, alongside ``pos_glory_cash``. The claim was never checked.

Mezze still drives hardware server-side by design, and that decision stands: it is
what makes a printer or a scale answer to the branch rather than to whichever till
happens to have a tab open. But "we do it differently" and "it cannot be done" are
not the same sentence, and only the first one was ever true.

So the box becomes a third TRANSPORT beside raw TCP and ePOS. It earns its place on
a real case: a USB or serial printer has no address of its own, and the box is how
it gets one. The bytes are identical — the same ESC/POS Mezze renders for every
other transport, base64'd into the proxy's JSON-RPC envelope — so a receipt printed
through a box and one printed down a socket are the same receipt.

The trap is the same one ePOS has and it is tested here: the proxy answers **HTTP
200 with ``result: false``** when no printer is attached. A caller that trusts the
status line reports a print that never happened.
"""
import base64
import json

from odoo.tests import tagged

from .common import MezzeHttpCase
from ..domain import scale as scale_domain
from ..models import hardware_render


class _Resp:
    def __init__(self, payload, status_code=200):
        self._p = payload
        self.status_code = status_code

    def json(self):
        if self._p is _BAD:
            raise ValueError('nope')
        return self._p

    @property
    def text(self):
        return json.dumps(self._p) if self._p is not _BAD else 'not json'


_BAD = object()


class _FakeRequests:
    def __init__(self):
        self.calls = []
        self.reply = _Resp({'jsonrpc': '2.0', 'result': True})

    def post(self, url, json=None, data=None, timeout=None,
             allow_redirects=None, headers=None):
        self.calls.append({'url': url, 'json': json})
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@tagged('post_install', '-at_install', 'mezze_iot')
class TestIotProxy(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.printer = env['mezze.printer'].sudo().create({
            'name': 'Boxed Printer', 'printer_type': 'receipt',
            'config_id': cls.pos_config.id, 'transport': 'iot',
            'iot_url': 'http://10.0.0.5:8069', 'width': 48})
        cls.scale = env['mezze.scale'].sudo().create({
            'name': 'Boxed Scale', 'config_id': cls.pos_config.id,
            'protocol': 'iot', 'iot_url': '10.0.0.5:8069', 'uom_name': 'kg'})
        env.flush_all()

    def setUp(self):
        super().setUp()
        self.fake = _FakeRequests()
        self._orig = hardware_render.requests
        hardware_render.requests = self.fake
        self.addCleanup(self._restore)

    def _restore(self):
        hardware_render.requests = self._orig

    # ── the address is composed, never free-form ─────────────────────────
    def test_01_the_endpoint_is_built_from_parts(self):
        hardware_render.send_to_printer(self.printer, b'\x1b@hello')
        self.assertEqual(self.fake.calls[0]['url'],
                         'http://10.0.0.5:8069/hw_proxy/default_printer_action')

    def test_02_a_bare_host_gets_a_scheme(self):
        # The scale fixture is configured without one, as an operator would.
        self.fake.reply = _Resp({'jsonrpc': '2.0', 'result': {'weight': 0.4}})
        hardware_render.read_scale(self.scale)
        self.assertTrue(self.fake.calls[0]['url'].startswith('http://10.0.0.5:8069'))

    def test_03_an_address_cannot_smuggle_a_query(self):
        self.printer.sudo().write({'iot_url': 'http://box/?x=1'})
        with self.assertRaises(ValueError):
            hardware_render.send_to_printer(self.printer, b'x')

    # ── printing ─────────────────────────────────────────────────────────
    def test_10_the_same_bytes_go_through_the_box(self):
        """One renderer. A boxed receipt and a socketed one are the same receipt."""
        payload = b'\x1b@MEZZE\n\x1dV\x00'
        hardware_render.send_to_printer(self.printer, payload)
        sent = self.fake.calls[0]['json']['params']['data']['document']
        self.assertEqual(base64.b64decode(sent), payload)

    def test_11_a_box_with_no_printer_is_not_a_print(self):
        """THE trap: HTTP 200 and nothing came out."""
        from ..domain import epos
        self.fake.reply = _Resp({'jsonrpc': '2.0', 'result': False})
        with self.assertRaises(epos.EposError) as c:
            hardware_render.send_to_printer(self.printer, b'x')
        self.assertEqual(c.exception.code, 'iot_no_printer')

    def test_12_an_unreachable_box_reads_as_unreachable(self):
        self.fake.reply = OSError('no route to host')
        with self.assertRaises(OSError):
            hardware_render.send_to_printer(self.printer, b'x')

    def test_13_an_http_error_is_not_a_print(self):
        from ..domain import epos
        self.fake.reply = _Resp({'error': 'nope'}, status_code=500)
        with self.assertRaises(epos.EposError):
            hardware_render.send_to_printer(self.printer, b'x')

    # ── weighing ─────────────────────────────────────────────────────────
    def test_20_a_weight_comes_back_from_the_box(self):
        self.fake.reply = _Resp({'jsonrpc': '2.0', 'result': {'weight': 0.4}})
        reading = hardware_render.read_scale(self.scale)
        self.assertAlmostEqual(reading['weight'], 0.4, places=3)

    def test_21_the_same_refusals_still_apply(self):
        # A boxed scale is still a scale: zero is not a quantity.
        self.fake.reply = _Resp({'jsonrpc': '2.0', 'result': {'weight': 0}})
        with self.assertRaises(scale_domain.ScaleError) as c:
            hardware_render.read_scale(self.scale)
        self.assertEqual(c.exception.code, 'not_positive')

    def test_22_a_box_that_answers_nothing_is_refused(self):
        self.fake.reply = _Resp({'jsonrpc': '2.0', 'result': {}})
        with self.assertRaises(scale_domain.ScaleError):
            hardware_render.read_scale(self.scale)

    def test_23_unparseable_is_refused(self):
        self.fake.reply = _Resp(_BAD)
        with self.assertRaises(scale_domain.ScaleError):
            hardware_render.read_scale(self.scale)

    # ── nothing else changed ─────────────────────────────────────────────
    def test_30_a_socket_printer_never_touches_http(self):
        raw = self.env['mezze.printer'].sudo().create({
            'name': 'Socket Printer', 'printer_type': 'receipt',
            'config_id': self.pos_config.id, 'transport': 'raw',
            'host': '10.1.1.1', 'port': 9100, 'width': 48})
        orig = hardware_render.raw_send
        seen = []
        hardware_render.raw_send = lambda h, p, d, timeout=4: seen.append(d) or len(d)
        try:
            hardware_render.send_to_printer(raw, b'x')
        finally:
            hardware_render.raw_send = orig
        self.assertTrue(seen, 'the raw path did not run')
        self.assertFalse(self.fake.calls, 'a socket printer was sent an HTTP request')
