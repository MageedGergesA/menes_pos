# Cashier ↔ Drive-Thru ordering convergence — audit

Written before CONV-1 changed anything. It corrects a claim I made in the DT-UX7A
report, and that correction changes the direction of the remaining passes.

## Correction to the DT-UX7A report

DT-UX7A said *"the Register already had a complete server-authoritative configurator
… and the Register already used it."* Half of that is wrong.

* The **server** half is right and unchanged: `_product_modifiers()`,
  `_line_attr_values()`, `price_extra`, persistence onto the order line and
  `_line_note()` into KDS are all production code, reached by `/bootstrap` and
  `/drivethru/create`.
* The **client** half is wrong. The configurator I pointed at (`modCtx`, `comboCtx`,
  `halfCtx`) lives in `static/pos.html`, whose first line reads
  *"DESIGN PROTOTYPE — NON-TRANSACTIONAL. Kept as a visual reference only. The
  production cashier is the standalone Owl app served at /mezze/pos."*

The production Register is `static/src/cashier/**` (Owl, bundle
`mezze_bridge.assets_cashier`) and it has **no product configurator at all** —
`grep` for modifier/attribute/combo across its JS returns only three comments in
`order_store.js` anticipating that "modifiers/notes/context are legitimately distinct
lines and must NOT merge". Nothing creates them.

**So the drive-thru configurator built in DT-UX7A is currently the only production
client configurator in Mezze.** CONV-3 is therefore not "give the drive-thru the
Register's configurator" but the reverse, or a shared extraction. Recorded here so
the plan is built on what is actually in the repository.

## The two implementations

| | Cashier Register | Drive-Thru Order Taker |
|---|---|---|
| Technology | Owl app, asset bundle | static HTML page, inline JS |
| Route | `/mezze/pos` → `mezze_bridge.cashier_page` | `/mezze/drivethru` → `static/drivethru.html` |
| Product source | `/bootstrap` | `/bootstrap` — **already the same** |
| Pricing | server | server — **already the same** |

That technology split is the real constraint. Owl components cannot be imported into
a static page without pulling the whole cashier bundle into it, and the drive-thru
board is deliberately a single self-contained page (it is also the surface an
appliance browser loads). So convergence here is **not** "mount the Owl components";
it is "make both consume one definition of the canonical thing".

## Feature-by-feature

| Feature | Cashier | Drive-thru | Same impl? | Should share? | Gap |
|---|---|---|---|---|---|
| Product source | `/bootstrap` | `/bootstrap` | **YES** | yes | none |
| Pricing authority | server | server | **YES** | yes | none |
| Attribute/modifier data | `/bootstrap` `modifiers[]` | same, now consumed | **YES** | yes | none |
| Product **card** | `.mz-tile` image-led, 141×227 reference, quick-add "+", 86 badge | bespoke `.mi` text tile, 130px, no image | **NO** | **YES** | **CONV-1** |
| Product **grid** | `.mz-grid`, `minmax(154px,1fr)`, 12px | `.menu`, `minmax(130px,1fr)`, 10px | **NO** | **YES** | **CONV-1** |
| Categories | `.mz-catbar` / `.mz-cat` chips + counts + favourites | **absent** — one flat list of 172 | **NO** | **YES** | **CONV-1** |
| Search | `.mz-searchbar` + Enter-to-add highlight | **absent** | **NO** | **YES** | **CONV-1** |
| Product image | real Odoo `/web/image/.../image_256` + initials fallback | none | **NO** | **YES** | **CONV-1** |
| 86 / availability | `.mz-tile--out` + badge + toggle | not shown | **NO** | partly (toggle is a permission) | CONV-1 (display) |
| Cart line model | `order_store.js` | local array with `lineKey` | **NO** | investigate | CONV-2 |
| Cart panel | `cart.js/xml` canonical | bespoke `.cartline` | **NO** | **YES** | CONV-2 |
| Configurator | **NONE** | built in DT-UX7A | **NO** | **YES — direction reversed** | CONV-3 |
| Combos | server publishes; neither client configures | same | n/a | yes | CONV-3 |
| Primary CTA | Charge → payment | Confirm & Send → kitchen | **NO** | **must stay different** | keep |
| Vehicle / lane / queue / timer / OCB | n/a | drive-thru only | n/a | **no** | keep separate |

## Where the duplication actually is

The canonical card is **already partly shared**: `.mz-card, .mz-tile, …` in
`static/design/components.css` owns the surface, radius, border and selected state,
and the drive-thru page already links that file.

What is **not** shared is the image-led card geometry — `.mz-grid`, `.mz-tile__media`,
`.mz-tile__body`, `.mz-tile-name`, `.mz-tile-price`, `.mz-tile__quick-add`,
`.mz-tile-badge`, `.mz-catbar`, `.mz-searchbar` — which lives in
`static/src/cashier/cashier.css`, i.e. **inside the cashier's asset bundle**, unreachable
from any page outside it. About 140 lines, heavily annotated with the measured
reference geometry.

That is the whole of CONV-1's real work: **move those rules into the shared design
layer so there is one definition**, then have the drive-thru render the canonical
markup against them. Not "write drive-thru cards".

## CONV-1 classification

| Piece | Verdict |
|---|---|
| `.mz-grid` / `.mz-tile*` / `.mz-catbar` / `.mz-searchbar` CSS | **EXTRACT SHARED** — out of the cashier bundle into `static/design/product-browser.css`, linked by both |
| Drive-thru `.menu` / `.mi` / `.mn` / `.mp` | **REMOVE DUPLICATE** |
| Drive-thru product markup | **REUSE DIRECTLY** — canonical `.mz-tile-cell` / `.mz-tile` markup |
| Product image route | **REUSE DIRECTLY** — `/web/image/product.product/<id>/image_256`; the drive-thru route is `auth='user'`, same as the Register, so the session authorises it and no token is exposed |
| Categories + search | **REUSE DIRECTLY** — canonical classes, drive-thru supplies the data it already boots with |
| Cashier `cashier.css` | **DO NOT CHANGE** behaviour — the extracted rules keep their bundle position, so the Register's cascade is untouched |
| Queue / vehicle / lane / timer / OCB | **KEEP DRIVE-THRU SPECIFIC** |
| Cart, configurator, CTA | **DO NOT CHANGE** in CONV-1 |

## Risk the extraction must not take

Moving rules out of `cashier.css` must not change the Register by a pixel. The
extracted file is loaded in the cashier bundle **immediately before** `cashier.css`
and after `components.css`, so every later rule still wins exactly as it does today.
The Register is re-measured after the move, not assumed.
