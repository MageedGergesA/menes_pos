# P3-BUTTON-PAGE-MATRIX — per-surface button status (DESIGN-P3A / P3A.1)

Every production button surface, its button styling **before** P3A, what changed, and the
**observed** verification state. "Observed" = opened in a real browser this track (not curl).
Honest scope: **P3A is PARTIAL** — canonical source is established and several surfaces are
migrated + verified; the rest are documented, not yet migrated.

| # | Surface | URL / mount | Buttons (before) | P3A/P3A.1 change | Canonical now? | Observed (browser) |
|---|---|---|---|---|---|---|
| 1 | **Owl cashier** | `/mezze/pos` (assets_cashier) | `.mz-btn` + `--primary/ghost/confirm/danger/charge/sm` **in cashier.css** (radius 14 local) | radius `14→var(--mz-radius-md)` (11); base/variants already `--mz-` token-driven | **yes** (name+tokens; radius now unified) | **LIVE-VERIFIED** (auth, pre-warmed bundle): Charge=`mz-btn--charge` #C0602E Hanken 50px |
| 2 | **Checkout** | `/checkout/s/<token>` | foundation + brand (P2) | — (no button change this pass) | n/a | LIVE (P2): foundation + terracotta, console 0 |
| 3 | **Onboarding** | `static/onboarding.html` | `.btn`/`.btn.primary` (gradient), local `--acc` | **fully migrated** → `.mz-btn --primary/--secondary`, `.mz-icon-btn`; legacy `.btn` CSS removed; `--mz-` brand tokens mapped onto `--acc` | **yes** | **LIVE-VERIFIED**: `#refresh`=`mz-btn--primary` #D89A54 radius11 minH44 Hanken700 no-gradient; icon-btn 44×44; console 0 |
| 4 | **POS prototype** | `static/pos.html` | `.button--*` (prototype) **+** admin `.mz-btn`/`.mz-btn small`/`.danger` (from mezze-design.js) | admin `.mz-btn` **dup CSS removed**; 5 consumers → `mz-btn--sm`/`mz-btn--danger`. `.button--*` prototype UNCHANGED | admin `.mz-btn`: **yes**; `.button--*`: **no (prototype)** | **LIVE-VERIFIED**: renders (bodyLen 318k), `mz-btn--danger` = themed filled salmon-red #E58A82 + dark text #1C1305 (AA), radius11 44px Hanken; `mz-btn--sm` 36px; console 0 |
| 5 | **Shop** | `static/shop.html` | `.btn` (gradient) + `.promobtn` | customer `.btn` gradient→flat `--mz-brand` via `mezze-customer.css` (attr override, v=d5). `.promobtn` NOT migrated | primary `.btn`: **yes**; `.promobtn`: **no** | LIVE (P3A): `.btn` flat #D89A54 radius11 no-gradient Hanken |
| 6 | **QR order** | `static/qr.html` | `.btn` + `.place/.cartbtn/.again` | customer `.btn` flat via bridge; ad-hoc classes NOT migrated | primary `.btn`: **yes**; ad-hoc: **no** | Bridge CSS shared w/ shop (observed on shop); qr ad-hoc pending |
| 7 | **Kiosk** | `static/kiosk.html` | `.startbtn/.review/.place/.ghost/.addbtn/.lang` (6) + governed large-touch | **MIGRATED (P3A.2)** — all 6 → `.mz-btn --primary/--secondary` + layout-only `.kiosk-*`; `--mz-` token bridge (on-brand ink fixed); legacy button CSS stripped; `.svcbtn`/`.cat` (segmented) + `.qbtn` (quantity→P3E) + `.n` (badge) excluded | **yes** | **PASS** — LIVE EN/AR × light/dark; Hanken(LTR)/IBM Plex Sans Arabic(RTL) 700, radius 11, brand #C0602E/#D89A54, touch 46–88px; contrast dark-primary 7.57 / light-primary 4.24(AA-lg) / secondary 14.85–16.68; keyboard Enter-activates + focus-visible; real order #1 draft/KDS DB-verified; console 0 |
| 8 | **CFD** | `static/cfd.html` | `.btn` | customer `.btn` flat via bridge | primary `.btn`: **yes** | bridge shared (observed on shop) |
| 9 | **Feedback** | `static/feedback.html` | `.btn` | customer `.btn` flat via bridge | primary `.btn`: **yes** | bridge shared (observed on shop) |
| 10 | **Courses** | `static/courses.html` | `.btn` | customer `.btn` flat via bridge | primary `.btn`: **yes** | bridge shared (observed on shop) |
| 11 | **Drive-thru** | `static/drivethru.html` | `.btn` | customer `.btn` flat via bridge | primary `.btn`: **yes** | bridge shared (observed on shop) |

## Scorecard against the P3A targets
- **Button styling systems: 5 → 2** (after P3A.2, canonical `.mz-btn` is the single styled source
  for cashier/onboarding/admin-pos/**kiosk** + the customer `.btn` bridge; **remaining second
  system = per-page ad-hoc** `.button--*` (pos prototype) / `.promobtn` (shop) / `.place/.cartbtn/
  .again` (qr)). Target `→1`; **not met yet** — shop/QR/pos remain (P3A.3+). Honest.
- **Unexplained duplicate Button vocabularies: 0** — the one genuine duplicate (`mezze-design.js`
  `.mz-btn`) is **removed**. Remaining non-canonical classes are *documented prototype/ad-hoc*,
  not unexplained duplicates.
- **Canonical source count = 1** (`static/design/components.css`) — **met**.
- **Semantic specialization preserved**: charge/confirm/danger/success kept as variants (payment
  + destructive warrant a distinct loud treatment per Restaurant UX Patterns); sizes compact/sm/
  touch kept for density/large-touch. No gratuitous variants added.

## Remaining to reach P3A COMPLETE (next micro-passes)
1. ~~kiosk~~ — **DONE (P3A.2)**: 6 buttons canonical, `--mz-` bridge, legacy CSS stripped, live
   EN/AR × light/dark + order DB-verified. Quantity `.qbtn` deferred → P3E.
2. **DESIGN-P3A.3 — shop `.promobtn`, qr `.place/.cartbtn/.again`** — strip legacy visual props
   (keep layout), add canonical class, verify light/dark/AR.
3. **pos.html `.button--*`** — prototype; migrate last (lowest stakes) or leave documented.
4. Full **dead legacy-CSS removal** on each migrated surface + final duplication audit → then
   mark **P3A COMPLETE** and proceed to **DESIGN-P3B (Status/Badge)**. **rc4 only after ALL P3
   families.**
