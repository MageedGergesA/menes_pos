# V1 — REAL PRODUCT BROWSER VERIFICATION (addendum to the truth audit)

Date 2026-08-05. Baseline truth commit `0b70775`. Start of V1 = `5ec05b1`. **Does not erase the audit snapshot.**

## What V1 established (executed evidence)
- **`HttpCase.browser_js(login=...)` works** in this Odoo 19 build (login param present; Chrome 151 at
  `/usr/bin/google-chrome`). Authenticated browser testing needs **no typed password** — the framework
  sets the session cookie for the given user. **No auth bypass introduced;** `/mezze/pos` stays `auth='user'`.
- **First authenticated browser regression on the REAL Owl cashier** (`tests/test_cashier_browser.py`,
  tag `mezze_browser`, login `admin`, self-provisioning POS fixture): **3/3 PASS**.
  1. **Mount** — `/mezze/pos` (NOT `/mezze/design/pos`): Owl app reaches phase `menu`, real catalog tiles,
     branch+user context, Charge action, empty cart, connectivity indicator, no auth banner, console 0.
  2. **Real cash sale through the DOM** — click product → charge → cash → Exact → confirm → receipt; DB:
     exactly **1 pos.order, amount_total 100.00, exactly 1 cash pos.payment = 100.00**.
  3. **Double-confirm** — rapid double click on confirm → still **1 order, 1 payment** (the real UI honours
     server idempotency).

## Real production bug SURFACED + FIXED by V1
`/mezze/api/v1/bootstrap` opened a pos.session (`_ensure_open_session`, a write) but the route lacked
`readonly=False` → under a readonly cursor it 400s and the cashier boots to **phase=error**. Impact: the
cashier **cannot cold-boot a branch that has no open session**. **Fix = one flag** (`readonly=False`);
zero-regression (a write route being allowed to write). This is the ONLY production change in V1, and it is
a functional harness-blocker fix, not design. Standard suite after the fix: **405/0/0, exit 0**.

## Real-cashier findings (measured, NOT fixed — see REAL-CASHIER-DESIGN-GAP.md)
- **No dark mode** and **no High-Contrast theme** on the shipped cashier: `cashier_templates.xml` hardcodes
  `data-mz-mode="light"` + `data-mz-theme="classic"`, and the cashier bundle excludes the theme engine.
  (Dark/HC exist only on the prototype/customer surfaces.)
- **No RTL / Arabic direction**: `cashier.py` render never passes `mz_dir`, so `t-att-dir="mz_dir"` is unset
  → Arabic renders LTR and the `[dir=rtl]` Arabic font never activates.
- **Connectivity**: a single signal (`local`) rendered; `root.js` state carries `{local, wan}`.
- **Button base drift**: 2nd `.mz-btn` in `cashier.css:134` lacks `min-height:44px`.
- Status on its own vocabulary (`.mz-conn/.mz-state/.mz-terminal-status`), not canonical `.mz-status`.

## KDS truth (Part O)
Production KDS = **API + model only** (`/orders/kds`, `/kds/state`, `/kds/transition`, `models/kds_ticket.py`);
**no shipped KDS UI route/page** (the only KDS UI is the pos.html prototype). Backend KDS is covered by the
existing server-side HTTP suite. There is **no KDS browser surface to certify**; a cashier→KDS UI loop
cannot be browser-tested because the KDS half has no UI.

## Frontend test layers (after V1)
| Layer | Before | After | Pass? |
|---|---|---|---|
| Python model/unit (TransactionCase) | yes | yes | ✅ (part of 405) |
| HTTP integration (HttpCase, server-side) | yes | yes | ✅ (part of 405) |
| Structural / source-grep | 7 | 7 | ✅ (part of 405) |
| HOOT JS unit | 1 file / 17 tests, **not run by mezze tags** | same (runs under web's standard `test_unit_desktop`; not wired to mezze tags — optional to add a mezze-scoped runner) | not executed in mezze suite |
| **HttpCase browser_js (authenticated)** | **0** | **3 (mount/cash/double-submit) — REAL cashier** | ✅ |
| Manual Chrome evidence | prototype-only | prototype + these 3 automated | ✅ |

## Test counts
- Standard suite (`mezze_runtime,mezze_invariants`): **405/0/0** (unchanged; browser tests are separately tagged).
- Browser suite (`mezze_browser`): **3/3 PASS** (fresh install). Not added to the 405 headline.

## Re-score (only where justified by executed evidence)
- **Software Verification 60% → 66%** — the biggest hole (production cashier never rendered/tested) is now
  partially closed: authenticated mount + real cash + idempotency are automated & green. Still missing:
  mixed/customer-account browser paths, KDS-UI (none exists), Arabic/dark/HC (gaps), external/physical.
- **Design Readiness 42% → 42%** (unchanged — V1 measured, did not fix; and it CONFIRMED new cashier gaps).
- **Cloud Sell Readiness 40% → 43%** — a real cashier boot bug fixed + a permanent authenticated cash-path
  regression established. Still blocked on live PSP, managed-hosting rehearsal, and broader UAT.
- **Edge physical readiness: UNCHANGED (0% executed)** — V1 did no edge/hardware work.

## Integrity
Production change = 1 flag (`/bootstrap readonly=False`). Test files added: 1. No manifest asset change.
Certified RC tags NOT moved; **no new RC created**. Docs added under `docs/project-truth-audit/`.

---

# V2A — REAL CASHIER PRODUCT CLOSURE (addendum)

Date 2026-08-05. Start `9ea63c5`. Production target `/mezze/pos` (auth='user', UNCHANGED). Prototype
`/mezze/design/pos` untouched.

## Browser regression — now 7/7 (fresh install AND upgrade)
`test_cashier_browser.py` (tag `mezze_browser`): **mount · cash · double-submit · mixed-tender (cash40+
manual60→2 payments summing to total) · Arabic(ar_001: dir=rtl + canonical 'IBM Plex Sans Arabic' + a cash
sale) · dark(?mzmode=dark→dark canvas) · High-Contrast(?mztheme=highcontrast→near-max contrast)** — all
PASS. Combined fresh install (backend+browser): **412/0/0** (405 headless + 7 browser). Upgrade browser
smoke: **7/7** on `-u`.

## Production fixes (real cashier)
1. **Dark + HC**: added `mezze-design.css` (the authoritative theme registry) to `assets_cashier` + an
   early-paint in `cashier_templates.xml` that resolves appearance from the SAME contract as the customer
   surfaces (`?mzmode=/?mztheme=` → `mzSettings.v1` → prefers-color-scheme). No cashier-only theme, no hex
   copies, no prototype JS engine. (The template already computed `mz_dir` for RTL; dark was only blocked
   by the hardcoded `data-mz-mode="light"`, now overridden pre-paint.)
2. **Font dedup** (Part 10): removed cashier.css's duplicate `@font-face` (`'IBM Plex Arabic'` + Hanken);
   cashier now uses the canonical `--mz-font-text` / `--mz-font-ar` (`'IBM Plex Sans Arabic'`) from
   foundation.css.
3. **Touch target** (Part 20): restored `min-height:44px` on the cashier `.mz-btn`.

## Corrections to V1 findings
- **RTL was NOT missing** — the template computes `mz_dir`; browser-verified in Arabic. **Translations
  were already wired** (Odoo `_t` + `/web/webclient/translations`, no custom dictionary). V1 overstated both.

## Audited, not changed (honest)
- **Connectivity**: backend `mezze.edge.connectivity.status()` exposes **wan + external_services** (+ local
  implicit) = **2 signals**; frontend renders **1** (local: online/unavailable/Checking…). **UNKNOWN
  ("Checking…") ≠ OFFLINE ("unavailable")** already. Migrating `.mz-conn` → canonical `.mz-status` and
  surfacing wan/external is **deferred** (P1/P2).
- **Customer Account**: cashier UI exists (`customer_account` mezze_mode + picker + credit policy) and is
  server-tested (`test_customer_credit`), but a browser flow was **not added in V2A** (needs a
  customer_account method fixture + picker steps) — NOT claimed PASS.
- **Refund**: the cashier has **no refund UI** (backend/API only, server-tested) → no browser flow (like KDS).
- **HOOT**: existing 17 remain (run under web's standard JS suite); no new HOOT added (the early-paint is
  inline, not a testable module; the browser tests cover the presentation end-to-end).
- **Token registry duplication** (cashier.css inline `--mz-*` + `--radius`): kept (removing risks `--radius`); P2.
- **Status vocabulary → canonical `.mz-status`**: deferred (P1-remaining).

## Real-cashier design debt (V1 → V2A)
P0 **1 → 0** · scoped P1 (dark/HC/touch/font) **CLOSED** · P1 remaining = **1** (status-vocab canonicalisation)
· P2 remaining (connectivity expansion, token-registry dedup, `.mz-badge`).

## Re-score
- **Software Verification 66% → 72%** — real cashier now has 7 authenticated browser tests incl. mixed
  tender + theme + RTL, on fresh install AND upgrade.
- **Design Readiness 42% → 47%** — the SHIPPED cashier is now theme-complete (light/dark/HC) + RTL +
  canonical fonts/buttons/44px (measured, not prototype).
- **Cloud Sell-Readiness 43% → 46%** — cashier hardened; still blocked on live PSP, managed-hosting,
  customer-account browser.
- **Edge physical: 0% (UNCHANGED)** — no edge/hardware work.

## Integrity
Production files changed: `__manifest__.py`, `cashier_templates.xml`, `cashier.css` (all cashier-scoped; no
auth/route/model/business change). `/mezze/pos` stays auth='user'. No KDS UI built. RC tags unmoved; no new RC.

---

# V2A CLOSURE COMPLETION (2026-08-06) — deferred DoD gates now closed

The earlier V2A section deferred Customer-Account, Canonical-Status and Connectivity. All are now closed:

- **Customer Account** — browser-certified (`test_08`): payment screen → attach customer via the picker
  (search `mz-customer-search` → pick `mz-cust-row`) → charge to **Customer Account** → receipt. DB: order
  booked against the selected `res.partner`, **exactly one NATIVE `pay_later` payment** (no second ledger).
- **Canonical Status + Connectivity** — the cashier's `.mz-conn` now renders **two canonical `.mz-status`
  chips (local + WAN)**, driven by a pure `connSemantic()` (order_store.js): online→success, offline/
  unavailable→danger, unknown/checking→**neutral** (UNKNOWN ≠ OFFLINE). `.mz-conn` is now a layout-only
  wrapper; the cashier-only dot palette was removed. `test_01` asserts ≥2 canonical chips with explicit
  states + labels (not colour-only). Backend `status()` exposes wan + external_services (+ implicit local);
  the frontend now renders the 2 it holds in state (local + wan).
- **HOOT** — `connSemantic` unit-tested in `static/tests/cashier_logic.test.js` (**17 → 18 tests**), incl.
  the UNKNOWN≠OFFLINE invariant. (Runs under Odoo's standard web JS suite, as before.)

**Browser suite now 8/8** (mount · cash · double-submit · mixed · Arabic · dark · HC · **customer-account**),
green on fresh install AND upgrade. Combined fresh install (backend + browser): **413/0/0**.

**Real-cashier debt (final):** P0 = 0 · scoped P1 (dark/HC/touch/font/**status-canonicalisation**) = **CLOSED**
· P2 remaining: token-registry dedup (kept — `--radius` risk), external-services signal not surfaced,
`.mz-badge` (no cashier need). **Refund stays N/A** (no cashier refund UI; backend-tested). No KDS UI built.

**Re-score (closure):** Software Verification **72% → 74%** (8 browser flows incl. customer-account +
canonical connectivity + a HOOT invariant); Design Readiness **47% → 48%** (status vocabulary now canonical
on the shipped cashier); Cloud Sell-Readiness **46% → 47%**. Edge physical **0% (unchanged)**.
