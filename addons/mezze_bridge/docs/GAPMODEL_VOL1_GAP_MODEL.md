# Mezze — Complete Gap Model · VOLUME I: The Gap Model

*Produced by the Enterprise Architecture Program Office (Google DE, Amazon PE, Stripe Staff, Shopify Arch Council, Toast CTO, Oracle Retail, SAP EA, Azure Reliability, AWS Well-Architected, Uber Marketplace, Cloudflare Infra, Apple HI, IBM Security, NIST, PCI/SOC2/ISO auditors, GDPR officer, Restaurant Ops Director, Michelin consultant, Enterprise QA, SRE Director, DB Researcher, Distributed-Systems Researcher, Product VP, UX Director, AI Platform Director, Enterprise PM). Target system: 1,000,000 restaurants · 100 countries · 25 years · offline-first · multi-tenant SaaS · AI-native · financial platform · restaurant OS.*

*This is not an RFC and not a roadmap. It is the gap model: the delta between what exists and what a Fortune-100 review board will demand. Six volumes: I Gap Model · II Top 500 Missing Capabilities · III Failure & Decision Catalogs (200 risks + 6×100) · IV Program Portfolio + Dependency Graph · V Engineering Backlog · VI Readiness Matrix + Self-Audit.*

## How to read maturity

Maturity scale (evidence-based, not intent-based): **0** none · **1** prototype/undocumented · **2** built, untested · **3** built + tested · **4** production-hardened + observable · **5** certified/proven at target scale. "Current" = what the codebase + working product demonstrably do today. "Desired" = what 1M-restaurant/100-country/25-year operation requires.

Every area's **fixed quality bar** (per the Implementation Roadmap) is: unit + integration + property + offline + replay + security + performance + migration + conformance tests. Rather than repeat that 85 times, it is stated once here; per-area rows below name only the *area-specific* evidence beyond the bar.

Board disagreements resolved inline as **[Resolved: …]**.

---

## The Gap Model Table (85 areas)

Columns: **Area · Cur→Des · Risk (top) · Sev · Impact (B/T/O) · Complexity · Key Dependencies · Evidence Required / DoD**. Sev: 🔴 blocker · 🟠 critical · 🟡 high · 🔵 medium · ⚪ low.

### Layer A — Business & Domain

| # | Area | Cur→Des | Top Risk | Sev | B/T/O | Cplx | Deps | Evidence / DoD |
|--|------|---------|----------|-----|-------|------|------|----------------|
|1|Business Model|2→5|Revenue thesis (graph/fintech) unbuilt|🟠|H/M/L|L|P9,P11|Metered billing live; graph-derived product sold to a pilot cohort|
|2|Domain Model|3→5|Ontology(40)↔code(subset) drift|🟡|M/H/M|L|P2|Code entities ≡ RFC-001; conformance CI 40/40|
|3|Ontology|4→5|Prose, not machine-enforceable|🔵|L/M/L|S|P2|Machine-readable ontology + conformance check|
|4|Operating Graph|1→5|Asset has no runtime substrate|🔴|H/H/M|XL|P2|Event store + projections + replay in prod|
|5|Business Invariants|1→5|74 invariants unenforced|🔴|H/H/M|L|P2,P3|74/74 executable guards + property tests|
|6|Domain Events|2→5|No event store/registry/versioning|🟠|M/H/M|L|P2|Immutable log + schema registry + upcasters|

### Layer B — Distributed Runtime

| # | Area | Cur→Des | Top Risk | Sev | B/T/O | Cplx | Deps | Evidence / DoD |
|--|------|---------|----------|-----|-------|------|------|----------------|
|7|Identity (entity)|2→5|No merge/unmerge, collision at 10⁶|🟠|M/H/M|L|P2|Reversible merge + 10⁶ collision property test|
|8|Time model|1→5|No business-day/event-time engine; DST×100 locales|🟡|M/H/M|M|P2|Time engine passes 100-locale/DST corpus|
|9|Offline|3→5|Power-loss durability unproven on HW|🟡|H/H/H|L|P2|Encrypted store + power-cut hardware test|
|10|Synchronization|3→5|Fan-out at branch scale unproven|🟡|H/H/H|L|P2,P3|Realtime transport + convergence ≤5s at scale|
|11|Distributed Consistency|1→5|Claimed, not modeled/verified|🟠|M/H/M|L|P2,P3|Formal model + Jepsen-style chaos green [Resolved: event-sourced + per-aggregate order + idempotent apply; CRDTs only for counters/sets, not orders — DB vs DS researcher tie broken toward event log]|
|12|Conflict Resolution|1→5|Silent last-writer corrupts orders|🟠|H/H/M|M|P5|Same-field clash → review 100%; dup-collapse test|

### Layer C — Security, Identity & Trust

| # | Area | Cur→Des | Top Risk | Sev | B/T/O | Cplx | Deps | Evidence / DoD |
|--|------|---------|----------|-----|-------|------|------|----------------|
|13|Authentication|1→5|**Single shared static token; auth='none'**|🔴|H/H/H|L|P1|0 auth='none' data routes; per-principal tokens|
|14|Authorization|2→5|No row/field scope; no ABAC|🟠|M/H/M|L|P1|Default-deny proven; scope matrix tested|
|15|Secrets Mgmt|1→5|Credentials in config params|🔴|M/M/H|S|P1|Vault; secret-scan CI clean; rotation drill|
|16|Audit|3→5|Not tamper-evident; no retention|🟡|M/M/H|M|P2|Hash-chained, tenant-partitioned, retained|
|17|Fraud|0→4|No velocity/anomaly controls|🟠|H/M/M|L|P6,P9|Refund/discount/void anomaly detection live|
|18|Security (platform)|1→5|No threat model/pen-test/WAF/rate-limit|🔴|H/H/H|L|P1,P7|Threat model + pen-test no-crit + WAF|

### Layer D — Financial Platform

| # | Area | Cur→Des | Top Risk | Sev | B/T/O | Cplx | Deps | Evidence / DoD |
|--|------|---------|----------|-----|-------|------|------|----------------|
|19|Payments|2→5|Single PSP (Egypt); no PCI/3DS/SCA|🔴|H/H/M|XL|P6|PSP-agnostic + PCI scope + no PAN in store|
|20|Ledger|2→5|Odoo reuse unattested|🟠|H/H/M|L|P6|Double-entry balances a generated year|
|21|Settlement|1→4|No recon vs processor files|🟠|H/M/M|L|P6|100% settlement-line attribution or exception|
|22|Tax|2→5|One endpoint; no jurisdiction packs|🟡|H/H/M|L|P6|Bit-for-bit `account.tax`; 2+ market packs|
|23|Pricing|2→4|No dynamic/channel pricing|🔵|M/M/L|M|P8,P12|Price versioning + channel prices tested|
|24|Discounts|2→4|No best-price solver; abuse guard|🔵|M/M/L|M|P6,P12|Best-price correctness + velocity guard|
|25|Promotions|2→4|No attribution/retention measurement|🔵|M/M/L|M|P9,P12|Promo→retention measured longitudinally|

### Layer E — Restaurant Domain

| # | Area | Cur→Des | Top Risk | Sev | B/T/O | Cplx | Deps | Evidence / DoD |
|--|------|---------|----------|-----|-------|------|------|----------------|
|26|Inventory|2→5|No recipe depletion→food cost; counts|🟡|H/M/M|L|P12|Food cost reconciles depletion→ledger|
|27|Kitchen/KDS|3→4|5-state vs 14-state; no bump-bar/SLA|🔵|M/M/H|M|P8|14-state FSM + hardware + SLA prediction|
|28|Reservations|3→4|No channel integrations/no-show model|🔵|M/M/M|M|P9,P12|Channel sync + no-show forecast|
|29|CRM|2→4|No segmentation/journeys/consent|🟡|M/M/M|M|P11,P12|Segments+journeys+consent-linked|
|30|Loyalty|3→4|No tiers/cross-brand/liability GL|🔵|M/M/M|M|P6,P12|Tier engine + liability posted to ledger|
|31|Restaurant Ops|3→5|No labor/purchasing/production depth|🟡|H/M/H|L|P12|Scheduling+purchasing+BOM live|
|32|Michelin/Fine-dining|1→4|No coursing/pacing/allergen depth|🔵|M/L/M|M|P12|Coursing+allergen+chef's-table flows [Resolved: Michelin consultant — allergen traceability is a *safety* requirement, elevate to 🟡]|

### Layer F — Platform Services

| # | Area | Cur→Des | Top Risk | Sev | B/T/O | Cplx | Deps | Evidence / DoD |
|--|------|---------|----------|-----|-------|------|------|----------------|
|33|Configuration|2→5|No cascade engine/versioning/templates|🟡|M/H/M|L|P8|0-code new branch; ≤1s propagate; rollback|
|34|Printing|2→4|No durable queue/DLQ/failover|🟡|M/M/H|M|P8|No lost ticket across failover chaos|
|35|Notifications|2→4|No priority/escalation/inbox|🟡|M/M/M|M|P8|Critical 100% delivered/escalated|
|36|Search|1→4|No service/AR normalize/ranking|🟡|M/M/M|M|P8|≤80ms@10k; AR parity corpus signed|
|37|Localization|2→5|AR/EN only; 90+ countries|🟡|H/M/M|L|P12|N-language pipeline; locale/number/date framework|
|38|Accessibility|2→5|AA claimed, unaudited|🔵|M/M/L|M|P12|AA audit + VPAT + SR journeys|

### Layer G — Data & Intelligence

| # | Area | Cur→Des | Top Risk | Sev | B/T/O | Cplx | Deps | Evidence / DoD |
|--|------|---------|----------|-----|-------|------|------|----------------|
|39|Analytics|1→5|No warehouse/semantic layer|🟡|H/M/M|L|P9|Warehouse reconciles to ledger|
|40|Forecasting|0→4|Absent|🟠|H/M/M|L|P9|Forecast evaluated vs actuals; MAPE tracked|
|41|Benchmarking|0→4|The moat is unbuilt|🟠|H/M/M|L|P9|Re-identification adversarial tests fail|
|42|AI Platform|1→4|Stub; no governance/eval|🟡|H/M/M|L|P9|Provider-agnostic + confidence gate + eval|
|43|Model Governance|0→4|No registry/versioning/drift|🟠|M/M/H|M|P9|Registry + drift alerts + rollback|
|44|Prompt Safety|0→4|No injection/jailbreak defense|🟠|H/M/M|M|P9|Prompt-injection red-team suite green|
|45|Hallucination Ctrl|0→4|No grounding/citation/abstain|🟠|H/M/M|M|P9|Confidence-gated abstain; grounded-only outputs|
|46|AI Evaluation|0→4|No eval harness/golden sets|🟠|M/M/M|M|P9|Per-capability eval gates in CI|
|47|Data Quality|1→4|No validation/anomaly/SLA|🟡|M/M/M|M|P9|DQ checks + freshness SLOs|
|48|Data Contracts|0→4|No producer/consumer contracts|🟡|M/H/M|M|P2,P9|Schema contracts enforced in CI|
|49|Knowledge/Operating Graph|1→5|Substrate + query layer absent|🔴|H/H/M|XL|P2,P9|Canonical queries (RFC-002 P7) answerable|

### Layer H — Reliability & Operations

| # | Area | Cur→Des | Top Risk | Sev | B/T/O | Cplx | Deps | Evidence / DoD |
|--|------|---------|----------|-----|-------|------|------|----------------|
|50|Observability|1→5|No metrics/traces/logs/SLO|🟠|M/H/H|L|P0,P7|Golden signals per service/tenant|
|51|Monitoring/Alerting|1→4|No alerts/on-call|🟠|L/M/H|M|P7|SLO breach pages on-call|
|52|Logging|1→4|Unstructured, PII risk|🟡|L/M/H|S|P0|Structured, PII-scrubbed, retained|
|53|Tracing|1→4|No distributed tracing|🟡|L/M/H|S|P0|Trace IDs end-to-end|
|54|Chaos|0→4|No fault injection/game-days|🟠|M/M/H|M|P7|Quarterly game-day evidence|
|55|Disaster Recovery|1→5|No tested failover/multi-region|🟠|H/H/H|L|P7|RTO≤30m/RPO≤5m game-day|
|56|Backups|1→5|No per-tenant PITR/restore drills|🟠|H/M/H|M|P7|Auto-verified single-tenant restore|
|57|Deployment|1→4|No CI/CD/IaC/canary|🟠|M/H/H|L|P0|Blue-green + canary + auto-rollback|
|58|Release Engineering|1→4|Manual flags; no staged rollout|🟡|L/M/H|M|P0|Governed flags + staged rollout|
|59|Cost/FinOps|0→4|No unit economics/cost attribution|🟡|H/L/M|M|P7|Per-tenant cost attribution + budgets|
|60|Storage|1→4|No tiering/lifecycle/residency|🟡|M/M/M|M|P7,P11|Lifecycle policies + residency tags|
|61|Caching|1→4|No tenant-namespaced cache strategy|🔵|L/M/M|S|P4,P7|Namespaced + invalidation ≤1s|
|62|Networking/Edge|1→4|No edge/latency strategy ×100 countries|🟡|M/M/M|L|P7|Edge POPs + latency SLOs per region|

### Layer I — Scale & Performance

| # | Area | Cur→Des | Top Risk | Sev | B/T/O | Cplx | Deps | Evidence / DoD |
|--|------|---------|----------|-----|-------|------|------|----------------|
|63|Scalability|1→5|Single Odoo instance; no cells/shards|🔴|H/H/H|XL|P4,P7|Cell architecture; 1M-restaurant load test|
|64|Performance|2→4|No load/soak/regression gates|🟡|M/M/M|M|P0,P7|Perf gates in CI; capacity model|
|65|Multi-tenancy|1→5|Multi-branch ≠ multi-tenant|🔴|H/H/H|XL|P1,P4|Control plane + isolation fuzz 100% denied|

### Layer J — Compliance, Privacy, Legal

| # | Area | Cur→Des | Top Risk | Sev | B/T/O | Cplx | Deps | Evidence / DoD |
|--|------|---------|----------|-----|-------|------|------|----------------|
|66|Compliance (fiscal)|1→5|Egypt only; 100-country fiscalization|🔴|H/M/H|L|P11|Pluggable fiscal packs; statutory validation|
|67|Privacy/GDPR|1→5|No consent/DSAR/erasure|🔴|H/M/H|L|P11|DSAR e2e; erasure preserves audit skeleton|
|68|Data Governance|1→4|No catalog/lineage/classification|🟠|M/M/M|M|P9,P11|Catalog+lineage+retention|
|69|Legal|1→4|No ToS/DPA/liability/e-discovery|🟡|H/L/M|M|P11|DPA + legal-hold + e-discovery export|
|70|Licensing (OSS/Odoo)|2→4|LGPL/Odoo license posture unmanaged|🟡|H/L/L|S|P0|License scan + attribution + policy|
|71|PCI DSS|0→5|No scope/attestation|🔴|H/M/H|L|P6,P11|AOC/ROC for deployment topology|
|72|SOC 2|0→5|No controls/evidence|🔴|H/L/H|L|P11|Type II report|
|73|ISO 27001|0→5|No ISMS|🟠|H/L/M|L|P11|Certificate|
|74|Gov/Public sector|0→3|No FedRAMP/local-gov posture|🔵|M/L/M|L|P11|Per-country gov requirements matrix|

### Layer K — Ecosystem & Developer

| # | Area | Cur→Des | Top Risk | Sev | B/T/O | Cplx | Deps | Evidence / DoD |
|--|------|---------|----------|-----|-------|------|------|----------------|
|75|Plugin Platform/SDK|0→5|Monolith; no extension points|🔴|H/H/M|XL|P10|Sample plugin extends w/o core edit; sandbox|
|76|Marketplace|0→4|Absent|🔵|H/M/M|L|P10|Signed bundles + review + entitlements|
|77|ERP Connectors|1→4|Odoo-only|🟡|H/M/M|L|P10|SAP/Oracle/NetSuite/QuickBooks adapters|
|78|Partner APIs|1→4|Internal only; no versioning/OAuth|🟡|H/M/M|M|P10|Public versioned API + sandbox + limits|
|79|CLI|0→3|Absent|🔵|L/M/L|S|P10|`mezze` CLI (lint/deploy/scaffold)|
|80|Developer Experience|1→4|No portal/docs/local env|🟡|M/M/M|M|P10|Portal + API ref + local dev|

### Layer L — Delivery & Enterprise Go-to-Market

| # | Area | Cur→Des | Top Risk | Sev | B/T/O | Cplx | Deps | Evidence / DoD |
|--|------|---------|----------|-----|-------|------|------|----------------|
|81|Testing|1→5|**Zero automated tests**|🔴|M/H/H|L|P0|Full pyramid; coverage gate|
|82|CI/CD|1→4|Absent|🟠|M/H/H|L|P0|Pipeline mandatory on every PR|
|83|Migration/Versioning|1→4|No data/schema migration framework|🟡|M/M/M|M|P0,P2|Zero-downtime migration + API semver|
|84|Documentation|3→4|No API ref/ops docs; ADR-thin|🔵|L/L/M|S|P0|API ref + ops docs + ADR cadence|
|85|Commercial/Enterprise GTM|1→4|No billing/SLA/procurement kit/PS/CS/training/cert|🟠|H/L/M|L|P11|Billing + SLA + security kit + PS/CS/training/cert programs|

---

## Cross-cutting board resolutions (disagreements settled)

- **[Consistency model]** DB Researcher pushed relational-with-strong-consistency; Distributed-Systems Researcher pushed pure event-sourcing/CRDT. **Resolved:** event-sourced log as system of record (RFC-002-aligned), per-aggregate ordering + idempotent apply for exactly-once; CRDTs restricted to commutative counters/sets (stock deltas, loyalty points); Odoo remains a *projection target*, not the source of truth. This keeps RFC-002 intact and is implementable.
- **[Payments vs Ops sequencing]** Stripe wanted payments first; SRE Director wanted observability first. **Resolved:** neither before P1 (identity) and P2 (substrate); P6 and P7 run in the same step (Q4), P7 slightly leading so payment incidents are observable.
- **[De-monolith timing]** Apple HI wanted the frontend split early for UX modularity; Product VP warned it stalls feature delivery. **Resolved:** de-monolith is P10 (after service seams exist in P8), extracted one workspace per release with byte-parity tests — no big-bang.
- **[Odoo dependency]** SAP EA flagged Odoo lock-in as an existential 25-year risk; Toast CTO noted Odoo accelerates today. **Resolved:** keep Odoo as a projection/accounting target behind an abstraction seam (P2/P6); the event log makes Odoo replaceable without rewriting the domain. Recorded as ADR (Vol IV, decision #1).
- **[AI-native]** AI Platform Director wanted AI in the core loop; NIST/GDPR insisted advisory-only. **Resolved:** AI is a lens on the graph, advisory-only, confidence-gated, never mutates truth (RFC-002 P8) — enforced in code (P9), never a truth author.

*Volume I ends. The remaining volumes enumerate the specifics: 500 capabilities (II), 200 risks + 600 failures/decisions (III), the program portfolio + dependency graph (IV), the ≤1-week backlog (V), and the readiness matrix + self-audit (VI).*
