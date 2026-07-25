"""R1 — Restaurant Service Loop: reservation/waitlist arrival lifecycle proofs.

Covers the gaps this increment fixed: guarded state transitions (illegal moves
rejected, not written), restore-out-of-cancelled, the no-double-seat guard, and
the idempotent seat->order attach (seating links the table's ONE draft order and a
retry does not create/duplicate). Existing order/course/payment idempotency is
already proven by the wider suite; this file targets only the R1 additions.
"""
import json

from odoo.exceptions import UserError
from odoo.tests import common, tagged


def _table(env, cfg):
    Table = env['restaurant.table'].sudo()
    floor = env['restaurant.floor'].sudo().search([('pos_config_ids', 'in', cfg.id)], limit=1) \
        or env['restaurant.floor'].sudo().search([], limit=1)
    vals = {'table_number': 991, 'active': True}
    if 'floor_id' in Table._fields and floor:
        vals['floor_id'] = floor.id
    return Table.create(vals)


def _draft_order(env, cfg, table=None):
    s = (env['pos.session'].sudo().search([('config_id', '=', cfg.id), ('state', '=', 'opened')], limit=1)
         or env['pos.session'].sudo().create({'config_id': cfg.id, 'user_id': env.uid}))
    p = (env['product.product'].search([('available_in_pos', '=', True)], limit=1)
         or env['product.product'].search([], limit=1))
    vals = {'session_id': s.id, 'company_id': cfg.company_id.id,
            'lines': [(0, 0, {'product_id': p.id, 'qty': 1, 'price_unit': 10.0,
                              'price_subtotal': 10.0, 'price_subtotal_incl': 10.0, 'tax_ids': [(6, 0, [])]})],
            'amount_total': 10.0, 'amount_paid': 0.0, 'amount_tax': 0.0, 'amount_return': 0.0,
            'pricelist_id': cfg.pricelist_id.id or False}
    if table and 'table_id' in env['pos.order']._fields:
        vals['table_id'] = table.id
    return env['pos.order'].sudo().create(vals), s


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestReservationLifecycle(common.TransactionCase):

    def setUp(self):
        super().setUp()
        self.cfg = self.env['pos.config'].search([], limit=1)
        self.table = _table(self.env, self.cfg)
        self.R = self.env['mezze.reservation'].sudo()

    def _res(self, **kw):
        v = dict(table_id=self.table.id, config_id=self.cfg.id,
                 start='2026-07-24 19:00:00', guests=2, customer_name='Sara')
        v.update(kw)
        return self.R.create(v)

    def test_arrival_happy_path(self):
        r = self._res()
        r.apply_transition('confirm'); self.assertEqual(r.state, 'confirmed')
        r.apply_transition('arrive', arrival_note='window seat please')
        self.assertEqual(r.state, 'arrived')
        self.assertTrue(r.arrived_at)
        self.assertEqual(r.arrival_note, 'window seat please')
        r.apply_transition('seat'); self.assertEqual(r.state, 'seated')
        r.apply_transition('complete'); self.assertEqual(r.state, 'done')

    def test_completed_cannot_reseat(self):
        r = self._res(state='done')
        with self.assertRaises(UserError):
            r.apply_transition('seat')
        self.assertEqual(r.state, 'done')            # not written

    def test_cancelled_needs_restore(self):
        r = self._res(state='cancelled')
        with self.assertRaises(UserError):
            r.apply_transition('seat')               # cannot open an order without restore
        r.apply_transition('restore')
        self.assertEqual(r.state, 'booked')
        r.apply_transition('seat')                   # now legal
        self.assertEqual(r.state, 'seated')

    def test_no_show_restore(self):
        r = self._res(state='no_show')
        r.apply_transition('restore'); self.assertEqual(r.state, 'booked')

    def test_late_flag_and_state(self):
        r = self._res(start='2020-01-01 12:00:00')   # a slot long past
        r.apply_transition('late'); self.assertEqual(r.state, 'late')
        r.apply_transition('arrive'); self.assertEqual(r.state, 'arrived')

    def test_idempotent_same_state(self):
        r = self._res(state='confirmed')
        r.apply_transition('confirm')                # no-op, must not raise
        self.assertEqual(r.state, 'confirmed')


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestWaitlistLifecycle(common.TransactionCase):

    def setUp(self):
        super().setUp()
        self.cfg = self.env['pos.config'].search([], limit=1)
        self.table = _table(self.env, self.cfg)
        self.W = self.env['mezze.waitlist'].sudo()

    def test_queue_progression(self):
        w = self.W.create({'config_id': self.cfg.id, 'party_size': 4, 'customer_name': 'Omar'})
        w.apply_transition('notify'); self.assertEqual(w.state, 'notified')
        w.apply_transition('seating'); self.assertEqual(w.state, 'seating')
        w.apply_transition('seat', table_id=self.table.id)
        self.assertEqual(w.state, 'seated')
        self.assertEqual(w.table_id.id, self.table.id)

    def test_seated_cannot_return_to_waiting(self):
        w = self.W.create({'config_id': self.cfg.id, 'party_size': 2, 'state': 'seated'})
        with self.assertRaises(UserError):
            w.apply_transition('notify')             # seated -> notified illegal

    def test_left_and_restore(self):
        w = self.W.create({'config_id': self.cfg.id, 'party_size': 2})
        w.apply_transition('left'); self.assertEqual(w.state, 'left')
        w.apply_transition('restore'); self.assertEqual(w.state, 'waiting')


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestSeatOrderIdempotent(common.HttpCase):

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('mezze_bridge.api_security', 'enforce')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        ICP.set_param('mezze_bridge.signing_mode.terminal', 'observe')
        self.cfg = self.env['pos.config'].search([], limit=1)
        self.table = _table(self.env, self.cfg)
        self.order, self.session = _draft_order(self.env, self.cfg, self.table)
        self.term = self.env['mezze.terminal'].create({
            'name': 'R1', 'identifier': 'R1-T', 'token': 'r1-tok',
            'branch_id': self.cfg.id, 'role': 'terminal', 'active': True})
        # a HOST human principal — holds RESERVATIONS_MANAGE, not pay/refund
        self.host = self.env['mezze.cashier'].sudo().create(
            {'name': 'Host', 'code': 'R1-H', 'role': 'host', 'active': True})
        self.res = self.env['mezze.reservation'].sudo().create({
            'table_id': self.table.id, 'config_id': self.cfg.id,
            'start': '2026-07-24 19:00:00', 'guests': 2, 'customer_name': 'Lina'})
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(body),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def test_seat_attaches_one_order_idempotently(self):
        body = {'token': 'r1-tok', 'cashier_id': self.host.id, 'reservation_id': self.res.id,
                'action': 'seat', 'session_id': self.session.id}
        st, b = self._post('/reservations/state', body)
        self.assertTrue(b.get('ok'), b)
        self.assertEqual(b['reservation']['state'], 'seated')
        self.assertTrue(b.get('order'))
        oid = b['order']['order_id']
        self.assertEqual(oid, self.order.id)                 # attached the table's existing draft
        # retry seat -> same order, no duplicate
        st, b2 = self._post('/reservations/state', body)
        self.assertEqual(b2['order']['order_id'], oid)
        self.res.invalidate_recordset()
        self.assertEqual(self.res.pos_order_id.id, self.order.id)
        # exactly one draft order on this table
        n = self.env['pos.order'].sudo().search_count(
            [('table_id', '=', self.table.id), ('state', '=', 'draft')])
        self.assertEqual(n, 1)

    def test_invalid_transition_rejected_over_http(self):
        self.res.write({'state': 'done'})
        st, b = self._post('/reservations/state',
                           {'token': 'r1-tok', 'cashier_id': self.host.id, 'reservation_id': self.res.id, 'action': 'seat'})
        self.assertEqual(b.get('error'), 'invalid_transition')
        self.res.invalidate_recordset()
        self.assertEqual(self.res.state, 'done')             # unchanged

    def test_host_permission_boundary(self):
        # §16 — a host runs the door but may NOT take payment (no ORDERS_PAY cap).
        st, b = self._post('/orders/pay',
                           {'token': 'r1-tok', 'cashier_id': self.host.id, 'uuid': self.order.uuid})
        self.assertEqual(b.get('error'), 'permission_denied')
        # …but the host CAN seat (RESERVATIONS_MANAGE) — proven above.


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestR11Acceptance(common.HttpCase):
    """R1.1 — merge financial safety (§8) + role boundaries (§10)."""

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('mezze_bridge.api_security', 'enforce')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        ICP.set_param('mezze_bridge.signing_mode.terminal', 'observe')
        self.cfg = self.env['pos.config'].search([], limit=1)
        self.tA = _table(self.env, self.cfg)
        self.tB = _table(self.env, self.cfg)
        self.tB.write({'table_number': 992})
        self.oA, self.session = _draft_order(self.env, self.cfg, self.tA)
        self.oB, _ = _draft_order(self.env, self.cfg, self.tB)
        self.term = self.env['mezze.terminal'].create({
            'name': 'R11', 'identifier': 'R11-T', 'token': 'r11-tok',
            'branch_id': self.cfg.id, 'role': 'terminal', 'active': True})
        C = self.env['mezze.cashier'].sudo()
        self.kitchen = C.create({'name': 'Chef', 'code': 'R11-K', 'role': 'kitchen', 'active': True})
        self.cashier = C.create({'name': 'Cash', 'code': 'R11-C', 'role': 'cashier', 'active': True})
        self.mgr = C.create({'name': 'Mgr', 'code': 'R11-M', 'role': 'manager', 'active': True})
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(body),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def _pay_method(self):
        pm = self.cfg.payment_method_ids[:1]
        return pm or self.env['pos.payment.method'].sudo().search([], limit=1)

    def test_merge_safe_when_both_unpaid(self):
        st, b = self._post('/tables/merge', {'token': 'r11-tok', 'cashier_id': self.mgr.id,
                                             'session_id': self.session.id,
                                             'from_table_id': self.tA.id, 'to_table_id': self.tB.id})
        self.assertTrue(b.get('ok'), b)
        self.assertTrue(b.get('merged'))

    def test_merge_blocked_when_source_has_payment(self):
        pm = self._pay_method()
        self.env['pos.payment'].sudo().create(
            {'pos_order_id': self.oA.id, 'amount': 5.0, 'payment_method_id': pm.id})
        self.oA.invalidate_recordset()
        self.env.flush_all()
        pay_before = self.env['pos.payment'].sudo().search_count([('pos_order_id', '=', self.oA.id)])
        st, b = self._post('/tables/merge', {'token': 'r11-tok', 'cashier_id': self.mgr.id,
                                             'session_id': self.session.id,
                                             'from_table_id': self.tA.id, 'to_table_id': self.tB.id})
        self.assertEqual(b.get('error'), 'merge_blocked_payments')
        # the paid source order and its payment must be untouched (nothing destroyed)
        self.oA.invalidate_recordset()
        self.assertTrue(self.oA.exists())
        self.assertEqual(self.env['pos.payment'].sudo().search_count([('pos_order_id', '=', self.oA.id)]), pay_before)

    def test_kitchen_cannot_pay(self):
        st, b = self._post('/orders/pay', {'token': 'r11-tok', 'cashier_id': self.kitchen.id, 'uuid': self.oA.uuid})
        self.assertEqual(b.get('error'), 'permission_denied')

    def test_cashier_cannot_modify_kds_prep(self):
        st, b = self._post('/kds/transition', {'token': 'r11-tok', 'cashier_id': self.cashier.id,
                                               'ticket_id': 1, 'action': 'ready'})
        self.assertEqual(b.get('error'), 'permission_denied')
