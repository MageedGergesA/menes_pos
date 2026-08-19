# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Split Bill V2 — the rules, with no ORM and no request in sight.

A split moves *ownership* of items between checks. It is a financial operation and
never a kitchen one, and the difference is the whole reason this module exists
separately from the controller: the invariants below are the part that must not be
got wrong, so they are kept where they can be read and tested on their own.

The three that matter most, stated once:

* **You cannot move what is not there.** Availability is the original quantity
  minus everything already allocated to other checks. Selected can never exceed it,
  and the client's opinion of the quantity is an opinion, not a fact.
* **A configured product is one commercial unit.** A meal is not a burger plus a
  drink that can wander off separately; moving it moves all of it. Combos are
  already a parent/child line structure in Odoo, so this is enforced by expanding a
  selection to its family rather than by hoping the UI never offers the child.
* **The family reconciles exactly.** Root plus every child equals the original, to
  the cent, with residual pennies allocated deterministically rather than lost.

Nothing here talks to the database, so nothing here can be fooled by a stale read;
the caller does that under a lock.
"""

# Reasons are stable strings: the UI maps them to sentences, tests assert on them,
# and none of them leaks whether a neighbouring check exists.
OK = None
REASON_NO_LINES = 'no_lines'
REASON_UNKNOWN_LINE = 'unknown_line'
REASON_NOT_POSITIVE = 'quantity_not_positive'
REASON_NOT_INTEGER = 'quantity_not_integer'
REASON_OVER_ALLOCATED = 'over_allocated'
REASON_COMBO_CHILD = 'combo_child_not_movable'
REASON_COMBO_PARTIAL = 'combo_not_atomic'
REASON_PAID = 'already_paid'
REASON_EMPTY_RESULT = 'nothing_selected'

# Quantities are compared with a tolerance because pos.order.line.qty is a Float.
# A till deals in whole burgers; this is here to survive float representation, not
# to permit fractional selling (see SB-DEBT-FRACTIONAL-ITEM).
EPS = 1e-6


def is_integral(qty):
    return abs(qty - round(qty)) <= EPS


def available(line):
    """What is still movable off this line.

    ``line`` is a plain dict: {'qty', 'allocated'}. Allocated is what previous
    splits already took, so availability shrinks as a family grows — which is why
    the second terminal in a race finds nothing left rather than a stale number.
    """
    return max(0.0, float(line.get('qty') or 0.0) - float(line.get('allocated') or 0.0))


def expand_combo_selection(lines, allocations):
    """Grow a selection so a configured product moves whole.

    Selecting the parent of a combo selects its children at the same multiple; the
    children are never independently selectable. Returns a new allocation list.

    A combo child priced at zero still travels: the child lines carry the
    configuration, and leaving them behind would put a meal on one check and its
    fries on another.
    """
    by_id = {int(k): v for k, v in lines.items()}
    picked = {int(a['origin_line_id']): float(a['quantity']) for a in allocations}
    out = dict(picked)
    for line_id, qty in picked.items():
        line = by_id.get(line_id) or {}
        parent_qty = float(line.get('qty') or 0.0)
        if parent_qty <= 0:
            continue
        for child_id in (line.get('combo_children') or []):
            child = by_id.get(int(child_id)) or {}
            child_qty = float(child.get('qty') or 0.0)
            # children scale with the parent: 2 of a 4-meal parent takes half of
            # each child line, in whole units
            share = round(child_qty * (qty / parent_qty))
            if share > 0:
                out[int(child_id)] = float(share)
    return [{'origin_line_id': k, 'quantity': v} for k, v in sorted(out.items())]


def validate(lines, allocations, allow_paid=False):
    """(reason | None) for one proposed allocation against current line state.

    ``lines``  : {line_id: {'qty', 'allocated', 'combo_parent_id', 'combo_children', 'paid'}}
    ``allocations``: [{'origin_line_id', 'quantity'}]
    """
    if not allocations:
        return REASON_EMPTY_RESULT
    by_id = {int(k): v for k, v in lines.items()}
    seen = {}
    for alloc in allocations:
        try:
            line_id = int(alloc['origin_line_id'])
            qty = float(alloc['quantity'])
        except (KeyError, TypeError, ValueError):
            return REASON_UNKNOWN_LINE
        line = by_id.get(line_id)
        if line is None:
            return REASON_UNKNOWN_LINE
        if qty <= EPS:
            return REASON_NOT_POSITIVE
        if not is_integral(qty):
            # Fractional ownership of a single line is a real feature and a real
            # accounting question; it is deferred, not silently allowed in.
            return REASON_NOT_INTEGER
        if line.get('paid') and not allow_paid:
            return REASON_PAID
        if qty > available(line) + EPS:
            return REASON_OVER_ALLOCATED
        seen[line_id] = seen.get(line_id, 0.0) + qty
        if seen[line_id] > available(line) + EPS:
            return REASON_OVER_ALLOCATED

    # A combo child may only travel as part of its parent's selection.
    for line_id, qty in seen.items():
        line = by_id.get(line_id) or {}
        parent_id = line.get('combo_parent_id')
        if not parent_id:
            continue
        parent_id = int(parent_id)
        if parent_id not in seen:
            return REASON_COMBO_CHILD
        parent = by_id.get(parent_id) or {}
        parent_total = float(parent.get('qty') or 0.0)
        child_total = float(line.get('qty') or 0.0)
        if parent_total > 0 and child_total > 0:
            expected = round(child_total * (seen[parent_id] / parent_total))
            if abs(qty - expected) > EPS:
                return REASON_COMBO_PARTIAL
    return OK


def remaining_after(lines, allocations):
    """Line quantities the root keeps. Used for preview and for the commit's own check."""
    picked = {}
    for alloc in allocations:
        line_id = int(alloc['origin_line_id'])
        picked[line_id] = picked.get(line_id, 0.0) + float(alloc['quantity'])
    out = {}
    for line_id, line in lines.items():
        line_id = int(line_id)
        out[line_id] = max(0.0, float(line.get('qty') or 0.0) - picked.get(line_id, 0.0))
    return out


def even_amounts(total, ways, precision=2):
    """Split a total into ``ways`` parts that sum EXACTLY back to it.

    100 / 3 is 33.34, 33.33, 33.33 — never 99.99 and never 100.01. The residual
    cents go to the earliest parts, deterministically, so the same input always
    produces the same answer and a report can be reproduced.

    Works in integer minor units precisely so the arithmetic cannot drift.
    """
    if ways <= 0:
        return []
    scale = 10 ** precision
    minor = int(round(float(total) * scale))
    sign = -1 if minor < 0 else 1
    minor = abs(minor)
    base, residual = divmod(minor, ways)
    parts = []
    for i in range(ways):
        cents = base + (1 if i < residual else 0)
        parts.append(sign * cents / float(scale))
    return parts


def reconciles(original_total, parts, precision=2):
    """True when the family sums back to the original, in minor units."""
    scale = 10 ** precision
    lhs = int(round(float(original_total) * scale))
    rhs = sum(int(round(float(p) * scale)) for p in parts)
    return lhs == rhs


def transfer_fired(fired, allocations, product_of_line):
    """Split a fired snapshot between root and child.

    ``fired`` is ``pos.order.mezze_fired`` decoded: {product_id_str: qty} of what the
    kitchen has already been told to make. When items move to a child check, the
    corresponding *already fired* quantity has to move with them — otherwise the
    child looks like fresh demand and the kitchen cooks a second burger for a bill
    that was only ever divided.

    Returns ``(root_fired, child_fired)``. Neither total nor sum changes: this
    redistributes, it never creates.
    """
    root = {str(k): float(v) for k, v in (fired or {}).items()}
    child = {}
    for alloc in allocations:
        line_id = int(alloc['origin_line_id'])
        qty = float(alloc['quantity'])
        product_id = product_of_line.get(line_id)
        if not product_id:
            continue
        key = str(product_id)
        moved = min(qty, root.get(key, 0.0))
        if moved <= 0:
            continue
        root[key] = root.get(key, 0.0) - moved
        child[key] = child.get(key, 0.0) + moved
        if root[key] <= EPS:
            root.pop(key, None)
    return root, child


def covers_conserved(root_covers, child_covers_list, original_covers):
    """A bill divided four ways is still four people, not sixteen."""
    return int(root_covers or 0) + sum(int(c or 0) for c in child_covers_list) == int(
        original_covers or 0)
