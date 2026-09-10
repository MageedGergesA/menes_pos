# Screen 01 — Register: visual difference register

Every visual difference between the frozen design's Register and what
`/mezze/pos` renders, one row each.

**Design source.** `docs/design-handoff/Mezze POS v3.dc.html` — the app shell at
lines 44–125 and the `isRegister` block at lines 126–710. Values quoted are the
literals in that file. Where the design computes a value at runtime
(`{{ chargeBg }}`, `{{ l.bd }}`, `{{ b.bg }}`) the row says `UNKNOWN — runtime`
rather than guessing.

**Our source.** The working tree at `feature/split-bill-v2`, which is **dirty**:
`cart.js/xml`, `product_grid.js`, `root.xml`, `cashier.css` and the four
`design/*.css` files all carry uncommitted changes. Rows below describe the
working tree, not `HEAD`.

**Theme.** Our values are the `classic` light ramp from
`static/mezze-design.css`, which is what `views/cashier_templates.xml` stamps by
default (`data-mz-theme="classic"` `data-mz-mode="light"`).

**Not rediscovered here.** Everything already carried in `GAP_REGISTER.md` §8
(S1-01…S1-11), §8b's element tables and §8c's affordance walk. This register is
the residue: what is still different after those closed.

**Token coverage.** A design value with no counterpart in
`docs/design-handoff/ui-design/MEZZE_DESIGN_TOKENS.json` is marked **[no token]**
in the Design column. There are 31 of them, listed in §12.

Effort: **S** one value · **M** a rule set or small markup change · **L** a new
component, new data, or behaviour.

**✅ = implemented.** Two passes have closed §3 (product grid and card) and §6
(totals block) at S and M effort: rows 26, 28–38, 40, 41, 43–48, 50–54, 57–59,
109–116, 119. Every one was verified in Chrome against `mezze_show` at 1854px in
the `classic` light theme, not just read back from source.

Colour literals from the design live in a
`:root[data-appearance="mezze"][data-mz-theme="classic"]` block at the foot of
each stylesheet, so dark and High-Contrast still resolve through our own tokens.

Rows in that range **not** implemented, each still open above:

| Row | Why not |
|---|---|
| 27 ✅ | The cap is `max-width:{{ gridMax }}` — a runtime value. (Worth noting: `ProductGrid._layout()` already sets an inline `max-width` from the design's own model, so this row's "Ours" column describes only the CSS fallback.) |
| 39 | **Held for a ruling** — §11 item 15. The design's Options affordance is a bordered button; ours is a label. Row 38 rebuilt the row around it, so converting it later is a self-contained change. |
| 42 ✅ | Badge fills are `{{ b.bg }}/{{ b.col }}` — runtime. |
| 49 ✅* | Density selected state is `{{ m.bg }}/{{ m.col }}/{{ m.bd }}` — runtime. |
| 55 ✅ | The placeholder is `{{ L.searchPh }}`, a translated label. The English string is quoted only second-hand in `GAP_REGISTER.md` §8b and with a leading ellipsis, so the exact text is not recoverable from the design source. |
| 117 ✅ | Total amount colour is `{{ bigCol }}` — runtime. |
| ~~118~~ | ~~Splitting the currency into its own span needs the formatter in `cart.js`~~ — **done later in the campaign**: `cart.js` gained `amountOnly()` and a currency getter, the same split row 37 made on the product tile. |

**The `UNKNOWN — runtime` bucket was too large.** The audit read the design's
markup block (lines 126–710) but not the model that feeds it. Every
`{{ … }}` placeholder in this register resolves to a literal a few thousand lines
further down the same file, so the values were recoverable all along:

| Row | Placeholder | Design source | Resolves to |
|---|---|---|---|
| 4 | `{{ railLabelSize }}` | `:37941` | `12.5px` expanded, `9.5px` collapsed |
| 14 ✅* | `{{ k.iconCol }}` | `:34383` | brand when active, `#C08A2E` for Favourites, else `accent-400` `#8C8579` **[no token]** |
| 15 ✅ | `{{ k.fw }}` / `{{ k.col }}` | `:34384` | `700`/brand active, `500`/`neutral-800` otherwise |
| 16 ✅ | `{{ catsCountSize }}` | `:37949` | `11px` expanded, `9px` collapsed |
| 17 ✅ | `{{ k.bg }}` | `:34384` | `accent-200` `#F0E4D8` — our `--mz-brand-soft`, so the fill was already right; only the ink was wrong |
| 21 ✅* | `{{ d.bg/col/bd }}` | `:34388` | selected = `--color-text` fill, `#FFFFFF` ink, `--color-text` border; otherwise white on `neutral-300` |
| 27 | `{{ gridMax }}` | `:39435` | `cols × maxTile + (cols−1) × 14` — the same 14px gutter row 26 was ruled on |
| 42 | `{{ b.bg }}/{{ b.col }}` | `:20918` | brand badge = accent + white; portion badge = `--color-text` + white; **low-stock = `neutral-700` `#645E52` + white**, not an amber |
| 49 | `{{ m.bg/col/bd }}` | `:34392` | identical to row 21 — selected is ink-filled |
| 55 | `{{ L.searchPh }}` | `:37606` | `Search menu, barcode or PLU — press /` |
| 91 / 108 | `{{ l.bd }}/{{ l.bg }}` | `:34457` | `neutral-200` on white; selected `accent-300` `#DCC6AE` on `accent-100` `#FFF9F0` **[no token]** |
| 93 ✅ | `{{ l.qtyCol }}` | `:34457` | `neutral-800`, brand when selected |
| 117 | `{{ bigCol }}` | `:39473` | `--color-text` — **ink, not brand** — and `warn` only when a balance is due |
| 123 ✅ | `{{ chargeSh }}` | `:39483` | `0 2px 8px rgba(181,101,46,.28)`, `none` when blocked |
| 124 ✅ | `{{ chargeBd }}` | `:39481` | brand, `neutral-300` when settled or blocked |
| 128 ✅ | `{{ chargeSize }}` | `:39478` | `17px`, `15px` when blocked |

`rgba(181,101,46,…)` in the charge shadow is `#B5652E` — the same brand literal the
palette ruling adopted, which is independent confirmation that the ruling was right.


**59 ✅\*** is partial: the chip is now dashed and typeset as the design has it,
but the design also puts an `add` glyph before the label. That needs a codepoint
from `static/src/shell/icons.js`, which no row in this range names, so it was
left alone rather than risking a literal word on the control.

**A defect this work introduced, and how it was found.** The row 112 edit left a
CSS comment unterminated in `design/order-panel.css`, so prose sat outside the
comment. Chrome's error recovery skipped it and **LTR looked perfect** — but
`rtlcss`, which Odoo shells out to when it builds the `.rtl.css` variant for an
Arabic session, aborts on a parse error and emits **nothing**. Every Arabic
Register, kiosk and storefront was therefore being served an empty stylesheet.
The suite caught it three times over (`test_cashier_browser.test_05`,
`test_media_preferences.test_14`, `test_quick_add.test_12`) and every one of them
looked environmental at first: the body font read "Times New Roman" and the
quick-add stopped mirroring, both of which are what "no CSS at all" looks like.

Fixed, and every stylesheet in the addon now round-trips through `rtlcss` cleanly.
**Worth a guard:** a test that runs `rtlcss` over the bundle would have caught this
in seconds, and it is the same class of silent failure `test_icon_subset` already
exists to prevent.

**Two assumptions made in the M pass**, both worth a look:

* **Row 113.** The design gates its collapse control behind a `hasSumToggle`
  flag whose condition is computed in the prototype and not recoverable. Ours
  offers it whenever there is something to collapse — a breakdown row or a
  service charge — and defaults to OPEN, because a bill that hides its own tax
  until asked is the failure the VAT row exists to fix.
* **Row 46.** The design's pill label is `{{ L.byWeight }}`, runtime. Ours reads
  "By weight". The geometry, glyph and placement are the design's.

---

## 1. Left rail

| # | Design | Ours | Change here | Effort |
|---|---|---|---|---|
| 1 ✅ | Rail item is a flex row/column whose height comes from `{{ railItemH }}` and padding from `{{ railItemPad }}`, so the item can never exceed the rail | Item is fixed `width:64px; height:51px` inside a `width:48px` rail — 8px overflows each side and is clipped by the group's `overflow-x:hidden` | `static/src/shell/rail.css:18` (rail), `:43` (item) | S |
| 2 ✅ | Item radius `var(--r)` = 11px | `border-radius:12px` | `static/src/shell/rail.css:44` | S |
| 3 ✅ | Item icon is a Material Symbol at `font-size:21px` | ~~No icon element at all~~ **corrected:** there IS one — `.mz-rail__ico`, a hand-drawn inline `<svg>` at 20px built in `rail.js`. A second icon language beside the one the design specifies, which `domain-docs/MEZZE_DESIGN_SYSTEM.md` rules out by name | `static/src/shell/rail.js`, `rail.css:41-49` | M |
| 4 | Label size is `{{ railLabelSize }}`, weight `{{ r.fw }}` (varies with active state) | `font-size:10px; font-weight:600`, constant | `static/src/shell/rail.css:48` | S |
| 5 ✅ | Badge: `top:5px; inset-inline-end:9px; min-width:16px; height:16px; border-radius:var(--r-sm)` = 6px, `font-size:9.5px; font-weight:700` | `top:4px; inset-inline-end:6px; min-width:16px; border-radius:999px; font-size:9.5px; font-weight:800; line-height:16px` | `static/src/shell/rail.css:86-92` | S |
| 6 ✅ | Rail carries a **collapse/expand toggle** at its foot: `min-height:44px`, radius `var(--r)`, white fill, 1px neutral-300 border, glyph 19px + caption 11.5px/600 | Absent — the rail has no collapse control | `static/src/shell/rail.xml` | M |
| 7 ✅ | Rail foot carries a two-line note: `{{ L.railNote }}` / `{{ L.roleFiltered }}` at `font-size:9px`, `color:neutral-400`, `line-height:1.4`, centred (design line 122) — e.g. "9 of 13 role-filtered" | Absent | `static/src/shell/rail.xml` | M |
| 8 ✅ | Rail dividers between groups: `height:1px; background:neutral-300; margin:8px 14px` | No inter-group divider; only a `border-top` on `.mz-rail__foot` | `static/src/shell/rail.css:39-40` | S |
| 9 ✅ | Rail background is `--color-neutral-100` (#F5F3EF), one step off the page | `background:var(--mz-surface)` = #FFFFFF — the rail is the same white as the cards | `static/src/shell/rail.css:19` | S |
| 10 ✅ | No avatar in the rail; the operator lives in the top bar | `.mz-rail__avatar` — a 34px circle at the rail foot | `static/src/shell/rail.css:62-66` | S |

## 2. Category nav

| # | Design | Ours | Change here | Effort |
|---|---|---|---|---|
| 11 ✅ | Column padding `12px 10px`, row gap `2px` | `padding:12px 12px` (`--mz-space-150` both axes), list gap `4px` | `static/design/category-nav.css:51`, `:73` | S |
| | ↳ **Follow-on: six tests re-pinned.** The design's column is **222px total**; the padding change moves the content basis from 197 to 201 and leaves the total exactly where it was (`201 + 20 + 1 rule = 222`). `test_category_nav_shared.py` asserted the *basis* at six places, so it failed on arithmetic, not on regression. Basis assertions now read 201 and the **222px total** is asserted alongside them, because the total is the invariant the four-column geometry depends on. | | `tests/test_category_nav_shared.py:87`, `:205-209`, `:297-300`, `:402-404`, `:421` | S |
| 12 ⛔ | The "CATEGORIES" caption is itself a **44px tappable header row** carrying the collapse toggle glyph (18px, `accent-400`) | A plain `<p>` caption; no collapse control. **Blocked on row 14:** the design's collapsed sidebar is ICON-ONLY, and our rows carry no icon. Collapsing without one leaves a column of blank 44px rows, so the toggle cannot do what the design's does until 14 is solved — and 14 needs a glyph per category, which is branch data nobody has configured | `static/src/cashier/root.xml:250`, `category-nav.css:68-72` | M |
| 13 ✅ | Caption `font-size:9.5px; font-weight:700; letter-spacing:.09em; color:neutral-400` | `font-size:10.5px; font-weight:800; letter-spacing:.10em; color:var(--mz-text-mut)` (#786A57) | `static/design/category-nav.css:68-72` | S |
| 14 | Each category row leads with a Material Symbol at `font-size:19px`, colour `{{ k.iconCol }}` | No icon; the row is label + count only | `static/src/cashier/root.xml:267-274` | M |
| 15 | Category label `font-size:12.5px`, weight `{{ k.fw }}` (varies) | `font-size:13px; font-weight:700`, constant | `static/design/category-nav.css:112-117` | S |
| 16 | Count uses `font-size:{{ catsCountSize }}` at weight 600, colour `neutral-400` | `font-size:11.5px; font-weight:700; color:var(--mz-text-mut)` | `static/design/category-nav.css:122-125` | S |
| 17 | Active category has no fill in the source (`{{ k.bg }}` — `UNKNOWN — runtime`) | `background:var(--mz-brand-soft)` #F6E9E0, `color:var(--mz-brand-press)` #984922 | `static/design/category-nav.css:119` | S |
| 18 ✅ | Divider above DIETARY: `height:1px; background:neutral-200; margin:10px 4px` **[no token]** | `border-top:1px solid var(--mz-border)` on `.mz-diets`, `margin-top:8px`, no side inset | `static/design/category-nav.css:80` | S |
| 19 ✅ | DIETARY caption `9.5px/700/.09em`, `padding:0 8px 7px` | Reuses `.mz-catside__label` at `10.5px/800/.10em` | `static/src/cashier/root.xml:282` | S |
| 20 ✅ | Diet chip row `gap:5px; padding:0 4px`; chip `min-height:44px; padding:0 12px; radius var(--r)` 11px; `11.5px/600` | Matches: `gap:5px`, `padding:0 4px`, `min-height:44px`, `padding:0 12px`, `border-radius:11px`, `11.5px/600` | — | — |
| 21 | Selected diet chip colours are `{{ d.bg }}/{{ d.col }}/{{ d.bd }}` — `UNKNOWN — runtime` | `background:var(--mz-text)` #2A2420, `color:var(--mz-surface)` — an ink-filled chip | `static/design/category-nav.css:89-91` | S |
| 22 ✅ | Menu-health card: `background:#FFFFFF`, `border:1px solid neutral-300`, `padding:11px 12px` **[no token]** | `background:var(--mz-surface-2)` #FAF6F0, `padding:12px` | `static/design/category-nav.css:96-100` | S |
| 23 ✅ | Menu-health caption `10px/700/.06em uppercase neutral-400`; figure mono `19px/700 neutral-800`; unit `11px neutral-600`; note `10.5px/1.4 neutral-600` | Same sizes and weights; colours are `--mz-text-mut` / `--mz-text` / `--mz-text-mut` | `static/design/category-nav.css:101-110` | — |
| 24 ✅ | The branch name lives in the **top bar** only | We additionally render a branch pill at the head of the sidebar (`.mz-catside__branch`: 12.5px/700, radius 12px, `surface-2` fill, 7px brand dot) — the branch is stated twice | `static/src/cashier/root.xml:246-249`, `category-nav.css:60-67` | S |
| 25 | Sidebar is present at every width — the canvas is fixed 1920×1080 with no breakpoints | Sidebar is `display:none` below 1280px and swaps to the `.mz-catbar` chip strip | `static/design/category-nav.css:34`, `:36` | M |

## 3. Product grid and card

| # | Design | Ours | Change here | Effort |
|---|---|---|---|---|
| 26 ✅ | Grid gutter `gap:14px` (design line 207) | `gap:11px` | `static/design/product-browser.css:43` | S |
| | ↳ **Contested and ruled.** `GAP_REGISTER.md` §8b recorded the design's gutter as 11px, contradicting the source literal, and `test_drivethru_order_taker.test_10` asserted the 11. Operator ruled **14** on 2026-09-09; the register row, the CSS and the test now agree. | | | |
| 27 | Grid has a `max-width:{{ gridMax }}` cap so cards stop growing | No max-width; tracks are `auto-fill minmax(220px,1fr)` and stretch to the column | `static/design/product-browser.css:43` | S |
| 28 ✅ | Grid padding `2px 20px 20px` | `4px 20px 20px` | `static/design/product-browser.css:39` | S |
| 29 ✅ | Card media is `aspect-ratio:16/10` (design line 210) | `aspect-ratio:1/1` — a square thumb where the design is landscape | `static/design/product-browser.css:75` | S |
| 30 ✅ | Media placeholder fill `#F1E7D2` **[no token]** | `background:var(--mz-surface-2)` #FAF6F0 | `static/design/product-browser.css:76` | S |
| 31 ✅ | Card rest shadow `0 1px 2px rgba(38,34,28,.04)` (design line 209; token `shadows.productTile`) | No rest shadow | `static/design/product-browser.css:69-73` | S |
| 32 ✅ | No hover shadow specified on the tile | `box-shadow:0 4px 14px rgba(0,0,0,.08)` on hover, and a second identical rule on `.mz-tile-cell:hover` | `static/design/product-browser.css:120`, `:138` | S |
| 33 ✅ | Card body padding `10px 12px 11px` **[no token]** | `padding:12px` on all four sides | `static/design/product-browser.css:92` | S |
| 34 ✅ | Product name `14.5px/600, line-height:1.25, min-height:20px` **[no token]** | `13px/600, line-height:1.15`, no min-height | `static/design/product-browser.css:145` | S |
| 35 ✅ | Arabic name `11px/500, line-height:1.25, color:neutral-500 (#9A9184), margin-bottom:3px, min-height:14px` | `11px/500, line-height:1.25, color:var(--mz-text-faint)` (#8A7E6E), `margin-top:1px`, no min-height | `static/design/product-browser.css:235-239` | S |
| 36 ✅ | Price is `'JetBrains Mono' 16px/700` with `font-variant-numeric:tabular-nums` | `15px/800` in the UI face, no tabular figures | `static/design/product-browser.css:146` | S |
| 37 ✅ | Currency is a **separate span** beside the price at `12px/500 neutral-600` | No currency span; the currency is inside the formatted price string | `static/src/cashier/components/product_grid.xml:49` | M |
| 38 ✅ | Price row is `display:flex; align-items:baseline; gap:3px` with a spacer pushing the Options control to the trailing edge | Price is a block with `padding-inline-end:34px` reserving the quick-add corner; no baseline row | `static/design/product-browser.css:146-150` | M |
| 39 | **Options is a control**: `min-height:34px; padding:0 10px; radius var(--r-sm)` 6px, `1px solid neutral-300`, white fill, `tune` glyph 14px + label `10.5px/700 neutral-800`, its own `onClick` | Options is a non-interactive `<span>`: inline-flex, `10.5px/700 var(--mz-text-2)`, `⚙` at 11px, no border, no fill, no handler | `static/src/cashier/components/product_grid.xml:57-61`, `product-browser.css:270-274` | M |
| 40 ✅ | Corner badges at `top:8px; inset-inline-start:8px; gap:4px` | `top:6px; inset-inline-start:6px; gap:3px` | `static/design/product-browser.css:248-252` | S |
| 41 ✅ | Badge `9.5px/800, letter-spacing:.05em, text-transform:uppercase, padding:3px 7px, radius var(--r-sm)` 6px, `box-shadow:0 1px 3px rgba(38,34,28,.18)` (token `shadows.badgePill`) | `9.5px/800, letter-spacing:.475px` (an absolute value, not `em`), `padding:3px 7px`, `radius:6px`, **no shadow**, no `text-transform` | `static/design/product-browser.css:253-256` | S |
| 42 | Badge fills are `{{ b.bg }}/{{ b.col }}` — `UNKNOWN — runtime` | Best and Combo both `var(--mz-brand)`; Portion `var(--mz-text)`; Low `var(--mz-warn)`. Best and Combo are indistinguishable | `static/design/product-browser.css:257-260` | S |
| 43 ✅ | Favourite star `top:7px; inset-inline-end:8px; font-size:17px; color:#F2C24E` **[no token]** with `text-shadow:0 1px 3px rgba(38,34,28,.35)` **[no token]** | `top:5px; inset-inline-end:6px; font-size:15px; color:#C08A2E`, no text-shadow | `static/design/product-browser.css:264-267` | S |
| 44 ✅ | Allergen line `margin-top:7px; gap:5px`, `warning` glyph 13px `neutral-600`, text `10px/700, letter-spacing:.03em, color:neutral-700` | `margin-top:3px; gap:4px`, `⚠` at 11px, text `10px/700`, no letter-spacing, `color:var(--mz-text-mut)` | `static/design/product-browser.css:240-245` | S |
| 45 ✅ | An 86'd item is a **full-media overlay**: `rgba(251,250,248,.66)` wash + a stamp rotated `-14deg`, accent fill, white mono `15px/700, letter-spacing:.14em`, `padding:5px 22px`, radius 6px, `box-shadow:0 2px 8px rgba(38,34,28,.22)` (token `shadows.stamp86`) | A corner pill: `top:8px; inset-inline-end:8px`, danger fill, `11px/800`, `radius:999px`, plus `opacity:.72` on the whole tile | `static/design/product-browser.css:154-158` | M |
| 46 ✅ | A weighed item shows a pill on the media: `bottom:8px; inset-inline-start:8px; height:26px; padding:0 8px; radius var(--r)`, `rgba(38,34,28,.86)` fill, `scale` glyph 13px + `10px/700` white | No by-weight affordance on the tile (only on the cart line) | `static/src/cashier/components/product_grid.xml` | M |
| 47 ✅ | Density model is `targetCols`/`maxTileWidth` per mode (6/300, 5/340, 4/400 — tokens `density.registerGrid`) | Track minimums 168 / 220 / 280px, and a second overriding pair on `.mz-catalog[data-density]` at 128 and 220px with different gaps | `static/design/product-browser.css:61-63`, `:291-296` | M |
| 48 ✅ | Density control chips are `height:44px; padding:0 13px; radius var(--r)` 11px, `12px/600` | `min-height:32px; padding:0 10px; radius:9px, 11.5px/700` — below the 44px floor every other control here holds | `static/design/product-browser.css:283-289` | S |
| 49 | Density selected state is `{{ m.bg }}/{{ m.col }}/{{ m.bd }}` — `UNKNOWN — runtime` | `background:var(--mz-text)`, `color:var(--mz-surface)` — an ink-filled chip | `static/design/product-browser.css:288` | S |
| 50 ✅ | Catalogue count line: `padding:0 20px 8px; gap:10px`, label `11.5px/600 neutral-600`, column caption **mono** `11px neutral-400` | `margin:0 0 8px; padding:0 4px`, label `12.5px/600 var(--mz-ink-soft, #8a7a6b)`, density caption not mono, `margin-inline-start:8px` | `static/design/product-browser.css:24-28`, `:280-281` | S |
| 51 ✅ | Search field `height:44px; padding:0 14px`, white fill, `1px neutral-300`, radius 11px, `search` glyph 19px `neutral-400` inside, input `13.5px` | Canonical `.mz-search`: `min-height:44px; padding:12px 16px; font-size:15px`, no leading glyph | `static/design/components.css:216-220` | S |
| 52 ✅ | Clear control is a bare `close` glyph at 17px `neutral-600` inside the field | A bordered 44×44 button outside the field | `static/design/product-browser.css:170-173` | S |
| 53 ✅ | Search row `padding:10px 20px 10px; gap:14px` | `padding:12px 16px 0; gap:12px` | `static/design/product-browser.css:163-166` | S |
| 54 ✅ | Keyboard hint is two lines, mono `10.5px neutral-400`, `line-height:1.7`, `text-align:end` | One line, `12px`, not mono, `color:var(--mz-text-mut)` | `static/src/cashier/cashier.css:481` | S |
| 55 | Placeholder names the scanner: "…menu, barcode or PLU" | `placeholder="Search menu — press /"` | `static/src/cashier/root.xml:343` | S |
| 56 ✅ | Design's grid empty state — none specified | `.mz-grid-empty` centred muted text at `padding:32px` | `static/design/components.css:362-364` | — |
| 57 ✅ | Open-checks strip: `padding:10px 20px 0; gap:7px` | `padding:8px 16px 0; gap:8px` | `static/design/category-nav.css:143-147` | S |
| 58 ✅ | Chip meta is mono `10.5px`, colour `{{ ck.metaCol }}` | mono `11px var(--mz-text-faint)` | `static/design/category-nav.css:172` | S |
| 59 ✅* | "New check" chip is **dashed**: `1px dashed neutral-300` with an `add` glyph 15px + `12px/600 neutral-600` | `.mz-ochecks__new` has no rule anywhere in the bundle, so it renders as a solid `.mz-ochecks__chip` with no glyph | `static/src/cashier/root.xml:334-337` | S |

## 4. Order panel

| # | Design | Ours | Change here | Effort |
|---|---|---|---|---|
| 60 ✅ | Panel `width:436px; background:#FFFFFF; border-inline-start:1px solid neutral-300` (design line 400) | `flex:0 0 436px`, `background:var(--mz-surface)` #FFFFFF, `border-inline-start:1px solid var(--mz-border)` — matches | — | — |
| 61 | Panel width is unconditional (fixed canvas) | Steps to 340px below 1400px and 320px below 1100px | `static/design/order-panel.css:222-231` | M |
| 62 ✅ | Head `padding:14px 18px 12px`, `border-bottom:1px solid neutral-200` **[no token]** | `padding:16px 16px`, `border-bottom:1px solid var(--mz-border)` (the 300-step, not the 200-step) | `static/design/order-panel.css:62-65` | S |
| 63 ✅ | Head title `13.5px/800, letter-spacing:.02em` | `13px/800`, no letter-spacing | `static/src/cashier/cashier.css:1201` | S |
| 64 ✅ | Head meta is plain mono text `11.5px neutral-600` at the trailing edge | The same node carries `.mz-cart-count`, so it renders as a **pill**: `brand-soft` fill, `brand-press` ink, `radius:999px`, `padding:2px 8px` — the later `.mz-cart-head__c` rule only resets size and colour | `static/src/cashier/components/cart.xml:12-13`, `order-panel.css:66`, `cashier.css:1202` | S |
| 65 ✅ | Second head row is a single line: mono order number (600, neutral-800) · "opened HH:MM" · mono elapsed · staff name, all `11.5px neutral-600` | `.mz-cart-meta` — one `11.5px` muted line, tabular; content assembled in `root.js` | `static/src/cashier/cashier.css:1203-1208` | — |
| 66 | Head carries a **queued/ETA chip**: `height:44px; padding:0 11px; radius var(--r)`, `11.5px/700`, `cloud_upload`-family glyph 16px + caret 16px at `opacity:.6`, expanding to an inline detail block | Absent | `static/src/cashier/components/cart.xml:9-16` | L |
| | ↳ **Resolved from the model, ready to build** (`Mezze POS v3.dc.html:37580-37600`). It is a per-check **e-receipt** chip with four states, each with its own glyph, detail line and action: `accepted` / `verified` / "UUID … · submitted …" / no action; `queued` / `cloud_upload` / "issued … · must reach ETA within 24h · …" / **Send now**; `rejected` / `gpp_bad` / the retry reason / **Fix and resubmit**; `none` / `receipt_long` / "A tax receipt is issued to ETA the moment this ticket is charged." / no action. Short labels are `Accepted` · `Queued · 24h` · `Rejected · 4103` · `No receipt`. Ours maps onto `mezze.einvoice` (draft / submitted / cleared / rejected / error) and would gate on the same probe row 136 uses, since a chip claiming an e-receipt on a till with no e-invoicing behind it is a claim, not a status. A fresh draft check sits in `none`, which is the design's behaviour and is the informative case. | | `static/src/cashier/components/cart.xml:9-16`, `controllers/w1.py:178` | L |
| 67 ✅ | Conflict banner sits **inside** the panel, below the head (`margin:10px 12px 0`) | Sits **outside** `.mz-cart`, as a sibling in the workspace before the panel | `static/src/cashier/root.xml:404-428` | M |
| 68 ✅ | Conflict banner `border:1px solid neutral-300`, `background:neutral-200`, `padding:11px 12px`, radius 11px | `border:1px solid var(--mz-warn)` #B5842B, `background:var(--mz-surface-2)`, `padding:12px`, radius 11px | `static/src/cashier/cashier.css:1473-1477` | S |
| 69 ✅ | Conflict leads with a `sync_problem` glyph at 18px `neutral-700` | No glyph | `static/src/cashier/root.xml:405-408` | S |
| 70 ✅ | Conflict title `12.5px/700 accent-700`; body `11px neutral-600, line-height:1.4` | Title `13px/800 var(--mz-text)`; body `11.5px var(--mz-text-mut)`, no line-height | `static/src/cashier/cashier.css:1479-1480` | S |
| 71 ✅ | Conflict actions: two `flex:1` buttons `height:44px`, white fill, `1px accent-300`, radius 11px, `12px/700`; then a fixed `flex:0 0 92px` Review at `12px/600 neutral-600` | Three `.mz-btn` variants — primary (dark brand fill), secondary, and a `--sm` Review at 36px. Keep-mine is loud where the design keeps all three quiet | `static/src/cashier/root.xml:419-427` | S |
| 72 ✅* | Order-type strip: container `padding:3px; gap:3px; background:neutral-100; border-radius:var(--r-sm)` 6px, **no border**; item radius `var(--r)` 11px, `12.5px`, active = white fill + `{{ t.sh }}` | Container `padding:4px; gap:4px; background:var(--mz-surface-2); border:1px solid var(--mz-border); radius:11px`; item radius 8px, `14px/600`, active = white + `0 1px 3px rgba(0,0,0,.10)`. Container and item radii are swapped relative to the design | `static/src/cashier/cashier.css:1119-1132` | S |
| 73 | Attached guest is an **inline card** in the panel: `1px neutral-300`, `--color-bg` fill, radius 11px, `padding:10px 12px`, a 32px `accent-200` circle with `12px/800` initials, name `13px/700`, an optional tag chip `9px/800/.06em` accent on `accent-100`, and a mono `11px` line of "phone · points" | A single 44px chip (`.mz-custchip`) showing a glyph and the customer name. No avatar, no tag chip, no points, no phone | `static/src/cashier/components/cart.xml:61-66`, `cashier.css:250-259` | L |
| 74 ✅* | Attached guest carries two 40×40 controls: `open_in_new` (open profile) and `person_remove` | Neither; clearing the customer is inside the picker modal | `static/src/cashier/components/cart.xml:61-66` | M |
| 75 ✅ | Unattached state is a **dashed** 44px row: `1px dashed neutral-300`, `--color-bg` fill, `person_add` 19px `neutral-500`, label `12.5px/700 neutral-700`, trailing caret | Solid `1px solid var(--mz-border)`, `var(--mz-surface)` fill, `12px/600 var(--mz-text-2)`, no caret | `static/src/cashier/cashier.css:250-259` | S |
| 76 | Guest search, results and "new guest" expand **inline** under that row: results rows `min-height:46px; radius var(--r)`, `--color-bg` fill, `1px neutral-200`, with a `person` glyph 17px, name `12.5px/600`, mono `10.5px` phone and mono `10.5px` points | A separate 520px modal (`.mz-custpick`) | `static/src/cashier/root.xml:131-209` | L |
| 77 ✅ | Lines region `padding:2px 12px 8px` | `padding:8px 12px` | `static/design/order-panel.css:71` | S |
| 78 ✅ | Empty cart is a **dashed card**: `1px dashed neutral-300`, radius 11px, `padding:34px 20px`, centred, `receipt_long` glyph 30px `accent-300`, title `13.5px/700`, two-line body `11.5px neutral-600, line-height:1.45` | One line of muted centred text at `padding:32px` via the shared empty helper | `static/src/cashier/components/cart.xml:81`, `components.css:362-363` | M |
| 79 | Lines are grouped into **courses** with a foldable head: 44px row, `neutral-100` fill, `1px neutral-200`, radius 11px, chevron 18px, title `11px/800/.1em uppercase`, mono count `11.5px/600`, a state chip `9.5px/700` and a mono amount `12px/600` | No grouping — the cart is a flat list. Coursing is a separate screen | `static/src/cashier/components/cart.xml:79-211` | L |
| 80 | Each course head carries its own **Fire** button: `min-height:44px; padding:0 14px; radius var(--r)`, `--color-text` fill, `accent-100` ink, `12px/700`, `skillet` glyph 17px | Firing is one panel-level verb for the whole check | `static/src/cashier/components/cart.xml:79-211` | L |
| | ↳ **Rows 79 and 80 are one modelling decision, not two CSS rows.** The design treats a course as a property of a CART LINE, so it can group an unsynced check and fire one group. Ours treats it as a state of a synced ticket: `/courses/board` is keyed to a `restaurant.table` and a session, and it assembles fired KDS tickets plus held staged courses (`controllers/main.py:4116-4135`). Two consequences the design never had to face — a line that has not synced yet belongs to no course, and a takeaway or delivery check has no table to key one to. Closing these rows means deciding whether course becomes a line attribute carried in the draft, which is a data change, not a panel change. | | `static/src/cashier/components/courses.js`, `controllers/main.py:4116` | L |
| 81 ✅ | Order note is a **dashed** field: `1px dashed neutral-300`, radius 11px, `padding:8px 11px; gap:8px`, `sticky_note_2` glyph 16px `neutral-400`, input `12px`, mono counter `10.5px neutral-400` | Solid `1px solid var(--mz-border)`, `var(--mz-surface)` fill, `padding:8px`, radius 11px; input `12px`, mono counter `10.5px var(--mz-text-faint)` | `static/src/cashier/cashier.css:1210-1221` | S |
| 82 ✅ | Element order in the panel foot: **order note → upsell → totals card → charge → footer verbs** | `presets → upsell → more-sheet → footer verbs → order note → totals → charge → fastpay`. The note and the verbs are on the wrong side of the totals | `static/src/cashier/components/cart.xml:213-358` | M |
| 83 ✅ | Upsell is a fixed **2-up row**: `padding:8px 12px 0; gap:8px`, each tile `flex:1`, `1px neutral-300`, `--color-bg` fill, radius 11px, `padding:7px 11px`, title `12px/700, line-height:1.2`, reason `10.5px neutral-600, margin-top:1px` | A wrapping chip row: `gap:4px; padding:8px 16px 0`, chip `padding:4px 8px`, radius 11px, `var(--mz-surface)` fill, title `12px/600`, reason `10.5px/500` | `static/src/cashier/cashier.css:270-293` | S |
| 84 ✅ | The More sheet is an **overlay**: `position:absolute; inset-inline 12px; bottom:142px; z-index:6`, white, radius 11px, `padding:10px`, `max-height:420px`, `box-shadow:0 -10px 34px rgba(38,34,28,.20)` (token `shadows.quickActionsSheet`), `animation:mzIn .18s` | In flow: a `border-top`, `padding:12px 16px 4px`, `max-height:46vh`, no fill of its own, **no shadow, no elevation, no animation** | `static/src/cashier/cashier.css:347-353` | M |
| 85 ✅ | Sheet group items are **wrapping pills**: `min-height:44px; padding:0 12px; radius var(--r)`, `12px/600`, glyph 17px inline before the label | A rigid `repeat(3, 1fr)` grid of 52px stacked `.mz-verb` tiles | `static/src/cashier/cashier.css:358` | M |
| 86 ✅ | Sheet group heading is a glyph + caption row: glyph 14px, caption `9.5px/700/.08em uppercase`, `padding:2px 4px 6px` | Caption only, `10px/800/.07em uppercase`, no glyph | `static/src/cashier/cashier.css:354-357` | S |
| 87 ✅ | Footer grid gap `7px` | `gap:6px` | `static/src/cashier/cashier.css:337` | S |
| 88 ✅ | Footer tile inner `gap:2px` | `gap:3px` | `static/src/cashier/cashier.css:305` | S |
| 89 ✅ | Footer tiles otherwise: `height:52px`, `1px neutral-300`, white, radius 11px, glyph 18px, label `11px/600` | `min-height:52px`, `1px var(--mz-border)`, `var(--mz-surface)`, radius 11px, glyph 18px, label `11px/600` — matches | — | — |
| 90 ✅ | No fast-pay row | `.mz-fastpay` — a row of secondary buttons under Charge | `static/src/cashier/components/cart.xml:350-358` | S |

## 5. Line anatomy

| # | Design | Ours | Change here | Effort |
|---|---|---|---|---|
| 91 ✅ | A line is a **bordered card**: `border:1px solid {{ l.bd }}`, `background:{{ l.bg }}`, `border-radius:var(--r-lg)` 13px, `margin-bottom:6px; overflow:hidden` | A row separated by `border-bottom:1px solid var(--mz-divider)`, no radius, no card | `static/design/order-panel.css:87` | M |
| 92 ✅ | Main row `padding:11px 12px; gap:10px; align-items:flex-start` | `padding:8px 8px; gap:8px; align-items:baseline` | `static/design/order-panel.css:87-88` | S |
| 93 | Quantity mono `13px/700, min-width:26px`, colour `{{ l.qtyCol }}` | mono `12px/800 var(--mz-brand-press)`, no min-width | `static/design/order-panel.css:89-92` | S |
| 94 ✅ | Line name `13.5px/600, line-height:1.3` | `font-weight:600`, size inherited from the panel (no rule sets it) | `static/design/order-panel.css:93` | S |
| 95 ✅ | Line amount is mono `13.5px/700` with `font-variant-numeric:tabular-nums` | `font-weight:700`, size inherited, not mono, not tabular | `static/design/order-panel.css:94` | S |
| 96 ✅ | Modifier sub-line `11px neutral-600, margin-top:2px, line-height:1.35` | `12px var(--mz-text-mut), margin-top:2px, line-height:1.35, padding-inline-start:8px` | `static/design/order-panel.css:95-98` | S |
| 97 ✅ | A free-text note is a **separate row** from the modifiers: `11px accent-700` with an `edit_note` glyph at 12px | Note and modifiers share the same `.mz-line-note` class and colour; no glyph on either | `static/src/cashier/components/cart.xml:134-136` | S |
| 98 ✅ | Line badges `margin-top:5px; gap:5px`, each `9.5px/700, letter-spacing:.04em, uppercase, padding:2px 6px, radius var(--r-sm)` 6px | `.mz-line-tag` `11px/700, letter-spacing:.02em, uppercase, padding:2px 6px, radius:999px` | `static/src/cashier/cashier.css:966-970` | S |
| 99 ✅ | Status badge colours come from the `orderLineStatus` token table (new/preparing/held/fired/served/paid, each a `bg`+`ink` pair) | Default is `--mz-ok` on `--mz-ok-soft` (green) for every tag; only the kitchen-state modifiers repaint, and they map fired+accepted → `surface-3`, preparing → warn, ready+served → ok. `new`, `held` and `paid` have no mapping | `static/src/cashier/cashier.css:1240-1244` | M |
| 100 ✅ | Seat badge `neutral-100` fill, `neutral-600` ink; MERGED badge `neutral-100` fill, `neutral-800` ink — two different inks | Both use the same `.mz-line-tag` green default | `static/src/cashier/cashier.css:966-970` | S |
| 101 ✅ | Line controls row `padding:0 12px 11px; gap:7px`; the stepper is a bordered group (`padding:3px`, white, `1px neutral-300`, radius `var(--r-sm)`) holding a 44px `remove`, a `min-width:46px` mono `15px/700` value and a 44px `add` on an `accent-200` fill | `.mz-line-ctrls` `gap:8px; margin-top:8px; flex-wrap:wrap`; the canonical `.mz-stepper` has no group border, both buttons share `surface-2`, and the value is mono `15px/800` | `static/design/order-panel.css:105-106`, `components.css:228-247` | M |
| 102 ✅ | The `add` button is tinted `accent-200` with `accent` ink, so increment reads louder than decrement | Both stepper buttons are identical | `static/design/components.css:229-236` | S |
| 103 ✅ | Edit and Note are `height:44px; padding:0 13px`, radius `var(--r)` 11px, `12.5px/600`, white fill, `1px neutral-300` | Both `min-height:44px; padding-inline:8px`, radius **8px**, `12px/600`, transparent fill | `static/design/order-panel.css:124-128`, `cashier.css:1108-1112` | S |
| 104 ✅ | Overflow is a `44×44` square with `more_horiz` at 19px, `1px neutral-300`, white, radius 11px | `.mz-line-more` 44×44, radius **10px**, transparent, `border:1px solid transparent` | `static/src/cashier/cashier.css:375-379` | S |
| 105 ✅ | Line menu is `margin:0 12px 11px`, `1px neutral-300`, `radius var(--r-lg)` 13px, rows separated by `border-bottom:1px solid neutral-200`, row `padding:9px 12px; gap:9px`, glyph 17px, label `12px/600` | `margin:6px 0 4px`, `1px var(--mz-border)`, radius 11px, `background:var(--mz-surface-2)`, `padding:4px`, `gap:2px` between rows (no separators), row `min-height:44px; padding:0 8px`, radius 9px, label `12.5px/600` | `static/src/cashier/cashier.css:385-401` | S |
| 106 ✅ | A gated row shows a `lock` glyph 14px `neutral-400` at the trailing edge | `.mz-linemenu__lock` at 15px `var(--mz-text-mut)` | `static/src/cashier/cashier.css:404` | S |
| 107 ✅ | No unit-price element on the line | `.mz-line-each` — a `11.5px` muted per-unit price in the name row | `static/design/order-panel.css:109-112` | S |
| 108 ✅ | Selected line is carried by `{{ l.bd }}`/`{{ l.bg }}` — `UNKNOWN — runtime` | `border-color:var(--mz-brand)` + `background:var(--mz-brand-soft)`, but `.mz-line` has only a `border-bottom`, so the brand border shows on one edge | `static/design/order-panel.css:82`, `:87` | S |

## 6. Totals block

| # | Design | Ours | Change here | Effort |
|---|---|---|---|---|
| 109 ✅ | The totals are a **card**: `margin:10px 12px 0`, `1px solid neutral-300`, `--color-bg` fill, radius 11px, `padding:12px 14px` **[no token]** | No container — the rows sit directly in `.mz-cart-foot` (`padding:16px`, `border-top`) | `static/design/order-panel.css:133`, `:136-140` | M |
| 110 ✅ | Breakdown row `padding:3px 0; gap:8px`, key `12.5px` | `padding:0 16px; min-height:22px`, key `13px/400` | `static/design/order-panel.css:136-140` | S |
| 111 ✅ | Breakdown value is mono `13px/600` with `font-variant-numeric:tabular-nums` | mono via `.mz-trow__v`, but size and weight are inherited (13px/400) and there is no `tabular-nums` | `static/design/order-panel.css:147` | S |
| 112 ✅ | A row may carry a mono `11px neutral-400` meta note beside its key | `.mz-trow__n` is emitted in the markup but **has no CSS rule anywhere**, so the item count renders at the row's own 13px/400 | `static/src/cashier/components/cart.xml:316` | S |
| 113 ✅ | A `hasSumToggle` row can collapse the breakdown: `min-height:34px; gap:6px`, chevron 16px, `11.5px/600 neutral-600` | No collapse; all rows are always shown | `static/src/cashier/components/cart.xml:310-333` | M |
| 114 ✅ | A `1px neutral-300` divider separates the breakdown from the total: `margin:9px 0 8px` | No divider | `static/src/cashier/components/cart.xml:333-334` | S |
| 115 ✅ | Total **label** is `12px/800, letter-spacing:.08em, text-transform:uppercase, color:neutral-800` | `.mz-total-k` sets only `flex:none`, so the label inherits the row's `26px/800` — it renders as large as the amount | `static/design/order-panel.css:152-153` | S |
| 116 ✅ | Total **amount** is mono `30px/700, letter-spacing:-.02em, tabular-nums` (design line 656) | `26px/800`, no letter-spacing, no tabular-nums; mono only because `.mz-total-amt` inherits nothing — it is the UI face | `static/design/order-panel.css:152`, `:155-156` | S |
| 117 | Total amount colour is `{{ bigCol }}` — `UNKNOWN — runtime` | `color:var(--mz-brand)` #C0602E | `static/design/order-panel.css:156` | S |
| 118 ✅ | Currency is a **separate span** after the amount at `15px/600 neutral-600` | No currency span; it is inside the formatted string | `static/src/cashier/components/cart.xml:336` | S |
| 119 ✅ | Total row is `align-items:baseline; gap:8px` with a flexible spacer between label and amount | `align-items:baseline; gap:8px`, no spacer — label and amount are adjacent, not justified | `static/design/order-panel.css:152` | S |

## 7. Primary action button

| # | Design | Ours | Change here | Effort |
|---|---|---|---|---|
| 120 ✅ | `height:64px` (design line 681) | `min-height:64px` — matches | — | — |
| 121 ✅ | `border-radius:var(--r)` = **11px** | `border-radius:14px` | `static/design/order-panel.css:171` | S |
| ~~122~~ | ~~Fill is `{{ chargeBg }}`; the token file records its shadow as `chargeButton: 0 2px 8px rgba(181,101,46,.26-.28)` — a terracotta glow~~ | **WITHDRAWN — this row was wrong.** Measured in Chrome, the button paints `color-mix(in srgb, var(--mz-brand) 88%, #1a0e06)` ≈ `#AC5629`, already in the accent family. `components.css:43` is overridden by a later, explicitly-commented rule at `components.css:626` that keeps the money CTA terracotta rather than success-green; I read the first and missed the second | — | — |
| 123 | Carries `box-shadow:{{ chargeSh }}` (terracotta, per the token above) | No shadow on the CTA | `static/design/order-panel.css:170-171` | S |
| 124 | Carries `border:1px solid {{ chargeBd }}` | Border comes from `.mz-btn`'s `1px solid transparent` | `static/design/components.css:18` | S |
| 125 ✅ | Content is glyph + label + **amount** + **currency**: glyph 22px, label `{{ chargeSize }}/700, letter-spacing:.01em`, amount mono `19px/700 tabular`, currency `14px/600 opacity:.85` | Glyph + label only. The amount is not repeated on the button | `static/src/cashier/components/cart.xml:339-346` | M |
| 126 ✅ | Content `gap:10px` | `gap:6px` | `static/src/cashier/cashier.css:365-368` | S |
| 127 ✅ | Glyph `font-size:22px` | `.mz-btn--charge__ico` at 19px | `static/src/cashier/cashier.css:369` | S |
| 128 | Label size is `{{ chargeSize }}` — `UNKNOWN — runtime`; `margin-bottom:8px` under the button | `font-size:15px`; margin below comes from the footer's own padding | `static/design/order-panel.css:171` | S |

## 8. Header / status strip

| # | Design | Ours | Change here | Effort |
|---|---|---|---|---|
| 129 ✅ | Bar `height:52px; padding:0 16px; gap:10px; background:#FFFFFF` (design line 46) | `height:52px`, `padding-block:0` with inline padding 20px from the canonical rule, `gap:12px`, `background:var(--mz-surface)` | `static/src/cashier/cashier.css:882-885`, `components.css:423-425` | S |
| 130 ✅ | Brand is a **28×28 rounded square** (radius `var(--r)`, accent fill, white `M` at `14px/800`) followed by "Mezze" at `14px/800, letter-spacing:-.01em` | No mark; `.mz-logo` is the word "Mezze" at `18px/800` in brand colour with `letter-spacing:.5px` | `static/design/components.css:427` | S |
| 131 ✅ | Branch name `13px/600 neutral-800`, ellipsised | `.mz-branch` weight 600, `color:var(--mz-text-2)`, **no size rule** — inherits | `static/design/components.css:428` | S |
| 132 ✅ | Session chip `#S-3`: mono `11px/600 neutral-600`, `neutral-100` fill, `1px neutral-300`, `padding:3px 8px`, radius `var(--r-sm)` 6px | `.mz-sesspill`: `min-height:31px; padding:0 12px; radius:999px`, `12px/400`, `surface-2` fill, plus a 7px `--mz-ok` dot the design does not have | `static/src/cashier/cashier.css:128-135` | S |
| 133 ✅* | The bar carries **no workspace navigation** — the rail is the only navigation | `.mz-nav` — four pill items (Floor / Register / Orders / Reservations) at `min-height:44px`, radius 999px, `14px/600`, active filled with a darkened brand | `static/src/cashier/root.xml:11-27`, `components.css:432-446` | M |
| 134 ✅ | Right side carries a **kitchen chip** (`skillet` glyph 14px + count, `11.5px/600 neutral-600`, `neutral-100` fill, `1px neutral-300`, `padding:4px 10px`, radius 6px) | The ops strip carries kitchen depth as one of several generic chips | `static/src/cashier/root.xml:43-47` | S |
| 135 ✅ | Right side carries a clickable **offline pill** with a 6px status dot | Two `.mz-status--sm` connectivity chips (local + WAN), each with a 7px dot | `static/src/cashier/root.xml:49-58` | S |
| 136 ✅ | Right side carries an **ETA compliance chip** and a separate mono **ETA queue chip** (`cloud_upload` glyph) | Neither | `static/src/cashier/root.xml:48-69` | L |
| 137 ✅ | Right side carries an **86 chip** when `hasE86`: `block` glyph 14px, `11.5px/700 accent-700` on `accent-100` with a full-accent border | An `86`-count chip exists but uses the generic `.mz-ops__c` styling (`11px/700`, `surface-2`, `--mz-border`) | `static/src/cashier/cashier.css:1229-1236` | S |
| 138 ✅ | Ops chips are `padding:4px 10px`, radius `var(--r-sm)` **6px**, `11.5px/600` | `padding:3px 9px`, radius **999px**, `11px/700` | `static/src/cashier/cashier.css:1229-1234` | S |
| 139 | A **lock/lock-screen** button: `min-width:44px; height:44px; padding:0 11px; radius var(--r)`, `neutral-100` fill, `1px neutral-300`, `lock` glyph 18px | Absent | `static/src/cashier/root.xml:48-69` | M |
| | ↳ **The design never finished this one.** Its handler is `lockNow:()=>this.setState({locked:true,lockPin:''})` (`:37928`), and `S.locked` is read **nowhere** in the 39,526-line file — no lock screen, no PIN prompt, nothing consumes either value. Building it as drawn would ship a button that does nothing, which this addon refuses by rule (`rail.js` omits the design's settings destination for exactly that reason). Closing it needs a product decision first: what locking does to an open check, which credential releases it, whether it survives a reload and whether it writes an audit event. **Not drift — an unfinished control.** | | | — |
| 140 | A **language toggle**: same 44px box, `translate` glyph 17px in accent + the language label at `13px/800` | Absent (a theme toggle occupies that slot instead) | `static/src/cashier/root.xml:63-68` | M |
| 141 ✅ | A `1px × 24px` neutral-300 **divider** before the operator block | Absent | `static/src/cashier/root.xml:59` | S |
| 142 ✅ | Operator block is a **26px circle** (accent-200 fill, accent ink, `11px/800` initials) plus two stacked lines: name `12px/700` and role `10.5px neutral-600`, `line-height:1.15` | `.mz-user` — a single text line, weight 600, `var(--mz-text-2)`, no size rule, no avatar, no role line | `static/design/components.css:430` | M |
| 143 | No theme control (the design states light theme only, no dark mode) | `.mz-themetog` — a 44px icon button toggling `☀`/`☾` | `static/src/cashier/root.xml:63-68` | — (see §11) |
| 144 ✅ | An **offline banner** row below the bar when `offline`: `padding:9px 18px`, `neutral-200` fill, `cloud_off` glyph 19px, title `12.5px/800`, body `12px/600, line-height:1.4`, a mono queue chip and a `min-height:38px` reconnect button on `--color-text` | Absent | `static/src/cashier/root.xml:70-78` | L |

## 9. Modals

### Configurator / modifier sheet

| # | Design | Ours | Change here | Effort |
|---|---|---|---|---|
| 145 ✅ | Panel `width:640px` (design line 264) | `.mz-modal` `max-width:460px` — the canonical confirm-dialog width, not overridden for the configurator | `static/design/components.css:265-270` | S |
| 146 ✅ | Radius `var(--r-lg)` = **13px** | `var(--mz-radius-lg)` = **14px** | `static/design/components.css:269` | S |
| 147 ✅ | Shadow `0 18px 44px rgba(38,34,28,.22)` (token `shadows.modalStandard`) | `0 16px 48px -12px rgba(0,0,0,.5)` — a cool, much darker shadow | `static/design/components.css:270` | S |
| 148 ✅ | Scrim `rgba(38,34,28,.34)`, and the overlay is inset `26px` from the workspace | `background:var(--mz-scrim, rgba(0,0,0,.5))`. **`--mz-scrim` is never defined in the cashier bundle** — it exists only in `static/pos.html`, the non-production prototype — so the fallback wins and the scrim is neutral black at .5 | `static/design/components.css:262` | S |
| 149 ✅ | Entrance `animation:mzIn .22s ease both` (fade + 8px rise) | `mz-dialog-pop 140ms` (fade + 6px rise) | `static/design/components.css:270`, `:301` | S |
| 150 ✅ | Head carries a **104×78 product image** (radius 11px, `neutral-200` fill) | No image in the configurator head | `static/src/cashier/components/product_config.xml:18-22` | M |
| 151 ✅ | Head carries a **description** line at `12px neutral-600, margin-top:3px, line-height:1.4` | Absent | `static/src/cashier/components/product_config.xml:18-22` | M |
| 152 ✅ | Head carries an **allergen chip**: `10.5px/700 neutral-700`, `neutral-200` fill, `1px neutral-300`, `padding:3px 8px`, radius 6px, `warning` glyph 13px | Absent | `static/src/cashier/components/product_config.xml:18-22` | M |
| 153 ✅ | Head `padding:16px 18px; gap:14px`; title `19px/800, letter-spacing:-.01em` | `padding:16px 18px`; title `19px/800`, no letter-spacing | `static/design/product-config.css:32-37` | S |
| 154 ✅ | Groups are separated by `margin-bottom:16px` and no rule | Groups are separated by `padding:14px 0` and a `border-bottom:1px solid var(--mz-border)` | `static/design/product-config.css:44-45` | S |
| 155 ✅ | Group title `11px/800, letter-spacing:.07em, uppercase, neutral-800`; required chip `10.5px/700, padding:2px 7px, radius 6px` | Group head and `.mz-cfg__tag` exist; sizes differ (see `product-config.css:46-60`) | `static/design/product-config.css:46-60` | S |
| 156 ✅ | Options are a **3-column grid**, `gap:8px` | A wrapping flex row, `gap:9px` | `static/design/product-config.css:61` | S |
| 157 ✅ | Option `min-height:52px; padding:9px 11px; radius var(--r)` 11px, `1.5px` border, label `12.5px/600` | `min-height:48px; padding:10px 15px; radius:12px`, `1.5px` border, label `15px/650` | `static/design/product-config.css:62-68` | S |
| 158 ✅ | Option leads with a **mark glyph** at 18px (`{{ o.mark }}`, colour `{{ o.markCol }}`) that shows selection without relying on fill | No mark glyph — selection is fill and border only | `static/src/cashier/components/product_config.xml:33-45` | M |
| 159 ✅ | Option delta is mono `11px/600` in accent, on its own line under the label | `.mz-cfg-opt__px` is inline beside the label | `static/design/product-config.css:75-81` | S |
| 160 ✅ | The sheet carries a **kitchen-note field**: caption `11px/800/.07em uppercase` + a bordered `padding:10px 12px` input at `12.5px` | Absent from the configurator — notes are a separate per-line modal | `static/src/cashier/components/product_config.xml:47-49` | M |
| 161 ✅ | Foot carries a **quantity stepper**: bordered group `padding:3px`, 44px `remove` on `neutral-100`, `min-width:56px` mono `16px/700` value, 44px `add` on `accent-200` | Absent — the configurator adds exactly one | `static/src/cashier/components/product_config.xml:52-66` | M |
| 162 ✅ | Foot is a horizontal row (`padding:12px 18px; gap:10px`) with the line total right-aligned before the buttons; Cancel `height:52px` and Save `height:52px; padding:0 22px` with a `check` glyph 19px and `box-shadow:0 2px 8px rgba(181,101,46,.26)` | `.mz-cfg__foot` is `flex-direction:column`, `padding:14px 18px`, buttons `min-height:48px`, Save has no glyph and no shadow | `static/design/product-config.css:101-124` | S |
| 163 ✅ | Line-total label `10.5px/700/.06em uppercase neutral-400`; value mono `19px/700 tabular` + currency `13px neutral-600` | `.mz-cfg__price-k` / `-v` — see `product-config.css:107-113` | `static/design/product-config.css:107-113` | S |

### Numpad

| # | Design | Ours | Change here | Effort |
|---|---|---|---|---|
| 164 ✅ | Panel `width:352px`, radius `var(--r-lg)`, `1px neutral-300`, `0 18px 44px rgba(38,34,28,.22)` (design line 334) | **The Numpad has no CSS at all.** `grep` across every stylesheet in the three bundles returns only `.mz-numpad__weigh`, `__weighbtn` and one `.mz-alert` margin. `.mz-numpad`, `__head`, `__display`, `__buf`, `__keys`, `__key` and the `.mz-num` helper are all unstyled — the same class of defect the upsell chips had | `static/src/cashier/cashier.css:1401-1403` | M |
| 165 ✅ | Header `padding:14px 18px 12px`; label `10.5px/700/.07em uppercase neutral-400`; name `15px/700`; value mono `34px/700 tabular`; unit `14px/600 neutral-600` | Unstyled (see #164) | `static/src/cashier/components/numpad.xml:9-30` | M |
| 166 ✅ | Keys are a `repeat(3,1fr)` grid, `gap:7px; padding:12px`, each `height:58px`, radius 11px, mono `19px/700` | Unstyled (see #164) | `static/src/cashier/components/numpad.xml:32-39` | M |
| 167 ✅ | Footer: Cancel `flex:1; height:52px; 13px/600` + Apply `flex:1.4; height:52px`, accent fill, `14px/700` | Unstyled (see #164) | `static/src/cashier/components/numpad.xml` | M |
| 168 | The pad has **no mode strip** — it edits one value | We render a `.mz-tab` segmented strip of modes above the display | `static/src/cashier/components/numpad.xml:18-25` | — (see §11) |
| 169 | Twelve keys, no separate backspace element | Twelve keys plus a thirteenth `⌫` function key | `static/src/cashier/components/numpad.xml:32-39` | S |

### Manager approval

| # | Design | Ours | Change here | Effort |
|---|---|---|---|---|
| 170 ✅ | Panel `width:430px`, radius `var(--r-lg)`, shadow `0 18px 44px rgba(38,34,28,.24)` (token `shadows.modalHeavy`), `position:fixed; z-index:40` (design line 359) | Rendered inside the shared `.mz-modal` at `max-width:460px`; the z-order is correct (`--mz-z-approval:80` via `.mz-modal-backdrop--approval`) but every other value differs | `static/design/components.css:265-270`, `foundation.css:78-82` | S |
| 171 ✅ | Header carries a **38×38 accent-100 rounded square** with a `shield_person` glyph at 20px in accent | No icon | `static/src/cashier/components/manager_gate.xml:7-11` | S |
| 172 ✅ | Title `15px/800`; subtitle names the action and the audit target — `11.5px neutral-600`, e.g. "Comp line · audited to shift 3" | `.mz-mgate__title` + `.mz-mgate__detail`; no audit-target statement | `static/src/cashier/components/manager_gate.xml:7-11` | S |
| 173 | A **reason chip row** precedes the PIN | ~~No reason selector in the gate~~ **corrected:** there IS one — a free-text `mz-manager-reason` input. The difference is chips versus typing, and the design's chip LABELS come from `{{ appr.reasons }}`, a runtime list, so the set cannot be recovered from the frozen file | `static/src/cashier/components/manager_gate.xml` | M |
| 174 | PIN is **four masked boxes**: each `flex:1; height:52px; 1.5px` border, radius 11px, `--color-bg` fill, mono `22px/700` | A single `<input type="password">` using the canonical `.mz-input` | `static/src/cashier/components/manager_gate.xml:35-41` | M |
| 175 ✅ | An on-screen **3×4 keypad**: keys `height:52px`, radius 11px, mono `18px/700` | No keypad — the manager types on the device keyboard | `static/src/cashier/components/manager_gate.xml` | M |
| 176 | Two fields only: reason + PIN. There is no separate identity field | Two text fields: manager **code** and PIN | `static/src/cashier/components/manager_gate.xml:16-41` | — (see §11) |
| 177 ✅ | Actions: Cancel `flex:1; height:52px` + Confirm `flex:1.4; height:52px` | `.mz-mgate__actions` with standard `.mz-btn` (44px) | `static/src/cashier/components/manager_gate.xml` | S |

## 10. Cross-cutting tokens

These are not confined to one region; each one shifts every row above.

| # | Design | Ours | Change here | Effort |
|---|---|---|---|---|
| 178 ✅ | Page background `--color-bg:#FBFAF8` | `--mz-canvas:#FFFDFB` | `static/mezze-design.css` (classic block) | S |
| 179 ✅ | Card/panel surface `--color-surface:#F7F4EE`; cards are explicitly `#FFFFFF` | `--mz-surface:#FFFFFF`, `--mz-surface-2:#FAF6F0`, `--mz-surface-3:#EFE7DB` — a three-step ramp where the design has two | `static/mezze-design.css` | S |
| 180 ✅ | Ink `--color-text:#2A2419` | `--mz-text:#2A2420` | `static/mezze-design.css` | S |
| 181 ✅ | Accent `--color-accent:#B5652E`, pressed `--color-accent-2:#8A5426` | `--mz-brand:#C0602E`, `--mz-brand-press:#984922` | `static/mezze-design.css` | S |
| 182 ✅ | Hairline `--color-neutral-300:#E7E3DB` | `--mz-border:#EAE2D6` | `static/mezze-design.css` | S |
| 183 ✅ | Muted ink `--color-neutral-600:#7C7568` | `--mz-text-mut:#786A57` | `static/mezze-design.css` | S |
| 184 ✅* | Radius scale `--r-sm:6px / --r:11px / --r-lg:13px` (three steps) | `--mz-radius-sm:8px / md:11px / lg:14px / xl:16px / pill:999px` (five steps). Only `md` agrees | `static/design/foundation.css:64` | S |
| 185 ✅ | Focus ring `3px solid accent, offset 2px` | `--mz-focus-width:2.5px`, offset 2px | `static/design/foundation.css:135` | S |
| 186 ✅ | Scrollbar `width:9px`, thumb `rgba(140,128,112,.34)`, radius `var(--r)`, `border:2px solid transparent; background-clip:padding-box` | No scrollbar styling anywhere in the cashier bundle — native scrollbars throughout | `static/design/foundation.css` | S |
| 187 | `*{box-sizing:border-box;margin:0}` on the whole document | No global reset; `.mz-catside` and `.mz-cart` each pin `box-sizing:content-box` to compensate | `static/design/category-nav.css:58`, `order-panel.css:52` | M |
| 188 ✅ | Body stack is `'Hanken Grotesk','IBM Plex Sans Arabic',system-ui,sans-serif` — Arabic in the **same** stack | `--mz-font-text` has no Arabic face; Arabic is a separate `--mz-font-ar` applied only under `[dir="rtl"]` or `[lang="ar"]` | `static/design/foundation.css:50-51` | M |
| 189 ✅ | Every number, timestamp and money value is `'JetBrains Mono'` with `font-variant-numeric:tabular-nums` (token `typography.numericStyle`) | Applied on the stepper value, `.mz-trow__v`, `.mz-line-q`, `.mz-mhealth__pct`, `.mz-catside__c` and the rail badge — but **not** on the tile price (#36), the line total (#95), the total amount (#116) or the breakdown values (#111) | see rows 36, 95, 111, 116 | S |
| 190 ✅* | Every control is drawn with a Material Symbol (`<span class="ms">`); "never emoji" is stated in `domain-docs/MEZZE_DESIGN_SYSTEM.md` | 11 of the 22 glyphs the Register asks for are missing from our 150-codepoint subset, so those controls fall back to text and emoji (`⚙`, `⚠`, `★`, `🔒`, `☀`) | `static/src/shell/icons.js`, `static/fonts/MaterialSymbolsRounded-subset.woff2` | L |
| 191 | Canvas is `1920×1080` fixed with `breakpoints: null` | Six breakpoints across the Register's stylesheets (1700, 1400, 1280, 1100 plus two density families) | `product-browser.css:188-206`, `order-panel.css:222-231`, `category-nav.css:36`, `rail.css:22` | M |
| 192 ✅ | Uppercase section labels use `letter-spacing:.03–.08em` per the design-system contract | Ours range from `.02em` to `.10em`, and `.mz-flag` uses an absolute `.475px` instead of an `em` value | `product-browser.css:254`, `category-nav.css:70`, `cashier.css:355` | S |

---

## 11. Deliberate decisions, not drift — for your ruling

These are divergences with a stated reason in the repository or an obvious
product rationale. None is listed as a defect above; each is here for a decision.

1. **Masked phone number.** The design prints the guest's full number; we render
   `••••4567`. Already flagged in `GAP_REGISTER.md`. Safer on a screen facing a
   queue.
2. **Guest panel is a modal, not inline** (rows 73–76). Already flagged in
   `GAP_REGISTER.md`. Same information, different placement, and the modal is a
   much larger surface than the design's inline card.
3. **No Escalate button on the tender lock.** The design's lock strip offers a
   manager override. `GAP_REGISTER.md` §8 S1-08 records that no endpoint can
   reverse a recorded tender on an open check, so the button would promise what
   the backend cannot do.
4a. **The design palette is now the `classic` theme** (rows 178-183), ruled
   2026-09-09. Changed in `static/gen_design.py` and regenerated, never hand-edited
   into `mezze-design.css`. Only `classic` and the `terracotta` accent moved: the
   design defines one light theme and the other eleven are this product's own.
   The generator's WCAG-AA gate passes on all twelve maps. **The P3A.4 button
   adaptation stays and was re-measured, not inherited:** white on the design's own
   #B5652E is 4.32:1, closer to AA than the old #C0602E's 4.24:1 but still under
   4.5, so the darkened primary fill is still required. Twelve per-file `classic`
   overrides became redundant once the tokens carried the design's values and were
   deleted; the five that remain are literals the token layer has no name for
   (#F1E7D2 tile ground, #F2C24E star, neutral-500 and neutral-700 inks).

4. ~~**Charge is green, not terracotta** (row 122).~~ **Withdrawn.** Verified in a
   browser: the Charge button is already terracotta. `components.css:626`
   deliberately overrides the canonical success fill for the money CTA, and says
   so in its own comment. Nothing to rule on.
5. **Primary and nav-active fills are darkened one step** (`color-mix(… 88%,
   #1a0e06)`). Documented in `components.css` as a WCAG AA adaptation: the
   source's white-on-#C0602E is 4.24:1 and fails for normal-size text.
6. **44px floors raised above the design's own values.** The quick-add's visible
   affordance is the design's 27px but its hit box is 44×44; category rows are
   44px where the reference was 40; line controls hold 44px. Stated in
   `product-browser.css:101-106` and `category-nav.css:111`.
7. **JetBrains Mono on the Total** instead of the reference's Hanken numerals,
   recorded as a justified deviation in `order-panel.css:148-150`.
8. **Latin digits with `tabular-nums`** rather than the design's Arabic-Indic
   numerals via its `N()` helper (`domain-docs/MEZZE_DESIGN_SYSTEM.md`). The
   stepper explicitly pins `unicode-bidi:isolate` and Latin digits.
9. **Self-hosted fonts** (`static/fonts/*.woff2`) where the design loads Google
   Fonts by CDN. Frozen by P2; not reversible without a policy change.
10. **Twelve themes and a dark mode** where the design states "light theme only;
    no dark mode exists in this product". Rows 143 and 178–183 are consequences
    of that decision, not independent choices. **Row 140 waits on this ruling**:
    the design puts a language toggle in the slot our theme toggle occupies, so
    whether that slot changes hands depends on whether the theme control stays.
11. **Extra tile controls** — quick-add `+`, info `i`, and the `86` toggle
    (rows in §3). None exists in the design; all three are real Register
    capabilities the design never had a surface for.
12. **Extra panel controls** — the fast-pay row (row 90), the order-type strip's
    disabled-reason text, and the top-bar workspace nav (row 133). The nav in
    particular duplicates the rail; the design navigates by rail alone.
13. **Numpad mode strip and backspace key** (rows 168–169). Ours edits quantity,
    price and weight from one pad; the design's pad edits one value.
14. **Manager gate asks for a code as well as a PIN** (row 176). Ours identifies
    the approver; the design's asks only for a PIN. **Row 174 waits on this
    ruling**: the design's PIN is four masked boxes, and how many fields the gate
    has decides whether those boxes replace the password input or sit beside a
    code field the design never draws. The input they would replace also carries
    the Chrome-autofill defences documented in `manager_gate.xml`, which would
    have to move with it.
15. **The `.mz-tile-opts` label rather than a button** (row 39) may be
    deliberate — tapping the card already opens the configurator — but nothing
    records it, and the design's is a control. Listed as drift; rule on it.

## 12. Design values with no token in `MEZZE_DESIGN_TOKENS.json`

Thirty-one literals appear in the Register block with no entry in the token file.
Anyone reproducing them is copying a number, not consuming a token.

- **Type sizes**: 9px, 9.5px, 10px, 10.5px, 11px, 11.5px, 12px, 12.5px, 13px,
  13.5px, 14.5px, 15px, 16px, 19px, 22px, 30px, 34px — the file records font
  *families* and a numeric style, but no type scale at all.
- **Spacing**: `10px 12px 11px` (card body), `14px 18px 12px` (panel head),
  `11px 12px` (menu-health card, conflict banner), `12px 14px` (totals card),
  `padding:0 16px` (top bar), `gap:14px` (grid gutter), `bottom:142px`
  (sheet offset).
- **Colours**: `#F1E7D2` (tile media ground), `#F2C24E` (favourite star),
  `rgba(251,250,248,.66)` (86 wash), `rgba(38,34,28,.86)` (by-weight pill),
  `rgba(38,34,28,.34)` (workspace scrim — distinct from the `.42` modal scrim),
  `rgba(38,34,28,.35)` (star text-shadow), `#2C5138` (the ok-state ink named in
  the design-system doc but absent from the Register's own palette).
- **Widths**: 640px (configurator), 352px (numpad), 430px (approval), 104×78
  (configurator thumbnail), 92px (Review button), 26px (line qty min-width),
  46px / 56px (stepper value min-widths).
- **Borders**: `1.5px` (selected option, PIN box, reason chip) — the token file
  records `selected: "1.5-2px"` as a range, not a value.

The four column widths (rail 48 / categories 222 / catalogue 1214 / panel 436)
are also untokenised, though `sizes.orderPanelWidth` covers the last of them.

---

**Total: 191 differences** (192 recorded, row 122 withdrawn after browser
verification). By region: rail 10, category nav 15, product grid/card 34, order
panel 31, line anatomy 18, totals 11, primary action 8, header/status 16, modals
33, cross-cutting 15. Fourteen further items are listed in §11 as decisions
rather than defects.

By effort: 128 S, 50 M, 8 L, plus 6 rows recorded as already matching.
