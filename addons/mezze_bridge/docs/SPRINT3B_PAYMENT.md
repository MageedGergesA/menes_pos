# Sprint 3B — Payment Experience Audit + Bounded Optimization

Baseline / rollback: **`sprint-1-design-foundation`**. Primitives frozen. Payment flow behaviourally identical — no backend / accounting / calculation / tender-logic change.

## Decision classification: **B — Bounded Polish** (one CSS-only change)

Reconnaissance found the payment screen well-structured and near-target. Exactly **one** genuine, harmful hierarchy deviation was found and fixed (Remaining under-emphasis). Everything else = **KEEP**. No re-layout / recompose.

## Current-state map

Two-column modal (`.modal.pay`, max-width 960px), header (`.mhead`: "Payment" + item/table subline + close `.mx`).

**LEFT `.payleft` (1.05fr):**
- `.paydue` — "Amount due" label (12px caps) + **`#pay-due` 40px/800** (the headline total, centered).
- `.paytips` — tip label + `#tipchips`.
- `.payremain` (`#pay-remain`) — live status line: "Remaining: EGP X" (amber `--warn`) or "✓ Fully covered" (green `--pos`, `.done`).
- `.tenders` (`#tenders`) — 2×N tender cards (cash/card/wallet/gift); `.tender.sel` = accent border + accent-soft bg.
- `#pay-cash1tap` (`.button--primary`) — one-tap exact-cash-and-complete; shown only before any tender.
- `.acqnote` — processor note.

**RIGHT `.payright` (1fr):**
- `.payamt` — "Entering" label + **`#pay-entry` 30px/800** (numpad working value, surface-2 box, right-aligned).
- `.quickcash` (`#quickcash`) — 4-col quick-cash buttons (44px).
- `.numpad` (`#pay-numpad`) — 3-col keypad (60px).
- `.tenderlist` (`#tenderlist`) — added tender lines (`.tli` + remove `.tlx`).
- `.changebox` (`#changebox`, hidden until change>0) — "Change due" + **`#pay-change` 30px** green (`--pos-soft`).
- `#pay-complete` (`.button--positive`) — Complete payment; disabled until `remaining()<=0.001`.

## UX findings (evidence-based)

| Question | Verdict |
|---|---|
| Amount due < 1s? | **Yes** — 40px centered headline. |
| Remaining unmistakable? | **No (pre-fix)** — 16px, the *smallest* key number, though it's the live target during mixed/partial. → fixed. |
| Change unmistakable? | Yes — 30px green box. |
| Selected tender obvious? | Yes — accent border + soft bg. |
| Mixed payment understandable? | Yes — tender list + live remaining. |
| Completion dominant? | Yes — full-width green `.button--positive`. |
| Accidental completion? | Guarded — disabled until covered + async double-click guard. |
| Disabled states clear? | Yes — Complete dim + Remaining explains why. |
| Quick-cash hittable? | Yes — 44px (meets min touch target). |
| Knows what's next? | Yes — Remaining→Covered→Change→Complete. |
| Duplicated controls? | No — one-tap cash / tender cards / quick-cash are distinct paths. |
| Competing values? | **One issue** — Remaining (16) was out-ranked by Entering/Change (30), inverting the target. |

## Information-hierarchy assessment

Target: 1 Amount due/Remaining · 2 Entered · 3 Change · 4 Tender · 5 Complete · 6 totals · 7 utility.
Pre-fix reality: Amount due 40 > Entering 30 = Change 30 > **Remaining 16** — Remaining (a tier-1 live target) sat *below* tier-2/3. **Only harmful deviation.** Post-fix: Remaining 22 sits clearly under the 40px headline and reads as the live secondary anchor (not competing with the headline, no longer dwarfed by transient input values).

## Business-logic dependency map (all PRESERVED — untouched)

- **State vars:** `payDue`, `payTenders[]`, `paySel`, `payEntry`, `BRIDGE.payGift`.
- **Calc/handlers:** `remaining()`, `paidTotal()`, `addTender()`, `renderQuick()`, `renderTenderList()`, `updatePayState()`, `updateEntry()`, `renderTenders()`, `#pay-complete` async handler, `#pay-cash1tap`, `.payamt` onclick, keypad handler, keydown (0-9/./Enter/Backspace/F1-4/c/e).
- **Completion gate:** `#pay-complete.disabled = remaining()>0.001`. **Change:** `Math.max(0,paidTotal()-payDue)`. **Rounding/format:** `EGP()`/`INT()`.
- **ids:** `#pay-due #pay-remain #pay-entry #pay-change #changebox #pay-complete #pay-cash1tap #pay-cash1amt #pay-cash1lbl #quickcash #pay-numpad #tenders #tenderlist #tipchips`.
- **classes JS reads:** `.tender`(`.sel`), `.tli`/`.tlx`, `.payamt`, `.numpad button`, `.quickcash button`, `.payremain`(`.done` via classList), `#changebox`(`.hidden`).
- **The changed selector `.payremain` is written by JS only via `classList.add/remove('done')` and `.textContent`** — a font-size change does not affect either. **Additive-safe.**

## State Matrix (all behaviour unchanged; only Remaining/Covered font size increased)

| State | Remaining line | Complete | Change box | Selected tender |
|---|---|---|---|---|
| No tender | "Remaining: EGP {due}" amber | disabled | hidden | cash (default) |
| Cash/Card selected | amber remaining | disabled | hidden | `.tender.sel` on choice |
| Partial | amber remaining (shrinking) | disabled | hidden | selected |
| Exact / Zero remaining | "✓ Fully covered" green | **enabled** | hidden | — |
| Overpayment | "✓ Fully covered" green | enabled | **shown** (green, change) | — |
| Mixed tender | amber until covered, then green | disabled→enabled | shown if over | last selected |
| Empty/invalid amount | unchanged (no tender added) | per remaining | — | — |
| Processing | (async) | disabled (guard) | — | — |
| Completed | flash + receipt | — | — | — |

## Visual audit

| Element | Measure | Classification |
|---|---|---|
| `.paydue .pv` amount | 40px/800 | No issue (correct #1). |
| **`.payremain`** | **16px/800** | **Hierarchy issue** → polish to 22px. |
| `.payamt .pav` entering | 30px/800 | No issue. |
| `.changebox` change | 30px | No issue. |
| `.tender.sel` | 1.5px accent border + accent-soft | No issue (clear). |
| `#pay-complete` | `.button--positive` full-width green | No issue (dominant). |
| `.quickcash button` | 44px | No issue (min touch met). |
| `.numpad button` | 60px | No issue. |
| Spacing (24px panels; 12/14/18 margins) | mixed | Token-only cleanup available; **deferred** (value-only, no visual gain, keep diff minimal). |

## Change made

`.payremain{font-size:16px → 22px}` — one declaration. Strengthens the live Remaining target and the "✓ Fully covered" confirmation (same rule spans both states via `.payremain.done`). Weight (800), color logic (`--warn`/`--pos`), margins, alignment, and all behaviour unchanged. `letter-spacing:-.01em` scales proportionally (−0.16→−0.22px) — an em-relative consequence of the size, not an independent edit.

## Primitive reuse

No new primitives; none invented. Payment-specific controls (tender cards, numpad, quick-cash, tender line, change/remaining indicators) correctly remain distinct per the brief. The two CTAs already use the frozen `.button` primitive (`#pay-cash1tap` `--primary`, `#pay-complete` `--positive`). The change touches only the payment-specific `.payremain` indicator.

## Screenshots / failure log

Required states could **not** be captured — the Chrome CDP bridge froze on the heavy `pos.html` (script-injection timeout), consistent across this program.
- Attempt 1 (tab …377): timeout. Attempt 2 (tab …389): timeout. Attempt 3 (tab …377): timeout. → **stopped after 3** per protocol.
- Opening the payment modal additionally requires interactive click-through on a frozen page (infeasible).
- **Visual confirmation is a MANUAL MERGE GATE:** please open Payment in light + dark and confirm the Remaining/Covered line reads as a clear secondary anchor. No visual proof is claimed here.

## Computed-style verification (light harness, both themes)

OLD vs NEW `.payremain`: `fontSize 16px→22px`; **color identical** — Remaining `--warn` (light rgb(196,106,22) / dark rgb(233,165,77)) and `.done` `--pos` (light rgb(28,154,96) / dark rgb(89,196,141)) unchanged; weight/variant/align/margins identical; letter-spacing scales with em (expected). No other property changed.

## Interaction / keyboard / focus verification

**No JS touched** → cash/card/mixed selection, quick-cash, exact cash, manual/numpad entry, backspace/delete, zero/empty handling, partial/over payment, change, Complete disabled/enabled, double-click suppression, Enter/Space, Tab order, focus retention, and failure recovery are all byte-identical. `.payremain` is not focusable/interactive.

## Business verification

No backend, no JS, no math: total, remaining, change, payment lines, mixed-tender totals, rounding, tax, discount, service charge, receipt totals, backend payload, order/payment-completion state — **all unchanged**. Diff = 1 CSS line; braces 2582=2582; 11 payment ids/handlers intact.

## Performance impact

DOM delta 0 · JS delta 0 · CSS delta 1 declaration value · no new elements/animation/library · a 6px larger status line reflows only its own row within a fixed-width modal. Negligible.

## Remaining UX debt (deferred, non-harmful)

- Token-only spacing normalization in the payment panels (value-identical; cosmetic).
- Optional `#pay-complete` height bump for extra CTA dominance (currently adequate; skipped to avoid touching the shared `.button--positive` primitive).
- Selected-tender cue could gain a check-glyph (currently clear enough).
- Accessibility (focus ring, `aria-live` on Remaining/Change) → Accessibility Sprint.

## STOP-condition result

No STOP tripped: no payment-logic/rounding/tax/tender change; every state mapped confidently; mixed-payment unambiguous; no DOM restructuring; selectors safely decoupled from the change (`.payremain` is text/`classList`-only in JS); computed business values unchanged; no backend; classification is **B**, not C/D.
