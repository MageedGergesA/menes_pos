# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Delivery-aggregator ingestion (Talabat / Jahez / HungerStation / …).

Odoo Community has no connector for the MENA food aggregators, so this is a
real build — but a THIN one: an aggregator order is just a prepaid delivery,
so ingestion maps the external payload to the SAME paid-`pos.order` +
`mezze.delivery` + KDS-ticket flow the on-premise delivery path already uses.

Three records model the integration:
  * ``mezze.aggregator``            — one channel per (aggregator, branch): its
    signing secret, the prepaid tender to book against, auto-accept, commission.
  * ``mezze.aggregator.product.map``— external menu SKU → Odoo product. Unmapped
    SKUs make an order REJECT (never silently drop an item = money/stock bug).
  * ``mezze.aggregator.order``      — one ingested order: idempotency key
    (aggregator, external_id), links to the pos.order/delivery, raw payload,
    gross/commission/payout, lifecycle.

The webhook contract is NORMALISED (see ``controllers/aggregator.py``): each
real aggregator's payload/signature scheme is adapted to it by a thin shim once
their partner API spec + credentials are available.
"""
from odoo import api, fields, models


class MezzeAggregator(models.Model):
    _name = 'mezze.aggregator'
    _description = "Mezze Delivery Aggregator Channel"
    _order = 'code, id'

    code = fields.Char(required=True, index=True,
                       help="Stable slug used in the webhook URL, e.g. 'talabat'.")
    name = fields.Char(required=True)
    config_id = fields.Many2one('pos.config', string="Branch", required=True,
                                ondelete='cascade', index=True)
    payment_method_id = fields.Many2one(
        'pos.payment.method', string="Prepaid tender", ondelete='set null',
        help="The POS payment method the prepaid aggregator total is booked to. "
             "Falls back to the branch's first tender when unset.")
    secret = fields.Char(help="HMAC-SHA256 signing secret shared with the aggregator. "
                              "Webhooks are rejected unless signed with it.")
    active = fields.Boolean(default=True)
    auto_accept = fields.Boolean(
        default=True,
        help="Fire straight to the kitchen on receipt. Off = hold for staff accept.")
    commission_pct = fields.Float(
        string="Commission %", default=0.0,
        help="Informational: the aggregator's cut, recorded per order for payout "
             "reconciliation. Does NOT change what the customer paid.")

    _code_config_uniq = models.Constraint(
        'unique(code, config_id)',
        "One aggregator channel per branch.",
    )


class MezzeAggregatorProductMap(models.Model):
    _name = 'mezze.aggregator.product.map'
    _description = "Mezze Aggregator Menu Mapping"
    _order = 'aggregator_id, external_sku'

    aggregator_id = fields.Many2one('mezze.aggregator', required=True,
                                    ondelete='cascade', index=True)
    external_sku = fields.Char(required=True, index=True,
                               help="The item id/SKU as the aggregator sends it.")
    product_id = fields.Many2one('product.product', required=True, ondelete='cascade')

    _sku_uniq = models.Constraint(
        'unique(aggregator_id, external_sku)',
        "Each aggregator SKU maps to one product.",
    )


class MezzeAggregatorOrder(models.Model):
    _name = 'mezze.aggregator.order'
    _description = "Mezze Aggregator Order"
    _order = 'received_at desc, id desc'

    aggregator_id = fields.Many2one('mezze.aggregator', required=True,
                                    ondelete='cascade', index=True)
    config_id = fields.Many2one('pos.config', related='aggregator_id.config_id',
                                store=True, index=True)
    external_id = fields.Char(required=True, index=True,
                              help="The aggregator's own order id — idempotency key.")
    pos_order_id = fields.Many2one('pos.order', ondelete='set null', index=True)
    delivery_id = fields.Many2one('mezze.delivery', ondelete='set null')
    state = fields.Selection(
        [('received', 'Received'), ('rejected', 'Rejected'),
         ('cancelled', 'Cancelled')],
        default='received', required=True, index=True)
    reject_reason = fields.Char()
    unmapped_skus = fields.Char()

    customer_name = fields.Char()
    phone = fields.Char()
    address = fields.Text()

    gross_total = fields.Float(help="What the customer paid the aggregator.")
    commission = fields.Float(help="Aggregator's cut (gross × commission%).")
    net_payout = fields.Float(help="Expected payout to the restaurant (gross − commission).")

    raw_payload = fields.Text(help="The raw normalised webhook body, for audit/debug.")
    received_at = fields.Datetime(default=fields.Datetime.now, index=True)

    _agg_ext_uniq = models.Constraint(
        'unique(aggregator_id, external_id)',
        "An aggregator order is ingested once (idempotency).",
    )

    @api.model
    def _find(self, aggregator, external_id):
        return self.search([('aggregator_id', '=', aggregator.id),
                            ('external_id', '=', external_id)], limit=1)
