"""Runtime proof of the P5.2 webhook + hardware outbox adoption.

Tagged ``mezze_runtime``. Real Odoo + PostgreSQL. Uses:
  * a LOCAL threaded HTTP webhook receiver (records event id / idempotency key /
    signature / count and returns a scripted status) — real HTTP, no mocks;
  * a DETERMINISTIC hardware adapter (patches hardware_render.raw_send to record
    sends and simulate device outages) — so print/drawer semantics are observable.

Covers transactional publish, rollback, idempotency, real delivery, retry,
dead-letter, SSRF rejection, missing-config dead-letter, print physical dedup,
device-outage retry, drawer stale-expiry, and company/branch isolation.
"""

import http.server
import json
import threading
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.mezze_bridge.controllers.main import MezzeBridgeController
from odoo.addons.mezze_bridge.models import hardware_render

from .common import MezzePosCase


# ---- local webhook receiver -------------------------------------------------
class _Recorder:
    def __init__(self):
        self.requests = []      # list of dicts
        self.status = 200
        self.lock = threading.Lock()


def _make_handler(rec):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            length = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(length) if length else b''
            with rec.lock:
                rec.requests.append({
                    'idempotency_key': self.headers.get('Idempotency-Key'),
                    'event_id': self.headers.get('X-Mezze-Event-Id'),
                    'correlation_id': self.headers.get('X-Mezze-Correlation-Id'),
                    'signature': self.headers.get('X-Mezze-Signature'),
                    'topic': self.headers.get('X-Mezze-Topic'),
                    'version': self.headers.get('X-Mezze-Payload-Version'),
                    'body': body.decode(errors='replace'),
                })
                status = rec.status
            self.send_response(status)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
    return H


def _paid_order(case, config, amount=10.0, cash=False):
    """Paid pos.order in ``config``'s own (config-scoped) session, using fixture data."""
    env = case.env
    s = case.open_test_session(config)
    p = case.product
    pm = config.payment_method_ids[:1]
    o = env['pos.order'].create({
        'session_id': s.id, 'company_id': config.company_id.id,
        'lines': [(0, 0, {'product_id': p.id, 'qty': 1, 'price_unit': amount,
                          'price_subtotal': amount, 'price_subtotal_incl': amount, 'tax_ids': [(6, 0, [])]})],
        'amount_tax': 0.0, 'amount_total': amount, 'amount_paid': 0.0, 'amount_return': 0.0,
        'pricelist_id': config.pricelist_id.id or False})
    o.add_payment({'amount': amount, 'payment_method_id': pm.id,
                   'name': fields.Datetime.now(), 'pos_order_id': o.id})
    try:
        o.action_pos_order_paid()
    except Exception:  # noqa: BLE001
        o.write({'state': 'paid'})
    return o


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestP52Runtime(MezzePosCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        self.ctrl = MezzeBridgeController()
        self.Event = self.env['mezze.outbox.event']
        self.HwJob = self.env['mezze.hw.job']
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('mezze_bridge.webhook_allow_http', '1')
        ICP.set_param('mezze_bridge.webhook_allow_loopback', '1')
        ICP.set_param('mezze_bridge.webhook_timeout', '5')
        self.cfg = self.pos_config
        self.cfg2 = self.make_second_pos_config()
        self.order = _paid_order(self, self.cfg)
        self.printer = self.env['mezze.printer'].create({
            'name': 'P52 Receipt', 'printer_type': 'receipt', 'config_id': self.cfg.id,
            'host': '10.9.9.9', 'port': 9100, 'width': 48, 'open_drawer': True, 'active': True})
        self.channel = self.env['mezze.aggregator'].create({
            'code': 'p52test', 'name': 'P52 Aggregator', 'config_id': self.cfg.id,
            'secret': 'sekret', 'notify_url': False})
        # deterministic hardware adapter
        self._hw_sends = []
        self._hw_fail = {'n': 0}
        self._orig_send = hardware_render.raw_send

        def fake_send(host, port, data, timeout=4):
            if self._hw_fail['n'] > 0:
                self._hw_fail['n'] -= 1
                raise OSError('device unavailable (simulated)')
            self._hw_sends.append({'host': host, 'port': port, 'bytes': len(data)})
            return len(data)
        hardware_render.raw_send = fake_send

    def tearDown(self):
        hardware_render.raw_send = self._orig_send
        super().tearDown()

    # -- helpers --------------------------------------------------------------
    def _drain(self, **kw):
        for _ in range(30):
            if self.Event._dispatch_batch(commit=False, **kw)['claimed'] == 0:
                break

    def _receiver(self):
        rec = _Recorder()
        srv = http.server.HTTPServer(('127.0.0.1', 0), _make_handler(rec))
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        self.addCleanup(srv.shutdown)
        url = 'http://127.0.0.1:%d/hook' % srv.server_address[1]
        return rec, url

    # ============================ WEBHOOK ============================
    def test_webhook_publish_and_rollback(self):
        # publish
        self.ctrl._publish_webhook(self.env, self.channel, self.order, 'order.accepted', {'x': 1})
        ev = self.Event.search([('event_type', '=', 'integration.webhook.deliver.v1')])
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev.idempotency_key,
                         'webhook:%s:order.accepted:%s' % (self.channel.id, self.order.uuid))
        self.assertEqual(ev.aggregate_type, 'integration.webhook')
        # secrets never in payload
        self.assertNotIn('sekret', ev.payload or '')
        self.assertNotIn('secret', json.loads(ev.payload))
        # rollback
        before = self.Event.search_count([])
        try:
            with self.env.cr.savepoint():
                self.ctrl._publish_webhook(self.env, self.channel, self.order, 'order.cancelled', {})
                raise RuntimeError('rollback')
        except RuntimeError:
            pass
        self.assertFalse(self.Event.search([('idempotency_key', 'like', '%order.cancelled%')]))
        self.assertEqual(self.Event.search_count([]), before)

    def test_webhook_publish_idempotent(self):
        self.ctrl._publish_webhook(self.env, self.channel, self.order, 'order.accepted', {'a': 1})
        self.ctrl._publish_webhook(self.env, self.channel, self.order, 'order.accepted', {'a': 2})
        self.assertEqual(self.Event.search_count(
            [('event_type', '=', 'integration.webhook.deliver.v1')]), 1)

    def test_webhook_real_delivery_and_signature(self):
        rec, url = self._receiver()
        self.channel.notify_url = url
        self.ctrl._publish_webhook(self.env, self.channel, self.order, 'order.accepted', {'hello': 'world'})
        ev = self.Event.search([('event_type', '=', 'integration.webhook.deliver.v1')])
        self._drain()
        self.assertEqual(ev.status, 'done', "webhook not delivered: %s" % ev.last_error)
        self.assertEqual(len(rec.requests), 1)
        r = rec.requests[0]
        self.assertEqual(r['idempotency_key'], ev.idempotency_key)
        self.assertEqual(r['event_id'], ev.event_id)
        self.assertEqual(r['topic'], 'order.accepted')
        self.assertTrue(r['signature'], "HMAC signature header missing")
        import hmac
        import hashlib
        expected = hmac.new(b'sekret', r['body'].encode(), hashlib.sha256).hexdigest()
        self.assertEqual(r['signature'], expected)

    def test_webhook_500_retries_then_succeeds(self):
        rec, url = self._receiver()
        rec.status = 500
        self.channel.notify_url = url
        self.ctrl._publish_webhook(self.env, self.channel, self.order, 'order.accepted', {})
        ev = self.Event.search([('event_type', '=', 'integration.webhook.deliver.v1')])
        self._drain(max_attempts=5)
        self.assertEqual(ev.status, 'failed')
        self.assertTrue(ev.next_retry)
        self.assertEqual(len(rec.requests), 1)
        # remote recovers; force retry-ready and redispatch
        rec.status = 200
        ev.next_retry = fields.Datetime.now() - timedelta(seconds=1)
        self._drain(max_attempts=5)
        self.assertEqual(ev.status, 'done')
        # at-least-once observable: same idempotency key sent twice
        self.assertEqual(len(rec.requests), 2)
        self.assertEqual(rec.requests[0]['idempotency_key'], rec.requests[1]['idempotency_key'])

    def test_webhook_400_dead_letters(self):
        rec, url = self._receiver()
        rec.status = 400
        self.channel.notify_url = url
        self.ctrl._publish_webhook(self.env, self.channel, self.order, 'order.accepted', {})
        ev = self.Event.search([('event_type', '=', 'integration.webhook.deliver.v1')])
        self._drain(max_attempts=8)
        self.assertEqual(ev.status, 'dead')

    def test_webhook_ssrf_dead_letters(self):
        # cloud-metadata destination is unsafe even with http allowed
        self.channel.notify_url = 'http://169.254.169.254/latest/meta-data'
        self.ctrl._publish_webhook(self.env, self.channel, self.order, 'order.accepted', {})
        ev = self.Event.search([('event_type', '=', 'integration.webhook.deliver.v1')])
        self._drain(max_attempts=8)
        self.assertEqual(ev.status, 'dead', "SSRF destination was not rejected")

    def test_webhook_loopback_blocked_when_flag_off(self):
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.webhook_allow_loopback', '0')
        rec, url = self._receiver()
        self.channel.notify_url = url          # 127.0.0.1 -> blocked now
        self.ctrl._publish_webhook(self.env, self.channel, self.order, 'order.accepted', {})
        ev = self.Event.search([('event_type', '=', 'integration.webhook.deliver.v1')])
        self._drain(max_attempts=8)
        self.assertEqual(ev.status, 'dead')
        self.assertEqual(len(rec.requests), 0, "a blocked loopback URL was still contacted")

    def test_webhook_missing_destination_dead_letters(self):
        self.channel.notify_url = False
        self.ctrl._publish_webhook(self.env, self.channel, self.order, 'order.accepted', {})
        ev = self.Event.search([('event_type', '=', 'integration.webhook.deliver.v1')])
        self._drain(max_attempts=8)
        self.assertEqual(ev.status, 'dead')

    def test_webhook_branch_isolation(self):
        # publish an event whose branch != the channel's branch -> dead
        self.Event.publish('integration.webhook.deliver.v1',
                           payload={'integration_id': self.channel.id, 'topic': 'order.accepted',
                                    'payload': {}},
                           aggregate_type='integration.webhook',
                           aggregate_id='wh:x', idempotency_key='wh:iso:1',
                           company_id=self.cfg.company_id.id, branch_id=self.cfg2.id)
        ev = self.Event.search([('idempotency_key', '=', 'wh:iso:1')])
        self._drain(max_attempts=8)
        # only a real mismatch (cfg2 != channel branch cfg) dead-letters
        if self.cfg2.id != self.cfg.id:
            self.assertEqual(ev.status, 'dead')

    # ============================ PRINT ============================
    def test_print_publish_rollback_idempotent(self):
        self.ctrl._publish_receipt_print(self.env, self.order, self.printer)
        ev = self.Event.search([('event_type', '=', 'hardware.print.requested.v1')])
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev.aggregate_id, 'printer:%s' % self.printer.id)
        # idempotent publish
        self.ctrl._publish_receipt_print(self.env, self.order, self.printer)
        self.assertEqual(self.Event.search_count(
            [('event_type', '=', 'hardware.print.requested.v1')]), 1)
        # rollback
        before = self.Event.search_count([])
        try:
            with self.env.cr.savepoint():
                other = _paid_order(self, self.cfg)
                self.ctrl._publish_receipt_print(self.env, other, self.printer)
                raise RuntimeError('rollback')
        except RuntimeError:
            pass
        self.assertEqual(self.Event.search_count([]), before)

    def test_print_delivers_after_dispatch(self):
        self.ctrl._publish_receipt_print(self.env, self.order, self.printer)
        ev = self.Event.search([('event_type', '=', 'hardware.print.requested.v1')])
        self.assertEqual(len(self._hw_sends), 0, "printed before dispatch")
        self._drain()
        self.assertEqual(ev.status, 'done')
        self.assertEqual(len(self._hw_sends), 1)
        self.assertEqual(self._hw_sends[0]['host'], '10.9.9.9')
        job = self.HwJob.search([('idempotency_key', '=', ev.idempotency_key)])
        self.assertEqual(job.status, 'done')

    def test_print_physical_dedup_on_redelivery(self):
        self.ctrl._publish_receipt_print(self.env, self.order, self.printer)
        ev = self.Event.search([('event_type', '=', 'hardware.print.requested.v1')])
        self._drain()
        self.assertEqual(len(self._hw_sends), 1)
        # force a duplicate DELIVERY (manual replay) -> ledger suppresses reprint
        ev.replay()
        self._drain()
        self.assertEqual(len(self._hw_sends), 1, "duplicate delivery produced a second physical print")

    def test_print_missing_printer_dead_letters(self):
        self.Event.publish('hardware.print.requested.v1',
                           payload={'order_id': self.order.id, 'printer_config_id': 999999,
                                    'company_id': self.cfg.company_id.id, 'branch_id': self.cfg.id},
                           aggregate_type='hardware.printer', aggregate_id='printer:x',
                           idempotency_key='print:missing:1')
        ev = self.Event.search([('idempotency_key', '=', 'print:missing:1')])
        self._drain(max_attempts=8)
        self.assertEqual(ev.status, 'dead')
        self.assertEqual(len(self._hw_sends), 0)

    def test_print_device_outage_retries(self):
        self._hw_fail['n'] = 1                 # first send raises OSError
        self.ctrl._publish_receipt_print(self.env, self.order, self.printer)
        ev = self.Event.search([('event_type', '=', 'hardware.print.requested.v1')])
        self._drain(max_attempts=5)
        self.assertEqual(ev.status, 'failed')
        ev.next_retry = fields.Datetime.now() - timedelta(seconds=1)
        self._drain(max_attempts=5)
        self.assertEqual(ev.status, 'done')
        self.assertEqual(len(self._hw_sends), 1)

    def test_print_company_isolation(self):
        self.Event.publish('hardware.print.requested.v1',
                           payload={'order_id': self.order.id, 'printer_config_id': self.printer.id},
                           aggregate_type='hardware.printer', aggregate_id='printer:iso',
                           idempotency_key='print:iso:1',
                           company_id=self.env['res.company'].create({'name': 'Zzz Co'}).id,
                           branch_id=self.cfg.id)
        ev = self.Event.search([('idempotency_key', '=', 'print:iso:1')])
        self._drain(max_attempts=8)
        self.assertEqual(ev.status, 'dead')       # company_mismatch
        self.assertEqual(len(self._hw_sends), 0)

    # ============================ DRAWER ============================
    def test_drawer_publish_and_deliver(self):
        self.ctrl._publish_drawer_open(self.env, self.order, self.printer, reason='cash_payment',
                                       principal='7')
        ev = self.Event.search([('event_type', '=', 'hardware.drawer.open.requested.v1')])
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev.aggregate_type, 'hardware.terminal')
        self._drain()
        self.assertEqual(ev.status, 'done')
        self.assertEqual(len(self._hw_sends), 1)
        job = self.HwJob.search([('idempotency_key', '=', ev.idempotency_key)])
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.principal, '7')

    def test_drawer_stale_command_expires(self):
        self.ctrl._publish_drawer_open(self.env, self.order, self.printer)
        ev = self.Event.search([('event_type', '=', 'hardware.drawer.open.requested.v1')])
        ev.created_at = fields.Datetime.now() - timedelta(seconds=600)   # stale
        self._drain()
        self.assertEqual(ev.status, 'done')        # ACKed (not retried forever)
        self.assertEqual(len(self._hw_sends), 0, "a stale drawer command opened the drawer")
        job = self.HwJob.search([('idempotency_key', '=', ev.idempotency_key)])
        self.assertEqual(job.status, 'expired')

    def test_drawer_duplicate_suppressed(self):
        self.ctrl._publish_drawer_open(self.env, self.order, self.printer)
        ev = self.Event.search([('event_type', '=', 'hardware.drawer.open.requested.v1')])
        self._drain()
        self.assertEqual(len(self._hw_sends), 1)
        ev.replay()
        self._drain()
        self.assertEqual(len(self._hw_sends), 1, "duplicate drawer command opened twice")
