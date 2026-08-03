# MEZZE POS v1.0 RC1 — FINAL COMMERCIAL PILOT — FIELD RUNBOOK

> Print this. Work top to bottom. Tick every box with real evidence. A blank box is
> NOT a pass. This runbook is the ONE script the pilot team follows in the restaurant.

```
Release:            mezze-v1.0-rc1
Commit:             ad32f3ea533912e01cacaa92e3427f808ff1a92e
Pilot date:         ____________________
Restaurant:         ____________________
Branch:             ____________________
Lead operator:      ____________________
Technical lead:     ____________________
Restaurant manager: ____________________
```

> **DO NOT TEST ANOTHER COMMIT. DO NOT MOVE THE RC TAG.**
> Every environment deploys exactly `mezze-v1.0-rc1` (`ad32f3e…`).

---

## ⛔ PILOT STOPS IMMEDIATELY FOR (CRITICAL — no operator may override)

- wrong financial amount
- duplicate payment / duplicate charge
- lost paid order
- lost kitchen (KDS) order
- data corruption
- unauthorized access
- unrecoverable database failure
- **unexplained financial reconciliation difference**

Log the defect in `defects/` with severity **CRITICAL**, halt, escalate to the
Technical lead. Do not "work around" a Critical.

---

## Pilot kit checklist (PART 6)

**Base Cloud / restaurant**
```
☐ Cashier workstation (Chromium)
☐ Independent waiter tablet
☐ Independent KDS screen (NOT a cashier tab)
☐ Real receipt printer (Epson TM-m30 series preferred)
☐ Cash drawer (only if in the sold SKU)
☐ Router / Wi-Fi
☐ Customer phone A (Android)
☐ Customer phone B (iOS preferred)
☐ Representative restaurant staff (cashier, waiter, kitchen, manager)
```
**Edge additionally**
```
☐ Clean Ubuntu 24.04 Host A
☐ Clean Ubuntu 24.04 Host B (NOT a clone of A)
☐ UPS
☐ Controllable WAN connection (you can physically cut it)
☐ Confirm LAN keeps working when WAN is removed
```

---

## Device policies

### Printer (PART 7)
Preferred baseline: **Epson TM-m30 i/ii/iii**, Wi-Fi or Ethernet ePOS, **Ethernet
preferred**, static/reserved IP.
- Record whether **Local Network Access (LNA)** or another supported secure native
  path is used for direct ePOS/browser printing.
- USB/ESC-POS is **not** equivalent to direct network ePOS — if used, record the
  **IoT box dependency**.
- **Bluetooth receipt printers: UNSUPPORTED.**

### LNA check (PART 8) — where Local Network Access is used
```
Browser:            ____________________
Browser version:    ____________________
LNA permission:     ☐ Granted   ☐ Not granted
Printer static IP:  ____________________
```
Use a current supported Chromium browser. **Do not proceed with LNA printer
certification if permission is denied.**

### KDS (PART 9)
Must be an **independent device/browser**, not another tab on the cashier device.
No IoT box is required for the preparation display.
```
KDS device: __________  OS: __________  Browser: __________  Conn: Wi-Fi / Ethernet
```

---

## Evidence rules (PART 10–11)

Every physical gate records: **Date/time · Operator · RC tag · Commit · Device ·
Expected · Actual · PASS/FAIL · Evidence · Defect ID (if any) · Comments.**
Evidence = photo / screenshot / receipt photo / command output / reconciliation
file / backup result / staff UAT sheet. **Never** accept "worked" / "looks fine" /
"probably okay".

File naming: `YYYYMMDD-HHMM_<gate>_<device>_<result>.<ext>`
(e.g. `20260815-1032_printer_arabic_TM-m30_PASS.jpg`). **No customer PII in
filenames or committed evidence** — redact names, phones, exact addresses.

Copy `results-template.md` into the matching subdirectory for each gate.

---

# EXECUTION — work the phases in order

Legend for the Result column: `PASS` / `FAIL(+defect id)` / `N/A(reason)`. Start
every physical row as **AWAITING EXECUTION**.

## PHASE 0 — Release check (PART 12)
```
☐ mezze-v1.0-rc1 exists (git tag --list mezze-v1.0-rc1)
☐ peeled tag == ad32f3e…  (git rev-parse 'mezze-v1.0-rc1^{}')
☐ runtime /admin/version.git_commit == ad32f3e…
☐ product_version = 1.0.0-rc.1
☐ module_version  = 19.0.2.0.0
☐ release_channel = rc
☐ working tree clean on the deployed host
```
FAIL the whole pilot if runtime git_commit ≠ ad32f3e (you are running the wrong build).

## PHASE 1 — Environment inventory (PART 13)
Fill `hardware-inventory.md` AND record host facts: Cloud host / Edge Host A / B;
CPU, RAM, disk, OS, kernel; Odoo, Python, PostgreSQL versions; domain, HTTPS; Odoo
workers; LAN subnet; WAN provider; router; printer/drawer/cashier/tablet/KDS/
phones/UPS. **No placeholder may survive final signoff.**

## PHASE 2 — Cloud deployment (PART 14) — if Cloud profile certified
```
☐ clean hosted environment (not localhost)   ☐ exact RC checkout
☐ Odoo starts   ☐ PostgreSQL starts   ☐ HTTPS valid   ☐ WebSocket works
☐ production onboarding works   ☐ validator: 0 blocking FAIL for the profile
☐ database manager secured   ☐ demo disabled   ☐ debug hidden   ☐ backup scheduled
```

## PHASE 3 — Edge Host A (PART 15) — subordinate ref: docs/sell-ready/edge/certification/s1_1b/RUNBOOK.md
```
☐ clean Ubuntu Server 24.04   ☐ hardware meets target   ☐ checkout exact RC
☐ installer   ☐ PostgreSQL   ☐ Odoo   ☐ systemd   ☐ nginx   ☐ HTTPS   ☐ WebSocket
☐ release identity == ad32f3e   ☐ reboot   ☐ validator   ☐ support bundle
☐ backup   ☐ restore
```
No physical PASS without executing on Host A.

## PHASE 4 — Edge Host B (PART 16)
Repeat Phase 3 on a **separate clean** environment. **DO NOT CLONE HOST A's
INSTALLED DISK.** Host B proves repeatable clean deployment. Record any difference
and any manual/unsupported intervention (target: 0).

## PHASE 5 — Cashier device (PART 17)
1 Login as cashier · 2 open production cashier · 3 load real menu · 4 add product ·
5 change qty · 6 remove line · 7 add again · 8 charge · 9 Cash exact · 10 new order ·
11 Cash with change · 12 Manual Card · 13 mixed Cash+Card · 14 reprint.
Record browser console. **Expected: 0 uncaught application errors.** Do EN and AR,
light and dark.

## PHASE 6 — Real tablet (PART 18) — physical device only
```
☐ login  ☐ floor/table list  ☐ open table  ☐ order  ☐ qty  ☐ modifiers
☐ guest count  ☐ transfer table  ☐ Arabic  ☐ touch  ☐ disconnect Wi-Fi  ☐ reconnect
```
Required: no horizontal overflow, no unusable dialog, no double-touch action, state
converges after reconnect. Record **physical resolution + actual CSS viewport**.

## PHASE 7 — KDS (PART 19)
Send once each: ☐ counter ☐ dine-in ☐ course ☐ table-QR addition ☐ pickup ☐ delivery.
Then ☐ Ready ☐ Completed ☐ cancellation ☐ item addition. **No duplicate KDS logical
order.**

## PHASE 8 — KDS network failure (PART 20)
1 disconnect KDS · 2 place 3+ orders · 3 reconnect · 4 observe convergence.
Record: placed-while-disconnected, appeared-after-reconnect, lost, duplicates,
recovery time. **Required: lost = 0, duplicates = 0.**

## PHASE 9 — Printer (PART 21) — physically print + photograph each
```
☐ English receipt  ☐ Arabic receipt  ☐ mixed AR/EN  ☐ Cash  ☐ Manual Card
☐ mixed tender  ☐ refund  ☐ long order  ☐ modifiers  ☐ delivery receipt  ☐ reprint
```
Verify on paper: money, Arabic legibility, reference, alignment, paper cut,
QR/barcode if present.

## PHASE 10 — Printer failure (PART 22)
1 start order · 2 complete payment · 3 disconnect printer · 4 attempt print ·
5 verify order/payment unchanged · 6 restore printer · 7 reprint.
**Required: no financial rollback, no duplicate payment, reprint succeeds.**

## PHASE 11 — Cash drawer (PART 23) — if sold, else mark N/A (not PASS)
```
☐ Cash opens drawer  ☐ Card does NOT open (if configured)  ☐ manual authorized open
☐ drawer reconnect
```

## PHASE 12 — Table QR, phone A (PART 24) — use the PRINTED QR (don't paste URL)
scan → menu → add → submit. Verify: correct branch, correct table, canonical order,
KDS once. Then **tamper** the table/context in the URL → **must REJECT**.

## PHASE 13 — Two-phone concurrency (PART 25)
Phone A + Phone B, same table, submit independent additions near-simultaneously.
Record exact products + timestamps. Required: both additions preserved, old lines
unchanged, KDS additions once, correct total.

## PHASE 14 — Pickup (PART 26)
Physical phone: full pickup journey — order, payment policy, KDS, Ready, tracking.

## PHASE 15 — Delivery (PART 27)
Physical phone: address → zone → fee → minimum → ETA → COD → KDS → dispatch → out
for delivery → delivered → COD collection. Use a real-but-controlled pilot address;
**redact the address in committed evidence.**

## PHASE 16 — Payment matrix (PART 28)
Cash: ☐ exact ☐ change. Manual Card: ☐ required device ☐ required reference
☐ duplicate WARN ☐ BLOCK ☐ manager approval ☐ cashier cannot self-approve.
Mixed: ☐ Cash+Card ☐ other configured tender. Refund: ☐ full ☐ partial ☐ repeat
protection. Record order/payment IDs in PRIVATE evidence only.

## PHASE 17 — Optional integrations (PART 29) — only if being sold/certified
Separate pages: Paymob / integrated terminal / cash machine / kiosk / aggregator.
If not sold: mark **NOT INCLUDED IN PILOT PROFILE** (never FAIL).

## PHASE 18 — Edge WAN 5 min (PART 30) — physically remove WAN, keep LAN
Record exact start/end. During outage: cashier orders, table order, KDS, printer,
Cash, manual payment. Record orders / payments / lost / dup orders / dup payments /
dup KDS. **Required: all lost & duplicates = 0.**

## PHASE 19 — Edge WAN 30 min (PART 31)
Meaningful workload: counter, dine-in, QR, mixed, refund (where locally supported).
Record all counts. Same zero-loss/zero-dup requirement.

## PHASE 20 — Edge WAN 2 hours (PART 32) — FLAGSHIP EDGE GATE
Target min: 20 counter, 10 dine-in, 5 Table-QR, mixed payments, refund, KDS,
printer, manager action. Online-only services must report unavailable/paused
**honestly** and must not corrupt local operation. Record exact counts.

## PHASE 21 — WAN reconnect (PART 33)
Restore WAN; observe a settling period. Verify: connectivity status converges,
external services recover, outbox converges, and **lost local = 0, dup order = 0,
dup payment = 0, dup KDS = 0**. Record outbox/queue state before + after.

## PHASE 22 — Server / worker failure (PART 34)
☐ local service interruption + recovery ☐ one-worker kill (if workers > 1).
Required: correct "local server unavailable" state (NOT "internet down", NOT a demo
fallback), no duplicate financial effect, clients recover. **Pilot host only — never
touch an unrelated production host.**

## PHASE 23 — Power / UPS (PART 35) — controlled safe test
Record UPS model, server draw (if measurable), whether router is protected, runtime,
shutdown/recovery behavior. **Do not invent UPS runtime.** PostgreSQL integrity must
remain valid; no financial data loss.

## PHASE 24 — Staff UAT (PART 36)
Real users per role: Cashier, Waiter, Kitchen, Manager (+ Host, Delivery where sold).
Run `docs/customer/UAT.md`. **A developer running every role is NOT staff UAT.**
Record operator, role, task, PASS/FAIL, comments, defect.

## PHASE 25 — Training observation (PART 37)
After normal training, observe staff WITHOUT developer guidance. Record task,
operator, "succeeded without help?", confusion, workaround, severity. **Do not code
subjective preferences automatically** — classify severity first.

## PHASE 26 — Live/simulated shift (PART 38) — recommended min 4 h (record exact)
Workload (adjust to sold profile): 30+ counter, 15+ dine-in, 10+ QR additions,
5+ pickup, 5+ delivery. During the shift also execute: product 86, table transfer,
table safe merge, **paid-merge BLOCK**, courses, manager discount/approval, refund,
reprint.

## PHASE 27 — Session close (PART 39)
Close via the production UI. **No SQL, no developer DB correction.** Capture result.

## PHASE 28 — Financial reconciliation (PART 40) — ⛔ HARD GATE
Reconcile: order totals, Cash, Manual Card, Wallet/Transfer, mixed tender, refunds,
COD, Customer Account, delivery fees, online provider (if tested). Record expected /
actual / difference / explanation. **UNEXPLAINED DIFFERENCE = 0.** Any nonzero
unexplained → **COMMERCIAL SIGNOFF = FAIL**.

## PHASE 29 — Cash physical count (PART 41) — if a real drawer is used
Count physically; compare to system expectation. **Do not edit historical payments
to force a match.** Record legitimate variance separately.

## PHASE 30 — Database integrity (PART 42)
Run the approved integrity/reconciliation tooling against the pilot DB (see
`software-preflight.md` for the query set). Required all-zero: overpaid orders,
orphan payments, refund-ceiling breach, orphan KDS, stuck critical outbox,
unexplained financial mismatch.

## PHASE 31 — Backup (PART 43)
After the shift, back up PostgreSQL + filestore. Record start, finish, duration, size.

## PHASE 32 — Restore (PART 44)
Restore to a separate clean target. Verify login, cashier, orders, payments,
receipts/files, KDS, customer ordering, delivery, validator. Record restore
duration + **order loss = 0, payment loss = 0, filestore loss = 0** + RTO.

## PHASE 33 — Support drill (PART 45)
A reviewer WITHOUT DB credentials injects one safe issue (printer offline / delivery
config invalid / external provider disabled), generates a support bundle, and
diagnoses from it. Record issue, bundle generated, diagnosis, time/steps,
**credentials exposed? (must be NO)**.

## PHASE 34 — Security (PART 46)
```
☐ HTTPS  ☐ no default password  ☐ DB manager secured  ☐ debug hidden
☐ demo disabled  ☐ PostgreSQL not needlessly public  ☐ support-bundle secrets = 0
☐ customer IDOR smoke  ☐ public status tokens scoped
```

## PHASE 35 — Performance observation (PART 47)
Record REAL observed latency for cashier interaction, KDS arrival, printer, QR
submit, delivery dashboard as `acceptable / slow / blocking` (+ approx measured).
**Do not invent benchmark numbers.**

## PHASE 36 — Resource snapshot (PART 48)
Before/during/after the shift record CPU, RAM, disk, DB size, filestore size, Odoo
workers, outbox/backlog. Operational evidence, not marketing.

---

## Defects, severity, and the RC patch rule

- Log every issue with `defects/DEFECT-TEMPLATE.md`.
- **CRITICAL** (money incorrect / duplicate charge / lost paid order / data
  corruption / security breach / unrecoverable) → **STOP PILOT**.
- **MAJOR** (core workflow blocked / real hardware unusable / repeated staff blocker
  / Arabic-tablet unusable / reconciliation mismatch) → **FIX BEFORE SELLING the
  affected profile**.
- **MINOR** (cosmetic / non-blocking) → defer.
- **If a code defect is found (PART 51):** DO NOT change `mezze-v1.0-rc1`.
  `reproduce → narrow fix → tests → full regression → retest the affected physical
  gate → new annotated mezze-v1.0-rc2`. No tag moves.

---

## Exit criteria & signoff

- **Cloud Base (PART 53):** real hosted deploy, cashier, tablet, KDS, printer,
  customer phone, staff UAT, 4h+ shift, session close, **financial diff 0**,
  backup/restore, security, support drill, 0 Critical, 0 unresolved financial Major.
- **Edge Base (PART 54):** all of Cloud + Host A, Host B, reboot, LAN, WAN 5m/30m/2h,
  reconnect, worker failure, UPS/power, Edge backup/restore.
- Record per-profile verdicts (GO / CONDITIONAL GO / NO-GO / NOT INCLUDED) in
  `signoff.md`, and collect the four named signoffs (Technical, Operations,
  Finance/Reconciliation, Restaurant Manager). **No blank signature counts as PASS.**
- **Final tag:** create `mezze-v1.0` only after the required base profiles physically
  PASS (PART 66) — on the passing RC commit, never by moving an RC.
