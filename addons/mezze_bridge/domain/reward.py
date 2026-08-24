# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""What a loyalty reward is worth, in money.

Mezze used to answer this question in the browser. ``/loyalty/redeem`` debited the
card and returned a number; the till then posted that number to ``/orders/pay``,
which grafted ``price_unit = -discount`` onto the order with **no check that a
reward existed, that the card had been debited, or that redeem had ever been
called.** Because ``/orders/pay`` needs only ORDERS_PAY — which a cashier and a bare
terminal both hold — while redeeming needs LOYALTY_ADJUST, the money route was a way
around the gate that was supposed to bound it.

The fix is not a tighter check on the number. It is to stop sending a number at all:
the till names a *reward*, and the server prices it. This module is that pricing, and
it is deliberately pure so the arithmetic can be tested without a database.

It mirrors Odoo's own vocabulary rather than inventing one, because the rewards being
priced are real ``loyalty.reward`` records:

    reward_type            'discount' | 'product'
    discount_mode          'percent' | 'per_order' | 'per_point'
    discount_applicability 'order' | 'cheapest' | 'specific'
    discount_max_amount    cap, 0 meaning no cap

Two invariants hold for every path through it:

* a reward can never make a bill negative — it is capped at what is owed;
* a reward is never worth more than its own ``discount_max_amount``.
"""

PERCENT = 'percent'
PER_ORDER = 'per_order'
PER_POINT = 'per_point'

ORDER = 'order'
CHEAPEST = 'cheapest'
SPECIFIC = 'specific'

# Refusal reasons. The caller turns these into an error envelope; the point of
# naming them is that a till can say WHY a reward is greyed out instead of just
# hiding it, which is how a cashier ends up telling a guest "the system won't let me".
NO_CARD = 'no_card'
NOT_ENOUGH_POINTS = 'not_enough_points'
NOTHING_TO_DISCOUNT = 'nothing_to_discount'
ALREADY_APPLIED = 'already_applied'
NO_ELIGIBLE_PRODUCT = 'no_eligible_product'


def discount_base(applicability, order_total, cheapest_unit_price=0.0,
                  specific_total=0.0):
    """The money a percentage reward applies to.

    ``order_total`` must already EXCLUDE existing reward lines — discounting a
    discount is how a stacked reward quietly doubles itself.
    """
    if applicability == CHEAPEST:
        return max(0.0, float(cheapest_unit_price or 0.0))
    if applicability == SPECIFIC:
        return max(0.0, float(specific_total or 0.0))
    return max(0.0, float(order_total or 0.0))


def discount_amount(mode, value, base, points_spent=0.0, max_amount=0.0,
                    remaining=None):
    """The positive money value of a discount reward.

    ``remaining`` is what the order still owes; the reward is clamped to it so a
    generous reward on a small bill cannot produce a negative total. Pass ``None``
    to skip that clamp (the caller then owns it).
    """
    try:
        value = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    base = max(0.0, float(base or 0.0))

    if mode == PERCENT:
        amount = base * value / 100.0
    elif mode == PER_POINT:
        amount = value * max(0.0, float(points_spent or 0.0))
    elif mode == PER_ORDER:
        amount = value
    else:
        # An unknown mode is worth nothing. Guessing here is how `per_point`
        # silently became zero in the old promotion engine — except that one
        # returned 0.0 while still claiming the mode was supported.
        return 0.0

    amount = max(0.0, amount)
    cap = float(max_amount or 0.0)
    if cap > 0.0:
        amount = min(amount, cap)
    if remaining is not None:
        amount = min(amount, max(0.0, float(remaining)))
    return amount


def points_after(balance, cost, clear_wallet=False):
    """The card balance once this reward is taken.

    ``clear_wallet`` rewards spend the whole balance rather than a fixed cost —
    that is what an eWallet payout is, and treating it as a fixed cost is how a
    wallet ends up with a stranded remainder nobody can spend.
    """
    balance = float(balance or 0.0)
    if clear_wallet:
        return 0.0
    return balance - float(cost or 0.0)


def spend_for(reward_cost, balance, clear_wallet=False):
    """How many points this redemption actually consumes."""
    if clear_wallet:
        return max(0.0, float(balance or 0.0))
    return float(reward_cost or 0.0)


def claimable(reward_cost, balance, remaining, reward_type='discount',
              has_card=True, already=False, eligible_products=True):
    """``(ok, reason)`` — may this reward be taken right now?

    Returns a reason on refusal rather than a bare False, so the till can explain
    itself. Checked server-side on apply as well; this shared helper is what keeps
    the list a guest is shown and the decision the server makes from drifting apart.
    """
    if not has_card:
        return False, NO_CARD
    if already:
        return False, ALREADY_APPLIED
    if float(balance or 0.0) + 1e-9 < float(reward_cost or 0.0):
        return False, NOT_ENOUGH_POINTS
    if reward_type == 'product':
        if not eligible_products:
            return False, NO_ELIGIBLE_PRODUCT
        return True, None
    if float(remaining or 0.0) <= 0.0:
        return False, NOTHING_TO_DISCOUNT
    return True, None
