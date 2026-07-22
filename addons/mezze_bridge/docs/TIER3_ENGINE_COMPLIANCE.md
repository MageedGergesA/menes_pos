# Tier 3 — Engine / Service Compliance Audit

*Per-spec comparison of the ~13 approved **engine/service specifications** (backend/architecture contracts) against what `pos.html` + the Odoo `mezze_bridge` actually do. **No code change** — audit only. Grounded in measured behaviour, not assumption.*

## What these specs are

They are **engineering contracts**, not UI designs. Each declares a single responsibility ("*owns X, never Y*") plus **rules · validation rules · on-fail/recovery · emitted events · performance budgets · telemetry · security · blockers before commercial launch**. They describe how a subsystem must *behave*, largely in the backend.

## What we built (the honest baseline)

`pos.html` is a **pilot/demo POS frontend** with an Odoo bridge:
- **Real:** the domain **UI + frontend math** — order/cart, split, park, gift, refund, discount, VAT 14% + service 12%, tenders, loyalty, KDS, floor, reservations, delivery, HQ, central kitchen, reports, live ops, receipt/print/email/WhatsApp send, ETA e-invoice hooks, manager-PIN gating, product search/filter.
- **Bridge:** `BRIDGE.*` calls to Odoo (`/ops/summary`, etc.) for live data; a demo offline fallback.
- **Not present (measured):** durable offline outbox, `navigator.onLine` connectivity detection, a print job-state queue, search debounce, telemetry/event emission.

## Compliance legend

🟢 **Adequate** for pilot (UI + behaviour present) · 🟡 **Partial** (UI present, engine contract incomplete) · 🔴 **Missing** (engine contract absent — commercial-production blocker)

---

## Per-Engine Audit

### 1. Order Engine — *rules, validation, on-fail/recovery, "every command emits its event"*
| Facet | Approved contract | Current | Status |
|---|---|---|---|
| Order lifecycle UI | create / modify / split / park / void | Full UI (`#lines`, verbs, split/park) | 🟢 |
| Frontend order math | line totals, subtotal | Computed in-frontend | 🟢 |
| Validation rules / on-fail-recovery | typed rejections, defined outcomes | Ad-hoc (toasts); no formal rule set | 🟡 |
| Emitted events / telemetry | every command emits event | **None** (0 emit/telemetry) | 🔴 |
**Verdict: ~65% (UI complete; formal rule/event contract absent).**

### 2. Payment Engine — *"owns orchestration, never arithmetic; idempotent auth; batched settlement + reconciliation; reversible refunds; deterministic splits; safe offline"*
| Facet | Approved | Current | Status |
|---|---|---|---|
| Tender UI + split + refund | tender model, splits, refunds | Full (tenders, split, 90 refund refs) | 🟢 |
| Deterministic splits | seat/item/equal splits | Implemented (`splitMode`) | 🟢 |
| Idempotent auth / provider routing | dedup auth, gateway routing | Not implemented (Paymob/ETA hooks demo) | 🔴 |
| Batched settlement + reconciliation | settlement ledger | Not implemented | 🔴 |
| Safe offline payment | queued, reconciled | Demo only (no durable queue) | 🔴 |
**Verdict: ~55% (payment *surface* strong; settlement/auth/offline engine absent).**

### 3. Tax Engine — *"owns tax determination; configurable rate/base/inclusivity"*
| Facet | Approved | Current | Status |
|---|---|---|---|
| Tax application | VAT + service charge | VAT 14% + service 12% computed live | 🟢 |
| Configurable determination | rate/base/inclusivity, rules | Hard-coded rates; not a determination engine | 🟡 |
| Inclusive/exclusive + rounding rules | defined | Not exposed/configurable | 🟡 |
**Verdict: ~60% (correct application; not configurable/rule-driven).**

### 4. Discount Engine — *"owns discounts; runs before tax; manager overrides; consumes loyalty"*
| Facet | Approved | Current | Status |
|---|---|---|---|
| Discount UI + manager override | discount verb, mgr approval | Present (discount verb, manager PIN) | 🟢 |
| Loyalty as eligibility/reward | loyalty integration | Loyalty present (34 refs) | 🟢 |
| **Runs-before-tax ordering** | explicit rule | **Not explicitly enforced/verifiable** (0) | 🟡 |
| Rule engine / validation | typed rules | Ad-hoc | 🟡 |
**Verdict: ~60%.**

### 5. Search Service — *"one keystroke budget; ≤40MB index / 10k records; debounce 60ms; cancelled queries never paint stale; results capped"*
| Facet | Approved | Current | Status |
|---|---|---|---|
| Product search + category filter | find anything | Present (search + `⌘K`, category chips) | 🟢 |
| Debounce 60ms | perf budget | **No debounce** (0) | 🔴 |
| ≤40MB index / 10k / stale-guard | indexed service | Client array filter, not an indexed service | 🔴 |
**Verdict: ~45% (works at demo scale; no indexed service or perf guarantees).**

### 6. Offline Engine — *"owns availability + outbox; ordered, persistent, idempotent queue; cached master data; cache→queue→RPC→ack; budgets; integrity"*
| Facet | Approved | Current | Status |
|---|---|---|---|
| Offline mode / cached data | works offline | Demo offline fallback (`BRIDGE.connected`) | 🟡 |
| **Durable outbox** (persistent/ordered/idempotent) | core contract | **Absent** (no store, 0) | 🔴 |
| Connectivity detection | `online`/`offline` events | **Absent** (`navigator.onLine` = 0) | 🔴 |
**Verdict: ~30% (offline is a UI state, not the spec's durable outbox engine).**

### 7. Synchronization Engine — *"ordered, idempotent, dead-lettered; replay→RPC→ack; budgets; integrity"*
| Facet | Approved | Current | Status |
|---|---|---|---|
| Backend sync | Odoo RPC | `BRIDGE.*` calls (346 refs) | 🟢 |
| Ordered / idempotent replay | queue replay | Direct calls; no replay queue | 🔴 |
| Dead-letter + integrity guarantees | consistency | Not implemented | 🔴 |
**Verdict: ~40% (live bridge works; no replay/consistency engine).**

### 8. Printing Service — *"owns delivery, never content; eight states; durable, ordered, deduplicated queue; failover ladder; a ticket is never silently lost"*
| Facet | Approved | Current | Status |
|---|---|---|---|
| Print/email/WhatsApp send | document delivery | Send buttons (`.sendbtn`) present | 🟢 |
| **8-state durable dedup queue** | core contract | **Absent** (no queue/state machine, 0) | 🔴 |
| Failover ladder / retry | never silently lost | **Absent** (0) | 🔴 |
**Verdict: ~35% (send UI present; no durable print queue).**

### 9. Notification Service — *"owns delivery of signals; category drives channel/tone/routing; critical never ignored quietly; escalation ladder"*
| Facet | Approved | Current | Status |
|---|---|---|---|
| Toasts + ops alerts | signal delivery | `toast()` + burn-rate alerts | 🟢 |
| Category-driven routing/tone | channel model | Partial (severity tones exist post colour-pack) | 🟡 |
| Escalation ladder / "never ignored" | critical guarantee | Not implemented | 🔴 |
**Verdict: ~50%.**

### 10. Permission Service — *"least-privilege per role; escalate, elevate briefly, always audit; temporary elevation (15 min); approval workflows; policy engine"*
| Facet | Approved | Current | Status |
|---|---|---|---|
| Role gating (manager) | least-privilege | Manager PIN gate; 86/override approval | 🟢 |
| **Temporary elevation (timed) + audit log** | core contract | **Not implemented** (PIN is per-action) | 🔴 |
| Policy engine / approval workflows | configurable | Ad-hoc gates | 🟡 |
**Verdict: ~50%.**

### 11. AI Service — *"advisory; proposes, never decides; role-scoped, grounded in tenant data; recommendations + forecasting"*
| Facet | Approved | Current | Status |
|---|---|---|---|
| Advisory surfaces | suggestions/forecasts | "Suggested" chip + burn-rate forecast (heuristic) | 🟡 |
| Grounded in tenant data / role-scoped | real model | Demo heuristics, not a grounded service | 🔴 |
**Verdict: ~35%.**

### 12. Restaurant Configuration — *config surface; blockers before production*
| Facet | Approved | Current | Status |
|---|---|---|---|
| Config surface | restaurant setup | Partial via HQ / Central Kitchen views | 🟡 |
| Dedicated config UI | full settings | **No `view-settings`** | 🔴 |
**Verdict: ~30%.**

### 13. Payment Workspace *(UI spec — overlaps Tier 2 P3)* — *"how a tender reaches the ledger; interaction/loading/empty; keyboard; feature flags"*
| Facet | Approved | Current | Status |
|---|---|---|---|
| Payment hierarchy (amount hero, methods) | full workspace | Overlay, hierarchy matched (Exp3 P3) | 🟢 |
| Full-workspace layout | edge-to-edge | Overlay (recorded product decision) | 🟡 |
| Loading / empty / error states | defined | Partial | 🟡 |
**Verdict: ~85% (visual); see Exp3 P3.**

---

## Summary

| Engine | UI/feature | Engine contract | Overall | Commercial blocker? |
|---|:--:|:--:|--:|:--:|
| Order | 🟢 | 🔴 events | ~65% | telemetry |
| Payment | 🟢 | 🔴 settlement/auth | ~55% | **yes** |
| Tax | 🟢 | 🟡 config | ~60% | config |
| Discount | 🟢 | 🟡 rules | ~60% | ordering rule |
| Search | 🟢 | 🔴 index/debounce | ~45% | at scale |
| Offline | 🟡 | 🔴 outbox | ~30% | **yes** |
| Sync | 🟢 | 🔴 replay | ~40% | **yes** |
| Print | 🟢 | 🔴 queue/failover | ~35% | **yes** |
| Notification | 🟢 | 🔴 escalation | ~50% | — |
| Permission | 🟢 | 🔴 elevation/audit | ~50% | audit |
| AI | 🟡 | 🔴 grounding | ~35% | — |
| Restaurant Config | 🟡 | 🔴 settings UI | ~30% | — |
| Payment Workspace | 🟢 | 🟡 states | ~85% | — |

**Weighted Tier-3 compliance ≈ 50%** — split sharply: the **domain UI + frontend math are pilot-ready (~🟢)**, while the **engine-grade contracts** (durable outbox, replay/dead-letter sync, print queue+failover, idempotent settlement, timed elevation+audit, indexed search, telemetry) are **largely absent (~🔴)**.

## Interpretation — this is expected, and correctly scoped

1. **The specs themselves say so.** Nearly every one ends with "*blockers before commercial launch*" — the authors classify the missing engine machinery as known pre-commercial work, not shipped features.
2. **It never was in scope.** P1–P7 and Experience 3.0 were *presentation-layer* programs under a hard "do not modify business logic / APIs" rule. Tier-3 engines are exactly that business/architecture layer.
3. **The right home is Odoo.** Durable outbox, settlement, sync replay, print queue, permission audit and telemetry belong in the `mezze_bridge` Odoo backend, not `pos.html`. Implementing them is a **backend engineering track**, separate from the visual program.

## Recommendation — the four true commercial blockers

For **pilot** (amber default, mezze opt-in): none of these block — the demo/bridge behaviour is adequate.

For **commercial production**, prioritise the four 🔴 that risk data loss or money:
1. **Offline durable outbox** + connectivity detection (no silent order loss offline).
2. **Sync replay / dead-letter** (ordered, idempotent, no double-post to Odoo).
3. **Print queue + failover** (a kitchen/receipt ticket is never silently lost).
4. **Payment settlement + idempotent auth** (no double-charge / lost tender).

`Search` (indexing/debounce) and `Permission` (timed elevation + audit) follow. These are a **backend engineering roadmap**, each a discrete workstream — and each would require lifting the "do not modify business logic" rule that governed the visual programs.

*Audit only — no code changed. `pos.html` untouched.*
