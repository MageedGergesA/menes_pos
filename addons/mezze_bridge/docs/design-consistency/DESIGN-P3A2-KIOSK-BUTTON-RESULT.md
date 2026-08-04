# DESIGN-P3A.2 — Kiosk Button Migration — Result

**Start commit `e341988`** (rc3 `fb59c79`; rc1/rc2/rc3 unmoved; **no rc4**). Scope: **kiosk
buttons only** — no shop/QR/pos.html prototype/Status/Dialog/Quantity work.

## Verdict
**COMPLETE (kiosk).** All 6 kiosk action-button classes migrated to the canonical `.mz-btn`;
legacy button visual CSS removed; quantity/segmented/chips/badge correctly excluded. Certified
in a real browser across EN/AR × light/dark, with a live pay-at-counter order placed + DB-verified.
One narrow shared-component fix (RTL Arabic font) made + consumers regression-checked.

## Inventory
```
Kiosk legacy Button classes before = 6   (.startbtn .review .place .ghost .addbtn .lang)
Kiosk true Button classes migrated  = 6
Quantity/non-Button exclusions      = 5   (.qbtn quantity→P3E; .svcbtn + .cat selectable
                                           choices; .n badge→P3B; non-interactive containers)
```

## Source mapping (canonical contract)
Hanken Grotesk 700 (LTR) / **IBM Plex Sans Arabic (RTL)**, radius 11 (`--mz-radius-md`), brand
via `--mz-`, one loud primary per screen (hero on Start / Review in cart bar / Place in sheet),
no destructive action in the kiosk. Kiosk large-touch (46–88px) preserved as governed
specialization (item 3/16).

| Legacy | Element(s) | Canonical class | Layout-only (kiosk-*) | Role |
|---|---|---|---|---|
| `.startbtn` | Order here / New order / I'm here | `mz-btn mz-btn--primary` | `.kiosk-hero` | primary hero |
| `.review` | Review order (cart bar) | `mz-btn mz-btn--primary` | `.kiosk-cta` | primary forward |
| `.place` | Place order | `mz-btn mz-btn--primary` | `.kiosk-place` | primary submit (pay-at-counter, brand — not the green `--confirm`) |
| `.ghost` | Add more items | `mz-btn mz-btn--secondary` | `.kiosk-secondary` | secondary |
| `.addbtn` | per-card Add (JS) | `mz-btn mz-btn--primary` | `.kiosk-add` | add-to-cart (NOT quantity) |
| `.lang` | language toggle | `mz-btn mz-btn--secondary` | `.kiosk-lang` | utility |

**Legacy visual classes removed:** `.startbtn` `.review`(`.cartbar .review`) `.place` `.ghost`
`.addbtn` `.lang` — all their bg/gradient/color/font/radius/border/shadow deleted. **Dead
`.card.off .addbtn` removed** (its `off` state was never applied in JS). **Layout-only retained:**
the six `.kiosk-*` classes set ONLY width / min-height / padding / font-size / margin — no
font-family/weight, color, background, border, radius, focus, hover, pressed, disabled, elevation.

## Token wiring (item 4)
`components.css` buttons consume `--mz-text-primary`/`--mz-surface-2`/`--mz-brand`/`--mz-on-brand`…
`mezze-design.css` defines `--mz-text` (not `-primary`), so **linking it would not satisfy the
button contract**. Chosen: a **token bridge on kiosk `:root`** mapping the button's exact contract
onto kiosk's existing palette (which already equals the canonical terracotta: `--acc` = #C0602E
light / #D89A54 dark) — not a duplicate palette. Geometry/type from the already-linked
`foundation.css`. **`--mz-on-brand` set to the canonical source ink (#FFFFFF light / #1C1305
dark)**, which FIXES the kiosk's pre-existing white-on-#D89A54 dark contrast drift (~2.2:1 → 7.57:1).
Non-button surfaces keep `--acc`/`--card` (item 23). Verified resolved: `--mz-brand` #D89A54(dk)/
#C0602E(lt), `--mz-on-brand` #1C1305(dk)/#FFFFFF(lt), `--mz-radius-md` 11, `--mz-font-text` Hanken,
`--mz-surface` #211a26(dk)/#fff(lt), `--mz-text-primary` #f4eef7(dk)/#241a2c(lt).

## Shared canonical fix (item 23/24)
Found during Arabic verification: the base `.mz-btn` hard-codes `--mz-font-text` (Hanken, no Arabic
glyphs) with no RTL variant → Arabic labels fell back to a system font on **every** surface. Added
to `components.css` (additive, RTL-only): `[dir="rtl"] .mz-btn,[dir="rtl"] .mz-icon-btn{font-family:
var(--mz-font-ar)}`. Now all surfaces' Arabic buttons compute IBM Plex Sans Arabic. **Cannot affect
LTR.** Consumers checked below.

## Browser certification (real DOM, provisioned store `kioskstore`, config 105, open session)
### English — Light
Primary (place/add/hero) `#C0602E` bg / **white** / Hanken 700 / radius 11. Secondary (back/lang)
white / `#241a2c` / radius 11. Contrast: **primary 4.24:1** (AA **Large** — kiosk labels are
18–28px bold; this is the canonical brand pairing used system-wide, not a kiosk regression);
**secondary 16.68:1**. No horizontal overflow. Console 0.
### English — Dark
Primary `#D89A54` bg / **`#1C1305` ink** / Hanken 700 / radius 11. Secondary `#211a26` / `#f4eef7`.
Contrast: **primary 7.57:1** (AA normal ✓), **secondary 14.85:1**. Disabled: opacity .45 +
not-allowed. No overflow. Console 0.
### Arabic — Light  &  Arabic — Dark  (real ar labels, dir=rtl)
Buttons compute **IBM Plex Sans Arabic 700**; labels (اطلب من هنا / إرسال الطلب / أضف المزيد /
مراجعة الطلب) not clipped; geometry + radius 11 preserved; hierarchy intact; icons not mirrored;
no overflow. Arabic+Dark screenshot shows the terracotta hero with dark ink (contrast fix) + the
excluded segmented service choices retaining their selectable-card look.

### Computed evidence
- English font: **Hanken Grotesk** (weight 700). Arabic font: **IBM Plex Sans Arabic** (weight 700).
- Brand: **#C0602E** (light) / **#D89A54** (dark). Radius: **11px** everywhere.

### Touch geometry (rendered heights)
| Control | Before ≈ (from original CSS pad+font) | After | ≥44 floor |
|---|--:|--:|:--:|
| hero (Order/New/I'm here) | ~92 | **88** | ✓ |
| Place order | ~79 | **76** | ✓ |
| Review order | ~66 | **64** | ✓ |
| Add more items (secondary) | ~60 | **60** | ✓ |
| Add (per card, frequent) | ~55 | **54** | ✓ |
| Language (utility) | ~46 | **46** | ✓ |
Smallest **frequent** kiosk target: **Add 54×… px**; utility Language 46px. All large-touch
preserved (46–88px) — **no frequent action dropped below its ~48–64 intent** (the `.kiosk-*`
min-heights were tuned up to match the originals after an initial draft measured slightly smaller).

### Keyboard / Focus / States
- **Keyboard:** Tab focuses native `<button>`; **Enter activates** (verified — toggled language
  ar→en). No custom key handling added.
- **Focus:** `:focus-visible` = true, **2px solid terracotta** outline (visible on light + dark);
  canonical rule `outline:2.5px solid var(--mz-focus)` present, `--mz-focus`=#D89A54(dk)/#C0602E(lt).
- **Disabled:** opacity .45 + cursor not-allowed (canonical — an improvement; old `.place` had no
  disabled style). Place button's in-flight `disabled=true` now reads as disabled.
- **Pressed:** canonical `:active{transform:scale(.97)}`; **Reduced motion:** honored (canonical
  `@media (prefers-reduced-motion)` disables transition/transform; kiosk's own reduced-motion block
  also present).

### Business smoke (item 22) — real order placed + DB-verified
Journey: Start → Add (Baklava + Falafel) → Review → **Place order** (all migrated buttons).
- UI: cart USD 70.00 → done screen, tracking **#1**, no error.
- DB (`verify_kiosk.py`): order #1 **state=draft** (unpaid — pay-at-counter, NOT faked paid),
  channel=**kiosk**, service=**takeaway**, total **80.5** (70 + 15% tax, server-side — unchanged),
  **KDS tickets=1**, lines=2. **Single order (no duplicate), amount correct, quantity/order/payment
  logic untouched.**
- Console: **0** across the whole journey.

### Shared regression (item 24)
- **Customer shop** — LIVE: `.btn` primary still canonical (flat `#D89A54`, Hanken 700, radius 11,
  no gradient). Console **0**.
- **Owl cashier** — `cashier.css` (which owns the cashier's `.mz-btn`) is **untouched this pass**;
  the only shared change is the RTL-additive rule (cannot affect LTR). Cashier was live-certified at
  P3A.1 (Charge `#C0602E`/Hanken/50px); the upgrade recompiled the assets_cashier bundle and passed
  403/0/0. In Arabic it now additionally gains IBM Plex Sans Arabic. No LTR regression possible.

## Tests
- **Fresh install (backend suite, item 28/29): 403 / 0 / 0, exit 0** (`-i mezze_bridge
  --without-demo=all --test-tags mezze_runtime,mezze_invariants`).
- **Upgrade (item 30): 403 / 0 / 0, exit 0** (`-u mezze_bridge` on the existing DB — bundle
  recompiled with the new components.css; kiosk reopened, no stale button CSS).
- No route/security changes (kiosk reuses existing `/shop/*` + `/mezze/api/v1`; no new routes).

## Remaining kiosk Button debt
**None** — every kiosk action button is canonical; quantity stepper deferred to P3E (documented).

## Remaining P3A debt elsewhere (unchanged this pass)
shop `.promobtn`, qr `.place/.cartbtn/.again`, pos.html `.button--*` prototype, final duplication audit.

## Re-score (conservative, kiosk-scoped)
Kiosk button consistency ▲ (5→1 canonical on kiosk); kiosk a11y/contrast ▲ (dark primary fixed
2.2→7.57:1; Arabic font correct). Design System Coherence **81 → 83%**; Overall Design Readiness
**81 → 82%**. (P3A still PARTIAL overall — shop/QR/pos remain.)

## Verdict
**DESIGN-P3A.2 (Kiosk) COMPLETE. rc1/rc2/rc3 unmoved. No rc4** (waits for full P3 closure).
Next: DESIGN-P3A.3 — Shop + QR canonical button migration.
