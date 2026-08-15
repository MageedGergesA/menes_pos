# CONV-2a — the category sidebar becomes one shared definition

The desktop category sidebar was written for the Register and lived inside the cashier's
asset bundle, so no page outside that bundle could reach it — which is the whole reason the
drive-thru had only a chip strip at every width. This pass moved it to
`static/design/category-nav.css` and proved the Register did not move by a pixel.

No layout was redesigned. The drive-thru board looks exactly as it did; what changed is
that the definition it will consume in CONV-2b now exists in one place.

## What moved

| | |
|---|---|
| New shared file | `addons/mezze_bridge/static/design/category-nav.css` |
| Rules moved | `.mz-catside` (base + the whole `@media (min-width:1280px)` block: branch chip, label, list, row, hover/active/focus, name, count) |
| Contract moved with it | `.mz-workspace:has(.mz-catside) .mz-catalog > .mz-catbar{display:none}` |
| Design-platform rules moved with it | `[data-mz-density="compact"|"comfortable"] .mz-catside__item` |
| Loaded by | `assets_cashier` (before `cashier.css`) **and** `static/drivethru.html` |
| Left in `cashier.css` | the **rail** (`.mz-nav`, `.mz-rail__ico`) — cashier shell, not category navigation |

Verified in the served bundle through the CSSOM: **one** `(min-width: 1280px)` block, each
`.mz-catside*` selector appearing exactly once, no second copy anywhere.

### One rule knowingly left behind

`:root[data-appearance="mezze"][data-mz-panel="left"] .mz-workspace > .mz-catside{order:2}`
stays in `cashier.css`. It is one third of a family that reorders **sidebar + catalogue +
order panel** together; the other two thirds are order-panel rules. Splitting a line off it
now would put a partial family in the shared file, so the whole family moves when the order
panel is extracted (CONV-2c). `test_02` excludes exactly this rule and asserts the carve-out
is exactly one rule wide — any *other* sidebar declaration reappearing in `cashier.css`
still fails.

### Why the order panel was not extracted in this pass

The plan listed it here. On inspection its rules are scattered across **five** regions of
`cashier.css` — the core panel (`.mz-cart*`/`.mz-line*`/`.mz-total*`), the 62px charge CTA,
`.mz-cart-actions`, a `@media (max-width:1100px)` override of `.mz-cart` itself, a selector
shared with the receipt, and the comp/tag/note-btn controls. Moving only the core would
leave `.mz-cart` defined in two files, which is the opposite of one effective source. It
gets its own pass and its own gate.

## Register zero-regression gate

Measured in a fixed-width iframe (the browser window would not resize reliably), on
`/mezze/pos` — the real route, not `?ws=register`. Same database, same theme
(`classic/lounge dark`), same catalogue of 172 products, before and after.

| | rail | category sidebar | menu | order panel | cols | card | media | search bar | overflow |
|---|---|---|---|---|---|---|---|---|---|
| **1920 before** | 68 | 201 | 1310 | 341 | 7 | 170.14 × 246.02 | 168.14² | 1310 × 58 | none |
| **1920 after** | 68 | 201 | 1310 | 341 | 7 | 170.14 × 246.02 | 168.14² | 1310 × 58 | none |
| **1440 before** | 68 | 201 | 830 | 341 | 4 | 186.75 × 262.63 | 184.75² | 830 × 58 | none |
| **1440 after** | 68 | 201 | 830 | 341 | 4 | 186.75 × 262.63 | 184.75² | 830 × 58 | none |
| **1280 before** | 68 | 201 | 670 | 341 | 3 | 199.66 × 275.55 | 197.66² | 670 × 58 | none |
| **1280 after** | 68 | 201 | 670 | 341 | 3 | 199.66 × 275.55 | 197.66² | 670 × 58 | none |
| **1024 before** | — | — (chips 683 × 83) | 683 | 341 | 4 | 150 × 225.88 | 148² | 683 × 58 | none |
| **1024 after** | — | — (chips 683 × 83) | 683 | 341 | 4 | 150 × 225.88 | 148² | 683 × 58 | none |

Category row at every width ≥1280, before and after: **176 × 44**, `min-height:44px`,
radius `11px`, `13px`, padding-inline-start `8px`. Gutter `12px`, grid padding `16px`
throughout. RTL measured at 1440 and 1024: identical geometry, panes mirrored
(`rail 1372..1440 · sidebar 1171..1372 · menu 341..1171 · order panel 0..341`).

**Structural geometry delta: 0px at every width, in both directions.** The comparison is a
field-by-field diff of 18 measured values per viewport; all six sets returned `IDENTICAL`.

Screenshots: `shots/conv2a-register-1920-before.jpg` → `shots/conv2a-register-1920-after.jpg`.
The only pixels that differ between them are the topbar's connectivity chips, which poll a
network state ("Local server online" vs "Checking…") — live data, not layout.

## Responsive contract, swept not sampled

| viewport | sidebar | chips |
|---|---|---|
| 1024 | none | flex |
| 1100 | none | flex |
| 1279 | none | flex |
| **1280** | **flex** | **none** |
| 1281 | flex | none |
| 1440 | flex | none |
| 1920 | flex | none |

Both visible: **0**. Neither visible: **0**. The boundary lands exactly on 1280.

## RTL and accessibility

| | result |
|---|---|
| Sidebar rule edge | LTR right, RTL left — one `border-inline-end`, no physical override |
| Row contents | name and count swap sides; the name is pushed off the leading edge |
| Physical `left:`/`right:`/`margin-left` in the shared file | **0** (asserted) |
| Touch floor | 44px, and the measured box is ≥44px — under LTR, RTL, compact and comfortable |
| Density | compact 6px / standard 0px / comfortable 16px padding-block; `min-height` untouched in all three |
| Focus | `.mz-catside__item:focus-visible` outline still present, asserted through the CSSOM |
| Selection | `aria-pressed` on every row; the active row is announced, not only coloured |

## Drive-thru foundation

| | |
|---|---|
| Consumes the shared product browser | **YES** (since CONV-1) |
| Consumes the shared desktop sidebar | **YES** — `category-nav.css` links and serves 200; canonical markup rendered on the board gets 176px basis and 44px rows |
| Consumes the compact chip form | **YES** — unchanged, still the board's navigation today |
| Ordering geometry shared | product browser + category navigation; the order panel is CONV-2c |
| Full layout converged | **NO** — expected: the four-pane Order Taker is CONV-2b |

The board renders **zero** sidebars today, asserted by `test_25`. CONV-2a makes the
definition available; it does not restyle anything an operator currently sees.

The shared sheet needs the platform **design layer** (tokens + canonical components), which
every Mezze surface already loads — and nothing from the cashier bundle. Proved by rendering
the sidebar in a document that links only the five design sheets, with no Owl and no
`assets_cashier`.

## Tests

`tests/test_category_nav_shared.py` — 15 tests, three classes: source (single definition,
wiring, no physical direction, density never touches hit area), Register (canonical sidebar,
exactly one navigation, focus ring), shareable (breakpoint sweep, no-bundle rendering, RTL
mirroring, density, the board serves it, the board is unchanged).

### Negative controls — every sabotage restored byte-identically (sha256 verified)

| sabotage | tests that failed |
|---|---|
| delete the `:has(.mz-catside)` contract rule | 3 — `test_03`, `test_11`, `test_20` |
| drop the row to `min-height:36px` | 6 — `test_06`, `test_10`, `test_21`, `test_22`, `test_23`, `test_24` |
| re-add a second `.mz-catside` block to `cashier.css` | 2 — `test_02`, `test_10` |

## Two things this pass got wrong first, recorded

* **The first RTL assertion had no teeth in one direction and lied in the other.** The
  standalone harness linked the component sheets but not the token sheet, and without
  `--mz-border` the whole `border-inline-end` declaration is dropped — so both edges read
  0px and the test failed for a reason that had nothing to do with mirroring. The harness now
  carries the appearance attributes every page is stamped with server-side.
* **`textAlign === 'start'` is a string check, not a mirroring check.** It depends on how a
  given Chrome serialises a computed value. Replaced with a geometric assertion: where the
  name and the count actually sit inside the row.
