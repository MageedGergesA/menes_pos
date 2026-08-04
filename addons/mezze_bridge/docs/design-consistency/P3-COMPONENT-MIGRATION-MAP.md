# P3-COMPONENT-MIGRATION-MAP — Button family

Canonical source: `static/design/components.css` (`.mz-btn` + variants). One row per migrated
legacy class. "Layout alias remaining?" = a page-local class kept for layout/placement ONLY
(never visual). "Visual debt removed?" = the legacy class's font/color/bg/radius/border/focus/
state declarations were deleted.

## Kiosk (DESIGN-P3A.2)
| Old class | Page | Classification | Canonical replacement | Layout alias | Visual debt removed |
|---|---|---|---|---|---|
| `.startbtn` | kiosk | primary hero | `.mz-btn --primary` | `.kiosk-hero` | yes |
| `.review` | kiosk | primary forward | `.mz-btn --primary` | `.kiosk-cta` | yes |
| `.place` | kiosk | primary submit | `.mz-btn --primary` | `.kiosk-place` | yes |
| `.ghost` | kiosk | secondary | `.mz-btn --secondary` | `.kiosk-secondary` | yes |
| `.addbtn` | kiosk | add-to-cart | `.mz-btn --primary` | `.kiosk-add` | yes |
| `.lang` | kiosk | utility | `.mz-btn --secondary` | `.kiosk-lang` | yes |

## Shop (DESIGN-P3A.3)
| Old class | Page | Classification | Canonical replacement | Layout alias | Visual debt removed |
|---|---|---|---|---|---|
| `.btn` (opt-add, place) | shop | primary | `.mz-btn --primary` | `.sfoot .mz-btn` (width) | yes |
| `.btn.dark` (checkout, payonline) | shop | secondary | `.mz-btn --secondary` | — | yes |
| `.btn` (Rate) | shop | primary link `<a>` | `.mz-btn --primary` | inline max-width | yes |
| `.btn.dark` (Order again) | shop | secondary | `.mz-btn --secondary` | inline max-width | yes |
| `.cartbar button` (View cart) | shop | sticky primary | `.mz-btn --primary` | `.shop-cart-cta` | yes |
| `.promobtn` (Apply) | shop | secondary | `.mz-btn --secondary` | `.shop-promo` | yes |
| `.langbtn` (ع) | shop | utility | `.mz-btn --secondary` | — | yes |

## QR (DESIGN-P3A.3)
| Old class | Page | Classification | Canonical replacement | Layout alias | Visual debt removed |
|---|---|---|---|---|---|
| `.place` (Send/Pay/mod-Add) | qr | primary | `.mz-btn --primary` | `.placewrap .mz-btn`, `.qr-split` | yes |
| `.place` (Pay online) | qr | secondary | `.mz-btn --secondary` | `.placewrap .mz-btn` | yes |
| `.cartbtn` (View order) | qr | sticky primary | `.mz-btn --primary` | `.cartbtn` (anim+layout) | yes |
| `.add` (+) | qr | add-to-cart | `.mz-btn --primary` | `.qr-add` (44×44) | yes |
| `.langbtn#billbtn` (Bill) | qr | primary utility | `.mz-btn --primary` | — | yes |
| `.langbtn#lang` | qr | utility | `.mz-btn --secondary` | — | yes |
| `.again` (Order more) | qr | secondary | `.mz-btn --secondary` | `.again` (margin) | yes |

## Onboarding (DESIGN-P3A.1) & admin (mezze-design.js)
| `.btn`/`.btn.primary` | onboarding | primary/secondary/icon | `.mz-btn --primary/--secondary`, `.mz-icon-btn` | — | yes |
| `.mz-btn.small`/`.danger` | admin (pos.html) | sm/danger | `.mz-btn--sm`/`--danger` | — | yes (dup removed) |

## Excluded (NOT Button — documented, not migrated)
| Pattern | Where | Reason | Future family |
|---|---|---|---|
| `.step`/`.stepper`/`.qbtn` | shop/qr/kiosk | quantity ± | **P3E QuantityStepper** |
| `.svcbtn`/`.seg`/`.tipchip` | kiosk/shop/qr | selectable segmented choice | Segmented/Choice |
| `.cat`/`.chip` | all | category filter chips/tabs | Chips/Tabs |
| `.opt`/`.modopt` | shop/qr | modifier option rows | Selectable list |
| `.qus` | qr | upsell suggestion card | Compound/Card |
| `.sx`/`.x` | shop/qr | dialog close (✕) | **Dialog** |
| `.n`/`.cnt`/badges | all | status/count badge | **P3B Status/Badge** |
| `.prod`/`.card`/`.add`(shop span) | shop/qr | product card / card glyph | **Card** |

## Not yet migrated (remaining Button debt)
| Pattern | Where | Status |
|---|---|---|
| `.button--*` | pos.html | **prototype** — P3A.4 (migrate or documented exception) |

**Button styling systems:** 5 → **2** (canonical `.mz-btn` + the pos.html `.button--*` prototype).
Target →1 pending only the pos.html prototype decision.
