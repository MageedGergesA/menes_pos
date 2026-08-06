# MEZZE DESIGN STATE — single source of truth (design truth audit)

**AUDIT ONLY. No production code changed. Nothing committed/pushed. No RC/tag moved.**

## 1. Audit date
2026-08-06.

## 2. Git identity
HEAD = origin/main = **`96a72e11dfaa0e3671529f549d3f71e8579cfca8`**; branch `main`; tree CLEAN; divergence 0/0. Module version **19.0.2.0.0**; product version **1.0.0-rc.1**. Latest product RC `mezze-v1.0-rc3` → commit `fb59c79` (unmoved). Design tag `sprint-1-design-foundation` present.

## 3. Original export identity
`/home/mageed/Downloads/Mezze POS Visual Redesign/export` — Figma-Make bundles; Saudi/Gulf Arabic-first (SAR, Levantine menu); benchmarked vs Foodics/Toast/Lightspeed/Square/Dynamics; declared **frozen v1.0**; framework-free production layer; Odoo-mapped throughout. **PRIMARY design authority.**

## 4. Exact export file count
**40 files.**

## 5. Interpretation
**FULLY 14 · PARTIALLY 26 · NOT 0.** JS-rendered/embedded content WAS extracted (`<x-dc>` prose + `<script>` literals + CSS-var tokens); no file was stub-only. Design authority = files 1–10,14–21; 22–40 are service/platform engineering references.

## 6. Design authority hierarchy
Export principles/tokens > operator-approved corrections (Owl impl layer; 12-theme/5-accent registry) > canonical shared tokens/components > production impl > prototype (`/mezze/design/pos`, reference-only) > stale derived docs. See DESIGN-AUTHORITY-AND-PRECEDENCE.md.

## 7. Original design principles
Typography disappears (legibility not beauty; tabular numerics; Arabic first-class, zero tracking, leading 1.7). Whitespace is information (8/4 lattice; distance encodes relationship). Structure first, color last (97% neutral / 3% terracotta accent = "act here"; status ≠ brand; dark authored not inverted). Motion communicates never decorates (80–200ms operational; spring = payment-complete only; reduced-motion honored). Density = one multiplier. Touch 44px + 8px gap, thumb-arc. Every state = color + a 2nd signal. Full detail: ORIGINAL-DESIGN-SYSTEM-MAP.md.

## 8. Original tokens
Full light+dark ramp, fonts, semantics, motion, density, touch: ORIGINAL-TOKEN-REFERENCE.md. Brand #C0602E/#D89A54; warn #B5842B; ok #2F7D4A; danger #B0433A; info #2C6E8F; vip #B08900. No purple/violet, no `--mz-active/offline/accent` token.

## 9. Current shared foundation
`static/design/foundation.css` = **near-exact reproduction** of the export tokens (fonts, spacing, radius, type, motion, touch all identical). `static/design/components.css` = canonical `.mz-btn`/`.mz-icon-btn` (P3A), `.mz-status`/`.mz-badge` (P3B) ONLY. `static/mezze-design.css` = theme registry (classic/dark/highcontrast + accents). **The foundation layer is the strongest, most-aligned asset. DO NOT re-value.**

## 10. Current component system
**2 canonical families** (Button, Status/Badge) vs the export's ~30 across 5 tiers. Alerts, Inputs, Quantity, Dialogs, Cards/ListRows, Empty/Loading, Tabs/Segmented (P3C–P3I) are **bespoke per-surface, not canonical**. The "component system" is 2 families deep.

## 11. Current production screens
2 hardened Owl (`/mezze/pos`, `/mezze/kds`) + 1 rendered QWeb customer hub (`/checkout/s/<token>`) + 9 static HTML (6 customer, 2 staff boards, 1 admin). Full table: CURRENT-PRODUCTION-SCREEN-INVENTORY.md.

## 12. Prototype / reference
`static/pos.html` (`/mezze/design/pos`) — 1 file, 11 internal `data-view` mockups. Reference-only; EXCLUDED from production scoring. It, not production, holds the real 11-destination nav + role model.

## 13. Screen compliance matrix
KDS ~90% · Cashier ~68% · shop/qr ~60% · cfd/feedback/drivethru/courses ~52% · kiosk/onboarding ~35% · checkout hub NOT-OBSERVED. Detail: SCREEN-BY-SCREEN-COMPLIANCE.md.

## 14. Typography
Fonts confirmed + adopted in cashier/kds/6-customer; **numeric font only in KDS** (cashier money not tabular-mono); **kiosk+onboarding misspell `'IBM Plex Arabic'`** → Arabic broken. Adoption ≈ 70%.

## 15. Color
Token-based; KDS 0 raw hex; cashier UI token-based (raw hex = legit palette-def + QR plate); customer bridged (terracotta at runtime) with legacy amber-ish fallback + a few color-only dots. `#E0982B` amber = 0× in production (compliance-report claim is STALE). Adoption ≈ 75%.

## 16. Spacing
KDS on the 4/8 lattice (32 primitives); **cashier 0 primitives / 267 raw px + local `--radius`**; customer page-local. Adoption ≈ 45%.

## 17. Components
See §10. Button P3A PARTIAL, Status/Badge P3B PARTIAL, P3C–P3I NOT STARTED. Adoption ≈ 35%.

## 18. Restaurant UX
KDS honors aging/timer/position/allergen/86/cancel; cashier honors payment-mirror/idempotency/mixed-tender. MISSING in production: favorites/predictive defaults, undo-toast, keyboard parity, and 4 of 6 designed staff workspaces. Alignment ≈ 55%.

## 19. Arabic / RTL
Strong on cashier/kds/6-customer (logical props, RTL font, computed dir, LTR numerics); **broken font on kiosk+onboarding**. Readiness ≈ 75%.

## 20. Themes
Real registry (dark + Mezze HC) on 8 surfaces; **kiosk+onboarding off-registry (self-lavender, no HC)**; `prefers-contrast`/`forced-colors` unsupported product-wide. ≈ 70%.

## 21. Accessibility
Owl status = text + `data-state` + aria (2-signal law met); focus/reduced-motion honored in cashier/kds; no systematic a11y certification; customer color-only dots + kiosk/onboarding gaps. ≈ 55%.

## 22. P3 family status (from code)
P3A Buttons **PARTIAL** · P3B Status **PARTIAL** · P3C Alerts **NOT STARTED** · P3D Inputs **NOT STARTED** · P3E Quantity **NOT STARTED** · P3F Dialogs **NOT STARTED** · P3G Cards/ListRows **NOT STARTED** · P3H Empty/Loading **NOT STARTED** · P3I Tabs/Segmented **NOT STARTED**.

## 23. Prototype-vs-production debt
**HIGH** — production shipped 2 of 6 designed staff workspaces; no production nav shell; deeper component tiers unbuilt. PROTOTYPE-VS-PRODUCTION-DESIGN-DEBT.md.

## 24. Design system coherence score
**≈ 62%** (see §38 of the report). Foundation excellent; components 2-deep; cashier spacing + cross-screen consistency drag.

## 25. UI/UX product readiness score
**≈ 52%** — cashier + KDS strong; 4 staff workspaces + deeper components + customer-consistency incomplete.

## 26. Top 20 gaps
TOP-20-PRODUCTION-UIUX-ISSUES.md (P1·HIGH: cashier 44px touch, no nav shell, cashier non-tabular money, kiosk/onboarding Arabic).

## 27. Do-not-touch
DESIGN-DO-NOT-TOUCH.md — foundation tokens, brand, theme registry, canonical components, the entire KDS surface, cashier payment hierarchy, KDS restaurant semantics.

## 28. Recommended implementation roadmap
- **R1 — Real Cashier UX closure** (44px touch on qty/cat, `--mz-space/--mz-radius/--mz-font-num` adoption, remove dup button base, favorites + undo-toast + keyboard parity). Highest ROI: highest-frequency production screen, all P1·HIGH, zero new surface risk.
- **R2 — Shared operational component tiers** (canonical Alert/Input/Quantity/Dialog/Card/Tabs — P3C–P3I) — shared leverage across every surface.
- **R3 — Production navigation shell + role IA** (connect cashier↔KDS↔future workspaces; the export's real IA).
- **R4 — Customer journey consistency** (bridge kiosk+onboarding to the registry; fix Arabic font; `.mz-btn` on drivethru/feedback/courses; add rendered/authenticated browser tests).
- **R5 — Build the 4 missing staff workspaces** (Floor/Table-Map, Reservations, Delivery, Reporting as Owl) on R2/R3.
- **R6 — Admin/Settings** production surface.
- **R7 — Accessibility / Arabic / theme certification** (forced-colors/prefers-contrast; live AA audit; Arabic browser cert on every surface).
- **R8 — Product-wide motion/icon polish** (Material Symbols unify; motion law audit).

**Chosen next phase: R1 — Real Cashier UX closure. Do NOT start (audit only).**
