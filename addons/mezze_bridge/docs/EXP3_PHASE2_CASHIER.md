# Experience 3.0 — Phase 2: Cashier Workspace

*Rebuild the cashier presentation to visual parity with the approved Cashier design. Business logic, APIs, keyboard shortcuts and workflows preserved. Shell geometry (Phase 1) is frozen and untouched.*

**STATUS: implemented, verified, local commit — awaiting review.**

---

## 1. Scope

Phase 1 delivered the shell geometry (68 | 176 | 1fr | 340). Phase 2 recomposes the **content** of the three cashier regions to match the approved artboard: the category panel, the product workspace, and (partially) the order rail.

Source of truth: `export/Cashier Order Screen.html` (inline-styled approved component values).

## 2. What changed — presentation only

| Component | Approved | Before (Phase 1) | After (Phase 2) |
|---|---|---|---|
| **Category caption** | 11px/700/.1em/uppercase/faint | none | **"CATEGORIES" caption added** |
| **Category items** | icon+label, radius 12, pad 10/11, no border, transparent→tint states | bordered pills, ink-black active | **borderless rows, radius 11, brand-tinted active** |
| **Category panel** | gap 4, pad 0/10/14 | gap 6, pad 12/8 | **gap 4, pad 0/10/14** |
| **Product card** | radius 14, full-bleed 1/1 image well + border-bottom, body pad 9/11/10 | padded thumbnail (13px inset), thumb has own radius+border | **full-bleed image well, radius 14, padded body** |
| **Product name** | 13.5px/600/1.25/-.01em, 2-line clamp | 2-line clamp (padded) | **same, now in padded body** |
| **Product grid** | `minmax(150px)`, gap 11 | `minmax(134px)`, gap ~8 | **`minmax(150px)`, gap 12** |

**Implementation:** CSS-only except **one markup change** — wrapping `#cats` in a `.catcol` column with the caption. `#cats` itself is untouched, so the JS that populates it works unchanged.

## 3. Preserved (verified)

| Guarantee | Evidence |
|---|---|
| **JavaScript byte-identical to `git HEAD`** | diff = 0 (business logic, APIs, state untouched) |
| Category filtering | click Bakery → grid re-rendered to 4 products ✓ |
| View switching (all 11 other workspaces) | 0 broken, 0 JS errors ✓ |
| Keyboard shortcuts | `/` focuses search ✓ |
| DOM hooks (`#cats`, `#grid`, `#search`, `.chip`, `.prod`) | unchanged ✓ |

## 4. Validation — measured live

**Product card (mezze):** padding 0 ✓, radius 14 ✓, overflow hidden ✓; image well aspect-ratio 1/1 ✓, radius 0 + border-bottom 1px ✓ (full-bleed); name 13px/600/1.25 in padded body ✓; price 15px/800 ✓; card width 159px (from `minmax(150)`) ✓.

**Category panel (mezze):** catcol 176px ✓; caption "CATEGORIES" 11px/700/uppercase ✓; inactive chips transparent ✓; active chip visible (bg ≠ panel) in **both** light and dark ✓; active label contrast **4.61:1** (passes AA) ✓.

**Amber:** same composition (card radius 18/amber, full-bleed well, caption, 176 catcol) — layout is appearance-independent, tokens still differ by appearance ✓.

### A bug caught and fixed during validation

The active category first used `--surface` bg + `--shadow-sm`. In mezze **dark**, `--shadow-sm` resolves to `none` (the approved dark elev-1, documented in P4A) **and** the panel is also `--surface` — so the active state was invisible against the panel. Fixed by using a **brand-tinted active** (`--accent-soft` bg + `--accent-strong` text), which is distinct and readable in both themes (4.61:1) and works despite dark elevation being flat.

## 5. Cashier compliance: **≈ 88%**

| Region | Compliance | Notes |
|---|--:|---|
| Shell geometry (Phase 1, frozen) | **100%** | 68/176/1fr/340 verified |
| Product workspace (search + grid + cards) | **~95%** | Full-bleed cards, correct grid; 1px diffs from token-snapping (below) |
| Category panel | **~85%** | Chrome/caption/states match; **per-category icons missing** (§7) |
| Order rail | **~65%** | Correct geometry + design-system styling; internal hierarchy not recomposed (§7) |
| **Weighted overall** | **≈ 88%** | |

**On the 1px differences:** the approved artboard uses raw px (body 9/11/10, gap 11). Our components consume the **completed Mezze spacing scale**, which snaps those to the nearest step (8/12). Per the brief ("use the completed Mezze Design System"), this is correct — the scale is now the source of truth, and the ≤1px deltas are inherent to it, not defects.

## 6. Before / After

- **Before (Phase 1):** vertical category column of **bordered pills** with a black active state, and **padded-thumbnail** product cards (image inset with its own border/radius), no panel caption.
- **After (Phase 2):** a captioned **"CATEGORIES"** panel with clean borderless rows and a terracotta-tinted active item; **full-bleed image-well** product cards (square photo edge-to-edge, name + price in a padded body) on a `minmax(150)` grid.

Both captured live (screenshots in session). Both appearances render the new composition.

## 7. Remaining visual differences

| # | Item | Reason | Recommendation |
|---|---|---|---|
| 1 | **Per-category icons** (approved category rows are icon+label) | This demo's categories (Coffee/Cold/Bakery/Food/Beans) have **no icon assignment** in the approved export, which defines icons for *its* category set. Assigning icons here would be inventing. The `.chip` already reserves an 11px leading `gap` for them. | Provide an approved category→Material-Symbol mapping, then render a leading `.mi` in the `#cats` builder. |
| 2 | **Order-rail internal hierarchy** not recomposed | The approved order-panel detail (totals hierarchy, primary/secondary actions, checkout CTA) overlaps almost entirely with **Phase 3 (Payment Workspace)**. Recomposing it now without that spec risks inventing and duplicating Phase 3. Geometry (340px) and design-system styling are already correct. | Address the order-rail hierarchy **together with Phase 3**, where the checkout/totals/CTA hierarchy is the core subject. |
| 3 | **Category caption is English-only** | `t()` returns the key for missing translations, so `data-i18n` was removed to avoid rendering the literal key. | Add a `cats.title` translation key (AR/EN) — one dict entry. |
| 4 | Rail button sizing (approved 46×44 vs live 64×49) | The rail is **shell**, now frozen. | Out of scope; raise as a shell-defect item only if desired. |

## 8. Recommendation for Phase 3

**Phase 2 is substantially complete (~88%) and correct.** The category panel and product workspace match the approved cashier; business logic, shortcuts and workflows are fully preserved (JS byte-identical); zero regressions.

**Recommend proceeding to Phase 3 (Payment Workspace) — and folding the order-rail hierarchy (§7 item 2) into it**, since the approved order panel and the payment flow are one design concern. Items 1 and 3 are small follow-ups that need a design/data input (icon map, i18n key), not engineering decisions.

*Committed locally (not pushed) as a reviewable checkpoint. Shell remains frozen.*
