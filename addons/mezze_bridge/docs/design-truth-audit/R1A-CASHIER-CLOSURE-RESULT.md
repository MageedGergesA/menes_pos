# R1A — REAL CASHIER DESIGN COMPLIANCE CLOSURE — RESULT

Scope: bring the REAL production cashier `/mezze/pos` (Owl, `static/src/cashier/`) into compliance with the original Mezze design authority. **CSS-only + one runtime design-acceptance test.** No business logic, no new features, no KDS change, `/mezze/design/pos` untouched (reference only).

- **R1A_START_COMMIT** = `483b3e4` (after committing the design-truth audit).
- Files changed: `static/src/cashier/cashier.css` (compliance edits), `tests/test_cashier_browser.py` (+1 design-acceptance test). **Zero production JS/template/logic change.**

## What changed (measured before → after)
| Metric | Before | After |
|---|---|---|
| Smallest high-frequency touch target | **36px** (qty stepper) | **44px** (qty, category, remove all ≥44) |
| Category tab height | ~38px | **44px** (min-height) |
| Line-remove control | unsized text button | **44×44px** |
| `--mz-space-*` spacing primitives | **0** | **131** |
| Raw px values | 267 | **131** (all remaining = dimensions/borders/font-size/icon geometry) |
| Local `--radius` vocabulary | 1 (`--radius:14px;--radius-sm:10px`) | **0** (removed) |
| `--mz-radius-*` references | 1 | **22** |
| Money numeric font (`--mz-font-num`/JetBrains Mono, tabular) | 0 | **applied to money + quantities** |
| Cashier `.mz-btn` base blocks | 1 (duplicate) | **0** — single canonical base (`components.css`) |
| Focus-visible on bespoke controls | partial | tile/method/quick/cust-row/cat/qty/remove all have it |

Charge/Confirm keep the terracotta "primary action" fill as an explicit context override (money hierarchy unchanged — no regression); width/size/min-height now come from canonical.

## Runtime acceptance (real browser, `test_09_r1a_design_compliance`, PASS)
Measured on the REAL `/mezze/pos` in headless Chrome at HEAD: qty ≥44×44, remove ≥44×44, category ≥44 tall, money font matches `jetbrains|mono`, charge on canonical base (min-height ≥44), qty stepper focusable. Also rendered live in Light / Dark (real `#191510`/`#D89A54` registry) / Arabic-RTL (mirrored, money LTR-isolated + mono).

## Test results (HEAD after R1A)
- **Backend (fresh install, `mezze_runtime,mezze_invariants,mezze_browser,mezze_hoot`): 430 / 0 / 0, exit 0.**
- **HOOT: 22 / 0** (70 assertions).
- **Cashier browser: 9 / 0** (8 existing + 1 new design-acceptance).
- **KDS browser: 11 / 0** (untouched).
- **Upgrade (`-u`) + cashier smoke: 418 / 0 / 0**, no stale assets.
- Console errors: 0 in all passing browser tests.

## Compliance re-score (same dimensions as the audit)
- **Cashier `/mezze/pos`: ~68% → ~90%.** P0 0→0 · **P1 3→0** · P2 3→2 (remaining P2 = bespoke Input/Dialog/Card families = P3D/F/G, explicitly deferred cross-surface; + inline-SVG icon system).
- **Design System Coherence: ~62% → ~65%** (cashier spacing/token/component/touch adoption up; other surfaces unchanged).
- **UI/UX Product Readiness: ~52% → ~55%** (cashier UX dimension up; other screens unchanged).

The residual ~10% cashier gap is the canonical component families (Input/Dialog/Card — P3D/F/G) and the icon library — both cross-surface R2/R3 work explicitly OUT of R1A, not cashier-specific defects.

## Confirmations
Only `/mezze/pos` treated as production; `/mezze/design/pos` reference-only; KDS not touched; no new cashier business features; qty/category/remove ≥44px; JetBrains Mono on money/numeric; one canonical `.mz-btn` base; spacing migrated to `--mz-space-*`; radius on the 8/11/14/16 scale; money hierarchy not regressed (charge stays terracotta); Arabic used real `ar_001`; dark used the real theme engine; HC uses the real Mezze app theme; no new hardcoded theme system; RC1/2/3 unmoved; no new RC.
