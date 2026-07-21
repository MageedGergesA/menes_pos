# P4A — Approved Mezze Surface System (Flag-Gated)

*Radius / elevation / shadow / surface / border only. Source of truth: `~/Downloads/Mezze POS Visual Redesign/export`. Amber remains the untouched default and is **pixel-identical**. No motion, spacing, density, layout, typography, icon, colour, navigation or business-logic change.*

## 1. Surface Implementation Summary

- **Everything is token-driven.** Hardcoded surface values in components: **border-radius 119 → 0**, **box-shadow 22 → 0**. The only literals left are two structural `0`/`inherit` resets and three explicit `none`s — absences, not values a token should own.
- **117 radius declarations** and **22 shadow declarations** were migrated to tokens, including **20 inline `style=` radii and 1 inline shadow** in markup/JS, which a CSS-only sweep would have missed.
- **Amber preserved by construction, not by care.** Each migrated declaration now reads a token whose *amber* value is the exact literal it had before, so the certified build resolves to the identical computed value. Proven mechanically: all **202 `border-radius`** and **60 `box-shadow`** declarations resolve to their `git HEAD` values (§9).
- **Approved scale implemented exactly** under `[data-appearance="mezze"]`: radius `8 / 11 / 14 / 16 / 999`, elevation `elev-1/2/3` in **both** light and dark.
- **Borders and surfaces needed no work** — P1 already routed every border/surface *colour* through `--border`, `--border-strong`, `--line`, `--surface{,-2,-3}`. Audit found **0** component rules with a hardcoded border or surface colour.
- **Structure:** braces balanced (2757=2757), `node --check` OK, every referenced token defined (0 undefined).

## 2. Radius Token Mapping

Approved scale (mezze): `--mz-radius-sm 8px · md 11px · lg 14px · xl 16px · pill 999px`.

**Semantic tokens** (already used by 83 declarations):

| Token | Amber | → Mezze | Note |
|---|--:|--:|---|
| `--r-sm` | 8px | **8px** | exact match |
| `--r-md` | 12px | **11px** | |
| `--r-lg` | 18px | **14px** | |
| `--r-xl` | 24px | **16px** | |
| `--r-pill` | 999px | **999px** | |
| `--r-circle` | 50% | 50% | **no approved equivalent** — retained, not invented (§10) |

**Amber-compat tokens.** The 99 hardcoded radii sat on values (4–26px) that exist on *neither* scale. Snapping them straight to the 5 approved steps would have moved amber by 1–2px, breaking "amber unchanged". So each literal became a token holding its exact amber value, re-pointed onto the approved step under mezze:

| Token | Amber | → Mezze step | Uses |
|---|--:|---|--:|
| `--r-4` | 4px | `sm` 8px | 3 |
| `--r-5` | 5px | `sm` 8px | 4 |
| `--r-6` | 6px | `sm` 8px | 10 |
| `--r-7` | 7px | `sm` 8px | 3 |
| `--r-9` | 9px | `sm` 8px | 13 |
| `--r-10` | 10px | `sm` 8px | 12 |
| `--r-11` | 11px | **`md` 11px** (exact) | 20 |
| `--r-13` | 13px | `lg` 14px | 7 |
| `--r-14` | 14px | **`lg` 14px** (exact) | 14 |
| `--r-15` | 15px | `xl` 16px | 2 |
| `--r-16` | 16px | **`xl` 16px** (exact) | 3 |
| `--r-20` | 20px | `xl` 16px | 3 |
| `--r-22` | 22px | `xl` 16px | 1 |
| `--r-26` | 26px | `xl` 16px | 1 |
| `--r-99` | 99px | `pill` | 2 |

*These numeric tokens are a **compatibility layer**, not a second design scale: their only job is to keep amber pixel-identical while routing mezze onto the approved five steps. The public API remains `sm/md/lg/xl/pill`.*

## 3. Elevation Mapping

Approved three-level model, implemented dual-theme:

| Token | Mezze light | Mezze dark |
|---|---|---|
| `--mz-elev-1` | `0 1px 2px rgba(42,36,32,.06)` | **`none`** |
| `--mz-elev-2` | `0 6px 16px -8px rgba(42,36,32,.16)` | `0 6px 18px -8px rgba(0,0,0,.5)` |
| `--mz-elev-3` | `0 18px 40px -14px rgba(42,36,32,.24)` | `0 22px 48px -16px rgba(0,0,0,.7)` |

Bound to the existing elevation roles so **no component changed**: `--shadow-sm → elev-1` (21 uses), `--shadow-md → elev-2` (5), `--shadow-lg → elev-3` (8).

## 4. Shadow Mapping

Beyond the three elevations, 22 hardcoded shadows were extracted into tokens (amber values verbatim):

| Token | Amber value | Mezze |
|---|---|---|
| `--shadow-accent` | `0 8px 22px rgba(224,152,43,.34)` | tint from `var(--accent)` |
| `--shadow-accent-sm/md/mdb/lg` | amber accent glows `.2/.24/.28/.3` | tint from `var(--accent)` |
| `--shadow-pos-sm/md/glow` | success glows | unchanged (semantic state colour) |
| `--shadow-drawer`, `--shadow-drop` | `-8px 0 30px -22px …`, `0 4px 14px …` | unchanged |
| `--ring-accent-2/-3` | `0 0 0 2px/3px var(--accent)` | follows brand automatically |
| `--ring-inset-pos/-crit/-warn` | `0 0 0 1px var(--…) inset` | unchanged |
| `--ring-pos`, `--ring-pos-soft` | focus/validation rings | unchanged |
| `--ring-pulse-from/-to` | amber pulse keyframe stops | tint from `var(--accent)` |
| `--scrim-spotlight` | `0 0 0 9999px rgba(8,5,1,.68)` | unchanged (§10) |

**Accent glows now follow the brand.** P1 explicitly deferred this ("`--shadow-accent` keeps an amber tint on terracotta buttons until the elevation phase") — this phase resolves it via `color-mix(… var(--accent) …)`, so mezze buttons no longer glow amber. Geometry is untouched; only the tint follows the already-approved brand token.

## 5. Border Mapping

**No changes required.** P1 already routed all border colour through tokens; this phase re-audited and confirmed:

| Role | Token | Mezze value (light / dark) |
|---|---|---|
| Default border | `--border` | `#EAE2D6` / `#453E33` |
| Strong border | `--border-strong` | `#D6C7B2` / `#5A4E3F` |
| Divider | `--line` | `--mz-divider` |
| Surfaces | `--surface`, `--surface-2`, `--surface-3` | approved values (P1) |

Component rules with a hardcoded border colour: **0**. `outline` declarations **8 → 8 identical**; `border-style` 2 → 2 identical; `border-width` unchanged.

## 6. Accessibility Report

- **Focus rings unchanged and visible.** All 8 `outline` declarations are byte-identical; `:focus-visible{outline:2.5px solid var(--accent);outline-offset:2px}` is untouched. Only the ring's *corner radius* is now a token (`--r-6` → 8px in mezze), which does not affect ring thickness, offset, or contrast. `--ring-accent-2/-3` now follow `var(--accent)`, so the ring keeps brand contrast in both appearances.
- **Shadows do not reduce readability.** No shadow is applied to text; all are container elevations. The approved elevations are *lighter* than amber's (e.g. elev-3 `.24` alpha with a `-14px` spread vs amber's `.18` at full spread), and none sit between text and its background.
- **Borders remain distinguishable.** Border colours are P1-approved and were WCAG-reviewed there; nothing in this phase alters them. Non-text contrast for `--border-strong` on `--surface` is unchanged.
- **Dark-mode elevation hierarchy — one finding.** The approved `--mz-elev-1` is **`none`** in dark, so `--shadow-sm` (the most-used elevation, 21 sites) renders *no shadow* in mezze dark. Separation there falls entirely to `--border`/`--border-strong`, which are present on all those components. This is the **approved model**, faithfully implemented and not worked around — but it is a deliberate reduction in dark-mode elevation cueing and belongs in the visual sign-off.

## 7. Performance Impact

- **No new assets, no new requests, no JS.** Pure CSS custom-property indirection.
- `pos.html` **422,139 → 426,774 bytes (+4,635)**; 86 new custom-property declarations.
- Custom-property resolution is done once per element at style computation; the added indirection depth is 2 (`--r-9 → --mz-radius-sm → 8px`). No measurable paint or layout cost, and **no layout is invalidated** — amber resolves to identical values, so its render tree is unchanged.

## 8. Before/After Screenshots

**Not captured** — the CDP bridge freezes on the heavy `pos.html` (persistent across every phase). Cascade behaviour was instead verified numerically in a live browser: amber and mezze (light + dark) computed values were read for all radius and elevation tokens and matched the approved values exactly (§9).
**Manual visual gate:** `…/pos.html?token=<t>&appearance=mezze` across **Cashier / Payment / Kitchen / Reports / Live Ops** in **light + dark + RTL**, then `?appearance=amber` to confirm the certified build is unchanged. Watch specifically for: softer corners (18px→14px on cards), lighter elevation, and **dark-mode `elev-1` being absent** (§6).

## 9. Regression Assessment

- **Amber pixel-identity — proven, not asserted.** Both files' token tables were resolved recursively and compared declaration-by-declaration: **202/202 `border-radius`** and **60/60 `box-shadow`** resolve to their original values. Declaration counts are unchanged, so nothing was dropped or duplicated.
- **Mezze cascade verified in-browser:** radius `8/11/14/16/999` exact; compat tokens snap correctly (`4→8`, `9→8`, `11→11`, `14→14`, `20→16`, `26→16`); elevation exact in light **and** dark (`--shadow-sm` → `none` in dark, as approved).
- **Structural:** braces 2757=2757, `node --check` OK, 0 undefined tokens, `outline`/`border-style` declarations identical.
- **Untouched by construction:** no markup, no JS, no selector, no layout/spacing/typography/icon/colour rule was modified — this phase only changed the *right-hand side* of `border-radius` and `box-shadow` declarations and added token definitions.
- **RTL:** radius tokens are corner-agnostic scalars; the only per-corner declarations (`0 0 16px 16px`, `22px 22px 0 0`, `0 4px 4px 0`) were tokenized in place without reordering, so RTL behaviour is exactly as before.

## 10. Recommendation for Sign-Off

**RECOMMEND SIGN-OFF for P4A**, conditional on the **manual visual gate** (5 workspaces × light/dark × RTL × amber/mezze) — the one check that cannot be automated here.

**Three items for the design owner to ratify:**

1. **Dark-mode `elev-1: none`** (§6) — approved as specified, but it removes shadow separation from the most-used elevation in dark. Confirm this is intended.
2. **Accent-glow retint** (§4) — resolves P1's deferred exception so glows follow the terracotta brand. Geometry unchanged; confirm the tint change is wanted in this phase.
3. **Two retained exceptions, documented rather than invented:** `--r-circle` (50%) and `--scrim-spotlight` (`rgba(8,5,1,.68)`) have **no approved equivalent**. The approved `--mz-scrim` exists but is far more transparent (.42), so substituting it would visibly weaken the tour spotlight — retained pending a source decision.

*Not in production behaviour — active only when `data-appearance="mezze"` is set. Motion, spacing and density not started.*
