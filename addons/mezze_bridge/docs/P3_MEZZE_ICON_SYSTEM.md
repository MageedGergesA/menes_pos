# P3 — Approved Mezze Icon System (Flag-Gated)

*Icon migration only. Source of truth: `~/Downloads/Mezze POS Visual Redesign/export` (Material Symbols Rounded, `wght 500 / GRAD 0 / opsz 24`, `FILL 0|1`, class `.mi`). Amber remains the untouched default and renders the **byte-identical** legacy SVG. No colour / typography / spacing / motion / density / radius / layout / business-logic change.*

## 1. Icon Implementation Summary

- **One abstraction layer, no per-site knowledge.** Every migrated icon is addressed **by registry name**. `IC(name)` returns the legacy SVG under amber and the approved ligature under mezze; call sites never name a glyph or a path.
- **73-entry registry** covering **94 of 104** occurrences (`ICONS[name] = {a: original attrs, g: original geometry, m: material ligature}`).
- **Three call-site forms, one layer:** 66 static markup icons annotated `data-ic="name"` (swapped at boot under mezze by `ICboot()`); 28 JS-rendered icons emit `IC("name")`; 5 dynamic wrappers now pass a **name** through data (`ic:'cash_note_t'`) and `mk()` args instead of raw path strings — 16 raw path literals removed from data, **0 remaining**.
- **Self-hosted subset:** Material Symbols Rounded extracted from the export bundle (blob `28e1e4a9…`), subsetted **369,656 → 7,552 bytes (−98.0%)**, 82 glyphs (55 icons + ligature components). No Google Fonts, no CDN, offline preserved.
- **Sizing layer:** 40 `.mi` rules mirror every existing `svg` CSS rule (`width`→`font-size`, `colour`/`opacity`/`flex` carried, `stroke-width` dropped) so icon boxes and layout are unchanged.
- **Verified:** amber byte-identity proven by executing the *real serialized registry* in Node against `git HEAD`; `node --check` OK; braces 2752=2752; all 55 ligatures confirmed present in the subset's GSUB table.

## 2. Mapping Table — legacy SVG → Material Symbol → usage

Registry name encodes the legacy icon; suffixes (`check_13`, `check__2`) are size/attribute variants of one glyph, preserved so amber stays byte-identical.

| Registry name | → Material Symbol | Uses | Icon box | Ligature source |
|---|---|--:|--:|---|
| `close` | `close` | 17 | 18px | export |
| `check__2` | `check` | 5 | via CSS | export |
| `person` | `person` | 5 | 16px | canonical |
| `shield_check` | `verified_user` | 4 | via CSS | canonical |
| `refund_return` | `undo` | 3 | via CSS | export |
| `arrow_down` | `arrow_downward` | 2 | via CSS | canonical |
| `arrow_up` | `arrow_upward` | 2 | via CSS | canonical |
| `search` | `search` | 2 | via CSS | export |
| `warning__2` | `warning` | 2 | via CSS | export |
| `arrow_right` | `arrow_forward` | 1 | via CSS | canonical |
| `arrow_send` | `arrow_forward` | 1 | 18px | canonical |
| `barcode` | `barcode_scanner` | 1 | via CSS | canonical |
| `bell` | `notifications` | 1 | 17px | canonical |
| `calendar` | `calendar_month` | 1 | via CSS | canonical |
| `card` | `credit_card` | 1 | via CSS | export |
| `cart_empty` | `shopping_cart` | 1 | via CSS | canonical |
| `cash_note` | `payments` | 1 | 18px | export |
| `central_kitchen` | `soup_kitchen` | 1 | via CSS | canonical |
| `check` | `check` | 1 | 14px | export |
| `check_13` | `check` | 1 | 13px | export |
| `check_15` | `check` | 1 | 15px | export |
| `check__3` | `check` | 1 | via CSS | export |
| `chevron_down` | `expand_more` | 1 | 14px | canonical |
| `coffee` | `local_cafe` | 1 | via CSS | canonical |
| `comp_gift` | `card_giftcard` | 1 | via CSS | canonical |
| `dashboard_chart` | `insights` | 1 | via CSS | export |
| `delivery_small` | `local_shipping` | 1 | 18px | canonical |
| `delivery_truck` | `local_shipping` | 1 | via CSS | canonical |
| `delivery_van` | `local_shipping` | 1 | via CSS | canonical |
| `dine_in` | `restaurant` | 1 | via CSS | canonical |
| `discount_tag` | `sell` | 1 | via CSS | canonical |
| `email` | `mail` | 1 | via CSS | canonical |
| `floor_tables` | `table_bar` | 1 | via CSS | export |
| `gift_card` | `redeem` | 1 | via CSS | canonical |
| `globe` | `language` | 1 | via CSS | canonical |
| `help` | `help` | 1 | via CSS | canonical |
| `hq_building` | `store` | 1 | via CSS | canonical |
| `kitchen_utensils` | `restaurant` | 1 | via CSS | canonical |
| `list_lines` | `notes` | 1 | via CSS | canonical |
| `lock` | `lock` | 1 | via CSS | canonical |
| `logout` | `logout` | 1 | via CSS | canonical |
| `map_pin` | `location_on` | 1 | via CSS | canonical |
| `margin_trend` | `trending_up` | 1 | 14px | export |
| `ops_bars` | `bar_chart` | 1 | via CSS | canonical |
| `park_order` | `pause` | 1 | via CSS | export |
| `person__2` | `person` | 1 | via CSS | canonical |
| `pos_terminal` | `point_of_sale` | 1 | via CSS | export |
| `print` | `print` | 1 | via CSS | canonical |
| `qr` | `qr_code_2` | 1 | via CSS | canonical |
| `reports_file` | `assessment` | 1 | via CSS | canonical |
| `screen_receipt` | `receipt_long` | 1 | via CSS | export |
| `shield_check__2` | `verified_user` | 1 | via CSS | canonical |
| `sparkle` | `auto_awesome` | 1 | 12px | canonical |
| `split_bill` | `call_split` | 1 | via CSS | canonical |
| `star_redeem` | `star` | 1 | via CSS | canonical |
| `star_tour` | `star` | 1 | via CSS | canonical |
| `swap_arrows` | `swap_horiz` | 1 | 15px | canonical |
| `takeaway_bag` | `shopping_bag` | 1 | via CSS | canonical |
| `theme_sun` | `light_mode` | 1 | via CSS | canonical |
| `warning` | `warning` | 1 | 16px | export |
| `whatsapp` | `chat` | 1 | via CSS | canonical |
| `add` | `add` | _dyn_ | via CSS | export |
| `card_terminal` | `credit_card` | _dyn_ | via CSS | export |
| `cash_note_t` | `payments` | _dyn_ | via CSS | export |
| `check_circle` | `check_circle` | _dyn_ | via CSS | export |
| `chevron_left` | `chevron_left` | _dyn_ | via CSS | canonical |
| `close_alt` | `close` | _dyn_ | via CSS | export |
| `help_t` | `help` | _dyn_ | via CSS | canonical |
| `merge` | `merge` | _dyn_ | via CSS | canonical |
| `note` | `receipt_long` | _dyn_ | via CSS | export |
| `refresh` | `refresh` | _dyn_ | via CSS | canonical |
| `table_move` | `table_restaurant` | _dyn_ | via CSS | canonical |
| `transfer` | `swap_horiz` | _dyn_ | via CSS | canonical |

**73 registry entries · 94 static+JS uses · 12 dynamic-only entries · 55 distinct ligatures.**

**Ligature provenance (important):** **15 of 55** ligatures are literally attested in the export's own markup. The other **40 are canonical Material Symbols names** I selected for semantic equivalence (e.g. printer→`print`, truck→`local_shipping`, bell→`notifications`). All 55 **exist in the approved font** — nothing was invented — but the *choice* for those 40 is engineering judgement and should be ratified by the design owner.

## 3. Icons That Remain SVG (and why)

| Item | Occurrences | Why it was not migrated |
|---|--:|---|
| **Mezze wordmark** (`.mmark`, `viewBox 0 0 100 100`) | 3 | Brand mark, not an icon. No Material Symbol equivalent exists and inventing one would be a brand change. |
| **Sparkline** (`.spark`, `viewBox 0 0 320 112`) | 1 | Data visualisation drawn at runtime, not an icon. |
| **CSS `url()` lock** (`.railbtn.locked::after`) | 1 | Lives inside a CSS `background-image` data-URI. A font ligature cannot be used as a CSS background image; migrating it would require changing the layout mechanism. *(The same lock **as an inline icon** did migrate → `lock`.)* |
| **Empty chart node** | 1 | Placeholder `<svg>` with no geometry. |

**No icon was kept as SVG for lack of a glyph** — coverage of the required set is 55/55.

## 4. Accessibility Validation

- **Decorative icons hidden:** every mezze ligature renders as `<span class="mi" aria-hidden="true">`. This is a net **improvement** — the ligature text (`close`) is explicitly hidden from assistive tech, where the legacy bare `<svg>` relied on implicit behaviour.
- **No accessible names lost:** audited the originals — **zero** migrated `<svg>` carried `aria-*`, `role`, or `<title>`. Only the *excluded* wordmark/sparkline had `aria-hidden`, and they are untouched.
- **Button labels intact:** `aria-label` **63 → 63**, `role` 16 → 16, `aria-pressed` 14 → 14, `aria-current` 4 → 4 — all unchanged (the single `aria-hidden` delta is the helper source itself).
- **Keyboard navigation unaffected:** neither `<svg>` nor `<span>` is focusable; no tab order, focus ring, or handler was touched.
- **RTL:** `.mi{direction:ltr}` so ligature shaping is correct inside RTL containers; icon *placement* still follows the existing logical-property layout.

## 5. Performance Comparison

| | Amber (certified) | Mezze |
|---|--:|--:|
| Icon font fetched | **0 bytes** — no `.mi` elements exist, so the family is never referenced | **7,552 bytes**, once, then cached |
| Icon payload in `pos.html` | 15,230 B of inline SVG (unchanged) | + 13,423 B registry |
| `pos.html` total | 408,036 B | 422,139 B (**+14,103**) |

- Full font **369,656 → 7,552 B (−98.0%)**; the unshipped full face was deleted from the repo.
- `font-display:block` is used deliberately (not `swap`): with `swap` an icon font briefly renders the **literal word** "close". Block avoids that flash.
- Under mezze the DOM gets *lighter* (one `<span>` replaces multi-`<path>` SVG); amber runtime is bit-for-bit what it was.

## 6. Before/After Screenshots

**Not captured** — the CDP bridge freezes on the heavy `pos.html` (persistent across every phase). Font *rendering* was instead verified structurally: the subset is valid woff2, family name intact, and **all 55 ligature substitutions confirmed present in the GSUB table** by direct inspection (stronger than a pixel diff for "does the glyph exist"). An in-browser width test was attempted but the 10 KB base64 truncated in transport — noted rather than glossed over.
**Manual visual gate:** open `…/pos.html?token=<t>&appearance=mezze` and confirm icons on **Cashier / Payment / Kitchen / Reports / Live Ops** in **light + dark + RTL**, then `?appearance=amber` to confirm the certified build is unchanged.

## 7. Regression Assessment

- **Amber byte-identity — proven, not asserted.** The registry was extracted from the shipped file, executed in Node, and every amber render matched the original string from `git HEAD`. The 12 entries not found verbatim are the data/`mk()` icons whose full `<svg>` never existed literally (assembled at runtime); their 5 wrappers were confirmed to use *exactly* the assumed attributes, so runtime output is identical.
- **No new SVG literals introduced (0);** 21 geometries moved from markup into the registry.
- **Static markup** differs only by an added `data-ic` attribute; under amber `ICboot()` returns immediately, so the DOM is untouched and icons need no JS to appear.
- **Structural:** `node --check` OK, braces balanced, `IC` defined once, `ICboot()` invoked once, layer inside the IIFE, no name collisions.
- **Residual risk** is visual only (glyph shape/optical size differs from the bespoke SVGs by design) — that is what the manual gate is for.

## 8. Recommendation for Sign-Off

**RECOMMEND SIGN-OFF for P3**, conditional on two design-owner decisions:

1. **Manual visual gate** (5 workspaces × light/dark × RTL × amber/mezze) — the one check I cannot automate here.
2. **Ratify the 40 canonical ligature choices** in §2 that are not attested in the export sample.

**One finding to record:** the bundled Material Symbols face is a **static instance — it has no `fvar` table**, so the approved `FILL / wght / GRAD / opsz` axes **cannot actually vary**. The `font-variation-settings` declaration is kept (it is the approved configuration and is forward-compatible) but is currently **inert**, which means the export's `FILL 0→1` active-state treatment is not reproducible until a variable font is supplied. Flagged, not worked around.

*Not in production behaviour — active only when `data-appearance="mezze"` is set. P4 not started.*
