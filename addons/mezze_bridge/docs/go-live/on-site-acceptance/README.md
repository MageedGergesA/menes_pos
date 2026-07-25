# On-Site Acceptance Pack — Mezze POS Controlled Pilot RC1

Release tag: **mezze-pilot-rc1** · Branch: `main` · Module: mezze_bridge 19.0.1.8.0

This pack is executed **on-site, on the exact tagged release**, by the pilot team. It is the
human half of the controlled-pilot gate — the engineering half (218 tests, validator 0-FAIL,
reconciliation 0, backup/restore 0-loss) is already proven and recorded under `../`.

**Nothing here may be marked Pass without a real observation.** Every checklist row has an operator,
date, tag, device, expected result, actual result, Pass/Fail, evidence filename, defect reference,
and comments. Blank = not yet executed. A single unresolved Critical or financial-Major defect blocks pilot approval.

## Order of execution
1. `environment-sheet.md` — record the exact on-site environment + confirm the running commit == tag.
2. `hardware-checklist.md` — receipt printer, cash drawer (kitchen printer if used).
3. `tablet-checklist.md` — true 1024×768 CSS viewport, RTL/LTR, light/dark, scale.
4. `service-loop-checklist.md` — five independent clients, full arrival→release loop + fault injection.
5. `financial-checklist.md` — end-of-session drawer + POS + accounting reconciliation.
6. `failure-recovery-checklist.md` — printer/KDS/tablet/worker faults, idempotency.
7. `signoff.md` — final operator + manager sign-off and the controlled-pilot verdict.

## Evidence
Store photos/video/screenshots next to each checklist (e.g. `hardware/receipt-arabic.jpg`) and put the
filename in the row's Evidence column. Do not store customer PII or card data in evidence.
