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
| 4 | **POS prototype** (DESIGN PROTOTYPE / NON-TRANSACTIONAL) | `static/pos.html` | `.button`/`.button--primary/secondary/strong/positive/sm/block` (27 sites) + `.iconbtn` (2) | **MIGRATED (P3A.4)** — `.button--*` → `.mz-btn --primary/--secondary/--success` + `.mz-btn--sm` + layout-only `.pos-flex`/`.pos-block`; `.iconbtn` → `.mz-icon-btn`; all legacy `.button`/`.iconbtn` CSS removed | **yes** | **PASS — prototype**: renders (bodyLen 318k), primary=darkened terracotta+ink, success=green #5FB884+dark-ink, secondary, icon 44×44; Hanken 700, radius 11; console 0. **Production cashier remains `/mezze/pos` (Owl), NOT this prototype.** |
| 5 | **Shop** | `static/shop.html` | `.langbtn/.btn(+.dark/.off)/.promobtn/.cartbar-button` | **MIGRATED (P3A.3)** — 9 sites → `.mz-btn --primary/--secondary` + layout-only `.shop-*`; legacy button CSS stripped; hierarchy restored (was collapsed); `.chip/.seg/.opt/.sx/.step/.add`-glyph excluded | **yes** | **PASS** — LIVE EN/AR × light/dark; Hanken/IBM-Plex-Arabic 700, r11, #C0602E/#D89A54, primary/secondary distinct; contrast 4.24(AA-lg)/7.57/15.31; keyboard Enter+focus-visible; order #3 draft, triple-click→1 (no dup); console 0 |
| 6 | **QR order** | `static/qr.html` | `.langbtn/.add/.cartbtn/.place/.again` | **MIGRATED (P3A.3)** — 9 sites → `.mz-btn --primary/--secondary` + layout-only `.qr-*`; add 40→44, place contrast 3.1→4.24 fixed, cartbtn weight 400→700; `.cat/.qus/.tipchip/.modopt/.x/.stepper` excluded | **yes** | **PASS** — LIVE EN/AR × light/dark; canonical fonts r11 44px; order #2 draft + KDS ticket=1 (no dup); tampered-token REJECT (security intact); console 0 |
| 7 | **Kiosk** | `static/kiosk.html` | `.startbtn/.review/.place/.ghost/.addbtn/.lang` (6) + governed large-touch | **MIGRATED (P3A.2)** — all 6 → `.mz-btn --primary/--secondary` + layout-only `.kiosk-*`; `--mz-` token bridge (on-brand ink fixed); legacy button CSS stripped; `.svcbtn`/`.cat` (segmented) + `.qbtn` (quantity→P3E) + `.n` (badge) excluded | **yes** | **PASS** — LIVE EN/AR × light/dark; Hanken(LTR)/IBM Plex Sans Arabic(RTL) 700, radius 11, brand #C0602E/#D89A54, touch 46–88px; contrast dark-primary 7.57 / light-primary 4.24(AA-lg) / secondary 14.85–16.68; keyboard Enter-activates + focus-visible; real order #1 draft/KDS DB-verified; console 0 |
| 8 | **CFD** | `static/cfd.html` | `.btn` | customer `.btn` flat via bridge | primary `.btn`: **yes** | bridge shared (observed on shop) |
| 9 | **Feedback** | `static/feedback.html` | `.btn` | customer `.btn` flat via bridge | primary `.btn`: **yes** | bridge shared (observed on shop) |
| 10 | **Courses** | `static/courses.html` | `.btn` | customer `.btn` flat via bridge | primary `.btn`: **yes** | bridge shared (observed on shop) |
| 11 | **Drive-thru** | `static/drivethru.html` | `.btn` | customer `.btn` flat via bridge | primary `.btn`: **yes** | bridge shared (observed on shop) |

## Scorecard against the P3A targets — FINAL (P3A.4)
- **Button styling systems: 5 → 1** ✅ — canonical `.mz-btn` vocabulary in `components.css` is the
  single styled source across cashier + kiosk + shop + qr + onboarding + pos-prototype. `cashier.css`
  = documented cashier-density context layer of the *same* `.mz-btn` vocabulary (canonical radius/
  focus/states/tokens; only font-size/padding density + full-width charge differ). The customer
  `.btn` bridge (cfd/feedback/courses/drivethru) is a legacy compatibility layer for un-migrated
  customer-shell pages — flat brand fill only, scheduled for a later shell pass; not a Button
  *vocabulary*. **Unexplained legacy Button visual systems = 0.**
- **Contrast gate (P3A.4):** primary darkened one terracotta step (ACCESSIBILITY ADAPTATION) →
  light 5.10:1 / dark 6.07:1 (was 4.24 fail at the 15px-normal label); secondary 15.31/13.52;
  danger 5.66/7.24; success 5.06/7.58 (dark-ink text fix); focus 4.18 (≥3.0). All AA.
- **11/11 production pages browser-observed** (this pass or prior track); Unobserved = 0.
- **Unexplained duplicate Button vocabularies: 0** — the one genuine duplicate (`mezze-design.js`
  `.mz-btn`) is **removed**. Remaining non-canonical classes are *documented prototype/ad-hoc*,
  not unexplained duplicates.
- **Canonical source count = 1** (`static/design/components.css`) — **met**.
- **Semantic specialization preserved**: charge/confirm/danger/success kept as variants (payment
  + destructive warrant a distinct loud treatment per Restaurant UX Patterns); sizes compact/sm/
  touch kept for density/large-touch. No gratuitous variants added.

## Remaining to reach P3A COMPLETE (next micro-passes)
1. ~~kiosk~~ — **DONE (P3A.2)**: 6 buttons canonical + order DB-verified. Quantity `.qbtn` → P3E.
2. ~~shop + QR~~ — **DONE (P3A.3)**: 18 sites canonical, legacy CSS stripped, live EN/AR × light/
   dark + orders DB-verified + QR tamper-guard intact. Quantity `.step`/`.stepper` → P3E.
3. **DESIGN-P3A.4 — pos.html `.button--*`** — prototype; migrate OR formal documented exception.
4. Final product-wide Button duplication audit → then **P3A COMPLETE** → **DESIGN-P3B (Status/
   Badge)**. **rc4 only after ALL P3 families.**
