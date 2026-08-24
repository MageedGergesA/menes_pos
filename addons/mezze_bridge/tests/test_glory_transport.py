# -*- coding: utf-8 -*-
"""Driving a Glory machine end to end, with a scripted socket.

``domain/glory`` is the protocol; this is the socket that carries it and the wiring
into the transaction spine that already refuses to let a browser assert money moved.

Three things get proved here that the pure protocol tests cannot:

* the socket.io **handshake** actually happens — open frame, login, credential
  check, function settings, open session — and the session id it yields is what the
  XML requests carry;
* a **PING is answered**. A device kept waiting for a PONG closes the connection,
  and it does that most readily during the long wait while a customer is feeding
  notes in — exactly when losing it is most expensive;
* the three outcome classes land in the database differently. SUCCESS settles one
  payment; a cancel leaves the bill payable and writes nothing; and
  ``CHANGE_SHORTAGE`` — the machine took a note and could not give change back —
  goes to **uncertain**, never settled and never auto-retried.

What no mock can establish is whether a real Glory unit accepts these bytes. That is
stated on the parity row rather than implied by this suite being green.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase
from ..domain import glory
from ..models.glory_transport import GloryTransport


class _ScriptedSocket:
    """A Glory that says whatever the test tells it to."""

    def __init__(self, script):
        self.script = list(script)
        self.sent = []
        self.closed = False

    def settimeout(self, t):
        pass

    def send(self, frame):
        self.sent.append(frame)

    def recv(self):
        if not self.script:
            raise OSError('device went away')
        item = self.script.pop(0)
        return item() if callable(item) else item

    def close(self):
        self.closed = True


def _handshake(session='S-1'):
    return ['0{"sid":"abc"}',
            '42["login response",{}]',
            '42["credential ok",{}]',
            '42["sendFunctionSetting",{}]',
            '42["sendSessionID",{"sessionId":"%s"}]' % session]


def _xml_event(xml):
    return '42' + json.dumps(['ChangeResponse', xml])


@tagged('post_install', '-at_install', 'mezze_glory')
class TestGloryTransport(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.method = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        cls.device = env['mezze.payment.device'].sudo().create({
            'name': 'Glory One', 'code': 'GLORY-1', 'config_id': cls.pos_config.id,
            'mode': 'cash_machine', 'integration_type': 'cash_machine',
            'glory_url': 'ws://10.0.0.9:8080/', 'glory_user': 'pos'})
        cls.device.set_glory_password('sekret')
        cls.dish = env['product.product'].sudo().create({
            'name': 'GL Plate', 'available_in_pos': True, 'list_price': 12.5,
            'type': 'consu'})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def _txn(self, total=12.5):
        order = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': self.dish.id, 'qty': 1,
                              'price_unit': total, 'price_subtotal': total,
                              'price_subtotal_incl': total, 'tax_ids': [(6, 0, [])]})],
            'amount_total': total, 'amount_paid': 0.0, 'amount_tax': 0.0,
            'amount_return': 0.0})
        self.env.flush_all()
        txn = self.env['mezze.terminal.transaction'].sudo().mezze_start(
            order, self.method, self.device, total, 'glory')
        txn.write({'kind': 'cash_machine'})
        return txn

    def _link(self, script):
        sock = _ScriptedSocket(script)
        return GloryTransport('ws://x/', 'pos', 'sekret', socket=sock), sock

    def _paid(self, txn):
        txn.pos_order_id.invalidate_recordset()
        return sum(txn.pos_order_id.payment_ids.mapped('amount'))

    # ── handshake ────────────────────────────────────────────────────────
    def test_01_the_handshake_yields_a_session(self):
        link, sock = self._link(_handshake('S-42'))
        self.assertEqual(link.connect(), 'S-42')
        self.assertEqual(len(sock.sent), 4,
                         'four events: login, credential, settings, open session')

    def test_02_the_session_id_travels_on_every_request(self):
        link, sock = self._link(_handshake('S-9') + [_xml_event(
            '<ChangeResponse result="0"><Amount>1250</Amount></ChangeResponse>')])
        link.connect()
        link.request('pay', 1, amount_minor=1250)
        self.assertIn('<SessionID>S-9</SessionID>', sock.sent[-1])
        self.assertIn('<Amount>1250</Amount>', sock.sent[-1])

    def test_03_a_ping_is_answered(self):
        """A device kept waiting for a PONG closes the connection."""
        link, sock = self._link(
            _handshake() + ['2', _xml_event('<ChangeResponse result="0"/>')])
        link.connect()
        link.request('pay', 1, amount_minor=100)
        self.assertIn('3', sock.sent, 'the PING went unanswered')

    def test_04_a_machine_with_no_session_is_refused(self):
        link, _s = self._link(['0{"sid":"a"}', '42["login response",{}]',
                               '42["credential ok",{}]',
                               '42["sendFunctionSetting",{}]',
                               '42["sendSessionID",{}]'])
        with self.assertRaises(glory.GloryError):
            link.connect()

    # ── outcomes on the bill ─────────────────────────────────────────────
    def test_10_a_successful_payment_settles_exactly_one(self):
        txn = self._txn()
        link, _s = self._link(_handshake() + [_xml_event(
            '<ChangeResponse result="0"><Amount>1250</Amount></ChangeResponse>')])
        txn.mezze_glory_pay(transport=link)
        self.assertEqual(txn.state, 'approved', txn.error_code)
        self.assertAlmostEqual(self._paid(txn), 12.5, places=2)

    def test_11_a_cancel_leaves_the_bill_payable(self):
        txn = self._txn()
        link, _s = self._link(_handshake() + [_xml_event('<ChangeResponse result="1"/>')])
        txn.mezze_glory_pay(transport=link)
        self.assertEqual(txn.state, 'cancelled')
        self.assertFalse(txn.uncertain)
        self.assertEqual(self._paid(txn), 0.0)

    def test_12_a_change_shortage_is_uncertain_and_settles_nothing(self):
        """THE case. The machine took a note and could not give change back."""
        txn = self._txn()
        link, _s = self._link(_handshake() + [_xml_event('<ChangeResponse result="10"/>')])
        txn.mezze_glory_pay(transport=link)
        self.assertTrue(txn.uncertain,
                        'a machine holding cash was reported as a clean refusal')
        self.assertEqual(txn.error_code, 'CHANGE_SHORTAGE')
        self.assertEqual(self._paid(txn), 0.0,
                         'money was booked while the machine still held it')

    def test_13_a_lost_connection_is_uncertain_not_a_decline(self):
        # A machine that was mid-transaction may be holding cash.
        txn = self._txn()
        link, _s = self._link(_handshake())      # dies before the response
        txn.mezze_glory_pay(transport=link)
        self.assertTrue(txn.uncertain)
        self.assertEqual(self._paid(txn), 0.0)

    def test_14_an_unconfigured_machine_takes_no_money(self):
        self.device.sudo().write({'glory_url': False})
        txn = self._txn()
        txn.mezze_glory_pay()
        self.assertEqual(txn.error_code, 'glory_unconfigured')
        self.assertEqual(self._paid(txn), 0.0)

    def test_15_the_socket_is_closed_whatever_happens(self):
        txn = self._txn()
        link, sock = self._link(_handshake() + [_xml_event('<ChangeResponse result="10"/>')])
        txn.mezze_glory_pay(transport=link)
        self.assertTrue(sock.closed, 'the connection was left open')

    def test_16_the_machine_password_is_not_stored_in_plaintext(self):
        self.env.cr.execute(
            "SELECT glory_password_enc FROM mezze_payment_device WHERE id = %s",
            (self.device.id,))
        stored = self.env.cr.fetchone()[0] or ''
        self.assertNotIn('sekret', stored)
        self.assertEqual(self.device._glory_password(), 'sekret')
