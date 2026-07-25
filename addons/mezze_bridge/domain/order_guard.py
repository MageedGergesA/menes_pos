"""Order-operation guard — bridges live order operations to the RFC-001 FSM.

The Odoo ``pos.order.state`` vocabulary (draft/paid/done/invoiced/cancel) is a
projection of the richer RFC-001 lifecycle. This module maps a live operation
onto the canonical FSM and returns a verdict, so the "only open orders can be
paid / modified" rule has ONE executable source of truth (RFC-000: never
duplicate business rules) instead of scattered ``if order.state != 'draft'``.

Pure and dependency-free (no Odoo import): deterministic, unit-testable,
importable by controllers. Never trusts the caller — unknown states/operations
are reported as skipped (ok, no verdict) rather than silently mutating anything.
"""

from collections import namedtuple

from .order_fsm import State, Event, apply_event, ForbiddenTransition

# pos.order.state  ->  canonical lifecycle state
ODOO_STATE_MAP = {
    "draft": State.OPEN,        # POS "draft" == an open, unpaid order
    "paid": State.PAID,
    "done": State.CLOSED,
    "invoiced": State.CLOSED,
    "cancel": State.CANCELLED,
}

# live operation  ->  representative FSM event.
#   pay     -> settlement      (illegal once already settled)
#   refund  -> refund          (illegal before settlement)
#   cancel  -> cancel          (illegal once settled/terminal)
#   close   -> close
#   comp/modify -> ADD_LINE     (reuses the "paid orders are immutable" rule)
OP_EVENT_MAP = {
    "pay": Event.PAY_FULL,
    "pay_partial": Event.PAY_PARTIAL,
    "refund": Event.REFUND,
    "cancel": Event.CANCEL,
    "close": Event.CLOSE,
    "comp": Event.ADD_LINE,     # comp mutates the order -> "immutable once paid"
    "modify": Event.ADD_LINE,
    "add_line": Event.ADD_LINE,
    "fire": Event.SEND,         # fire to kitchen: legal only from an open lifecycle
}

Verdict = namedtuple("Verdict", ["ok", "event", "reason"])

# Modes for the live guard (mirrors ir.config_parameter 'mezze_bridge.fsm_guard').
MODE_OFF = "off"
MODE_OBSERVE = "observe"
MODE_ENFORCE = "enforce"
VALID_MODES = (MODE_OFF, MODE_OBSERVE, MODE_ENFORCE)

# Result of a live evaluation. ``blocked`` -> caller must reject before mutating.
# ``audit_detail`` -> a violation was found and this dict must be recorded.
EvalResult = namedtuple("EvalResult", ["blocked", "violation", "verdict", "audit_detail"])


def check_operation(odoo_state, operation):
    """Return a Verdict for performing ``operation`` on an order in ``odoo_state``.

    ok=True  -> permitted (or unknown state/op -> skipped, never blocks)
    ok=False -> forbidden by the FSM; ``reason`` explains why.
    """
    fsm_state = ODOO_STATE_MAP.get(odoo_state)
    if fsm_state is None:
        return Verdict(True, None, "unknown_state_skipped:%s" % odoo_state)
    event = OP_EVENT_MAP.get(operation)
    if event is None:
        return Verdict(True, None, "unknown_operation_skipped:%s" % operation)
    try:
        apply_event(fsm_state, event)
        return Verdict(True, event, "ok")
    except ForbiddenTransition:
        return Verdict(
            False, event,
            "forbidden:%s cannot %s (event %s)" % (odoo_state, operation, event.value),
        )


def evaluate(odoo_state, operation, mode, ctx=None):
    """Pure live-guard decision. No Odoo, no I/O — fully unit-testable.

    Returns an EvalResult:
      * mode 'off'            -> never evaluates, never blocks, never audits.
      * allowed operation     -> blocked=False, violation=False, no audit.
      * forbidden + 'observe' -> blocked=False (behaviour preserved), audit_detail set.
      * forbidden + 'enforce' -> blocked=True (reject before mutation), audit_detail set.

    ``ctx`` is a dict of safe operational context merged into the audit detail
    (endpoint, order id, branch, correlation id, actor, timestamp). The caller is
    responsible for excluding secrets/PAN/PII — this function copies ``ctx`` as-is.
    """
    if mode not in VALID_MODES:
        mode = MODE_OBSERVE                       # unknown/misconfigured -> safe default
    if mode == MODE_OFF:
        return EvalResult(False, False, None, None)
    verdict = check_operation(odoo_state, operation)
    if verdict.ok:
        return EvalResult(False, False, verdict, None)
    detail = dict(ctx or {})
    detail.update({
        "operation": operation,
        "server_state": odoo_state,               # authoritative, never client-supplied
        "mapped_event": verdict.event.value if verdict.event else None,
        "reason": verdict.reason,
        "reason_code": "forbidden_transition",
        "mode": mode,
        "observe_proceeded": mode == MODE_OBSERVE,  # observe never blocks the endpoint
    })
    return EvalResult(mode == MODE_ENFORCE, True, verdict, detail)
