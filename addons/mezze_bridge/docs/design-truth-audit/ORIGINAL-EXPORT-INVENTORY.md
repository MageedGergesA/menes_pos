# ORIGINAL EXPORT INVENTORY — 40 files

Source: `/home/mageed/Downloads/Mezze POS Visual Redesign/export`. **Exact count: 40 `.html` bundles.**
These are Figma-Make exports: a JS loader stub + real content in an escaped `<x-dc>` prose block and in `<script>` string literals (unicode/backslash-escaped). Content was recovered (not stub-only) via custom extractors. Product is **Saudi/Gulf, Arabic-first** (SAR currency, Levantine menu), benchmarked vs Foodics/Toast/Lightspeed/Square/Dynamics, declared **frozen v1.0**, Odoo-mapped, framework-free production layer ("No React, No Tailwind").

**Interpretation totals: FULLY = 14 · PARTIALLY = 26 · NOT = 0.** ("Partially" = engineering/service contracts whose scope+structure were recovered but whose interiors are template-bound data with little *design* content — not the design authority.)

| # | File | Class | Topic | Interp | Authority |
|---|------|-------|-------|--------|-----------|
| 1 | Foundation Engine | FOUNDATION | live token engine (theme/density/RTL/motion/flags, one root attr each) | FULLY | AUTHORITY |
| 2 | Mezze Design System | FOUNDATION/PRINCIPLE | surfaces, elevation, tiers, light+dark maps, 10 semantic colors + psychology, WCAG-AA | FULLY | AUTHORITY |
| 3 | Mezze Typography System | PRINCIPLE | 3 faces, 6 laws, modular scale, tabular numerics, Arabic tuning | FULLY | AUTHORITY |
| 4 | Mezze Spacing System | PRINCIPLE | 8px/4px lattice, semantic stacks, 3 densities, touch spacing | FULLY | AUTHORITY |
| 5 | Mezze Motion System | PRINCIPLE | 5 principles, 6 durations, 4 eases, restaurant-speed, reduced-motion | FULLY | AUTHORITY |
| 6 | Mezze Component Language | PRINCIPLE/GOV | 10 laws, 5 tiers, 30-section doc contract, 16-state model, a11y matrix | FULLY | AUTHORITY |
| 7 | Primitive Library | PRIMITIVE | 15 vanilla-JS primitives (createX) | FULLY | REFERENCE |
| 8 | Mezze Component Library | COMPONENT | full 5-tier catalog, live specimens | FULLY | AUTHORITY |
| 9 | Compound Library | COMPOUND | restaurant compounds: composition tree, deps, events, API, aria, perf | FULLY | AUTHORITY |
| 10 | Workspace Library | WORKSPACE | composition-only workspaces, <16ms budget, migration/rollback, journeys | FULLY | AUTHORITY |
| 11 | Application Shell | STAFF SCREEN | enterprise shell+inspector: session/role/branch/terminal/shift, offline queue, plugins | PARTIALLY | SCREEN REF |
| 12 | Cashier Workspace Pro | STAFF SCREEN | hardened cashier: virtualized grid, perf, keyboard map (⌘↵ charge) | PARTIALLY | SCREEN REF |
| 13 | **Cashier Order Screen** | STAFF SCREEN | the **live ship reference** ("the implementation ships in") | PARTIALLY | SCREEN REF (primary) |
| 14 | Mezze Restaurant UX Patterns | RESTAURANT | 7 laws, 10 categories / 50+ workflows, error-recovery, rush budget | FULLY | AUTHORITY |
| 15 | Cashier Workspace Specification | STAFF SCREEN | order-entry + payment-handoff spec | FULLY | SCREEN REF |
| 16 | Kitchen Workspace Specification | STAFF SCREEN | KDS spec: ticket state machine, aging, bump/recall, stations | FULLY | SCREEN REF |
| 17 | Payment Workspace Specification | STAFF SCREEN | settle across 9 tenders, cash/card sub-flows, idempotency | FULLY | SCREEN REF |
| 18 | Cashier Freeze Pack | GOVERNANCE | closes 3 critical cashier blockers (hand-off gate) | PARTIALLY | AUTHORITY (gate) |
| 19 | Kitchen Freeze Pack | GOVERNANCE | closes KDS blockers (14-state machine, recall, routing, multi-screen) | PARTIALLY | AUTHORITY (gate) |
| 20 | Admin Console | ADMIN/GOV | Workspace Governance: Locked/Bounded/Free, scope, templates, overrides | PARTIALLY | SCREEN REF |
| 21 | Settings | ADMIN | personal settings, org-locked read-only, sync, export | PARTIALLY | SCREEN REF |
| 22 | Mezze Enterprise Product Specification | REFERENCE | SSOT: modules/features/roles/hardware/integrations | PARTIALLY | REFERENCE |
| 23 | Mezze POS Implementation Playbook | REFERENCE | 6 phased reversible releases | PARTIALLY | REFERENCE |
| 24 | Mezze Platform SDK | SERVICE-SPEC | plugin/workspace/AI extension points, command/event bus | PARTIALLY | REFERENCE |
| 25 | AI Service Specification | SERVICE-SPEC | advisory-only intelligence (proposes, never decides) | PARTIALLY | REFERENCE |
| 26 | Discount Engine Specification | SERVICE-SPEC | headless discount/promo before Tax | PARTIALLY | REFERENCE |
| 27 | Order Engine Specification | SERVICE-SPEC | shared lifecycle/state/calculations; maps 1:1 to Odoo | PARTIALLY | REFERENCE |
| 28 | Payment Engine Specification | SERVICE-SPEC | headless auth/capture/void/refund/split/idempotency | PARTIALLY | REFERENCE |
| 29 | Tax Engine Specification | SERVICE-SPEC | tax determination → account.tax + fiscal positions | PARTIALLY | REFERENCE |
| 30 | Permission Service Specification | SERVICE-SPEC/GOV | RBAC→ABAC default-deny → res.groups + record rules | PARTIALLY | REFERENCE |
| 31 | Printing Service Specification | SERVICE-SPEC | receipts/kitchen/labels → Odoo IoT | PARTIALLY | REFERENCE |
| 32 | Notification Service Specification | SERVICE-SPEC | notifications/alerts/approvals | PARTIALLY | REFERENCE |
| 33 | Offline Engine Specification | SERVICE-SPEC | local-first, connectivity detect, ordered outbox, replay | PARTIALLY | REFERENCE |
| 34 | Synchronization Engine Specification | SERVICE-SPEC | deterministic reconcile, drains outbox, conflict resolution | PARTIALLY | REFERENCE |
| 35 | Search Service Specification | SERVICE-SPEC | providers, ranking, offline index, EN/AR | PARTIALLY | REFERENCE |
| 36 | Search Service Freeze Pack | GOVERNANCE | closes search blockers | PARTIALLY | REFERENCE |
| 37 | Restaurant Configuration Specification | SERVICE-SPEC/ADMIN | 8-level Global→User inheritance, nothing hardcoded | PARTIALLY | REFERENCE |
| 38 | Restaurant Configuration Freeze Pack | GOVERNANCE | closes config blockers (9-level merge, versioning) | PARTIALLY | REFERENCE |
| 39 | Multi-Tenant SaaS Platform Specification | SERVICE-SPEC | tenancy/isolation/subscriptions/billing/marketplace | PARTIALLY | REFERENCE |
| 40 | Multi-Tenant SaaS Freeze Pack | GOVERNANCE | closes tenancy blockers | PARTIALLY | REFERENCE |

**Design authority = files 1–10, 14–21 (foundation, principles, component libraries, restaurant patterns, workspace specs, the 5 Freeze Packs, Cashier Order Screen ship-reference). Files 22–40 are product/service/platform engineering references (not visual design authority).**
