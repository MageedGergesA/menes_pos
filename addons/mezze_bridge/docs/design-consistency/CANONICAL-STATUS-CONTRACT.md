# CANONICAL-STATUS-CONTRACT (DESIGN-P3B)

ONE semantic state language. Business states map to a SMALL semantic set — never a unique
colour per business state. Status is **never colour-only**: it always carries a text label;
icon / leading dot / border-shape reinforce. **Brand (terracotta) is NOT a status colour.**

## Canonical source
`static/design/components.css` — `.mz-status` (operational status) + `.mz-badge` (quiet metadata).
Consumes `--mz-` semantic tokens (`--mz-ok/-soft`, `--mz-warn/-soft`, `--mz-danger/-soft`,
`--mz-info/-soft`, `--mz-text-mut`, `--mz-surface-2`, `--mz-border-strong`) with hex fallbacks so
it renders on every surface. Text colour is mixed toward `--mz-text` (dark ink in light / light
ink in dark) so labels stay **WCAG-AA (≥4.5:1)** on the light-tint soft backgrounds in BOTH themes.

## Semantic variants (9)
| Variant | Meaning | Colour family | Reinforcement beyond colour |
|---|---|---|---|
| `neutral` | inert / metadata-ish state | muted grey on surface-2 | text |
| `info` | informational | info (teal-blue) | text (+ optional dot) |
| `active` | in-progress / live | info + **pulsing dot** | text + animated dot |
| `success` | done / ok / paid / ready | ok (green) | text (+ dot) |
| `warning` | needs attention / late | warn (amber) | text (+ dot) |
| `paused` | intentionally halted | warn (amber) | text + **pause** semantics/icon |
| `danger` | failed / cancelled / error | danger (red) | text (+ dot) |
| `offline` | not reachable | muted grey + **strong border** | text + border |
| `not-tested` | never run / unknown | muted grey + **DASHED border** | text + dashed shape → unmistakably NOT pass/fail |

Sizes: `--sm` (admin/compact) · default (customer) · `--lg` (KDS / far-read). `--pill` = full-round.

## Brand ≠ status (item 10)
The prototype's old `.status-badge--accent` (terracotta) is **removed** from the status language.
Terracotta remains BRAND only. No state maps to accent unless the original source explicitly does
(none do). Selected/active-tab uses stay in the Tabs/Segmented family (P3I), not status.

## Status vs Badge vs Chip (classification — items 5, 12, 13)
- **`.mz-status`** — operational state (order/table/KDS/payment/delivery/connectivity/go-live).
- **`.mz-badge`** — quiet METADATA (channel / course / role / category / "optional"): fw 600, muted,
  NO semantic urgency colour. A badge is not automatically a pill; prefer text/list hierarchy.
- **chips / filters / segmented / selectable modifier cards / tabs** — NOT status → **Tabs/Segmented
  (P3I)**. **Alerts** → **P3C**. **`.st-*` card border/opacity modifiers** → **Card (P3G)**.

## Live-region restraint (items 23, 24)
`role="status"` / `aria-live="polite"` ONLY on dynamic status MESSAGES that update and should be
announced (e.g. Go-Live overall summary, payment result, connectivity change, order submitted).
Persistent badges (Paid / Ready / role) get NO live region. Whole headers / cards / grids are
never live regions. Assertive alerts are deferred to P3C.

## Verified contrast (measured, both modes — item 26)
| Variant | Light | Dark | Required | Result |
|---|--:|--:|--:|---|
| neutral | 4.88 | 6.02 | 4.5 | PASS |
| info/active | 5.88 | 7.01 | 4.5 | PASS |
| success | 5.64 | 6.64 | 4.5 | PASS |
| warning/paused | 5.67 | 9.09 | 4.5 | PASS |
| danger | 5.61 | 6.67 | 4.5 | PASS |
| offline | 4.88 | 6.02 | 4.5 | PASS |
| not-tested | 5.18 | 8.03 | 4.5 | PASS |
