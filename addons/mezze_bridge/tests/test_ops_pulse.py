"""The Register rail's live counts, and the branch they are counted over.

`/ops/pulse` answers "how busy is this shift" in one call — the rail's Kitchen
and Orders badges and the exceptions strip above them — because five polls from
every till is how a branch server falls over at the moment it is busiest.

It shipped counting the WRONG SET. The branch was read as
``browse(int(config_id))`` straight from the request body, and then only the
draft-order count used it: kitchen tickets, prep average, rejected receipts,
bookings and the outbox queue were all counted with no branch filter at all. On
a two-branch company a cashier in one shop read the other shop's kitchen queue,
and a caller that simply omitted ``config_id`` got a group-wide count of
everything.

That is the inverse of what `domain/route_scope.py` classifies this route as.
Category B's contract is that the query STARTS from the principal's
authoritative scope and client input may only narrow it — and the structural
test that enforces the registry caught the route as unclassified, which is what
led here. Classifying it without fixing it would have made the guard lie.

These tests are therefore about the SET, not the numbers: build the same
situation in two branches and assert each till sees only its own.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestOpsPulseScope(MezzeHttpCase):
    fixture_profile = 'RESTAURANT'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.token = 'pulse-tok'
        ICP.set_param('mezze_bridge.api_token', cls.token)
        ICP.set_param('mezze_bridge.api_security', 'observe')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        ICP.set_param('mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.other = cls.pos_config.copy({'name': 'Pulse Second Branch'})
        cls.env.flush_all()

    def _pulse(self, config_id):
        r = self.url_open(
            '/mezze/api/v1/ops/pulse',
            data=json.dumps({'token': self.token, 'config_id': config_id}),
            headers={'Content-Type': 'application/json'}, timeout=30)
        body = r.json()
        self.assertTrue(body.get('ok'), body)
        return body

    def _ticket(self, config, state='fired'):
        """A kitchen ticket on a named branch, via its own order so config_id
        (a stored related on the order) resolves the way production creates it."""
        session = self._open_session_for(config)
        order = self.env['pos.order'].create({
            'session_id': session.id, 'company_id': config.company_id.id,
            'amount_tax': 0, 'amount_total': 0, 'amount_paid': 0, 'amount_return': 0,
        })
        return self.env['mezze.kds.ticket'].create({
            'pos_order_id': order.id, 'station': 'Grill', 'state': state})

    def test_01_the_kitchen_count_is_this_branchs_kitchen(self):
        self._ticket(self.pos_config)
        self._ticket(self.other)
        self._ticket(self.other)
        self.env.flush_all()
        mine = self._pulse(self.pos_config.id)
        self.assertEqual(mine['kitchen'], 1,
                         'the rail counted another branch\'s kitchen: %r' % mine)

    def test_02_each_branch_sees_only_its_own(self):
        """Both directions, because a filter that happens to name the right branch
        once is not a filter — it is a coincidence."""
        self._ticket(self.pos_config)
        for _ in range(3):
            self._ticket(self.other)
        self.env.flush_all()
        self.assertEqual(self._pulse(self.pos_config.id)['kitchen'], 1)
        self.assertEqual(self._pulse(self.other.id)['kitchen'], 3)

    def test_03_bookings_are_counted_per_branch(self):
        from odoo import fields as ofields
        now = ofields.Datetime.now()
        # Each branch gets its OWN floor and table: `table_id` is required on a
        # reservation, and borrowing the first branch's table for the second would
        # leave the two rows distinguishable only by the very field under test.
        #
        # Built directly rather than through `factories.make_floor_and_tables`,
        # which first UNLINKS every floor already attached to the config it is
        # given. `self.other` is a copy of `self.pos_config` and shares its floor,
        # so the factory would delete the fixture's own floor and tables out from
        # under the first half of this test.
        other_floor = self.env['restaurant.floor'].create({
            'name': 'Pulse Second Floor',
            'pos_config_ids': [(6, 0, [self.other.id])]})
        other_table = self.env['restaurant.table'].create({
            'table_number': 91, 'floor_id': other_floor.id, 'seats': 4})
        for cfg, table, n in ((self.pos_config, self.tables[0], 1),
                              (self.other, other_table, 2)):
            for i in range(n):
                self.env['mezze.reservation'].create({
                    'config_id': cfg.id, 'table_id': table.id,
                    'name': 'Guest %s' % i,
                    'start': now, 'guests': 2, 'state': 'booked'})
        self.env.flush_all()
        self.assertEqual(self._pulse(self.pos_config.id)['bookings'], 1)
        self.assertEqual(self._pulse(self.other.id)['bookings'], 2)

    def test_04_the_answer_names_the_branch_it_counted(self):
        """So a till can tell it was answered about itself. Without this the
        response is a bare set of numbers with no way to notice they are the
        wrong shop's."""
        body = self._pulse(self.pos_config.id)
        self.assertEqual(body.get('config_id'), self.pos_config.id, body)

    def test_05_omitting_the_branch_does_not_widen_the_scope(self):
        """The original defect's worst shape: no config_id meant no filter, so the
        counts silently became group-wide. The token decides the branch, so an
        omitted claim must fall back to the token's own branch — never to
        'everything'."""
        self._ticket(self.pos_config)
        for _ in range(4):
            self._ticket(self.other)
        self.env.flush_all()
        r = self.url_open(
            '/mezze/api/v1/ops/pulse',
            data=json.dumps({'token': self.token}),
            headers={'Content-Type': 'application/json'}, timeout=30)
        body = r.json()
        self.assertTrue(body.get('ok'), body)
        self.assertEqual(
            body['kitchen'], 1,
            'omitting config_id widened the count to every branch: %r' % body)

    # ── the exceptions the strip is FOR ──────────────────────────────────
    def test_06_an_86d_item_is_counted_for_this_branch_only(self):
        """The strip's whole job is to surface what is going wrong. A count that
        stays zero while an item is 86'd is a strip nobody will trust twice."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('mezze_bridge.eightysix_%s' % self.pos_config.id,
                      json.dumps([self.product.id]))
        ICP.set_param('mezze_bridge.eightysix_%s' % self.other.id,
                      json.dumps([self.product.id, self.product.id + 1]))
        self.env.flush_all()
        self.assertEqual(self._pulse(self.pos_config.id)['off86'], 1)
        self.assertEqual(self._pulse(self.other.id)['off86'], 2)

    def test_07_a_queued_outbox_is_counted(self):
        self.env['mezze.outbox.event'].sudo().publish(
            'test.pulse.v1', payload={'x': 1}, aggregate_type='pos.order',
            aggregate_id='1', branch_id=self.pos_config.id)
        self.env.flush_all()
        self.assertGreaterEqual(self._pulse(self.pos_config.id)['queued'], 1,
                                'a pending outbox event is not reported')

    def test_08_a_quiet_branch_reports_zero_rather_than_nothing(self):
        """Every figure must be PRESENT and zero, not absent. The client hides a
        chip on a falsy value, so an omitted key and a real zero look identical on
        screen — but only one of them means "I could not read this"."""
        body = self._pulse(self.pos_config.id)
        for key in ('kitchen', 'orders', 'rejected', 'off86', 'bookings', 'queued'):
            self.assertIn(key, body, 'the pulse cannot answer %r: %r' % (key, body))
