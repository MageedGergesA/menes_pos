# D3 — Forty-File Source Coverage Matrix

All 40 files in `/home/mageed/Downloads/Mezze POS Visual Redesign/export` were read
(full unescaped char counts recorded during inventory). Status legend: **P**=Implemented & proven,
**U**=Implemented but unproven, **PT**=Partial, **IU**=Intentionally unsupported, **S**=Superseded, **M**=Missing.

| # | File | Category | Authority | Production mapping | Status |
|---|---|---|---|---|---|
| 1 | Mezze Design System | Foundation | authoritative | mezze-design.css tokens (12 themes/5 accents) | P |
| 2 | Mezze Typography System | Foundation | authoritative | Hanken Grotesk + IBM Plex Arabic @font-face; type scale | P |
| 3 | Mezze Spacing System | Foundation | authoritative | `--mz-space-*` + density factor | P |
| 4 | Mezze Motion System | Foundation | advisory | duration/easing tokens + reduced-motion | P |
| 5 | Foundation Engine | Foundation | advisory | token hierarchy primitive→semantic→component→workspace | P |
| 6 | Primitive Library | Foundation | advisory | primitive `--mz-*` tokens | P |
| 7 | Compound Library | Foundation | advisory | shared compound components (cards/rows/badges) | U |
| 8 | Mezze Component Language | Foundation | advisory | component naming/semantics | U |
| 9 | Mezze Component Library | Foundation | advisory | pos.html + engine components | U |
| 10 | Workspace Library | Foundation | advisory | 11 staff workspaces (pos.html) | P |
| 11 | Application Shell | Platform | authoritative | shared rail+topbar shell; bootstrap `/settings/effective` | P |
| 12 | Cashier Order Screen | Cashier | authoritative | pos.html POS view | P |
| 13 | Cashier Workspace Pro | Cashier | authoritative | pos.html POS view | P |
| 14 | Cashier Workspace Specification | Cashier | advisory | pos.html | U |
| 15 | Cashier Freeze Pack | Cashier | **freeze** | certified amber build preserved; mezze layered | P |
| 16 | Kitchen Workspace Specification | Kitchen | advisory | KDS view + outbox | U |
| 17 | Kitchen Freeze Pack | Kitchen | **freeze** | KDS delivery unchanged (reused) | P |
| 18 | Payment Workspace Specification | Payment | advisory | Payment flow (existing engine) | U |
| 19 | Payment Engine Specification | Payment | authoritative | existing payment engine (NOT redesigned) | P |
| 20 | Admin Console | Admin | authoritative | `#view-admin` (templates/assignments/locks/permissions/audit) | P |
| 21 | Settings | User Settings | **authoritative** | 101-catalog + `#view-settings` (13 sections) | P |
| 22 | Restaurant Configuration Specification | Config | authoritative | cascade + templates + governance | P |
| 23 | Restaurant Configuration Freeze Pack | Config | **freeze** | cascade invariants preserved | P |
| 24 | Permission Service Specification | Platform | authoritative | authz roles + `ui_*`/`settings.*` caps | P |
| 25 | Mezze Enterprise Product Specification | Enterprise | advisory | overall product | U |
| 26 | Mezze POS Implementation Playbook | Enterprise | advisory | — | U |
| 27 | Mezze Platform SDK | Platform | advisory | — | IU |
| 28 | Mezze Restaurant UX Patterns | UX | advisory | patterns applied across workspaces | U |
| 29 | Multi-Tenant SaaS Platform Specification | Platform | advisory | company/branch scope in cascade | PT |
| 30 | Multi-Tenant SaaS Freeze Pack | Platform | **freeze** | scope isolation invariants | PT |
| 31 | Order Engine Specification | Engine | authoritative | pos.order.sync_from_ui (reused) | P |
| 32 | Discount Engine Specification | Engine | authoritative | existing discount path (display prefs never grant) | P |
| 33 | Tax Engine Specification | Engine | authoritative | existing tax (or_tax_break is DISPLAY-only) | P |
| 34 | Search Service Specification | Service | authoritative | server search; se_* settings DISABLED honestly | PT |
| 35 | Search Service Freeze Pack | Service | **freeze** | search contract preserved | PT |
| 36 | Offline Engine Specification | Service | authoritative | offline journal + localStorage cache (reused) | P |
| 37 | Synchronization Engine Specification | Service | authoritative | sync/outbox + idempotency (reused) | P |
| 38 | Printing Service Specification | Service | authoritative | hardware print (reused); or_print DISABLED | P |
| 39 | Notification Service Specification | Service | authoritative | bus + audit; notification prefs DISABLED | PT |
| 40 | AI Service Specification | Service | advisory | AI upsell row (real endpoint) | PT |

**Coverage:** 40/40 read. Freeze packs (15,17,23,30,35) honoured (invariants preserved, not redesigned).
Conflicts resolved per the precedence rule (freeze > spec; production decision > prototype; security/financial > visual).
