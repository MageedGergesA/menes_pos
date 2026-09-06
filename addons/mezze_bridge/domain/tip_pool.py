"""Tip pooling — the ONE distribution resolver (design BE-008).

A tip is money owed to staff: a liability from the moment it is captured, and
never the branch's to keep, spend or round. The design contract
(``docs/TIP_POOLING.md``) states the shape this must have, and the reason it is
one function rather than arithmetic inlined per screen: four numbers for one
liability is how a pool ends up short and nobody can say whose money it was.

Pure and dependency-free (no Odoo import), like ``order_guard``: deterministic
and unit-testable. It computes shares only — it does not decide eligibility,
read a clock, or post anything. The caller supplies who was on shift.

MONEY IS IN MINOR UNITS (piastres) throughout. Shares are integers, and the
remainder is ALLOCATED by largest-remainder rather than rounded per share, so
``sum(shares) == pool`` exactly. Rounding each share independently is the defect
this exists to prevent.
"""

from collections import namedtuple

# Rule ids — recorded on the run, so a signed distribution can be re-read next
# month and still explain itself.
EQUAL = 'equal'
HOURS = 'hours'
ROLE = 'role'
CUSTOM = 'custom'
DIRECT = 'direct'
HYBRID = 'hybrid'
RULES = (EQUAL, HOURS, ROLE, CUSTOM, DIRECT, HYBRID)

# Role weights for the role-weighted and hybrid support splits.
ROLE_WEIGHTS = {'server': 1.0, 'bar': 0.8, 'kitchen': 0.5, 'rider': 0.5}
DEFAULT_ROLE_WEIGHT = 1.0

# Share of a server's own captures that funds the support pool under Hybrid.
TIP_OUT_PCT = 15.0

# Error codes — returned, never raised: a rule that cannot be applied is a
# refusal to sign, not a crash.
ERR_NO_ONE = 'no_eligible_staff'
ERR_CUSTOM_TOTAL = 'custom_pct_not_100'
ERR_UNKNOWN_RULE = 'unknown_rule'
ERR_NO_WEIGHT = 'no_weight_to_split_by'

#: key       — opaque person id (the caller's cashier id)
#: role      — lowercase role name; unknown roles take DEFAULT_ROLE_WEIGHT
#: minutes   — minutes ACTUALLY worked, breaks excluded
#: captured  — piastres captured on this person's own checks (card, with tender)
#: declared  — piastres of cash tips this person declared
Person = namedtuple('Person', 'key role minutes captured declared')

#: key, weight (the rule's weight for this person), share (piastres)
Row = namedtuple('Row', 'key weight share')

#: rule   — the rule applied
#: pool   — the liability being distributed (piastres)
#: rows   — one Row per eligible person, input order preserved
#: total  — sum of shares; equals pool when err is None
#: err    — an ERR_* code when the rule cannot be applied (rows empty, total 0)
Result = namedtuple('Result', 'rule pool rows total err')


def role_weight(role):
    """Weight for a role. Unknown roles weigh 1.0 rather than 0 — a person on
    shift with a tipped role must never silently receive nothing."""
    return ROLE_WEIGHTS.get((role or '').strip().lower(), DEFAULT_ROLE_WEIGHT)


def pooled_amount(people, rule):
    """The liability under ``rule``.

    Declared CASH stays with the person who declared it under Direct and Hybrid,
    and enters the pool under Equal, Hours, Role and Custom. This is the question
    every team argues about, so it is answered in one place.
    """
    captured = sum(p.captured for p in people)
    if rule in (DIRECT, HYBRID):
        return captured
    return captured + sum(p.declared for p in people)


def allocate(pool, weights):
    """Split ``pool`` piastres across ``weights`` by largest remainder.

    Returns a list of integers summing EXACTLY to ``pool``. Zero total weight
    returns None — the caller reports it rather than dividing by zero.
    """
    total_w = sum(weights)
    if total_w <= 0:
        return None
    exact = [pool * w / total_w for w in weights]
    floors = [int(x) for x in exact]
    remainder = pool - sum(floors)
    # Hand the leftover piastres to the largest fractional parts, biggest first;
    # ties go to the earlier position so the result is deterministic.
    order = sorted(range(len(exact)), key=lambda i: (-(exact[i] - floors[i]), i))
    for i in order[:remainder]:
        floors[i] += 1
    return floors


def distribute(people, rule, custom_pct=None, tip_out_pct=TIP_OUT_PCT):
    """Apply ``rule`` to ``people`` and return a :class:`Result`.

    ``custom_pct`` maps person key -> percentage, and is required by CUSTOM.
    Percentages must total 100 or the run is refused BY NUMBER, not silently
    normalised — a rule the team agreed to cannot be rewritten on their behalf.
    """
    if rule not in RULES:
        return Result(rule, 0, [], 0, ERR_UNKNOWN_RULE)
    people = list(people)
    if not people:
        return Result(rule, 0, [], 0, ERR_NO_ONE)

    pool = pooled_amount(people, rule)

    if rule == CUSTOM:
        pct = custom_pct or {}
        total = sum(pct.get(p.key, 0) for p in people)
        # Compared at 2dp: a percentage the manager typed, not a float sum.
        if round(total, 2) != 100.0:
            return Result(rule, pool, [], 0, ERR_CUSTOM_TOTAL)
        weights = [float(pct.get(p.key, 0)) for p in people]
    elif rule == EQUAL:
        weights = [1.0] * len(people)
    elif rule == HOURS:
        weights = [float(p.minutes) for p in people]
    elif rule == ROLE:
        weights = [p.minutes * role_weight(p.role) for p in people]
    elif rule == DIRECT:
        # Each server keeps the tips captured on their own checks. No weighting:
        # the allocation IS the capture, so it needs no remainder handling.
        rows = [Row(p.key, float(p.captured), p.captured) for p in people]
        return Result(rule, pool, rows, sum(r.share for r in rows), None)
    else:  # HYBRID
        return _hybrid(people, pool, tip_out_pct)

    shares = allocate(pool, weights)
    if shares is None:
        return Result(rule, pool, [], 0, ERR_NO_WEIGHT)
    rows = [Row(p.key, w, s) for p, w, s in zip(people, weights, shares)]
    return Result(rule, pool, rows, sum(shares), None)


def _hybrid(people, pool, tip_out_pct):
    """Direct, less a tip-out into a support pool split by hours x role weight.

    The tip-out is taken from each person's OWN captures (so a server who took
    nothing contributes nothing) and re-split across everyone on shift by
    hours x role weight.

    DECIDED: the contract says "a support pool split by hours x role weight"
    without defining which roles count as support. It splits across EVERYONE on
    shift -- the literal reading, confirmed with the product owner. Role weight
    already does the work of paying support roles less than the floor, so a
    second notion of "support" would double-count that.
    """
    tip_out = [int(p.captured * tip_out_pct / 100.0) for p in people]
    support = sum(tip_out)
    kept = [p.captured - t for p, t in zip(people, tip_out)]

    weights = [p.minutes * role_weight(p.role) for p in people]
    split = allocate(support, weights)
    if split is None:
        # Nobody has worked time to split the support pool by: it stays with the
        # people who earned it rather than evaporating.
        split = [0] * len(people)
        kept = [p.captured for p in people]

    rows = [Row(p.key, w, k + s) for p, w, k, s in zip(people, weights, kept, split)]
    return Result(HYBRID, pool, rows, sum(r.share for r in rows), None)
