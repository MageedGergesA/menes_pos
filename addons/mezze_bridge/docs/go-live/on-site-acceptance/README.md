# On-Site Acceptance Pack — Mezze POS Controlled Pilot

## Release under certification
**`mezze-pilot-rc3` → `8ad8ed90c116b57a1c3e66b5323c5e3a9807d0a0`** (RC3 is immutable; run acceptance on
exactly this tag). RC1 `634d17e` and RC2 `13276b9` are prior identities, unchanged.

## Current status
**NOT CERTIFIED — awaiting physical/on-site execution.** The engineering half is proven and recorded
under `../` (229 automated tests 0 failed/0 error, validator settings-catalog PASS, reconciliation 0,
backup/restore 0-loss, catalog 101/18/76/7 on fresh install). This pack is the **human/hardware half** and
has **not** been executed — no gate here is passed. See `p2-status.md` for the full P2 status.

**Nothing here may be marked Pass without a real observation.** Every checklist row has operator, date/time,
RC tag, commit, branch, device, role, expected result, actual result, ☐ Pass ☐ Fail, evidence reference,
defect ID, and comments. Blank = not yet executed. A single unresolved Critical or financial-Major defect
blocks pilot approval.

## Required physical gates (all currently AWAITING EXECUTION)
Physical/verified **tablet** (1024×768 CSS viewport, Arabic RTL) · **cashier** workstation · **KDS**
browser/device · **receipt printer** (ESC/POS) · **cash drawer** · **customer QR phone** · concurrent
**multi-client** restaurant flow · network **reconnect** tests (KDS + tablet) · **worker-failure** recovery ·
representative **staff UAT** · 2–4h **shift simulation** · **session closing** · **financial reconciliation**
(unexplained difference = 0).

## Order of execution
1. `environment-sheet.md` — record the exact on-site environment + confirm the running commit == `8ad8ed9`.
2. `hardware-checklist.md` — receipt printer, cash drawer (kitchen printer if used).
3. `tablet-checklist.md` — true 1024×768 CSS viewport, RTL/LTR, light/dark, scale.
4. `service-loop-checklist.md` — five independent clients, full arrival→release loop + fault injection.
5. `financial-checklist.md` — end-of-session drawer + POS + accounting reconciliation.
6. `failure-recovery-checklist.md` — printer/KDS/tablet/worker faults, idempotency.
7. `signoff.md` — final operator + manager sign-off and the controlled-pilot verdict.

## Evidence structure
Each subdirectory is an evidence slot (currently `AWAITING EXECUTION`, see its own README):

| Directory | Holds |
|---|---|
| `devices/` | device matrix: models, browsers, CSS viewports, roles, users, network |
| `tablet/` | waiter-tablet acceptance (LTR/RTL, light/dark, 100%/120%), screenshots |
| `cashier/` | cashier workstation flows, session open/close, payment states |
| `kds/` | KDS display, ticket lifecycle, additions/cancellations, 50+ ticket load |
| `printer/` | receipt printer: EN/AR/mixed receipts, failure/reconnect, model/firmware |
| `drawer/` | cash-drawer kick on authorized cash, closed on card-only, role checks |
| `qr/` | customer QR ordering from a real phone: submit, duplicate, stale, revoke |
| `pickup/` | pickup ordering + pay-at-counter, edge cases |
| `delivery/` | pay-on-delivery + manual dispatch runbook |
| `aggregator/` | approved pilot aggregator: signed/duplicate/invalid callbacks, mapping |
| `failures/` | printer/KDS/tablet/worker failure + lost-response idempotency runs |
| `staff-uat/` | representative-staff UAT records per role (host/waiter/cashier/kitchen/manager) |
| `shift-simulation/` | 2–4h simulation: order counts, timings, injected faults, errors |
| `financial/` | end-of-shift drawer + POS + accounting reconciliation (difference = 0) |
| `session-close/` | real POS session close: expected vs counted cash, discrepancy, sign-off |
| `photos/` | on-site photos/video (no customer PII or card data) |
| `final/` | consolidated final acceptance summary + go/no-go |

Naming: `<gate>-<detail>.<ext>` (e.g. `printer/receipt-arabic.jpg`, `tablet/rtl-100-floor.png`). Put the
filename in the checklist row's Evidence column. **Do not store customer PII, card data, or credentials.**

## Release rule
If a physical test discovers a production defect requiring code changes: **RC3 remains immutable** →
record defect → add regression test → narrow fix → complete affected acceptance gates → full automated
suite → clean worktree → tag `mezze-pilot-rc4`. Never patch RC3 in place; never move RC3.
