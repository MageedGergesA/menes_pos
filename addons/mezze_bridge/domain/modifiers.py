"""Restaurant modifier selections — the canonical shape (design BE-010, M-01..M-04).

``docs/MENU_ENGINE.md`` §2a freezes what an order line records when a guest picks
Large / Extra spicy / No onion:

    ModifierSelection
      g   modifier group key
      t   option identifier
      p   price delta captured at order time

and states the rule this module exists to hold: **a rendered label
("Large · Extra spicy") is DERIVED, never stored.** Register once stored the
pre-joined string as the line's fact, which could not carry a price delta or a
group id at all -- two owners for one fact, and the poorer one winning.

Three readers, and only three: ``render`` (display), ``has`` (presence) and
``same`` (array-aware equality for merging identical lines). The design records
why the last one matters: a string ``===`` silently stopped merging identical
configurations the moment the shape changed.

Pure and dependency-free, like ``order_guard`` and ``tip_pool``: no Odoo import,
so the rules are unit-testable without a database.

NOTE ON IDENTITY. The prototype uses an option's LABEL as its identifier and
flags that plainly: renaming an option would silently detach it from every line
already using it. Here ``t`` is the option's stable database id and the label is
carried only for display -- the doc's own instruction for the Odoo persistence.
"""

from collections import namedtuple

#: g — modifier group key (stable)
#: t — option identifier (stable id, NOT the label)
#: label — display text only; never an identity
#: p — price delta captured when the line was taken
Selection = namedtuple('Selection', 'g t label p')

SEP = ' · '          # the middot the design renders between selections

# Refusal codes — returned as a list, never raised: an unsatisfied group is a
# thing to tell the guest, not a crash.
ERR_REQUIRED = 'required_group_missing'
ERR_MIN = 'below_min_select'
ERR_MAX = 'above_max_select'
ERR_UNKNOWN_GROUP = 'unknown_group'
ERR_UNKNOWN_OPTION = 'unknown_option'
ERR_UNAVAILABLE = 'option_unavailable'

#: key       — the group's stable key
#: required  — the guest must satisfy it
#: min_select/max_select — 0 means "unbounded"; Odoo has no native equivalent,
#:              which is why this is a POS-side rule (MENU_ENGINE §2)
#: options   — {option_id: available_bool}
Group = namedtuple('Group', 'key required min_select max_select options')


def render(selections):
    """The display label. Derived on demand -- never written to the line."""
    return SEP.join(s.label for s in selections if s.label)


def has(selections):
    """Whether a line carries any selection. ``mods`` is ALWAYS an array."""
    return bool(selections)


def same(a, b):
    """Array-aware equality, for merging identical lines.

    Compares group, option and captured delta -- order-insensitive, because two
    lines configured identically in a different click order are the same line.
    The delta is compared too: a line taken before a price change is NOT the
    same line as one taken after, and merging them would silently reprice one.
    """
    return sorted((s.g, s.t, round(s.p or 0.0, 4)) for s in a) == \
           sorted((s.g, s.t, round(s.p or 0.0, 4)) for s in b)


def validate(groups, selections):
    """Refusals for ``selections`` against ``groups``. Empty list means valid.

    Every rule here is one the guest can trip at the point of choice, which is
    where the design says an 86'd option must be refused -- not at checkout,
    and never after the kitchen has been told.
    """
    errors = []
    by_key = {g.key: g for g in groups}
    chosen = {}
    for s in selections:
        group = by_key.get(s.g)
        if group is None:
            errors.append((ERR_UNKNOWN_GROUP, s.g))
            continue
        if s.t not in group.options:
            errors.append((ERR_UNKNOWN_OPTION, s.t))
            continue
        if not group.options[s.t]:
            # 86 lives on the OPTION, so a branch can run out of one size
            # without withdrawing the dish.
            errors.append((ERR_UNAVAILABLE, s.t))
        chosen.setdefault(s.g, []).append(s.t)

    for group in groups:
        picks = len(chosen.get(group.key, ()))
        if group.required and not picks:
            errors.append((ERR_REQUIRED, group.key))
            continue
        if not picks:
            continue                      # optional and untouched: fine
        if group.min_select and picks < group.min_select:
            errors.append((ERR_MIN, group.key))
        if group.max_select and picks > group.max_select:
            errors.append((ERR_MAX, group.key))
    return errors


def total_delta(selections):
    """What the selections add to the line's unit price."""
    return sum(s.p or 0.0 for s in selections)
