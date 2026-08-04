# P3-BUTTON-INVENTORY (exact, corrected)

DESIGN_P3A_START_COMMIT `553b21b`. Corrects the earlier over-count (a `\.btn--` grep
matched the `mz-btn--` substring — the Owl cashier was **already** canonical).

## Accurate button-styling sources (BEFORE P3A)
| System | Where it is **styled** | Usage | Verdict |
|---|---|---|---|
| **`.mz-btn` (canonical)** | `static/src/cashier/cashier.css` | Owl cashier: 59 `mz-btn` + `--primary`(12)/`--ghost`(26)/`--confirm`(8)/`--danger`(4)/`--charge`(1)/`--sm`(3) | **already canonical name**, but styled in cashier.css (not shared), radius/padding cashier-local |
| **`.mz-btn` (2nd def)** | `static/mezze-design.js` (generated admin CSS) | admin/design surfaces | **duplicate `.mz-btn` definition** (admin variant: h44/pad0-16/radius10) |
| **`.button--*`** | `static/pos.html` (inline) | pos.html **design prototype** only: primary(21)/positive(10)/block(7)/strong(4)/secondary(3)/sm(3) | separate system, prototype surface |
| **`.btn` (per-file)** | `courses/onboarding/drivethru/feedback/shop` inline | full-width CTA, **gradient** bg, radius 13/14/15 | per-file drift (gradient = off-source) |
| **ad-hoc** | kiosk `.startbtn/.svcbtn/.addbtn/.place`, qr `.place/.cartbtn/.again`, shop `.promobtn`, pos `.charge` | per-page | per-page; kiosk = large-touch **governed specialization** |

**Button styling vocabularies before = 5** (canonical mz-btn, mz-design.js mz-btn,
`.button--*`, per-file `.btn`, per-page ad-hoc). **Class-name count ~12+.**

## After P3A (this pass)
| Change | Result |
|---|---|
| Canonical `.mz-btn` moved to ONE shared file `static/design/components.css` (source-exact: h44 / radius-md 11 / pad 0-20 / Hanken 700 / `--mz-brand`; variants primary/secondary/tertiary/ghost/danger/success/charge/confirm; sizes compact/default/touch; base+`.mz-icon-btn`; all states + focus + reduced-motion) | **1 canonical source** |
| Owl cashier `.mz-btn` (cashier.css) — **left unchanged** (already canonical: same name + `--mz-` tokens, verified at P2). A consolidation into components.css was attempted then **reverted** because the Owl app didn't live-mount on the fresh test serve this session (environmental; valid bundle; no console errors) — no unverified change shipped to the production cashier. File-level dedup deferred to a live-verified pass. | **cashier already canonical; unchanged** |
| components.css `<link>` added to all 9 static SPAs + checkout template + assets_cashier bundle | `.mz-btn` available product-wide |
| Customer `.btn` gradient → **flat `--mz-brand`** + canonical font/radius via `mezze-customer.css` (`[data-appearance="mezze"] .btn`), cache `v=d4→d5` (shop/qr/cfd/feedback/courses/drivethru) | **6 customer surfaces' primary CTA canonicalized** (source: no gradients) |

## Explicitly NOT migrated this pass (honest — remaining P3A work)
- `static/pos.html` `.button--*` (design **prototype** surface).
- `static/mezze-design.js` second `.mz-btn` (admin generated CSS) — duplicate to reconcile.
- kiosk `.startbtn/.svcbtn/.addbtn/.place` — **governed large-touch specialization** (Part 22: preserve scale); already on Hanken + terracotta; not force-shrunk to standard `.mz-btn`.
- onboarding `.btn` (admin console) — still its own inline style.
- Per-page secondary/ad-hoc (`.place/.cartbtn/.again/.promobtn`).
- Full **markup** migration to `.mz-btn` class names (customer buttons canonicalized by CSS override, not yet by class rename) + dead-CSS removal.

**→ DESIGN-P3A is PARTIAL, not COMPLETE. No rc4.** See `DESIGN-P3A-BUTTON-RESULT.md`.

---

## Kiosk section (DESIGN-P3A.2 — exact inventory)

Source: `static/kiosk.html` (single file; inline `<style>` + inline `<script>`). Links
`design/foundation.css` + `design/components.css` (NOT mezze-design.css/mezze-customer.css).

### Every kiosk action-style class, classified
| Class | Element(s) | Classification | Decision |
|---|---|---|---|
| `.startbtn` | `#k-startbtn` "Order here", `#k-newbtn` "New order", `#k-imhere` "I'm here" | **BUTTON** (hero primary, large-touch) | **MIGRATE** → `mz-btn mz-btn--primary` + layout `.kiosk-hero` |
| `.review` | `#k-review` "Review order" (cart bar) | **BUTTON** (forward primary) | **MIGRATE** → `mz-btn mz-btn--primary` + `.kiosk-cta` |
| `.place` | `#k-place` "Place order" | **BUTTON** (primary submit / pay-at-counter) | **MIGRATE** → `mz-btn mz-btn--primary` + `.kiosk-place` |
| `.ghost` | `#k-back` "Add more items" | **BUTTON** (secondary) | **MIGRATE** → `mz-btn mz-btn--secondary` + `.kiosk-secondary` |
| `.addbtn` | per-card "Add" (JS-generated) | **BUTTON** (add-to-cart action — NOT quantity) | **MIGRATE** → `mz-btn mz-btn--primary` + `.kiosk-add` |
| `.lang` | `#k-lang` language toggle | **BUTTON** (utility) | **MIGRATE** → `mz-btn mz-btn--secondary` + `.kiosk-lang` |
| `.svcbtn` / `.svcbtn.on` | Takeaway / Eat in | **SELECTABLE CHOICE (segmented)** — mutually-exclusive `.on` selection | **EXCLUDE** (not a button) → future Segmented component |
| `.cat` / `.cat.on` | category filter | **TAB / CHIP** — selectable filter | **EXCLUDE** → future Chips/Tabs |
| `.qbtn` | cart `−` / `+` | **QUANTITY CONTROL** | **DEFER → DESIGN-P3E QuantityStepper** (untouched) |
| `.cartbar .n` | count | **NON-BUTTON (badge)** | → DESIGN-P3B Status/Badge |
| `.logo`, `.card`, `.pic`, `.cn`, `.totrow`… | — | **NON-INTERACTIVE** | out of scope |

### Counts
```
Kiosk legacy Button classes before = 6   (.startbtn .review .place .ghost .addbtn .lang)
Kiosk true Button classes to migrate = 6
Quantity/non-Button exclusions = 5        (.qbtn quantity; .svcbtn + .cat selectable choices;
                                           .n badge; non-interactive containers)
```

### Token wiring decision (item 4)
`components.css` buttons consume `--mz-text-primary`/`--mz-text-secondary`/`--mz-surface-2`/
`--mz-brand`/`--mz-on-brand`/… . **mezze-design.css defines `--mz-text` (not `-primary`)**, so
linking it would NOT satisfy the button contract (same reason onboarding P3A.1 needed a bridge).
Chosen mechanism: a **token bridge on kiosk `:root`** mapping the button's exact contract onto
kiosk's existing palette (which already equals the canonical terracotta: `--acc` = #C0602E light /
#D89A54 dark) — NOT a new/duplicate palette. Geometry/type come from the already-linked
foundation.css; button rules from components.css. **`--mz-on-brand` set to the canonical source
ink (#FFFFFF light / #1C1305 dark)** — this FIXES the kiosk's pre-existing white-on-#D89A54 dark
contrast drift (~2.2:1 → 7.6:1). Non-button surfaces keep kiosk's `--acc`/`--card` (item 23).
