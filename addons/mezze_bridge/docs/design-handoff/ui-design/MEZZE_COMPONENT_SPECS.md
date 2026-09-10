# MEZZE COMPONENT SPECS

Reusable UI patterns extracted from `Mezze POS v3.dc.html`. No CSS classes exist in source — every value below is an inline style read from the template, or a computed value traced from the logic class (marked "traced"). Cross-references point to the screen doc that shows the component in full context; this file is the cross-screen index, not a duplicate of it.

## Button matrix

| Variant | Height | Padding | Font | Radius | Border | Background | States |
|---|---|---|---|---|---|---|---|
| Primary (Charge, Save, Confirm) | 52–64px | `0 18–22px` | 13–14.5px/700 | `var(--r)` | none/1px brand | `var(--color-accent)` or `var(--color-text)` | 4-state table in `01-pos-register.md` §6b for Charge specifically |
| Secondary (Cancel, Bill, More) | 44–52px | `0 12–18px` | 12–13px/600–700 | `var(--r)` | 1px `neutral-300` | `#FFFFFF` | active/inactive via bg swap to `neutral-100`/`var(--color-text)` |
| Destructive (Void line, delete) | 42–46px | `0 10–12px` | 11.5–12.5px/700 | `var(--r)` | 1px `accent-300` | `var(--color-accent-100)` | text color `var(--color-accent)` |
| Icon-only | 32–44px square | — | icon 14–22px | `var(--r)` | 0–1px | transparent or `#FFFFFF` | selected/armed states swap bg to `var(--color-accent)`/`var(--color-text)` |
| Segmented/toggle option | 36–44px | `0 12–14px` | 11–12.5px/500–700 | `var(--r)` | 0–1.5px | active `#FFFFFF`/`var(--color-text)`, inactive `transparent` | see per-screen active/inactive rules |
| Pill chip (filter, category, tab) | 34–44px | `0 10–14px` | 10.5–12.5px/600–800 | `var(--r)`/`var(--r-sm)` | 0–1.5px | computed per active state | count/meta text usually JetBrains Mono, dimmer color |

Source: Register action bar & category rail (`01-pos-register.md`), Floor toolbar (`02-floor.md`), Kitchen toolbar/layout tabs (`03-kitchen.md`).

## Card matrix

| Card type | Width | Min-height | Padding | Radius | Border | Shadow |
|---|---|---|---|---|---|---|
| Register product tile | grid-computed (`gridCols`) | — | `10px 12px 11px` (text block) | **14px literal** | 1px `neutral-300` | `0 1px 2px rgba(38,34,28,.04)` |
| Order line card | 436px panel width | auto | `11px 12px` | `var(--r-lg)` | 1px, color by selection | none default |
| KDS ticket (grid) | `D.gridMin` (306/248px) | auto | `D.pad` (13/9px) | `var(--r-lg)` | 1px, color by timing state | `0 1px 1px rgba(42,36,25,.04), 0 2px 6px rgba(42,36,25,.05)` |
| KDS ticket (lane/expo sub-column) | 236–252px fixed | auto | `9–11px` | `var(--r-lg)` | 1px, state-colored | same as grid |
| Floor selection/editor card | 320px (side panel) | auto | `12–18px` | `var(--r-lg)` | 1px `neutral-300` | none |
| Modal / sheet (Tender, Modifier, Approval, Numpad) | 352–640px | auto, max-height capped | `12–18px` | `var(--r-lg)` | 1px `neutral-300` | `0 18px 44px rgba(38,34,28,.22–.24)` |

## Chip / badge / pill matrix

| Kind | Size | Typography | Notes |
|---|---|---|---|
| Product badge (dietary/spicy/etc.) | pill, `3px 7px` | 9.5px/800, uppercase, letter-spacing .05em | pass-through per-item colors; 86'd state overrides to hardcoded `danger`/white |
| Status pill (line/table/ticket) | pill, `2–3px 6–8px` | 9.5–10px/700–800, uppercase | colors from the status-triplet system (`MEZZE_DESIGN_TOKENS.json` → `statusTriplets`), NOT the brand accent |
| Count badge (nav, category) | pill, min-width 16px | JetBrains Mono 9.5–11px/600–700 | `var(--color-accent)` bg + white text on nav; neutral on category |
| Allergen flag | pill or inline row | 10–11px/700–800 | own dedicated row on product tiles so it never truncates |
| Rush/priority flag | pill, `3–7px` | 10px/800, uppercase | `var(--color-accent)` bg, `neutral-100` text, `bolt` icon |

## Table / ticket / grid components

- **Product tile** — anatomy, states (86'd, favorite, by-weight): `01-pos-register.md` §6.
- **Order line** — anatomy, 3 mutually-exclusive expanded states (locked/editable/menu): `01-pos-register.md` §6.
- **Floor table token** — wood top, seat-dot geometry, status card: `02-floor.md` §6 (traced formulas for tile size, seat-dot layout, chair colors).
- **Fixture (floor editor)** — PNG-art rendering (tile/stretch/fit modes), selection outline only: `02-floor.md` §6 (fixture rendering, traced).
- **KDS ticket card** — 3 render contexts (grid/lane/expo), one shared state-color system: `03-kitchen.md` §10–11.
- **Data table** (Orders board, Reports, Stock, etc.) — not yet documented; pattern is: header row `neutral-400` uppercase labels, body rows `1px neutral-200` dividers, numeric columns right-aligned JetBrains Mono. Full spec pending those screens' docs.

## Form / input matrix

| Element | Height | Padding | Border | Notes |
|---|---|---|---|---|
| Text input (search, note, name) | 40–44px | `0 11–14px` | 1px `neutral-300` | placeholder `neutral-400`, no focus ring override beyond global `:focus-visible` |
| Numpad key | 52–58px | — | 1px `neutral-300` | JetBrains Mono 18–19px/700 |
| PIN dot box | 52px | — | 1.5px | JetBrains Mono 22px/700 |
| Stepper (qty) | 44px per button | 3px track padding | 1px `neutral-300` track | dec = `neutral-100` bg, inc = `accent-200` bg, icon-colored to match |

## Modal / drawer / sheet matrix

| Kind | Width | Position | z-index | Overlay |
|---|---|---|---|---|
| Modifier sheet | 640px | absolute, centered | (DOM order) | `rgba(38,34,28,.34)` |
| Numpad | 352px | absolute, centered | (DOM order) | `rgba(38,34,28,.34)` |
| Manager approval | 430px | **fixed**, centered | **40** | `rgba(38,34,28,.42)` |
| Tender (payment) | 520px | absolute, centered | 20 | `rgba(38,34,28,.42)` |
| Gift card tender | 560px | absolute, centered | 30 | `rgba(38,34,28,.46)` |
| Floor move dialog | 560px | absolute, centered | 25 | `rgba(38,34,28,.42)` |
| Floor push-to-branch dialog | 460px | absolute, centered | 26 | `rgba(38,34,28,.42)` |
| Delivery map (max) | flex-fill | absolute, inset:0 | 26 | `rgba(38,34,28,.5)` |
| Quick-actions sheet (in-panel) | fills order panel width minus 24px | absolute, above action bar | 6 | none (opaque card) |

All modals share: radius `var(--r-lg)`, `animation: mzIn .18–.22s ease both` (fade + 8px rise), white background, 1px `neutral-300` border.

## Source mapping
No CSS classes exist anywhere in this codebase — every visual property is inline, computed per-render from the logic class. To locate a component's real values, search the logic class for its prop-object name (e.g. `fxSkin(`, `kdsView(`, `flTileSize(`, `ST=`, `FL_STATES`, `this.K`) rather than looking for a stylesheet rule.
