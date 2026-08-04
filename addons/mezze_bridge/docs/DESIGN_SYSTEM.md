# Mezze POS — Design System

> **⚠ AUTHORITY CORRECTION (DESIGN-P2).** This document is a downstream translation and
> is **NOT** the primary visual authority. The **primary design authority** is the
> original *Mezze POS Visual Redesign* export (see
> `docs/design-consistency/AUTHORITATIVE-DESIGN-SYSTEM.md` +
> `PRECEDENCE-AND-CORRECTIONS.md`). Where this file disagreed with the source it had
> **drifted** — corrected facts:
> - **Brand = Terracotta `#C0602E` (light) / `#D89A54` (dark)** — *not* amber `#E0982B`.
> - **Fonts = Hanken Grotesk (interface) / IBM Plex Sans Arabic / JetBrains Mono** —
>   *not* `system-ui` / Noto Kufi. (`@font-face` lives in `static/design/foundation.css`.)
> - **Spacing = 4px lattice on 8px base**, primitives `0,2,4,6,8,12,16,20,24,32,48,72`
>   — *not* a scale ending at `40`.
> - **Radius = 8 / 11 / 14 / 16 / pill** — *not* 8/12/18/24.
> - **Namespace `--mz-`**, architecture primitive→semantic→component; colors/themes owned
>   by `static/mezze-design.css`, fonts/geometry/motion by `static/design/foundation.css`.
>
> The sections below remain useful as `pos.html` implementation notes, but the source
> above wins on any conflict.

*Original note: Source of truth for Claude Design and for Platform-Polish implementation on the vanilla `pos.html`. Values are the real tokens measured from the running app; component specs are the normalized ("premium") targets that resolve the audit's drift.*

---

## 1. Brand & Voice

**Mezze** — an enterprise Restaurant POS for MENA F&B (Egypt / Gulf). Warm luxury-hospitality, not a generic admin dashboard. Bilingual **English + Arabic (RTL)**. Runs on real hardware for **10-hour cashier shifts**.

**Aesthetic:** premium, minimal, warm, restaurant-focused — the feel of "Apple designing Toast POS." Amber/terracotta warmth on deep warm-neutral surfaces; never cold blue-grey SaaS.

**Design principles (in priority order):**
1. Speed over beauty — never slow the cashier.
2. Large touch targets (44px minimum), readable at arm's length.
3. Large totals; **tabular numerals everywhere** money or time appears.
4. Clear hierarchy: primary number → secondary → label → action → status.
5. Information first, decoration second. Max two clicks to any action.
6. Status is **never color alone** — pair with icon / label / sign / border.

---

## 2. Color Tokens (measured — light + dark, theme-adaptive)

Every color is defined for a warm **light** baseline and a warm **dark** theme. Neutrals are warm (tan/brown bias), not grey.

| Token | Light | Dark | Role |
|---|---|---|---|
| `--canvas` | `#EBE8E0` | `#131009` | app background |
| `--surface` | `#FFFFFF` | `#1C1810` | cards, panels |
| `--surface-2` | `#F6F3ED` | `#252016` | insets, chips |
| `--surface-3` | `#EDE8DE` | `#312A1E` | hover fills |
| `--border` | `#E1DBCC` | `rgba(255,240,210,.09)` | card borders |
| `--border-strong` | `#CDC5B2` | `rgba(255,240,210,.17)` | emphasis borders |
| `--line` | `#E9E4D8` | `rgba(255,240,210,.065)` | dividers |
| `--ink` | `#1E1A12` | `#F4EFE3` | primary text |
| `--ink-2` | `#5B5343` | `#BEB4A0` | secondary text |
| `--ink-3` | `#8B8370`\* | `#867D6A`\* | labels / muted |
| `--accent` | `#E0982B` | `#EFA23C` | brand amber (fills/borders) |
| `--accent-strong` | `#B4750F` | `#F6B65B` | accent text/emphasis |
| `--on-accent` | `#221806` | `#1A1305` | text on accent |
| `--on-color` | `#FFFFFF` | `#FFFFFF` | text on colored buttons |
| `--pos` (success) | `#1C9A60` | `#59C48D` | ready / paid / open |
| `--warn` | `#C46A16` | `#E9A54D` | preparing / caution |
| `--crit` (danger) | `#C1402A` | `#EA6A4C` | short / refund / late |
| `--info` | `#2563C9` | `#5B96F0` | tender / neutral info |
| `--violet` | `#6552CE` | `#8A7BF0` | dispatched / loyalty |
| `--teal` | `#0C8B81` | `#2FB2A8` | secondary accent |

Each semantic color has a **`-soft`** background pair (≈13–16% alpha): `--accent-soft`, `--pos-soft`, `--warn-soft`, `--crit-soft`, `--info-soft`, `--violet-soft`, `--teal-soft`. Backdrop: `--backdrop` (translucent scrim).

\* **Accessibility note:** `--ink-3` measures **3.76:1** (light) / 4.34:1 (dark) on surface — below WCAG AA 4.5 for small text. In the design system, use `--ink-3` only for ≥bold or ≥14px labels; use `--ink-2` for small secondary body text. Status colors (`--warn` 3.87, `--pos` 3.60 light) are for fills/badges/large-bold text, **not** small body text on white.

---

## 3. Typography

- **UI font:** `system-ui, -apple-system, "Segoe UI", Roboto, "Noto Kufi Arabic", "Helvetica Neue", sans-serif` (Noto Kufi Arabic carries RTL).
- **Numeric font:** `ui-monospace, "SF Mono", "JetBrains Mono", "Roboto Mono", Menlo, monospace` — **tabular**, for all money/time/counts.
- **Weights:** 600 (label), 700 (default), 800 (emphasis/number). No light weights.

**Type scale (rationalized — collapses 32 ad-hoc sizes to 10 steps):**

| Token | Size | Use |
|---|---|---|
| `--text-4xl` | 31px / 800 | KPI hero value, display |
| `--text-3xl` | 26px / 800 | screen totals (variance, refund total) |
| `--text-2xl` | 20px / 800 | H1 / section number |
| `--text-xl` | 18px / 800 | H2 / branch name |
| `--text-lg` | 16px / 800 | card title / large value |
| `--text-md` | 14px / 700 | body strong / button |
| `--text-base` | 13px / 600 | body |
| `--text-sm` | 12px / 600 | small |
| `--text-xs` | 11px / 800 | **uppercase eyebrow label** (letter-spacing .05em) |

Eyebrow labels: 11px, uppercase, `letter-spacing:.05em`, `--ink-3`. Big numbers: tabular, `letter-spacing:-.02em`, weight 800.

---

## 4. Spacing (4px base)

`--space-1:4  --space-2:8  --space-3:12  --space-4:16  --space-5:20  --space-6:24  --space-7:32  --space-8:40`

Card padding 16 (`--space-4`); panel padding 20–24; modal padding 22–24; button padding `0 20`; gaps 8–12. **Snap to the scale — avoid 5/7/9/11/13.**

## 5. Radius

`--r-sm:8  --r-md:12  --r-lg:18  --r-xl:24  --r-pill:999`

Buttons/inputs → `--r-md` (12) · cards → `--r-lg` (18) · modals → `--r-xl` (24) · badges → `--r-sm` (8) · chips/pills → `--r-pill`.

## 6. Elevation (shadows)

- `--shadow-sm` — cards resting: `0 1px 2px / 0 1px 3px` warm-black.
- `--shadow-md` — hover lift / popovers.
- `--shadow-lg` — modals: `0 20px 48px` (light) / `0 26px 60px` (dark).
- `--shadow-accent` — amber glow on primary CTA (sparingly).

## 7. Motion

`--dur-fast:130ms  --dur-base:160ms  --dur-slow:220ms` · `--ease-standard:cubic-bezier(.2,.8,.3,1)` · `--ease-spring:cubic-bezier(.2,1.4,.4,1)`.

All interactions 130–220ms. Hover lift `translateY(-1px)`; press `scale(.97)`; modal entrance `translateY+scale` at `--dur-slow`. **Honor `prefers-reduced-motion`.** Never animate an entire poll-refreshed view.

## 8. Z-index ladder

`--z-base:1  --z-dropdown:20  --z-sticky:30  --z-overlay:50  --z-sheet:52  --z-modal:60  --z-toast:120`

---

## 9. Components (normalized "premium" specs)

**Button** — one family, variants by color. Height **44** (compact) / **50** (primary bar). Radius `--r-md`. Padding `0 20`. Font `--text-md`/700. Icon gap 8. Press `scale(.97)` @ `--dur-fast`. Focus: 2.5px `--accent` ring. Disabled: opacity .45.
- `primary` = `--accent` + `--on-accent` · `success/pos` = `--pos` + `--on-color` (confirm/pay) · `dark` = `--ink` + `--canvas` · `ghost` = `--surface-2` + border · `danger` = `--crit`.

**Status badge** — one component, state modifiers. Height ~24. Padding `4 9`. Radius `--r-sm`. Font `--text-xs` (11) uppercase, weight 800, letter-spacing .04. State = `-soft` bg + solid color + optional 1px border. Always accompanied by text label (never color-only).

**Card** — `--surface`, 1px `--border`, radius `--r-lg`, padding `--space-4`, `--shadow-sm`. Optional 4px inline-start status stripe for state (preparing=warn, ready=pos, dispatched=violet).

**KPI tile** — value `--text-4xl` tabular/800; label `--text-xs` uppercase eyebrow; optional delta row (up=`--pos`, down=`--crit`). Reused across HQ / Reports / Live Ops.

**Modal / Overlay** — radius `--r-xl`, `--shadow-lg`, `--backdrop` scrim, entrance `--dur-slow`. Widths: sm 440 / md 600 / lg 920 / pay 960. `role="dialog"`, `aria-modal`, focus-trap, Esc-closes.

**Input** — height **44**, radius `--r-md`, 1px `--border`, `--surface` bg. Placeholder `--ink-3`. Focus: **keep the 2.5px `--accent` ring** (do not `outline:none`). Numeric inputs tabular.

**Number stepper** — 44px row, `--r-md`, +/− buttons ≥44 hit area, press feedback `--dur-fast`.

**Chip / filter** — pill (`--r-pill`), height 44, `--surface` / `--surface-2`, selected = `--accent-soft` + `--accent-strong`.

**Toast** — `--surface`, `--shadow-md`, radius `--r-md`, `--z-toast`, `aria-live="polite"`. Success accent `--pos`, error `--crit`.

**Icons** — line icons, stroke-width **2**, sizes **16 / 18 / 20 / 24** only (from a 4-step token set). 14px for dense inline, 40+ for empty-state heroes.

---

## 10. Accessibility contract

- Global visible focus ring: `2.5px solid --accent`, offset 2px (applies to **all** interactive elements, incl. inputs).
- **44px** minimum touch on every interactive control.
- Text contrast ≥ 4.5:1 (normal) / 3:1 (large) — see §2 note on `--ink-3`/status colors.
- Full **RTL**: logical properties (`inset-inline`, `margin-inline`), `dir="rtl"`, Noto Kufi.
- `prefers-reduced-motion` fully honored.
- Status conveyed by **icon + label + color + sign**, never color alone.
- Modals: `role="dialog"` + `aria-modal` + focus-trap + Esc.

---

*Implementation note: Mezze is vanilla HTML/CSS/JS on Odoo (no React/Tailwind). Use this system to generate on-brand designs in Claude Design; visual decisions get implemented as CSS tokens/rules on `pos.html` — preserving all workflows, APIs, routes, IDs, classes, and handlers.*
