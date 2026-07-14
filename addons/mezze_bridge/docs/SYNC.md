# Mezze Offline ⇄ Cloud Sync — Design

Status: **sync engine LIVE** (2026-07-14). `register`, `push` (sales upsert +
commutative stock/loyalty delta-merge + dead-letter + exactly-once), `pull`
(watermarked config-down, branch-scoped, cursor-paginated, soft-delete aware),
and `reconcile` (manager oversight of the apply ledger) are all implemented and
proven. Remaining: the `.exe` bundling + terminal-scoped `pos_reference`
sequence. The design below is the full spec.

## The one principle

> **Sync events (deltas), not state.**

Never replicate `stock = 40` or `points = 320`. Replicate `-1 croissant sold`
and `-200 points redeemed`. Deltas are **commutative** — apply them in any order,
on any node, and every node converges to the same result. This eliminates
last-write-wins data loss, makes ordering irrelevant, and sidesteps clock skew
(the runtime can't rely on wall-clock ordering anyway). It is the single decision
that makes the whole engine correct.

## Topology & authority

```
        ┌──────────────── CLOUD (HQ — truth for shared config) ────────────────┐
        │  Odoo + Postgres   ·   /mezze/sync/v1/{register,push,pull}            │
        └──────▲──────────────────────▲──────────────────────▲──────────────────┘
        push ▲ │ pull            push ▲│ pull            push ▲│ pull
        ┌─────┴─┴─────┐         ┌──────┴┴──────┐         ┌──────┴┴──────┐
        │ TERMINAL A  │         │  TERMINAL B  │         │  TERMINAL C  │
        │Odoo+PG+.exe │         │ Odoo+PG+.exe │         │ Odoo+PG+.exe │
        │  outbox     │         │   outbox     │         │   outbox     │
        └─────────────┘         └──────────────┘         └──────────────┘
```

The .exe bundles a **local Odoo + Postgres** and the *same* front-end pointed at
`localhost` (the front-end's `base` query param already makes the backend origin
swappable — see `static/pos.html`). The UI is byte-for-byte identical online and
offline; only the sync worker differs.

### Who owns truth for what

| Data | Owner | Direction | Method | Conflict |
|---|---|---|---|---|
| Catalog: products, prices, taxes, modifiers, categories | Cloud | ↓ pull | watermark (idempotent) | none |
| Menu availability, floor layout, branch config | Cloud | ↓ pull | watermark | none |
| Users / PINs / permissions | Cloud | ↓ pull | watermark | none |
| Loyalty program/reward **definitions** | Cloud | ↓ pull | watermark | none |
| Sales: `pos.order`, payments, KDS tickets, cash moves | Terminal | ↑ push | outbox, append-only | none (disjoint) |
| Inventory **quantities** | Shared | ↕ both | **delta events** | commutative merge |
| Loyalty **point balances** | Shared | ↕ both | **transaction events** | commutative merge |

Everything hard collapses to: **config pulls down (idempotent)**, **events push
up (idempotent by uuid)**. The only genuinely shared mutable state is inventory +
points, and both become commutative deltas.

## Change capture

### Terminal → cloud: the outbox (`mezze.sync.outbox`)
Every syncable mutation appends one durable, ordered row. The worker drains it in
`seq` order and marks `synced` on cloud ack. It survives crashes and offline
stretches (it is a Postgres table). `res_uuid` = idempotency key; `seq` = ordering
key. Populate via ORM `create/write/unlink` overrides on the synced models (or a
`write_date > watermark` scan for a faster MVP).

### Cloud → terminal: watermark (`mezze.sync.cursor`)
Terminal stores `last_pulled = max(write_date)` per config model and asks the
cloud "give me everything changed since." Re-applying config is idempotent, so no
outbox is needed downward.

## The worker loop

Cleanest as an `ir.cron` inside the bundled local Odoo (no extra runtime in the
.exe):

```
every N seconds (online) / queue (offline):
  # PUSH  (terminal -> cloud)
  batch = outbox.where(synced = false).order(seq).limit(500)
  ack   = POST cloud/mezze/sync/v1/push {terminal_id, token, events: batch}
  outbox.mark_synced(ack.up_to_seq)          # resume from N+1 next time

  # PULL  (cloud -> terminal)
  changes = POST cloud/mezze/sync/v1/pull {terminal_id, since: watermarks}
  apply(changes)                              # upsert config by uuid, apply deltas
  cursor.advance(changes.new_watermarks)
```

- **Push cadence:** debounced ~2–5s online; unbounded queue offline.
- **Pull cadence:** ~30–60s, plus an immediate pull after each push ack.
- **Transport:** HTTPS `type='json2'` endpoints, per-terminal token, gzip,
  cursor-resumable.

## The three conflict cases

### 1. Sales — trivially safe
Each `pos.order` has a globally-unique `uuid` (already present). Cloud upserts by
uuid → idempotent; two terminals never create the same order, so no conflict is
possible. **Must-fix:** `pos_reference` sequences must be **terminal-scoped**
(`{branch}-{terminal}-{seq}`) or two offline terminals mint the same number.

### 2. Inventory — commutative deltas + accept offline oversell
- Terminals push stock **movement events** (`{product, location, delta:-1,
  order_uuid}`), never absolute on-hand. Cloud applies all deltas → true global
  on-hand. Terminals keep a local *estimate* for display + low-stock alerts,
  corrected on each pull.
- Two branches offline both selling the last unit → cloud goes negative on
  reconcile. **This is physics, not a bug** (Foodics/Marn behave identically).
  Handle as a business event: flag negative quant → manager alert.
- Central-kitchen inter-branch transfers are **HQ-authoritative**: terminals
  *request*, cloud *confirms*. Never move stock between branches offline.

### 3. Loyalty points — transaction events, same merge
- Sync `loyalty.history` rows (`+earn` / `-redeem`), never the balance. Balance =
  Σ transactions. Commutative → converges. Earn is always safe.
- Offline redeem is the only risk (redeem at two branches while both offline).
  Mitigate: reconcile flags `balance < 0` → claw back the later redemption or comp
  it; optional policy knob **"redemptions require online"** (earning never does).

## Schema (this commit scaffolds these)

| Model | Side | Purpose |
|---|---|---|
| `mezze.terminal` | both | terminal identity: id, token, branch, `last_acked_seq` cursor |
| `mezze.sync.outbox` | terminal | ordered, durable change journal (`seq`, `res_uuid`, `op`, `payload`) |
| `mezze.sync.cursor` | both | pull watermark per model |
| `mezze.sync.applied` | cloud | reconcile ledger: one row per applied event, `(terminal, res_uuid)` unique = exactly-once + dead-letter + flags |

Every synced model needs a stable global id (`uuid`). `pos.order` has one; add to
`mezze.kds.ticket`, `loyalty.history` events, stock-delta events, cash moves.

## Endpoints (`/mezze/sync/v1/*`, this commit scaffolds these)

| Route | Does | Status |
|---|---|---|
| `register` | mint/return terminal identity + token, assign branch | working |
| `push` | ingest + **APPLY** an outbox batch, dedupe by `(terminal, seq)` + `(terminal, res_uuid)`, ack `up_to_seq` | **LIVE** |
| `pull` | return config/state changed since watermark | **LIVE** |

### pull query (live)
Config flows DOWN, idempotent (re-applying config is safe → no downward outbox).
`since` maps model → the terminal's last watermark. For each `PULL_MODELS` entry
`_pull_model` runs `write_date > watermark` (oldest-first), **branch/company
scoped** (`_pull_scope`: floors/tables by `pos_config_ids`, anything with
`company_id` by the branch's company + shared), projects a curated field set
(`_pull_row`: m2o→id, m2m→ids; products also carry taxes/categ/modifiers), and
returns the new watermark = the last row's `write_date`. **Cursor-paginated**:
`PULL_LIMIT` per model, `more[model]=true` when a page fills, so the terminal
re-pulls with the advanced watermark until `complete`. **Soft deletes** ride
along: `active_test=False` means an archived row returns with `active:false`.
Response: `{changes{model:[rows]}, watermarks{model:iso}, more{model:bool},
complete}`. Verified: initial full pull (branch-scoped floors/tables), empty
re-pull, single-record incremental delta after a write, branch-2 isolation.

### push apply-path (live)
Each event above `last_acked_seq` is applied inside its **own `cr.savepoint()`**,
then recorded in `mezze.sync.applied` (the cloud reconcile ledger):

- **Dispatch by `model`** — `pos.order` → `_apply_sale` (upsert by uuid into the
  branch's cloud session via `sync_from_ui`, server-side tax through
  `_build_lines`; **no loyalty earn** — loyalty rides its own event so it can't
  double-count); `stock`/`stock.delta` → `_apply_stock_delta` (commutative
  `stock.quant._update_available_quantity`); `loyalty`/`loyalty.history` →
  `_apply_loyalty_txn` (signed points + `loyalty.history` row).
- **Exactly-once** — two guards: the `last_acked_seq` cursor (fast path) **and**
  a unique `(terminal, res_uuid)` on `mezze.sync.applied` (catches a replay whose
  seq was reset). A replayed batch is a no-op.
- **Dead-letter** — a poison event (bad product, etc.) is rolled back by its
  savepoint, recorded `state='failed'` with the error + payload, and the cursor
  **advances past it** so one bad event never blocks the terminal's queue.
- **Reconcile flags** — a delta that drives stock/points negative is recorded
  `state='flagged'` (`note=negative_stock` / `negative_points`) — applied, not
  rejected (it's the real "sold offline past zero" business event).
- **Retry-safe** — a Postgres concurrency error re-raises (`_reraise_if_retryable`)
  so the whole request retries on a fresh snapshot instead of half-applying.

Response: `{up_to_seq, applied, skipped, flagged, failed, applied_events:true}`.

## Terminal lifecycle

| Phase | What happens |
|---|---|
| Register | `POST register` → cloud issues `terminal_id` + token, assigns branch |
| Bootstrap | full pull: catalog, taxes, modifiers, floor, users, customers, stock snapshot → set watermarks |
| Steady | worker loop: push outbox, pull deltas |
| Offline | outbox accumulates on disk; UI 100% functional; estimates for stock/points |
| Reconnect | drain outbox from `last_acked+1`; pull merged truth; reconcile flags surface to manager |

## MVP cut vs full engine

| Ship first (80% of value) | Add later |
|---|---|
| Sales push (append-only, by uuid) | Stock delta merge + oversell flags |
| Config pull (watermark) | Loyalty transaction merge |
| Terminal register + bootstrap | Central-kitchen HQ-authoritative flow |
| Outbox + resume-from-seq | Reconcile dashboard for managers |
| Terminal-scoped `pos_reference` | Online-only redemption policy toggle |

The MVP alone gives a terminal that runs a full offline shift and syncs all sales
up — the shippable milestone. Stock/loyalty merge is the second pass.

## Why this is tractable here

- `uuid` + `fire_uuid` idempotency already exist → the exactly-once backbone is done.
- `orders/sync` already upserts by uuid → the `push` handler is batched `order_sync` + a few models.
- The front-end `base` swap already lets the same UI run against local or cloud.
- `mezze.sync.log` was the instinct; `mezze.sync.outbox` is its grown-up form.

The failure mode to avoid is syncing *state* instead of *events*. Get that one
decision right and the rest is plumbing.
