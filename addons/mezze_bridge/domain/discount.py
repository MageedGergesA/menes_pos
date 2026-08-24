# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Who may take money off a bill, and how much.

Until now Mezze had no answer to that question. ``pos.order.line.discount`` is a
core Odoo field and ``_build_lines`` has always applied whatever percentage the
client sent — but no surface ever sent one, no ceiling existed, and no audit event
was written. The capability ``orders.discount`` existed and was held only by
supervisor and above, which meant the only *reachable* discount in the product was
a 100% comp.

That is the wrong shape for a restaurant. A cashier settling a complaint needs to
take 10% off without walking a manager across the floor; a manager needs to take
50% off without asking anyone. So authority here is TIERED, not boolean:

    capability  ->  MAY this principal discount at all?
    ceiling     ->  how far, before a manager has to stand behind it?

Both are enforced server-side. The ceiling is not a UI hint: a client that posts
40% with a cashier token is refused with ``approval_required`` and the attempt is
audited, exactly as if it had tried to comp without a PIN.

Percentages, not amounts
------------------------
Discounts are expressed as a percentage because that is what the native field
stores. An amount-off is therefore derived (``pct = amount / subtotal * 100``) by
the caller, not represented separately — one representation means one place where
tax stays correct, and ``compute_all`` keeps working untouched.

This module is deliberately pure: no ORM, no request, no config read. The caller
supplies the ceilings it looked up. That is what makes the table below testable
without a database, and it is the same split used by ``domain/refund.py`` and
``domain/order_fsm.py``.
"""

# Verdicts. The caller maps these onto HTTP; nothing here knows about HTTP.
ALLOWED = 'allowed'                    # within this role's own ceiling
NEEDS_APPROVAL = 'needs_approval'      # over it — a manager may still authorise
REFUSED = 'refused'                    # this role does not discount at all
INVALID = 'invalid'                    # not a usable percentage

# ir.config_parameter keys, per role. A role absent from this map is unlimited
# (manager/admin) or has no discount right at all (waiter/kitchen/host) — the
# capability check decides which, not this module.
CEILING_PARAMS = {
    'cashier': 'mezze_bridge.discount_ceiling_cashier',
    'supervisor': 'mezze_bridge.discount_ceiling_supervisor',
}

# Conservative defaults. A branch that wants a looser till sets its own; a branch
# that never configured anything still gets a bounded cashier rather than an
# unbounded one, because the failure mode of a too-low ceiling is one manager PIN
# and the failure mode of a too-high one is unpriced shrinkage.
CEILING_DEFAULTS = {
    'cashier': 10.0,
    'supervisor': 25.0,
}

# A bare terminal token is the device standing on the counter with nobody
# identified behind it. It is not MORE trusted than the least-privileged human who
# uses it, so it inherits the cashier ceiling rather than getting its own.
CEILING_ALIASES = {
    'terminal': 'cashier',
}

# Roles that may exceed any ceiling by their own authority — and therefore also the
# only roles whose PIN can authorise somebody else's over-ceiling discount.
UNLIMITED_ROLES = frozenset({'manager', 'admin', 'administrator'})

# Minimum role rank that can approve an over-ceiling discount. Mirrors the rank
# model already used by comp and by duplicate-reference approval in /orders/pay
# (cashier 0, supervisor 1, manager 2) — a supervisor can authorise a cashier's
# over-ceiling discount, and nobody can authorise their own.
APPROVER_MIN_RANK = 1


def ceiling_for(role, get_param=None):
    """The maximum percentage ``role`` may apply unaided.

    Returns ``None`` for "no ceiling". ``get_param`` is any callable taking
    ``(key, default)`` — in production that is ``ir.config_parameter.get_param``;
    in tests it is a dict lookup. Omit it to get the shipped defaults.

    A misconfigured parameter (blank, non-numeric, negative) falls back to the
    default rather than to "unlimited": a typo in a config value must never widen
    authority.
    """
    if role in UNLIMITED_ROLES:
        return None
    resolved = CEILING_ALIASES.get(role, role)
    if resolved not in CEILING_PARAMS:
        # Not a discounting role. The capability gate is the real refusal; a zero
        # ceiling here just means "nothing is within your authority" if it ever is.
        return 0.0
    default = CEILING_DEFAULTS[resolved]
    if get_param is None:
        return default
    raw = get_param(CEILING_PARAMS[resolved], default)
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return default
    if value < 0.0:
        return default
    return min(value, 100.0)


def evaluate(role, percent, ceiling=None, has_capability=True):
    """Decide what happens to a discount request. Pure.

    ``ceiling`` is what ``ceiling_for`` returned (``None`` = unlimited). Pass
    ``has_capability=False`` when the principal does not hold ``orders.discount``
    at all, so a role that cannot discount is refused rather than being offered an
    approval path it could never complete.

    Returns ``(verdict, detail)`` where detail carries the numbers a caller needs
    for its error envelope and its audit row.
    """
    try:
        pct = float(percent)
    except (TypeError, ValueError):
        return INVALID, {'reason': 'not_a_number', 'percent': percent}
    if pct != pct or pct in (float('inf'), float('-inf')):  # NaN / inf
        return INVALID, {'reason': 'not_finite', 'percent': percent}
    # 0 is not a discount, it is a removal — callers that want to clear a discount
    # say so explicitly rather than sending 0 and hoping.
    if pct <= 0.0 or pct > 100.0:
        return INVALID, {'reason': 'out_of_range', 'percent': pct}
    if not has_capability:
        return REFUSED, {'percent': pct, 'ceiling': ceiling}
    if ceiling is None:
        return ALLOWED, {'percent': pct, 'ceiling': None}
    if pct <= float(ceiling):
        return ALLOWED, {'percent': pct, 'ceiling': float(ceiling)}
    return NEEDS_APPROVAL, {'percent': pct, 'ceiling': float(ceiling)}


def can_approve(role):
    """True iff ``role`` may authorise somebody else's over-ceiling discount."""
    return rank_of(role) >= APPROVER_MIN_RANK


def rank_of(role):
    """The approval rank of a role. Unknown roles rank lowest, never highest."""
    return {'cashier': 0, 'supervisor': 1, 'manager': 2,
            'admin': 2, 'administrator': 2}.get(role, 0)
