# Failure-Recovery Acceptance

> Operator: ____________________  Date: __________  Release tag: `mezze-pilot-rc1`  Branch: `main`  Device/Client: ____________________

> Rule: no item may be marked Pass without a real on-site observation. Leave blank until executed.

| # | Test | Expected result | Actual result | Verdict | Evidence file | Defect ref | Comments |
|---|------|-----------------|---------------|---------|---------------|------------|----------|
| 1 | Receipt printer disconnect + reconnect | job prints once on recovery | | ☐ Pass ☐ Fail | | | |
| 2 | KDS disconnect + reconnect | no duplicate tickets, state restored | | ☐ Pass ☐ Fail | | | |
| 3 | Waiter tablet disconnect + reconnect | authoritative state restored | | ☐ Pass ☐ Fail | | | |
| 4 | Lost payment response (network drop after tender) | same-uuid retry returns existing payment | | ☐ Pass ☐ Fail | | | |
| 5 | Duplicate QR / aggregator submission | one logical order | | ☐ Pass ☐ Fail | | | |
| 6 | One worker killed mid-service | queued work delivers once, no loss | | ☐ Pass ☐ Fail | | | |
| 7 | Stuck outbox event | visible in outbox, replay does not duplicate | | ☐ Pass ☐ Fail | | | |
| 8 | Session close with everything resolved | closes and reconciles | | ☐ Pass ☐ Fail | | | |
