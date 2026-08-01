# P2 — On-Site Hardware Acceptance & Controlled Pilot Certification — STATUS

> **This phase is NOT complete and the controlled pilot is NOT certified by this session.**
> P2 requires executing physical-hardware and human gates (real waiter tablet, ESC/POS receipt
> printer, cash drawer, customer phones, representative restaurant staff, a live 2–4h service
> shift). This work was attempted on a **hardware-less development host** (`mageed-Latitude-5501`)
> with no printer, no drawer, no tablet, no phones, and no restaurant staff. Those gates therefore
> **could not be executed** and are left **unmarked** (not passed, not failed) in the checklists and
> the subdirectories under this folder. Nothing here is pre-marked passed.

## What WAS verified this session (real, reproducible)

### 1. Release identity (DoD: RC3 identity verified) — CONFIRMED
- Tag `mezze-pilot-rc3` → commit **`8ad8ed90c116b57a1c3e66b5323c5e3a9807d0a0`** (matches the required
  `8ad8ed9`). RC3 was **not** moved, recreated, or retagged. RC1 `634d17e` / RC2 `13276b9` unchanged.

### 2. Environment (partial — dev host, NOT a pilot deployment)
| Field | Value |
|---|---|
| Release tag / commit | `mezze-pilot-rc3` / `8ad8ed9` |
| Host | `mageed-Latitude-5501` (developer laptop — **not** a pilot server) |
| OS | Linux 6.8.0-124-generic |
| Odoo | 19.0 | Python 3.10.12 | PostgreSQL 14.23 |
| Reverse proxy / workers / branch / register | **N/A here** — to be recorded on the pilot host |
| Printer / drawer / tablet / KDS device / phones | **NONE attached** (`/dev/usb/lp*`, `/dev/ttyUSB*` absent) |

### 3. Disabled-feature gate (DoD: features disabled through code/config) — CONFIRMED in RC3 code
- **Online card checkout** — genuinely **ABSENT**: no PSP / hosted-payment / card-checkout route exists
  (grep of `controllers/`), so it cannot be reached.
- **Drive-thru (D-1)** — present in code but all three `/drivethru/*` handlers are `self._authorize()`-gated
  (authenticated terminal only, not public). Remains **disabled for the pilot** by not provisioning a
  drive-thru client; must **not** be enabled. Not a public/navigation path.
- **Durable seat-level line identity / true split-by-seat** — genuinely **ABSENT**: not modelled
  (grep of `models/`).
- Unverified aggregators / payment providers, unsupported public cancellation, experimental settings —
  not provisioned; kept inactive.

## What CANNOT be executed on this host (must be done on-site — currently UNMARKED)
Tablet acceptance (§4) · Arabic RTL on a real tablet (§4/§6) · cashier workstation (§5) · **receipt
printer** (§6/§21) · **cash drawer** (§7) · KDS on a physical display (§8) · KDS disconnect/reconnect (§9) ·
waiter-tablet disconnect/reconnect (§10) · the live multi-client loop with real devices (§11) · customer QR
on a real phone (§13) · pickup/delivery on real customer devices (§14/§15) · aggregator against the approved
pilot integration (§16) · **worker-kill during live service** (§20) · **manager approvals by real human
principals on-site** (§22) · **staff UAT with representative restaurant staff** (§23) · the **2–4h shift
simulation** (§24) · end-of-shift drawer reconciliation (§25) · real POS session close (§26) · observed
on-device latency (§27).

None of these may be marked passed without the physical devices and people. The checklists in this folder
(`tablet-checklist.md`, `hardware-checklist.md`, `financial-checklist.md`, `service-loop-checklist.md`,
`failure-recovery-checklist.md`, `signoff.md`, `environment-sheet.md`) are the instruments to record them
on site. The subdirectories (`tablet/`, `cashier/`, `kds/`, `printer/`, `drawer/`, `qr/`, `pickup/`,
`delivery/`, `aggregator/`, `failures/`, `staff-uat/`, `shift-simulation/`, `financial/`, `session-close/`,
`photos/`, `final/`, `devices/`) are the evidence slots — all currently **awaiting execution**.

## Software-level proofs that already exist — and what they do NOT prove
The RC3 automated suite (229 tests) + prior multi-worker concurrency runs establish the *logic-level*
invariants that the on-site gates will exercise physically:
- idempotency (lost-response → one payment; duplicate QR / aggregator callback → one order),
- financially-safe merge blocking (paid/partial/refund → 409, payment rows untouched),
- multi-worker no-double-effect, outbox recovery / KDS re-delivery,
- refund ≤ sold, cancellation-via-refund-engine, secure status tokens.

**These are NOT a substitute for P2.** They prove the code behaves correctly; they do **not** prove a real
printer prints an Arabic receipt, a drawer kicks only on authorized cash, a physical tablet is usable at
1024×768 RTL, or that real staff can run a shift. P2 exists precisely to verify the physical/human layer,
which this session cannot reach.

## Verdict
- **Controlled pilot: NOT CERTIFIED by this session.** Blocked solely on execution of the on-site
  hardware/staff/shift gates above — no software defect is known to block it, and RC3 is the correct,
  verified candidate. Certification requires the on-site team to execute this pack on the pilot hardware
  and complete `signoff.md`.
- **Unrestricted public launch: NO-GO** (unchanged) — online card, broad load test, and full public
  automation remain out of scope.

No production code was changed. RC3 remains the pilot candidate; **no RC4 is warranted** (no defect found
that requires a code change). If the on-site run surfaces a Critical/Major defect, follow §29: defect →
regression test → focused fix → re-run affected gates → full suite → clean worktree → `mezze-pilot-rc4`
(never move RC3).
