# P1 Final Verdict

## Controlled pilot: **GO** (conditional on two on-site verifications)
The release candidate (mezze_bridge 19.0.1.8.0, commit ce8dc74) is a reproducible, rollback-safe
candidate for a CONTROLLED single-branch pilot with trusted staff, PROVIDED that, before first
live service, the branch team completes the two verifications that cannot be performed in the CI
environment:
  1. **Real hardware** — receipt/kitchen printer, cash drawer, and (if used) payment terminal exercised
     per the hardware runbook.
  2. **Real tablet** — the waiter tablet flow at 1024×768 (100% + 120% scale, Arabic RTL) on the physical device.

Everything else is proven: 218 green tests, config validator (0 FAIL), financial reconciliation
(0 diff / 294 genuine orders), backup+restore (0 loss, ~14s RTO), multi-worker idempotency
(seat/fire/pay/merge/aggregator → one logical operation), hardened status tokens, and the safety
guards (merge-financial-safety, readonly-route fixes, role boundaries). Unsafe capabilities
(online card, drive-thru, seat-level split, advanced dispatch) are disabled.

## Unrestricted public launch: **NO-GO**
Blocked by design for this increment: no proven public online **card** payment journey; hardware
and physical-tablet acceptance are on-site steps; a full on-site staff UAT + service-day simulation
are the pilot itself, not a CI artifact. These are the explicitly deferred product capabilities.

## Unresolved blockers
- Critical: **0**
- Major (financial): **0**
- On-site prerequisites (not blockers, but gates before first service): real hardware, real tablet.
