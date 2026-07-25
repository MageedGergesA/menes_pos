"""Refund ceiling invariant — the ONE canonical, server-side refundable check.

Pure and dependency-free (no Odoo, no I/O): deterministic, unit/property-testable,
importable by the controller. Money is compared in INTEGER MINOR UNITS only —
never binary floating-point — so a client cannot exploit decimal precision.

Canonical invariant (RFC-001 money rules; RFC-000 never-trust-client):

    refundable_minor = paid_minor - already_refunded_minor
    valid  iff  0 < requested_minor <= refundable_minor

`paid_minor` and `already_refunded_minor` come from authoritative Odoo values
(orig.amount_paid and the summed amount_total of the original's successful refund
orders); the client never supplies the refundable amount. `to_minor` applies the
currency's decimal precision so partial refunds sum exactly and rounding cannot
create or destroy more than the currency's minor unit.
"""

from collections import namedtuple

Verdict = namedtuple("Verdict", ["ok", "reason", "refundable_minor"])

# Error/reason codes (stable, machine-readable).
OK = "ok"
NON_POSITIVE = "refund_non_positive"
EXCEEDS = "refund_exceeds_refundable"
# linkage / per-line quantity codes
ORIGINAL_REQUIRED = "refund_original_required"
LINE_MISSING = "refund_line_missing"
LINE_NOT_IN_ORIGINAL = "refund_line_not_in_original"
PRODUCT_MISMATCH = "refund_line_product_mismatch"
QTY_INVALID = "refund_quantity_invalid"
QTY_EXCEEDS_REMAINING = "refund_quantity_exceeds_remaining"
LINKAGE_AMBIGUOUS = "refund_linkage_ambiguous"
COMPANY_MISMATCH = "refund_company_mismatch"
CURRENCY_MISMATCH = "refund_currency_mismatch"

QVerdict = namedtuple("QVerdict", ["ok", "reason", "remaining_units"])


def qty_to_units(qty, digits):
    """Convert a quantity to integer units at the product-UoM precision, so
    per-line quantity eligibility never uses binary-float equality."""
    try:
        q = 10 ** int(digits)
        return int(round(float(qty) * q))
    except (TypeError, ValueError):
        raise ValueError("malformed quantity: %r" % (qty,))


def check_line_quantity(requested_units, sold_units, already_refunded_units):
    """Per-line quantity ceiling in integer units.

        remaining = sold - already_refunded
        ok iff 0 < requested <= remaining

    Non-positive requested -> QTY_INVALID. Over remaining (incl. by one unit) ->
    QTY_EXCEEDS_REMAINING. Reserved/pending quantity is accounted for by the
    caller aggregating committed refunds under the per-original advisory lock.
    """
    remaining = int(sold_units) - int(already_refunded_units)
    if not isinstance(requested_units, int) or requested_units <= 0:
        return QVerdict(False, QTY_INVALID, remaining)
    if requested_units > remaining:
        return QVerdict(False, QTY_EXCEEDS_REMAINING, remaining)
    return QVerdict(True, OK, remaining)


def to_minor(amount, decimal_places):
    """Convert a currency amount to integer minor units at the currency's
    precision. Rounds half-to-even via round(); fails closed on bad input."""
    try:
        q = 10 ** int(decimal_places)
        return int(round(float(amount) * q))
    except (TypeError, ValueError):
        raise ValueError("malformed monetary amount: %r" % (amount,))


def check_refund(requested_minor, paid_minor, already_refunded_minor):
    """Return Verdict(ok, reason, refundable_minor). All args in minor units.

    * requested_minor must be a positive integer (fails closed otherwise).
    * refundable = paid - already_refunded (may be <= 0 if fully/over refunded).
    * ok iff 0 < requested <= refundable.

    Negative/zero requested -> NON_POSITIVE (cannot increase capacity).
    requested > refundable  -> EXCEEDS (over-refund blocked, incl. by one minor
    unit). A negative refundable (historical over-refund) rejects every positive
    request, which is the safe, capacity-preserving behaviour.
    """
    refundable = int(paid_minor) - int(already_refunded_minor)
    if not isinstance(requested_minor, int) or requested_minor <= 0:
        return Verdict(False, NON_POSITIVE, refundable)
    if requested_minor > refundable:
        return Verdict(False, EXCEEDS, refundable)
    return Verdict(True, OK, refundable)
