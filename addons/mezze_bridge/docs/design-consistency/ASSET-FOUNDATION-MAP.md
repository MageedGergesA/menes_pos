# Asset & Foundation Map (DESIGN-P2)

## The Mezze `--mz-` foundation is TWO complementary CSS files (one source of truth each)

| File | Owns | Themed? | Loaded by |
|---|---|---|---|
| `static/mezze-design.css` (pre-existing) | **colors + theme/accent registry** (`--mz-brand/-canvas/-surface/…`, 22 theme×accent blocks) | yes, `[data-appearance="mezze"]` | pos, shop, qr, cfd, feedback, courses, drivethru (7) |
| `static/mezze-customer.css` (pre-existing) | customer bridge: maps customer local tokens → `--mz-` | — | shop, qr, cfd, feedback, courses, drivethru (6) |
| **`static/design/foundation.css` (DESIGN-P2, new)** | **fonts (`@font-face`) + font/size/weight/spacing/radius/motion/density primitives** (NO colors) | n/a | **all 9 static files + checkout + assets_cashier** |

`foundation.css` **complements** `mezze-design.css` — it adds the non-color layer that
file lacks, and defines **no** color token (avoids a second color source).

## How each surface loads the foundation

| Surface | Mechanism |
|---|---|
| 9 static HTML SPAs (`pos/shop/qr/kiosk/onboarding/courses/drivethru/cfd/feedback`) | `<link rel="stylesheet" href="design/foundation.css">` in `<head>` (after charset) |
| `/mezze/pos` (Owl cashier) | `mezze_bridge/static/design/foundation.css` added to the `mezze_bridge.assets_cashier` bundle, **before** `static/src/cashier/**` so cashier CSS can consume/override |
| `/checkout/s/<token>` (payment) | `<link href="/mezze_bridge/static/design/foundation.css">` in the QWeb `<head>` |

## Bundle notes (Part E / AF)
- Foundation is **not** dumped into `web.assets_common` (would affect unrelated Odoo
  screens); it is scoped to Mezze surfaces only.
- Font `@font-face` uses **absolute** URLs (`/mezze_bridge/static/fonts/…`) so they
  resolve identically whether served as a raw static file **or** bundled — the browser
  downloads each face **once** (same absolute URL across all consumers, incl. pos.html's
  own inline `@font-face`).
- `assets_cashier` fresh-install compiled cleanly (403/0/0), so the bundle addition is
  valid.

## Open architectural decision
Whether to keep `foundation.css` as a separate complementary file or fold its
font/geometry primitives into `mezze-design.css` (single foundation file). Deferred to
operator review — `mezze-design.css` is the operator's D1 design-platform artifact.
