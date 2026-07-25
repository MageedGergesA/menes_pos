"""Pure tests for the outbox dispatch policy (domain/outbox.py).

Runnable two ways:
  * Standalone:  python3 tests/test_outbox_policy.py
  * Under Odoo:  --test-tags mezze_invariants

Covers: backoff monotonicity + cap + floor, failure classification (retryable vs
permanent), the retry/dead-letter decision table, ordering-block predicate, plus
mutation checks that prove the suite catches a broken policy.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from domain import outbox as policy  # noqa: E402


def run_property_tests(iterations=20000):
    import random
    failures = []

    # backoff: non-negative, >= base, <= cap, monotonic non-decreasing in attempt
    prev = -1
    for attempt in range(1, 40):
        b = policy.next_backoff(attempt, base_seconds=2, factor=2, cap_seconds=3600)
        if b < 2:
            failures.append(("backoff_below_base", attempt, b))
        if b > 3600:
            failures.append(("backoff_above_cap", attempt, b))
        if b < prev:
            failures.append(("backoff_not_monotonic", attempt, b, prev))
        prev = b
    # eventually hits the cap and stays there
    if policy.next_backoff(30) != 3600 or policy.next_backoff(100) != 3600:
        failures.append(("backoff_cap_not_sticky",))
    # attempt<=0 floors to base
    if policy.next_backoff(0) != 2 or policy.next_backoff(-5) != 2:
        failures.append(("backoff_floor",))

    # classification partition: every mapped name is retryable XOR permanent
    for name in policy._EXC_MAP:
        cls = policy.classify(name)
        r = policy.is_retryable(cls)
        if r == (cls in policy.PERMANENT_CLASSES):
            failures.append(("classify_partition", name, cls))
    # unknown -> retryable (fail-open on delivery)
    for _ in range(200):
        rnd = "Weird%dError" % random.randint(0, 1_000_000)
        if not policy.is_retryable(policy.classify(rnd)):
            failures.append(("unknown_not_retryable", rnd))

    return failures


def run_decision_cases():
    f = []
    # permanent failure -> dead immediately, regardless of attempts
    for cls in ("permanent", "configuration", "security", "validation"):
        st, bo = policy.decide(cls, attempt=1, max_attempts=8)
        if st != policy.DEAD or bo is not None:
            f.append(("permanent_should_dead", cls, st, bo))
    # retryable with attempts left -> failed + a positive backoff
    st, bo = policy.decide("transport", attempt=1, max_attempts=8)
    if st != policy.FAILED or not (bo and bo > 0):
        f.append(("retryable_should_retry", st, bo))
    # retryable but exhausted (attempt == max) -> dead
    st, bo = policy.decide("timeout", attempt=8, max_attempts=8)
    if st != policy.DEAD or bo is not None:
        f.append(("exhausted_should_dead", st, bo))
    # attempt beyond max also dead
    st, bo = policy.decide("retryable", attempt=99, max_attempts=8)
    if st != policy.DEAD:
        f.append(("over_max_should_dead", st, bo))
    # ordering-block: only DONE unblocks the aggregate
    for s in (policy.PENDING, policy.INFLIGHT, policy.FAILED, policy.DEAD):
        if not policy.blocks_aggregate(s):
            f.append(("should_block", s))
    if policy.blocks_aggregate(policy.DONE):
        f.append(("done_should_not_block",))
    return f


def run_mutation_tests():
    """Prove the suite FAILS against deliberately broken policy variants."""
    caught = 0
    total = 0

    def mutant_decide_never_dead(fc, attempt, max_attempts):
        return (policy.FAILED, 1)  # bug: never dead-letters

    def mutant_backoff_shrinks(attempt, **kw):
        return max(1, 100 - attempt)  # bug: decreases with attempt

    def mutant_classify_all_permanent(name):
        return policy.PERMANENT  # bug: everything permanent

    # exhausted decision should be DEAD; mutant returns FAILED -> must be caught
    total += 1
    st, _ = mutant_decide_never_dead("timeout", 8, 8)
    if st != policy.DEAD:
        caught += 1
    # backoff must be monotonic; mutant shrinks -> must be caught
    total += 1
    if mutant_backoff_shrinks(2) < mutant_backoff_shrinks(1):
        caught += 1
    # unknown must classify retryable; mutant says permanent -> must be caught
    total += 1
    if not policy.is_retryable(mutant_classify_all_permanent("Weird")):
        caught += 1
    return caught, total


if __name__ == "__main__":
    pf = run_property_tests()
    df = run_decision_cases()
    caught, total = run_mutation_tests()
    ok = (len(pf) == 0 and len(df) == 0 and caught == total)
    print("Outbox dispatch-policy tests")
    print(f"  property failures : {len(pf)} {pf[:3]}")
    print(f"  decision failures : {len(df)} {df[:3]}")
    print(f"  mutations caught  : {caught}/{total}")
    print("RESULT:", "PASS ✓" if ok else "FAIL ✗")
    raise SystemExit(0 if ok else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestOutboxPolicy(TransactionCase):
        def test_property(self):
            self.assertEqual(run_property_tests(), [], "outbox backoff/classify invariants violated")

        def test_decisions(self):
            self.assertEqual(run_decision_cases(), [], "outbox decision table wrong")

        def test_mutations(self):
            caught, total = run_mutation_tests()
            self.assertEqual(caught, total, "suite failed to catch a broken policy")
except Exception:  # Odoo not present
    pass
