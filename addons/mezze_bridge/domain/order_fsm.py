"""Order lifecycle finite-state machine — RFC-001 executable invariants.

ONE executable source of truth for the Order lifecycle. Odoo models and
controllers delegate here instead of re-implementing status guards, so a
forbidden transition is impossible by construction everywhere.

Canon:
  * RFC-001 "Order lifecycle & state machine": 13 states; forbidden transitions.
  * RFC-001 invariant: "A paid order cannot become unpaid."
  * RFC-002 P1.4 (truth durable), P1.7 (history/replay), P4 (event -> graph).
  * RFC-000: deterministic transitions; never trust ordering/retries.

Properties guaranteed (and property-tested in tests/test_order_fsm.py):
  * Determinism   — apply_event is a pure function of (state, event).
  * Closed set    — only allowed (state, event) pairs exist; all else raises.
  * Replay-safe   — fold(events) is order-preserving and reproducible.
  * Monotonic $   — once settled (PAID reached), an order can never re-enter a
                    pre-payment state ("a paid order cannot become unpaid").
  * Terminality   — ARCHIVED has no outgoing transitions.
"""

from enum import Enum


class State(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    HELD = "held"
    CONFIRMED = "confirmed"
    SENT = "sent"
    COOKING = "cooking"
    READY = "ready"
    SERVED = "served"
    PAID = "paid"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    ARCHIVED = "archived"


class Event(str, Enum):
    ADD_LINE = "add_line"
    OPEN = "open"
    HOLD = "hold"
    RESUME = "resume"
    CONFIRM = "confirm"
    SEND = "send"
    START_COOKING = "start_cooking"
    MARK_READY = "mark_ready"
    SERVE = "serve"
    PAY_PARTIAL = "pay_partial"   # balance remains > 0 -> state unchanged
    PAY_FULL = "pay_full"         # balance reaches 0    -> PAID
    CLOSE = "close"
    CANCEL = "cancel"
    REFUND = "refund"
    ARCHIVE = "archive"


class ForbiddenTransition(Exception):
    """Raised when a (state, event) pair is not an allowed transition."""

    def __init__(self, state, event):
        self.state, self.event = state, event
        super().__init__(f"forbidden transition: {state.value} --{event.value}-->")


# The transition table IS the business rule. Absence == forbidden.
# Partial payment self-loops (order stays open); only PAY_FULL reaches PAID.
_T = {
    State.DRAFT: {
        Event.ADD_LINE: State.DRAFT,      # self-loop: building the order
        Event.OPEN: State.OPEN,           # guard (caller): >= 1 line
        Event.CANCEL: State.CANCELLED,
    },
    State.OPEN: {
        Event.ADD_LINE: State.OPEN,
        Event.HOLD: State.HELD,
        Event.CONFIRM: State.CONFIRMED,
        Event.SEND: State.SENT,
        Event.PAY_PARTIAL: State.OPEN,
        Event.PAY_FULL: State.PAID,
        Event.CANCEL: State.CANCELLED,
    },
    State.HELD: {
        Event.RESUME: State.OPEN,         # restores exact snapshot
        Event.CANCEL: State.CANCELLED,
    },
    State.CONFIRMED: {
        Event.SEND: State.SENT,
        Event.PAY_PARTIAL: State.CONFIRMED,
        Event.PAY_FULL: State.PAID,
        Event.CANCEL: State.CANCELLED,
    },
    State.SENT: {
        Event.START_COOKING: State.COOKING,
        Event.PAY_PARTIAL: State.SENT,
        Event.PAY_FULL: State.PAID,
        Event.CANCEL: State.CANCELLED,
    },
    State.COOKING: {
        Event.MARK_READY: State.READY,
        Event.PAY_PARTIAL: State.COOKING,
        Event.PAY_FULL: State.PAID,
    },
    State.READY: {
        Event.SERVE: State.SERVED,
        Event.PAY_PARTIAL: State.READY,
        Event.PAY_FULL: State.PAID,
    },
    State.SERVED: {
        Event.PAY_PARTIAL: State.SERVED,
        Event.PAY_FULL: State.PAID,
        Event.CANCEL: State.CANCELLED,    # pre-payment cancel (manager-gated upstream)
    },
    State.PAID: {
        Event.CLOSE: State.CLOSED,
        Event.REFUND: State.REFUNDED,     # a NEW truth, never an un-payment
    },
    State.CLOSED: {
        Event.REFUND: State.REFUNDED,     # reversing entry (upstream), not an edit
        Event.ARCHIVE: State.ARCHIVED,
    },
    State.CANCELLED: {
        Event.ARCHIVE: State.ARCHIVED,    # terminal except archival
    },
    State.REFUNDED: {
        Event.ARCHIVE: State.ARCHIVED,
    },
    State.ARCHIVED: {},                   # terminal
}

# States at or beyond settlement. Reaching any of these sets "paid forever".
SETTLED_STATES = frozenset({State.PAID, State.CLOSED, State.REFUNDED})
# Pre-payment states that a settled order must NEVER return to.
PRE_PAYMENT_STATES = frozenset({
    State.DRAFT, State.OPEN, State.HELD, State.CONFIRMED,
    State.SENT, State.COOKING, State.READY, State.SERVED,
})
TERMINAL_STATES = frozenset({State.ARCHIVED})


def allowed_events(state):
    """Return the set of events permitted from `state` (pure)."""
    return frozenset(_T[State(state)].keys())


def apply_event(state, event):
    """Pure transition. Returns the next State or raises ForbiddenTransition.

    Never trusts the caller: an illegal (state, event) always raises rather than
    silently no-oping, so bad input cannot corrupt the lifecycle.
    """
    st, ev = State(state), Event(event)
    nxt = _T[st].get(ev)
    if nxt is None:
        raise ForbiddenTransition(st, ev)
    return nxt


def fold(events, start=State.DRAFT):
    """Replay an ordered event log into a final state (idempotent per run).

    Replay-safe: folding the same log twice yields the same result. Raises on the
    first forbidden event so a corrupt log cannot produce a phantom state.
    """
    state = State(start)
    for ev in events:
        state = apply_event(state, ev)
    return state


def is_settled(state):
    """True once an order has reached settlement (RFC-001 monotonic money)."""
    return State(state) in SETTLED_STATES


def reachable(start):
    """All states reachable from `start` via allowed transitions (BFS)."""
    seen, frontier = set(), [State(start)]
    while frontier:
        s = frontier.pop()
        if s in seen:
            continue
        seen.add(s)
        frontier.extend(_T[s].values())
    return frozenset(seen)
