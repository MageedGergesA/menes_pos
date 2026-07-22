# Mezze 2035 — The CTO's Narrative

*Written as the CTO of Mezze, not as an Odoo developer. This is a five-year plan to build the best restaurant operating system in the world. It reads as an Amazon six-pager, a Stripe RFC, and a Sequoia memo braided together. It is opinionated on purpose. Where the previous audit was too kind or too harsh, I correct it. Where a decision was fashionable rather than correct, I reject it.*

---

## The thesis, in one paragraph

Every incumbent restaurant OS — Toast, Square, Simphony — won by owning **three things**: the **money** (payments), the **moment of truth** (a terminal that never fails during a Friday-night rush), and the **ecosystem** (integrations that make switching painful). None of them won on features, and none of them won on design. Mezze's audit says we are world-class on the one thing that doesn't build a moat (design) and absent on the three that do. **The entire five-year plan is therefore a single sentence: keep the design edge, and go win the money, the reliability, and the ecosystem — in a region the incumbents can't serve — before we try to win the world.** Everything below is the how.

I am going to make one architectural decision on page one that governs everything after it, so let me make it now and defend it for the rest of the document.

---

## The decision that governs everything: **Odoo was the right womb, the wrong body**

The audit called Odoo "a double-edged sword." That was diplomatic. Here is the CTO version.

Odoo was **exactly the correct bootstrap.** It gave us — for free, on day one — double-entry accounting, stock deduction, loyalty, tax posting, and a data model that took Toast years and tens of millions to build. Building Mezze *on top of Odoo* is why a small team has a working, accounting-correct POS at all. I would make that choice again without hesitation. Anyone who says "you should have built it from scratch" has never had to ship revenue with a small team.

**And Odoo is a fatal choice as the permanent platform substrate.** It is a single-database, single-company, monolithic ERP with a request/worker model and a longpoll bus that does not horizontally scale to 100,000 tenants. It is not multi-tenant. Its release cadence is not ours to control. Its performance ceiling is not ours to raise. If Mezze *is* an Odoo customization, then Mezze's ceiling *is* Odoo's ceiling, and Odoo's ceiling is a few hundred restaurants per deployment. That is a consultancy business, not a platform company — and the audit correctly noted that the consultancy origin (Teklines) is visible in the architecture.

So here is the governing decision, and it is the most important sentence in this plan:

> **Mezze stops being an Odoo application and becomes a purpose-built, cloud-native, local-first platform that *integrates* Odoo — and NetSuite, QuickBooks, SAP, Xero — as one interchangeable back-office among many.**

This is the **Shopify move.** Shopify did not become a Rails app that sells things; it became a commerce *platform* with a Rails core it has spent a decade decomposing. Mezze becomes a restaurant *platform* with an accounting integration, where Odoo is one adapter behind a `FinanceGateway` interface. The instant Odoo is *behind an interface* instead of *underneath the product*, three things become true: we can scale past Odoo's DB model, we can sell to a restaurant that already runs SAP, and we can replace Odoo entirely in year 4 without the customer noticing.

The `mezze_bridge` addon — which the audit correctly praised for its idempotent sync and dead-letter ledger — **is the seed of this.** It already speaks a versioned JSON API and reuses Odoo's write path idempotently. We do not throw it away. We **invert** it: today the frontend talks *to Odoo via the bridge*; tomorrow the platform owns the truth and *pushes to Odoo (or SAP) via an adapter that looks exactly like today's bridge, reversed.* The bridge becomes the first `FinanceGateway` implementation. That is a rewrite of *ownership*, not of *code we throw in the bin*.

Everything in Parts 1–11 follows from this one decision.

---

# PART 1 — Architecture Vision for 2035

The organizing principle is **local-first, cloud-authoritative, event-sourced.** A restaurant terminal must take an order when the internet is down, the payment processor is slow, and the kitchen printer is on fire — and *lose nothing.* That is not a feature; it is the physics of the business. Toast's actual moat is that it stays up. So the terminal is not a thin client; it is an **edge node that owns its own data and reconciles with the cloud through an append-only event log.** This single idea resolves offline, sync, and reliability simultaneously.

```
                        ┌───────────────────────────────────────────────────┐
                        │                 MEZZE CLOUD (control + data plane) │
                        │                                                    │
 ┌──────────────┐  event log   ┌──────────────┐   ┌──────────────┐          │
 │  TERMINAL    │─────────────▶│ SYNC INGEST  │──▶│  EVENT BUS    │          │
 │ (edge node)  │◀─────────────│ (Temporal)   │   │ (NATS JS)     │          │
 │ local store  │  pull/config └──────┬───────┘   └──────┬────────┘          │
 │ outbox+CRDT  │                     │                  │                   │
 │ POS · KDS ·  │              ┌──────▼──────┐   ┌───────▼───────┐  ┌───────┐│
 │ print · pay  │              │ ORDER svc   │   │ PAYMENTS svc  │  │ PRINT ││
 └──────┬───────┘              │ KITCHEN svc │   │ (Temporal wf) │  │ svc   ││
        │ LAN                  │ INVENTORY   │   │ Stripe/Adyen/ │  │(queue)││
   ┌────▼─────┐                │ LABOR ...   │   │ Paymob/Geidea │  └───────┘│
   │ printers │                └──────┬──────┘   └───────┬───────┘           │
   │ (ESC/POS)│                       │                  │                   │
   │ terminals│              ┌────────▼──────────────────▼─────────┐         │
   │ scanners │              │  DATA LAKE (Iceberg/S3) ──▶ ClickHouse│        │
   └──────────┘              │  + Feature store  ──▶ AI / copilots  │         │
                             └───────────────────────────────────────┘        │
                        │  Identity (OIDC) · Secrets (Vault) · OTel everywhere │
                        └──────────────────────────────────────────────────────┘
       ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
       │ GUEST (edge) │   │ OWNER app    │   │ DEVELOPER    │
       │ QR/pay/menu  │   │ Manager app  │   │ platform/SDK │
       │ Cloudflare   │   │ (GraphQL)    │   │ (REST+webhk) │
       └──────────────┘   └──────────────┘   └──────────────┘
```

Subsystem by subsystem, the 2035 target:

**Frontend (terminal).** Rewritten off the single 4,962-line file into a **TypeScript, compile-time-reactive app (Svelte 5 or SolidJS), offline-first, running against a local store.** I am choosing a *compile-time* framework over React deliberately and against fashion: a POS runs on cheap Android/iPad hardware for 5–7 years; runtime overhead and bundle churn are the enemy; React's re-render model and ecosystem churn are liabilities on a device that must be fast and stable for a decade. The **design system survives intact** — it is our crown jewel — but it is *externalized* from the HTML file into a versioned token package (Style Dictionary → CSS + iOS + Android + email) so one source of truth drives every surface. The terminal ships as a PWA and as native shells (Capacitor/native) for hardware access.

**Frontend (guest/owner/manager/developer).** Separate apps, separate lifecycles. Guest ordering runs at the **edge (Cloudflare Workers)** — global, cheap, instant menus and receipts. Owner/Manager apps are data-graph apps over **GraphQL**. The developer platform is REST + webhooks.

**Backend.** A **modular monolith to start, decomposed by seam later** — not microservices on day one. This is the Shopify/Linear discipline: microservices are an *organizational* scaling tool, not an engineering virtue, and premature decomposition is how startups die of ops complexity. The monolith is organized by **Domain-Driven Design bounded contexts** (Order, Kitchen, Payments, Inventory, Labor, Identity, Billing) with hard module boundaries, so that when Payments needs to scale independently, it *lifts out cleanly* because it was never entangled. Runtime: **TypeScript (Bun/Node) for velocity and full-stack shared types**, with **Rust or Go for the three hot paths** where correctness and latency are money — the **sync ingest**, the **payment state machine**, the **print queue**. You do not write a settlement engine in a language that lets a floating-point rounding bug ship silently.

**API.** **gRPC internally** (typed contracts, fast, generated clients), **REST + webhooks publicly** (simplicity, universal, the integration lingua franca), **GraphQL for the read-heavy owner/analytics graph** (flexible querying is exactly what dashboards need; it is the wrong tool for writes and we won't force it there). One schema registry; contracts are the law.

**Sync & Offline (the heart).** An **event-sourced sync engine**, generalizing the pattern the audit found genuinely good in `mezze.sync.outbox`/`applied`. Terminal owns a local store (SQLite/embedded) + an **append-only outbox** with per-terminal `seq` ordering and `res_uuid` idempotency (both already exist). Cloud ingest is **exactly-once with a dead-letter ledger** (already exists) but moved into a **Temporal workflow** so replay, backpressure, and poison-handling are durable and observable rather than hand-rolled. Where events genuinely commute (stock deltas, loyalty points), we use **CRDT-style delta merges** (the outbox already carries deltas, not absolute state — that instinct was right). This is the **Linear sync-engine playbook** applied to restaurants, and it is the single biggest reliability multiplier we own.

**Printing.** A **durable print service**: every ticket is a **`print.job` with an 8-state lifecycle** driven by a **Temporal workflow** — queued → sending → printed / failed → retry(exponential) → failover(station→backup→receipt→hold) → dead-letter. A kitchen ticket is *never silently lost* because "lost" is not a reachable state in the machine. Reprint and stuck-job surfaces for managers. This is a from-scratch build; the ESC/POS render primitive we keep.

**Payments.** We **own orchestration and reconciliation; we delegate processing and PCI.** Stripe/Adyen as the global rail, Paymob/Geidea/HyperPay for MENA, behind one `PaymentProvider` interface. The **auth → capture → settle lifecycle is a Temporal workflow** with an **idempotent auth key per order+tender** — a double-tap on "Charge" re-reads the existing transaction and never double-charges. Batched end-of-day settlement + acquirer reconciliation. **Payments is not a feature; it is the business model** — this is where the revenue share lives, and it is why we build the orchestration ourselves instead of iframe-ing a processor and taking a referral fee.

**Kitchen.** Beyond a display: a **routing + capacity + coursing engine.** Orders route to stations by rule and by *live load*; capacity models predict ticket times; coursing fires and holds. This is where "restaurant OS" earns the name — the kitchen is the constraint, and software that manages the constraint is worth more than software that displays it.

**AI.** A **copilot-per-role layer** on top of a real **feature store + warehouse** (see Data). Not bolted-on chat; grounded, role-scoped agents that *act* (order stock, adjust prep, flag anomalies) with human approval. **Built last, deliberately** — AI without the data foundation is theater, and we will not ship theater.

**Restaurant services.** Inventory intelligence, recipes/BOM/food-cost, purchasing/suppliers, labor/scheduling — each a bounded context, each closing a Phase-3 lifecycle gap. These are what convert "POS" into "OS."

**Cloud platform.** **Cell-based multi-tenancy** (Slack/Figma model): tenants are packed into *cells* (self-contained full-stack pods), each cell isolated, with a routing control plane. Schema-per-tenant within a cell for isolation; DB-per-tenant for enterprise accounts. This is how you get to 100,000 tenants without a single-DB write hotspot and without cross-tenant blast radius.

**Deployment.** Managed containers first (Fly.io/ECS) → **Kubernetes when cell orchestration demands it**, not before. Multi-region. Blue/green + instant rollback. IaC (Terraform) from day one — the audit's "deployment 30/100" becomes non-negotiable table stakes.

**Monitoring & Observability.** **OpenTelemetry everywhere, no exceptions** → Prometheus/Grafana/Tempo/Loki (or Datadog if we'd rather buy time than build). SLOs with error budgets. Synthetic checks per store. The audit's "10/100 observability" is not a weakness to improve; it is a **prerequisite to having customers at all** — you cannot operate what you cannot see.

**Developer Platform & Plugin SDK.** A **typed SDK, a sandboxed plugin runtime, webhooks, and a marketplace.** This is the long-term moat: Toast's app store is why enterprise chains don't leave. We build the API platform in year 2 and open it in year 3.

**Event Bus.** **NATS JetStream** as the durable backbone — deliberately *not* Kafka. Restaurant event volume does not need Kafka's operational weight for years, and NATS is lighter, edge-friendly, and simpler to run. Redis Streams for intra-service ephemerality. We adopt Kafka only if and when volume *forces* it, and we'll be glad we didn't run it to move kitchen tickets in year 1.

**Data Lake / Warehouse / Analytics.** Events land in an **Iceberg/S3 lake** (cheap, open, replayable) and are served to **ClickHouse** for analytics (columnar, absurdly fast on restaurant time-series — the right tool, chosen for the workload not the logo). A **feature store** feeds AI. Reports stop running on demo data and start running on a real warehouse.

**Security.** **Zero-trust.** The 106 `auth='none'` endpoints on a shared token — the audit's worst finding — are replaced by an **API gateway with OIDC/JWT, per-tenant keys, scopes, and rate limiting.** WAF, secrets in **Vault** with rotation, a real threat model, and an external pen-test before any enterprise logo. mTLS device identity for terminals.

**Identity.** **OIDC (Ory/WorkOS/Auth0)** for humans, **SCIM** for enterprise provisioning, **device identity** for terminals. One identity plane, federated.

**Secrets.** **Vault** (or cloud KMS), rotation, no credential ever in `ir.config_parameter` or a repo.

**Scaling.** Cell-based tenancy + stateless services + event-sourced data = **horizontal by construction.** The terminal being local-first means the cloud is not in the critical path of a sale, which is the single most important scaling property a POS can have: **your revenue does not depend on our uptime.**

---

# PART 2 — Technical North Star (and the choices I reject)

If I started Mezze today with unlimited talent, here is the stack and the *reasoning*, including the fashionable things I would **not** do.

| Choice | Decision | Why (not fashion) |
|---|---|---|
| **Modular monolith vs microservices** | **Modular monolith**, DDD boundaries, split by seam later | Microservices are an org-scaling tool; adopting them at 10 engineers buys distributed-systems pain with no benefit. Split Payments/Sync out *when scale forces it* — they're already bounded. |
| **Local-first vs thin client** | **Local-first** (terminal owns data, syncs event log) | The defining reliability property of a POS. Removes the cloud from the sale's critical path. |
| **Event sourcing** | **Yes, for the transaction spine** (orders, payments, stock, KDS) | We already have the outbox/idempotency/dead-letter instinct; event log = perfect audit + replay + offline + analytics for free. Not everywhere — config/catalog stay CRUD. |
| **CQRS** | **Yes, lightly** — write to event log, project to read models (ClickHouse for analytics) | Restaurant reads (dashboards, KDS) and writes (orders) have wildly different shapes and scale. |
| **CRDTs** | **Only where events commute** (stock/loyalty deltas) | CRDTs everywhere is over-engineering; server-authoritative ordering is simpler for money. Use CRDTs surgically. |
| **DDD** | **Yes** | The only way a modular monolith stays clean enough to decompose later. |
| **Temporal** | **Yes** — payments, print, sync, settlement, onboarding | Durable, retryable, observable workflows *are literally the four reliability blockers*. This is the highest-leverage single tool in the plan. |
| **NATS JetStream vs Kafka** | **NATS** now, Kafka only if forced | Lighter ops, edge-friendly, sufficient for years. Running Kafka early is résumé-driven development. |
| **Redis Streams** | **Yes, intra-service** | Ephemeral queues, caching, rate-limit counters. |
| **gRPC** | **Internal** | Typed, fast, generated clients across services. |
| **GraphQL** | **Owner/analytics read graph only** | Right for flexible reads; wrong (and we won't force it) for writes/webhooks. |
| **REST + webhooks** | **Public/developer platform** | Universal, simple, the integration standard. |
| **OpenTelemetry** | **Everywhere, non-negotiable** | Vendor-neutral observability is table stakes, not a differentiator. |
| **ClickHouse** | **Analytics warehouse** | Columnar speed on time-series; the correct engine for restaurant analytics. |
| **Iceberg/S3 lake** | **Yes** | Cheap, open, replayable event store feeding ClickHouse + AI. |
| **Elastic/Typesense** | **Typesense** for product/menu search | Elastic is heavyweight ops; Typesense is fast, simple, and fits catalog scale. |
| **Kubernetes** | **Later** (managed containers first) | k8s is an operational tax you pay when cell orchestration demands it — not before. |
| **Cloudflare / edge** | **Guest-facing + config CDN** | Global menus/QR/receipts at edge latency and cost. |
| **Language: TS + Rust/Go** | **TS for velocity, Rust/Go for money hot paths** | Shared types across the stack; memory-safe correctness where a bug is a chargeback. |
| **Framework: Svelte/Solid (terminal)** | **Compile-time reactive** | Small, fast, stable for a decade on cheap hardware. React's churn/runtime cost is a POS liability. |
| **Multi-tenancy: cells** | **Cell-based, schema-per-tenant** | Isolation + horizontal scale to 100k without a single-DB hotspot. |

**Things I reject on principle:** Kafka-by-default, microservices-by-default, GraphQL-everywhere, k8s-on-day-one, blockchain-anything, and "AI-first" before the data foundation exists. Each is a way to look sophisticated while shipping slower. The north star is **boring, correct, local-first, and observable** — and we win with it.

---

# PART 3 — The Five-Year Roadmap

The sequencing law: **reliability and foundation before features; a regional beachhead before global; data before AI; platform before marketplace.** Budgets are order-of-magnitude, fully loaded.

### Year 1 — "Never lose an order." (Foundation + Reliability + Beachhead)
- **Objectives:** close the four money/data Criticals; make the terminal local-first; win the first 100 real restaurants in MENA.
- **Major systems:** test/CI/observability foundation; local-first terminal (outbox + connectivity); durable print (Temporal); payment state machine + idempotent auth + settlement (Temporal); wire the live sync engine to the terminal + reconcile UI; OTel everywhere.
- **New products:** production-grade POS + KDS + payments in Egypt/KSA/UAE with **ZATCA + ETA e-invoicing** compliance as a wedge feature.
- **Debt removed:** start the frontend de-monolith (strangler); externalize design tokens; replace `auth='none'`+shared-token with the gateway.
- **Infra:** managed containers, IaC, staging, backups/PITR, DR plan.
- **Hiring / team:** grow **5 → ~18.** VP/Chief Architect of Platform (the gating hire), SRE lead, security eng, 2 backend, 3 frontend, QA lead, 2 solutions/support.
- **Budget:** **~$4–6M.** **Impact:** a product you can actually sell without losing customers' money; a defensible MENA compliance+design wedge.

### Year 2 — "Become a platform." (Multi-tenancy + Restaurant depth)
- **Objectives:** true cell-based multi-tenancy; inventory + labor; scale MENA to ~1,000 restaurants.
- **Major systems:** cell architecture + tenant isolation + provisioning; billing/subscriptions/entitlements; admin console; inventory intelligence; labor/scheduling; kitchen routing/capacity engine; data lake + ClickHouse warehouse (reports on real data).
- **New products:** Owner app, Manager app, self-serve onboarding, guest QR ordering (edge).
- **Debt removed:** finish frontend framework migration; Odoo behind the `FinanceGateway` interface (Mezze now owns the truth).
- **Infra:** multi-region cells; feature-flag + config service; secrets vault.
- **Hiring / team:** **~18 → ~40.** Payments team, Platform team, Data team, DevRel seed.
- **Budget:** **~$10–15M.** **Impact:** SaaS economics unlocked; a real dashboard; the OS story begins.

### Year 3 — "Open the ecosystem." (Developer platform + Delivery + Expand)
- **Objectives:** launch the API platform, SDK, webhooks, and marketplace; delivery/dispatch + aggregators; enter a second region (or begin US mid-market).
- **Major systems:** developer portal, sandboxed plugin runtime, marketplace, partner portal; delivery dispatch + driver app + aggregator webhooks; CRM/marketing execution; central-kitchen/franchise multi-entity.
- **New products:** Customer app, Supplier/Vendor portals, franchise console.
- **Debt removed:** decompose Payments + Sync out of the monolith into services (they were always bounded); retire the last Odoo coupling in the hot path.
- **Infra:** Kubernetes for cell orchestration; global edge.
- **Hiring / team:** **~40 → ~70.** Kitchen team, Cloud team, DevRel, Solutions Engineering, AI/Data build-out.
- **Budget:** **~$20–30M.** **Impact:** integration lock-in begins; the moat starts to compound.

### Year 4 — "The restaurant runs itself." (AI + Enterprise)
- **Objectives:** ship the copilot layer on the now-real data foundation; land enterprise/multi-unit chains; option to replace Odoo entirely.
- **Major systems:** feature store + forecasting → auto-purchasing → dynamic prep; vision (drive-through, waste, portioning); voice ordering; role copilots (owner/manager/kitchen/cashier/developer); enterprise identity (SCIM, SSO), SOC2, advanced RBAC.
- **New products:** AI Platform, Finance/HR/Payroll depth, enterprise franchise suite.
- **Debt removed:** own accounting core (replace the Odoo adapter with native ledger where it wins), or keep Odoo where it's fine — decided on data, not ego.
- **Hiring / team:** **~70 → ~90.** Full AI team, enterprise squads, security/compliance org.
- **Budget:** **~$30–45M.** **Impact:** differentiation the incumbents can't match quickly; enterprise ACVs.

### Year 5 — "Best in the world, on our terms." (Global + Autonomy)
- **Objectives:** semi-autonomous restaurant operations; global expansion where design+AI+payments win; category leadership in MENA and a credible global #3–#4.
- **Major systems:** cross-region scale to 10k–100k tenants; autonomous ops loops (forecast→order→schedule→price→route with human exception-handling); marketplace flywheel; platform SLAs.
- **Hiring / team:** **~90 → ~150+.**
- **Budget:** **~$40–60M.** **Impact:** a platform company, not a POS vendor.

**Five-year cumulative:** **~$110–160M** deployed to reach a defensible, AI-native, multi-tenant global restaurant OS — consistent with a Series A → B → C trajectory, *not* a bootstrapped consultancy.

---

# PART 4 — The Restaurant Platform (every product Mezze should own)

Each product: **mission · primary users · core capabilities · roadmap.** The rule: own the surfaces that touch **money, the guest, or the kitchen constraint**; integrate the rest.

| Product | Mission | Primary users | Core capabilities | Roadmap |
|---|---|---|---|---|
| **POS** | Take any order, any channel, never fail | Cashier | dine/take/delivery, split, discount, tax, tender, offline | local-first → AI-assisted upsell |
| **Kitchen / KDS** | Run the constraint | Line, expo | routing, capacity, coursing, timing, bump | capacity AI, vision QA |
| **Reservations/Waitlist** | Fill every seat optimally | Host, guest | booking, deposits, channels, quote-times | AI seat/time optimization |
| **Delivery** | Own off-premise | Dispatcher, driver | dispatch, driver app, aggregator webhooks | route AI, ETA prediction |
| **Loyalty** | Repeat visits | Guest, marketer | points, rewards, tiers | AI personalization |
| **CRM** | Know every guest | Owner, marketer | profiles, segments, history | predictive LTV |
| **Marketing** | Drive demand | Marketer | campaigns, offers, channels | AI campaign generation |
| **Inventory** | Never 86, never waste | Manager | counts, par, waste, theoretical-vs-actual | predictive reorder |
| **Recipes/BOM** | Cost & consistency | Chef, owner | recipes, yield, food-cost | AI menu engineering |
| **Production / Central Kitchen** | Make at scale | CK manager | production plans, BOM explosion, transfers | demand-driven production |
| **Franchise** | Run many as one | Franchisor | multi-entity, brand control, roll-ups | franchise benchmarking |
| **Analytics** | Truth in numbers | Owner, ops | warehouse, dashboards, cohorts | copilot-answered analytics |
| **Finance** | Books that reconcile | Owner, accountant | ledger/adapter, reconciliation | native ledger option |
| **HR / Scheduling / Payroll** | Right staff, right time | Manager | scheduling, time, pay | AI labor optimization |
| **Customer App** | Guest self-service | Guest | order, pay, loyalty, book | voice/AI ordering |
| **Owner App** | Run the business from a phone | Owner | KPIs, alerts, approvals | owner copilot |
| **Manager App** | Run the shift | Manager | ops, exceptions, labor | manager copilot |
| **Supplier / Vendor Portal** | Close the supply loop | Suppliers | POs, catalogs, invoices | auto-purchasing |
| **Marketplace** | Extend without us | Developers, operators | apps, integrations | revenue-share ecosystem |
| **Developer Platform / API** | Build on Mezze | Developers | SDK, webhooks, sandbox | plugin runtime, app store |
| **AI Platform** | Operate the restaurant | Everyone | copilots, forecasting, vision | autonomy loops |

---

# PART 5 — The Enterprise Platform

The layer that converts "product" into "company." Cell-based tenancy is the spine; everything else hangs off it.

| Capability | Design |
|---|---|
| **Multi-tenancy** | Cell-based; schema-per-tenant (DB-per-tenant for enterprise); routing control plane; blast-radius contained per cell |
| **Identity** | OIDC humans, SCIM enterprise, device identity (mTLS) for terminals, one federated plane |
| **Billing / Subscriptions** | Usage-metered + seat + payments-rev-share; Stripe Billing or in-house metering; entitlements service |
| **Organizations** | Tenant → brand → region → location → terminal hierarchy; org-scoped everything |
| **Permissions** | Policy engine (OPA-style), timed elevation + audit, per-tenant RBAC, least-privilege baselines |
| **Audit** | Extend the existing append-only log to platform-wide, immutable, exportable, SOC2-attestable |
| **Configuration** | Versioned, per-tenant config service (not `ir.config_parameter`), promotion/rollback |
| **Feature Flags** | Server-driven flag service, per-tenant/cohort, kill-switches |
| **Notifications** | Category-driven multi-channel (in-app/SMS/email/push) with escalation ladders |
| **Integrations / Webhooks** | Signed, retried, replayable webhooks; connector framework |
| **SDK / Plugin System** | Typed SDK; sandboxed plugin runtime (WASM) so third-party code can't take down a store |
| **Marketplace** | Curated app store, revenue share, review pipeline — the lock-in moat |
| **Admin / Developer / Partner Portals** | Internal support console (impersonation, session tools), external dev portal, partner portal |

---

# PART 6 — Artificial Intelligence in 2035

The 2035 vision is **the self-driving restaurant, with a human in the loop for exceptions.** AI does not "assist"; it *operates*, and the manager manages the exceptions. This is only credible because Years 1–3 build the data foundation (event lake + warehouse + feature store) that makes grounding possible. AI is the payoff, not the premise.

- **Demand forecasting** predicts covers by daypart/weather/event; drives everything downstream.
- **Purchasing** auto-generates POs to suppliers from the forecast + par levels; the manager approves exceptions.
- **Inventory prediction** flags run-outs before they happen; **food-waste reduction** models over-prep.
- **Kitchen optimization** routes and paces tickets by live capacity; **order timing** fires courses.
- **Staff scheduling** builds the labor plan against forecast demand and labor law; **dynamic pricing** adjusts within owner-set guardrails.
- **Vision systems** run drive-through order accuracy, portioning QA, and waste tracking from cameras.
- **Voice ordering** takes phone/drive-through/kiosk orders conversationally.
- **Copilots per role** — the interface to all of it:
  - **Owner copilot:** "Why was margin down last week?" → grounded answer + action.
  - **Manager copilot:** runs the shift, surfaces exceptions, drafts the schedule.
  - **Kitchen copilot:** balances load, warns of 86s, paces coursing.
  - **Cashier copilot:** upsell, allergen, split-check help.
  - **Developer copilot:** builds integrations against our SDK.

Opinion, stated plainly: **most "AI in POS" today is a chatbot on a dashboard, and it is worthless.** Ours is worth building only because the local-first event spine gives us clean, real-time, tenant-grounded data. Without that, we would be shipping the same theater as everyone else, and I would refuse to ship it.

---

# PART 7 — Competitive Strategy

**Forget feature parity — it is a losing game against companies with 10x the engineers.** Strategy is about where we *don't* fight and what we *dominate*.

**Where Mezze intentionally does NOT compete:**
- **Hardware manufacturing.** Partner. Toast's vertical hardware is a moat we can't out-spend; we run on commodity + partner terminals.
- **Generic accounting/ERP.** Integrate (Odoo/QuickBooks/SAP). We are not an ERP.
- **US enterprise on day one.** Toast/Simphony own it; a frontal assault dies. We flank.
- **Everything-for-everyone globally in year 1.** Focus is the weapon.

**What Mezze DOMINATES (the moats we build):**
1. **MENA / Arabic-first + compliance.** Egypt, KSA, UAE. Arabic/RTL as a first-class citizen (not an afterthought bolt-on like the incumbents), ZATCA + ETA e-invoicing native, local payment rails (Paymob/Geidea/mada). Toast and Square barely operate here. **We win a region the giants can't serve, then expand — the Square/Shopify beachhead playbook.**
2. **Design & UX as a wedge.** The one thing the audit says we're world-class at. It wins demos, reduces training cost, and lowers churn. We lean in *hard* — but we know it's the wedge, not the moat.
3. **Local-first reliability.** "Offline that actually works" is a genuine differentiator in a region with unreliable connectivity — and everywhere on a Friday night.
4. **Payments + the money flow.** Own orchestration and rev-share; this is the durable revenue moat, same as Toast.
5. **The developer ecosystem.** The long game: an app marketplace makes switching painful. This is the compounding moat that turns a regional winner into a global platform.

**The competitive posture vs each incumbent, in one line each:**
- **Toast:** we don't fight their US hardware+scale; we out-design them and own MENA, then their mid-market on ecosystem+price.
- **Square:** we out-verticalize them (they're horizontal SMB); restaurant-native depth + MENA.
- **Simphony (Oracle):** we out-*modern* them — cloud-native, local-first, beautiful vs their legacy enterprise weight.
- **Lightspeed:** we out-reliability and out-design them in our region.
- **Revel/SpotOn/Clover:** out-design, out-reliability, out-platform.
- **Odoo POS:** we already out-design it by a mile — and we *use* its guts while transcending its ceiling. The irony is our starting advantage.

---

# PART 8 — Technical Debt (what I'd delete, rewrite, invest in)

Owning this company, here is the unsentimental verdict.

**What is exceptional (protect and amplify):**
- **The design system** — genuinely world-class, token-disciplined, dual-theme, accessible. *Externalize it; it's the crown jewel.*
- **The design/verification *discipline*** — 58 docs, byte-level regression proofs, live-verified phases. This engineering *culture* is rare and worth more than any single artifact.
- **The sync engine pattern** — outbox + `seq` + `res_uuid` idempotency + dead-letter + delta payloads. The audit was wrong to score it low; this instinct is exactly right and becomes the platform's spine.
- **The audit log** — append-only, ACL-locked, money-action coverage. Enterprise-shaped already.
- **The MENA/compliance work** (ETA/ZATCA hooks) — a real regional moat.

**What I'd rewrite (not delete — these are load-bearing and work):**
- **The frontend monolith → a component framework.** Not because monoliths are bad (this one shipped a world-class product), but because *one 4,962-line file caps the team at ~1–2 safe editors*, and the P5/P6/P7 live-only bugs prove the risk. Strangler migration, design system preserved.
- **The sync ownership → invert it.** Move the truth into the platform; Odoo becomes an adapter.
- **Payments & print → Temporal workflows.** Durable state machines replace hand-rolled/synchronous flows.
- **Auth → an API gateway.** Kill the 106 `auth='none'` shared-token endpoints.

**What should never have been built as a *destination* (but was fine as a *bootstrap*):**
- **Mezze-as-an-Odoo-customization.** Correct to start; wrong to stay. The `bridge` is the escape hatch and we already have it.

**What I would delete today: nothing.** You do not delete working revenue. You *strangle and replace* it, module by module, behind stable interfaces — which is what every line above describes.

**What deserves the most investment, in order:** (1) the reliability/foundation/observability base — it's the license to operate; (2) multi-tenancy — it's the license to be a company; (3) the design system externalization — cheap, high-leverage, protects the moat; (4) payments orchestration — it's the revenue; (5) the developer platform — it's the compounding moat.

---

# PART 9 — The Engineering Organization

Scale the org the way you scale the architecture: **generalists who can hold the whole system first, specialists as seams harden.**

**At 5 (today+):** CTO/architect · 2 senior full-stack · 1 SRE/platform · 1 design-engineer. *Everyone owns everything.* Ship reliability.

**At 10:** + backend (payments/sync) · frontend (de-monolith) · QA/test-infra · security · solutions/support. *First team boundaries appear.*

**At 25:** distinct **Platform**, **POS**, **Payments**, **Cloud/SRE** teams; **Data** seed; **Design System** ownership; **DevRel** seed. Principal engineer #1.

**At 50:** add **Kitchen**, **AI/Data**, **Security/Compliance (SOC2)**, **Solutions Engineering**, **Support Engineering**; VP Engineering hired; 2–3 principals across payments/platform/data.

**At 100:** full org — **VP Eng + directors** per domain; **Platform, POS, Kitchen, Payments, Cloud, DevOps/SRE, Security, QA, AI, Data, Design System, DevRel, Support Eng, Solutions Eng**; a platform/architecture council; on-call maturity; internal developer platform team.

**The single most important hire, at any size:** the **VP/Chief Architect of Platform** with real multi-tenant SaaS scars. The audit's gating condition stands: *this person is a close condition of the round, not a post-close hope.* Design talent we have; platform leadership is the gap, and it is the gap that kills the company if unfilled.

---

# PART 10 — The Investment Memo (Sequoia / a16z / YC lens)

**Company:** Mezze POS — an AI-native, design-led restaurant operating system, MENA-first.

**Strengths.** World-class design/UX and engineering discipline; a mature accounting substrate (Odoo) as a capital-efficient bootstrap; a genuinely good sync/reliability pattern already in code; a real regional wedge (Arabic/RTL + ZATCA/ETA compliance + local payment rails) in a large, underserved, fast-growing market the incumbents ignore; unusually strong documentation/culture for the stage.

**Weaknesses.** No multi-tenancy, no tests, no observability, no CI/CD, a single-file frontend monolith, an unfinished payment state machine, and a platform coupled to Odoo's scaling ceiling. Consultancy origin visible in the architecture. **The entire "platform" and "SaaS" layer is unbuilt.**

**Opportunities.** MENA restaurant tech is early and huge; compliance mandates (Saudi ZATCA, Egypt ETA) create a *forced* buying event that favors a compliant, local, beautiful product; a payments-rev-share model; a developer ecosystem; AI-native operations as the 2035 wave.

**Threats.** Incumbents (Toast/Square) entering MENA; local competitors; the execution risk of a design team building a platform; capital intensity ($110–160M over 5y); Odoo dependency risk if not decoupled on schedule.

**Technology moat (today → target).** Today: shallow (design is copyable, though hard). Target: *deep* — local-first reliability + payments orchestration + MENA compliance + a plugin marketplace. The moat is built, not inherited.

**Business moat.** Payments rev-share (recurring, defensible) + ecosystem lock-in + regional compliance + brand. The classic restaurant-OS moat, achievable.

**Execution risk: HIGH.** The team's proven competence is *design*; the plan requires *platform engineering at scale*. This is the crux, and it is exactly what the VP-Platform gating hire is meant to de-risk.

**Market risk: MEDIUM.** MENA demand and compliance tailwinds are real; the risk is timing and incumbent entry.

**Platform risk: HIGH-but-addressable.** Multi-tenancy and Odoo-decoupling are hard but well-understood; the roadmap sequences them correctly.

**Would I invest?** **Yes — as a seed/Series A design-led regional platform bet, conditionally.** The pattern investors love is *"exceptional taste + a real wedge + a fixable platform gap + a market with tailwinds."* Mezze is precisely that. The bet is not "this code scales" (it doesn't); the bet is "*this team's taste plus this region's tailwind plus a bought-in platform leader compounds into the category winner.*"

**How much / valuation.** A **$4–8M seed or a $15–25M Series A**, structured with a **milestone tranche gated on the reliability+foundation sprint and the VP-Platform hire.** Valuation framed on the *wedge and team*, not current ARR — this is a bet on taste and market, priced accordingly, with the platform risk reflected in tranching rather than a lower headline.

**The one-sentence memo:** *Fund the platform this design deserves, in the region the giants can't serve, with a platform leader as a close condition — or don't fund it at all.*

---

# PART 11 — Final CTO Verdict

I will not be polite, and I will challenge my own prior reports.

**I challenge Odoo.** Keeping Mezze *as* an Odoo app is the single decision that would kill this company, and I have made the call to reverse it: Odoo becomes an adapter, not the substrate. Anyone who resists this because "we know Odoo" is optimizing for the team's comfort over the company's ceiling. The bridge is our escape hatch; we take it.

**I challenge the frontend.** The single-file monolith is the best *prototype* I've seen and an unacceptable *platform*. It shipped world-class design with a tiny team — genuine, and I respect it — but it caps us at one or two safe editors and it *silently hid two entire broken phases* until a human loaded the page. That is not a quirk; it is the ceiling on team scale. We preserve the design system and rewrite the shell around it. Not someday — starting Year 1.

**I challenge the backend.** The domain modeling and the sync engine are better than my audit credited — I was wrong, and I've corrected it. But 106 `auth='none'` endpoints on a shared token, zero tests on money code, and zero observability are not "areas to improve"; they are *disqualifying for a business that holds other people's money.* We fix them first, before a single feature.

**I challenge the roadmap — including this one.** Any five-year plan is fiction in the details. What is *not* fiction is the *sequence*: reliability before features, region before world, data before AI, platform before marketplace. If we execute the sequence and miss half the dates, we still win. If we chase features and AI before reliability and multi-tenancy, we die with a beautiful demo. The sequence is the plan; the dates are guesses.

**I challenge my own audit's headline.** "44/100" was fair as a *snapshot* and misleading as a *verdict*. The right verdict is: **Mezze is a 95th-percentile design company sitting on a 25th-percentile platform, in a 90th-percentile market, with a team that has proven exactly the rare thing (taste + discipline) and not yet proven the learnable thing (platform scale).** That is not a 44/100 company. That is a *fundable, winnable, conditional* company.

**What Mezze becomes by 2035 if every recommendation is executed:** the **default restaurant operating system of the Middle East and a credible global top-four** — a local-first platform that *never loses an order*, that *owns the money flow*, that runs a self-driving restaurant with a human on exceptions, that Arabic-speaking operators love and switch *to*, with a developer marketplace that makes them never switch *away*. Not the biggest — Toast will be bigger. But on the axes we chose to dominate — **design, reliability, MENA, payments, and AI-native operations** — the best in the world. A platform company worth billions, not because it out-featured the incumbents, but because it **out-focused** them: it picked a region they couldn't serve, a reliability bar they took for granted, and a design bar they never reached — and it built the boring, correct, observable platform underneath to make all three durable.

That is the company. The design is already here. The market is already here. The only thing missing is the platform — and the platform is *learnable, hireable, and sequenced.* So we build it.

*— The CTO*
