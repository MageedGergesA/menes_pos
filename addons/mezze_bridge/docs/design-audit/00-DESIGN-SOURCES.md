# 00 — Design Sources Inventory

Audit-only. No production code changed. Release under audit: `mezze-v1.0-rc1`
(`ad32f3e`). Evidence gathered by source reading + browser `read_page` on the
running app (screenshots blocked intermittently by tooling — see PART 7 note in the
main report).

## Authoritative source

| Source | Classification | Notes |
|---|---|---|
| `docs/DESIGN_SYSTEM.md` | **AUTHORITATIVE** | 148 lines; tokens *measured from the running `pos.html`* + normalized "premium" component specs. Covers brand/voice, color (light+dark), typography (10-step scale), spacing (**4px base**), radius (8/12/18/24/pill), elevation, motion, z-index, components, and an explicit accessibility contract (44px touch, focus ring, RTL logical props, status-never-color-alone, documented `--ink-3` 3.76:1 caveat). This is the single token source of truth. |
| `static/pos.html` | **AUTHORITATIVE (current implementation)** | The design-reference implementation of the DS. 340 CSS custom properties; radius + font-size fully tokenized; a11y instrumented (73 `aria-label`, 3 `role=dialog`, 2 `aria-live`, 3 `prefers-reduced-motion`). Browser title self-identifies as **"Enterprise POS (Design Prototype)"** with demo data — it is the design canon, not the production data path. |

## Current production implementations

| Source | Classification | Notes |
|---|---|---|
| `/mezze/pos` (Owl app `static/src/cashier/**`) | **CURRENT IMPLEMENTATION** | The actual production cashier (auth=user). Component-based (cart/payment_screen/product_grid/manual_tender/…). Ships its own `cashier.css`; does **not** import the full `pos.html` token set. |
| `static/shop.html` | **CURRENT IMPLEMENTATION / CONFLICTING** | Customer off-premise storefront. Own 19-var palette, 45 hardcoded font-sizes, 20 hardcoded radii. Does not use DS token names. |
| `static/qr.html` | **CURRENT IMPLEMENTATION / CONFLICTING** | Table-QR ordering. Own vocab (`--saffron/--ink/--bg`, `--r:16px`). |
| `static/kiosk.html` | **CURRENT IMPLEMENTATION / CONFLICTING** | Kiosk. Own vocab (`--acc/--card/--txt`, `--r:22px`). Not on the theme registry. |
| `static/onboarding.html` | **CURRENT IMPLEMENTATION / CONFLICTING** | S5 admin/Go-Live console (added late). Copies kiosk's vocab, `--r:16px`. **Zero** focus/ARIA/reduced-motion. |
| `static/{courses,drivethru,cfd,feedback}.html` | **CURRENT IMPLEMENTATION** | Secondary staff/customer surfaces; small own palettes, hardcoded scales. |

## Historical / reference

| Source | Classification | Notes |
|---|---|---|
| `/home/mageed/Downloads/Mezze POS Visual Redesign/export/*.html` (~40 files: Mezze Design System, Spacing System, Typography System, Motion System, Component Library, Restaurant UX Patterns, Cashier/Kitchen/Payment/Admin specs, Freeze Packs) | **HISTORICAL / REFERENCE ONLY** | The earlier authoritative visual source. Superseded by `docs/DESIGN_SYSTEM.md` for tokens (the DS was measured from the shipped app). Use the export for *pattern intent*, not current values. **Where the export says "8px grid" it CONFLICTS with the current 4px-base DS** — see `01-DESIGN-CONFLICTS.md`. |
| `docs/DESIGN_COMPLIANCE_REPORT.md`, `docs/FINAL_DESIGN_SIGNOFF.md`, `docs/design-governance-acceptance/` | **REFERENCE** | Prior compliance/signoff records for the `pos.html` polish work. |

## Headline conclusion

There is a genuinely strong, coherent design system — **but it is implemented in
essentially one surface (`pos.html`)**. The production cashier Owl app, the three
customer surfaces, the kiosk, the admin console, and the four secondary screens each
carry **independent token vocabularies**. Mezze today is *one excellent design
system + eight design-debt islands*, not one uniformly-applied system. This is the
central theme of the whole audit.
