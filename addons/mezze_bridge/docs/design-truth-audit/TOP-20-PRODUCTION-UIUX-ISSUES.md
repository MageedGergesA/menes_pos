# TOP 20 PRODUCTION UI/UX ISSUES (real production only)

Severity P0 (blocks/error-risk) · P1 (major usability/sales/adoption) · P2 (inconsistency/polish) · P3 (cosmetic). Frequency H/M/L. Ranked by business impact (P1·HIGH first). AUDIT ONLY — no fix here.

| # | Screen | Issue | Export principle violated | Current impl | Impact | Sev·Freq | Direction |
|---|---|---|---|---|---|---|---|
| 1 | Cashier | Qty stepper 36px + category tabs ~38px < 44px | "44px min every surface" | `cashier.css:117,73` | mis-taps at rush on the busiest controls | **P1·H** | size to 44px + 8px gap |
| 2 | Staff product | No production nav shell; cashier & KDS are isolated islands | 6 workspaces + shell + role rail | 2 unlinked Owl apps | staff cannot move between surfaces; feels like separate apps | **P1·H** | production nav shell + role gating |
| 3 | Cashier | Amounts/totals not tabular-mono | "restaurant software is numeric software; tabular so total never shifts layout" | text font, no `--mz-font-num` | totals jump; slower reconciliation | **P1·H** | adopt `--mz-font-num` for money |
| 4 | Kiosk + Onboarding | Arabic font misspelled `'IBM Plex Arabic'`, unbridged → system fallback | "dedicated Arabic family, first-class" | `kiosk.html:20`, `onboarding.html:20` | broken Arabic on a self-serve + go-live screen | **P1·H** (kiosk) | fix name + load bridge |
| 5 | Cashier | Spacing = 267 raw px, 0 `--mz-space` primitives; local `--radius` | "one 8/4 lattice; off-grid auto-rejected" | `cashier.css` | rhythm drift vs KDS/foundation | P1·M | migrate to `--mz-space/--mz-radius` |
| 6 | Customer (drivethru/feedback/courses) | Legacy gradient `.btn`, not `.mz-btn` (no 44px/state contract) | Button primitive | `drivethru:97,feedback:49,courses:88` | inconsistent buttons; no state/focus contract | P1·M | adopt `.mz-btn` |
| 7 | Kiosk + Onboarding | Off-registry lavender palette; no dark registry; no HC | "authored themes; AA floor; warm-only palette" | own `:root[data-mz-mode]` | off-brand; no HC on a public + admin screen | P1·M | bridge to registry |
| 8 | Component system | Only 2 of ~30 families canonical (Alert/Input/Quantity/Dialog/Card/Tabs bespoke) | 5-tier component system | components.css | duplicated bespoke CSS; drift risk | P1·M | canonicalize P3C–P3I |
| 9 | Cashier | No favorites/recent/predictive defaults | "cashiers hit the same 5–8 categories all shift" | absent | slower rush throughput | P1·M | favorites + predictive tender |
| 10 | Cashier | No undo-toast reversible-for-seconds | "speed without fear; every rushed action reversible" | absent | error anxiety; slower staff | P1·M | undo toast on destructive/quick actions |
| 11 | Customer (drivethru/onboarding) | Color-only status dots/badges | "state never carried by color alone" | `drivethru:58-62`, `onboarding:37` | fails glare/low-vision/grayscale | P1·M | add text/icon second signal |
| 12 | Cashier | Duplicate `.mz-btn` base block | single canonical button source | `cashier.css:131` | divergence risk from canon | P2·M | remove; rely on components.css |
| 13 | Product-wide | No `prefers-contrast` / `forced-colors` support | "HC parity" | absent | OS-HC users unserved | P2·M | map to app HC theme |
| 14 | Cashier | Bespoke `.mz-input`/`.mz-tender-input` (P3D not started) | Input primitive | `cashier.css:154,209` | inconsistent inputs/focus | P2·M | canonical input |
| 15 | Icons | Inline SVG everywhere vs Material Symbols Rounded | export icon system | all Owl+customer | library drift (labeled, low risk) | P2·L | optional unify |
| 16 | Customer surfaces | Zero executed browser evidence (shop/qr/kiosk/checkout/etc.) | AA "measured live" gate | no tests | design claims unverified at runtime | P2·M | add authenticated/rendered browser tests |
| 17 | 4 staff workspaces | Floor/Reservations/Delivery/Reporting unbuilt as production | designed workspaces | proto+JSON only | product ships 2 of 6 designed staff screens | P2·M (product scope) | build as Owl (roadmap) |
| 18 | Cashier | No keyboard parity (⌘↵/⌘Z/"/" ) | "safe shortcuts mirror every touch action" | absent | expert-cashier speed | P2·M | keyboard map |
| 19 | Density | `--mz-density` token unused by any per-context selector | 3 density modes | token only | no compact drive-thru / comfortable training mode | P3·L | wire density selection |
| 20 | Cashier | Category tabs not canonical Tabs/Segmented (P3I) | Segmented Control | `.mz-catbar` bespoke | polish/consistency | P3·L | canonical tabs |
