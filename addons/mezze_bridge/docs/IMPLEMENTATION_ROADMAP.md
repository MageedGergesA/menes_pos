# Mezze — Master Implementation Roadmap

*Principal Engineer deliverable. Turns the frozen canon (Constitution, RFC-000/001/002) and the EAB audit into running, tested software. No architecture is redesigned. Every program produces code, APIs, and tests, and moves named audit findings from red to green. Runtime maturity: **27% → Enterprise-Ready**, in six dependency-ordered steps.*

Task tags: **[F]** feature · **[T]** technical · **[Q]** test/quality · **[D]** docs · **[O]** ops. Rule: no task > 2 weeks; every task independently shippable behind a flag. Quality bar per deliverable: unit + integration + property + offline + replay + security + performance + migration + conformance tests.

---

## 1 · EXECUTIVE SUMMARY

The architecture is ~95–100%; the runtime is ~27%. The bottleneck is that the canon's guarantees are **documented, not enforced**, and the platform's trust/operations spine **does not exist in code**. This roadmap closes that with **13 programs (P0–P12)** in strict dependency order, grouped into **6 maturity steps**:

| Step | Programs | Runtime | Theme |
|---|---|---|---|
| 1 | P0 Foundations · P1 Security & Identity | 27→**40%** | *Verifiable & trustworthy* |
| 2 | P2 Runtime Substrate · P3 Invariant Enforcement | 40→**55%** | *The asset & correctness exist* |
| 3 | P4 Multi-Tenancy · P5 Sync/Consistency | 55→**70%** | *A real SaaS* |
| 4 | P6 Financial Core · P7 Observability/DR/Ops | 70→**85%** | *Sellable & operable* |
| 5 | P8 Platform Services · P9 Data & Intelligence | 85→**95%** | *Differentiated platform* |
| 6 | P10 Extensibility · P11 Compliance/Enterprise · P12 Product Breadth | 95→**Enterprise-Ready** | *Ecosystem & trust* |

Two principles govern sequencing: (1) **nothing is "done" until a test proves it** — so P0 (test harness + CI) is the literal root of the graph; (2) **you cannot secure or isolate what you cannot identify** — so P1 (identity/auth) precedes multi-tenancy, financial, and everything enterprise. The Operating-Graph substrate (P2) is the second root: it is the substrate every intelligence, benchmark, and audit-trail capability projects from.

**Estimate basis:** a world-class org running ~5 parallel squads. Durations are in team-quarters (Q). Complexity: S/M/L/XL. Total critical path ≈ **6 quarters** to 95%, **~7–8 quarters** to Enterprise-Ready with compliance certifications (which have external calendar dependencies).

---

## 2 · DEPENDENCY GRAPH

```
                          ┌─────────────────────┐
                          │  P0 Foundations     │  (test harness, CI/CD, IaC,
                          │  (ROOT)             │   flag platform, obs skeleton)
                          └─────────┬───────────┘
                 ┌──────────────────┼───────────────────┐
                 ▼                  ▼                    ▼
        ┌────────────────┐ ┌────────────────┐   (all later programs
        │ P1 Security &  │ │ P2 Runtime     │    inherit P0)
        │ Identity       │ │ Substrate      │
        └───┬────────┬───┘ └───┬────────┬───┘
            │        │         │        │
            │        │         ▼        │
            │        │  ┌──────────────┐│
            │        │  │ P3 Invariant ││
            │        │  │ Enforcement  ││
            │        │  └──┬────────┬──┘│
            ▼        ▼     ▼        │   ▼
        ┌────────────────────┐ ┌───┴─────────────┐
        │ P4 Multi-Tenancy   │ │ P5 Sync /       │
        │ Control Plane      │ │ Consistency     │
        └──┬───────┬─────┬───┘ └─────────────────┘
           │       │     │
           ▼       │     ▼
   ┌──────────────┐│ ┌──────────────────┐
   │ P7 Observ/DR ││ │ P8 Platform      │
   │ /Backup/Ops  ││ │ Services         │
   └──────┬───────┘│ └────────┬─────────┘
          │        ▼          │
          │ ┌──────────────┐  │
          │ │ P6 Financial │  │   (P6 needs P1+P2+P3)
          │ │ Core         │  │
          │ └──────┬───────┘  │
          ▼        ▼          ▼
   ┌──────────────────┐ ┌───────────────────┐
   │ P9 Data &        │ │ P10 Extensibility │  (needs P1+P4+P8 +
   │ Intelligence     │ │ & Ecosystem       │   frontend de-monolith)
   └──────────────────┘ └─────────┬─────────┘
   ┌────────────────────────────┐ ▼
   │ P11 Compliance/Enterprise  │ ┌──────────────────┐
   │ (needs P1+P4+P6+P7)        │ │ P12 Product      │
   └────────────────────────────┘ │ Breadth + FE     │
                                   └──────────────────┘
```

**Edges (strict):** P1←P0 · P2←P0 · P3←P2 · P4←P1,P2 · P5←P2,P3 · P6←P1,P2,P3 · P7←P0,P4 · P8←P2,P4 · P9←P2,P4,P7 · P10←P1,P4,P8 · P11←P1,P4,P6,P7 · P12←P8,P10.

---

## 3 · ENGINEERING PROGRAMS

> Each program lists: Purpose · Business value · Technical value · Dependencies · Deliverables · Acceptance criteria · Definition of Done · Test strategy · Migration · Operational readiness · Rollback · Security · Performance · Audit improvement · RFC principles enforced · Epics & tasks.

---

### PROGRAM 0 — Engineering Foundations
**Purpose.** Make "done" objectively verifiable. Nothing later can be trusted without a test harness, CI/CD, and deploy/observe primitives.
**Business value.** Every subsequent claim becomes provable; cuts regression cost; unblocks enterprise diligence ("show me your pipeline").
**Technical value.** The measurement substrate for the whole roadmap; every DoD hooks into it.
**Dependencies.** None (root).
**Deliverables.**
- Test harness for the `mezze_bridge` addon: Odoo test runner wired for unit + integration (`TransactionCase`/`HttpCase`), a JS test runner for `pos.html` logic, and a **property-testing** library integrated (money/state invariants).
- CI pipeline: lint → unit → integration → build → contract tests → coverage gate → security scan (SAST + dependency/SBOM) → artifact.
- CD: environment promotion (dev→staging→prod), **Infrastructure-as-Code** for the Odoo + reverse-proxy + worker topology, one-command ephemeral env.
- **Feature-flag service** (server-authoritative, replaces manual `?appearance=` pattern): typed flags, per-tenant/per-branch targeting, kill-switch.
- Observability **skeleton**: structured logging, a metrics endpoint, request/trace IDs threaded through every controller.
- Contract-test framework for the HTTP API (request/response schemas versioned).
**Acceptance criteria.** CI green on every PR; coverage gate ≥70% on new code; a seeded property test catches an injected money-rounding bug; a flag flip changes behavior in <5s without deploy; `terraform plan/apply` (or equivalent IaC) stands up a full env from zero.
**Definition of Done.** No merge path without passing pipeline; flags documented; every controller emits a trace ID; runbook for the pipeline exists.
**Test strategy.** Meta: tests that assert the harness itself detects seeded faults (mutation testing on a sample module).
**Migration.** Additive; no runtime data change. Wrap existing routes with trace-ID middleware.
**Operational readiness.** Pipeline dashboards; flag audit log; build provenance.
**Rollback.** Pipeline stages are gates, not mutations; flags default-off.
**Security.** SAST + SBOM + dependency scanning from day one; secret-scanning in CI.
**Performance.** Middleware overhead budget <2ms/request; CI < 15 min.
**Audit improvement.** Testing 3→45 · Deployment 15→55 · Release Eng 20→55 · Observability 5→25 · DX 10→30. **+3–4% runtime.**
**RFC enforced.** RFC-000 laws on verification/reversibility become executable gates.

**Epics & tasks (≤2wk each):**
- E0.1 Test harness — [T] Odoo unit+integration runner in CI · [T] JS logic test runner for `pos.html` · [T] integrate property-test lib · [Q] seed 20 property tests for calc order · [D] "How to test" guide.
- E0.2 CI/CD — [T] lint+unit+integration stages · [T] coverage gate · [T] SAST+SBOM+dep-scan stage · [T] contract-test stage · [O] staging/prod promotion.
- E0.3 IaC — [T] codify Odoo+proxy+worker topology · [O] ephemeral env script · [Q] IaC apply/destroy test.
- E0.4 Flag service — [F] typed flag store + eval API · [F] targeting (tenant/branch) · [Q] flag-eval property tests · [D] flag catalog.
- E0.5 Obs skeleton — [T] structured logging + trace-ID middleware · [T] metrics endpoint · [Q] trace-propagation integration test.

---

### PROGRAM 1 — Security & Identity Baseline
**Purpose.** Replace the single shared static token / `auth='none'` model with real per-principal authentication and authorization. The audit's #1 blocker.
**Business value.** Passes the first gate of any enterprise/PSP security review; enables SSO deals; prevents fleet-wide compromise.
**Technical value.** Identity is the precondition for tenancy isolation (P4), financial authorization (P6), and audit attribution (P2/P3).
**Dependencies.** P0.
**Deliverables.**
- **Principal model**: device, user, service — each with its own credential; short-lived signed access tokens + refresh; rotation + revocation; expiry.
- **Auth service**: device enrollment, user login (password+PIN policies), token issue/verify; pluggable **SSO (OIDC/SAML)** and **MFA** interfaces.
- **Authorization engine** (the Permission Service, first cut): default-deny; roles × permissions × scopes (tenant/branch/terminal/workspace/field); `can()` evaluated at call time; elevation with TTL + approval workflow; every check audited.
- Replace every `auth='none'` data route with `auth` middleware validating a **scoped, expiring, per-principal token**; aggregator webhooks keep HMAC but gain replay protection + rotation.
- **Secrets vault** integration (out of `ir.config_parameter`); API **rate limiting** + gateway policy; security headers/CSP audit for the frontends.
**Acceptance criteria.** Zero routes with `auth='none'` except explicitly public (health); a stolen device token is useless after revocation (test); a cashier cannot call a manager route (test); rate limiter sheds load at threshold (test); pen-test of auth surface with no criticals.
**Definition of Done.** Shared static token removed from code paths; `can()` default-deny proven; elevation auto-expires; secrets in vault; CSP enforced.
**Test strategy.** Security tests (authz matrix, token replay, privilege escalation attempts, rate-limit), property tests on `can()` (deny-by-default holds for all undefined tuples), integration tests for SSO/MFA stubs.
**Migration.** Dual-run: accept legacy token behind a flag for N releases while devices re-enroll; telemetry on legacy-token usage → flip off at zero.
**Operational readiness.** Auth dashboards (login failures, token issuance, elevation events); revocation runbook.
**Rollback.** Flag re-enables legacy token for a bounded window; authz engine falls back to deny (safe).
**Security.** This *is* the security program; adds threat model + pen-test.
**Performance.** `can()` cached ≤2ms; token verify ≤5ms.
**Audit improvement.** Authentication 18→75 · Authorization 28→70 · Permissions 32→70 · Audit 55→65 (attribution) · Enterprise 12→30. **+5–6% runtime.**
**RFC enforced.** RFC-001/002 **Authority** and **Trust** principles (who may assert facts) become enforced; RFC-000 least-privilege law executable.

**Epics & tasks:**
- E1.1 Principals & tokens — [F] principal model · [F] token issue/verify/rotate/revoke · [Q] token lifecycle security tests.
- E1.2 Auth service — [F] device enrollment · [F] user login + PIN policy · [T] OIDC adapter · [T] SAML adapter · [T] MFA interface · [Q] SSO/MFA integration tests.
- E1.3 Authorization engine — [F] role/permission/scope model · [F] `can()` default-deny · [F] elevation+approval w/ TTL · [Q] authz-matrix + escalation security tests · [D] role catalog.
- E1.4 Route hardening — [T] auth middleware on all data routes · [T] webhook replay-protection · [Q] "no auth=none" conformance test.
- E1.5 Secrets & edge — [T] vault integration · [T] rate limiter/gateway · [T] CSP/security-headers · [Q] rate-limit + header tests · [O] revocation runbook · [O] threat model + pen-test.

---

### PROGRAM 2 — Runtime Substrate (RFC-002 executable)
**Purpose.** Make the Operating Graph real: an event-sourced spine that captures truth losslessly and projects every view. The company's asset becomes a running system.
**Business value.** Without it, benchmarking/forecasting/analytics/audit-history (the moat) have no substrate. This is the difference between "the graph is the company" as slogan vs. fact.
**Technical value.** Single source of truth for state; projections replace ad-hoc reads; replay enables rebuilds and debugging.
**Dependencies.** P0.
**Deliverables.**
- **Event store**: append-only, immutable, ordered per aggregate; each event carries id, aggregate, type, version, event-time, observation-time, business-day, actor, tenant, causation/correlation, idempotency key (RFC-001 §5/§8/§9, RFC-002 P1/P4).
- **Event schema registry** + event versioning (upcasters); backward-compatible evolution.
- **Projection engine**: deterministic, disposable read-models rebuilt from the log (RFC-002 P6). First projections: current-order, KDS, cash-session, day-book.
- **Replay engine**: rebuild any projection or any past state at any point in time (RFC-002 P1.7/§5.4); crash-resumable cursors.
- **Identity service**: global edge-born IDs, reversible **merge/unmerge** with audit (RFC-002 §5.3), conflict-by-rule hooks.
- **Conformance tests**: assert code state == ontology; assert projections are pure functions of the log.
**Acceptance criteria.** Any projection is byte-reproducible from the log (replay test); "as-of" query returns correct historical state for 100 sampled timestamps; an offline-born event joins without collision (property test at 10^6 ID scale); a merge is fully reversible with history preserved.
**Definition of Done.** All new writes go through events; existing `mezze.sync.outbox` becomes a producer into the store; projections serve reads; replay rebuilds prod-shaped data in CI.
**Test strategy.** Replay tests (rebuild == live), property tests (ID uniqueness, ordering, idempotent apply), offline tests (edge-born events), conformance tests (ontology↔state), migration tests (backfill).
**Migration.** Backfill: derive an initial event log from current Odoo state (a one-time "genesis" projection); dual-write during transition; cut reads to projections behind a flag.
**Operational readiness.** Log lag metrics, projection freshness, replay tooling, dead-projection alarms.
**Rollback.** Projections disposable — fall back to direct Odoo reads via flag; event store is additive (never destructive), so rollback is read-path only.
**Security.** Events immutable + signed; actor/tenant on every event; PII policy for event payloads (redaction hooks feed P11).
**Performance.** Append ≤10ms; projection apply ≤16ms; replay ≥1000 events/s; as-of query ≤120ms.
**Audit improvement.** Operating Graph 10→65 · Events 40→80 · Identity 45→75 · Time 30→60 · Domain Model 55→75. **+6–7% runtime.**
**RFC enforced.** RFC-002 P1 (node/edge/history/identity/time), P4 (event→graph), P6 (projections disposable) — all become executable and tested.

**Epics & tasks:**
- E2.1 Event store — [F] append/read API (per-aggregate order) · [F] event envelope (times/actor/tenant/idempotency) · [Q] ordering+idempotency property tests · [Q] immutability test.
- E2.2 Schema registry — [F] event schema + version + upcaster · [Q] schema-evolution migration tests · [D] event catalog (from RFC-001 §5).
- E2.3 Projection engine — [F] projection runtime + cursors · [F] current-order/KDS/cash/day-book projections · [Q] projection-purity + replay-equivalence tests.
- E2.4 Replay engine — [F] rebuild-projection · [F] as-of state query · [Q] replay==live test · [Q] crash-resume test.
- E2.5 Identity service — [F] edge-born ID minting · [F] reversible merge/unmerge + audit · [Q] 10^6 collision property test · [Q] merge-reversibility test.
- E2.6 Migration — [T] genesis backfill from Odoo state · [T] dual-write bridge from `sync.outbox` · [Q] backfill conformance test.

---

### PROGRAM 3 — Business Invariant Enforcement
**Purpose.** Turn RFC-001's 74 invariants and RFC-002's laws from prose into executable guards with property tests. Correctness stops being aspirational.
**Business value.** Prevents corrupt money/state reaching production (unpaid-paid, negative stock, tax-on-pre-discount) — the class of bug that ends financial-audit certification.
**Technical value.** A single enforcement layer every command passes through; invariants become regression-proof.
**Dependencies.** P2 (events/state), P0.
**Deliverables.**
- **Invariant registry**: each of the 74 invariants encoded as a named, testable predicate over aggregate state/events.
- **Command guard layer**: every state-changing command validated against applicable invariants before commit; violation → typed rejection + audit event (never silent).
- **Property-test suite**: generative tests that attempt to violate each invariant across random histories.
- **Conformance report**: CI artifact listing invariant → guard → test coverage (must be 74/74).
**Acceptance criteria.** 74/74 invariants have a guard and ≥1 property test; a fuzzer cannot drive the system into any forbidden state in N million generated operations; every rejection emits an audit event with the invariant id.
**Definition of Done.** No command path bypasses the guard layer; conformance report is green in CI; forbidden transitions from RFC-001 (Draft→Paid, Closed→Open, refund>captured…) are provably unreachable.
**Test strategy.** Property/fuzz tests per invariant; replay tests (historical events never violate); integration tests (guard rejects at API boundary); migration tests (backfilled events satisfy invariants or are quarantined).
**Migration.** Run guards in "observe" mode over backfilled history first; quarantine violators to a review queue; then enforce.
**Operational readiness.** Invariant-violation dashboard (should be ~0); quarantine review tooling.
**Rollback.** Guards flag-gated per invariant-family; observe-mode fallback.
**Security.** Guards are an integrity control; violations are security-relevant events.
**Performance.** Guard evaluation ≤5ms/command.
**Audit improvement.** Business Invariants 30→85 · Domain Model 75→85 · Financial Ledger 30→45 (integrity) · Distributed Consistency 25→40. **+4–5% runtime.**
**RFC enforced.** RFC-001 all 74 invariants; RFC-002 P1.4 (truth durable) — enforced, not documented.

**Epics & tasks:**
- E3.1 Registry — [F] invariant predicate framework · [F] encode invariants 1–37 · [F] encode invariants 38–74 · [D] invariant→guard map.
- E3.2 Guard layer — [F] command interceptor · [F] typed rejection + audit emit · [Q] boundary rejection integration tests.
- E3.3 Property suite — [Q] generative tests invariants 1–37 · [Q] generative tests 38–74 · [Q] forbidden-transition unreachability tests.
- E3.4 Conformance — [T] CI conformance report (74/74) · [T] observe-mode + quarantine · [O] violation dashboard.

---

### PROGRAM 4 — Multi-Tenancy Control Plane
**Purpose.** Convert multi-branch-on-Odoo into a true multi-tenant SaaS with a control plane, isolation, and lifecycle.
**Business value.** Unlocks the SaaS business model, self-serve onboarding, and per-tenant billing; without it "SaaS platform" is false.
**Technical value.** Tenant becomes a first-class isolation boundary across auth, data, cache, files, jobs, search, events.
**Dependencies.** P1 (identity), P2 (substrate), P0.
**Deliverables.**
- **Tenant model + lifecycle** (Prospect→Trial→Provisioning→Active⇄Suspended→Read-only→Archived→Deleted) with control-plane API (Provision/Suspend/Restore/Delete/Clone/Export/Import/Upgrade/Downgrade/Health).
- **Provisioning saga**: idempotent, compensatable steps; no partial tenants; target ≤90s.
- **Isolation enforcement**: tenant claim in every token (P1), tenant on every event (P2), tenant-scoped data access, namespaced cache/files/jobs; middleware hard-denies missing/mismatched tenant + alerts.
- **Cross-tenant leakage test suite** (the make-or-break).
- **Resource quotas / noisy-neighbor** controls; entitlement/feature-flag resolution per tenant (via P0 flag service).
**Acceptance criteria.** Provision a working tenant in ≤90s automated; a deliberately crafted cross-tenant request is denied and alerted in 100% of a fuzzed corpus; a suspended tenant blocks writes but preserves data; a saga failure leaves **zero** residue.
**Definition of Done.** Every data path is tenant-scoped and tested; control-plane API covered; quotas enforced; leakage suite green.
**Test strategy.** Isolation/security tests (cross-tenant fuzz), saga property tests (idempotent+compensatable under injected failures), performance tests (provisioning SLA), migration tests (existing branches → tenants).
**Migration.** Map current companies/branches onto the tenant hierarchy; backfill tenant id onto historical events/records; verify isolation before cutover.
**Operational readiness.** Control-plane dashboards, tenant health, quota alerts, provisioning traces.
**Rollback.** Control-plane ops reversible where marked; provisioning saga auto-compensates; isolation defaults to deny.
**Security.** Tenant isolation is the top multi-tenant security control; add per-tenant audit partitioning.
**Performance.** Isolation overhead <5%; provisioning <90s; config propagation ≤1s.
**Audit improvement.** Multi-tenancy 18→80 · Data Governance 10→35 · Platform Readiness 20→50 · Commercial 15→35 · Enterprise 30→45. **+6–7% runtime.**
**RFC enforced.** RFC-002 P1.11/§9 (authority bounded by ownership; privacy boundary) enforced at the tenant edge.

**Epics & tasks:**
- E4.1 Lifecycle — [F] tenant model + 10 states · [F] control-plane API (10 ops) · [Q] lifecycle transition tests.
- E4.2 Provisioning saga — [F] saga runtime (idempotent/compensatable) · [F] 6 provisioning steps · [Q] failure-injection saga tests · [Q] ≤90s perf test.
- E4.3 Isolation — [T] tenant claim end-to-end (token→event→data) · [T] cache/file/job namespacing · [Q] cross-tenant fuzz suite · [O] mismatch alerting.
- E4.4 Quotas/entitlements — [F] per-tenant quotas · [F] entitlement resolution · [Q] noisy-neighbor load test.
- E4.5 Migration — [T] company/branch→tenant mapping · [T] backfill tenant id · [Q] isolation-before-cutover test.

---

### PROGRAM 5 — Sync, Offline & Distributed Consistency
**Purpose.** Harden the strongest existing area (exactly-once sync) into a proven distributed system: realtime transport, formal conflict resolution, convergence guarantees.
**Business value.** Offline-first at 1M-restaurant / multi-branch scale without data loss or double-charges — the operational trust of the product.
**Technical value.** Closes the consistency proofs the audit flagged as claimed-not-modeled.
**Dependencies.** P2 (event substrate), P3 (invariants), P0.
**Deliverables.**
- **Realtime transport** for fan-out (branch↔cloud, terminal↔terminal) with backpressure.
- **Conflict engine**: per-field resolution by version/clock, additive line-merge, same-field clash → review queue + human-resolution UX; duplicate collapse by idempotency key; server-truth for stock.
- **Convergence + exactly-once proofs**: property tests under adversarial ordering/duplication/partition.
- Encrypted, power-loss-durable local store validated on target terminal hardware; card-offline risk policy.
**Acceptance criteria.** Zero lost/duplicated orders across a chaos suite (partition, dup, reorder, crash); convergence ≤5s post-reconnect at branch scale; a power-cut mid-write loses nothing (hardware test); same-field conflicts always reach review, never silent last-writer.
**Definition of Done.** Conflict engine wired through the command/guard layer; realtime transport live behind flag; chaos suite green in CI.
**Test strategy.** Offline tests, replay tests, property/chaos tests (Jepsen-style ordering/partition), hardware durability tests, security tests (signed ops).
**Migration.** Layer conflict engine over the existing outbox/applied-ledger; shadow-run against production event stream before enforcing.
**Operational readiness.** Sync lag, conflict rate, dead-letter, convergence dashboards; conflict-review tooling.
**Rollback.** Realtime transport flag-off → polling fallback; conflict engine observe-mode.
**Security.** Ops signed/checksummed; no PAN cached; tenant-scoped channels.
**Performance.** Replay ≥100 events/s; convergence ≤5s; queue write ≤10ms.
**Audit improvement.** Sync 70→88 · Offline 65→85 · Distributed Consistency 25→65 · Conflict Resolution 30→70. **+4–5% runtime.**
**RFC enforced.** RFC-002 P1.8/§5 (identity born at edge, conflict-by-rule, merge) and RFC-001 offline/idempotency invariants.

**Epics & tasks:**
- E5.1 Transport — [F] realtime channel + backpressure · [Q] fan-out load test · [O] channel dashboards.
- E5.2 Conflict engine — [F] per-field resolver · [F] review queue + resolution UX · [F] duplicate-collapse · [Q] conflict property tests.
- E5.3 Consistency proofs — [Q] adversarial ordering/partition chaos suite · [Q] exactly-once property tests · [Q] convergence SLA test.
- E5.4 Durable edge — [T] encrypted local store · [Q] power-loss hardware test · [F] card-offline policy · [Q] offline replay tests.

---

### PROGRAM 6 — Financial Core
**Purpose.** Make money provably correct: attested ledger, PSP-agnostic payments with PCI scope, settlement reconciliation, determination-grade tax.
**Business value.** Prerequisite to process cards at scale, pass financial audit, and pursue fintech/lending; unlocks non-Egypt markets.
**Technical value.** Payments/tax/discount become engines behind the command/guard layer, mapped to Odoo accounting but attested independently.
**Dependencies.** P1 (auth), P2 (events), P3 (invariants).
**Deliverables.**
- **Immutable ledger projection** from events with double-entry attestation; fiscal-close controls; multi-currency + FX.
- **PSP-agnostic payment engine** (10-state FSM): provider abstraction, idempotency keys, 3DS/SCA, tokenization vault (no PAN in Mezze), void/refund via reversing entries; multi-PSP routing + fallback.
- **Settlement/reconciliation engine**: match captures to processor settlement files; fee/interchange accounting; payout; dispute/chargeback flow.
- **Tax determination engine**: jurisdiction cascade, inclusive/compound, discount-before-tax, freeze/reverse; per-jurisdiction rule packs (framework + first markets); parity reconciled bit-for-bit with `account.tax`.
**Acceptance criteria.** Ledger balances to zero across a generated year of activity (property test); no PAN present anywhere in storage/logs (security scan); a processor settlement file reconciles with 100% line attribution or flags exceptions; refund posts a reversing entry and never edits a closed order; tax matches `account.tax` bit-for-bit on a 10k-line corpus.
**Definition of Done.** Payments run through the provider abstraction with idempotency proven vs a gateway simulator; settlement recon job green; tax packs for launch markets pass parity; PCI scope documented.
**Test strategy.** Property tests (ledger balance, tax rounding/compound, no-double-capture), integration tests vs gateway/settlement simulators, security tests (PAN absence, key handling), migration tests (historical money → ledger), replay tests (money events reproduce balances).
**Migration.** Rebuild the ledger from the event log; reconcile against Odoo's `account.move` as the parity oracle; run parallel for a fiscal period.
**Operational readiness.** Reconciliation dashboards, exception queues, chargeback SLA tracking, close-cycle checklist.
**Rollback.** Provider abstraction falls back per-PSP; ledger projection disposable/rebuildable; tax packs versioned.
**Security.** PCI-DSS scope + tokenization vault; keys in vault (P1); PAN/CVV never logged.
**Performance.** Authorize (excl. provider) ≤50ms; tax determine+calc ≤5ms; reconciliation batch within EOD window.
**Audit improvement.** Payments 25→70 · Settlement 10→60 · Financial Ledger 30→75 · Tax 30→70 · Compliance 10→30 (PCI scope). **+6–7% runtime.**
**RFC enforced.** RFC-001 money invariants (paid-can't-unpay, payment↔order, discount-before-tax) as ledger-level guarantees.

**Epics & tasks:**
- E6.1 Ledger — [F] double-entry projection · [F] multi-currency+FX · [F] fiscal-close controls · [Q] balance property tests.
- E6.2 Payment engine — [F] provider abstraction + 10-state FSM · [F] idempotency + tokenization vault · [T] 3DS/SCA · [Q] no-double-capture + PAN-absence tests.
- E6.3 Settlement — [F] recon vs settlement files · [F] fee/interchange accounting · [F] dispute/chargeback flow · [Q] reconciliation property tests.
- E6.4 Tax engine — [F] determination cascade · [F] rule-pack framework + 2 markets · [Q] `account.tax` parity corpus · [D] jurisdiction pack authoring guide.

---

### PROGRAM 7 — Observability, DR, Backup & Operations
**Purpose.** Make the platform operable for 20 years: see everything, recover from anything, prove it.
**Business value.** SLAs become possible; enterprise diligence passes; incidents shrink from unbounded to measured.
**Technical value.** Turns the P0 skeleton into a full SRE stack; per-tenant backup/DR built on P4 boundaries.
**Dependencies.** P0, P4 (tenancy for per-tenant backup/isolation).
**Deliverables.**
- Full **observability**: metrics, distributed tracing, structured logs, dashboards, SLOs + error budgets, alerting.
- **Backup**: per-tenant, encrypted, point-in-time; scheduled **restore drills** (RPO ≤5min / RTO ≤30min).
- **Disaster recovery**: multi-region strategy, tested failover, runbooks.
- **Incident management**: SEV levels, on-call, escalation, postmortems, status page.
- **Capacity/perf**: load-test harness, capacity model, perf-regression gates in CI.
**Acceptance criteria.** A killed region fails over within RTO with data loss within RPO (game-day evidence); a single-tenant PITR restore succeeds and is auto-verified; SLO breach fires an alert to on-call; a perf regression blocks a PR.
**Definition of Done.** Golden-signal dashboards per service+tenant; DR runbook exercised; backup/restore automated + verified; status page live.
**Test strategy.** Chaos/game-day tests, restore-drill tests, load/soak tests, alerting tests (synthetic breach), migration tests (backup schema evolution).
**Migration.** Instrument existing services incrementally; backfill dashboards; first DR drill in staging then prod.
**Operational readiness.** This program *is* operational readiness.
**Rollback.** Observability additive; DR failover reversible (fail-back procedure).
**Security.** Logs PII-scrubbed; backup encryption + access control; audit of restores.
**Performance.** Tracing overhead <3%; alert latency <1min.
**Audit improvement.** Observability 25→80 · DR 10→75 · Backup 15→80 · Scalability 10→40 · Operational Playbooks 40→80 · Performance 25→60. **+6–7% runtime.**
**RFC enforced.** RFC-000 operability/reliability laws (graph integrity = losslessness) become measured guarantees.

**Epics & tasks:**
- E7.1 Observability — [T] metrics+traces+logs pipeline · [T] per-service/tenant dashboards · [F] SLOs+error budgets · [O] alerting rules.
- E7.2 Backup/DR — [F] per-tenant PITR backup · [O] automated restore drill · [O] multi-region failover + fail-back · [Q] game-day chaos tests.
- E7.3 Incident — [O] SEV process+on-call+escalation · [O] status page · [D] incident/postmortem templates.
- E7.4 Capacity/perf — [T] load-test harness · [Q] perf-regression CI gate · [D] capacity model.

---

### PROGRAM 8 — Platform Services
**Purpose.** Build the headless services the export specs prescribe: Config cascade, full Permission Service, Search, Notification, durable Printing.
**Business value.** Operational depth restaurants feel daily; parity-plus vs Toast/Foodics on config/search/notifications/printing reliability.
**Technical value.** Extracts logic into reusable, tenant-scoped services on the substrate — the seams the SDK (P10) will expose.
**Dependencies.** P2 (substrate), P4 (tenancy). (Permission Service extends P1.)
**Deliverables.**
- **Configuration cascade engine** (8–9 level, LOCK keys, versioned publish/rollback, templates, ≤1s propagation).
- **Permission Service** completion (policy engine, 10 scopes, ABAC-ready) building on P1.
- **Search Service** (multi-provider, EN/AR normalization pipeline, deterministic ranking, offline index, permission-filtered).
- **Notification Service** (13 categories, 6 priorities, escalation ladder, inbox, dedup, tenant-scoped channels).
- **Printing Service** (durable priority queue, DLQ, failover, intent-based routing, governed reprints) over the existing ESC/POS layer.
**Acceptance criteria.** New branch stands up by config only (0 code); config change propagates ≤1s and locked keys can't be overridden (test); search returns deterministic ranked results ≤80ms@10k with Arabic normalization parity (native-reviewer corpus); a critical notification is delivered+acked or escalated 100% (test); a kitchen ticket is never lost across printer failover (chaos test).
**Definition of Done.** Each service tenant-scoped, event-driven, flag-gated, with its own test pyramid; frontends consume services instead of inline logic.
**Test strategy.** Per-service unit/integration/property tests; search relevance corpus; notification escalation determinism tests; printing DLQ/failover chaos tests; config rollback migration tests.
**Migration.** Strangler pattern: route reads/writes to services behind flags; retire inline implementations once parity proven.
**Operational readiness.** Per-service dashboards, DLQ monitors, config-propagation metrics.
**Rollback.** Each service flag-gated with inline fallback.
**Security.** All services enforce P1 authz + P4 tenancy; search/notification permission-filter before return.
**Performance.** Config propagate ≤1s; search ≤80ms@10k; notify <200ms; print enqueue <20ms.
**Audit improvement.** Configuration 30→80 · Permissions 70→85 · Search 25→80 · Notifications 30→80 · Printing 50→80. **+5–6% runtime.**
**RFC enforced.** RFC-002 P6 projections (services are projection-backed); RFC-001 config/authority ownership.

**Epics & tasks:**
- E8.1 Config engine — [F] cascade fold + LOCK · [F] versioned publish/rollback + templates · [Q] deterministic-resolution + propagation tests.
- E8.2 Permission Service — [F] policy engine + 10 scopes · [F] ABAC hooks · [Q] policy property tests.
- E8.3 Search — [F] provider framework + pipeline · [F] AR/EN normalization · [F] deterministic ranking + offline index · [Q] relevance + latency + isolation tests.
- E8.4 Notification — [F] categories/priorities/channels · [F] escalation ladder + inbox + dedup · [Q] escalation determinism + no-leak tests.
- E8.5 Printing — [F] durable queue + DLQ + failover · [F] intent routing + governed reprint · [Q] failover chaos + no-duplicate tests.

---

### PROGRAM 9 — Data & Intelligence
**Purpose.** Build the North Star product: analytics warehouse, forecasting, and cross-restaurant benchmarking — plus the advisory AI platform — all projected from the substrate.
**Business value.** The differentiator no competitor can copy without the graph; foundation for financing/benchmarking revenue.
**Technical value.** Turns accumulated events into decisions while honoring the truth/derivation boundary (RFC-002 P8).
**Dependencies.** P2 (event history), P4 (tenancy/privacy), P7 (ops).
**Deliverables.**
- **Analytics platform**: warehouse fed by projections/CDC, semantic metrics layer, scheduled + self-serve reporting.
- **Forecasting engine**: demand/inventory/labor; retained with horizon; evaluated against actuals (RFC-002 §3.6).
- **Benchmarking engine**: cross-restaurant, privacy-preserving (data-clean-room / aggregation with k-anonymity), exposing own-position + anonymized aggregate only (RFC-002 §9.6).
- **AI platform**: provider-agnostic, advisory-only, confidence-gated, explainable; model registry + eval harness + drift monitoring; copilots (advisory).
**Acceptance criteria.** A benchmark never exposes an identifiable peer's particulars (privacy property test on adversarial queries); a forecast writes nothing into the operational record (conformance test); AI outputs are always marked derived + carry confidence (test); warehouse figures reconcile to the ledger.
**Definition of Done.** Derivations are demonstrably disposable and re-derivable; truth/derivation boundary enforced in code; benchmarking live for a pilot cohort.
**Test strategy.** Privacy property tests (re-identification attempts fail), conformance tests (derivation never becomes truth), reconciliation tests (analytics↔ledger), model eval/drift tests.
**Migration.** Backfill warehouse from the event log; forecasts/benchmarks start accumulating from genesis.
**Operational readiness.** Data-freshness SLOs, model performance dashboards, drift alerts.
**Rollback.** All derivations disposable — kill a model/benchmark with zero truth impact.
**Security.** Tenant isolation + PII minimization in the clean room; no cross-tenant particulars ever leave aggregation.
**Performance.** Interactive reco <300ms cached; benchmark refresh within batch window.
**Audit improvement.** Analytics 22→75 · Forecasting 5→65 · Benchmarking 2→65 · AI 10→60 · Decision Engine 0→40. **+5–6% runtime.**
**RFC enforced.** RFC-002 P7/P8/§9.6 (canonical queries, intelligence-never-becomes-truth, privacy boundary) enforced in code.

**Epics & tasks:**
- E9.1 Warehouse — [T] CDC/projection feed · [F] semantic metrics layer · [F] reporting · [Q] analytics↔ledger reconciliation tests.
- E9.2 Forecasting — [F] demand/inventory/labor models · [F] horizon retention + actual-evaluation · [Q] never-writes-truth conformance test.
- E9.3 Benchmarking — [F] privacy-preserving aggregation (k-anonymity/clean-room) · [F] own-position vs aggregate exposure · [Q] re-identification adversarial tests.
- E9.4 AI platform — [F] provider abstraction + registry · [F] confidence gate + explanation · [F] copilots (advisory) · [Q] eval + drift + advisory-only tests.

---

### PROGRAM 10 — Extensibility & Ecosystem
**Purpose.** Break the frontend monolith into a shell + modules, expose the Platform SDK and extension points, and open partner/ERP/marketplace surfaces.
**Business value.** Turns a product into a platform (third-party ecosystem); partner/ERP integrations; marketplace revenue.
**Technical value.** Formalizes the seams built in P8 into governed extension points; de-risks the 5k-line `pos.html`.
**Dependencies.** P1 (auth), P4 (tenancy), P8 (services). Plus frontend modularization.
**Deliverables.**
- **Frontend de-monolith**: `pos.html` → application shell + independently-loadable workspace modules (behavior byte-preserved; presentation from Experience 3.0 retained).
- **Platform SDK**: plugin manifest, 11-state plugin lifecycle, **21 extension points**, command bus, 8-layer settings, sandboxing.
- **Marketplace**: signed bundles, static-scan + conformance verification, semver-gated staged rollout, entitlements/billing.
- **Public partner API**: versioned, documented, sandboxed, OAuth, rate-limited; developer portal + CLI.
- **ERP connector framework**: SAP/Oracle/NetSuite/QuickBooks adapters + standard export.
**Acceptance criteria.** A sample plugin installs, activates, and extends a workspace without touching core (test); a plugin cannot modify core files or bypass permissions (security test); `mezze lint` blocks a non-conformant bundle in CI; a partner integrates via the public API in a sandbox using only published docs.
**Definition of Done.** Shell+modules shipped behind flag with behavior parity; SDK versioned with minSdk enforcement; marketplace review pipeline live; ≥1 ERP connector in production.
**Test strategy.** Conformance tests (extension-point contracts), security tests (plugin sandbox escape attempts), integration tests (sample plugins), contract tests (partner API), migration tests (monolith→modules parity).
**Migration.** Strangler on the frontend: extract one workspace module per release behind a flag, parity-tested against the monolith; retire the monolith last.
**Operational readiness.** Plugin health dashboards, marketplace review queue, API usage/limits.
**Rollback.** Per-module flags fall back to monolith; plugins disable without core impact.
**Security.** Plugin sandboxing, signing, permission scoping; API OAuth + rate limits.
**Performance.** Workspace switch ≤100ms; plugin load budgeted; no core regression.
**Audit improvement.** Plugin SDK 5→75 · Marketplace 0→60 · Partner APIs 20→75 · ERP 15→60 · DX 30→75 · Technical Debt 20→55 (de-monolith). **+5–6% runtime.**
**RFC enforced.** RFC-000 extensibility/"shell holds no business logic" laws executable.

**Epics & tasks:**
- E10.1 De-monolith — [T] app shell + module loader · [F] extract cashier module (parity) · [F] extract kitchen/payment/reports/live-ops modules · [Q] behavior-parity tests per module.
- E10.2 SDK — [F] manifest + lifecycle · [F] 21 extension points + command bus · [F] sandbox · [Q] extension-point conformance + sandbox-escape tests.
- E10.3 Marketplace — [F] signed bundle + scan/verify · [F] staged rollout + entitlements · [O] review queue.
- E10.4 Partner/ERP — [F] public versioned API + OAuth + rate limit · [D] developer portal + CLI · [F] ERP connector framework + 1 connector · [Q] partner contract tests.

---

### PROGRAM 11 — Compliance, Privacy & Enterprise Trust
**Purpose.** Earn the certifications and controls that gate enterprise, government, bank, and 100-country operation.
**Business value.** Removes the procurement blockers (SOC2/ISO/SSO/DPA); opens regulated markets; enables fintech.
**Technical value.** Implements privacy/data-governance controls on the substrate + tenancy; pluggable fiscalization/residency.
**Dependencies.** P1 (auth/SSO), P4 (tenancy/residency), P6 (financial), P7 (ops evidence).
**Deliverables.**
- **Privacy engineering**: consent store, DSAR, right-to-erasure reconciled with immutable audit (anonymize private attributes, preserve skeletal fact — RFC-002 §9.6), PII inventory + classification.
- **Data governance**: catalog, lineage, retention/legal-hold, DPA.
- **Fiscalization framework**: pluggable per-country e-invoicing/fiscal packs (ZATCA, EU, …) beyond ETA; data-residency routing.
- **Enterprise trust**: SSO/SAML (from P1) hardened, audit export, SLA + status page, security questionnaire kit; **SOC 2 Type II** + **ISO 27001** control implementation + evidence collection; **PCI attestation** (from P6).
- **Commercial stack**: billing/metering/invoicing, plan enforcement, onboarding, contracts.
**Acceptance criteria.** A DSAR completes end-to-end with erasure that preserves audit integrity (test); a residency-tagged tenant's data never leaves its region (test); fiscal packs pass statutory validation in launch markets; SOC2/ISO audits pass with collected evidence; billing meters usage accurately (reconciliation test).
**Definition of Done.** Controls implemented + evidenced; certifications in-progress/achieved (external calendar); billing live; residency enforced.
**Test strategy.** Privacy property tests (erasure vs audit), residency isolation tests, fiscal parity tests, billing reconciliation tests, control-evidence conformance tests.
**Migration.** Backfill PII inventory/classification over historical events; apply retention; enable residency routing per tenant.
**Operational readiness.** Compliance dashboards, evidence automation, DSAR SLA tracking.
**Rollback.** Controls additive; billing dual-run before enforcement.
**Security.** This program *is* enterprise security posture.
**Performance.** DSAR within regulatory SLA; residency routing overhead minimal.
**Audit improvement.** Compliance 30→80 · Privacy 15→80 · Data Governance 35→75 · Enterprise 45→85 · Commercial 35→80. **+5–6% runtime.**
**RFC enforced.** RFC-002 §9 privacy/governance boundary as certified controls.

**Epics & tasks:**
- E11.1 Privacy — [F] consent store · [F] DSAR pipeline · [F] erasure-vs-audit reconciliation · [Q] privacy property tests.
- E11.2 Data governance — [F] catalog+lineage · [F] retention/legal-hold · [D] DPA.
- E11.3 Fiscalization/residency — [F] fiscal-pack framework + 2 markets · [F] residency routing · [Q] statutory + residency tests.
- E11.4 Enterprise trust — [O] SOC2/ISO control implementation + evidence · [F] audit export · [O] SLA+status page · [D] security questionnaire kit.
- E11.5 Commercial — [F] billing/metering/invoicing · [F] plan enforcement · [F] onboarding · [Q] billing reconciliation tests.

---

### PROGRAM 12 — Product Breadth & Frontend Completion
**Purpose.** Close remaining restaurant-operations depth and formalize the design/component/UX layer, on the modular frontend (P10).
**Business value.** Full functional parity-plus with incumbents; complete restaurant OS.
**Technical value.** Completes domain coverage on the substrate/services; formalizes the component library.
**Dependencies.** P8 (services), P10 (modular frontend). Parallelizable late.
**Deliverables.**
- Inventory depth (counts, transfers, par levels, waste-to-movement, recipe depletion), purchasing/procurement, recipe/production/BOM (true food cost), labor scheduling.
- CRM depth (segmentation, journeys, consent-linked), loyalty tiers + liability GL, dynamic/channel pricing.
- Localization platform (TMS, N languages, locale formats, non-Arabic RTL), accessibility audit + VPAT.
- **Component Library** + **UX Patterns** as catalogued, tested artifacts (from Experience 3.0 + existing components); Order/Payment/KDS FSMs formalized to contracts.
**Acceptance criteria.** Food cost reconciles from recipe depletion to ledger; a new language ships via the pipeline without code; a11y audit passes AA with VPAT; component library components pass the state/contract tests; FSMs match the engine specs (conformance test).
**Definition of Done.** Domain breadth covered + tested; localization/a11y industrialized; component library published.
**Test strategy.** Domain property/integration tests, localization pipeline tests, a11y automated + manual audit, component contract tests, FSM conformance tests.
**Migration.** Feature-flag each domain module; parity-test against current behavior.
**Operational readiness.** Per-module dashboards; localization coverage metrics.
**Rollback.** Per-module flags.
**Security.** Inherits P1/P4/P8 controls.
**Performance.** Inventory/pricing recompute within command budgets.
**Audit improvement.** Inventory 35→80 · CRM 30→70 · Loyalty 50→80 · Pricing 40→75 · Localization 35→80 · Accessibility 40→85 · Restaurant Ops 60→90 · Component layer 52→85. **+4–5% runtime.**
**RFC enforced.** RFC-001 domain completeness (all 40 entities have runtime homes).

**Epics & tasks:**
- E12.1 Inventory/supply — [F] counts/transfers/par · [F] recipe depletion → food cost · [F] purchasing/BOM · [Q] cost-reconciliation tests.
- E12.2 CRM/loyalty/pricing — [F] segmentation+journeys · [F] loyalty tiers + liability GL · [F] dynamic/channel pricing · [Q] domain property tests.
- E12.3 Localization/a11y — [F] TMS pipeline + N languages · [O] a11y audit + VPAT · [Q] locale + a11y tests.
- E12.4 Component library — [F] catalogued components + state contracts · [F] FSM formalization · [Q] component + FSM conformance tests · [D] library + UX-pattern docs.

---

## 4 · DETAILED BACKLOG (consolidated)

Each program above lists its epics and ≤2-week tasks tagged [F]/[T]/[Q]/[D]/[O]. Consolidated counts:

| Program | Epics | Tasks (approx) | Complexity | Squad-quarters |
|---|---|---|---|---|
| P0 Foundations | 5 | ~22 | L | 1.0 |
| P1 Security & Identity | 5 | ~22 | XL | 1.5 |
| P2 Runtime Substrate | 6 | ~24 | XL | 2.0 |
| P3 Invariant Enforcement | 4 | ~14 | L | 1.0 |
| P4 Multi-Tenancy | 5 | ~20 | XL | 2.0 |
| P5 Sync/Consistency | 4 | ~15 | L | 1.5 |
| P6 Financial Core | 4 | ~18 | XL | 2.0 |
| P7 Observability/DR/Ops | 4 | ~16 | L | 1.5 |
| P8 Platform Services | 5 | ~20 | L | 2.0 |
| P9 Data & Intelligence | 4 | ~16 | L | 1.5 |
| P10 Extensibility | 4 | ~18 | XL | 2.0 |
| P11 Compliance/Enterprise | 5 | ~20 | XL | 2.5* |
| P12 Product Breadth | 4 | ~18 | L | 2.0 |

\*P11 includes external audit calendars (SOC2 Type II observation window) that run in parallel with engineering.

**Every task carries the fixed quality bar:** unit + integration + property + offline + replay + security + performance + migration + conformance tests (whichever apply), plus a doc update and an ops hook. A task is not shippable without its tests green in CI (P0).

---

## 5 · QUARTER-BY-QUARTER ROADMAP

*Assumes ~5 parallel squads. Programs on the critical path serialize; independents parallelize.*

| Quarter | Primary (critical path) | Parallel | Exit runtime |
|---|---|---|---|
| **Q1** | P0 Foundations → P1 Security/Identity (start), P2 Substrate (start) | — | **~34%** |
| **Q2** | P1 (finish), P2 (finish) → P3 Invariants | — | **~40% → 47%** |
| **Q3** | P4 Multi-Tenancy | P5 Sync/Consistency | **~55%** |
| **Q4** | P6 Financial Core | P7 Observability/DR/Ops | **~70%** |
| **Q5** | P8 Platform Services | P9 Data & Intelligence | **~85%** |
| **Q6** | P10 Extensibility | P12 Product Breadth (start) | **~92%** |
| **Q7** | P11 Compliance/Enterprise | P12 (finish) | **~95% → Enterprise-Ready** |

(SOC2 Type II observation typically adds a calendar tail beyond Q7 to *certified*; the controls are code-complete by Q7.)

---

## 6 · CRITICAL PATH

```
P0 → P1 → P4 → P6 → P11
 └──→ P2 → P3 → P5
      P2 → P4 (join)
      P4 → P7 → P9
      P4 + P8 → P10 → P12
```

**Longest chain (gates Enterprise-Ready):** `P0 → P1 → P4 → P6 → P11` — security/identity → tenancy → financial core → compliance/enterprise. **P2 → P3 → P5** runs alongside and must complete before P6 depends on P3. **De-monolith (P10)** is the critical path for the *ecosystem* outcome and must not start before P8 exposes service seams.

**Single biggest schedule risk:** P2 (Runtime Substrate) — it is a second root feeding P3, P4, P6, P9. Under-resourcing P2 delays everything downstream. **Mitigation:** staff P2 as a dedicated squad from Q1 alongside P1.

---

## 7 · AUDIT SCORE IMPROVEMENT AFTER EACH PROGRAM

*Overall runtime maturity, cumulative (baseline 27%). Each row = evidence-backed increment.*

| After | Runtime | Key findings turned green |
|---|---|---|
| **P0** | ~30% | Testing, CI/CD, flags, obs-skeleton |
| **P1** | **~40%** | Authentication (18→75), Authorization, Permissions — **the #1 blocker cleared** |
| **P2** | ~47% | Operating Graph substrate exists; Events, Identity, Time |
| **P3** | **~55%** | 74 invariants enforced; correctness provable |
| **P4** | ~63% | True multi-tenancy; isolation tested |
| **P5** | **~70%** | Distributed consistency proven; offline/conflict hardened |
| **P6** | ~78% | Payments/settlement/ledger/tax; PCI scope |
| **P7** | **~85%** | Observability, DR, backup, incident — operable |
| **P8** | ~90% | Config/Search/Notification/Printing/Permission services |
| **P9** | **~95%** | Analytics, forecasting, benchmarking, AI — the moat runs |
| **P10** | ~96% | SDK, marketplace, partner/ERP, de-monolith |
| **P11** | **Enterprise-Ready** | Compliance, privacy, SOC2/ISO controls, billing, SSO |
| **P12** | (breadth) | Domain completeness, localization, a11y, component library |

---

## 8 · FINAL TARGET — the 27% → Enterprise-Ready progression

**27% → 40% (Steps: P0, P1).** *Capabilities:* CI/CD + test harness + flags + obs skeleton; per-principal auth replacing the shared token; default-deny authorization; secrets vault; rate limiting. *Evidence:* zero `auth='none'` data routes; coverage gate live; pen-test no-criticals on auth; property test catches a seeded money bug. *Findings resolved:* Authentication, Authorization, Permissions, Testing(partial), Deployment, Release.

**40% → 55% (Steps: P2, P3).** *Capabilities:* event store + projection + replay + identity; 74 invariants as executable guards + property tests. *Evidence:* projections byte-reproducible from the log; as-of queries correct; fuzzer cannot reach a forbidden state; 74/74 conformance report green. *Findings resolved:* Operating Graph, Events, Identity, Time, Business Invariants, Domain Model.

**55% → 70% (Steps: P4, P5).** *Capabilities:* tenant control plane + isolation + provisioning saga; realtime transport + conflict engine + convergence/exactly-once proofs; durable encrypted edge. *Evidence:* ≤90s provisioning; cross-tenant fuzz 100% denied; zero lost/dup orders in chaos suite; power-loss hardware test passes. *Findings resolved:* Multi-tenancy, Distributed Consistency, Conflict Resolution, Sync, Offline.

**70% → 85% (Steps: P6, P7).** *Capabilities:* attested ledger, PSP-agnostic payments + PCI scope, settlement recon, tax determination; full observability, DR, backup, incident. *Evidence:* ledger balances across a generated year; no PAN in storage; settlement 100% attributed; tax bit-for-bit vs `account.tax`; region failover within RTO/RPO game-day. *Findings resolved:* Payments, Settlement, Financial Ledger, Tax, Observability, DR, Backup, Operational Playbooks, Performance.

**85% → 95% (Steps: P8, P9).** *Capabilities:* config cascade, permission/search/notification/printing services; analytics warehouse, forecasting, privacy-preserving benchmarking, advisory AI. *Evidence:* new branch by config only; deterministic search ≤80ms@10k with AR parity; critical-notification 100% delivered/escalated; benchmark re-identification tests fail to identify; forecast writes no truth. *Findings resolved:* Configuration, Search, Notifications, Printing, Analytics, Forecasting, Benchmarking, AI.

**95% → Enterprise-Ready (Steps: P10, P11, P12).** *Capabilities:* SDK + marketplace + partner/ERP + de-monolithed frontend; compliance/privacy/data-governance controls, SOC2/ISO evidence, PCI attestation, SSO, billing; domain breadth + localization + a11y + component library. *Evidence:* sample plugin extends a workspace without touching core and cannot escape its sandbox; DSAR erasure preserves audit integrity; residency enforced; SOC2/ISO controls evidenced; billing reconciles; a11y AA + VPAT. *Findings resolved:* Plugin SDK, Marketplace, Partner APIs, ERP, Compliance, Privacy, Data Governance, Enterprise Readiness, Commercial Readiness, Localization, Accessibility, Technical Debt.

**Final state:** a tested, observable, multi-tenant, offline-first, compliant restaurant operating platform whose correctness is enforced (not documented), whose asset (the Operating Graph) is a running substrate, and whose canon (Constitution, RFC-000/001/002) is executable — ready for enterprise customers, governments, banks, payment networks, and a third-party ecosystem, with no further architectural documents required to execute.

*— Principal Engineer. Build order is dependency-strict; every deliverable ships with its tests; every percentage is evidence-backed.*
