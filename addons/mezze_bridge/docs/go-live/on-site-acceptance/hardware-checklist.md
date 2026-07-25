# Hardware Acceptance

> Operator: ____________________  Date: __________  Release tag: `mezze-pilot-rc1`  Branch: `main`  Device/Client: ____________________

> Rule: no item may be marked Pass without a real on-site observation. Leave blank until executed.

## Required devices present
| # | Test | Expected result | Actual result | Verdict | Evidence file | Defect ref | Comments |
|---|------|-----------------|---------------|---------|---------------|------------|----------|
| 1 | Cashier terminal present & signed in | reaches POS, correct branch | | ☐ Pass ☐ Fail | | | |
| 2 | Independent KDS device/browser present | separate client, shows kitchen queue | | ☐ Pass ☐ Fail | | | |
| 3 | Real receipt printer connected | prints a test page | | ☐ Pass ☐ Fail | | | |
| 4 | Real cash drawer connected | kicks on authorized cash op | | ☐ Pass ☐ Fail | | | |
| 5 | Waiter tablet present | reaches waiter UI | | ☐ Pass ☐ Fail | | | |

## Receipt printer
| # | Test | Expected result | Actual result | Verdict | Evidence file | Defect ref | Comments |
|---|------|-----------------|---------------|---------|---------------|------------|----------|
| 1 | English receipt | legible, aligned, correct totals | | ☐ Pass ☐ Fail | | | |
| 2 | Arabic receipt | correct RTL shaping, legible | | ☐ Pass ☐ Fail | | | |
| 3 | Mixed Arabic/English receipt | both scripts correct | | ☐ Pass ☐ Fail | | | |
| 4 | Receipt with modifiers | modifiers listed under line | | ☐ Pass ☐ Fail | | | |
| 5 | Long product names | wrap/truncate cleanly, no overflow | | ☐ Pass ☐ Fail | | | |
| 6 | Discount shown | discount line + adjusted total | | ☐ Pass ☐ Fail | | | |
| 7 | Tax shown | tax line correct | | ☐ Pass ☐ Fail | | | |
| 8 | Partial-payment receipt | shows paid + balance due | | ☐ Pass ☐ Fail | | | |
| 9 | Mixed-payment receipt | each tender line shown | | ☐ Pass ☐ Fail | | | |
| 10 | Refund receipt | clearly marked refund, negative | | ☐ Pass ☐ Fail | | | |
| 11 | Duplicate-print protection | reprint does not double financials | | ☐ Pass ☐ Fail | | | |
| 12 | Printer disconnect mid-print | job queues, no crash, no double | | ☐ Pass ☐ Fail | | | |
| 13 | Reconnect + retry | queued job prints once on reconnect | | ☐ Pass ☐ Fail | | | |

## Cash drawer
| # | Test | Expected result | Actual result | Verdict | Evidence file | Defect ref | Comments |
|---|------|-----------------|---------------|---------|---------------|------------|----------|
| 1 | Opens on authorized cash operation | drawer kicks | | ☐ Pass ☐ Fail | | | |
| 2 | Does NOT open for card-only (unless configured) | stays closed | | ☐ Pass ☐ Fail | | | |
| 3 | Reconnect after unplug | drawer usable again | | ☐ Pass ☐ Fail | | | |
| 4 | Unavailable-device response | clear error, no crash | | ☐ Pass ☐ Fail | | | |
| 5 | Wrong-terminal assignment blocked | rejected | | ☐ Pass ☐ Fail | | | |

## Kitchen printer (if used by this branch)
| # | Test | Expected result | Actual result | Verdict | Evidence file | Defect ref | Comments |
|---|------|-----------------|---------------|---------|---------------|------------|----------|
| 1 | Kitchen printer test OR mark N/A with reason | tickets print, or N/A: ____________ | | ☐ Pass ☐ Fail | | | |
