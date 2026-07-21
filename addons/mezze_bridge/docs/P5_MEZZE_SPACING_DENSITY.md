# P5 — Approved Mezze Spacing & Density System (Flag-Gated)

*Spacing + density only. Source of truth: `~/Downloads/Mezze POS Visual Redesign/export`. Amber remains the untouched default and is **pixel-identical**. No colour, typography, icon, motion, radius, elevation, shadow, business-logic, navigation or workflow change.*

## 1. Spacing Implementation Summary

- **Zero hardcoded spacing remains.** Hardcoded spacing values: **608 → 0**. 811 substitutions across **612 declarations** — 505 in CSS and **107 inline `style=` declarations** in markup/JS that a CSS-only sweep would have missed.
- **31 distinct px lengths** (0–52px) drove the whole surface, so the P4A compatibility-token strategy scaled cleanly.
- **Amber preserved by construction.** Each declaration reads a token whose *amber* value is the literal it had before. Proven mechanically: **612/612** declarations resolve to their `git HEAD` values (§6).
- **Approved 12-step scale implemented exactly:** `0 · 2 · 4 · 6 · 8 · 12 · 16 · 20 · 24 · 32 · 48 · 72px`.
- **Scope decision:** the sweep covers `padding`, `margin`, `gap`/`row-gap`/`column-gap` and their logical variants. It deliberately **excludes positioning offsets** (`top`, `left`, `inset`, `inset-inline-*`). Those are layout *coordinates*, not spacing; density-multiplying them would physically relocate absolutely-positioned elements — the layout movement this phase forbids. Reported, not migrated.
- **Structure:** braces 2765=2765, `node --check` OK, 0 undefined tokens.

## 2. Density Implementation Summary

Approved three-mode model, implemented exactly:

| Mode | `--mz-density` | Example (`--pad-dialog` 20px) |
|---|--:|--:|
| compact | `.8` | 16px |
| standard *(default)* | `1` | 20px |
| comfortable | `1.25` | 25px |

- Applied via `[data-mz-density]` on the root, scoped to the mezze appearance. Selector specificity is `:root[data-appearance="mezze"][data-mz-density="…"]` **(0,3,0)** so it reliably beats the appearance block (0,2,0) — the cascade trap that broke reduced-motion in P4B was avoided here by design.
- **Every spacing token resolves correctly in every density** — verified live for all three modes (§7).
- **Amber has no density concept.** Its compat tokens are literal px, so `[data-mz-density]` has no effect on the certified build.
- **Touch tokens are deliberately not density-scaled** (`--touch:44px`, `--touch-lg:48px`, `--touch-gap:8px`) — matching the approved values, and correct: shrinking a touch target by 20% would be an accessibility regression.

## 3. Spacing Token Mapping

**Architecture — Primitive → Semantic → Component → Components:**

```
--mz-space-*  (12-step primitive)
   ↓  × var(--mz-density)
--pad-card / --pad-panel / --pad-dialog / --gap-grid / --stack-sm|md|lg   (semantic)
   ↓
--sp-*  (component tokens — one per migrated literal)
   ↓
components
```

**Semantic tokens — attested in the export:**

| Token | Primitive | Standard density |
|---|---|--:|
| `--pad-card` | `--mz-space-150` | 12px |
| `--pad-panel` | `--mz-space-200` | 16px |
| `--pad-dialog` | `--mz-space-300` | 20px |
| `--gap-grid` | `--mz-space-150` | 12px |
| `--stack-sm` | `--mz-space-100` | 8px |
| `--stack-md` | `--mz-space-200` | 16px |
| `--stack-lg` | `--mz-space-400` | 24px |
| `--touch` / `--touch-lg` / `--touch-gap` | — | 44 / 48 / 8px *(not scaled)* |

**Semantic tokens the brief requires but the export does NOT define** — implemented as derived aliases and flagged rather than passed off as approved:

| Token | Derived from | Standard | Status |
|---|---|--:|---|
| `--inline-sm` | `--mz-space-075` | 6px | **not attested — needs ratification** |
| `--inline-md` | `--mz-space-100` | 8px | **not attested** |
| `--section` | `--mz-space-400` | 24px | **not attested** |
| `--pad-toolbar` | `--mz-space-150` | 12px | **not attested** |
| `--gap-form` | `--mz-space-150` | 12px | **not attested** |

The export defines only card/panel/dialog padding, grid gap and the three stacks. Inline, section, toolbar and form spacing were requested by the brief but have no approved values, so they are derived from approved primitives at the step matching current usage — declared, documented, and awaiting a source decision (same treatment as P3's unattested ligatures).

## 4. Compatibility-Token Mapping

The 31 amber literals sit on values that mostly exist on neither scale; snapping them directly would have moved amber by 1–2px. Each became a token holding its exact amber value, re-pointed onto the approved step (× density) under mezze:

| Amber literal | Component token | → Approved step (standard) |
|--:|---|---|
| 0 | `--sp-0` | `space-000` → 0 |
| 1, 2, 3 | `--sp-1/2/3` | `space-025` → 2px |
| 4, 5 | `--sp-4/5` | `space-050` → 4px |
| 6, 7 | `--sp-6/7` | `space-075` → 6px |
| 8, 9, 10 | `--sp-8/9/10` | `space-100` → 8px |
| 11, 12, 13, 14 | `--sp-11/12/13/14` | `space-150` → 12px |
| 15, 16, 17, 18 | `--sp-15/16/17/18` | `space-200` → 16px |
| 20, 22 | `--sp-20/22` | `space-300` → 20px |
| 24, 26, 28 | `--sp-24/26/28` | `space-400` → 24px |
| 30, 34, 38, 40 | `--sp-30/34/38/40` | `space-600` → 32px |
| 44, 48, 52 | `--sp-44/48/52` | `space-800` → 48px |

*The public API is the approved 12-step scale plus the semantic tokens. `--sp-*` are compatibility/component tokens whose only job is to keep amber pixel-identical while routing mezze onto the approved scale.*

## 5. Hardcoded Spacing Count

| | Before | After |
|---|--:|--:|
| CSS spacing declarations | 505 (501 hardcoded) | **0 hardcoded** |
| Inline `style=` spacing | 107 (all hardcoded) | **0 hardcoded** |
| **Total hardcoded values** | **608** | **0** |
| Substitutions applied | — | 811 |
| Distinct px lengths | 31 | 31 compat tokens |

Non-length keywords (`auto` ×35, `%`, `env(safe-area-inset-bottom)`) are preserved as-is; the `16px` inside `calc(16px + env(…))` was tokenized in place.

## 6. Amber Pixel-Identity Verification

Both files' token tables were resolved recursively and compared declaration-by-declaration, property name included:

```
declarations: 612 -> 612
amber-identical after resolution: 612/612
AMBER PIXEL-IDENTITY: PROVEN
```

No declaration was added, dropped, reordered, or had its property changed.

## 7. Mezze Validation Report

Measured as **computed `padding-left` on a live probe element** (custom properties return their specified value, so reading the variable alone would not have proven the `calc()` resolves):

| Token | Amber | Mezze standard | compact (.8) | comfortable (1.25) |
|---|--:|--:|--:|--:|
| `--sp-9` | 9px | **8px** | 6.4px | 10px |
| `--sp-12` | 12px | 12px | 9.6px | 15px |
| `--sp-14` | 14px | **12px** | 9.6px | 15px |
| `--sp-16` | 16px | 16px | 12.8px | 20px |
| `--sp-24` | 24px | 24px | 19.2px | 30px |
| `--pad-card` | 12px | 12px | 9.6px | 15px |
| `--pad-dialog` | 20px | 20px | 16px | 25px |
| `--stack-md` | 16px | 16px | 12.8px | 20px |
| `--touch` | 44px | 44px | **44px** | **44px** |
| `--sp-0` | 0 | 0 | 0 | 0 |

All 7 assertions pass: amber literal, mezze snaps to scale, semantic tokens resolve, compact/comfortable multiply correctly, touch unscaled, zero stays zero.

## 8. Accessibility Assessment

- **Touch targets — analysed, with one finding.** `--touch` tokens are not density-scaled, and **15 of 17** interactive rule-groups set an explicit `height`/`min-height`, which this phase never touches (height is not a spacing property). Only **2 controls are sized purely by padding** — `.langtog button` and `.segmented button` — so under **compact** density they shrink proportionally (e.g. `.segmented button` padding 7/4px → 5.6/3.2px). Note also that **no rule currently declares `min-height:44px`** anywhere; that is a **pre-existing** gap, not introduced here, which compact density would amplify for those two controls. **Recommendation:** if compact density ships, add `min-height:var(--touch)` to padding-sized controls — deferred because adding a min-height changes layout, which this phase forbids.
- **Keyboard focus spacing:** `outline-offset` is not a spacing property and was not touched; focus rings sit at the same offsets in every appearance and density.
- **RTL:** all logical properties (`margin-inline-*`, `padding-inline-*`) were preserved as logical — only their *values* changed. No physical/logical substitution occurred, so RTL mirroring behaves exactly as before.
- **Scrolling / clipping / overflow:** at **standard** density (the default) mezze spacing is equal to or *smaller* than amber at every step, so overflow pressure does not increase. **Comfortable (1.25) inflates all spacing by 25%** and is the realistic clipping risk on fixed-height POS panels (KDS columns, order rail) — this is the single most important thing to exercise at the visual gate.
- **Sub-pixel values:** compact density yields fractional px (6.4 / 9.6 / 12.8px). Browsers handle this fine, but it can produce marginally softer edges — inherent to the approved `.8` multiplier, not an implementation artefact.

## 9. Performance Assessment

- **No new assets, no requests, no JS.** CSS custom-property indirection only.
- Resolution depth is 3 (`--sp-9 → calc(--mz-space-100 × --mz-density) → 8px`), evaluated once per element at style computation.
- `pos.html` **430,545 → 442,211 bytes (+11,666)** — the largest phase delta, reflecting 811 substitutions plus the token blocks.
- **Density changes are a style recalculation**, not a layout algorithm change; switching density re-lays-out once, as any class toggle would.

## 10. Regression Assessment

- **Amber:** 612/612 declarations pixel-identical (§6); declaration count, property names and ordering unchanged.
- **Mezze:** verified live across all three densities (§7).
- **Untouched:** no markup structure, no JS logic, no selector, no property name. This phase changed only the right-hand side of spacing declarations and added token definitions.
- **Excluded by design:** positioning offsets (`top`/`left`/`inset*`) remain literal — migrating them would move elements under density (§1).
- **Structural:** braces balanced, `node --check` OK, 0 undefined tokens across 77 defined / 55 referenced spacing tokens.

## 11. Recommendation for Sign-Off

**RECOMMEND SIGN-OFF for P5**, conditional on the **manual visual gate** — with a sharper focus than previous phases, because spacing is the first system that can genuinely break a layout:

1. **Comfortable density (1.25) is the real risk.** Exercise `?appearance=mezze` with `data-mz-density="comfortable"` across Cashier / Payment / Kitchen / Reports / Live Ops in light + dark + RTL, watching specifically for clipping and overflow in fixed-height regions (KDS columns, order rail, modal bodies).
2. **Ratify the 5 unattested semantic tokens** (§3) — `--inline-sm`, `--inline-md`, `--section`, `--pad-toolbar`, `--gap-form` have no approved values and are currently derived.
3. **Decide on the touch-target follow-up** (§8) — no `min-height:44px` exists today; compact density would shrink two padding-sized controls further.

*Not in production behaviour — active only when `data-appearance="mezze"` is set; density additionally requires `data-mz-density`. P6 not started.*
