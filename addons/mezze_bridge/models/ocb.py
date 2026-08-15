# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Order Confirmation Board — the customer's view of the order being typed.

A guest at a drive-thru window cannot see the operator's screen, so the first time
they learn what was ordered is when the bag arrives. The OCB puts the order in front
of them **while it is being entered**, so a wrong item, a missing modifier or a
surprising total is caught before anything is fired. That is the whole product: an
accuracy device, not signage and not a second POS.

The awkward part, audited in ``docs/drive_thru/OCB-DATA-FLOW-AUDIT.md``: the
drive-thru cart is a JavaScript array in the operator's browser and nothing exists on
the server until Send to kitchen. There is no draft to read. So the operator's page
PUBLISHES its cart here on every change, and this record is the server-side
projection the customer's display reads.

Two deliberate choices follow from that:

* **Money is computed here, never in the display's JavaScript.** The projection runs
  the real pricelist and the product's own taxes through Odoo's ``compute_all``, so
  the customer sees the same arithmetic the order will use rather than a second
  implementation of it.
* **The snapshot lives in the database, not in a worker's memory.** Four workers, a
  page reload and an Odoo restart all have to show the same order, and only shared
  state does that.

The display's credential is a ``mezze.terminal`` — the model that already stores an
opaque token as a non-reversible fingerprint — rather than a parallel device
architecture invented for this screen.
"""
import json

from odoo import api, fields, models

#: What the customer's screen is showing. `offline` is never stored — it is what the
#: display itself concludes when it cannot reach the server.
OCB_STATES = [
    ('idle', 'Ready for an order'),
    ('ordering', 'Order being entered'),
    ('confirmed', 'Order confirmed'),
]

#: How long a confirmation stays up before the display returns to idle. Short on
#: purpose: the next car is already at the speaker.
CONFIRM_SECONDS = 8


class MezzeOcbDisplay(models.Model):
    _name = 'mezze.ocb.display'
    _description = 'Mezze Drive-Thru Order Confirmation Display'
    _order = 'config_id, lane, id'

    name = fields.Char(required=True, help="Human label, e.g. 'Lane 1 confirmation board'.")
    identifier = fields.Char(
        required=True, index=True, copy=False,
        help="Stable id for provisioning, e.g. ocb-<config>-<lane>.")
    config_id = fields.Many2one('pos.config', string='Branch', required=True,
                                ondelete='cascade', index=True)
    lane = fields.Integer(required=True, default=1, index=True,
                          help="The ordering lane this display belongs to. A display "
                               "serves exactly one lane and can never show another.")
    #: The display's own credential. Reusing mezze.terminal means the opaque token is
    #: stored only as a fingerprint and the existing rotation/revocation machinery
    #: applies unchanged.
    terminal_id = fields.Many2one('mezze.terminal', ondelete='set null', copy=False)
    lang = fields.Char(
        default='en_US',
        help="Display language. NOT the operator's language: a cashier working in "
             "Arabic must not turn an English-speaking guest's screen Arabic. There "
             "is no customer-language truth in the product, so this is display "
             "configuration rather than an inferred preference.")
    active = fields.Boolean(default=True)
    last_seen = fields.Datetime(help="Last time the display asked for state.")

    # ---- transient projection -------------------------------------------------
    # The live order is here because there is nowhere else: pre-fire, no pos.order
    # exists (see the data-flow audit). This is the only server copy, so it is not a
    # redundant one. It is cleared the moment the order ends.
    state = fields.Selection(OCB_STATES, default='idle', required=True, index=True)
    revision = fields.Integer(
        default=0, copy=False,
        help="Monotonic per display. A display must never apply an older snapshot "
             "after a newer one, and polling can deliver responses out of order.")
    payload = fields.Text(copy=False, help="JSON snapshot the display renders. Transient.")
    payload_at = fields.Datetime(copy=False)
    #: Set only once the order actually exists, so the confirmation can name it.
    order_ref = fields.Char(copy=False)

    _sql_constraints = []

    # ------------------------------------------------------------------ lookup
    @api.model
    def _resolve_token(self, raw):
        """The display for a presented RAW token, or an empty recordset.

        The token is the ONLY input. There is deliberately no lane parameter to
        override and no id to increment: a credential resolves to exactly one
        display, and that display's lane is the only lane it can ever see.
        """
        if not raw or len(str(raw)) < 24:
            return self.browse()
        Term = self.env['mezze.terminal'].sudo()
        fp = self.env['mezze.secret.store'].token_hash(str(raw))
        term = Term.with_context(active_test=False).search(
            [('token_fingerprint', '=', fp)], limit=1) if fp else Term
        if not term:                      # dev fallback, mirrors _resolve_principal
            term = Term.with_context(active_test=False).search(
                [('token', '=', str(raw))], limit=1)
        if not term or not term.active:
            return self.browse()
        display = self.sudo().search([('terminal_id', '=', term.id)], limit=1)
        return display if display and display.active else self.browse()

    @api.model
    def _provision(self, config, lane=1, name=None, lang='en_US'):
        """Create (or re-key) a display and return ``(display, raw_token)``.

        The raw token is returned ONCE and never stored — only its fingerprint is,
        exactly as terminals work. Deliberately a method rather than a wizard: a
        display is provisioned once, by an admin, and then a kiosk browser is pointed
        at the URL forever.

            display, token = env['mezze.ocb.display']._provision(config, lane=1)
            url = '/mezze/ocb/%s' % token
        """
        import secrets
        config = config.sudo()
        identifier = 'ocb-%s-%s' % (config.id, int(lane or 1))
        raw = secrets.token_urlsafe(32)
        Term = self.env['mezze.terminal'].sudo()
        term = Term.with_context(active_test=False).search(
            [('identifier', '=', identifier)], limit=1)
        # role='kitchen' is the narrowest existing principal: read-only over kitchen
        # state and orders, with no pay/fire/drawer/admin. A customer display holds no
        # capability it could ever need to use — it never calls a capability-gated
        # endpoint — but it must not carry a station's rights if it is ever misused.
        vals = {'token': raw, 'branch_id': config.id, 'active': True, 'role': 'kitchen'}
        if term:
            term.write(vals)
        else:
            term = Term.create(dict(vals, name='OCB — %s lane %s' % (config.name, lane),
                                    identifier=identifier))
        display = self.sudo().search([('identifier', '=', identifier)], limit=1)
        dvals = {'config_id': config.id, 'lane': int(lane or 1), 'terminal_id': term.id,
                 'lang': lang or 'en_US', 'active': True,
                 'name': name or 'Lane %s confirmation board' % int(lane or 1)}
        if display:
            display.write(dvals)
        else:
            display = self.sudo().create(dict(dvals, identifier=identifier))
        return display, raw

    @api.model
    def _for_lane(self, config, lane):
        """The display serving one lane of one branch, or empty."""
        if not config:
            return self.browse()
        return self.sudo().search(
            [('config_id', '=', config.id), ('lane', '=', int(lane or 1))], limit=1)

    # ------------------------------------------------------------------ pricing
    def _price_lines(self, lines):
        """Money for a pre-fire cart, through the SAME path the order will use.

        Pre-fire there is no pos.order to ask, so the projection prices the cart from
        the branch's pricelist and each product's own taxes via Odoo's ``compute_all``
        — the engine, not a reimplementation of it. Read in ONE batch: the display
        polls, and a per-line product read would be an N+1 on a customer screen.

        Returns ``(rows, money)``. Only rows that exist are reported: a branch with no
        tax gets no tax row, because inventing "VAT 15%" on a customer's screen is a
        lie with a number on it.
        """
        self.ensure_one()
        rows, subtotal, tax_total = [], 0.0, 0.0
        ids = [int(l.get('product_id')) for l in (lines or []) if l.get('product_id')]
        if not ids:
            return rows, {'subtotal': 0.0, 'tax': 0.0, 'total': 0.0}
        products = self.env['product.product'].sudo().browse(ids).exists()
        by_id = {p.id: p for p in products}
        products.mapped('taxes_id')                       # one prefetch for the batch
        pricelist = self.config_id.sudo().pricelist_id
        company = self.config_id.sudo().company_id
        # Price in BATCHES, one per distinct quantity. A pricelist can have quantity
        # breaks, so a single price per product would be wrong; but the distinct
        # quantities in a cart are bounded by the menu, not by how many lines the
        # operator types, so the work stops growing with the order.
        price_by = {}
        if pricelist:
            by_qty = {}
            for line in (lines or []):
                pid = int(line.get('product_id') or 0)
                qty = float(line.get('qty') or 0)
                if pid in by_id and qty > 0:
                    by_qty.setdefault(qty, set()).add(pid)
            for qty, pids in by_qty.items():
                try:
                    priced = pricelist._get_products_price(
                        products.filtered(lambda p: p.id in pids), qty)
                except Exception:      # noqa: BLE001 — a pricelist must never blank the board
                    priced = {}
                for pid, value in (priced or {}).items():
                    price_by[(pid, qty)] = value
        for line in (lines or []):
            product = by_id.get(int(line.get('product_id') or 0))
            if not product:
                continue
            qty = float(line.get('qty') or 0)
            if qty <= 0:
                continue
            price = price_by.get((product.id, qty), product.list_price)
            taxes = product.taxes_id.filtered(lambda t: t.company_id == company) or product.taxes_id
            if taxes:
                computed = taxes.compute_all(price, currency=company.currency_id,
                                             quantity=qty, product=product)
                net, gross = computed['total_excluded'], computed['total_included']
            else:
                net = gross = price * qty
            subtotal += net
            tax_total += gross - net
            rows.append({
                # `name`, not display_name: an internal code like "[GIFTCARD]" is
                # noise on a screen a customer is reading from a car.
                'name': product.name,
                'qty': qty,
                # Modifiers are rendered when they exist. The drive-thru order taker
                # does not collect any today (see the data-flow audit); nothing is
                # invented to fill the space.
                'modifiers': [m for m in (line.get('modifiers') or []) if m],
                'note': (line.get('note') or '').strip() or None,
                'line_total': round(gross, 2),
            })
        return rows, {'subtotal': round(subtotal, 2),
                      'tax': round(tax_total, 2),
                      'total': round(subtotal + tax_total, 2)}

    # ------------------------------------------------------------------ publish
    def _publish(self, lines):
        """The operator's cart changed. Project it for the customer."""
        self.ensure_one()
        rows, money = self._price_lines(lines)
        if not rows:
            return self._clear()
        currency = self.config_id.sudo().company_id.currency_id
        snapshot = {
            'lines': rows,
            'money': money,
            'currency': {'name': currency.name,
                         'symbol': currency.symbol,
                         'position': currency.position,
                         'decimals': currency.decimal_places},
        }
        self.sudo().write({
            'state': 'ordering',
            'revision': self.revision + 1,
            'payload': json.dumps(snapshot),
            'payload_at': fields.Datetime.now(),
            'order_ref': False,
        })
        return self

    def _confirm(self, order=None):
        """The order was sent. Say thank you, briefly, then idle."""
        self.ensure_one()
        ref = ''
        if order:
            ref = order.tracking_number or order.pos_reference or ''
        self.sudo().write({
            'state': 'confirmed',
            'revision': self.revision + 1,
            'payload_at': fields.Datetime.now(),
            'order_ref': ref or False,
        })
        return self

    def _clear(self):
        """Back to idle, and the previous customer's order is GONE.

        Cleared rather than left behind: the next guest must not read the last one's
        order, which is a privacy question before it is an accuracy one.
        """
        self.ensure_one()
        self.sudo().write({
            'state': 'idle',
            'revision': self.revision + 1,
            'payload': False,
            'payload_at': fields.Datetime.now(),
            'order_ref': False,
        })
        return self

    # ------------------------------------------------------------------ read
    def _snapshot(self):
        """What the customer's display renders. Nothing else is in here.

        Deliberately absent: employee identity, cashier or user ids, terminal or
        session tokens, product ids, cost, margin, tax ids, KDS routing, database ids,
        POS config internals, vehicle free text. A public screen gets the order and
        the lane, and that is all.
        """
        self.ensure_one()
        state = self.state
        data = None
        if state == 'ordering' and self.payload:
            try:
                data = json.loads(self.payload)
            except ValueError:
                state, data = 'idle', None
        if state == 'confirmed' and self._confirmation_expired():
            state = 'idle'
        out = {
            'display': {'name': self.name, 'lane': self.lane, 'lang': self.lang or 'en_US'},
            'state': state,
            'revision': self.revision,
            'order': None,
        }
        if state == 'ordering' and data:
            out['order'] = {'ref': None, 'lines': data.get('lines') or [],
                            'money': data.get('money') or {},
                            'currency': data.get('currency') or {}}
        elif state == 'confirmed':
            out['order'] = {'ref': self.order_ref or None, 'lines': [],
                            'money': {}, 'currency': {}}
        return out

    def _confirmation_expired(self):
        self.ensure_one()
        if not self.payload_at:
            return True
        delta = fields.Datetime.now() - self.payload_at
        return delta.total_seconds() > CONFIRM_SECONDS
