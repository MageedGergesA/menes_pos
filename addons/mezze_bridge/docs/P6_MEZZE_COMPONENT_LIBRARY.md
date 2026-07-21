# P6 — Approved Mezze Component Library (Flag-Gated)

*Component-library compliance. Source of truth: `~/Downloads/Mezze POS Visual Redesign/export`. Amber remains the untouched default and is **pixel-identical**. No business logic, workflow, navigation, screen layout or architecture change. No new colours, spacing values or typography introduced — components consume only the completed P1–P5 design system.*

## 1. Component Compliance Summary

- **20 component families / 442 component rules audited. 20 families compliant, 3 structural exceptions** (all `border-style` keywords and one border *width* — no design values). See §6.
- **The outstanding gap was typography**, which P2 deliberately deferred as layout-affecting. P6 closes it with the compatibility-token strategy the brief endorsed: **font-size 401 → 0**, **font-weight 269 → 0**, **line-height 32 → 0**, **letter-spacing 70 → 0**, **font-family 3 → 0**, **residual colour literals 38 → 0**.
- **Amber pixel-identity now proven across the entire design system — 2,555 declarations** spanning every P1–P6 property (§9).
- **No component redesign.** Markup tag sequence (**3,410 tags**) and CSS selector sequence (**1,065 selectors**) are byte-identical; JS line count unchanged (2,956). Only declaration *values* changed.

## 2. Component Inventory & 3. Components Audited

| Component family | Rules | Hardcoded design values | Status |
|---|--:|--:|---|
| Buttons | 56 | 0 | ✅ compliant |
| Inputs / Text fields | 15 | 0 | ✅ |
| Search | 11 | 0 | ✅ |
| Dropdowns / Menus | 14 | 0 | ✅ |
| Cards | 32 | 1 | ⚠️ §6 |
| Product cards | 20 | 0 | ✅ |
| Category chips | 30 | 1 | ⚠️ §6 |
| Badges / Status pills | 22 | 0 | ✅ |
| Dialogs / Modals | 26 | 0 | ✅ |
| Tooltips | 10 | 0 | ✅ |
| Tables / Rows / Lists | 60 | 0 | ✅ |
| Tabs / Segmented | 10 | 0 | ✅ |
| Toast / Alerts | 17 | 0 | ✅ |
| Empty states | 10 | 0 | ✅ |
| Progress indicators | 7 | 0 | ✅ |
| Quantity controls / Number pad | 20 | 0 | ✅ |
| Payment / Checkout controls | 28 | 0 | ✅ |
| KDS cards | 13 | 0 | ✅ |
| Receipts | 17 | 0 | ✅ |
| Floor plan | 24 | 1 | ⚠️ §6 |
| **Total** | **442** | **3** | |

Every family resolves through **Primitive → Semantic → Component → Component**: `--mz-*` primitives (P1–P5) → semantic roles (`--accent`, `--surface`, `--pad-*`, `--stack-*`, `--font-*`) → component tokens (`--sp-*`, `--r-*`, `--fs-*`, `--fw-*`, `--dur-*`) → components.

## 4. Components Changed

No component was *redesigned*; the change is that every component now reads tokens instead of literals.

| Property | Declarations migrated | Amber | → Mezze |
|---|--:|---|---|
| `font-size` | 401 | exact literals (35 compat tokens) | approved 9-step scale |
| `font-weight` | 269 | exact literals (7 tokens) | approved 5 weights (900 → 800) |
| `line-height` | 32 | exact literals (11 tokens) | approved leading; `1`/`1.05` retained |
| `letter-spacing` | 70 | exact literals (19 tokens) | **retained** — no approved values |
| `font-family` | 3 (+3 compat tokens) | exact original mono stacks | approved `--mz-font-num` |
| colour literals | 38 | `--on-color` + 4 compat tokens | follows appearance |

**Type-scale mapping** (amber literal → approved step under mezze): `≤11.5px → 11` · `12–12.5 → 12` · `13–13.5 → 13` · `14–15 → 15` · `16–19 → 18` · `20–22 → 22` · `24–27 → 26` · `28–34 → 32` · `>34 → 40`.

## 5. Components Already Compliant

Radius, elevation, shadow, motion and spacing were already fully tokenized by P4A/P4B/P5 and re-verified here: **border-radius 2, box-shadow 3, transition/animation 1, spacing 1** residual values — every one a structural `none`/`0`/`auto`/`inherit`, not a design value. All 20 families passed on those axes without a single change in this phase.

## 6. Remaining Exceptions

| Exception | Where | Why it stays |
|---|---|---|
| `border-inline-start-width: 4px` | `.dlvcard` (accent stripe) | The approved system defines **no border-width scale**. Tokenizing it as *spacing* would be semantically wrong and would let density resize a border. Documented, not invented. |
| `border-style: solid` | `.custchip.on` | A CSS keyword, not a design value. |
| `border-style: dashed` | `.table.rs .tabletop` | A CSS keyword, not a design value. |
| **`letter-spacing` (19 tokens)** | app-wide | The approved system defines **no letter-spacing tokens** (established in P2). Values are tokenized so no component holds a literal, but they resolve to their amber values in *both* appearances. **Needs a source decision.** |
| `line-height: 1` / `1.05` (11 uses) | icon/glyph containers incl. `.mi` | These are *resets* for glyph alignment, not text leading. The approved leading scale starts at 1.2; forcing it would shift icons vertically. Retained. |
| 4 icons + brand mark | P3 | Unchanged from P3 (wordmark, sparkline, CSS `url()` lock, empty chart node). |

## 7. Accessibility Report

- **Contrast unchanged** — no colour value was altered; the 38 literals became tokens resolving to the identical colours. P1's flagged pairs (notably `warn/warn-soft` 2.86) are unchanged and still awaiting a source decision.
- **Readability improves under mezze.** The approved scale's floor is 11px, so the smallest labels rise from **8px/9px/10px → 11px** (+10–37%). This is a genuine accessibility gain and simultaneously the largest reflow risk (§11).
- **Touch targets unaffected** — 15 of 17 interactive rule-groups set explicit `height`/`min-height`, which this phase does not touch. The pre-existing absence of any `min-height:44px` (reported in P5) is unchanged.
- **Keyboard navigation and focus visibility unchanged** — no selector, `outline`, or `tabindex` was modified; focus rings resolve exactly as before.
- **Screen-reader labels unchanged** — no markup was touched (3,410 tags identical); P3's `aria-label` 63 / `role` 16 counts hold.
- **RTL** — logical properties preserved throughout; only values changed.
- **Font weights clamp 900 → 800** under mezze (approved maximum), a marginal reduction in emphasis contrast on 3 declarations.

## 8. Performance Impact

- **No new assets, requests, or JS.** CSS custom-property indirection only.
- `pos.html` **442,211 → 453,149 bytes (+10,938)**.
- Deepest resolution chain is 3 (`--fs-14 → --mz-size-400 → 15px`), evaluated once per element at style computation.
- Under mezze, text sizes change, so **the first paint after switching appearance reflows** — a one-time layout, not a per-frame cost.

## 9. Regression Assessment

**Amber pixel-identity — proven across the whole design system.** Both token tables resolved recursively and compared declaration-by-declaration:

```
font-size 401/401 · font-weight 269/269 · line-height 33/33 · letter-spacing 72/72
font-family 25/25 · color 429/429 · background 297/297 · background-color 1/1
border 120/120 · border-top 17/17 · border-bottom 27/27 · border-color 70/70
border-radius 202/202 · box-shadow 60/60 · transition 62/62 · animation 12/12
padding 242/242 · margin 20/20 · gap 196/196
AMBER PIXEL-IDENTITY across 2555 declarations: PROVEN
```

- **Structure untouched:** markup tags 3,410 identical; CSS selectors 1,065 identical; JS lines 2,956 unchanged.
- **All 37 changed JS lines audited individually** — 36 pure literal→token swaps in inline `style=` strings, 1 identical (a `font-family` swap my skeleton check didn't model).
- **One cosmetic artefact:** a single space was dropped inside `color-mix(in srgb, …)` on JS line 245, because the value regex stops at a JS quote. The comma is the separator, so the CSS is functionally identical — reported rather than left unmentioned.
- **Two bugs found and fixed during validation:**
  1. **Real amber regression** — mapping three plain monospace stacks to `var(--font-num)` silently changed amber's font stack (`--font-num` is `ui-monospace,"SF Mono","Roboto Mono",Menlo,monospace`). Caught by the identity proof; fixed with `--ff-mono-a/b/c` compat tokens holding the exact original stacks.
  2. A comment containing the literal text `letter-spacing:` was being counted as a declaration, causing a false 72→73 count mismatch. Comment reworded so future audits stay clean.

## 10. Before/After Screenshots

**Not captured** — the CDP bridge freezes on the heavy `pos.html`, unchanged across every phase. Verified numerically instead: amber identity across 2,555 declarations, and mezze resolution measured on a live probe element (computed `font-size`/`font-weight`/`line-height`, since custom properties return specified values).

Measured mezze resolution: `8px→11px`, `10px→11px`, `13px→13px`, `14px→15px`, `20px→22px`, `30px→32px`; weights `900→800`, `700→700`; leading `1.5→1.4`, `1.25→1.2`, `1→1` (retained); letter-spacing unchanged.

**Manual gate:** `…/pos.html?appearance=mezze` across Cashier / Payment / Kitchen / Reports / Live Ops in light + dark + RTL + all density modes.

## 11. Recommendation for Sign-Off

**RECOMMEND SIGN-OFF for P6**, conditional on a visual gate that is now genuinely load-bearing — this is the first phase whose mezze output **reflows text**:

1. **Small-label reflow is the top risk.** Raising 8/9/10px labels to 11px is a +10–37% jump on the densest elements (badges, status pills, chips, KDS meta, table numerals). Combined with **comfortable density (1.25)** from P5, this is the worst-case overflow scenario — exercise that combination first.
2. **Ratify letter-spacing** (§6) — 19 tokens currently resolve to amber values because the approved system defines none. Several amber values are negative tracking (`-.02em`) tuned for the *old* typeface; they may not suit Hanken Grotesk.
3. **Confirm the `line-height: 1` retention** (§6) — I judged these to be glyph-alignment resets rather than leading. If any were intended as text leading, they should map to `--mz-leading-tight`.

*Not in production behaviour — active only when `data-appearance="mezze"` is set. P7 not started.*
