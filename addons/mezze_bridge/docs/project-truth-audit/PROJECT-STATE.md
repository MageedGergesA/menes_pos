# MEZZE — PROJECT STATE (single source of truth, forensic audit)

**Audit date:** 2026-08-05 · **Auditor mode:** read-only, no product changes · **Confidence:** MEDIUM-HIGH
(git/code/tests HIGH; runtime browser MEDIUM — no automated browser evidence exists; physical LOW — 0% executed).

> **V1 + V2A UPDATE (2026-08-05, see `V1-VERIFICATION-ADDENDUM.md`):** authenticated browser regression on
> the REAL Owl cashier (`HttpCase.browser_js(login=...)`) now covers **7 flows** — mount, cash, double-submit,
> **mixed tender, Arabic/RTL, dark, High-Contrast** — 7/7 PASS on fresh install AND upgrade (combined
> **412/0/0**). V1 fixed a real boot bug (`/bootstrap readonly=False`); **V2A completed the shipped cashier**:
> dark + HC wired to the real theme contract (mezze-design.css + early-paint), fonts deduped to canonical
> `--mz-font-*`, `.mz-btn` 44px restored. (RTL was already wired — a V1 over-statement, now corrected.)
> Revised scores: **Software Verification 60→74%**, **Design Readiness 42→48%**, **Cloud Sell-Readiness
> 40→47%**; Edge physical 0% (unchanged). KDS still has no UI; cashier refund has no UI (backend-tested).
> V2A closure added customer-account + canonical connectivity/status + a HOOT invariant (8/8 browser, 413/0/0).

## 1–4. Repository / release / git
- Repo `/home/mageed/odoo_work_19/mezze`, branch `main`. **HEAD = origin/main = `5ec05b1`**, tree CLEAN, divergence 0/0.
- Module version **19.0.2.0.0** (`__manifest__.py`). Runtime product version **1.0.0-rc.1** (productization.py:16). Edge pack base **19.0.1.9.0** (older). → 3 version identifiers (drift).
- 8 tags, all identical local↔remote, none moved (see GIT-RELEASE-TRUTH). **Latest certified product RC = `mezze-v1.0-rc3` → fb59c79.** Latest pilot RC = `mezze-pilot-rc3` → 8ad8ed9.

## 5. HEAD vs certified RC
HEAD is **12 commits past rc3**, and ALL 12 are **design (P3A Buttons + P3B Status) + docs + 3 structural tests** — no functional/payment/model change since rc3. **The certified FUNCTIONAL product == rc3;** HEAD adds only *uncertified, prototype-scoped* design migration.

## 6. Architecture
Managed custom-code Odoo deployment (custom Python controllers/models + `cryptography` dep) → **NOT Odoo Online SaaS**; runs on Odoo.sh / self-hosted (Cloud) or on-prem (Edge). Cashier = standalone **Owl** app at `/mezze/pos` (auth='user'). Customer fronts = static HTML + JSON API (tokenized, server-authoritative pricing). **`static/pos.html` = visual reference PROTOTYPE at `/mezze/design/pos`, NOT the shipped cashier.**

## 7. Capability matrix (impl ≠ cert) — see CAPABILITY-MATRIX
Core POS, restaurant ops, reservations/waitlist, QR/shop/pickup, delivery(+COD), aggregator ingest, drive-thru — all **IMPLEMENTED**. No whole capability missing.

## 8. Payments — see CAPABILITY-MATRIX
Cash/manual/mixed/partial/refund/online(**Demo only**)/customer-account/credit-governance = implemented + server-tested. Integrated terminal / cash machine / bank-QR = **software-orchestration only, real hardware/bank refused (PENDING)**. **Paymob wired, never executed.** Wallet acquirer driver = TODO stub. Egypt/InstaPay QR = NOT certified.

## 9. Online / Cloud
Software ~90% (all surfaces implemented, money delegated to native). Verification ~55% (Demo online-pay/delivery/self-order/bank-QR/aggregator-HMAC tested; **no browser E2E, no live Paymob, no real aggregator**). Sell-ready ~40%.

## 10. Edge / Offline — see PHYSICAL-CERTIFICATION-TRUTH
Deploy pack complete + self-tested (~85% software, ~80% artifacts) but **physical certification = 0% executed** (module's own report: "NOT SELL-READY"). Edge sell-ready ~15%. Certified OS = Ubuntu 24.04.

## 11. Security / integrity
Comprehensive + tested (auth gate default enforce, branch/company scope, route-scope, endpoint coverage, HMAC signing, nonce/replay, idempotency, outbox, refund ceiling, redaction leakage=0, AES-256-GCM at rest, rate limit, append-only audit). **One honest gap:** object-scope wiring covers money+hardware+session-close; other Category-A routes authn+capability gated but not object-scoped ("wiring pending").

## 12. Testing — see TEST-TRUTH
**405/0/0 fresh install + 405/0/0 upgrade (re-verified this audit, exit 0).** Settings catalog 101 (18 working/76 disabled/7 hidden). **NO executed frontend/browser test exists** — all green is server-side Python + source-grep structural. Authenticated-browser evidence = MISSING. Production Owl cashier is not exercised by any rendering test.

## 13. Design — see DESIGN-TRUTH
Foundation + canonical `.mz-btn` + 9-variant `.mz-status` language are real. **But P3A = PARTIAL** (3 legacy button pages + a 2nd drifted `.mz-btn` base in the production cashier) and **P3B = PARTIAL** (prototype/customer migrated; production cashier on its own token-aligned status system; card borders → P3G; `.mz-badge` unadopted; 2 legacy conn palettes; kiosk+onboarding have no theme engine → no dark/HC). **P3C–P3I NOT STARTED.** HC app theme = YES; prefers-contrast/forced-colors = NO. **9 shipped HTML surfaces** (not 11) + the Owl cashier.

## 14. Browser (this audit)
OPENED & rendered (prototype/static, offline): pos.html(floor/delivery/reservations/settings/KDS/HC — this session), shop, onboarding, kiosk. All render on the design foundation; data surfaces show correct "needs backend token" states. **Production Owl cashier `/mezze/pos`: NOT OPENED (auth-gated; no synthetic-login browser path exists).** No surface BROKEN.

## 15. Physical / external — see PHYSICAL-CERTIFICATION-TRUTH
Everything NOT EXECUTED (0%): terminals, cash machines, printer, drawer, tablet, KDS hardware, WAN outage, reboot, staff UAT, shift, backup/restore-on-host, live Paymob.

## 16. Disabled / deferred
Deferred: P3G card borders, P3I filters, P3C–P3I families. Simulator-only (real refused): integrated terminal, cash machine. Wired-not-run: Paymob. TODO: wallet acquirer driver, aggregator per-partner shim. NOT certified: Egypt InstaPay QR. 76/101 settings = disabled/"not available yet".

## 17. Readiness percentages (fixed model)
| Category (weight) | Score | Evidence |
|---|---|---|
| Core transaction engine (15) | 92 | all core flows implemented + tested |
| Restaurant operations (12) | 90 | floors/reservations/waitlist/courses/KDS/drive-thru |
| Payments (13) | 85 (impl) | broad; several external-cert-pending |
| Omnichannel/customer (10) | 90 | QR/shop/kiosk/pickup/self-order |
| Delivery (7) | 92 | full + COD, tested |
| Edge/offline software (8) | 85 | deploy pack complete |
| Security/integrity (8) | 90 | comprehensive + tested (scope gap) |
| Admin/settings/productization (7) | 87 | productization strong; 76% settings disabled |
| Design/UX (10) | 42 | P3A/P3B partial; P3C–P3I not started |
| Testing/installability (10) | 78 | 405/0/0 + upgrade; no browser/physical |
| **SOFTWARE IMPLEMENTATION** | **≈83%** | weighted |
| **SOFTWARE VERIFICATION** | **≈60%** | server-side strong; no browser/frontend/external/production-cashier |
| **DESIGN READINESS** | **≈42%** | foundation+buttons partial; 7 families absent |
| **CLOUD SELL READINESS** | **≈40%** | blocked: live PSP, managed-host rehearsal, browser/UAT |
| **EDGE SELL READINESS** | **≈15%** | blocked: 0% physical certification |
| **OVERALL SELL READINESS** | **≈40%** | hard-gate capped (below) |

## 18. Commercial verdict (hard-gate logic — average must not hide a blocker)
- **Demo / Pre-Sales: GO** — software works, renders, honest positioning/known-limitations docs exist.
- **Controlled Pilot: CONDITIONAL** — a supervised **Cloud** pilot with cash/manual/customer-account (no live online payment, no hardware dependency) is feasible; an **Edge** pilot is NOT until the clean-host install + basic hardware run is executed.
- **Cloud Production Sale: CONDITIONAL** — needs live PSP cert (if selling online payments), managed-hosting rehearsal + HTTPS, and at least one executed browser/UAT of the real cashier.
- **Edge Production Sale: NO-GO** — physical certification 0%; the module's own report says NOT SELL-READY.
- **100% Product-Ready claim: NO** — P3A/P3B partial, P3C–P3I not started, 0% physical cert, no browser tests, external certs pending.

## 19. Remaining blockers — see REMAINING-TO-100
P0: Edge physical cert; live PSP cert; managed-hosting rehearsal; executed browser/UAT.

## 20. Do-not-touch (already adequate — change only on a real defect)
Payment/money invariants + refund ceiling; idempotency/tender-key; auth gate + signing + nonce/replay; transactional outbox; secret/bundle redaction (leakage=0) + crypto-at-rest; canonical `.mz-btn`/`.mz-status` component definitions; foundation tokens/fonts; productization (release-identity/version/support-bundle/onboarding/neutralize); the 405-test server-side suite. **These are the strongest, most-tested parts — do not re-architect.**

## 21. Known conflicts — see STALE-DOCS-AND-CONFLICTS
403(stale, real 405); "no HC" (P3B.4 wrong); 22.04 vs 24.04; S6 pins rc1 vs rc3/HEAD; "browser-verified" vs no browser test; P3A "COMPLETE" vs PARTIAL; 3 version strings.

## 22. Next recommended phase (ONE — do not auto-start)
**Reconcile-then-certify:** (a) adopt this audit as the baseline + fix the stale-docs single-sources (SMALL); then (b) the highest-value *new* work is **executed verification of the real product** — an S6-style **clean-host Edge bring-up + a first authenticated browser/UAT run of the Owl cashier** — because software implementation is already ~83% but verification/physical is the true gap. Design P3 continuation is P2 (not a sell-blocker).

---
**Audit integrity:** production code NOT modified; nothing committed, tagged, or pushed; no RC moved. Only untracked docs under `docs/project-truth-audit/`.
