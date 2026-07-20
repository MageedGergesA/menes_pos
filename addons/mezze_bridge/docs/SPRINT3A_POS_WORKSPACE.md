# Sprint 3A — POS Workspace (Enterprise Layout Modernization) · Bounded Polish

Baseline / rollback: **`sprint-1-design-foundation`** (immutable). Primitives frozen (2B-1…2B-6): Empty State, Stepper, Status Badge, Button, Segment, Input, tokens, motion, radius, z-index.

## Scope decision (CTO-ratified)

Investigation found the POS workspace **already implements the recommended enterprise structure** — top bar (branch · session · role · connection · language) → left `.catalog` (search + scan / categories / product grid) → center-right `.ticket` (order header with seat + order-type segment + customer / cart lines / quick-action verbs / grouped totals) → bottom checkout (`.foot`: subtotal · discount · service · VAT · **Total**) with a dominant **Charge** CTA. It is already HIG-refined (~9.3/10) and densely coupled to JS (`renderGrid`/`renderOrder`/`updateTotals`/`charge`).

Per the standing rule *(a rewrite needs technical justification + why refactor is insufficient)* and this sprint's own ladder *(Keep → Polish → Re-layout → Recompose → never redesign)*, a ground-up **Recompose was rejected** (target structure already present; incremental polish sufficient; STOP-gated order/checkout wiring). CTO selected **Bounded Polish + targeted Re-layout**.

**Rule reaffirmed:** business logic, checkout flow, order math, tax, and inventory are untouched. No JS, no ids, no render targets, no DOM structure changed.

## Changes (CSS-only, 5 rules, all inside `<style>`)

| # | Rule | Change | Goal | Risk |
|---|---|---|---|---|
| 1 | `.trow.big` (Grand Total) | 17→**19px**, padding-top 8→10, margin-top 5→6, +`letter-spacing:-.01em` | Grand-Total dominance (hierarchy #1); anchors the totals group below the dashed separator, still under the 21px Charge-CTA amount | low |
| 2 | `.prod .pname` | +`-webkit-line-clamp:2` (`display:-webkit-box;-webkit-box-orient:vertical;overflow:hidden`) | Long-name handling → uniform card heights, cleaner grid scan | low |
| 3 | `.cats` | `gap:8px`→`var(--space-2)`, `padding-bottom:12px`→`var(--space-3)` | Spacing onto tokens (value-identical) | none |
| 4 | `.grid` | `gap:12px`→`var(--space-3)` | Spacing onto tokens (value-identical) | none |
| 5 | `.searchrow` | `margin-bottom:12px`→`var(--space-3)` | Spacing onto tokens (value-identical) | none |

`--space-2`=8px, `--space-3`=12px → #3–5 are **zero-pixel-change** hygiene (Sprint-1 style value-identical tokenization). #1–2 are the only intentional visual deltas.

## Primitive-reuse report

The workspace already consumes the frozen primitives where applicable: `.button` (checkout/actions via the `.charge` hero + `.button` family elsewhere), `.segment` (mode toolbars), `.input` (settings/modal fields), status badges (delivery/CK/reservations). **No new hand-rolled chrome to migrate** in the POS core — the order-type `.segmented` and `.seat` remain the `aria-pressed` pill family (intentionally distinct from `.segment` per 2B-5). So "reduce duplicated controls" was already satisfied by Phase 2; 3A adds no primitives and invents none.

## Verification

- **Diff scope:** 5 CSS lines, all inside `<style>`; braces 2582=2582 (982=982 in `<style>`).
- **Coupling:** 0 id / class-token / render-target / handler changes; `renderGrid`/`renderOrder`/`updateTotals`/`charge` targets (`#grid`,`#lines`,`#t-*`,`#charge`,`.prod`,`.pname`,`.trow.big`) intact.
- **Value-identity (hygiene):** `var(--space-2)`=8px, `var(--space-3)`=12px — #3–5 resolve to the prior literals; no computed change.
- **Business:** no backend, no JS, no order math / tax / checkout / inventory change → all payloads and totals identical.
- **Visual before/after screenshots:** **not captured** — CDP froze on the heavy `pos.html` (documented issue in this program). Changes are local/uncommitted and awaiting CTO visual review; #1–2 should be eyeballed in light + dark before merge.

## Information-hierarchy outcome

Grand Total (19px, weight 800, separated) → Charge CTA amount (21px, dominant button) remains the checkout anchor; sub-lines (13px) clearly subordinate. Product grid: price (14.5/800) > name (13.5/600, now clamped) preserves price-first scan with stable card heights.

## Remaining UX debt (deferred)

Off-scale spacing (14/11/9/18/13px in `.catalog`/`.thead`/`.foot`/`.lines`/`.verbs`) left as-is — snapping to tokens moves pixels and needs visual sign-off (appearance pass). Accessibility (focus-ring restoration, `aria-invalid`, label association) → Accessibility Sprint. Any further re-layout (denser grid, right-utility column split) is a Recompose and out of the ratified bounded scope.
