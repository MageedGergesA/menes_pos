# DESIGN-P3A.3 — Shop + QR Button Migration — Result

**Start commit `e8be9f1`** (rc3 `fb59c79`). Actual RC targets verified from Git this pass:
rc1=`ad32f3e`, rc2=`7fee641`, rc3=`fb59c79` (peeled commits — the earlier reports cited the
annotated-tag object hashes; these are the commits). **rc1/rc2/rc3 unmoved. No rc4.**

Scope: **shop.html + qr.html customer buttons only.** No kiosk / QuantityStepper / Status /
Alert / Input / Dialog / Card / Navigation / customer-shell / pos-prototype / backend changes.

## Verdict
**COMPLETE (shop + QR).** Every true customer action button migrated to the canonical `.mz-btn`;
legacy button visual CSS stripped; quantity/segmented/chips/dialog-close/card excluded. Certified
in a real browser across EN/AR × light/dark, real orders placed on both surfaces + DB-verified,
QR tamper guard confirmed intact. One contained customer-bridge token fix (no components.css change).

## Source
Re-read Component Language / Compound Library / Restaurant UX Patterns button sections + the
shop/QR self-order screens. Button contract unchanged (Hanken 700 LTR / IBM Plex Sans Arabic RTL,
h44, radius 11, brand via `--mz-`, one loud primary per step, destructive separated). **Fully
interpreted source: 8 / 40** (unchanged — the compound/customer specs corroborate but don't alter
the button contract).

## Inventory
### Shop (`shop.html`)
```
Shop legacy visual Button classes before = 4   (.langbtn .btn(+.dark/.off) .promobtn .cartbar-button)
Shop true Buttons migrated               = 9 markup sites (lang, opt-add, checkout, payonline,
                                              place, cart CTA, promo Apply, Rate link, Order-again)
Shop excluded controls                   = 6   (.chip category, .seg fulfil, .opt modifier,
                                              .sx dialog-close, .step quantity→P3E, .add card glyph
                                              [aria-hidden decoration inside the .prod card])
```
### QR (`qr.html`)
```
QR legacy visual Button classes before   = 5   (.langbtn .add .cartbtn .place .again)
QR true Buttons migrated                 = 9 markup sites (Bill, lang, add-to-cart, cart CTA,
                                              Send-to-kitchen, mod Add-to-order, Pay, Pay-online,
                                              Order-more)
QR excluded controls                     = 6   (.cat chips, .qus upsell card, .tipchip segmented,
                                              .modopt selectable, .x dialog-close, .stepper qty→P3E)
```

## Canonical mappings
| Legacy | Page | Classification | Canonical | Layout alias |
|---|---|---|---|---|
| `.btn` (opt-add, place) | shop | primary CTA | `.mz-btn --primary` | `.sfoot .mz-btn{width:100%}` |
| `.btn.dark` (checkout, payonline) | shop | secondary | `.mz-btn --secondary` | — |
| `.cartbar button` (View cart) | shop | sticky primary | `.mz-btn --primary` | `.shop-cart-cta` |
| `.promobtn` (Apply) | shop | secondary | `.mz-btn --secondary` | `.shop-promo` |
| `.langbtn` (ع) | shop | utility | `.mz-btn --secondary` | — |
| `.btn` (Rate `<a>`) | shop | primary link | `.mz-btn --primary` (stays `<a>`) | inline max-width |
| `.btn.dark` (Order again) | shop | secondary | `.mz-btn --secondary` | inline max-width |
| `.place` (Send/Pay/mod-Add) | qr | primary | `.mz-btn --primary` | `.placewrap .mz-btn`, `.qr-split` |
| `.place` (Pay online) | qr | secondary | `.mz-btn --secondary` | `.placewrap .mz-btn` |
| `.cartbtn` (View order) | qr | sticky primary | `.mz-btn --primary` | `.cartbtn` (anim+layout) |
| `.add` (+) | qr | add-to-cart | `.mz-btn --primary` | `.qr-add` (44×44) |
| `.langbtn#billbtn` (Bill) | qr | primary utility | `.mz-btn --primary` | — |
| `.langbtn#lang` | qr | utility | `.mz-btn --secondary` | — |
| `.again` (Order more) | qr | secondary | `.mz-btn --secondary` | `.again{margin-top}` |

**`.promobtn` result:** genuine secondary action → `.mz-btn --secondary` (visual responsibility removed).
**`.place` result:** primary submit (or secondary for Pay-online) → `.mz-btn`; **its dark-on-terracotta
contrast (~3.1:1) is FIXED** to white-on-brand. `.place` visual class fully removed.
**`.cartbtn` result:** sticky primary → `.mz-btn --primary`; `.cartbtn` kept for reveal animation +
internal count/label/total layout ONLY (no visuals). weight 400→700 fixed.
**`.again` result:** secondary → `.mz-btn --secondary`; `.again` kept for `margin-top` only.

**Legacy visual CSS removed:** shop `.langbtn`,`.btn`,`.btn.dark`,`.btn:disabled`,`.btn.off`,
`.cartbar button`,`.cartbar .cc/.ct`,`.promobtn`(×2). qr `.langbtn`,`.add`,`.add:active`,
`.cartbtn`(visual),`.place`,`.place:active`,`.place:disabled`,`.place#modadd`,`.done .again`(visual).
**Layout-only retained:** shop `.shop-cart-cta`/`.shop-promo`/`.sfoot .mz-btn`; qr `.qr-add`/
`.qr-split`/`.cartbtn`(anim)/`.again`(margin)/`.placewrap .mz-btn`. None set font/color/bg/radius/
border/focus/hover/pressed/disabled/elevation.
**Quantity controls (`.step`/`.stepper`):** left untouched → **DEFERRED DESIGN-P3E**.

## Token wiring (contained)
`components.css .mz-btn` consumes `--mz-text-primary`/`--mz-text-secondary`; `mezze-design.css`
provides `--mz-text`/`--mz-text-2`. Added aliases in **`mezze-customer.css`** (loaded only by the 6
customer pages — NOT cashier/kiosk): `--mz-text-primary:var(--mz-text); --mz-text-secondary:
var(--mz-text-2)`. Additive; cache `?v=d5→d6` on shop+qr. **components.css / cashier.css / kiosk.html
UNCHANGED** → cashier & kiosk unaffected by construction. Arabic font comes from the P3A.2
`[dir=rtl] .mz-btn{font-family:var(--mz-font-ar)}` rule (already shipped).

## Browser acceptance (real DOM, store `kioskstore`, QR table 41)
| State | Shop | QR |
|---|---|---|
| **EN Light** | PASS — primary #C0602E/white, secondary white/#2a2420, Hanken 700, r11, no gradient, hierarchy distinct, no overflow, console 0 | PASS — add 44×44 white/#C0602E, cartbtn primary Hanken 700, place white text, all r11, no overflow |
| **EN Dark** | PASS — primary #D89A54/#1C1305 (7.57:1), secondary #2a251d/#f5f1eb (13.52:1), distinct, no overflow, console 0 | PASS — place #D89A54/#1C1305 (7.57:1), secondary correct, no overflow |
| **AR Light** | PASS — IBM Plex Sans Arabic 700, r11, 44px, not clipped, no overflow | PASS — IBM Plex Sans Arabic 700, billbtn primary #C0602E r11, no overflow |
| **AR Dark** | PASS — IBM Plex Sans Arabic, #D89A54/#1C1305, distinct, no overflow (screenshot) | PASS — IBM Plex Sans Arabic 700, r11, 44px, not clipped (place أرسل للمطبخ, again اطلب المزيد, bill الحساب), no overflow |

- **Computed fonts:** EN **Hanken Grotesk** 700; AR **IBM Plex Sans Arabic** 700.
- **Brand:** #C0602E (light) / #D89A54 (dark). **Radius:** 11px everywhere.

### Touch geometry (rendered heights)
| Page | Control | Before | After |
|---|---|--:|--:|
| shop | cart CTA | 59 | 61 |
| shop | Place / Pay-online / Checkout / Promo / Lang | 44–55 | 44 |
| qr | cart CTA | 56 | 58 |
| qr | **Add (+)** | **40** | **44** (fixed) |
| qr | Place / Pay / Bill / Lang / Again | 44–50 | 44 |
**Smallest frequent customer target = 44×44** (QR Add, raised from 40). No target below 44×44.

### Keyboard / Focus / Disabled / Loading
- Native `<button>` / `<a>` throughout. **Tab** focuses; **focus-visible** renders (2px solid
  terracotta on inputs/chips; canonical `.mz-btn:focus-visible` = 2.5px `--mz-focus` present);
  **Enter activates** (verified — focused shop `#lang`, Enter toggled en→ar).
- **Disabled:** canonical `:disabled` (opacity .45, not-allowed); shop `#place` disables on empty
  cart / below-minimum; qr `#place` disables on empty cart.
- **Loading / double-submit:** place handlers set `btn.disabled=true` before the await; a triple
  rapid-click on shop Place created **exactly one** order (#3). Backend idempotency unchanged.

### Contrast (measured)
| Pair | Light | Dark |
|---|--:|--:|
| Primary text/bg | **4.24:1** | **7.57:1** |
| Secondary text/bg | 15.31:1 | 13.52–13.5:1 |
| Focus ring / bg | terracotta, visible | terracotta, visible |
**Honest note:** the light primary (white on #C0602E) = **4.24:1** — meets **AA-Large** but is ~0.26
below AA-normal (4.5) for labels under 18.66px-bold. This is the **canonical brand pairing**
(`--mz-brand #C0602E` / `--mz-on-brand #FFF`, system-wide across cashier/onboarding/kiosk/shop),
**not introduced by this pass** — the migration *improved* QR (dark-on-terracotta 3.1 → 4.24). Dark
mode passes AA-normal. Flagged as a pre-existing design-system item for a future contrast pass.

### Mobile viewports (item 26 — honest)
Requested 390px via resize, but the browser reports **`innerWidth: 1920`** — I **could not enforce an
exact device CSS viewport** in this environment, so I do not claim 360/390/430 device tests. What IS
verified: **horizontal overflow = 0** at the tested width on every state above; QR is intrinsically
`max-width:520` (centered mobile layout); shop switches to a 2-col grid at `≤520`. CTAs not clipped.

### Functional regression
- **Shop:** add → cart → checkout (name/phone) → Place → order **#3 draft**, done screen, single
  order (triple-click guard held). No amount/logic change.
- **QR:** add → cart → Send-to-kitchen → order **#2 draft**, **KDS ticket = 1**, 1 line, no duplicate.
- **QR security:** tampered `qr` token → `/qr/menu` and `/qr/order` both **REJECT** ("Invalid QR
  token for this table"); no fake order. Guard is server-side, untouched.

### Shared regression (item 33)
- **Kiosk:** Start still canonical (mz-btn--primary, #D89A54/#1C1305, Hanken, r11, 88px) — unchanged.
- **Cashier:** by construction — components.css/cashier.css unchanged; cashier does not load
  mezze-customer.css. Live re-render not required (no shared-component change reaches it).

## Tests
- Fresh install `-i mezze_bridge --without-demo=all` (mezze_runtime,mezze_invariants): **403/0/0**.
- Upgrade `-u mezze_bridge`: **403/0/0**.
- No route/security changes (reuses `/shop/*`, `/qr/*`, `/mezze/api/v1`).
- All changes are static assets → the Python test surface is unaffected.

## Duplication audit
```
Shop unexplained legacy Button visual systems = 0
QR   unexplained legacy Button visual systems = 0
```

## Remaining P3A debt
`pos.html` `.button--*` prototype (P3A.4 or documented exception) → then final product-wide
Button duplication audit → **P3A COMPLETE**. QuantityStepper (shop/qr `.step`/`.stepper`) = P3E.

## Re-score (conservative)
Button consistency ▲ (customer surfaces now canonical; hierarchy restored); customer action
hierarchy ▲ (primary/secondary distinct — was collapsed); touch ▲ (QR add 40→44); a11y ▲ (Arabic
font correct, QR place contrast 3.1→4.24/7.57). Design System Coherence **83 → 85%**; Overall Design
Readiness **82 → 84%**. (P3A still PARTIAL overall — pos.html prototype remains.)

## Verdict
**DESIGN-P3A.3 (Shop + QR) COMPLETE. rc1/rc2/rc3 unmoved. No rc4.**
Next operator decision: **DESIGN-P3A.4** — pos.html prototype migration OR documented prototype
exception → final Button duplication audit → P3A COMPLETE → DESIGN-P3B (Status/Badge).
