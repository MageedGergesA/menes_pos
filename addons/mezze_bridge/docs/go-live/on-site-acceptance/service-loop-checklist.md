# Independent-Client Service Loop

> Operator: ____________________  Date: __________  Release tag: `mezze-pilot-rc1`  Branch: `main`  Device/Client: ____________________

> Rule: no item may be marked Pass without a real on-site observation. Leave blank until executed.

> Five independent clients: (1) host/waiter tablet (2) cashier browser (3) KDS browser (4) manager browser (5) customer QR/mobile. Each a SEPARATE client.

## Happy-path loop
| # | Test | Expected result | Actual result | Verdict | Evidence file | Defect ref | Comments |
|---|------|-----------------|---------------|---------|---------------|------------|----------|
| 1 | Reservation arrival | checked in | | ☐ Pass ☐ Fail | | | |
| 2 | Table assignment | table assigned, one owner | | ☐ Pass ☐ Fail | | | |
| 3 | Waiter order | lines added on tablet | | ☐ Pass ☐ Fail | | | |
| 4 | Hold/fire courses | courses fire to KDS | | ☐ Pass ☐ Fail | | | |
| 5 | KDS preparing/ready | states advance on KDS client | | ☐ Pass ☐ Fail | | | |
| 6 | Waiter served | served state set | | ☐ Pass ☐ Fail | | | |
| 7 | QR customer addition | customer adds item via QR, merges to one order | | ☐ Pass ☐ Fail | | | |
| 8 | Manager discount approval | approved on manager client | | ☐ Pass ☐ Fail | | | |
| 9 | Partial cash payment | cash part recorded | | ☐ Pass ☐ Fail | | | |
| 10 | Card completion | balance completed | | ☐ Pass ☐ Fail | | | |
| 11 | Receipt print | one receipt | | ☐ Pass ☐ Fail | | | |
| 12 | Cash drawer | opens on cash op | | ☐ Pass ☐ Fail | | | |
| 13 | Table release | released once | | ☐ Pass ☐ Fail | | | |

## Fault injection (must stay correct)
| # | Test | Expected result | Actual result | Verdict | Evidence file | Defect ref | Comments |
|---|------|-----------------|---------------|---------|---------------|------------|----------|
| 1 | Product 86 after cart creation | 86 propagates; checkout rejects item | | ☐ Pass ☐ Fail | | | |
| 2 | Printer unavailable | queues, no double, recovers | | ☐ Pass ☐ Fail | | | |
| 3 | KDS disconnect/reconnect | no duplicate items, state restored | | ☐ Pass ☐ Fail | | | |
| 4 | Waiter tablet disconnect/reconnect | authoritative state restored | | ☐ Pass ☐ Fail | | | |
| 5 | Lost payment response | same-uuid retry -> one payment | | ☐ Pass ☐ Fail | | | |
| 6 | Duplicate QR submission | one logical order | | ☐ Pass ☐ Fail | | | |
| 7 | Worker restart mid-flow | queued work delivers once | | ☐ Pass ☐ Fail | | | |

## Required outcomes
| # | Test | Expected result | Actual result | Verdict | Evidence file | Defect ref | Comments |
|---|------|-----------------|---------------|---------|---------------|------------|----------|
| 1 | One logical order | no duplicate order | | ☐ Pass ☐ Fail | | | |
| 2 | One logical payment | no double charge | | ☐ Pass ☐ Fail | | | |
| 3 | No duplicate KDS items | kitchen sees each once | | ☐ Pass ☐ Fail | | | |
| 4 | No stale silent overwrite | conflicts -> 409, not overwrite | | ☐ Pass ☐ Fail | | | |
| 5 | One table release | released exactly once | | ☐ Pass ☐ Fail | | | |
| 6 | Zero financial difference | reconciles to 0 | | ☐ Pass ☐ Fail | | | |
