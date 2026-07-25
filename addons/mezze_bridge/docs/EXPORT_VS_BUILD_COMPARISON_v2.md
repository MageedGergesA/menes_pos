# Export vs. Build — Comparison Report (v2)

*Source: `~/Downloads/Mezze POS Visual Redesign/export/` — 40 packed design/engineering documents (self-unpacking bundles; content extracted from each `data-dc-script`). Compared against the shipped build: the `mezze_bridge` Odoo 19 addon (30 models, 5 controllers, ~7k LOC) + `static/pos.html` (4,962 LOC) + `docs/`. Date: 2026-07-22.*

## 0. The headline

The export is no longer one screen — it is a **complete enterprise-platform blueprint**: a frozen design system, a 5-tier component library, a UX-pattern layer, six workspace specs, **eight headless business-engine contracts**, and a platform/SaaS/services tier (SDK, multi-tenant control plane, Permission/Printing/AI/Search/Notification/Config services), several stamped **OFFICIALLY FROZEN** at 100.

Our build is a **working, Odoo-native vertical slice that actually runs**: live sync/offline, payments (Paymob), e-invoicing (ETA), KDS with realtime bus, hardware printing, and a rich single-file frontend with a full design-token system. It realizes the *product* the specs describe — but as a **monolithic Odoo bridge**, not as the specs' **headless-engines + plugin-SDK + multi-tenant SaaS** architecture.

**One-line verdict:** we have ~**70%** of the *product surface* and ~**35%** of the *platform architecture* the export now prescribes. The gaps are concentrated in the platform tier (SDK, multi-tenant control plane, dedicated Search/Notification/Permission/AI services), not in the day-to-day POS.

Legend: ✅ built & wired · 🟡 partial / by-Odoo-reuse / undocumented · ❌ not built

---

## 1. Design-System Layer

| Export spec | Requires (concrete) | Our build | Status |
|---|---|---|---|
| **Mezze Design System** | primitive→semantic→component tokens; terracotta `#C0602E`; authored dark theme; 5 elevation levels; 10 semantic colors; WCAG AA floor | 99 `--mz-*` tokens, dual light/dark authored, `--mz-elev-1..3`, brand/danger/ok/info/delivery semantic sets w/ soft/hover/press/on- variants; AA-verified | ✅ |
| **Mezze Typography** | 3 typefaces (Hanken/IBM Plex Arabic/JetBrains), 9-step ~1.2 scale on 4px grid, 16 roles, tabular numerics | `--mz-font-ar/num/text` (those 3 fonts self-hosted), leading scale, tabular numerics in totals/KDS | ✅ (roles not formally catalogued) |
| **Mezze Spacing** | 8px grid, 12-step scale, 3 densities (×0.75/1.0/1.25) | spacing/padding tokens + `--mz-density`; Experience-3.0 spacing pass | ✅ |
| **Mezze Motion** | 6 durations (80–1200ms), 4 easings (Carbon curves), reduced-motion, animate transform/opacity only | `--mz-dur-instant..deliberate`, `--mz-ease-standard/spring/decelerate`; reduced-motion honored | ✅ |
| **Component Language** (5 tiers, 30-section contract, 16-state model) | 76 components across T1–T5, each documented, states never color-only | Components exist in `pos.html` (grid, order line, chips, dialogs, KDS ticket…) but **not** a catalogued 5-tier library with the 30-section contract | 🟡 |
| **Component Library** (interactive catalog) | living catalog w/ maturity lifecycle | No standalone catalog; components are inline in the app | 🟡 |
| **Restaurant UX Patterns** (50+ flows, tap budgets, benchmarked vs Foodics/Toast) | Counter sale ≤3 taps/0 dialogs, recovery patterns, 600 orders/hr | Flows are **built and working** (counter/dine-in/split/refund/86/transfer) but not documented as budgeted, benchmarked patterns | 🟡 |
| **Enterprise Product Spec** (24 modules, 17-field contract, 9-role matrix) | whole-platform SSOT | Most modules exist as features; not organized as an EPS with per-feature contracts | 🟡 |
| **Implementation Playbook** (P1–P7 / R1–R7, presentation-only, flag-gated) | phased reskin, reversible, gate-before-promote | **Exactly how we worked** — our `docs/P1..P7` + `EXP3_PHASE1..6` mirror it; appearance flag = the coexistence flag | ✅ |

**Design layer: strong alignment.** Tokens, theme, motion, spacing, typography, and the migration method are essentially as specified. The gap is *formalization* — we have the components and flows but not the catalogued Component Library / UX-Pattern documents.

---

## 2. Workspaces

| Export spec | Requires (concrete) | Our build | Status |
|---|---|---|---|
| **Application Shell** | 4-region shell, workspace router ≤100ms | Experience-3.0 4-region grid (rail/cat/center/ticket); `goView()` router, 11 views | ✅ |
| **Cashier Workspace** (readiness 89; Freeze Pack **100/FROZEN**) | 4 regions, virtualized grid ≤200 DOM @10k SKUs, search ≤80ms, 6 readiness signals, 13-action API, conflict UI, partial-payment handoff | Deep cashier: cats/grid/order/modifiers/combos/half-half/upsell/customer/quick-keys/PIN; wired to live API | ✅ (grid not formally virtualized to 10k; conflict-merge UI is 🟡) |
| **Kitchen (KDS)** (readiness 84; Freeze Pack **100/FROZEN**, 14-state machine) | station lanes, 14-state ticket FSM, recall contract, deterministic routing, multi-screen sync, bump ≤1s | `mezze.kds.ticket` state machine (fired→accepted→preparing→ready→served) + **bus realtime broadcast**, recall, station | ✅ (our FSM has ~5 states vs spec's 14; routing is simpler) |
| **Payment Workspace** (readiness 82) | 9 tenders, split (equal/amount/seat/item), idempotent card flow, reversing-entry refunds | `openPay`, tenders, tips, split-bill, numpad, receipt; **native Paymob** capture + `mezze.reversal` compensation | ✅ (idempotency present-ish; split-by-seat/item 🟡) |
| **Admin Console** (governance: templates, scope locks, audit) | workspace templates, Free/Bounded/Locked settings, 4 admin roles, reversible audit | Manager dashboard + `buildReconcile` + audit log exist, but **no** template/scope-lock governance console | 🟡 |
| **Settings** (14 personal categories, synced across terminals, org-locks read-only) | per-user prefs cascade + org lock display | Theme/density/appearance toggles + localStorage; **no** 14-category synced personal-settings model or org-lock layer | 🟡 |

**Workspace layer: the two flagship workspaces (Cashier, Kitchen) and Payment are genuinely built and live-wired.** The governance surfaces (Admin Console, personal Settings cascade) are the gaps.

---

## 3. Headless Business Engines

*The export's central architectural bet: eight **UI-less** engines that own all logic, consumed via a command bus. Each maps "1:1 to Odoo." Our build largely honors the Odoo mapping but implements the logic **inside controllers/Odoo**, not as separable headless engines.*

| Engine (readiness) | Requires (concrete) | Our build | Status |
|---|---|---|---|
| **Order Engine** (84) | 13-state FSM, 13 commands/8 events, fixed calc order, offline outbox, idempotent dedupe → `pos.order`/`pos.order.line` | Order sync via native `pos.order.sync_from_ui`; **outbox + exactly-once apply**; fire/course tracking. Logic in Odoo, not a discrete FSM engine | 🟡→✅ on behavior, 🟡 on architecture |
| **Payment Engine** (80) | 10-state FSM, provider abstraction, idempotency keys, reversing entries, PCI boundary | Native Paymob (`payment.transaction` + unified checkout + HMAC webhook); `mezze.reversal`; degrades w/o creds | ✅ behavior / 🟡 as engine |
| **Tax Engine** (80) | determination cascade, inclusive/compound, discount-before-tax, freeze/reverse, **bit-for-bit `account.tax`** | Single `/w1/config/tax` endpoint; **relies on Odoo `account.tax`** — which is exactly the spec's mapping target | 🟡 (reuse-aligned; no determination engine) |
| **Discount Engine** (80) | best-price solver, coupons/loyalty/bundles, cost-floor, run-before-tax → pricelist/coupon/loyalty | **Native `loyalty`/promo** via `/promo`,`/loyalty`,`/giftcard` endpoints | 🟡 (reuse-aligned; no best-price solver) |
| **Offline Engine** (80) | 8-state connectivity FSM, durable append-only outbox, 0 lost orders | `mezze.sync.outbox` durable change-journal + frontend queueing | ✅ |
| **Sync Engine** (80) | ordered replay, exactly-once, dead-letter, convergence ≤5s → RPC/ack | **`/mezze/sync/v1` register/push/pull/reconcile all LIVE**; dual-guard exactly-once (`last_acked_seq` + `mezze.sync.applied`); **poison → dead-letter in savepoint, cursor advances** | ✅ **(strongest match in the whole build)** |
| **Search Service** (83) | 13 providers, 6-stage pipeline, ranking weights, EN/AR normalize, ≤80ms@10k, offline index | Frontend substring search over menu; **no** dedicated multi-provider service, ranking contract, or Arabic-normalization pipeline | 🟡/❌ |
| **Notification Service** (80) | 13 categories, 6 priorities, 11 channels, escalation ladder, inbox → `bus.bus`/`mail.*` | `/bus/poll` realtime + KDS bus broadcast; **no** priority/escalation/inbox/dedup service | 🟡 |

**Engines: behavior is largely present, architecture is not.** We implemented the *outcomes* (orders sync, payments capture, tax/discount via Odoo, offline durable, exactly-once sync) but not the *separable headless-engine + command-bus* form. Sync/Offline are the cleanest matches; Search and Notification are the real feature gaps.

---

## 4. Platform & Services Tier

| Spec (readiness) | Requires (concrete) | Our build | Status |
|---|---|---|---|
| **Multi-Tenant SaaS Platform** + **Freeze Pack (100/FROZEN)** | `Tenant→Org→Brand→Restaurant→Branch→Terminal→User`; absolute tenant isolation; 10-state tenant lifecycle; provisioning saga ≤90s; 5 plans; billing; backup RPO≤5m/RTO≤30m | **Multi-branch/multi-company via Odoo companies** + branch-scoped cursors + `/branches`,`/hq/summary`; `mezze.terminal` registry. **No** tenant control plane, provisioning saga, lifecycle, isolation guarantees, or billing | ❌ **(biggest architectural gap — consistent with prior due-diligence: "multi-branch, not multi-tenant")** |
| **Platform SDK** | plugin manifest, 11-state plugin lifecycle, **21 extension points**, command system, 8-layer settings cascade, marketplace | Monolithic single-file `pos.html`; **no** plugin runtime, extension points, or SDK | ❌ |
| **Permission Service** (82) | `User→Role→Permission→Policy→Scope`; 12 roles, 10 scopes, 15 categories; **default-deny**; elevation/approval; → `res.groups`/`ir.rule` | Shared-token auth + cashier PIN + **2 native POS groups + 50 ACL rows**; `/w1/approve` for escalations. **No** policy engine, 10-scope model, or elevation TTLs | 🟡 |
| **Printing Service** (80) | durable priority queue, DLQ, failover, governed reprints, intent-based routing → `iot.device`/ESC/POS | `/mezze/hardware` ESC/POS raw-socket receipt+kitchen+drawer, `mezze.printer` config | ✅ device layer / 🟡 no durable DLQ+failover queue |
| **AI Service** (74 — lowest) | provider-agnostic advisory platform, 12 capabilities, 5 copilots, confidence-gated, never mutates | `/ai/upsell` endpoint only | 🟡 |
| **Restaurant Configuration** + **Freeze Pack (100/FROZEN)** | 8–9 level config cascade, 16 domains, LOCK keys, versioned publish/rollback, templates, 0-code new branch → `pos.config`/`res.company` | Config via `pos.config`/`res.company` + `/config/tax`; **no** dedicated cascade engine, versioning, or templates | 🟡 |
| **Search Freeze Pack (100/FROZEN)** | versioned index, deterministic ranking, offline, atomic swap | (see Search above) | 🟡/❌ |

**Platform tier: the largest divergence.** The export prescribes a horizontal SaaS platform (tenant control plane + plugin SDK + governed services); we built a single-tenant-per-DB Odoo app. Note the export's *own* Odoo mappings (company/`pos.config`/`res.groups`) validate our reuse strategy for the **data model** — but not for the **control-plane and extensibility** layers, which we simply don't have.

---

## 5. Freeze-Pack Readiness vs. our reality

| Frozen spec | Export verdict | Our corresponding build | Reality |
|---|---|---|---|
| Cashier Freeze Pack | **FROZEN · Workspace 100 / Impl 96** | Cashier fully built & wired | Behavior matches; conflict-UI + 10k-virtualization are the honest fast-follows |
| Kitchen Freeze Pack | **FROZEN · Workspace 100 / Impl 95** | KDS built w/ bus realtime | 5-state vs spec 14-state FSM; routing simpler |
| Multi-Tenant SaaS Freeze Pack | **FROZEN · 100 / Impl 92** | Multi-branch only | **Not built as a tenant platform** |
| Restaurant Config Freeze Pack | **FROZEN · 100 / Impl 94** | Odoo-config reuse | No cascade/versioning engine |
| Search Freeze Pack | **FROZEN · 100 / Impl 95** | Frontend search | No service |

The export's "FROZEN/100" scores describe the **spec's completeness**, not shipped code. Where we have shipped (Cashier, Kitchen, Sync, Payments, Hardware), reality tracks the spec well; where we haven't (SaaS control plane, Search/Config services), the frozen spec is a blueprint awaiting build.

---

## 6. What we have that the export doesn't emphasize

- **Real, live Odoo integrations** the specs only *point at*: native Paymob capture + webhook, native ETA e-invoicing (`l10n_eg_edi_eta`), aggregator webhooks with HMAC, GL/session CSV export, waste logging.
- **A working exactly-once sync engine with dead-lettering** — arguably more concretely realized than any single engine spec.
- **Bilingual AR/EN + RTL** deeply wired (260 `data-i18n`, 331 RTL refs) — the specs require it; we've done it.
- **Six additional customer surfaces** (`qr.html`, `shop.html`, `cfd.html`, `courses.html`, `drivethru.html`, `feedback.html`) beyond the specs' POS focus.

---

## 7. Prioritized gap list (if we chase the export)

**High value / high effort (architectural):**
1. Multi-tenant control plane (provisioning, lifecycle, isolation, billing) — currently ❌.
2. Platform SDK + extension points — currently ❌ (requires breaking the `pos.html` monolith).

**High value / medium effort (feature services):**
3. Search Service (multi-provider, Arabic normalization, ranking) — 🟡→ build.
4. Notification Service (priorities, escalation, inbox) — 🟡→ build.
5. Permission Service (default-deny policy engine, 10 scopes, elevation) — 🟡→ harden.

**Medium value / low effort (formalization):**
6. Publish the Component Library + UX-Pattern docs from what already exists in `pos.html`.
7. Formalize the Order/Payment FSMs (13-/10-/14-state) to match the engine contracts.
8. Config cascade engine + Admin Console governance + personal Settings sync.

**Reuse-aligned (leave as-is):** Tax & Discount — the specs themselves map to `account.tax`/pricelist/loyalty, which we already reuse. Don't rebuild; just verify parity.

---

*Report generated from extracted spec content + repo inventory. No code changed. Committed to your discretion.*
