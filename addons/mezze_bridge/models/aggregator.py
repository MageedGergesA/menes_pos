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

The webhook contract is NORMALISED (see ``controllers/aggregator.py``), and the
adaptation to a real platform's payload is CONFIGURATION rather than a shim: a
channel carries a ``payload_mapping`` saying where that platform's JSON keeps the
order id, the items, the SKU, the quantity, the price and the customer. Onboarding
Talabat is filling that in from their specification, not a code change and a
release — and the parts that are actually hard and actually shared (signature,
idempotency, SKU resolution, rejection, money) stay in one place and stay tested.

Their specs are partner-gated, so a module full of field names nobody here has seen
would look finished, pass its own tests, and be wrong in a way that only shows up on
the first live order. See ``domain/aggregator_mapping``.
"""
import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..domain import aggregator_mapping


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
    # P6.2 — the HMAC secret is envelope-encrypted at rest (AES-256-GCM, master key
    # outside the DB). ``secret`` is a NON-STORED, redacted accessor (write encrypts,
    # read returns '***') so no ORM read / serialization / export ever exposes the
    # plaintext; the verification code retrieves it via ``_secret()`` only.
    secret = fields.Char(compute='_compute_secret', inverse='_inverse_secret', store=False,
                         help="HMAC-SHA256 signing secret (write-only; stored encrypted).")
    secret_enc = fields.Char(
        string="Encrypted secret", copy=False, groups='base.group_system',
        help="AES-GCM envelope of the HMAC secret. Never read directly.")
    notify_url = fields.Char(
        string="Outbound status URL",
        help="Server-side destination for order-status callbacks to the aggregator. "
             "Resolved at delivery time by the outbox webhook consumer; never taken "
             "from an event payload. https only (SSRF-guarded).")
    active = fields.Boolean(default=True)
    auto_accept = fields.Boolean(
        default=True,
        help="Fire straight to the kitchen on receipt. Off = hold for staff accept.")
    payload_mapping = fields.Text(
        string='Payload mapping (JSON)',
        help="Where this platform's order JSON keeps the fields Mezze needs. Left "
             "empty, Mezze's own native shape is assumed.\n\n"
             "A path is dotted and a numeric segment indexes a list, e.g.\n"
             '{"external_id": "order.reference", "items": "order.basket",\n'
             ' "item_sku": "menu_item_id", "item_qty": "count",\n'
             ' "item_price": "unit_price.amount",\n'
             ' "customer_phone": "client.contacts.0.value"}\n\n'
             "Onboarding a platform is filling this in from their specification, "
             "not a code change and a release.")

    status_mapping = fields.Text(
        string='Status callback mapping (JSON)',
        help="Where this platform wants each field of a status callback, e.g.\n"
             '{"external_id": "order.reference", "status": "order.state"}\n\n'
             "Left empty, Mezze's own flat shape is sent.")
    status_names = fields.Text(
        string='Status names (JSON)',
        help="What this platform calls each Mezze status, e.g.\n"
             '{"accepted": "CONFIRMED", "out_for_delivery": "ON_THE_WAY"}\n\n'
             "A status with no name of its own is sent through unchanged: a platform "
             "receiving a word it does not know will say so, and that beats silence, "
             "which looks identical to a restaurant that never bothered.")

    @api.constrains('status_mapping', 'status_names')
    def _check_status_mapping(self):
        for rec in self:
            for field, validator in (('status_mapping',
                                      aggregator_mapping.validate_status_mapping),
                                     ('status_names', None)):
                raw = (rec[field] or '').strip()
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                except ValueError as exc:
                    raise ValidationError(_("%s is not valid JSON: %s") % (field, exc))
                if validator:
                    problems = validator(parsed)
                    if problems:
                        raise ValidationError(_("%s: %s") % (field, '; '.join(problems)))
                elif not isinstance(parsed, dict):
                    raise ValidationError(_("%s must be an object") % field)

    def _status_mapping(self):
        self.ensure_one()
        try:
            return json.loads(self.status_mapping or '{}') or {}
        except ValueError:
            return {}

    def _status_names(self):
        self.ensure_one()
        try:
            return json.loads(self.status_names or '{}') or {}
        except ValueError:
            return {}

    @api.constrains('payload_mapping')
    def _check_payload_mapping(self):
        """Refuse a mapping that could never produce an order.

        Checked when the channel is SAVED rather than when the first live order
        arrives, because the second one is somebody's dinner.
        """
        for rec in self:
            raw = (rec.payload_mapping or '').strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except ValueError as exc:
                raise ValidationError(_("Payload mapping is not valid JSON: %s") % exc)
            problems = aggregator_mapping.validate_mapping(parsed)
            if problems:
                raise ValidationError(_("Payload mapping: %s") % '; '.join(problems))

    def _mapping(self):
        """The parsed mapping, or {} for Mezze's native shape."""
        self.ensure_one()
        try:
            return json.loads(self.payload_mapping or '{}') or {}
        except ValueError:
            return {}

    commission_pct = fields.Float(
        string="Commission %", default=0.0,
        help="Informational: the aggregator's cut, recorded per order for payout "
             "reconciliation. Does NOT change what the customer paid.")

    _code_config_uniq = models.Constraint(
        'unique(code, config_id)',
        "One aggregator channel per branch.",
    )

    def _aad(self):
        self.ensure_one()
        return ('agg:%s' % (self.code or self.id)).encode()

    def _compute_secret(self):
        # secret_enc is group-restricted (system-only); the redaction marker is
        # returned so no generic ORM/RPC read ever yields plaintext.
        for r in self:
            r.secret = '***' if r.sudo().secret_enc else False

    def _inverse_secret(self):
        Store = self.env['mezze.secret.store']
        for r in self:
            val = r.secret
            if val and val != '***':
                # encrypt at rest; then drop the just-written plaintext from cache so
                # a subsequent read recomputes to the redaction marker.
                r.sudo().write({'secret_enc': Store.encrypt(val, aad=r._aad())})
        self.invalidate_recordset(['secret'])

    def _secret(self):
        """Retrieve the plaintext HMAC secret for the verification path only.
        Fails closed (None) if unset or the master key is unavailable."""
        self.ensure_one()
        enc = self.sudo().secret_enc
        if not enc:
            return None
        try:
            return self.env['mezze.secret.store'].decrypt(enc, aad=self._aad(),
                                                          purpose='aggregator_hmac')
        except Exception:  # noqa: BLE001 — fail closed
            return None

    def _migrate_plaintext_secrets(self):
        """Idempotently migrate legacy plaintext HMAC secrets to envelope ciphertext.

        Handles both (a) plaintext sitting in ``secret_enc`` (e.g. a raw copy) and
        (b) the legacy pre-encryption ``secret`` column, which Odoo leaves in place
        when the field became non-stored — its values are encrypted then the column
        is dropped so no plaintext survives. Skips already-enveloped values; never
        logs a value; fails closed if the master key is missing."""
        from ..domain import crypto
        Store = self.env['mezze.secret.store']
        cr = self.env.cr
        migrated = 0
        # (b) legacy plaintext column
        cr.execute("SELECT 1 FROM information_schema.columns "
                   "WHERE table_name='mezze_aggregator' AND column_name='secret'")
        if cr.fetchone():
            cr.execute("SELECT id, secret FROM mezze_aggregator "
                       "WHERE secret IS NOT NULL AND secret <> ''")
            for aid, plain in cr.fetchall():
                r = self.browse(aid)
                r.sudo().write({'secret_enc': Store.encrypt(plain, aad=r._aad())})
                migrated += 1
            cr.execute("ALTER TABLE mezze_aggregator DROP COLUMN secret")
        # (a) plaintext accidentally in the ciphertext column
        cr.execute("SELECT id, secret_enc FROM mezze_aggregator "
                   "WHERE secret_enc IS NOT NULL AND secret_enc <> ''")
        for aid, enc in cr.fetchall():
            if not crypto.is_envelope(enc):
                r = self.browse(aid)
                r.sudo().write({'secret_enc': Store.encrypt(enc, aad=r._aad())})
                migrated += 1
        return migrated


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
    # NOTE: ``mezze_notify`` lives here rather than on the controller because two
    # callers need it — the ingestion webhook and the delivery FSM — and a model is
    # the only place both can reach without a request context. A second copy in the
    # controller is how the two would drift.

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

    def mezze_notify(self, status):
        """Tell the platform where its order has got to.

        Best-effort and never inline: it goes through the same outbox the accept
        callback uses, so delivery is durable, retried and dead-lettered, and a
        platform being down can never roll back a state change that has already
        happened in the restaurant. A courier does not un-leave because an API
        timed out.
        """
        self.ensure_one()
        channel = self.aggregator_id
        order = self.pos_order_id
        if not channel or not order:
            return False
        canonical = {'external_id': self.external_id, 'status': status,
                     'pos_reference': order.pos_reference,
                     'gross_total': self.gross_total}
        # Shaped the way THIS platform wants it. ``order_id`` is deliberately absent:
        # it is a database key of ours, meaningless to them, and there is no reason
        # to hand an external party our primary keys.
        payload = aggregator_mapping.build_status(
            canonical, channel._status_mapping(), channel._status_names())
        from ..controllers.main import MezzeBridgeController
        MezzeBridgeController()._publish_webhook(
            self.env, channel, order, 'order.%s' % status, payload)
        return True
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
