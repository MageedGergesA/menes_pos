# Mezze design system — the in-app visual language

Canonical for `Mezze POS v3.dc.html`, `Mezze Online Ordering.dc.html`, and every screen built in
this project. **Modernist is not used in-app** — it is available only for artefacts outside the
product itself (decks, standalone docs) if ever requested. Do not introduce it into any `.dc.html`
screen.

## Type

| Role | Family | Notes |
|---|---|---|
| Latin UI text | **Hanken Grotesk** | weights 400/600/700/800 used across the app |
| Arabic UI text | **IBM Plex Sans Arabic** | matched weights; loaded alongside Hanken Grotesk, never substituted |
| Numerals, money, codes, refs | **JetBrains Mono** | every number, timestamp, order ref, PIN dot, ID |

Sizes never go below 10px for metadata, 11.5–13px for body/labels, 14–17px for card titles,
19–26px for KPI figures. Letter-spacing `.03–.08em` + uppercase on section labels only.

## Color

Warm-neutral palette via CSS custom properties — never hardcoded hex except `#FFFFFF` (card
surfaces) and a handful of semantic exceptions (`#2C5138` ok-state, `#FFFFFF`/certain overlays):

```
--color-bg            page background, warm off-white
--color-text           primary ink
--color-neutral-100…800   warm neutral ramp, light to dark
--color-accent          brand accent (used sparingly: warnings, CTAs, brand marks)
--color-accent-100…700   accent ramp — 100 for tinted backgrounds, 700 for text/icons on them
```

Rule followed throughout: **max one accent hue per screen**, everything else neutral. Status
color is semantic, not decorative — accent = attention/blocked, neutral-800/text = normal-but-firm,
`#2C5138`-family = success, never more than needed to make a state legible.

## Spacing, radius, elevation

- Radius tokens: `var(--r-sm)` (chips, small badges), `var(--r)` (default — buttons, rows, cards),
  `var(--r-lg)` (panels, sheets)
- No drop shadows as decoration; sheets/modals use a single soft shadow
  (`0 18px 44px rgba(38,34,28,.24)`) and nothing else
- Consistent padding rhythm: 6/8/9/11/13/14/16/20px — never arbitrary
- `gap` for every sibling layout (flex/grid), never margin-based spacing between repeated items

## Components (inline-styled, no CSS classes)

- **Tab strips** — pill row on `var(--color-neutral-200)`, active tab white with a subtle count
  badge in accent
- **KPI strips** — horizontal cards, `border-inline-end` dividers, JetBrains Mono figure + uppercase
  label + a one-line sub-caption
- **State chips** — `padding:3px 9px`, `border-radius:var(--r-sm)`, paired bg/border/text triads per
  semantic state (never color alone — always paired with a Material Symbols glyph + label)
- **Two/three-pane workspaces** — left list (fixed width 280–390px) · center detail (flex:1) ·
  right rail (fixed width 330–392px) — the layout every governance/ops screen in this project uses
- **PIN pad** — 3×4 numeric grid, dot indicators, JetBrains Mono digits
- **Icons** — Material Symbols only (`<span class="ms">`), never emoji, never custom SVG icon sets

## RTL / Arabic

- `dir="rtl"` flips the whole shell; `padding-inline-start/end` and `margin-inline-*` used
  throughout instead of left/right so mirroring is automatic
- **Arabic-Indic numerals** (٠١٢…) rendered via the shared `N()` helper on every number, date,
  time and money value — never raw JS string interpolation of a number
- Every user-facing string passes through `tr()` (or `trf()` for sentences with dynamic values —
  see `docs/AR_KEY_COLLISIONS.md`); **no string is ever assembled from separately-translated
  fragments** — a sentence with a number or a name in it gets one whole-sentence key with `{0}`
  holes, translated as one unit
- Money always renders through `M()` (branch currency conversion) composed with `N()`

## What Claude Code needs to reproduce this

1. Load Hanken Grotesk + IBM Plex Sans Arabic + JetBrains Mono as the only three font families
2. Reproduce the CSS custom property palette above as design tokens (light theme only; no dark
   mode exists in this product)
3. Implement `tr()`/`trf()`/`N()`/`M()` as real i18n + locale-numeral + currency functions backed
   by a translation table — the prototype's `PHRASES` object is the seed content for that table
4. Keep the two/three-pane workspace layout, the tab-strip pattern and the state-chip pattern as
   the three load-bearing UI patterns reused across every operational screen
5. RTL is not a mirrored stylesheet bolted on after the fact — build every new screen with logical
   (inline-start/end) properties from the start
