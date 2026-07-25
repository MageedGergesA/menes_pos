# True Tablet Acceptance

> Operator: ____________________  Date: __________  Release tag: `mezze-pilot-rc1`  Branch: `main`  Device/Client: ____________________

> Rule: no item may be marked Pass without a real on-site observation. Leave blank until executed.

> Use a physical tablet OR a browser whose **CSS viewport is verified 1024×768 via dev tools** (`window.innerWidth`/`innerHeight`). A resized hi-DPI desktop window is NOT acceptable unless dev tools confirm the CSS viewport.

Record verified CSS viewport: innerWidth = ______  innerHeight = ______

| # | Test | Expected result | Actual result | Verdict | Evidence file | Defect ref | Comments |
|---|------|-----------------|---------------|---------|---------------|------------|----------|
| 1 | Login on tablet | authenticates, reaches home | | ☐ Pass ☐ Fail | | | |
| 2 | Arabic RTL layout | mirrored correctly, readable | | ☐ Pass ☐ Fail | | | |
| 3 | English LTR layout | correct | | ☐ Pass ☐ Fail | | | |
| 4 | Light mode | legible, correct contrast | | ☐ Pass ☐ Fail | | | |
| 5 | Dark mode | legible, correct contrast | | ☐ Pass ☐ Fail | | | |
| 6 | 100% scale | no overflow, actions reachable | | ☐ Pass ☐ Fail | | | |
| 7 | 120% scale | no overflow, actions reachable | | ☐ Pass ☐ Fail | | | |
| 8 | Floor navigation | floors switch, tables visible | | ☐ Pass ☐ Fail | | | |
| 9 | Reservation seating | seat a reservation | | ☐ Pass ☐ Fail | | | |
| 10 | Table selection | select a table, open order | | ☐ Pass ☐ Fail | | | |
| 11 | Product selection | add products | | ☐ Pass ☐ Fail | | | |
| 12 | Modifiers | apply modifiers | | ☐ Pass ☐ Fail | | | |
| 13 | Quantities | change qty | | ☐ Pass ☐ Fail | | | |
| 14 | Course hold/fire | hold then fire a course | | ☐ Pass ☐ Fail | | | |
| 15 | Ready notification | ready state received | | ☐ Pass ☐ Fail | | | |
| 16 | Bill request | request bill | | ☐ Pass ☐ Fail | | | |
| 17 | Cashier handoff | order visible to cashier | | ☐ Pass ☐ Fail | | | |
| 18 | Manager approval dialog | dialog fits screen, usable | | ☐ Pass ☐ Fail | | | |
| 19 | Disconnect/reconnect | reconnect restores authoritative state | | ☐ Pass ☐ Fail | | | |

## Layout invariants (all must hold)
| # | Test | Expected result | Actual result | Verdict | Evidence file | Defect ref | Comments |
|---|------|-----------------|---------------|---------|---------------|------------|----------|
| 1 | No horizontal overflow | body does not scroll sideways | | ☐ Pass ☐ Fail | | | |
| 2 | No hidden primary actions | fire/pay/approve reachable | | ☐ Pass ☐ Fail | | | |
| 3 | Touch-safe control sizes | no mis-taps | | ☐ Pass ☐ Fail | | | |
| 4 | Readable table labels | legible at arm's length | | ☐ Pass ☐ Fail | | | |
| 5 | Usable order panel | full order list usable | | ☐ Pass ☐ Fail | | | |
| 6 | Dialogs fit | no clipped dialogs | | ☐ Pass ☐ Fail | | | |
| 7 | Popovers align | anchored correctly | | ☐ Pass ☐ Fail | | | |
| 8 | Floor geometry not mirrored wrongly in RTL | physical layout correct | | ☐ Pass ☐ Fail | | | |
