"""What the open-checks strip says about each check.

The strip existed (S1-09) and carried the wrong three facts. It printed the raw
`pos_reference` — "260-1-000041" — then the age, then the money. The design's
chip is `Table 12 · 19 · 12m` plus a state mark: WHO the check belongs to, HOW
MUCH IS ON IT, how long it has sat, and whether it is already part paid.

Two of those were simply the wrong field:

* the label fell back to `pos_reference`, which names a database row, not a
  check a cashier can pick out of a queue;
* the meta printed `guests`, which is a different fact from the design's — the
  prototype reduces the LINES (`a + (l.weight ? 1 : l.qty)`) — and which is zero
  on every counter sale, so most chips showed an age and nothing else.

The amount is gone on purpose. It was the widest element on the strip and the
least actionable: it does not tell a cashier which check to pick up, and it
pushed the age off the chip on a busy counter.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestOpenCheckChip(MezzeHttpCase):
    fixture_profile = 'RESTAURANT'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.token = 'chip-tok'
        ICP.set_param('mezze_bridge.api_token', cls.token)
        ICP.set_param('mezze_bridge.api_security', 'observe')
        ICP.set_param('mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.sess = cls._open_session_for(cls.pos_config)
        cls.env.flush_all()

    def _order(self, qty=3, table=None, paid=0.0):
        vals = {'session_id': self.sess.id, 'company_id': self.pos_config.company_id.id,
                'amount_tax': 0, 'amount_total': 0, 'amount_paid': 0, 'amount_return': 0}
        if table is not None:
            vals['table_id'] = table.id
        o = self.env['pos.order'].create(vals)
        self.env['pos.order.line'].create({
            'order_id': o.id, 'product_id': self.product.id,
            'qty': qty, 'price_unit': 10.0, 'price_subtotal': 10.0 * qty,
            'price_subtotal_incl': 10.0 * qty})
        if paid:
            method = self.pos_config.payment_method_ids[:1]
            self.env['pos.payment'].create({
                'pos_order_id': o.id, 'amount': paid,
                'payment_method_id': method.id})
        self.env.flush_all()
        return o

    def _rows(self):
        r = self.url_open('/mezze/api/v1/orders/list',
                          data=json.dumps({'token': self.token, 'filter': 'open',
                                           'limit': 20}),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        body = r.json()
        self.assertTrue(body.get('ok'), body)
        return {row['uuid']: row for row in body.get('orders', [])}

    def test_01_the_row_carries_what_is_on_the_check(self):
        """`items` is the design's figure — the lines, not the covers."""
        o = self._order(qty=4)
        row = self._rows().get(o.uuid)
        self.assertTrue(row, 'the open check is not on the strip at all')
        self.assertEqual(row.get('items'), 4,
                         'the chip cannot say what is on the check: %r' % row)

    def test_02_a_part_paid_check_is_marked(self):
        """A check already carrying a tender is mid-settlement. Opening it blind is
        how a guest gets charged twice."""
        o = self._order(qty=2, paid=5.0)
        row = self._rows().get(o.uuid)
        self.assertTrue(row, 'the part-paid check is not on the strip')
        self.assertEqual(row.get('tendered'), 5.0,
                         'the strip cannot tell a part-paid check apart: %r' % row)

    def test_03_an_untendered_check_is_not_marked(self):
        """The mark has to discriminate, or it is decoration on every chip."""
        o = self._order(qty=2)
        row = self._rows().get(o.uuid)
        self.assertEqual(row.get('tendered'), 0.0, row)

    def test_04_a_table_check_is_named_by_its_table(self):
        table = self.tables[0]
        o = self._order(qty=1, table=table)
        row = self._rows().get(o.uuid)
        self.assertTrue(row, 'the table check is not on the strip')
        self.assertEqual(str(row.get('table')), str(table.table_number),
                         'the chip cannot name the table: %r' % row)

    def test_05_the_row_never_carries_a_bare_reference_as_its_only_name(self):
        """Every row must offer something human — a table, a guest, or a type —
        so the client never has to fall back to the database reference."""
        self._order(qty=1, table=self.tables[0])
        self._order(qty=2)
        for row in self._rows().values():
            self.assertTrue(
                row.get('table') or row.get('partner') or row.get('order_type'),
                'this check can only be named by its reference: %r' % row)
