# Commercial-Production Backend Blockers — Implementation Plan

*Scopes the four data-loss/money-risk blockers from the Tier-3 audit into concrete backend workstreams against the **actual `mezze_bridge` codebase**. Planning only — no code here.*

> **Audit correction (important).** The Tier-3 audit measured only `pos.html` and concluded these engines were "absent." Reading the Odoo backend shows that is wrong: the durable outbox, exactly-once + dead-letter sync ledger, append-only audit log, payment-provider + reversal models, and ESC/POS printing are **already built** (`controllers/sync.py` — "all four endpoints LIVE"; `docs/SYNC.md`, `W1.md`, `W2.md`). So this is a **complete-the-seams** plan, not build-from-scratch. Revised blocker sizing below reflects that.

## Current backend assets (what already exists)

| Asset | File | State |
|---|---|---|
| Durable terminal outbox (seq-ordered, delta payloads, uuid idempotency) | `models/mezze_sync_outbox.py` | ✅ model built |
| Cloud reconcile ledger: exactly-once + **dead-letter** + reconcile flags | `models/mezze_sync_applied.py` | ✅ built |
| Sync endpoints: `/register /push /pull /reconcile` (cursor + savepoint-per-event + poison advance) | `controllers/sync.py` (441 L) | ✅ **LIVE & proven** |
| Append-only audit log (ACL-locked create-only) | `models/mezze_audit_log.py` | ✅ built |
| Payment providers (Paymob/Fawry/HyperPay/mada/Geidea) + txn + **reversal** residual handling | `models/mezze_payment.py`, `mezze_reversal.py`, `controllers/w1.py` | 🟡 modelled; PSP state machine `TODO` |
| Network ESC/POS printing (render + raw TCP `/print/receipt` `/print/kitchen`) | `hardware.py` (model+ctrl) | 🟡 synchronous send, no queue |
| Idempotent order write (native `pos.order.uuid` via `sync_from_ui`) | `controllers/main.py` | ✅ built |

## Architectural decision that gates Blocker 1

**Offline topology fork — must be chosen first:**
- **(A) Browser client-outbox** *(current deployment: `pos.html` → single Odoo bridge).* Offline resilience = an **IndexedDB queue in the browser** + connectivity detection + a drain worker posting to `/sync/push`. Smaller, ships on today's topology.
- **(B) Edge-Odoo-per-terminal** *(the `SYNC.md` designed end-state).* Each terminal runs a local Odoo with the Postgres `mezze.sync.outbox`; cloud is HQ. Larger infra (an Odoo per till), but the backend outbox/push/pull is already written for it.

**Recommendation: (A) for pilot/commercial v1** — it fits the shipped browser frontend and reuses the *same* `/sync/push` idempotent ingest. (B) is a later scale decision, not a v1 blocker.

---

## Blocker 1 — Offline Durable Outbox + Connectivity *(client-side gap)*

**Contract:** *ordered, persistent, idempotent queue; cache→queue→RPC→ack; no silent loss offline.*
**Exists:** backend ingest (`/sync/push`, idempotent) ✅. **Gap:** the browser has **no** client outbox / connectivity detection (measured: 0).

| Task | Layer | Size |
|---|---|--:|
| Connectivity detector (`navigator.onLine` + heartbeat ping to bridge; `online`/`offline` events) | `pos.html` JS | S |
| **Client outbox** in IndexedDB: append every syncable mutation (order pay/void/refund/discount, KDS bump, cash move) with `{seq, res_uuid, model, op, payload(delta)}` | `pos.html` JS | **L** |
| Drain worker: on reconnect, POST batches to `/sync/push` in `seq` order; on `up_to_seq` ack, mark drained; honour `failed`/`flagged` in the response | `pos.html` JS | M |
| Offline UI: banner, "N queued", disable non-offline-safe actions (per `SYNC.md` "what works offline") | `pos.html` JS | S |
| Cache master data for offline (catalog/prices/taxes/floor) in IndexedDB from the bootstrap payload | `pos.html` JS | M |

**Acceptance:** kill the network mid-shift → take orders/pay(cash)/bump → restore → every operation lands in Odoo exactly once, in order; nothing lost; dead-lettered poison surfaced. **Risk:** medium (client persistence correctness; cash-only offline payment). **Effort ≈ 2–3 wk.**

## Blocker 2 — Sync Replay / Dead-Letter *(mostly done — wire + surface)*

**Contract:** *ordered, idempotent, dead-lettered; replay→RPC→ack; consistency.*
**Exists:** the whole engine — `/sync/push` exactly-once (cursor + `mezze.sync.applied`), poison dead-letter with cursor-advance, `/reconcile` read ✅. **Gap:** frontend doesn't call it yet (depends on Blocker 1), and the **dead-letter/reconcile ledger has no manager UI**.

| Task | Layer | Size |
|---|---|--:|
| Wire the drain worker (Blocker 1) to `/sync/push`; handle `applied/skipped/flagged/failed` counts | `pos.html` JS | S (shared with B1) |
| **Reconcile surface**: manager view of `mezze.sync.applied` — failed (dead-letter) + flagged (sold-past-zero) rows, with **replay** action on failed | `pos.html` + `/reconcile` (exists) | M |
| Open-reversal + terminal-health tiles into Live Ops / Manager | `pos.html` | S |
| Batch-size / backpressure limits + telemetry counters on push | `controllers/sync.py` | S |

**Acceptance:** a poison event dead-letters without blocking the queue; a manager sees it, fixes data, replays it; flagged negative-stock shows as a business event. **Risk:** low (engine proven). **Effort ≈ 1–1.5 wk** (largely UI, atop B1).

## Blocker 3 — Print Queue + Failover *(biggest new build)*

**Contract:** *eight states; durable, ordered, deduplicated queue; failover ladder; a ticket is never silently lost.*
**Exists:** printer config + ESC/POS render + raw TCP send (`/print/*`) ✅, but **synchronous, no queue** — a printer offline = lost ticket. **Gap:** the durable job queue + failover.

| Task | Layer | Size |
|---|---|--:|
| **`mezze.print.job` model**: `{uuid, printer_id, doc_type, payload, state, attempts, last_error, next_retry}`, states `queued→sending→printed / failed→retry→dead` (the spec's 8) | new model | M |
| Enqueue on order events (receipt on pay, kitchen ticket on send-to-kitchen) → job, not direct TCP | `controllers/hardware.py` / `main.py` | M |
| Drain worker (`ir.cron` or `bus`): send in order, exponential retry, **failover ladder** (station printer → backup → receipt printer → hold), dedupe by `uuid` | new worker | **L** |
| Reprint / "stuck jobs" manager UI + KDS "not printed" flag | `pos.html` | M |
| Emit `print.*` events to audit/telemetry | wire to `mezze.audit.log` | S |

**Acceptance:** unplug a kitchen printer → tickets queue, retry, fail over to backup, and none vanish; a manager can reprint; recovery drains automatically. **Risk:** medium-high (hardware timing, failover correctness). **Effort ≈ 2–3 wk.**

## Blocker 4 — Payment Settlement + Idempotent Auth *(complete the PSP state machine)*

**Contract:** *idempotent auth; batched settlement + reconciliation; reversible refunds; no double-charge / lost tender.*
**Exists:** provider models, `mezze.payment.transaction` → native `payment.transaction`, `mezze.reversal` residual, audit, native Paymob (W1), uuid-idempotent order write ✅. **Gap:** `/w1/payment/intent` is `TODO` ("pending / not implemented"); the auth→capture→settle state machine + reconciliation are incomplete.

| Task | Layer | Size |
|---|---|--:|
| Complete the PSP **state machine**: intent→authorized→captured/failed/voided, persisted on `mezze.payment.transaction`, webhook-driven | `controllers/w1.py`, `models/mezze_payment.py` | **L** |
| **Idempotent auth key** (per order+tender `res_uuid`): a retried charge re-reads the existing txn, never double-authorizes | `controllers/w1.py` | M |
| **Batched settlement + reconciliation** job: end-of-day capture/settle sweep; match acquirer settlement report → txns; surface unmatched | new `ir.cron` + report | **L** |
| Extend reversal flow: auto-reverse on `order_finalize_failed` where the acquirer supports it; else the existing open-reversal manager surface | `controllers/w1.py` (extends W2) | M |
| Provider adapters beyond Paymob (Fawry/HyperPay/mada/Geidea) behind the same interface | per-provider | M each |

**Acceptance:** a double-tap / network-retry on "Charge" never double-charges; a captured-but-finalize-fail lands in `mezze.reversal` (open) and is visible; EoD settlement matches acquirer report. **Risk:** high (money + PSP integration + PCI scope). **Effort ≈ 3–4 wk** for Paymob-complete; +~1 wk per extra provider.

---

## Cross-cutting (all four)

| Item | Note |
|---|---|
| **Telemetry** | The audit's "0 telemetry" is real — add structured event counters (push applied/failed, print states, auth outcomes) to `mezze.audit.log` + a metrics endpoint. **S–M**, shared. |
| **Idempotency is the through-line** | `res_uuid` already exists across outbox/applied/order. Reuse the *same* key for print jobs and payment auth so replays are safe everywhere. |
| **Tests** | Each blocker needs failure-injection tests (kill-network, printer-offline, double-charge, poison-event) — these ARE the acceptance criteria. **M** per blocker. |
| **Constraint waiver** | This work **modifies business logic / APIs** — it requires explicitly lifting the "presentation-only" rule that governed P1–P7 and Experience 3.0. It is a distinct backend track. |

## Sequencing & dependencies

```
1. DECIDE offline topology (A browser-outbox recommended)     ← gate
2. Blocker 1  Offline client outbox + connectivity     (2–3 wk)  ─┐
3. Blocker 2  Sync UI + replay/reconcile surface       (1–1.5wk) ─┘ (needs B1's drain)
4. Blocker 3  Print queue + failover                   (2–3 wk)    (independent — can parallelize)
5. Blocker 4  Payment state machine + settlement       (3–4 wk)    (independent — highest risk)
   +  Cross-cutting telemetry + failure tests          (ongoing)
```

- **B1 → B2** are coupled (B2 is mostly the manager UI over B1's now-flowing data + the already-live engine). Do them together.
- **B3** and **B4** are independent of B1/B2 and of each other — parallelizable across engineers.
- **Priority order by money/data-loss risk:** B4 (double-charge) ≈ B3 (lost kitchen ticket) > B1/B2 (offline loss). Sequence by risk **or** parallelize.

## Effort summary

| Blocker | Existing | Real gap | Risk | Est. |
|---|---|---|:--:|--:|
| 1 · Offline outbox | backend ingest ✅ | browser queue + connectivity | med | 2–3 wk |
| 2 · Sync replay/DL | **engine ✅ (live)** | frontend wiring + manager UI | low | 1–1.5 wk |
| 3 · Print queue | send primitive ✅ | durable queue + failover | med-high | 2–3 wk |
| 4 · Payment settle | providers+reversal ✅ | PSP state machine + settlement | **high** | 3–4 wk |
| Cross-cut | audit log ✅ | telemetry + failure tests | — | ongoing |
| **Total** | | | | **~8–12 wk** (1–2 eng, some parallel) |

**Bottom line:** the sync engine — the hardest, most dangerous of the four to get right — is **already built and proven**. The remaining work is (1) a browser offline queue, (2) manager surfaces over the live sync ledger, (3) a durable print queue, and (4) completing the payment PSP state machine + settlement. None blocks the **pilot**; all four are the real gate to **commercial** launch. Each is a discrete workstream with a failure-injection acceptance test as its definition of done.

*Plan only. No code changed. Requires the "do not modify business logic" rule to be lifted for the backend track.*
