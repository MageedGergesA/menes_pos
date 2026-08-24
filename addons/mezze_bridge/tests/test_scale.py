# -*- coding: utf-8 -*-
"""Selling by weight, and asking the scale.

Weighed products already survived the round trip — the catalogue ships
``to_weight``, the quantity is kept as a measurement — and could not be SOLD from
the Register at all: the pad refused the decimal point in Qty mode, deliberately,
because "a decimal there is a typo". True of a burger and exactly wrong for 0.4 kg
of cheese, so the feature existed everywhere except where a cashier stands.

The scale itself is driven server-side, like the printers, because Community has no
IoT Box and a browser cannot open a socket to a bench scale.

What is tested hardest is what this refuses, because all three refusals are money:

* an UNSTABLE reading is not a weight — every scale says whether the pan has
  settled, and taking the number anyway charges the guest for the bounce as the item
  is put down. That error is always in the shop's favour, which is why it survives
  unreported;
* a unit is never CONVERTED — a scale left in pounds against a product priced per
  kilo is a 2.2x error on the bill;
* zero or negative is not a sale.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase
from ..domain import scale as scale_domain
from ..models import hardware_render


@tagged('post_install', '-at_install', 'mezze_scale')
class TestScaleProtocol(MezzeHttpCase):
    """The parsing, with no scale and no server."""
    fixture_profile = 'POS'

    # -- Toledo 8217 ------------------------------------------------------
    def test_01_a_settled_toledo_reading_is_a_weight(self):
        r = scale_domain.parse_toledo(b'\x02\x00 0.400kg\r\n\x03', want_unit='kg')
        self.assertEqual(r['weight'], 0.4)
        self.assertTrue(r['stable'])

    def test_02_motion_is_refused(self):
        with self.assertRaises(scale_domain.ScaleError) as c:
            scale_domain.parse_toledo(b'\x02\x01 0.400kg\r\n\x03', want_unit='kg')
        self.assertEqual(c.exception.code, 'unstable')

    def test_03_over_capacity_is_refused(self):
        with self.assertRaises(scale_domain.ScaleError) as c:
            scale_domain.parse_toledo(b'\x02\x02 9.999kg\r\n\x03', want_unit='kg')
        self.assertEqual(c.exception.code, 'out_of_range')

    def test_04_a_frame_that_is_not_a_frame_is_refused(self):
        for junk in (b'', b'hello', b'\x00\x00'):
            with self.assertRaises(scale_domain.ScaleError):
                scale_domain.parse_toledo(junk, want_unit='kg')

    # -- ASCII line -------------------------------------------------------
    def test_10_a_steady_line_reading_is_a_weight(self):
        r = scale_domain.parse_line('ST,GS,   0.400kg', want_unit='kg')
        self.assertEqual(r['weight'], 0.4)

    def test_11_unsteady_is_believed(self):
        with self.assertRaises(scale_domain.ScaleError) as c:
            scale_domain.parse_line('US,GS,   0.400kg', want_unit='kg')
        self.assertEqual(c.exception.code, 'unstable')

    def test_12_grams_are_arithmetic_not_a_guess(self):
        # Unlike pounds, the conversion is exact and the unit is a display choice.
        r = scale_domain.parse_line('ST,GS,   400g', want_unit='kg')
        self.assertEqual(r['weight'], 0.4)
        self.assertEqual(r['unit'], 'kg')

    def test_13_pounds_against_a_kilo_price_are_refused(self):
        # THE money rule. 2.2x, always in the same direction.
        with self.assertRaises(scale_domain.ScaleError) as c:
            scale_domain.parse_line('ST,GS,   1.500lb', want_unit='kg')
        self.assertEqual(c.exception.code, 'unit_mismatch')

    def test_14_an_empty_pan_is_not_a_quantity(self):
        with self.assertRaises(scale_domain.ScaleError) as c:
            scale_domain.parse_line('ST,GS,   0.000kg', want_unit='kg')
        self.assertEqual(c.exception.code, 'not_positive')

    def test_15_a_tare_left_in_is_not_a_quantity(self):
        with self.assertRaises(scale_domain.ScaleError) as c:
            scale_domain.parse_line('ST,GS,  -0.200kg', want_unit='kg')
        self.assertEqual(c.exception.code, 'not_positive')

    def test_16_an_unknown_protocol_is_named(self):
        with self.assertRaises(scale_domain.ScaleError) as c:
            scale_domain.parse('semaphore', b'x')
        self.assertEqual(c.exception.code, 'unknown_protocol')


class _FakeSocket:
    def __init__(self, reply):
        self.reply = reply
        self.sent = []

    def settimeout(self, t):
        pass

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, n):
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply

    def close(self):
        pass


@tagged('post_install', '-at_install', 'mezze_scale')
class TestScaleEndpoint(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'sc-tok')
        cls.scale = cls.env['mezze.scale'].sudo().create({
            'name': 'Deli Scale', 'config_id': cls.pos_config.id,
            'host': '10.5.5.5', 'port': 4001, 'protocol': 'line', 'uom_name': 'kg'})
        cls.env.flush_all()

    def setUp(self):
        super().setUp()
        self.reply = b'ST,GS,   0.400kg\r\n'
        self._orig = hardware_render.socket.create_connection
        test = self

        def fake_conn(addr, timeout=None):
            test.addr = addr
            return _FakeSocket(test.reply)
        hardware_render.socket.create_connection = fake_conn
        self.addCleanup(self._restore)

    def _restore(self):
        hardware_render.socket.create_connection = self._orig

    def _read(self, **kw):
        body = dict({'token': 'sc-tok', 'config_id': self.pos_config.id}, **kw)
        r = self.url_open('/mezze/hardware/scale/read', data=json.dumps(body),
                          headers={'Content-Type': 'application/json'})
        return r.status_code, r.json()

    def test_20_a_till_can_ask_what_is_on_the_pan(self):
        code, d = self._read(uom='kg')
        self.assertEqual(code, 200, d)
        self.assertTrue(d.get('ok'), d)
        self.assertEqual(d['weight'], 0.4)
        self.assertEqual(d['scale'], 'Deli Scale')

    def test_21_it_asks_the_configured_address(self):
        self._read(uom='kg')
        self.assertEqual(self.addr, ('10.5.5.5', 4001))

    def test_22_an_unstable_pan_is_reported_as_such(self):
        # Not an error a cashier should read as a fault — the pan settles and they
        # tap again.
        self.reply = b'US,GS,   0.400kg\r\n'
        code, d = self._read(uom='kg')
        self.assertEqual(code, 409)
        self.assertEqual(d['error'], 'unstable')

    def test_23_a_wrong_unit_is_refused_before_the_socket_is_opened(self):
        # Nothing about the reading can rescue a scale set to the wrong unit, so it
        # is not asked in the first place.
        self.addr = None
        code, d = self._read(uom='lb')
        self.assertEqual(code, 409)
        self.assertEqual(d['error'], 'unit_mismatch')
        self.assertIsNone(self.addr, 'the scale was contacted anyway')

    def test_24_an_unplugged_scale_reads_as_unreachable(self):
        def boom(addr, timeout=None):
            raise OSError('no route to host')
        hardware_render.socket.create_connection = boom
        code, d = self._read(uom='kg')
        self.assertEqual(code, 503)
        self.assertEqual(d['error'], 'scale_unreachable')

    def test_25_a_branch_with_no_scale_says_so(self):
        other = self.make_second_pos_config()
        code, d = self._read(config_id=other.id, uom='kg')
        self.assertEqual(code, 404)
        self.assertEqual(d['error'], 'no_scale')

    def test_26_the_branch_is_told_at_boot_whether_it_has_one(self):
        # So a weighed line never offers a button that answers "no scale".
        r = self.url_open('/mezze/api/v1/bootstrap',
                          data=json.dumps({'token': 'sc-tok',
                                           'config_id': self.pos_config.id}),
                          headers={'Content-Type': 'application/json'})
        self.assertTrue(r.json()['config']['has_scale'])

    def test_27_a_scale_with_no_address_is_not_advertised(self):
        self.scale.sudo().write({'host': False})
        r = self.url_open('/mezze/api/v1/bootstrap',
                          data=json.dumps({'token': 'sc-tok',
                                           'config_id': self.pos_config.id}),
                          headers={'Content-Type': 'application/json'})
        self.assertFalse(r.json()['config']['has_scale'])
