# Mezze — Complete Gap Model · VOLUME V: Engineering Backlog

*Every task ≤1 week, independently shippable, each referencing Constitution/RFC · Audit Finding · Program · Epic · Acceptance Test. This volume gives the **complete critical-path backlog (P0→P6, the first ~3 quarters)** at ≤1-week granularity, plus the **task schema and generation rule** by which each remaining program's backlog is expanded at kickoff (hand-authoring all ~2,800 tasks for 28 programs upfront is waste — real orgs decompose per-program at sprint-zero using a fixed schema; that schema is here so the expansion is mechanical and consistent).*

## Task schema (every task carries these)

```
ID:        <Pn>-<Epic>-<seq>
Title:     <imperative, ≤1 week>
Type:      [F]eature | [T]ech | [Q]test | [D]oc | [O]ps
Refs:      Canon=<Constitution/RFC-00x §>  Audit=<Vol-I area # or Vol-III risk #>
           Program=<Pn>  Epic=<epic>  Acceptance=<AT-id>
DoD:       code + the applicable subset of {unit, integration, property, offline,
           replay, security, performance, migration, conformance} tests green in CI,
           behind a flag, doc + ops hook updated.
```

Acceptance tests (AT-*) are referenced by id; each program owns its AT catalog. A task is **done** only when its AT is green in CI.

---

## P0 — Engineering Foundations (backlog)

- **P0-E0.1-01** [T] Wire Odoo `TransactionCase`/`HttpCase` runner into CI. Refs: Canon=RFC-000(verification); Audit=#81 Testing; Epic=Test-harness; AT-P0-01 (a failing test blocks merge).
- **P0-E0.1-02** [T] Add JS unit-test runner for `pos.html` logic modules. Audit=#81; AT-P0-02.
- **P0-E0.1-03** [T] Integrate property-testing library; scaffold generators for Money/Qty. Canon=RFC-001(value objects); AT-P0-03.
- **P0-E0.1-04** [Q] 20 property tests for calc order (discount→tax, rounding-once). Canon=RFC-001 invariants; Audit=#5; AT-P0-04.
- **P0-E0.1-05** [D] "How to test" guide + fixtures. AT-P0-05 (new dev writes a test in <1h).
- **P0-E0.2-01** [T] Pipeline: lint + unit stages. Audit=#82; AT-P0-06.
- **P0-E0.2-02** [T] Pipeline: integration + contract-test stages. AT-P0-07.
- **P0-E0.2-03** [T] Coverage gate (≥70% new code). AT-P0-08.
- **P0-E0.2-04** [T] SAST + dependency-scan + SBOM stage. Audit=#9,#76; AT-P0-09.
- **P0-E0.2-05** [T] Secret-scanning stage + pre-commit hook. Audit=#3; AT-P0-10.
- **P0-E0.2-06** [O] Staging→prod promotion with approval gate. AT-P0-11.
- **P0-E0.3-01** [T] Codify Odoo+proxy+worker topology as IaC. Audit=#57; AT-P0-12.
- **P0-E0.3-02** [O] Ephemeral-env spin-up/tear-down script. AT-P0-13 (env from zero <15m).
- **P0-E0.3-03** [Q] IaC apply/destroy idempotency test. AT-P0-14.
- **P0-E0.4-01** [F] Typed flag store + server-side eval API. Audit=#58; AT-P0-15.
- **P0-E0.4-02** [F] Flag targeting (tenant/branch/percentage). AT-P0-16.
- **P0-E0.4-03** [Q] Flag-eval property tests + kill-switch test. AT-P0-17.
- **P0-E0.4-04** [D] Flag catalog + lifecycle policy (retire stale). Audit=#34-mistake; AT-P0-18.
- **P0-E0.5-01** [T] Structured logging + trace-ID middleware on all controllers. Audit=#52,#53; AT-P0-19.
- **P0-E0.5-02** [T] Metrics endpoint (RED per route). Audit=#50; AT-P0-20.
- **P0-E0.5-03** [Q] Trace-propagation integration test across a request. AT-P0-21.
- **P0-E0.5-04** [O] Pipeline + flag + trace dashboards. AT-P0-22.

## P1 — Security & Identity (backlog)

- **P1-E1.1-01** [F] Principal model (device/user/service). Canon=RFC-002 P1.11(Authority); Audit=#13; Epic=Principals; AT-P1-01.
- **P1-E1.1-02** [F] Signed access token issue/verify. AT-P1-02.
- **P1-E1.1-03** [F] Refresh + rotation + revocation. Audit=#4; AT-P1-03 (revoked token rejected).
- **P1-E1.1-04** [Q] Token lifecycle security tests (replay, expiry, tamper). AT-P1-04.
- **P1-E1.2-01** [F] Device enrollment flow. AT-P1-05.
- **P1-E1.2-02** [F] User login + PIN/password policy. AT-P1-06.
- **P1-E1.2-03** [T] OIDC adapter. Audit=#6; AT-P1-07.
- **P1-E1.2-04** [T] SAML 2.0 adapter. AT-P1-08.
- **P1-E1.2-05** [T] SCIM provisioning endpoint. AT-P1-09.
- **P1-E1.2-06** [T] MFA (TOTP/WebAuthn) + step-up interface. Audit=#5; AT-P1-10.
- **P1-E1.2-07** [Q] SSO/MFA integration tests (IdP simulator). AT-P1-11.
- **P1-E1.3-01** [F] Role/permission/scope model. Canon=RFC-002 §9; Audit=#14; AT-P1-12.
- **P1-E1.3-02** [F] `can()` default-deny evaluator (cached ≤2ms). AT-P1-13.
- **P1-E1.3-03** [F] Elevation (approval/PIN/session) with TTL + audit. AT-P1-14.
- **P1-E1.3-04** [F] Approval workflows (void/refund/override/config). Canon=RFC-001 approval levels; AT-P1-15.
- **P1-E1.3-05** [Q] Authz-matrix + privilege-escalation security tests. AT-P1-16.
- **P1-E1.3-06** [D] Role catalog (12 roles × scopes). AT-P1-17.
- **P1-E1.4-01** [T] Auth middleware; replace `auth='none'` on orders routes. Audit=#2,#13; AT-P1-18.
- **P1-E1.4-02** [T] Replace `auth='none'` on payments/w1 routes. AT-P1-19.
- **P1-E1.4-03** [T] Replace `auth='none'` on sync/hardware/aggregator routes. AT-P1-20.
- **P1-E1.4-04** [Q] "No auth='none' data route" conformance test. AT-P1-21.
- **P1-E1.4-05** [T] Webhook signature + replay-protection + rotation. Audit=#13,#79; AT-P1-22.
- **P1-E1.4-06** [T] Legacy-token dual-run flag + usage telemetry. AT-P1-23.
- **P1-E1.5-01** [T] Vault integration; migrate `api_token` + provider creds. Audit=#3,#15; AT-P1-24.
- **P1-E1.5-02** [T] Rate limiter + gateway policy per principal/tenant. Audit=#7,#73; AT-P1-25.
- **P1-E1.5-03** [T] CSP + security headers on pos/qr/shop/cfd surfaces. Audit=#12; AT-P1-26.
- **P1-E1.5-04** [T] Tighten CORS from `*` to allowlist. Audit=#87-sec; AT-P1-27.
- **P1-E1.5-05** [Q] Rate-limit + header + CORS security tests. AT-P1-28.
- **P1-E1.5-06** [O] Threat model (STRIDE) + external pen-test of auth surface. Audit=#11,#83; AT-P1-29 (no criticals).
- **P1-E1.5-07** [O] Secret-rotation + revocation runbook. AT-P1-30.

## P2 — Runtime Substrate (backlog)

- **P2-E2.1-01** [F] Event envelope type (times/actor/tenant/causation/idempotency). Canon=RFC-002 P1,P4/RFC-001 §5,§9; Audit=#4,#6; AT-P2-01.
- **P2-E2.1-02** [F] Append API (per-aggregate ordering). AT-P2-02.
- **P2-E2.1-03** [F] Read API (by aggregate, by cursor). AT-P2-03.
- **P2-E2.1-04** [Q] Ordering + idempotent-apply property tests. Canon=RFC-002 P1.7; AT-P2-04.
- **P2-E2.1-05** [Q] Immutability test (append-only enforced). Canon=RFC-002 P1.4; AT-P2-05.
- **P2-E2.2-01** [F] Event schema registry + validation. Audit=#48; AT-P2-06.
- **P2-E2.2-02** [F] Upcaster framework (version N→N+1). AT-P2-07.
- **P2-E2.2-03** [Q] Schema-evolution migration tests. AT-P2-08.
- **P2-E2.2-04** [D] Event catalog generated from RFC-001 §5. AT-P2-09.
- **P2-E2.3-01** [F] Projection runtime + checkpoint cursors. Canon=RFC-002 P6; AT-P2-10.
- **P2-E2.3-02** [F] Current-order projection. AT-P2-11.
- **P2-E2.3-03** [F] KDS + cash-session + day-book projections. AT-P2-12.
- **P2-E2.3-04** [Q] Projection-purity + replay-equivalence tests. Audit=#3; AT-P2-13 (replay==live byte-equal).
- **P2-E2.4-01** [F] Rebuild-projection command. AT-P2-14.
- **P2-E2.4-02** [F] As-of state query API. Canon=RFC-002 §5.4; AT-P2-15 (100 sampled timestamps correct).
- **P2-E2.4-03** [Q] Crash-resume replay test. AT-P2-16.
- **P2-E2.4-04** [F] Snapshotting (threshold-based). AT-P2-17.
- **P2-E2.5-01** [F] Edge-born ID minting (time-ordered, offline-safe). Canon=RFC-002 P1.8; Audit=#7; AT-P2-18.
- **P2-E2.5-02** [Q] 10⁶-scale collision property test. AT-P2-19.
- **P2-E2.5-03** [F] Reversible merge + audit. Canon=RFC-002 §5.3; AT-P2-20.
- **P2-E2.5-04** [F] Un-merge (reverse). AT-P2-21.
- **P2-E2.5-05** [Q] Merge-reversibility + history-preservation test. AT-P2-22.
- **P2-E2.6-01** [T] Genesis backfill from current Odoo state. Audit=#9-cap; AT-P2-23.
- **P2-E2.6-02** [T] Dual-write bridge from `mezze.sync.outbox`. AT-P2-24.
- **P2-E2.6-03** [Q] Backfill conformance test (state ≡ ontology). Canon=RFC-001; AT-P2-25.
- **P2-E2.6-04** [T] PII-classification + redaction hooks on event payloads. Audit=#67; AT-P2-26.

## P3 — Invariant Enforcement (backlog)

- **P3-E3.1-01** [F] Invariant-predicate framework. Canon=RFC-001 invariants; Audit=#5; AT-P3-01.
- **P3-E3.1-02** [F] Encode invariants 1–19 (order/line/money). AT-P3-02.
- **P3-E3.1-03** [F] Encode invariants 20–37 (payment/tax/discount). AT-P3-03.
- **P3-E3.1-04** [F] Encode invariants 38–55 (stock/movement/waste). AT-P3-04.
- **P3-E3.1-05** [F] Encode invariants 56–74 (identity/time/audit). AT-P3-05.
- **P3-E3.1-06** [D] Invariant→guard map. AT-P3-06.
- **P3-E3.2-01** [F] Command-interceptor guard layer. AT-P3-07.
- **P3-E3.2-02** [F] Typed rejection + audit emit on violation. Canon=RFC-002(Audit node); AT-P3-08.
- **P3-E3.2-03** [Q] Boundary-rejection integration tests. AT-P3-09.
- **P3-E3.3-01** [Q] Generative tests invariants 1–37. AT-P3-10.
- **P3-E3.3-02** [Q] Generative tests invariants 38–74. AT-P3-11.
- **P3-E3.3-03** [Q] Forbidden-transition unreachability tests (Draft→Paid, Closed→Open…). Canon=RFC-001 FSM; AT-P3-12.
- **P3-E3.4-01** [T] CI conformance report (74/74 guard+test). AT-P3-13.
- **P3-E3.4-02** [T] Observe-mode + violation quarantine over backfill. AT-P3-14.
- **P3-E3.4-03** [O] Invariant-violation dashboard (target 0). AT-P3-15.

## P4 — Multi-Tenancy (backlog)

- **P4-E4.1-01** [F] Tenant model + hierarchy. Canon=RFC-002 §9(ownership); Audit=#12,#65; AT-P4-01.
- **P4-E4.1-02** [F] Tenant 10-state lifecycle. AT-P4-02.
- **P4-E4.1-03** [F] Control-plane API (10 ops). AT-P4-03.
- **P4-E4.1-04** [Q] Lifecycle-transition tests. AT-P4-04.
- **P4-E4.2-01** [F] Saga runtime (idempotent/compensatable). AT-P4-05.
- **P4-E4.2-02** [F] 6 provisioning steps. AT-P4-06.
- **P4-E4.2-03** [Q] Failure-injection saga tests (no partial tenant). Audit=#16-mistake; AT-P4-07.
- **P4-E4.2-04** [Q] ≤90s provisioning perf test. AT-P4-08.
- **P4-E4.3-01** [T] Tenant claim in token → event → data access. Audit=#20,#89; AT-P4-09.
- **P4-E4.3-02** [T] Cache/file/job namespacing by tenant. Audit=#19; AT-P4-10.
- **P4-E4.3-03** [Q] Cross-tenant fuzz suite (100% denied). Audit=#20,#203-cap; AT-P4-11.
- **P4-E4.3-04** [O] Tenant-mismatch hard-deny + alerting. AT-P4-12.
- **P4-E4.4-01** [F] Per-tenant quotas + admission. Audit=#104; AT-P4-13.
- **P4-E4.4-02** [F] Entitlement/feature resolution per tenant. AT-P4-14.
- **P4-E4.4-03** [Q] Noisy-neighbor load test. AT-P4-15.
- **P4-E4.5-01** [T] Company/branch → tenant mapping. AT-P4-16.
- **P4-E4.5-02** [T] Backfill tenant id onto events/records. AT-P4-17.
- **P4-E4.5-03** [Q] Isolation-before-cutover test. AT-P4-18.

## P5 — Sync/Offline/Consistency (backlog)

- **P5-E5.1-01** [F] Realtime channel + backpressure. Audit=#10,#228-cap; AT-P5-01.
- **P5-E5.1-02** [Q] Fan-out load test (branch scale). AT-P5-02.
- **P5-E5.1-03** [O] Channel dashboards. AT-P5-03.
- **P5-E5.2-01** [F] Per-field conflict resolver. Canon=RFC-002 §5.3; Audit=#11,#12; AT-P5-04.
- **P5-E5.2-02** [F] Conflict review queue + resolution UX. AT-P5-05.
- **P5-E5.2-03** [F] Duplicate-collapse by idempotency key. Audit=#106-mistake; AT-P5-06.
- **P5-E5.2-04** [Q] Conflict property tests (same-field→review 100%). AT-P5-07.
- **P5-E5.3-01** [Q] Adversarial ordering/partition chaos suite. Audit=#239-cap; AT-P5-08.
- **P5-E5.3-02** [Q] Exactly-once property tests (0 lost/dup). AT-P5-09.
- **P5-E5.3-03** [Q] Convergence-SLA test (≤5s). AT-P5-10.
- **P5-E5.4-01** [T] Encrypted durable local store. Audit=#9; AT-P5-11.
- **P5-E5.4-02** [Q] Power-loss hardware durability test. AT-P5-12.
- **P5-E5.4-03** [F] Card-offline risk policy + store-and-forward. Audit=#106-cap; AT-P5-13.
- **P5-E5.4-04** [Q] Offline replay tests (edge-born events join). AT-P5-14.

## P6 — Financial Core (backlog)

- **P6-E6.1-01** [F] Double-entry ledger projection. Canon=RFC-001 money invariants; Audit=#18,#20; AT-P6-01.
- **P6-E6.1-02** [F] Multi-currency + FX capture. AT-P6-02.
- **P6-E6.1-03** [F] Fiscal-close controls + period lock. AT-P6-03.
- **P6-E6.1-04** [Q] Balance property test (generated year → 0). AT-P6-04.
- **P6-E6.2-01** [F] PSP provider abstraction + 10-state FSM. Canon=RFC-001 Payment≠Tender; Audit=#19; AT-P6-05.
- **P6-E6.2-02** [F] Idempotency keys + tokenization vault. Audit=#8,#25-sec; AT-P6-06.
- **P6-E6.2-03** [T] 3DS/SCA flow. AT-P6-07.
- **P6-E6.2-04** [Q] No-double-capture + PAN-absence tests. Audit=#58,#25; AT-P6-08.
- **P6-E6.3-01** [F] Settlement reconciliation vs processor files. Audit=#21,#57; AT-P6-09.
- **P6-E6.3-02** [F] Fee/interchange accounting. AT-P6-10.
- **P6-E6.3-03** [F] Dispute/chargeback flow. AT-P6-11.
- **P6-E6.3-04** [Q] Reconciliation property tests. AT-P6-12.
- **P6-E6.4-01** [F] Tax determination cascade. Canon=RFC-001 discount-before-tax; Audit=#22; AT-P6-13.
- **P6-E6.4-02** [F] Rule-pack framework + 2 markets. AT-P6-14.
- **P6-E6.4-03** [Q] `account.tax` parity corpus (bit-for-bit). AT-P6-15.
- **P6-E6.4-04** [D] Jurisdiction-pack authoring guide. AT-P6-16.

---

## Backlog generation rule for P7–P27 (mechanical expansion at kickoff)

Each remaining program expands to ≤1-week tasks by the same schema. **Rule:** for every Epic in the program (Vol IV), emit tasks in this fixed order — (a) [F] the smallest shippable slice, iterated; (b) [T] the integration/wiring; (c) [Q] the applicable test subset from the quality bar; (d) [O] the ops hook (dashboard/runbook/alert); (e) [D] the doc. Every task references its Program, Epic, the Canon clause it enforces, the Vol-I area / Vol-III risk it closes, and an AT-id. **Sizing check:** if a task exceeds one week, split by (i) entity, (ii) endpoint, (iii) tender/jurisdiction/locale, (iv) happy-path vs edge, or (v) observe-mode vs enforce. This yields, per program, ~15–25 tasks (matching Vol IV epic counts), for a full portfolio backlog of **~600 tasks across P7–P27** on top of the **~135 critical-path tasks above** — i.e., ~735 ≤1-week tasks total, generated deterministically. (The catalog is not padded to a round number; it is exactly what the epics require.)

**Representative expansions (one epic per remaining program, to demonstrate the rule):**

- **P7-E7.2-01** [F] Per-tenant PITR backup job. Refs: Audit=#56; AT-P7-09. → then [O] restore-drill automation, [Q] auto-verify restore, [O] multi-region failover, [Q] game-day chaos.
- **P8-E8.3-01** [F] Search provider framework. Audit=#33; AT-P8-11. → [F] AR/EN normalization, [F] deterministic ranking, [F] offline index, [Q] relevance+latency+isolation.
- **P9-E9.1-01** [T] CDC feed from event log to warehouse. Audit=#39; AT-P9-01. → [F] semantic layer, [Q] analytics↔ledger reconciliation.
- **P11-E11.4-01** [O] SOC 2 control implementation (access). Audit=#72; AT-P11-10. → evidence automation, ISO ISMS, PCI AOC.
- **P13-E13.4-01** [Q] Prompt-injection red-team suite. Audit=#44; AT-P13-06. → confidence-gate test, eval-gate CI, drift monitor.
- **P14-E14.3-01** [Q] Re-identification adversarial test on benchmarks. Canon=RFC-002 §9.6; Audit=#41; AT-P14-05. → k-anonymity aggregation, MAPE tracking.
- **P16-E16-01** [F] Fiscal-pack framework. Audit=#66; AT-P16-01. → ZATCA pack, EU packs, statutory validation.
- **P21-E21-01** [F] Cell placement service. Audit=#63; AT-P21-01. → tenant sharding, 1M load test, blast-radius game-day.
- **P23-E23-01** [F] DSAR pipeline. Audit=#67; AT-P23-01. → erasure-vs-audit reconciliation, residency routing, property tests.
- **P24-E24-01** [F] Usage metering. Audit=#85; AT-P24-01. → billing/invoicing, plan enforcement, reconciliation test.

*Volume V ends. Every critical-path task is ≤1 week with full references; the remaining ~600 are generated by the fixed rule at each program's sprint-zero — deterministic, not improvised.*
