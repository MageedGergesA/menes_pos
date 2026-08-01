# Mezze Edge v1.0 — S1 Certification Report

> **VERDICT: NOT SELL-READY — engineering-preparation pass only.** S1 sell-ready certification requires
> physical Edge hardware (server, ESC/POS printer, cash drawer, tablet, KDS device, cashier station, UPS,
> router) and a live on-site run. This pass was performed on the developer laptop `mageed-Latitude-5501`
> with **no such hardware attached**. Every physical/on-hardware gate below is **NOT EXECUTED** — none is
> marked PASS. Automated tests alone cannot pass S1 (spec §35).

## Release & environment (verified, real)
- Software base: `mezze-pilot-rc3` → **`8ad8ed90c116b57a1c3e66b5323c5e3a9807d0a0`** (unmoved). Module 19.0.1.9.0.
- Host: dev laptop (not Edge hardware); Odoo 19.0; PostgreSQL 14.23; Python 3.10.12. Supported baseline OS
  target: Ubuntu Server 22.04 LTS.
- Hardware present: **none** (`/dev/usb/lp*`, `/dev/ttyUSB*` absent — no printer/drawer/serial).

## Engineering preparation delivered this pass (docs only; RC3 code untouched)
- `readiness-matrix.md` — 32 Edge concerns classified (software Ready; deployment mostly Missing/Partial; hardware not certified).
- `wan-capability-matrix.md` — per-feature WAN-outage behavior (design contract for the §19 test).
- `../hardware/HCL.md` — hardware classification template, **no CERTIFIED rows** (Bluetooth printers excluded).
- `PRODUCT.md` — editions, v1 boundary, WAN status model (§8), network topology (§5), HTTPS strategy (§6), marketing-claims boundary (§33).
- `offline-behavior.md` — WAN vs LAN vs server vs power outage distinctions (§32).
- `installation.md` — deployment/installer approach (§2–3), parameterized, no dev paths; installer script not yet built.
- `certification/` — 21 evidence slots, all **NOT EXECUTED**.

## Gate status
| # | Gate | Status |
|---|------|--------|
| Installer / clean install (§3/§28) | **NOT EXECUTED** — installer not built; needs clean host/VM |
| Automatic startup / recovery (§7/§21/§22) | **NOT EXECUTED** — systemd units not packaged; needs Edge host |
| HTTPS / reverse proxy (§6) | **NOT EXECUTED** — proxy/cert artifacts not built |
| Edge validator 0 FAIL (§25) | **PARTIAL** — RC3 go-live validator exists (settings_catalog PASS on fresh install); Edge profile not added |
| Receipt printer (§11) | **NOT EXECUTED** — no printer |
| Cash drawer (§12) | **NOT EXECUTED** — no drawer |
| Waiter tablet 1024×768 + Arabic RTL (§13) | **NOT EXECUTED** — no tablet |
| KDS on device (§14) | **NOT EXECUTED** — no KDS device |
| Cashier hardware (§15) | **NOT EXECUTED** — no station |
| QR on LAN during WAN outage (§16) | **NOT EXECUTED** — undecided/uncertified → currently *NOT SUPPORTED IN EDGE v1* until certified |
| Local backup / offsite backup (§17) | **NOT EXECUTED** on Edge (pg_dump proven in RC1; two-tier Edge script pending) |
| Restore (§18) | **NOT EXECUTED** on Edge (restore proven 0-loss in RC1; re-verify on hardware) |
| WAN 5-min / 30-min / 2-hour outage (§19) | **NOT EXECUTED** — no Edge deployment / no WAN to physically cut |
| WAN reconnection invariants (§20) | **NOT EXECUTED** on hardware (idempotency proven at logic level in suite) |
| LAN / Edge-server failure (§21) | **NOT EXECUTED** |
| Power failure recovery (§22) | **NOT EXECUTED** (PostgreSQL crash-safe by design) |
| UPS (§23) | **NOT EXECUTED** — recommendation documented only |
| Local performance over LAN (§24) | **NOT MEASURED** — no LAN/hardware |
| Support bundle (§26) | **NOT BUILT** (design noted; production-code item) |
| Staff UAT (§30) | **NOT EXECUTED** — no representative staff |
| 2–4h shift simulation (§31) | **NOT EXECUTED** — 0 hours |
| Session close + financial reconciliation (§35) | **NOT EXECUTED** — no live session |

## Software-level proofs that already exist (NOT a substitute for physical gates)
RC3: 229 automated tests 0 failed/0 error; fresh-install catalog 101/18/76/7; reconciliation 0 (294 genuine
orders); backup/restore 0 row loss; idempotency (lost-response→1 payment, duplicate QR/aggregator→1 order),
safe-merge blocking, multi-worker no-double-effect. These prove the *logic*; they do not prove a real
printer, drawer, tablet, LAN, WAN cut, or a staffed shift.

## Defects
- Critical: **0** · financial Major: **0** (no new software defects found this pass).

## Release impact
**No production code changed.** RC3 remains the software base. **No `mezze-edge-rc1` created** — an Edge
release requires the deployment artifacts to be built AND the physical gates certified, neither of which
this hardware-less pass can complete.

## Sell-ready percentage
**Not quantified as a pass.** Software/logic base: substantially ready (RC3 green). Deployment packaging:
started (design/docs), largely unbuilt. Physical certification: **0% executed.** Mezze Edge v1.0 is
**NOT 100% sell-ready**; it is at the engineering-preparation boundary.

## Next actions (to resume S1 with hardware)
1. Build deployment artifacts: installer, systemd units, nginx+HTTPS, logrotate, two-tier backup, Edge
   validator profile, support bundle, WAN status model → cut `mezze-edge-rc1` (immutable) after full
   automated re-acceptance.
2. Procure/assign reference hardware per HCL and run §11–§31 on real Edge hardware, recording evidence in
   `certification/`.
3. Complete the 2-hour WAN outage (mandatory) + reconnect invariants + shift + session close + financial
   reconciliation (= 0), then declare sell-ready only if all mandatory gates pass.
