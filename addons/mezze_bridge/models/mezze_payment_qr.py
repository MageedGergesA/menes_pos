"""S2C-4 — Bank App (Payment) QR. Reuses Odoo's NATIVE QR generator
(pos.payment.method.get_qr_code / res.partner.bank.build_qr_code_base64) — Mezze
writes NO QR-format code (see docs/sell-ready/payments/payment-qr-audit.md).

Native Odoo POS Bank-App-QR is CASHIER-CONFIRMED (the QRPopup returns a boolean the
cashier chooses; there is no automatic bank webhook). This model preserves that
manual model with server authority over amount/currency/account/payload:

  * the amount is the order's authoritative remaining (or a partial ceiling) — the
    browser cannot inflate it;
  * a durable ``token`` binds the QR to (order, method, amount, remaining_snapshot);
  * confirm is a manual cashier action that requires the QR to still match the
    order's CURRENT remaining (any change ⇒ stale_qr ⇒ regenerate) and produces
    exactly ONE pos.payment (idempotent via tender_key=token + SELECT..FOR UPDATE +
    the unique(pos_order_id, mezze_tender_key) constraint);
  * provenance is ``manual`` — the bank is NOT auto-verified.

This is completely separate from Table QR (self-order /qr/menu,/qr/bill,/qr/pay).
"""
import base64
import io
import json
import logging
import secrets

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

STATE_PENDING = 'pending'
STATE_CONFIRMED = 'confirmed'
STATE_CANCELLED = 'cancelled'


class MezzePaymentQr(models.Model):
    _name = 'mezze.payment.qr'
    _description = 'Mezze bank-app payment QR (generate + manual confirm)'
    _order = 'id desc'

    token = fields.Char(required=True, index=True, copy=False,
                        help='Durable identity; also the payment idempotency key.')
    pos_order_id = fields.Many2one('pos.order', required=True, ondelete='cascade', index=True)
    payment_method_id = fields.Many2one('pos.payment.method', required=True)
    amount = fields.Float(required=True)
    remaining_snapshot = fields.Float(required=True,
                                      help='Order remaining at generation; confirm requires it unchanged (stale guard).')
    currency_id = fields.Many2one('res.currency')
    qr_method = fields.Char(help='Native res.partner.bank QR method id (e.g. sct_qr, emv_qr).')
    reference = fields.Char(help='Free communication encoded in the QR (order reference).')
    state = fields.Selection([(STATE_PENDING, 'Pending'), (STATE_CONFIRMED, 'Confirmed'),
                              (STATE_CANCELLED, 'Cancelled')], default=STATE_PENDING, required=True, index=True)
    pos_payment_id = fields.Many2one('pos.payment', ondelete='set null', copy=False)

    _token_uniq = models.Constraint('unique(token)', 'QR token must be unique.')

    # ------------------------------------------------------------------ helpers
    @api.model
    def _new_token(self):
        return 'mzq-' + secrets.token_urlsafe(18)

    def _order_remaining(self):
        self.ensure_one()
        order = self.pos_order_id
        prec = order.currency_id.decimal_places or 2
        paid = round(sum(order.payment_ids.mapped('amount')), prec)
        return round(order.amount_total - paid, prec)

    def _bank_account(self):
        self.ensure_one()
        return self.payment_method_id.journal_id.bank_account_id

    # ------------------------------------------------------------------ lifecycle
    @api.model
    def mezze_generate(self, order, method, amount=None):
        """Create a QR generate-record with a server-authoritative amount and return
        it. Validates the method is a properly-configured bank-app QR method."""
        if method.payment_method_type != 'qr_code' or not method.qr_code_method:
            raise UserError("Payment method %r is not a configured Bank App QR method." % method.name)
        bank = method.journal_id.bank_account_id
        if method.journal_id.type != 'bank' or not bank:
            raise UserError("Method %r needs a bank journal with a bank account to generate QR codes." % method.name)
        prec = order.currency_id.decimal_places or 2
        eps = 1.0 / (10 ** prec)
        paid = round(sum(order.payment_ids.mapped('amount')), prec)
        remaining = round(order.amount_total - paid, prec)
        if remaining <= eps:
            raise UserError("This order is already fully paid.")
        amt = round(float(amount), prec) if amount is not None else remaining
        if amt <= 0:
            raise UserError("QR amount must be positive.")
        if amt - remaining > eps:
            raise UserError("QR amount exceeds the remaining balance.")
        if amt + eps < remaining and not method.mezze_allow_partial:
            raise UserError("Partial payment is not allowed for %r." % method.name)
        return self.sudo().create({
            'token': self._new_token(),
            'pos_order_id': order.id,
            'payment_method_id': method.id,
            'amount': amt,
            'remaining_snapshot': remaining,
            'currency_id': order.currency_id.id,
            'qr_method': method.qr_code_method,
            'reference': order.pos_reference or order.name or '',
            'state': STATE_PENDING,
        })

    def native_payload(self):
        """The RAW string the QR encodes, from Odoo's native generator. Contains the
        bank/amount/currency/reference — never a Mezze token."""
        self.ensure_one()
        bank = self._bank_account()
        params = bank._get_qr_code_generation_params(
            self.qr_method, self.amount, self.currency_id, self.pos_order_id.partner_id,
            self.reference or '', '')
        return params.get('value') if params else ''

    def native_image(self):
        """Base64 data-URI PNG of the NATIVE payload. Prefers Odoo's own rasterizer
        (get_qr_code); if the environment cannot raster it (e.g. reportlab renderPM
        is missing its T1 fonts), falls back to rendering the SAME native payload
        with the qrcode library — the ENCODED CONTENT is identical, only the pixels
        are drawn by a different rasterizer."""
        self.ensure_one()
        try:
            return self.payment_method_id.get_qr_code(
                self.amount, self.reference or '', '', self.currency_id.id,
                self.pos_order_id.partner_id.id or False)
        except Exception as e:  # noqa: BLE001 — env raster failure, not a data error
            _logger.warning("Native QR raster failed (%s); rendering native payload with qrcode.", e)
            return self._render_payload_png(self.native_payload())

    @staticmethod
    def _render_payload_png(payload):
        """Render an exact QR PNG (data-URI) of a payload with the qrcode library."""
        import qrcode  # system dependency; encode-only, no font needed
        img = qrcode.make(payload or '')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()

    def mezze_cancel(self):
        self.ensure_one()
        if self.state == STATE_CONFIRMED:
            raise UserError("A confirmed QR payment cannot be cancelled here.")
        if self.state == STATE_CANCELLED:
            return self
        self.state = STATE_CANCELLED
        self._log('qr.cancelled', {'token': self.token})
        return self

    def mezze_confirm(self, actor=None):
        """Manual cashier confirmation of a scanned/paid QR. Server-authoritative:
        the QR must still match the order's CURRENT remaining (stale guard) and
        produces exactly ONE pos.payment (idempotent + concurrency-safe). Provenance
        is manual — the bank is NOT auto-verified."""
        self.ensure_one()
        # serialise concurrent confirms of THIS token
        self.env.cr.execute("SELECT id FROM mezze_payment_qr WHERE id=%s FOR UPDATE", (self.id,))
        self.invalidate_recordset(['state', 'pos_payment_id'])
        if self.state == STATE_CONFIRMED:
            return self.pos_payment_id  # idempotent
        if self.state == STATE_CANCELLED:
            raise UserError("This QR was cancelled; generate a new one.")
        order = self.pos_order_id
        prec = order.currency_id.decimal_places or 2
        eps = 1.0 / (10 ** prec)
        current_remaining = self._order_remaining()
        # STALE guard: any change to the order/remaining since generation invalidates
        # the displayed QR (its encoded amount no longer matches what is due).
        if abs(current_remaining - self.remaining_snapshot) > eps:
            raise UserError("The order changed since this QR was generated — regenerate the QR.")
        if self.amount - current_remaining > eps:
            raise UserError("QR amount exceeds the remaining balance.")
        # durable idempotency backstop
        existing = order.payment_ids.filtered(lambda p: p.mezze_tender_key == self.token)
        if existing:
            self.write({'state': STATE_CONFIRMED, 'pos_payment_id': existing[:1].id})
            return existing[:1]
        vals = {
            'amount': self.amount, 'payment_method_id': self.payment_method_id.id,
            'name': fields.Datetime.now(), 'pos_order_id': order.id,
            'mezze_tender_key': self.token,
            'mezze_confirmation_source': 'manual',   # cashier-confirmed, not bank-verified
            'payment_ref_no': (self.reference or '')[:64],
        }
        order.add_payment(vals)
        payment = order.payment_ids.filtered(lambda p: p.mezze_tender_key == self.token)[:1]
        self.write({'state': STATE_CONFIRMED, 'pos_payment_id': payment.id})
        if self._order_remaining() <= eps and order.state == 'draft':
            order.action_pos_order_paid()
        self._log('qr.confirmed', {'token': self.token, 'amount': self.amount,
                                   'method': self.payment_method_id.name, 'actor': actor or ''})
        return payment

    # ------------------------------------------------------------------ audit
    def _log(self, event, detail):
        try:
            self.env['mezze.audit.log'].sudo().log(
                event, severity='info', res_model='pos.order',
                res_id=self.pos_order_id.id, res_uuid=self.pos_order_id.uuid or False,
                detail=json.dumps(detail))
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ projection
    def mezze_payload(self, include_image=False):
        """PII-safe projection for the cashier. The QR image/payload are the native
        bank content (no Mezze secret). ``reference`` is the order reference."""
        self.ensure_one()
        order = self.pos_order_id
        prec = order.currency_id.decimal_places or 2
        paid = round(sum(order.payment_ids.mapped('amount')), prec)
        data = {
            'qr_token': self.token,   # NB: request param is 'qr_token' — 'token' is the bearer
            'state': self.state,
            'amount': round(self.amount, prec),
            'currency': self.currency_id.name,
            'qr_method': self.qr_method or '',
            'reference': self.reference or '',
            'paid': paid,
            'remaining': round(order.amount_total - paid, prec),
            'order_total': round(order.amount_total, prec),
            'order_state': order.state,
            'pos_reference': order.pos_reference or '',
            'has_payment': bool(self.pos_payment_id),
        }
        if include_image:
            data['image'] = self.native_image()
            data['payload'] = self.native_payload()  # public bank content (for decode/verify)
        return data
