# Mezze POS — Design Compliance Report

*Source of truth: `~/Downloads/Mezze POS Visual Redesign/export` (40 approved spec HTML files). Target: current implementation `mezze_bridge/static/pos.html`. Scope: identify every visual mismatch — no redesign, no invented improvements. Analysis only; no code changed.*

## 0. Headline Verdict

**NON-COMPLIANT at the foundation level.** The approved redesign is the frozen **`--mz-*` terracotta** design system (Hanken Grotesk / JetBrains Mono / IBM Plex Sans Arabic, Material Symbols icons, warm near-white canvas, density scaling, dual-theme). The current build is the **amber `#E0982B`** system (system fonts, 104 inline SVGs, `--space-1..8`, no density). These are **two different design systems**. Because every component and screen inherits the foundation, essentially **100% of surfaces render differently** from the approved source. This is the appearance migration the program explicitly deferred as "flag-gated, appearance-changing."

**Nothing here is a defect in the current build** — it is a fully-verified, self-consistent system; it simply predates / diverges from the now-approved terracotta redesign.

## 1. Source Inventory (what the export contains)

- **Foundation/design-system (visual scope):** Mezze Design System, Typography System, Spacing System, Motion System, Foundation Engine.
- **Component specs:** Primitive Library, Compound Library, Mezze Component Library/Language, Workspace Library.
- **Workspace/screen specs:** Application Shell, Cashier Order Screen, Cashier Workspace Pro/Specification, Payment Workspace, Kitchen Workspace, Admin Console, Settings.
- **Platform/service specs (out of *visual* scope — backend/product):** AI, Search, Notification, Payment/Order/Tax/Discount/Printing/Permission/Sync/Offline Engines, Multi-Tenant SaaS Platform, Restaurant Configuration, SDK, Freeze Packs.
- Token convention: canonical `--mz-*` + bare aliases; **dual-theme** (every token has light+dark values); **density-scaled** spacing.

## 2. COLOR — Compliance Matrix

| Role | Approved (`--mz-*`, light / dark) | Current (`:root`) | Verdict |
|---|---|---|---|
| Brand | `--mz-brand` **#C0602E** / #D89A54 (+ hover #AC5427, press #984922, soft #F6E9E0/#3A2E1F) | `--accent` **#E0982B** / #EFA23C (+ strong #B4750F) | **MISMATCH** — terracotta vs amber; **no hover/press tokens** in current |
| On-brand | #FFFFFF / #1C1305 | `--on-accent` #221806 | MISMATCH |
| Canvas | `--mz-canvas` **#FFFDFB** / #191510 | `--canvas` **#EBE8E0** | MISMATCH (warm near-white vs mid beige) |
| Surface tiers | text/text-2/mut/faint 4-tier | surface/surface-2 + ink/ink-2/ink-3 3-tier | STRUCTURAL DIFF |
| Text | `--mz-text` #2A2420, `-2` #4A4038, `-mut` #786A57, `-faint` #8A7E6E | `--ink` #1E1A12, `-2` #5B5343, `-3` #8B8370 | MISMATCH (4 vs 3 tiers, all values differ) |
| Border / strong / divider | #EAE2D6 / #D6C7B2 / #F1EBE1 | #E1DBCC / #CDC5B2 / #E9E4D8 (`--line`) | MISMATCH (near, not equal) |
| Success | `--mz-ok` **#2F7D4A** / soft #E6F1E8 | `--pos` **#1C9A60** (+ `--ok` #2f9e6b) | MISMATCH (darker green; two success greens in current) |
| Danger | `--mz-danger` **#B0433A** / soft #F7E4E1 | `--crit` **#C1402A** | MISMATCH |
| Warn | *(no separate warn — brand/danger carry it)* | `--warn` **#C46A16** | STRUCTURAL DIFF (current has an extra semantic) |
| Info | `--mz-info` **#2C6E8F** / soft #E2EEF3 | `--info` **#2563C9** | MISMATCH (teal-blue vs royal blue) |
| Violet / Teal | *(not in approved core)* | `--violet` #6552CE, `--teal` #0C8B81 | Current has non-approved semantics |
| Focus | `--mz-focus` #C0602E | (uses `--accent` via `:focus-visible`) | MISMATCH (color) |

**Summary:** every brand and semantic colour differs; the current palette is missing brand hover/press states and adds non-approved semantics (violet/teal/separate-warn/second-success).

## 3. TYPOGRAPHY — Compliance Matrix

| Aspect | Approved | Current | Verdict |
|---|---|---|---|
| Text font | **Hanken Grotesk** (`--mz-font-text`) | `--font-ui` = system-ui/-apple-system/Segoe/Roboto/Noto Kufi | **MAJOR MISMATCH** — brand font **not loaded** |
| Numeric font | **JetBrains Mono** (primary) | `--font-num` = ui-monospace → JetBrains only as *fallback* | PARTIAL — not the primary/loaded face |
| Arabic font | **IBM Plex Sans Arabic** (`--mz-font-ar`) | Noto Kufi Arabic (in the UI stack) | MISMATCH |
| Icon system | **Material Symbols Rounded** (icon font) | **104 inline `<svg>`** | **MAJOR ARCHITECTURAL MISMATCH** |
| Type scale | `--mz-size-100..900` = **11/12/13/15/18/22/26/32/40** | `--text-xs..4xl` = 11/12/13/**14/16/20**/26/**31** | MISMATCH at 4 of 9 steps (15≠14, 18≠16, 22≠20, 40≠31) |
| Weight tokens | regular 400 / medium 500 / semibold 600 / bold 700 / extrabold 800 | ad-hoc (no weight tokens) | STRUCTURAL DIFF |
| Leading tokens | tight 1.2 / normal 1.4 / relaxed 1.55 / **ar 1.7** | ad-hoc line-heights; **no Arabic-specific leading** | MISSING |

## 4. SPACING & DENSITY — Compliance Matrix

| Aspect | Approved | Current | Verdict |
|---|---|---|---|
| Scale | `--mz-space-000..1200` = **0/2/4/6/8/12/16/20/24/32/48/72** (12 steps) | `--space-1..8` = 4/8/12/16/20/24/32/40 (8 steps) | MISMATCH — missing 2/6/48/72; off-by-scale |
| **Density** | `--mz-density` **.8 / 1 / 1.25** (compact/comfortable/spacious) multiplier on all spacing | **NONE** | **MISSING FEATURE** |
| Semantic spacing | `--mz-pad-card/panel/dialog`, `--mz-gap-grid`, `--mz-inline-sm/md` (density-scaled) | raw px values | MISSING |

## 5. RADIUS / MOTION / ELEVATION — Compliance Matrix

| Aspect | Approved | Current | Verdict |
|---|---|---|---|
| Radius | sm 8 / **md 11** / **lg 14** / **xl 16** / pill 999 | sm 8 / **md 12** / **lg 18** / **xl 24** / pill 999 | MISMATCH at md/lg/xl |
| Motion durations | instant 80 / fast 120 / mod 180 / slow 240 / deliberate 320 ms (5 steps) | fast 130 / base 160 / slow 220 ms (3 steps) | MISMATCH (scale + step count) |
| Easing | accelerate `(.4,0,1,1)` / decelerate `(0,0,0,1)` / spring `(.5,1.4,.5,1)` / standard `(.2,0,0,1)` | standard `(.2,.8,.3,1)` / spring `(.2,1.4,.4,1)` | MISMATCH (different curves; 2 vs 4 named) |
| Elevation/shadows | `--mz-elev-1/2/3` warm-tinted `rgba(42,36,32,…)` | `--shadow-sm/md/lg` neutral `rgba(0,0,0,…)` | MISMATCH (warm vs neutral) |
| Reduced motion | durations collapse to 1ms | global `*{animation/transition:.001ms}` | EQUIVALENT ✅ |

## 6. COMPONENTS — Structural Compliance

The approved system is a **4-tier library** (Primitive → Compound → Component → Workspace) with a formal naming language (e.g., *IconButton*, *Product Card*, *Quantity Stepper*, …). The current build has **6 extracted primitives** (`.button`, `.segment`, `.input`/`.textarea`, `.status-badge`, `.empty-state`, `.stepper`) plus domain-specific controls.

| Approved concept | Current equivalent | Verdict |
|---|---|---|
| Brand button (terracotta + hover/press states) | `.button--primary` (amber, no press token) | RESKIN + state-token gap |
| IconButton (Material Symbols) | `.iconbtn` + inline SVG | ICON-SYSTEM MISMATCH |
| Quantity Stepper | `.stepper`/`--lg` | naming + token reskin |
| Product Card | `.prod` | reskin (colour/radius/type/shadow) |
| Segment / Chip / Badge / Input / Dialog / Toast | `.segment`, `.chip`, `.status-badge`, `.input`, `.overlay .modal`, `.toast` | present but reskin required |
| **Density-aware components** | — | **MISSING** |
| **Material-Symbols icon component** | — | **MISSING** (SVG-based) |
| Formal weight/leading/elevation tokens on components | ad-hoc | GAP |

**Missing vs present:** no component is structurally *absent* for the core POS, but **every component needs a reskin** to the approved tokens, plus **two capabilities are missing** (density system, icon-font system). A full per-component pixel audit is a follow-on to token alignment (deferred until §8-P1..P4 land, since each component inherits the foundation).

## 7. LAYOUT / WORKSPACES — Structural Compliance

- The approved export is a **multi-tenant SaaS** product (Application Shell, Admin Console, Settings, Multi-Tenant SaaS spec, tenant theming). The current build is **single-tenant Odoo POS**. → Tenant/theming shell, Admin Console, and Settings surfaces are **out of the current scope** (product-level, not just visual).
- Cashier Order Screen / Workspace Pro / Payment / Kitchen specs map to current `#view-pos` / `#ov-pay` / `#view-kds`. The **regional structure is broadly analogous** (catalog + ticket + checkout; column-per-ticket KDS), but each renders under the mismatched foundation → **visually non-compliant even where layout matches**.
- A per-screen pixel-diff is only meaningful **after** the foundation is aligned; before that, the delta is dominated by colour/type/icon/spacing, not layout.

## 8. Implementation Plan — ordered by Impact × Risk

*Principle: align the **token foundation first** (highest visual coverage, mechanical), then typography/icons (dependency + effort), then component/screen verification (cascades). Each phase behind a flag, pixel-diffed, reversible — same discipline as the design program.*

| # | Work | Impact | Risk | Notes / dependencies |
|---|---|---|---|---|
| **P1** | **Brand + semantic colour remap** to `--mz-*` palette (terracotta, hover/press/soft, canvas/text/border tiers, ok/danger/info, focus) | **Highest** (recolours 100% of surfaces) | **Med** | Mechanical if primitives consume tokens; must add missing hover/press/soft tiers and reconcile current extras (violet/teal/warn/2nd-success). Dual-theme values already provided. |
| **P2** | **Typography** — load & apply Hanken Grotesk + JetBrains Mono + IBM Plex Sans Arabic; remap type scale (9-step), weight tokens, leading tokens incl. Arabic 1.7 | High | **Med-High** | **Adds a font dependency** (currently 0 deps) — self-host/`@font-face`; type-scale change **moves pixels app-wide**; RTL Arabic leading. |
| **P3** | **Icon system** — migrate 104 inline SVGs → **Material Symbols Rounded** | High (visual) | **High** | New icon-font dependency; per-icon name mapping, sizing/optical-alignment; largest mechanical effort. Consider keeping SVG fallback. |
| **P4** | **Radius / motion / elevation** remap (md 11/lg 14/xl 16; 5-step durations + 4 eases; warm shadows) | Med | **Low** | Value remap; low regression risk. |
| **P5** | **Spacing scale + density system** — adopt the 12-step `--mz-space-*` + `--mz-density` multiplier + semantic pad/gap tokens | Med | **Med** | Re-tokenizes spacing (the deferred appearance work); density is a new capability; verify no layout breakage per view. |
| **P6** | **Component library alignment** — reconcile the 6 primitives with the Primitive/Compound/Component tiers; add density-awareness + icon-font component | Med | **Med** | Per-component reskin verification once P1–P5 land. |
| **P7** | **Per-workspace pixel parity** — Cashier / Payment / Kitchen vs the approved workspace specs | Med | **Low-Med** | Cascades from tokens; verify layout deltas screen-by-screen with visual sign-off. |
| **P8** | *(out of visual scope)* Multi-tenant shell, Admin Console, Settings, tenant theming; the service/engine specs | — | — | **Product/platform work, not a visual-compliance task.** Flag for product decision. |

**Sequencing rationale:** P1 (colour) gives the largest visual convergence for the least risk and unblocks meaningful screenshots; P2/P3 (fonts/icons) carry the dependency + effort risk and should be flag-gated and separately signed-off; P4/P5 are token remaps; P6/P7 are verification passes that only make sense after the foundation matches. P8 is a scope question, not a compliance fix.

## 9. Risk & Governance Notes

- This is a **deliberate appearance change** (a redesign migration), not a bug-fix — it changes 100% of the visual output *by design*. It should run **flag-gated** (e.g., `--mz-*` behind a theme switch) so the current, certified amber build remains the fallback until the terracotta system is signed off.
- **New dependencies:** P2/P3 introduce web fonts + an icon font — the build is currently **0-dependency / self-contained (~102 KB gzip)**. Self-hosting the fonts (no CDN) preserves the offline/CSP posture; budget the added weight.
- **Verification:** the CDP screenshot bridge has frozen on the heavy page throughout — each phase needs **human visual sign-off** in light + dark + RTL against the approved spec files.
- **No code was changed and no commit was made in producing this report.**

## 10. Bottom Line

The current build is **fully non-compliant** with the approved terracotta redesign because it *is a different, self-consistent design system*. Bringing it into compliance is a **foundation-first token/typography/icon migration** (P1→P7), high in visual impact and cleanly sequenceable by risk, behind a flag, with per-phase visual sign-off. The platform/multi-tenant/service specs in the export (P8) are product scope, not visual compliance, and need a separate decision.
