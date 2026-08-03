# Mezze POS — Final Sell-Ready Readiness (S5)

_Baseline commit: `ffdb855` (S5_START_COMMIT). Module version `19.0.2.0.0`,
product `1.0.0-rc.1`._

This is the single go/no-go document. It rolls up the software product plus the two
editions. Percentages are engineering judgements against the S5 definition of done,
not marketing figures.

## 1. What S5 delivered

- **Product capability matrix** (`product/PRODUCT-CAPABILITY-MATRIX.md`) — every
  capability classified with one status word.
- **Two editions** (`product/EDITIONS.md`) — Mezze Cloud (managed custom hosting)
  and Mezze Edge (branch-local, survives WAN outage) + Cloud-vs-Edge matrix.
- **Version/release identity** (`product/VERSIONING.md`, `/admin/version`) —
  product/module/Odoo/commit/edition/mode/channel; MAJOR.MINOR.PATCH policy;
  stable/rc/dev channels.
- **Go-Live readiness + commercial profiles** (`product/READINESS-PROFILES.md`,
  `/admin/golive`) — counter/restaurant/restaurant_qr/delivery/full/edge; strict
  FAIL/WARNING/NOT TESTED/PASS/NA policy; NOT TESTED never becomes PASS.
- **First-run onboarding** (`product/ONBOARDING.md`, `mezze.onboarding`,
  operator console) — reuses Odoo models, resumable, idempotent, completion derived
  from the validator.
- **Support bundle + redaction** (`product/SUPPORT-DIAGNOSTICS.md`,
  `/admin/support_bundle`) — leakage=0 (tested); no DB dump/orders/PII; plus
  `/admin/audit/export`.
- **Staging neutralization** (`data/neutralize.sql`, `is_neutralized()`) — honored
  by the validator; production+neutralized = FAIL.
- **Explicit demo restaurant** (`demo/README.md`) — never auto-loaded; demo-in-
  production = FAIL.
- **Backup/restore + update + installers** (`product/UPDATE-PROCESS.md`,
  `product/INSTALLERS.md`, `deploy/edge/*`) — executable, backup-gated, RTO≈14s.
- **Customer documentation set** (`docs/customer/*`) — getting-started, role guides,
  troubleshooting, HCL, payment capabilities, known limitations, privacy, security
  baseline, UAT.

## 2. Test evidence

- Full `mezze_bridge` suite on a **fresh `--without-demo=all`** DB (factory-empty,
  production onboarding path): **403 tests, 0 failed, 0 errors**.
- **Upgrade acceptance:** a pre-S5 database upgraded (`-u mezze_bridge`) to the S5
  code: **14/0/0**. S5 adds **no new stored models** (release-identity, onboarding,
  and productization are AbstractModels), so the upgrade is pure code — no schema
  migration risk.
- New S5 tests (`test_productization.py`): redaction **leakage=0** (synthetic
  secrets + PII planted, none survive), release identity, commercial profiles
  (delivery-requires-zone → FAIL; NOT TESTED never upgraded), support-bundle safety
  (no orders/PII/secrets), onboarding derived/idempotent, neutralized + demo
  production guards, `/admin/*` route smoke.
- **Secret scan:** covered by `TestRedaction` + `TestSupportBundle` (in the 403).
- Structural governance: `TestEndpointCoverage`, `TestRouteScope` pass — the 6 new
  `/admin/*` endpoints are registered in `domain/authz` + `domain/route_scope`.

## 3. Readiness verdicts

| Track | Readiness | Verdict |
|---|---|---|
| **Software product** | ~95% | **GO** — software-complete, 403/0/0, fresh-install + upgrade proven. Remaining 5% is physical/external certification, which is out of software scope. |
| **Mezze Cloud** (sell-ready) | ~85% | **CONDITIONAL GO** — software ready; conditioned on live external-payment certification (Paymob) and one managed-hosting provisioning rehearsal. |
| **Mezze Edge** (sell-ready) | ~80% | **CONDITIONAL GO** — software ready; conditioned on the S6 two-host clean-install certification and physical hardware (printer/drawer/terminal) sign-off. |

Cloud and Edge sell-readiness are gated on items outside pure software:
- Edge two-host clean-install certification — **PENDING** (S6 pilot).
- Physical hardware (printer/drawer/terminal/cash machine/kiosk) — **PHYSICAL CERT
  PENDING** (S6 pilot).
- Paymob live + bank-QR (Egypt/InstaPay) — **EXTERNAL CERT PENDING** (needs live
  credentials).

## 4. Intentional Deferred-V2 list (small, named)

- True split-by-seat identity (split by amount/line ships).
- Explicit modifier min/max beyond single-select.
- Per-channel product availability (branch-global 86 ships).
- Table-QR combo picker UI parity (server + storefront already support combos).
- Real-time cross-branch Edge customer credit.

## 5. After S5

Next is **S6 — physical pilot** (hardware + on-site certification), **not** new
software platforms. Do not add another restaurant feature category.
