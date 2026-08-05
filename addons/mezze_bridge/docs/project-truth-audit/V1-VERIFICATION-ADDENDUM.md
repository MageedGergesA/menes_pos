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
