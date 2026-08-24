# -*- coding: utf-8 -*-
"""The first real terminal adapter: Stripe Terminal.

``mezze.terminal.transaction`` has been a finished, server-authoritative spine with
nothing behind it — by design, because the honest alternative to "no adapter" was
accepting a browser's word that a card had been approved. This gives it one provider.

Stripe is first for a reason about VERIFICATION rather than market share: its
Terminal product has a simulated reader in test mode, so the entire path can be
proven with a free test key, no hardware and no certification programme. That makes
the remaining gate on this row "get a test key" instead of "enter certification",
which is a different kind of blocked.

The design rule, stated once: **only the provider settles.** A transport failure is
not a decline — "I did not hear back" and "the card was refused" are indistinguishable
from a socket and are opposite facts about a guest's money. So an attempt that ends
without an answer stays uncertain and is RESOLVED BY ASKING, using the transaction's
own durable ``request_id`` as the idempotency key, which is what makes asking again
safe. Only when the provider itself cannot be reached does it fall through to the
manager override that already exists.
"""
import logging

import requests

from odoo import models

from ..domain import terminal_adapters as ta

_logger = logging.getLogger(__name__)

#: How long any single provider call may take. Short on purpose: a cashier is
#: standing at a terminal, and a request that hangs for a minute produces exactly
#: the uncertain state this adapter exists to avoid.
_TIMEOUT = 12
#: How long to keep asking the reader what it is doing before giving up on the poll.
#: Giving up does NOT decide anything — it hands over to the reconcile path.
_POLL_SECONDS = 90
_POLL_INTERVAL = 2


class MezzeTerminalTransactionStripe(models.Model):
    _inherit = 'mezze.terminal.transaction'

    # ------------------------------------------------------------------ wire
    def _stripe_call(self, path, body=None, idempotency_key=None, method='POST'):
        """One call to Stripe. Transport failures stay ``OSError``.

        ``requests`` exceptions are ``OSError`` subclasses, so an unreachable
        provider classifies the same way an unreachable printer does, and the
        caller can tell "we never got an answer" apart from "the answer was no".
        """
        device = self.mezze_device_id
        key = device._provider_secret() if device else None
        if not key:
            raise ta.AdapterError(ta.ERROR, 'no_credentials')
        headers = {'Authorization': 'Bearer %s' % key,
                   'Stripe-Version': '2024-06-20'}
        if idempotency_key:
            # THE safety property. Re-sending a request that may already have been
            # received returns the FIRST result rather than taking a second payment.
            headers['Idempotency-Key'] = idempotency_key
        url = '%s%s' % (ta.STRIPE_API, path)
        if method == 'GET':
            resp = requests.get(url, headers=headers, timeout=_TIMEOUT)
        else:
            resp = requests.post(url, data=body or {}, headers=headers,
                                 timeout=_TIMEOUT)
        try:
            payload = resp.json()
        except ValueError:
            raise ta.AdapterError(ta.UNKNOWN, 'unparseable_response')
        if resp.status_code >= 400:
            err = payload.get('error') or {}
            code = err.get('decline_code') or err.get('code') or ''
            raise ta.AdapterError(
                ta.classify_error(code, resp.status_code), code,
                (err.get('message') or '')[:160])
        return payload

    # ------------------------------------------------------------------ flow
    def _stripe_intent(self):
        """Create (or re-fetch) the PaymentIntent for this attempt.

        Idempotent on ``request_id``: called twice — by a retry, or by the
        reconcile path after a timeout — it returns the same intent rather than a
        second one, which is the difference between asking again and charging
        again.
        """
        self.ensure_one()
        if self.provider_reference:
            return self._stripe_call(
                '/v1/payment_intents/%s' % self.provider_reference, method='GET')
        order = self.pos_order_id
        body = ta.intent_payload(
            self.amount, (self.currency_id.name or order.currency_id.name or ''),
            self.request_id,
            decimal_places=(self.currency_id.decimal_places or 2),
            description=order.pos_reference or order.name)
        intent = self._stripe_call('/v1/payment_intents', body,
                                   idempotency_key=self.request_id)
        ref = ta.reference_of(intent)
        if ref:
            # Written before the reader is asked to do anything, so the ordinary
            # reconcile path has something to look up. It is deliberately NOT
            # committed early: committing here would commit everything else in the
            # request too, and a half-written order is a worse failure than a
            # reference that has to be recovered. Recovery is covered by the
            # idempotency key — see ``mezze_stripe_reconcile``.
            self.sudo().write({'provider_reference': ref})
        return intent

    def _stripe_process(self, intent_id):
        return self._stripe_call(
            '/v1/terminal/readers/%s/process_payment_intent'
            % (self.mezze_device_id.provider_reader_id or ''),
            {'payment_intent': intent_id},
            idempotency_key='%s-proc' % self.request_id)

    def _stripe_poll(self, deadline_fn):
        """Watch the reader until it stops working, or we stop waiting.

        Giving up decides NOTHING. It leaves the attempt uncertain and lets the
        reconcile path ask the PaymentIntent what actually happened, because the
        reader is only where the customer is standing — the intent is where the
        money is.
        """
        reader_id = self.mezze_device_id.provider_reader_id or ''
        while not deadline_fn():
            reader = self._stripe_call('/v1/terminal/readers/%s' % reader_id,
                                       method='GET')
            state = ta.state_from_reader(reader)
            if state != ta.PROCESSING:
                return state
        return ta.TIMEOUT

    # -------------------------------------------------------------- settling
    def _stripe_settle(self, state, intent=None, code=''):
        """Apply an outcome the PROVIDER produced. Never called on a guess."""
        self.ensure_one()
        if state == ta.APPROVED:
            vals = {}
            if intent:
                vals['provider_reference'] = ta.reference_of(intent) or self.provider_reference
                card = ta.card_of(intent)
                if card:
                    vals['card_type'] = card
            if vals:
                self.write(vals)
            self._settle_payment(provenance='integrated')
            self.write({'state': 'approved', 'uncertain': False, 'error_code': ''})
        elif state == ta.DECLINED:
            self.write({'state': 'declined', 'uncertain': False,
                        'error_code': code or 'declined'})
        elif state == ta.CANCELLED:
            self.write({'state': 'cancelled', 'uncertain': False,
                        'error_code': code or ''})
        else:
            # Uncertain. A charge may exist; the order stays payable, nothing is
            # auto-retried, and the manager override keeps its own provenance.
            self.write({'state': state if state in ('timeout', 'unknown') else 'error',
                        'uncertain': True, 'error_code': code or state})
        return self

    def mezze_stripe_run(self, deadline_fn=None):
        """Take one card payment on a real reader.

        Returns self. Raises nothing a caller has to catch: every failure ends as a
        state on this record, because a terminal attempt that raises its way out of
        the transaction is one whose outcome is not written down anywhere.
        """
        self.ensure_one()
        if self.state == 'approved':
            return self
        deadline_fn = deadline_fn or (lambda: False)
        try:
            intent = self._stripe_intent()
            state = ta.state_from_intent(intent)
            if state == ta.APPROVED:
                # Already paid — a retry after an answer we never saw.
                return self._stripe_settle(ta.APPROVED, intent)
            self.write({'state': 'waiting_customer'})
            self._stripe_process(intent['id'])
            self.write({'state': 'processing'})
            outcome = self._stripe_poll(deadline_fn)
            if outcome in ta.UNCERTAIN:
                # Do not report a timeout without asking the money what happened.
                return self.mezze_stripe_reconcile()
            final = self._stripe_call('/v1/payment_intents/%s' % intent['id'],
                                      method='GET')
            return self._stripe_settle(ta.state_from_intent(final), final)
        except ta.AdapterError as exc:
            if exc.state in ta.UNCERTAIN:
                return self.mezze_stripe_reconcile(fallback=exc)
            return self._stripe_settle(exc.state, code=exc.code)
        except OSError as exc:
            # We never heard back. That is not a decline.
            _logger.warning("Mezze terminal %s: transport failure: %s",
                            self.request_id, exc)
            return self.mezze_stripe_reconcile(fallback=exc)

    def mezze_stripe_reconcile(self, fallback=None):
        """Ask the provider what happened, instead of asking a cashier.

        This is the method the whole adapter is shaped around. An uncertain terminal
        payment is the expensive failure in a restaurant: the guest may have been
        charged, the bill says unpaid, and the only tools without this are charging
        again or waving them through. Asking is cheap, safe (the reference was
        written before anything was sent) and almost always decisive.

        If the provider cannot be reached EITHER, the attempt stays uncertain —
        which is the honest answer and exactly what the manager override is for.
        """
        self.ensure_one()
        ref = self.provider_reference
        try:
            if ref:
                intent = self._stripe_call('/v1/payment_intents/%s' % ref,
                                           method='GET')
            else:
                # No reference — the process may have died between creating the
                # intent and writing it down. Re-issuing the CREATE under the same
                # idempotency key is how that is recovered: Stripe returns the
                # original intent if it ever arrived, and a fresh unused one if it
                # did not. Either way the answer is authoritative, and either way
                # only one intent has ever existed for this attempt.
                order = self.pos_order_id
                intent = self._stripe_call(
                    '/v1/payment_intents',
                    ta.intent_payload(
                        self.amount,
                        (self.currency_id.name or order.currency_id.name or ''),
                        self.request_id,
                        decimal_places=(self.currency_id.decimal_places or 2),
                        description=order.pos_reference or order.name),
                    idempotency_key=self.request_id)
                new_ref = ta.reference_of(intent)
                if new_ref:
                    self.sudo().write({'provider_reference': new_ref})
        except (ta.AdapterError, OSError) as exc:
            _logger.warning("Mezze terminal %s: could not reconcile: %s",
                            self.request_id, exc)
            return self._stripe_settle(ta.UNKNOWN, code='reconcile_failed')
        state = ta.state_from_intent(intent)
        if state == ta.WAITING and not (intent.get('last_payment_error') or {}):
            # Created and never presented to a card. Nothing was charged, so the
            # order stays payable and the cashier simply tries again — this is not
            # an uncertainty and must not reach the manager override.
            return self._stripe_settle(ta.CANCELLED, code='not_started')
        if state in (ta.PROCESSING, ta.WAITING):
            # Still live at the provider. Not settled, not lost — and specifically
            # not force-done eligible yet, or a manager would be overriding a
            # payment that is about to succeed on its own.
            self.write({'state': 'processing', 'uncertain': False})
            return self
        code = ''
        if state == ta.DECLINED:
            last = intent.get('last_payment_error') or {}
            code = last.get('decline_code') or last.get('code') or 'declined'
        elif fallback is not None and state in (ta.UNKNOWN, ta.ERROR):
            code = getattr(fallback, 'code', '') or 'unknown'
        return self._stripe_settle(state, intent, code=code)
