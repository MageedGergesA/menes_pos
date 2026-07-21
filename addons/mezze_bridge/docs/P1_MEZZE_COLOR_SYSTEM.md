# P1 — Approved Mezze Terracotta Color System (Flag-Gated)

*Appearance migration, **colour only**. Source of truth: `~/Downloads/Mezze POS Visual Redesign/export`. Amber remains the untouched default; the approved Mezze palette is opt-in behind `[data-appearance="mezze"]`. No layout / type / icon / motion / spacing / radius / structure / JS-behaviour change.*

## 1. Theme Implementation Summary

- **Architecture — two orthogonal axes:**
  - **Mode** (existing): `data-theme="light|dark"` (+ `prefers-color-scheme`) — the light/dark toggle, unchanged.
  - **Palette** (new): `data-appearance="amber"(default) | "mezze"` — the brand appearance.
- **Layer 1 — `--mz-*` primitives:** all 27 approved colour tokens, **dual-theme** (light + dark), defined under `:root[data-appearance="mezze"]` mirroring the existing 3-way structure (base + `@media dark` + explicit `[data-theme]`).
- **Layer 2 — semantic aliases:** under `[data-appearance="mezze"]`, the existing role tokens (`--accent`, `--canvas`, `--ink`, `--pos`, …) are re-pointed to the `--mz-*` primitives. **Components are unchanged** — they keep consuming role tokens; only the token *values* swap. This satisfies "no hardcoded colours" (everything resolves through tokens) and requirement #6 (future phases P2–P6 add `--font-*`/`--r-*`/`--dur-*` aliases under the same flag — no component rewrites).
- **Flag hook:** one guarded init line — opt-in via `?appearance=mezze` or `localStorage.mzAppearance='mezze'`; **default is amber (zero behaviour change).**
- **Diff:** `+52 / -0` (purely additive — amber CSS untouched). `node --check` OK; braces balanced.

## 2. Complete Colour Token Mapping

*Role token → approved `--mz-*` primitive (light / dark) → consumer count. All values EXACT from the export.*

| Role token (consumed by components) | → `--mz-*` (light / dark) | Consumers |
|---|---|--:|
| `--accent` | `--mz-brand` #C0602E / #D89A54 | 54 |
| `--accent-strong` | `--mz-brand-press` #984922 / #C98C48 | 41 |
| `--on-accent` | `--mz-on-brand` #FFFFFF / #1C1305 | 13 |
| `--accent-soft` | `--mz-brand-soft` #F6E9E0 / #3A2E1F | 30 |
| `--canvas` | `--mz-canvas` #FFFDFB / #191510 | 21 |
| `--surface` | `--mz-surface` #FFFFFF / #2A251D | 50 |
| `--surface-2` | `--mz-surface-2` #FAF6F0 / #332D23 | 55 |
| `--surface-3` | `--mz-surface-3` #EFE7DB / #3E362B | 9 |
| `--border` | `--mz-border` #EAE2D6 / #453E33 | 95 |
| `--border-strong` | `--mz-border-strong` #D6C7B2 / #5A4E3F | 28 |
| `--line` | `--mz-divider` #F1EBE1 / #332D23 | 31 |
| `--ink` | `--mz-text` #2A2420 / #F5F1EB | 67 |
| `--ink-2` | `--mz-text-2` #4A4038 / #E4DBCC | 48 |
| `--ink-3` (+`--muted`) | `--mz-text-mut` #786A57 / #B6AB9A | 128 |
| `--pos` / `--ok` | `--mz-ok` #2F7D4A / #5FB884 | 54 / 3 |
| `--pos-soft` | `--mz-ok-soft` #E6F1E8 / #1E332A | 11 |
| `--warn` | `--mz-warn` #B5842B / #E0B24C | 42 |
| `--warn-soft` | `--mz-warn-soft` #F6EDD8 / #352C18 | (color-mix) |
| `--crit` | `--mz-danger` #B0433A / #E58A82 | 41 |
| `--crit-soft` | `--mz-danger-soft` #F7E4E1 / #3A2420 | 6 |
| `--info` | `--mz-info` #2C6E8F / #6FB2D0 | 6 |
| `--info-soft` | `--mz-info-soft` #E2EEF3 / #1C2E38 | 2 |
| `--backdrop` (scrim) | `--mz-scrim` rgba(38,32,26,.42) / rgba(0,0,0,.62) | 1 |
| Focus ring | follows `--accent` → `--mz-brand` (= `--mz-focus`) | (`:focus-visible`) |
| `--mz-text-faint` #8A7E6E / #9A8C79 | built; no current 4th-tier consumer | 0 |
| `--mz-vip` #B08900 / #E5C558 | built; no current consumer | 0 |
| `--mz-brand-hover` #AC5427 / #E2A860 | built; current hover = brightness filter | 0 |

~**836** component consumer-sites recolour through the alias layer, **zero component edits**.

## 3. Accessibility Report (WCAG 2.2 AA, computed from exact approved values)

**Dark mode — ALL PASS** (10/10): text 16.1, text-mut 8.0, on-brand/brand 7.6, brand-text 7.5, ok/warn/danger/info on softs 5.5–7.0, focus 7.5.

**Light mode:**

| Pair | Ratio | AA (4.5 normal / 3.0 large·UI) |
|---|--:|---|
| text / canvas | 15.09 | ✅ |
| text-2 / canvas | 9.94 | ✅ |
| text-mut / canvas | 5.18 | ✅ |
| text-mut / surface-2 | 4.88 | ✅ |
| brand-press-as-text / canvas | 6.25 | ✅ |
| danger / danger-soft | 4.62 | ✅ |
| info / info-soft | 4.76 | ✅ |
| text-faint / canvas | 3.91 | ✅ large only |
| brand / canvas (focus ring, UI) | 4.18 | ✅ UI 3.0 |
| **on-brand(white) / brand (button label)** | **4.24** | ⚠️ FAIL normal / ✅ large-bold (button labels are ≥14px bold) |
| **brand-as-text / canvas** | **4.18** | ⚠️ FAIL normal / ✅ large·UI (use `--accent-strong`=brand-press 6.25 for small text) |
| **ok / ok-soft (badge)** | **4.36** | ⚠️ FAIL normal (badges are small-bold) |
| **warn / warn-soft** | **2.86** | ❌ FAIL (worst — muted gold on gold-cream) |

**These are properties of the *approved source values*, not implementation errors** — per the brief I used exact values and did **not** approximate/redesign. Findings for the design owner's awareness:
- On-brand-white / brand button text (4.24) and brand-as-text (4.18) pass at the **bold/large** sizes where they're actually used; small terracotta text should use `--accent-strong` (brand-press, 6.25 ✅).
- `ok/ok-soft` (4.36) and especially **`warn/warn-soft` (2.86)** are low for small badge text. **Flagged to the design source** — cannot be remediated in P1 without changing approved values (that would be a redesign).
- Focus visibility, disabled (opacity, unchanged), and all dark-mode states pass.

## 4. Remaining Colour Exceptions (documented, not redesigned)

1. **`--teal` (20) / `--violet` (26)** — the approved system defines **no teal/violet**. These retain their current amber-palette values under mezze (used for free-table/seat = teal, reserved/delivery = violet). *Not remapped — inventing a mapping would violate "do not invent colours." Awaiting a source decision.*
2. **Shadows `--shadow-sm/md/lg` + `--shadow-accent`** — elevation is out of P1 (colour-only) scope; retained (approved `--mz-elev-*` is a later elevation phase). `--shadow-accent` keeps an amber tint on terracotta buttons until then.
3. **`--on-color` (#fff)** — genuine on-colour white used on green/danger fills (correct in both modes); not aliased to `--mz-on-brand` (which is dark in dark-mode) to avoid dark text on coloured fills.
4. **Hardcoded `#fff`/`#000` (32)** — on-colour contrasts on coloured fills; correct in both palettes (white-on-colour). Brand-specific on-colour is handled via `--on-accent`.
5. **Built-but-unconsumed:** `--mz-text-faint` (no 4th ink tier in components), `--mz-vip` (no VIP UI), `--mz-brand-hover`/`-press` for *hover/press* (current hover = `filter:brightness()` which auto-adapts to terracotta; wiring components to the discrete hover/press tokens is a small follow-up requiring `:hover/:active` colour edits).

## 5. Before/After Screenshots

**Not captured** — the Chrome CDP bridge freezes on the heavy `pos.html` (persistent across all phases). Because P1 is **flag-gated and additive (amber default unchanged)**, "before" = the current certified amber build. **Manual visual sign-off gate:** open the app with **`?appearance=mezze`** and toggle light/dark on Cashier / Payment / Kitchen:
`…/mezze_bridge/static/pos.html?token=<token>&appearance=mezze`
Verify terracotta brand, warm canvas, and the semantic states; then repeat with `?appearance=amber` (or no flag) to confirm the amber build is byte-identical.

## 6. Regression Assessment

- **Amber build:** `+52/-0` additive diff → **no existing rule changed**; harness confirms amber tokens resolve to the exact original values (light `#E0982B`, dark `#EFA23C`, canvas/ink/pos/crit unchanged). **Zero regression risk to the certified build.**
- **Mezze build:** cascade verified (7/7) — semantic aliases resolve to `--mz-*` correctly in light **and** dark; the `[data-appearance]`×`[data-theme]` specificity/order is correct.
- **Behaviour:** flag reader is opt-in + guarded (default off); the light/dark toggle, business logic, and all workflows are untouched. `node --check` OK.
- **RTL:** colour-only change; no directional CSS touched → RTL unaffected in both palettes.

## 7. Sign-Off Recommendation

**RECOMMEND SIGN-OFF for P1 (colour system), conditional on:**
1. **Human visual review** of the mezze palette on Cashier / Payment / Kitchen in light + dark + RTL (CDP-blocked screenshots → manual gate).
2. **Design-source decision** on the flagged contrast items — chiefly **`warn/warn-soft` (2.86)** and the small-text uses of `ok/ok-soft` and brand-as-text — and on **teal/violet** (no approved equivalent). These are source-value questions, not implementation defects.

The implementation is **faithful (exact values), complete (all documented tokens), token-driven (no hardcoded colours, no component edits), fully flag-gated (amber preserved), and P2–P6-ready** (typography/icons/radius/motion/density swap under the same flag without touching components). Not committed to production behaviour — enabled only when the appearance flag is set.
