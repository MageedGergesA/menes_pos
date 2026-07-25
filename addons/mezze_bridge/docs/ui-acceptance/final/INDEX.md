# Mezze POS — Final UI Acceptance (D2)

Real screenshots of the running application (live Odoo 19 + PostgreSQL, DB `mezze_test`),
captured via Chrome automation by navigating the app's own rail (not force-injected DOM).

| Field | Value |
|---|---|
| Date | 2026-07-24 |
| Commit | `ce8dc74` (+ D2 working changes) |
| Addon version | 19.0.1.4.0 |
| Rendered viewport | ~1568×778 CSS px (desktop terminal). See "Tablet note" below. |
| Default theme | Mezze Classic (light) · Terracotta accent |
| Density | standard (compact/comfortable also evidenced) |
| Scale | 100% (80% and 140% also evidenced) |
| Reduced motion | on during capture (avoids the app's ambient-animation CDP-freeze) |

## Staff workspaces
| Workspace | File | Notes |
|---|---|---|
| Cashier | staff-cashier-light-classic-1366.jpg | product grid, order panel, AI upsell, verbs |
| Cashier (dark) | staff-cashier-dark-lounge-1366.jpg | every surface dark |
| Cashier (RTL) | staff-cashier-arabic-rtl.jpg | full shell mirror |
| Cashier (compact) | staff-cashier-compact-density.jpg | density tightens grid/rows |
| Cashier (HC light/dark) | staff-cashier-highcontrast-light/-dark.jpg | high-contrast both modes |
| Cashier (80%/140%) | staff-cashier-scale-80/-140.jpg | UI scale extremes |
| Payment | *(overlay; see report §4 — opened from Cashier, not separately framed)* | |
| Floor Plan | staff-floor-plan.jpg | real table shapes, seats, occupancy stats, labeled legend |
| KDS | staff-kds-empty-BEFORE.jpg / -AFTER-fixed.jpg | empty-state fix (D2) |
| Coffee Queue | staff-coffee-queue-empty.jpg | Barista Queue + Pickup lanes |
| Live Operations | staff-live-ops.jpg | live KPIs, hourly chart, food-cost variance |
| Reservations | staff-reservations-empty.jpg | tabs, + New reservation, empty state |
| Delivery | staff-delivery-empty.jpg | dispatch board / apps tabs |
| Manager | staff-manager-shift-command.jpg | shift command, sub-tabs |
| Reports | staff-reports-light.jpg / -dark-lounge.jpg / -arabic-rtl.jpg | KPIs, CSV export, tabs |
| HQ | staff-hq-branches.jpg | org totals + branch comparison |
| Central Kitchen | staff-central-kitchen.jpg | prep stock, request form, per-branch |
| User Settings | staff-user-settings-13categories.jpg | 13 categories + provenance |
| Admin Console | staff-admin-console-templates.jpg | templates, authenticated |

## Customer-facing surfaces
| Surface | File | Notes |
|---|---|---|
| Online shop | cust-online-shop-mezze-classic.jpg | terracotta hero, tokens adopted |
| CFD | cust-cfd-display-mezze-classic.jpg | order summary, tokens adopted |
| QR ordering | cust-qr-invalid-error-state.jpg | invalid-QR customer error state |
| Drive-thru | cust-drivethru-header.jpg | header adopts tokens (board empty offline) |
| Feedback | cust-feedback-form.jpg | star rating + form, tokens adopted |
| Courses | cust-courses-error-state.jpg | "Could not connect" error state |

## Known accepted differences
- **Tablet note:** `resize_window` does not change the rendered CSS viewport on this
  hi-DPI capture host (frames stay ~1568px). The responsive layer (`@media (max-width:1040px)`
  and logical/RTL properties) is present in source and exercised at the widths the tooling
  allowed; a dedicated narrow-tablet (≤1024px) frame is NOT included. Not claimed as rendered.
- **Empty-state enrichment:** KDS is the fully-enriched exemplar (icon + title + guidance).
  Reservations/Delivery/Coffee-Queue/CK empty messages are centered via the shared
  `.empty-state` fix but remain single-line text (icons not added per-string this pass).
- **Drive-thru offline board** shows no explicit empty/offline message when loaded without a
  station config (header still themed). Minor; secondary surface.
- Sparse demo data (few live orders/tickets) means several operational lists show their
  empty states rather than dense content; those are valid state captures.
