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

## pos.html prototype (DESIGN-P3A.4)
| Old class | Page | Classification | Canonical replacement | Layout alias | Visual debt removed |
|---|---|---|---|---|---|
| `.button` (base) | pos | button base | `.mz-btn` | — | yes |
| `.button--primary` | pos | primary | `.mz-btn--primary` | `.pos-flex` | yes |
| `.button--strong` | pos | primary (dark emphasis) | `.mz-btn--primary` | `.pos-flex` | yes |
| `.button--positive` | pos | success | `.mz-btn--success` | `.pos-flex` | yes |
| `.button--secondary` | pos | secondary | `.mz-btn--secondary` | — | yes |
| `.button--sm` | pos | small size | `.mz-btn--sm` | — | yes |
| `.button--block` | pos | full-width | (layout) | `.pos-block` | yes |
| `.iconbtn` | pos | icon button | `.mz-icon-btn` | `.mz-icon-btn svg` sizing | yes |

## Cashier (context layer — documented intentional)
`cashier.css` keeps a `.mz-btn` **context layer** (same vocabulary + `--mz-` tokens + canonical
radius/focus/hover/active/states) differing ONLY in cashier density (font-size 16 / padding) +
full-width charge/confirm + the P3A.4 contrast adaptation. Not a second vocabulary.

## Resolved — all old Button visual classes
`.startbtn .review .place .ghost .addbtn .lang .btn .btn.dark .btn.off .promobtn .cartbar-button
.cartbtn(visual) .again(visual) .button .button--* .iconbtn .add(qr)` → **all resolved** to the
canonical `.mz-btn`/`.mz-icon-btn` vocabulary; every legacy visual definition removed.

**Button styling systems: 5 → 1** ✅ (canonical `.mz-btn` only). **Unexplained legacy Button
vocabularies: 0.** Remaining page-local classes are **layout-only** (documented) or the customer
`.btn` compatibility bridge (flat brand fill for un-migrated customer-shell pages cfd/feedback/
courses/drivethru — a later shell pass, not a Button vocabulary). Quantity (`.qbtn/.step/.stepper`)
→ **P3E**.
