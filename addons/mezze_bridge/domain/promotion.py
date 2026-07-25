"""Executable enforcement-promotion gate for the order lifecycle guard.

Enforcement (`mezze_bridge.fsm_guard = enforce`) may only be recommended when
every criterion below is met. This is an EXECUTABLE gate, not a checklist: call
``assess(summary, evidence)`` and act on ``ready``. The observation window is
expressed as a minimum count of *classified* observations (evidence-based),
NOT an invented time duration — ``min_observations`` is configurable.

``summary`` — aggregated from the ``order.fsm_violation`` audit events, which are
directly queryable, e.g. in Odoo:
    env['mezze.audit.log'].search([('event','=','order.fsm_violation')])
grouped by the ``operation`` / ``server_state`` fields in each event's detail.

    summary = {
        'observed_count':   int,   # total violations observed in observe mode
        'unclassified':     int,   # violations not yet triaged
        'unexplained_fp':   int,   # confirmed false positives with no explanation
        'by_operation':     {op: count, ...},   # queryable violation rate by op
    }
    evidence = {
        'suites_green':     bool,  # refund/comp/fire/payment integration + regression
        'mutation_green':   bool,  # mutation tests prove the guard cannot be bypassed
        'rollback':         {op: bool, ...},  # per-op off-mode bypass proof; must
                                   # cover pay/fire/refund/comp/cancel, each True.
                                   # (legacy: a bool 'rollback_tested' is honoured
                                   #  only when no per-op dict is supplied.)
        'dashboards_ready': bool,  # violation rate identifiable by operation
        'owner_approved':   bool,  # release owner explicitly approves promotion
    }
"""

from collections import namedtuple

Readiness = namedtuple("Readiness", ["ready", "blocking"])

DEFAULT_MIN_OBSERVATIONS = 0  # project-configurable; 0 means "no minimum required"

# rollback_tested is TRUE only when the off-mode bypass is proven for EVERY
# guarded operation. Missing any one keeps enforcement un-promotable.
REQUIRED_ROLLBACK_OPS = ("pay", "fire", "refund", "comp", "cancel")


SECURITY_PROMOTION_CRITERIA = (
    ("classification_complete", "not_every_route_classified"),
    ("gate_coverage_complete", "protected_routes_missing_gate"),
    ("signature_required_enforced", "sig_required_routes_accept_unsigned"),
    ("multicompany_runtime_green", "multi_company_isolation_unproven"),
    ("multibranch_runtime_green", "multi_branch_isolation_unproven"),
    ("replay_runtime_green", "replay_protection_unproven"),
    ("revoked_terminal_green", "terminal_revocation_unproven"),
    ("legacy_token_understood", "legacy_shared_token_usage_unclassified"),
    ("suites_green", "test_suites_not_green"),
)


def security_ready(evidence):
    """Executable observe->enforce promotion gate for the API security layer.
    Returns Readiness(ready, blocking). Every criterion must be explicitly True."""
    evidence = evidence or {}
    blocking = [label for key, label in SECURITY_PROMOTION_CRITERIA
                if not bool(evidence.get(key, False))]
    return Readiness(ready=not blocking, blocking=blocking)


def rollback_tested(evidence):
    """Derive rollback_tested from explicit per-operation results.

    ``evidence['rollback']`` must be a dict {op: bool} covering every op in
    REQUIRED_ROLLBACK_OPS, each True. A legacy bool ``evidence['rollback_tested']``
    is honoured only if no per-op dict is supplied. Returns (bool, [missing/failed]).
    """
    evidence = evidence or {}
    rb = evidence.get("rollback")
    if isinstance(rb, dict):
        bad = [op for op in REQUIRED_ROLLBACK_OPS if rb.get(op) is not True]
        return (not bad, bad)
    # legacy fallback: an explicit bool, but only if no per-op evidence given
    if evidence.get("rollback_tested") is True:
        return (True, [])
    return (False, list(REQUIRED_ROLLBACK_OPS))


def assess(summary, evidence, min_observations=DEFAULT_MIN_OBSERVATIONS):
    """Return Readiness(ready: bool, blocking: [reason, ...]).

    Pure and deterministic. Every criterion is checked; ``blocking`` lists the
    exact unmet ones so the caller can report what remains.
    """
    summary = summary or {}
    evidence = evidence or {}
    blocking = []

    if int(summary.get("unexplained_fp", 0)) != 0:
        blocking.append("unexplained_false_positives:%d" % summary["unexplained_fp"])
    if int(summary.get("unclassified", 0)) != 0:
        blocking.append("unclassified_violations:%d" % summary["unclassified"])
    if int(summary.get("observed_count", 0)) < int(min_observations):
        blocking.append("insufficient_observations:%d<%d"
                        % (summary.get("observed_count", 0), min_observations))
    rb_ok, rb_missing = rollback_tested(evidence)
    if not rb_ok:
        blocking.append("rollback_not_proven_for:%s" % ",".join(rb_missing))

    for key, label in (
        ("suites_green", "integration_regression_suites_not_green"),
        ("mutation_green", "mutation_tests_not_proving_bypass_resistance"),
        ("dashboards_ready", "violation_rate_not_queryable_by_operation"),
        ("owner_approved", "release_owner_not_approved"),
    ):
        if not bool(evidence.get(key, False)):
            blocking.append(label)

    return Readiness(ready=not blocking, blocking=blocking)
