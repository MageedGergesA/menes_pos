# Mezze — Complete Gap Model · VOLUME IV: Program Portfolio & Dependency Graph

*28 programs covering all 85 gap-model areas and all 500 capabilities. P0–P12 are specified in full in `IMPLEMENTATION_ROADMAP.md`; here they are recapped in the portfolio shape and P13–P27 are added to close the remaining surface. Every program: Purpose · Deps · Squads · Epics · Key Features · Acceptance · KPIs · Exit Criteria · Rollback · Audit Evidence. Detailed ≤1-week tasks live in Volume V.*

## Portfolio index

| # | Program | Maturity step | Primary areas closed |
|--|---------|--------------|----------------------|
| P0 | Engineering Foundations | 1 | Testing, CI/CD, IaC, flags, obs-skeleton |
| P1 | Security & Identity Baseline | 1 | AuthN, AuthZ, secrets, rate-limit |
| P2 | Runtime Substrate | 2 | Operating Graph, events, identity, time |
| P3 | Invariant Enforcement | 2 | Business invariants, domain conformance |
| P4 | Multi-Tenancy Control Plane | 3 | Multi-tenancy, isolation, provisioning |
| P5 | Sync/Offline/Consistency | 3 | Sync, offline, consistency, conflict |
| P6 | Financial Core | 4 | Payments, ledger, settlement, tax |
| P7 | Observability/DR/Ops | 4 | Observability, DR, backup, deploy |
| P8 | Platform Services | 5 | Config, search, notification, printing, permission |
| P9 | Data Platform & Analytics | 5 | Analytics, warehouse, data contracts, DQ |
| P10 | Extensibility & Ecosystem | 6 | SDK, marketplace, partner API, ERP, de-monolith |
| P11 | Enterprise Trust & Certifications | 6 | SOC2, ISO, SLA, procurement |
| P12 | Product Breadth & Frontend | 6 | Component library, FSMs, remaining domain |
| **P13** | **AI Platform & Governance** | 5 | AI, model gov, prompt safety, eval |
| **P14** | **Forecasting & Benchmarking (the Moat)** | 5 | Forecasting, benchmarking, financing scoring |
| **P15** | **Financial Crime & Fraud** | 4 | AML/KYC/sanctions, fraud platform |
| **P16** | **Global Fiscalization & Tax** | 4 | Per-country fiscal packs, remittance |
| **P17** | **Payments Expansion** | 4 | Regional methods, wallets, disputes, cash mgmt |
| **P18** | **Inventory, Supply & Procurement** | 6 | Inventory depth, recipes, purchasing, waste |
| **P19** | **Kitchen & Labor Operations** | 6 | 14-state KDS, routing, scheduling, attendance |
| **P20** | **CRM, Loyalty & Reservations** | 6 | Segmentation, tiers, channels, no-show |
| **P21** | **Scale & Cell Architecture** | 3–5 | Cells, sharding, perf at 1M |
| **P22** | **Cost/FinOps & Capacity** | 4 | Cost attribution, capacity, budgets |
| **P23** | **Privacy Engineering & Data Governance** | 6 | GDPR/DSAR/erasure, catalog, lineage, residency |
| **P24** | **Commercial Platform** | 6 | Billing, metering, SLA, contracts |
| **P25** | **Support, Services, Training & Certification** | 6 | Support tooling, PS, CS, training, cert |
| **P26** | **Localization & Accessibility Platform** | 6 | N-language TMS, locale framework, WCAG/VPAT |
| **P27** | **Reference & Master Data Management** | 2–3 | Currencies, countries, MCC, allergens, golden records |

---

## PROGRAMS P0–P12 (recap — full spec in IMPLEMENTATION_ROADMAP.md)

Each retains its full spec in the roadmap doc. Portfolio-shape summary:

- **P0 Foundations** — Deps: none · Squad: Platform-Eng · Exit: CI mandatory, coverage gate, flags live · Audit ev: green pipeline, seeded-bug caught.
- **P1 Security & Identity** — Deps: P0 · Squad: Security · Exit: 0 `auth='none'`, default-deny proven, vault · Audit ev: pen-test no-crit, authz matrix.
- **P2 Runtime Substrate** — Deps: P0 · Squad: Core-Domain · Exit: projections replay-equal, as-of queries · Audit ev: replay==live, 10⁶ ID test.
- **P3 Invariant Enforcement** — Deps: P2 · Squad: Core-Domain · Exit: 74/74 guards+tests · Audit ev: conformance report, fuzz clean.
- **P4 Multi-Tenancy** — Deps: P1,P2 · Squad: Platform · Exit: isolation fuzz 100% denied, ≤90s provision · Audit ev: cross-tenant suite.
- **P5 Sync/Consistency** — Deps: P2,P3 · Squad: Distributed-Systems · Exit: 0 lost/dup in chaos · Audit ev: Jepsen-style green.
- **P6 Financial Core** — Deps: P1,P2,P3 · Squad: Payments+Ledger · Exit: ledger balances, no PAN, tax parity · Audit ev: settlement recon.
- **P7 Observability/DR/Ops** — Deps: P0,P4 · Squad: SRE · Exit: DR game-day within RTO/RPO · Audit ev: restore drill, SLO dashboards.
- **P8 Platform Services** — Deps: P2,P4 · Squad: Services · Exit: 0-code branch, search ≤80ms, critical-notif 100% · Audit ev: per-service tests.
- **P9 Data Platform & Analytics** — Deps: P2,P4,P7 · Squad: Data · Exit: warehouse reconciles to ledger, data contracts in CI · Audit ev: DQ SLOs.
- **P10 Extensibility** — Deps: P1,P4,P8,FE-demonolith · Squad: Platform+DevEx · Exit: sample plugin, sandbox-escape tests · Audit ev: `mezze lint` gate.
- **P11 Enterprise Trust & Certs** — Deps: P1,P4,P6,P7 · Squad: Security+Compliance · Exit: SOC2/ISO controls evidenced · Audit ev: reports.
- **P12 Product Breadth & Frontend** — Deps: P8,P10 · Squad: Product-Eng · Exit: component library published, FSMs conformant · Audit ev: contract tests.

---

## NEW PROGRAMS P13–P27 (full portfolio spec)

### P13 — AI Platform & Governance
- **Purpose.** A provider-agnostic, advisory-only, governed AI layer that turns the graph into decisions without ever becoming truth.
- **Deps.** P2 (substrate), P4 (tenancy/privacy), P9 (data), P23 (privacy).
- **Squads.** AI-Platform, Data, Security.
- **Epics.** Provider abstraction & registry · Inference gateway (permission+cache+context+guardrail) · Prompt-template versioning & injection defense · Hallucination control (grounding/abstain) · Eval harness & golden sets · Drift monitoring · Copilots (advisory) · OCR/translation/recommendation capabilities · AI audit log · Clean-room training governance · EU-AI-Act classification.
- **Key features.** Confidence gating; explanation on every output; HITL for money/stock; PII redaction before inference; per-tenant cost caps; content-safety filters.
- **Acceptance.** AI never mutates truth (conformance test); prompt-injection red-team suite green; below-threshold → abstain (test); eval gates block regressions in CI.
- **KPIs.** Recommendation acceptance rate; forecast MAPE (owned by P14); OCR field accuracy; hallucination rate <target; AI cost/tenant.
- **Exit criteria.** Advisory-only guardrail enforced in code; eval + drift live; ≥2 copilots in pilot.
- **Rollback.** All AI disposable — kill a model/capability with zero truth impact (flag).
- **Audit evidence.** Advisory-only conformance test; red-team report; eval-gate CI logs; AI audit-log samples. Closes areas 42–46, 460.

### P14 — Forecasting & Benchmarking (the Moat)
- **Purpose.** Build the North Star network product: forecasting and privacy-preserving cross-restaurant benchmarking + financing scoring.
- **Deps.** P2, P9, P4, P23 (privacy), P13 (AI serving).
- **Squads.** Data-Science, Data-Platform, Privacy.
- **Epics.** Demand/inventory/labor forecasting · Forecast accuracy tracking (MAPE/backtest) · Peer-set/similarity/cohorting · Privacy-preserving aggregation (k-anonymity/clean-room/DP) · Benchmark products (cost/labor/menu-mix) · Financing-qualification scoring · Supplier/procurement benchmarking · Anomaly detection.
- **Key features.** Re-identification-resistant aggregation; own-position-vs-aggregate exposure only; longitudinal trajectory views.
- **Acceptance.** Re-identification adversarial tests fail to identify any peer; forecast writes no truth (conformance); benchmark exposes only anonymized aggregate + own position.
- **KPIs.** Forecast MAPE; benchmark adoption; financing-decision precision/recall vs outcomes.
- **Exit.** Benchmarking live for a pilot cohort; forecasting drives prep/labor suggestions.
- **Rollback.** Derivations disposable (flag).
- **Audit evidence.** Privacy property tests; MAPE dashboards; RFC-002 P7/P8/§9.6 conformance. Closes areas 40–41; capabilities 411–426.

### P15 — Financial Crime & Fraud
- **Purpose.** AML/KYC/sanctions + operational-fraud controls (refund/void/discount/cash abuse).
- **Deps.** P1, P6, P9.
- **Squads.** Risk, Payments, Data.
- **Epics.** KYC onboarding (vendor) · Sanctions screening (onboard+periodic) · AML transaction monitoring/structuring detection · Fraud rules engine (velocity/anomaly) · ML fraud scoring (later) · Case management + SAR filing · Chargeback/representment.
- **Key features.** Velocity guards on refunds/discounts/voids; device/geo signals; manager-approval escalation.
- **Acceptance.** Sanctions hit blocks onboarding (test); refund-abuse pattern flagged (test); structuring alert fires on crafted sequence.
- **KPIs.** Fraud loss rate; false-positive rate; SAR turnaround; sanctions-screening coverage 100%.
- **Exit.** AML/KYC live for fintech flows; fraud rules in production.
- **Rollback.** Rules flag-gated; observe-mode.
- **Audit evidence.** Screening logs; case-management records; fraud-rule test suite. Closes area 17; capabilities 130, 496.

### P16 — Global Fiscalization & Tax
- **Purpose.** Pluggable per-country fiscal/e-invoicing packs + tax determination + remittance.
- **Deps.** P6 (tax engine), P11.
- **Squads.** Tax-Eng, Compliance (per-region).
- **Epics.** Fiscal-pack framework · ZATCA (KSA) · EU packs (Italy SdI, Spain, Poland, Hungary…) · LATAM (Brazil NF-e, Mexico CFDI) · Egypt ETA hardening · Determination cascade · Exemptions/reverse-charge · Remittance/filing automation · Fiscal-device integration.
- **Key features.** Effective-dated rates; freeze/reverse; per-jurisdiction rounding; real-time authority reporting where mandated.
- **Acceptance.** Each pack passes statutory validation; tax bit-for-bit vs `account.tax`; e-invoice cleared by authority sandbox.
- **KPIs.** Markets certified; filing accuracy; determination latency ≤5ms.
- **Exit.** Framework + 4 markets live.
- **Rollback.** Packs versioned; per-market flag.
- **Audit evidence.** Statutory validation certificates; parity harness. Closes area 66; capabilities 171–200.

### P17 — Payments Expansion
- **Purpose.** Broaden beyond Egypt/Paymob: regional methods, wallets, disputes, cash management, multi-acquirer.
- **Deps.** P6 (payment core), P15 (fraud).
- **Squads.** Payments (regional pods).
- **Epics.** Regional method adapters (mada/Fawry/Benefit/KNET/UPI/PIX…) · Wallets (Apple/Google/regional) · 3DS/SCA · Dispute/chargeback flow · Cash management (float/drops/recon) · Gift/stored-value · House accounts · Pre-auth/incremental · DCC/FX at POS · Least-cost routing · Payout/sub-merchant · Recurring billing.
- **Acceptance.** Each method authorizes/captures/refunds in sandbox with idempotency; dispute evidence submits; cash session reconciles.
- **KPIs.** Auth rate; payment success; dispute win rate; methods per market.
- **Exit.** Top methods live in launch markets.
- **Rollback.** Per-method/per-PSP flag.
- **Audit evidence.** Idempotency tests, no-PAN scan, reconciliation. Closes capabilities 100–140.

### P18 — Inventory, Supply & Procurement
- **Purpose.** True food cost via recipe depletion + purchasing/procurement + waste + valuation.
- **Deps.** P2, P6 (ledger for COGS), P8 (config).
- **Squads.** Inventory-Eng.
- **Epics.** Recipe→ingredient depletion · Movements-primary stock model · Physical counts as adjustments · Waste events · Transfers · Par levels/reorder · Purchase orders/receipt/3-way match · Supplier catalog/price history · Yield/sub-recipes · Batch/lot/expiry (allergen/recall) · Valuation (FIFO/avg) · Central-kitchen production.
- **Acceptance.** Food cost reconciles depletion→ledger; count creates a movement (no overwrite); waste reduces stock + records cause.
- **KPIs.** Food-cost variance; stockout rate; waste %; PO cycle time.
- **Exit.** Depletion + purchasing + waste live.
- **Rollback.** Per-feature flag.
- **Audit evidence.** Cost-reconciliation tests; movement-integrity property tests. Closes area 26; capabilities 321–340.

### P19 — Kitchen & Labor Operations
- **Purpose.** 14-state KDS FSM + routing + hardware + labor scheduling/attendance/payroll.
- **Deps.** P2, P3 (FSM invariants), P8 (config/print), P5 (multi-screen sync).
- **Squads.** Kitchen-Eng, Workforce-Eng.
- **Epics.** 14-state ticket FSM · Deterministic routing · Recall contract · Bump-bar hardware · SLA prediction/aging · Coursing/pacing · Expo aggregation · Multi-screen sync · Allergen propagation (safety) · Labor scheduling/rostering · Time & attendance → payroll · Shift/cash-session.
- **Acceptance.** FSM matches spec (conformance); no lost ticket across failover; allergen flags on every relevant ticket.
- **KPIs.** Ticket-appear latency ≤1s; recall-in-window 100%; labor-cost accuracy.
- **Exit.** 14-state KDS + scheduling live.
- **Rollback.** Per-feature flag; FSM behind flag with parity test.
- **Audit evidence.** FSM conformance; allergen-propagation test. Closes area 27,31; capabilities 341–360.

### P20 — CRM, Loyalty & Reservations
- **Purpose.** Retention engine: segmentation, journeys, loyalty tiers+liability, reservation channels+no-show.
- **Deps.** P2, P6 (liability GL), P20 self, P23 (consent).
- **Squads.** Growth-Eng.
- **Epics.** Customer 360 · Segmentation · Journeys/campaigns · Consent/preference (privacy-linked) · Loyalty tiers/accrual/redemption · Cross-brand loyalty · Loyalty liability accounting · Reservation channels · No-show prediction/deposits · Feedback/reviews/sentiment.
- **Acceptance.** Loyalty liability posts to ledger; consent enforced downstream (marketing suppressed without consent); no-show model evaluated vs actuals.
- **KPIs.** Retention lift; loyalty active rate; no-show reduction.
- **Exit.** Segmentation + tiers + channels live.
- **Rollback.** Per-feature flag.
- **Audit evidence.** Consent-enforcement test; liability reconciliation. Closes areas 28–30; capabilities 361–385.

### P21 — Scale & Cell Architecture
- **Purpose.** Re-architect for 1M restaurants: cells, tenant sharding, read replicas, backpressure, load-tested to peak.
- **Deps.** P4 (tenancy), P7 (ops), P2 (substrate).
- **Squads.** Platform-Scale, SRE.
- **Epics.** Cell architecture + placement · Tenant sharding/routing · Hot-tenant mitigation · Read replicas/read-write split · Backpressure/admission control · Load/soak testing at 1M · Auto-scaling/load shedding · Multi-region traffic mgmt · Thundering-herd/reconnect controls.
- **Acceptance.** 1M-restaurant synthetic load test meets SLOs; single-cell failure bounded blast radius; celebrity-tenant isolated.
- **KPIs.** p99 latency at peak; cell utilization; blast-radius %.
- **Exit.** Cell architecture in prod; peak load test passes.
- **Rollback.** Cell rollout staged; traffic shifting reversible.
- **Audit evidence.** Load-test reports; blast-radius game-day. Closes areas 63–65; capabilities 296–320.

### P22 — Cost/FinOps & Capacity
- **Purpose.** Unit economics, per-tenant cost attribution, capacity planning, budgets/alerts.
- **Deps.** P7 (observability), P4 (tenancy).
- **Squads.** FinOps, SRE.
- **Epics.** Cost attribution (per-tenant/txn) · Unit-economics dashboards · Capacity forecasting · Budget/alert automation · Storage/compute lifecycle optimization · AI/GPU cost governance.
- **Acceptance.** Every tenant has a cost attribution; a budget breach alerts; capacity forecast informs scaling.
- **KPIs.** Cost/transaction; cost/tenant; margin per tenant; forecast accuracy.
- **Exit.** Per-tenant unit economics live.
- **Rollback.** Reporting-only, additive.
- **Audit evidence.** Cost dashboards; capacity model. Closes area 59; capabilities 267, 318.

### P23 — Privacy Engineering & Data Governance
- **Purpose.** GDPR/DSAR/erasure reconciled with immutable audit; catalog/lineage/classification; residency.
- **Deps.** P1, P2 (event PII), P4 (tenancy/residency).
- **Squads.** Privacy-Eng, Data-Governance.
- **Epics.** Consent + lawful-basis store · DSAR (access/portability) · Right-to-erasure (anonymize private, keep skeletal fact) · PII inventory + classification · Data catalog + lineage · Retention + legal hold + e-discovery · Residency enforcement · Sub-processor management · Cookie/tracking consent.
- **Acceptance.** DSAR completes e2e; erasure preserves audit integrity (property test); residency-tagged data never leaves region (test).
- **KPIs.** DSAR SLA; erasure completeness; residency-violation count (0).
- **Exit.** DSAR + erasure + residency live.
- **Rollback.** Additive controls; enforcement flagged.
- **Audit evidence.** DSAR logs; erasure-vs-audit test; residency test. Closes areas 67–68; capabilities 486–495.

### P24 — Commercial Platform
- **Purpose.** Monetize: metered billing, plans/entitlements, invoicing, SLA, contracts, procurement kit.
- **Deps.** P4 (metering), P6 (payments/ledger), P11.
- **Squads.** Commerce-Eng.
- **Epics.** Usage metering · Subscription billing/invoicing · Plan/entitlement enforcement · Dunning/collections · SLA definition + credits · Contract/order management · Enterprise procurement kit (security questionnaire, RFP, DPA) · Tax on SaaS billing.
- **Acceptance.** Billing meters usage accurately (reconciliation test); over-limit tenant read-only (test); SLA breach issues credit.
- **KPIs.** Revenue leakage (0); billing accuracy; churn; time-to-close (procurement).
- **Exit.** Metered billing live; procurement kit published.
- **Rollback.** Billing dual-run before enforcement.
- **Audit evidence.** Billing reconciliation; SLA reports. Closes areas 1,85; capability 500.

### P25 — Support, Professional Services, Training & Certification
- **Purpose.** The human operating system: support tooling, PS onboarding, CS, training, certification.
- **Deps.** P1 (impersonation authz), P7 (diagnostics), P10 (APIs).
- **Squads.** Support-Eng, Enablement.
- **Epics.** Support console (consented impersonation, diagnostics) · Ticketing integration · Onboarding/migration tooling (competitor import) · Customer-success health/playbooks · Training curriculum + LMS · Certification program · Knowledge base.
- **Acceptance.** Support can impersonate with consent+audit; a competitor dataset imports; a user completes certification.
- **KPIs.** Time-to-resolution; onboarding time; certification pass rate; CSAT.
- **Exit.** Support tooling + training + cert live.
- **Rollback.** Tooling additive.
- **Audit evidence.** Impersonation audit logs; migration tests. Closes areas 54,85; capabilities 174–175, 180, 483.

### P26 — Localization & Accessibility Platform
- **Purpose.** Industrialize N-language localization + locale framework + WCAG AA/VPAT.
- **Deps.** P12 (frontend modular), P0.
- **Squads.** i18n-Eng, Accessibility.
- **Epics.** TMS integration + ICU messages · Locale/number/date/currency framework · Non-Arabic RTL (Hebrew, Farsi, Urdu) · Pluralization/gender rules · Translation QA gates · Accessibility audit + VPAT · Screen-reader journeys · High-contrast/reduced-motion conformance.
- **Acceptance.** New language ships via pipeline (no code); a11y AA audit passes with VPAT.
- **KPIs.** Language coverage; a11y conformance %; localization defect rate.
- **Exit.** Pipeline + ≥5 languages + AA/VPAT.
- **Rollback.** Per-locale flag.
- **Audit evidence.** a11y audit report; locale test corpus. Closes areas 37–38; capabilities 498–499.

### P27 — Reference & Master Data Management
- **Purpose.** Authoritative reference data (currencies, countries, MCC, allergens, tax jurisdictions) + golden-record MDM.
- **Deps.** P2 (identity), P4.
- **Squads.** Data-Platform.
- **Epics.** Reference-data service (versioned) · Currency/FX source · Country/region/locale registry · MCC/payment reference · Allergen taxonomy · Golden-record resolution (guest/supplier/customer) · Reference-data governance/change process.
- **Acceptance.** All engines consume reference service (no hardcoded lists); a golden record resolves duplicates.
- **KPIs.** Reference-data freshness; duplicate rate; golden-record coverage.
- **Exit.** Reference service live; MDM resolving.
- **Rollback.** Reference service versioned; consumers pin versions.
- **Audit evidence.** Reference-consumption conformance; dedup tests. Closes capabilities 28–29, 35.

---

## COMPLETE DEPENDENCY GRAPH

```
P0 ───┬─► P1 ──┬─────────────────────────► P4 ─┬─► P7 ─┬─► P21 (Scale)
      │        │                                │       └─► P22 (FinOps)
      │        └─► P6 ◄── P2,P3                  ├─► P8 ─┬─► P10 ─► P12
      │                                          │       └─► P9 ─┬─► P13 (AI)
      ├─► P2 ──┬─► P3 ──┬─► P5                    │              └─► P14 (Moat)
      │        │        └─► P6 (Financial)        ├─► P23 (Privacy) ─► P20
      │        └─► P27 (Ref/MDM)                  │
      │                                           └─► P11 ◄── P6,P7
      └─► (all inherit P0)
P6 ──► P15 (Fraud) ──► P17 (Payments Expansion)
P6 ──► P16 (Fiscalization)
P2,P6,P8 ──► P18 (Inventory) ; P2,P3,P8,P5 ──► P19 (Kitchen/Labor)
P4,P6,P11 ──► P24 (Commercial) ; P1,P7,P10 ──► P25 (Support/Services)
P12 ──► P26 (Localization/A11y)
```

**Critical path (to Enterprise-Ready):** `P0 → P1 → P4 → P6 → P11 → P24`. Financial-crime (P15) and fiscalization (P16) gate *market entry*; privacy (P23) gates *EU/regulated markets*; scale (P21) gates *the 1M ceiling*.

**Parallel streams (independent once deps met):**
- Stream A (Trust): P1 → P4 → P11 → P24 → P25.
- Stream B (Correctness): P2 → P3 → P5.
- Stream C (Money): P6 → {P15, P16, P17}.
- Stream D (Platform): P8 → {P9 → {P13, P14}, P10 → P12 → P26}.
- Stream E (Reliability/Scale): P7 → {P21, P22}.
- Stream F (Domain): P18, P19, P20 (after their engine deps).

**Longest chain:** Stream D's `P0→P2→(P4/P8)→P9→P14` (the moat) and Stream A's `P0→P1→P4→P11→P24` (trust/commercial) co-determine the timeline. P2 and P4 are the two convergence nodes — **staff both from Q1**.

*Volume IV ends. Volume V is the ≤1-week backlog; Volume VI is the readiness matrix + self-audit.*
