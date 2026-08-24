# -*- coding: utf-8 -*-
"""Turning a card terminal's answer into a state Mezze can bank — no I/O here.

Mezze's terminal spine is finished and has never had a provider behind it. That was
the right call: the model refuses to accept a browser's claim of success for a real
provider, so the alternative to "no adapter" was fake approvals, which is worse than
nothing. But it left a registry containing one entry, a simulator, and a row on the
parity report reading "no real terminal".

This is the seam. It maps ONE provider's vocabulary onto the normalized states the
rest of the product already speaks, and it decides which answers are final and which
are merely the last thing we heard.

The distinction that matters is not approved/declined — every integration gets that
right. It is **uncertain**: the request left, the customer may have tapped, and the
answer never came back. Mezze already models that (``uncertain``, force-done with its
own provenance), and an adapter's real job is to make it rare — by asking the
provider what happened rather than asking a cashier to guess. Everything below is
shaped around being able to ask again safely:

* the idempotency key is the transaction's own durable ``request_id``, so re-sending
  a request that may already have been received cannot take a second payment;
* a transport failure is never a decline. "I did not hear back" and "the card was
  refused" look identical from a socket and are opposite facts about a guest's money;
* only the PROVIDER may settle. A timeout resolves by querying, and if the query
  also fails the transaction stays uncertain — which is honest, and is what the
  manager override exists for.
"""

#: Normalized states, mirrored from ``models.mezze_terminal_txn`` so this module
#: stays importable without Odoo. Kept as plain strings deliberately: a second
#: enumeration that drifts from the first would be worse than a duplicated literal.
APPROVED = 'approved'
DECLINED = 'declined'
CANCELLED = 'cancelled'
PROCESSING = 'processing'
WAITING = 'waiting_customer'
TIMEOUT = 'timeout'
UNKNOWN = 'unknown'
ERROR = 'error'

#: Outcomes that mean "a charge may exist and we do not know". Never auto-retried.
UNCERTAIN = frozenset({TIMEOUT, UNKNOWN, ERROR})


class AdapterError(Exception):
    """A provider answered, and the answer was not a payment."""

    def __init__(self, state, code='', detail=''):
        self.state = state
        self.code = code or ''
        self.detail = detail or ''
        super().__init__('%s:%s' % (state, self.code) if self.code else state)


# ---------------------------------------------------------------------------
# Stripe Terminal
# ---------------------------------------------------------------------------
#
# Chosen first for a reason that is about verification rather than market share:
# Stripe Terminal has a SIMULATED reader in test mode. A shop can prove this whole
# path end to end with a free test key and no hardware and no certification, which
# makes the remaining gate "get a test key" rather than "enter a certification
# programme". The other vendors on the parity row cannot be reached that way.
#
# The flow is three calls and a poll:
#   1. create a PaymentIntent for the amount (capture_method=automatic)
#   2. POST it to the reader — /v1/terminal/readers/{id}/process_payment_intent
#   3. poll the reader until action.status leaves 'in_progress'
# and the PaymentIntent's own status is the money truth at the end of it.

STRIPE = 'stripe_terminal'
STRIPE_API = 'https://api.stripe.com'

#: PaymentIntent status -> what it means for a bill.
#
# ``requires_payment_method`` is deliberately absent: it is BOTH the status of a
# brand-new intent nobody has presented a card to, and the status of one whose card
# was refused. Mapping it to "declined" would report a decline for an attempt that
# never happened — which matters because the reconcile path can legitimately create
# an intent it has never used. What separates them is ``last_payment_error``, so
# that is where the decision is made instead of in this table.
_INTENT_STATE = {
    'succeeded': APPROVED,
    'requires_capture': APPROVED,      # authorised; captured separately
    'processing': PROCESSING,
    'requires_confirmation': WAITING,
    'requires_action': WAITING,
    'canceled': CANCELLED,
}

#: Reader action status -> the cashier-facing state while it is still live.
_ACTION_STATE = {
    'in_progress': PROCESSING,
    'succeeded': APPROVED,
    'failed': DECLINED,
}

#: Stripe error codes that are the CARD's answer rather than ours. Anything not
#: listed is treated as uncertain, because a code nobody has seen before must not
#: quietly become "declined" — that is the direction that loses a real payment.
_DECLINE_CODES = frozenset({
    'card_declined', 'expired_card', 'incorrect_cvc', 'insufficient_funds',
    'card_not_supported', 'currency_not_supported', 'invalid_pin',
    'pin_try_exceeded', 'withdrawal_count_limit_exceeded', 'offline_pin_required',
})

#: Codes that mean the request never took effect. Safe to treat as cancelled: no
#: charge exists, so the order stays payable and the cashier simply tries again.
_HARMLESS_CODES = frozenset({
    'terminal_reader_timeout',       # the reader was not reachable at all
    'terminal_reader_offline',
    'canceled',
    'payment_intent_action_canceled',
})


def minor_units(amount, decimal_places=2):
    """Money as an integer, because a card network does not take floats.

    Rounded once, here, so the amount asked of the terminal and the amount written
    to the bill are the same rounding — a half-cent difference between the two is a
    reconciliation nobody can close.
    """
    return int(round(float(amount) * (10 ** int(decimal_places))))


def intent_payload(amount, currency, request_id, decimal_places=2, description=None):
    """The PaymentIntent to create for one terminal request."""
    body = {
        'amount': minor_units(amount, decimal_places),
        'currency': (currency or '').lower(),
        'payment_method_types[]': 'card_present',
        'capture_method': 'automatic',
        # Mezze's own durable id travels with the charge, so a statement line or a
        # Stripe dashboard row can be matched back to a bill without guesswork.
        'metadata[mezze_request_id]': request_id,
    }
    if description:
        body['description'] = description[:200]
    return body


def classify_error(code, http_status=None):
    """What a failure MEANS for the guest's money.

    Defaulting to uncertain is deliberate and is the whole point of the function.
    An unrecognised failure treated as a decline tells a cashier to charge the card
    again, and if the first one did go through the guest has now paid twice — so an
    unknown answer stays unknown and goes to the manager path with its own audit
    trail, which is a slower and correct outcome instead of a fast and wrong one.
    """
    code = (code or '').strip()
    if code in _DECLINE_CODES:
        return DECLINED
    if code in _HARMLESS_CODES:
        return CANCELLED
    if http_status is not None and 400 <= int(http_status) < 500 and code in (
            'resource_missing', 'parameter_invalid_integer', 'parameter_missing'):
        # Our request was malformed. Nothing was charged and retrying it unchanged
        # will fail the same way, so it is an error rather than an uncertainty.
        return ERROR
    return UNKNOWN


def state_from_intent(intent):
    """The money truth: what the PaymentIntent says happened."""
    if not isinstance(intent, dict):
        return UNKNOWN
    status = (intent.get('status') or '').strip()
    if status in _INTENT_STATE:
        return _INTENT_STATE[status]
    last = intent.get('last_payment_error') or {}
    if status == 'requires_payment_method':
        # A card was presented and refused, or nothing has been presented at all.
        return (classify_error(last.get('decline_code') or last.get('code'))
                if last else WAITING)
    if last:
        return classify_error(last.get('decline_code') or last.get('code'))
    return UNKNOWN


def state_from_reader(reader):
    """What the reader is doing right now, while the customer is still holding it."""
    if not isinstance(reader, dict):
        return UNKNOWN
    action = reader.get('action') or {}
    status = (action.get('status') or '').strip()
    if status == 'failed':
        failure = action.get('failure_code') or ''
        return classify_error(failure)
    return _ACTION_STATE.get(status, PROCESSING if action else WAITING)


def reference_of(intent):
    """A reference safe to print and to reconcile against — never a card number."""
    if not isinstance(intent, dict):
        return ''
    return intent.get('id') or ''


def card_of(intent):
    """The card brand, for the receipt line. Nothing identifying, by design: a
    receipt that carries more than a brand and last-four is a receipt that becomes
    somebody's problem when it is dropped in a car park."""
    try:
        charge = (intent.get('charges') or {}).get('data') or []
        details = (charge[0].get('payment_method_details') or {}) if charge else {}
        present = details.get('card_present') or {}
        brand = (present.get('brand') or '').upper()
        last4 = present.get('last4') or ''
        return ('%s %s' % (brand, last4)).strip()
    except Exception:  # noqa: BLE001 — a receipt label is never worth an exception
        return ''


#: Providers with a real adapter. A provider absent from here is refused rather
#: than faked — which is the behaviour the terminal model already had, and the
#: reason it was safe to ship with no adapters at all.
ADAPTERS = frozenset({STRIPE})


def supported(provider):
    return (provider or '') in ADAPTERS
