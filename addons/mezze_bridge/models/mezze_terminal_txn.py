"""S2C-3 — Integrated payment terminal transaction (server-authoritative).

Mezze reimplements NO provider protocol (see docs/sell-ready/payments/
integrated-terminal-audit.md). This model is the durable, server-side source of
truth for ONE integrated-terminal attempt. Its purpose is three invariants that a
browser can never be trusted to keep:

  1. The OUTCOME is decided on the server. A browser POST of {"approved": true}
     can never mint a payment. For the TEST simulator the server computes the
     result from the request's stored scenario (the client's claim is ignored /
     audited). For a real native provider the completion is simply not accepted
     (integration PENDING) — no fake success.
  2. ONE approved terminal transaction => exactly ONE pos.payment, via the SAME
     converging path as /orders/pay, idempotent on the durable request_id (reused
     as the per-tender idempotency key) and serialised with SELECT ... FOR UPDATE.
  3. Force Done is a manager-gated MANUAL OVERRIDE with its own provenance and a
     reconciliation flag — never confused with a provider-confirmed payment.
"""
import json
import secrets

from odoo import api, fields, models
from odoo.exceptions import UserError

# Normalized cashier-facing states (S2C-3 §7). Native provider/paymentline states
# are mapped onto these; nothing provider-specific leaks to the UI.
STATE_READY = 'ready'
STATE_SENDING = 'sending'
STATE_WAITING = 'waiting_customer'
STATE_PROCESSING = 'processing'
STATE_APPROVED = 'approved'
STATE_DECLINED = 'declined'
STATE_CANCELLED = 'cancelled'
STATE_ERROR = 'error'
STATE_TIMEOUT = 'timeout'
STATE_UNKNOWN = 'unknown'

# States where a physical request is still live (single-in-flight guard, §30).
ACTIVE_STATES = (STATE_SENDING, STATE_WAITING, STATE_PROCESSING)
# Terminal (settled) states.
FINAL_STATES = (STATE_APPROVED, STATE_DECLINED, STATE_CANCELLED)
# Uncertain: a charge MIGHT exist — never auto-retry, force-done eligible (§16-22).
UNCERTAIN_STATES = (STATE_ERROR, STATE_TIMEOUT, STATE_UNKNOWN)

# TEST-ONLY simulator scenarios (§40). Map a scenario to the authoritative outcome
# the SERVER will apply. DELAYED_SUCCESS/DUPLICATE_SUCCESS are UX behaviours handled
# by the client adapter; their financial outcome is a normal success.
_SIM_OUTCOME = {
    'success': STATE_APPROVED,
    'delayed_success': STATE_APPROVED,
    'duplicate_success': STATE_APPROVED,
    'decline': STATE_DECLINED,
    'cancel': STATE_CANCELLED,
    'error': STATE_ERROR,
    'timeout': STATE_TIMEOUT,
    'unknown': STATE_UNKNOWN,
}

# S2C-7 — TEST-ONLY cash-machine simulator scenarios. Maps a scenario to the
# authoritative outcome the SERVER applies for a `kind='cash_machine'` request. As
# with the card simulator, this tests Mezze's ORCHESTRATION — it does NOT implement
# the Glory (or any) device protocol (see docs/…/cash-machine-audit.md). A native
# connection failure is documented by Odoo as a transaction cancellation → no
# payment, order stays payable (never a stuck 'pending').
_CASH_SIM_OUTCOME = {
    'success_exact': STATE_APPROVED,
    'success_with_change': STATE_APPROVED,
    'delayed_success': STATE_APPROVED,
    'duplicate_success': STATE_APPROVED,
    'cancel': STATE_CANCELLED,
    'connection_error': STATE_CANCELLED,   # native: connection failure == cancellation
    'unknown': STATE_UNKNOWN,
}
# NOTE on refunds (§38-42): Odoo's Glory integration exposes only a manager-only
# negative-amount cash *dispense*, welded to the coupled native GloryService; there is
# no standalone device path, so a device-confirmed cash-machine REFUND is classified
# ADAPTER PENDING (refused server-side, never faked). The refund *ceiling/engine* is the
# already-certified L2 refund (/orders/refund). See docs/…/cash-machine-audit.md.


class MezzeTerminalTransaction(models.Model):
    _name = 'mezze.terminal.transaction'
    _description = 'Mezze integrated payment terminal transaction'
    _order = 'id desc'

    request_id = fields.Char(required=True, index=True, copy=False,
                             help='Durable, server-minted identity for this attempt (also the payment idempotency key).')
    # S2C-7: the same server-authoritative spine backs integrated card terminals
    # (kind='terminal') and automated cash machines (kind='cash_machine'). The money
    # invariants are identical; only the cashier-facing states and change reporting
    # differ. Default keeps every existing terminal row behaving exactly as before.
    kind = fields.Selection([('terminal', 'Integrated terminal'),
                             ('cash_machine', 'Cash machine')], default='terminal', required=True, index=True)
    pos_order_id = fields.Many2one('pos.order', required=True, ondelete='cascade', index=True)
    payment_method_id = fields.Many2one('pos.payment.method', required=True)
    mezze_device_id = fields.Many2one('mezze.payment.device', ondelete='set null')
    provider = fields.Char(help="Native terminal integration id, or 'test' for the simulator.")
    amount = fields.Float(required=True)
    currency_id = fields.Many2one('res.currency')
    state = fields.Selection([
        (STATE_READY, 'Ready'), (STATE_SENDING, 'Sending'), (STATE_WAITING, 'Waiting for customer'),
        (STATE_PROCESSING, 'Processing'), (STATE_APPROVED, 'Approved'), (STATE_DECLINED, 'Declined'),
        (STATE_CANCELLED, 'Cancelled'), (STATE_ERROR, 'Error'), (STATE_TIMEOUT, 'Timeout'),
        (STATE_UNKNOWN, 'Unknown')], default=STATE_READY, required=True, index=True)
    uncertain = fields.Boolean(default=False,
                               help='A charge may exist but is unconfirmed — force-done eligible; never auto-retried.')
    provider_reference = fields.Char(help='Safe provider/terminal reference on success (no PAN/secret).')
    authcode = fields.Char()
    card_type = fields.Char()
    pos_payment_id = fields.Many2one('pos.payment', ondelete='set null', copy=False,
                                     help='The ONE payment produced by an authoritative approval / force done.')
    force_done = fields.Boolean(default=False)
    # TEST-ONLY: the deterministic scenario the simulator will resolve to. Populated
    # only when provider='test'; ignored for real providers.
    sim_scenario = fields.Char()
    error_code = fields.Char(help='Operational, non-sensitive error tag for the UI.')
    # S2C-7 cash-machine reporting. The machine counts inserted cash and returns
    # change; the PAYMENT is always the net (== amount, <= remaining) — inserted cash
    # is NEVER booked as revenue. change_amount is display/receipt only.
    inserted_amount = fields.Float(default=0.0, help='Cash the machine counted (device-reported).')
    change_amount = fields.Float(default=0.0, help='Change the machine returned (device-reported).')
    # TEST-ONLY: simulated inserted cash for the success_with_change scenario.
    sim_inserted = fields.Float(default=0.0)

    _request_uniq = models.Constraint('unique(request_id)', 'Terminal request id must be unique.')

    # ------------------------------------------------------------------ helpers
    @api.model
    def _new_request_id(self):
        return 'mzt-' + secrets.token_urlsafe(18)

    def _is_test(self):
        self.ensure_one()
        return (self.provider or '') == 'test'

    def _order_remaining(self):
        """Authoritative remaining balance from the order (never trusts the client)."""
        self.ensure_one()
        order = self.pos_order_id
        prec = order.currency_id.decimal_places or 2
        paid = round(sum(order.payment_ids.mapped('amount')), prec)
        return round(order.amount_total - paid, prec)

    # ------------------------------------------------------------------ lifecycle
    @api.model
    def mezze_start(self, order, method, device, amount, provider):
        """Open ONE integrated-terminal request with a server-authoritative amount.
        Enforces single-in-flight per order (§30) and the partial-payment ceiling
        (§10). Returns the created transaction in WAITING_CUSTOMER."""
        prec = order.currency_id.decimal_places or 2
        eps = 1.0 / (10 ** prec)
        # single active request per order
        active = self.sudo().search([('pos_order_id', '=', order.id),
                                     ('state', 'in', list(ACTIVE_STATES))], limit=1)
        if active:
            raise UserError("A terminal request is already in progress for this order.")
        paid = round(sum(order.payment_ids.mapped('amount')), prec)
        remaining = round(order.amount_total - paid, prec)
        if remaining <= eps:
            raise UserError("This order is already fully paid.")
        req = round(float(amount), prec) if amount is not None else remaining
        if req <= 0:
            raise UserError("Terminal amount must be positive.")
        if req - remaining > eps:
            raise UserError("Terminal amount exceeds the remaining balance.")
        if req + eps < remaining and not method.mezze_allow_partial:
            raise UserError("Partial payment is not allowed for %r." % method.name)
        txn = self.sudo().create({
            'request_id': self._new_request_id(),
            'pos_order_id': order.id,
            'payment_method_id': method.id,
            'mezze_device_id': device.id if device else False,
            'provider': provider or (method.mezze_terminal_provider or ''),
            'amount': req,
            'currency_id': order.currency_id.id,
            'state': STATE_WAITING,
        })
        return txn

    @api.model
    def mezze_start_cashmachine(self, order, method, device, amount):
        """Open ONE cash-machine request (kind='cash_machine') with a server-
        authoritative amount. Reuses mezze_start's ceiling/single-in-flight guards;
        the browser can never inflate the machine amount (§8/§21)."""
        provider = method.mezze_terminal_provider or ''
        txn = self.mezze_start(order, method, device, amount, provider)
        txn.kind = 'cash_machine'
        return txn

    def _apply_cash_result(self, claimed_outcome=None):
        """SERVER-authoritative settlement of a live CASH-MACHINE request. Same trust
        model as the card path: the browser's claim is advisory; for the simulator the
        outcome is the stored scenario; a real device is refused (adapter PENDING).
        On approval books exactly ONE pos.payment == the NET amount (<= remaining) and
        records inserted/change for display only — inserted cash is never revenue."""
        self.ensure_one()
        if self.state == STATE_APPROVED:
            return self
        if self.state in (STATE_DECLINED, STATE_CANCELLED):
            return self
        if not self._is_test():
            # No native Glory adapter is wired to the standalone cashier yet (audit).
            # A browser claim can never mint a cash-machine payment.
            self.write({'state': STATE_ERROR, 'error_code': 'device_integration_pending'})
            raise UserError(
                "Cash machine %r is supported by Odoo (pos_glory_cash) but not yet "
                "wired to the Mezze standalone cashier. No payment was taken." % (self.provider or '?'))
        scenario = self.sim_scenario or 'success_exact'
        outcome = _CASH_SIM_OUTCOME.get(scenario, STATE_APPROVED)
        if claimed_outcome and claimed_outcome != outcome:
            self._log('cashmachine.outcome_mismatch',
                      {'claimed': claimed_outcome, 'authoritative': outcome, 'scenario': scenario})
        prec = self.currency_id.decimal_places or 2
        if outcome == STATE_APPROVED:
            # Change semantics: inserted >= amount; change = inserted - amount; the
            # PAYMENT is the amount (net). success_exact => inserted == amount, change 0.
            inserted = round(self.sim_inserted, prec) if (scenario == 'success_with_change'
                                                          and self.sim_inserted) else self.amount
            if inserted < self.amount:
                inserted = self.amount
            change = round(inserted - self.amount, prec)
            ref = self.provider_reference or ('CASH-' + self.request_id[-8:].upper())
            self.write({'provider_reference': ref, 'inserted_amount': inserted, 'change_amount': change})
            self._settle_payment(provenance='cash_machine')
            self.write({'state': STATE_APPROVED, 'uncertain': False})
        elif outcome == STATE_CANCELLED:
            # cancel AND connection_error land here: NO payment, order stays payable.
            self.write({'state': STATE_CANCELLED, 'uncertain': False,
                        'error_code': 'connection_error' if scenario == 'connection_error' else ''})
        elif outcome == STATE_UNKNOWN:
            self.write({'state': STATE_UNKNOWN, 'uncertain': True, 'error_code': 'unknown'})
        else:  # error (e.g. refund_error routed elsewhere)
            self.write({'state': STATE_ERROR, 'uncertain': True, 'error_code': 'cash_machine_error'})
        return self

    def mezze_apply_result(self, claimed_outcome=None):
        """SERVER-authoritative settlement of a live request. The browser's
        ``claimed_outcome`` is advisory ONLY: for the simulator the outcome comes
        from the stored scenario; a mismatch is audited, never obeyed. Real
        providers are not accepted here (integration PENDING) — no payment. On an
        authoritative approval, creates exactly ONE pos.payment (idempotent)."""
        self.ensure_one()
        if self.kind == 'cash_machine':
            return self._apply_cash_result(claimed_outcome)
        # idempotent: already settled
        if self.state == STATE_APPROVED:
            return self
        if self.state in (STATE_DECLINED, STATE_CANCELLED):
            return self
        if not self._is_test():
            # No native adapter is wired to the standalone cashier yet (see audit).
            # We must NOT accept a browser-asserted success for a real provider.
            self.write({'state': STATE_ERROR, 'error_code': 'provider_integration_pending'})
            raise UserError(
                "Integrated terminal for provider %r is supported by Odoo but not yet "
                "wired to the Mezze standalone cashier. No payment was taken." % (self.provider or '?'))
        outcome = _SIM_OUTCOME.get(self.sim_scenario or 'success', STATE_APPROVED)
        # audit any client/server outcome divergence (never trust the client)
        if claimed_outcome and claimed_outcome != outcome:
            self._log('terminal.outcome_mismatch',
                      {'claimed': claimed_outcome, 'authoritative': outcome})
        if outcome == STATE_APPROVED:
            ref = self.provider_reference or ('SIM-' + self.request_id[-8:].upper())
            self.write({'provider_reference': ref, 'card_type': self.card_type or 'SIMCARD'})
            self._settle_payment(provenance='integrated')
            self.write({'state': STATE_APPROVED, 'uncertain': False})
        elif outcome == STATE_DECLINED:
            self.write({'state': STATE_DECLINED, 'uncertain': False, 'error_code': 'declined'})
        elif outcome == STATE_CANCELLED:
            self.write({'state': STATE_CANCELLED, 'uncertain': False})
        elif outcome == STATE_TIMEOUT:
            self.write({'state': STATE_TIMEOUT, 'uncertain': True, 'error_code': 'timeout'})
        elif outcome == STATE_UNKNOWN:
            self.write({'state': STATE_UNKNOWN, 'uncertain': True, 'error_code': 'unknown'})
        else:  # error
            self.write({'state': STATE_ERROR, 'uncertain': True, 'error_code': 'terminal_error'})
        return self

    def mezze_cancel(self):
        """Cancel a live request (delegates to the native cancel path for a real
        adapter; here the simulator just settles CANCELLED). No payment. Not allowed
        once approved."""
        self.ensure_one()
        if self.state == STATE_APPROVED:
            raise UserError("An approved terminal payment cannot be cancelled here.")
        if self.state in (STATE_DECLINED, STATE_CANCELLED):
            return self
        self.write({'state': STATE_CANCELLED, 'uncertain': False})
        self._log('terminal.cancelled', {'request_id': self.request_id})
        return self

    def mezze_force_done(self, manager, reason):
        """Manager-gated MANUAL OVERRIDE for an uncertain/failed request (§22-25).
        Requires an eligible state, a manager principal (verified by the caller),
        and a reason. Creates exactly ONE payment with force-done provenance and a
        reconciliation flag; writes an immutable audit line. Cashiers can never
        reach this (the caller enforces role rank >= manager)."""
        self.ensure_one()
        if not manager:
            raise UserError("Manager authorization is required for Force Done.")
        if not (reason or '').strip():
            raise UserError("A reason is required for Force Done.")
        if self.state == STATE_APPROVED:
            return self  # idempotent — already settled
        if self.state not in UNCERTAIN_STATES:
            raise UserError("Force Done is only available after a terminal error or uncertain result.")
        self._settle_payment(provenance='manual_force_done', recon_flag=True)
        self.write({'state': STATE_APPROVED, 'uncertain': False, 'force_done': True,
                    'provider_reference': self.provider_reference or ('FORCE-' + self.request_id[-8:].upper())})
        self._log('terminal.force_done', {
            'request_id': self.request_id, 'amount': self.amount,
            'provider': self.provider, 'device': self.mezze_device_id.name or '',
            'approver_id': manager.id, 'approver': manager.name, 'role': manager.role,
            'reason': (reason or '')[:200]}, severity='warning')
        return self

    # ------------------------------------------------------------------ payment
    def _settle_payment(self, provenance='integrated', recon_flag=False):
        """Create THE one pos.payment for this transaction and converge on the
        existing money engine. Idempotent + concurrency-safe: a row lock serialises
        concurrent completions and the unique (order, tender_key=request_id) DB
        constraint is the durable backstop, so N approvals => ONE payment."""
        self.ensure_one()
        # serialise concurrent settlement of THIS transaction
        self.env.cr.execute("SELECT id FROM mezze_terminal_transaction WHERE id=%s FOR UPDATE", (self.id,))
        self.invalidate_recordset(['pos_payment_id', 'state'])
        if self.pos_payment_id:
            return self.pos_payment_id
        order = self.pos_order_id
        # durable idempotency: a prior settlement may have committed the payment
        existing = order.payment_ids.filtered(lambda p: p.mezze_tender_key == self.request_id)
        if existing:
            self.pos_payment_id = existing[:1].id
            return existing[:1]
        prec = order.currency_id.decimal_places or 2
        eps = 1.0 / (10 ** prec)
        remaining = self._order_remaining()
        amount = round(min(self.amount, remaining), prec)
        if amount <= 0:
            # nothing left to charge (already settled elsewhere) — stay idempotent
            return self.env['pos.payment']
        vals = {
            'amount': amount, 'payment_method_id': self.payment_method_id.id,
            'name': fields.Datetime.now(), 'pos_order_id': order.id,
            'mezze_tender_key': self.request_id,
            'mezze_confirmation_source': provenance,
            'mezze_recon_flag': recon_flag,
        }
        if self.provider_reference:
            vals['payment_ref_no'] = self.provider_reference
        if self.authcode:
            vals['payment_method_authcode'] = self.authcode
        if self.card_type:
            vals['card_type'] = self.card_type
        if self.mezze_device_id:
            vals['mezze_device_id'] = self.mezze_device_id.id
        order.add_payment(vals)
        payment = order.payment_ids.filtered(lambda p: p.mezze_tender_key == self.request_id)[:1]
        self.pos_payment_id = payment.id
        # finalise the sale once the balance is settled (reuses core lifecycle)
        if self._order_remaining() <= eps and order.state == 'draft':
            order.action_pos_order_paid()
        return payment

    # ------------------------------------------------------------------ audit
    def _log(self, event, detail, severity='info'):
        try:
            self.env['mezze.audit.log'].sudo().log(
                event, severity=severity, res_model='pos.order',
                res_id=self.pos_order_id.id, res_uuid=self.pos_order_id.uuid or False,
                detail=json.dumps(detail))
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ projection
    def mezze_payload(self):
        """PII-safe projection for the cashier (no secrets, masked reference)."""
        self.ensure_one()
        order = self.pos_order_id
        prec = order.currency_id.decimal_places or 2
        paid = round(sum(order.payment_ids.mapped('amount')), prec)
        ref = self.provider_reference or ''
        masked = ('••••' + ref[-4:]) if len(ref) > 4 else ref
        return {
            'request_id': self.request_id,
            'kind': self.kind,
            'state': self.state,
            'uncertain': self.uncertain,
            'amount': round(self.amount, prec),
            'inserted': round(self.inserted_amount, prec),
            'change': round(self.change_amount, prec),
            'provider': self.provider or '',
            'device': self.mezze_device_id.name or '',
            'reference_masked': masked,
            'error_code': self.error_code or '',
            'force_done': self.force_done,
            'paid': paid,
            'remaining': round(order.amount_total - paid, prec),
            'order_total': round(order.amount_total, prec),
            'order_state': order.state,
            'pos_reference': order.pos_reference or '',
            'has_payment': bool(self.pos_payment_id),
        }
