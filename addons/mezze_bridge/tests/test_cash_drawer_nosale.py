# -*- coding: utf-8 -*-
"""Opening the till without a sale.

``/drawer/open`` has existed with its capability, its branch scoping and its object
gate intact — and nothing on the register ever called it. A cashier who needed to
make change or correct a miscount had to ring something up to get the drawer open,
which is precisely the workaround that makes a till's cash untraceable.

What was genuinely missing on the server was the RECORD. A drawer that opens with no
money changing hands is both an ordinary thing a cashier does and the shape of the
commonest till theft, so who opened it and when is the only thing that lets an
unexplained variance at close be traced to anything. It costs nothing to write and
cannot be reconstructed afterwards.
"""
import json
import socket
import threading

from odoo.tests import tagged

from .common import MezzeHttpCase


class _FakeDrawer:
    """A socket that accepts one connection and remembers the bytes.

    Without it every assertion about the RECORD skips, because ``_send`` cannot
    reach anything and the endpoint returns before it audits. An earlier version of
    this file did exactly that: five green tests, four of them skipped, and the audit
    — the only part that was genuinely missing on the server — never exercised.
    """

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', 0))
        self.sock.listen(8)
        self.port = self.sock.getsockname()[1]
        self.received = []
        self._stop = False
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while not self._stop:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            try:
                self.received.append(conn.recv(4096))
            finally:
                conn.close()

    def close(self):
        self._stop = True
        try:
            self.sock.close()
        except OSError:
            pass


@tagged('post_install', '-at_install', 'mezze_drawer')
class TestNoSaleDrawer(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'dr-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.drawer = _FakeDrawer()
        cls.addClassCleanup(cls.drawer.close)
        cls.printer = env['mezze.printer'].sudo().create({
            'name': 'DR Front', 'printer_type': 'receipt',
            'config_id': cls.pos_config.id,
            'host': '127.0.0.1', 'port': cls.drawer.port,
            'open_drawer': True, 'width': 48,
        })
        env.flush_all()

    def _open(self, **kw):
        r = self.url_open('/mezze/hardware/drawer/open',
                          data=json.dumps(dict(kw, token='dr-tok')),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _rows(self):
        return self.env['mezze.audit.log'].sudo().search(
            [('event', '=', 'drawer.opened')], order='id desc')

    def test_01_the_endpoint_is_reachable_with_no_order(self):
        # The whole point: no sale, no order, no cart.
        d = self._open()
        # Either it reached the drawer or the socket refused — both mean the request
        # was accepted and routed. What must NOT happen is a refusal to try.
        self.assertNotIn(d.get('error'),
                         ('permission_denied', 'authentication_required',
                          'no_drawer_printer'),
                         'a no-sale open was refused outright: %s' % d)

    def test_02_the_kick_actually_reaches_the_drawer(self):
        d = self._open()
        self.assertTrue(d.get('ok'), d)
        self.assertTrue(self.drawer.received, 'nothing was sent to the drawer')
        # ESC/POS kick, pin 0 — the bytes a drawer actually opens on.
        self.assertIn(b'\x1bp\x00', self.drawer.received[-1])

    def test_03_a_successful_open_is_recorded(self):
        before = len(self._rows())
        d = self._open(reason='making change')
        self.assertTrue(d.get('ok'), d)
        rows = self._rows()
        self.assertEqual(len(rows), before + 1,
                         'the till opened and nothing recorded it')
        detail = json.loads(rows[0].detail or '{}')
        self.assertEqual(detail.get('reason'), 'making change')

    def test_04_the_record_is_a_warning_not_an_info_line(self):
        # It has to be findable among thousands of ordinary events.
        self.assertTrue(self._open().get('ok'))
        self.assertEqual(self._rows()[0].severity, 'warning')

    def test_05_a_failed_open_records_nothing(self):
        # Auditing an open that never happened would put phantom events in the trail
        # a variance is investigated from. Proven by pointing the printer at a port
        # nothing is listening on, rather than by hoping the environment has none.
        self.printer.sudo().write({'port': 9})
        before = len(self._rows())
        d = self._open()
        self.assertFalse(d.get('ok'))
        self.assertEqual(d.get('error'), 'printer_unreachable')
        self.assertEqual(len(self._rows()), before,
                         'a drawer that never opened was recorded as opened')
