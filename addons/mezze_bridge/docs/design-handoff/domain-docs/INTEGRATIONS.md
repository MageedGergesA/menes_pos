# Integrations

The aggregator connector, as designed in **screen 22 Channels → Channel setup**, and specified for
implementation. Every state and every refusal in this document exists in the prototype — this is a
spec of built behaviour, not a wishlist.

---

## Why states, not a toggle

A channel is four things at once: a **credential**, a **token clock**, a **menu mapping** and a
**call budget**. Any one of them can be the thing that is broken, and they fail differently. So the
connector has six operator-facing states, each of which names a consequence:

| State | What is true | What it costs |
|---|---|---|
| **Connected** | orders arrive, menu matches, token fresh | — |
| **Authenticating** | token refresh in flight | new orders queue at the provider for minutes |
| **Mapping required** | their catalogue has items ours does not recognise | a kitchen ticket nobody can make |
| **Rate limited** | over the provider's call budget | menu changes the guest cannot see yet |
| **Paused** | we closed the channel | nothing — the only state we chose |
| **Error** | connection refused | revenue arriving at the provider, never reaching us |

**Error is not a warning.** The provider keeps taking orders; they just never arrive. The UI says
so in those words, because "connection error" reads as a technical problem when it is a revenue
problem measured per minute.

Own channels (Mezze app, QR table, Kiosk) have no provider and no token — they write to the order
board directly — but they carry the same state vocabulary so a row means the same thing everywhere.

## Actions, and what they refuse

- **Retry now** — only offered in `error`; refused elsewhere with "the connection is not in error".
  A second failure means the credential, not the network, and the message says to go to the
  provider dashboard.
- **Re-authenticate** — moves to `authenticating`. Orders already accepted are explicitly safe.
- **Map the items** — jumps to Menu mapping scoped to that channel.
- **Match by name and size** — bulk-matches, and states that anything it could not match stays
  unmapped **rather than guessed**. A wrong auto-match is worse than an unmapped item.
- **Batch the pushes** — the fix for `rate limited`: one call per change set instead of one per
  item. Order polling was never the cause and is never throttled to fix it.
- **Pause / Resume** — sets us closed at the provider. Orders in flight still arrive.

---

# Provider sections

## Talabat

- **State in prototype:** Rate limited — 591 of 600 calls used; a 14:00 price change pushed one call per item
- **Auth:** OAuth 2 client credentials. `POST /oauth/token` with `client_id` / `client_secret`,
  60-minute access token, refresh before 15 minutes remain.
- **Account:** one credential per branch (`MZ-CAI-Downtown-01`). Branch identity is on the
  credential, not a parameter — a shared credential across branches is how an order lands at the
  wrong kitchen.
- **API version:** v2 (2026-04).
- **Order delivery:** webhook, with a 30-second reconcile poll as the safety net. `POST /webhook/order`
  → `202` immediately, then accept/reject as a separate call. Never do business logic inside the
  webhook response.
- **Endpoints to implement:**
  - `POST /orders/{id}/accept` — body carries our prep estimate in minutes
  - `POST /orders/{id}/reject` — body carries a reason code from a fixed enum (see reject reasons below)
  - `PUT /menu` — full catalogue push, idempotent by item external id
  - `PATCH /menu/items/{extId}/availability` — the 86 path; must be a single item call, not a menu push
  - `PUT /store/status` — open / closed / busy, used by Pause
- **Rate budget:** 600 calls/hour. Prototype shows 412. Menu pushes batch; availability patches do
  not count against the same bucket in v2, which is why 86 stays instant while a price change waits.
- **Commission:** 22%, on gross including delivery fee. Posts to its own journal.
- **Payout:** weekly, Wednesday, for the prior Mon–Sun. Reconciled in the Payouts tab — commission
  and adjustments are separate lines, never netted before they land.
- **Gotcha:** their order id is not unique across branches. Key on `(branch, orderId)` or duplicates
  will merge. The prototype's reject reasons include "Duplicate from the aggregator" because this
  happens in practice.

## Elmenus

- **State in prototype:** Error — signature rejected, 401 on six consecutive webhooks, circuit open since 15:33; underneath it 104 of 112 items are mapped, with the 8 unmapped named
- **Auth:** static API key in `X-Api-Key`, plus HMAC-SHA256 signature on every inbound webhook
  (`X-Signature`, body + shared secret). Reject unsigned webhooks; do not "accept and log".
- **Account:** `mezze-downtown` slug.
- **API version:** v1.4.
- **Order delivery:** webhook only, no reconcile endpoint. **This is the risk:** a missed webhook is
  a lost order with no way to discover it. Implement an inbound sequence-number check and alarm on
  a gap.
- **Endpoints to implement:**
  - `POST /v1/orders/{id}/status` — one endpoint for accept, reject and ready, distinguished by a
    `status` field
  - `POST /v1/catalogue` — accepts or rejects the **whole** push; 8 unmapped items reject all 112.
    This is why Mapping required is a blocking state rather than a partial one.
  - `POST /v1/catalogue/availability` — batch of `{extId, available}`
- **Rate budget:** 300/hour. Prototype shows 186.
- **Commission:** 18% on gross excluding delivery fee.
- **Payout:** weekly, Thursday. The prototype seeds one payout as **short** — the reconciliation has
  to survive a provider paying less than the statement.
- **Mapping model:** they key on their own item id, so our map is
  `product.product ← external identifier (provider, extId)`. Size and modifier variants are separate
  external ids on our variants — the 8 unmapped items in the prototype are all variant-level
  ("Mixed Grill · half", "Mint Lemonade · 1 L"), which is the realistic failure.

## Mezze app (own)

- **State:** Connected. First-party session, no token, no commission.
- **Delivery:** direct write into `pos.order`. No webhook, no queue, ~60 ms.
- **Why it is in this list:** so the operator compares like with like — the app's 0% next to
  Talabat's 22% is the whole argument for pushing guests to own channels, and it belongs in the
  same table as the aggregators.

## QR table (own)

- **State:** Connected. Direct write, attaches to the open table check on the Floor.
- **Note:** the order must join an existing check rather than create a new one, or a table pays twice.

## Kiosk (own)

- **State:** Connected, but the log carries `Device offline · orders held on the kiosk`.
- **Delivery:** device pairing (see `docs/DEVICE_PLATFORM.md`) with a local-first buffer. A kiosk
  that cannot reach the branch keeps taking orders and holds them; the fleet screen counts them as
  "orders held on devices" and they are **not** in the branch totals until they arrive.

---

## Shared implementation notes for Claude Code

**Credentials** live in `ir.config_parameter` per channel per branch, never in code and never in the
POS client. The client only sees state.

**Order ingestion** is one path regardless of provider:

```
provider webhook → verify signature → normalise → pos.order (draft)
  → availability check → accept or reject with reason → KDS tickets per station
```

Normalise **before** business logic, so 86 rules, prep estimates and station routing are provider-agnostic.

**Item mapping** is an external identifier per product/variant, one row per `(provider, extId)`.
Never match on name at runtime — the "match by name and size" action is an authoring-time helper
that writes explicit rows, and it deliberately leaves unmatched items unmatched.

**Reject reasons** are a fixed enum shared by all providers, mapped to each provider's own codes at
the edge: kitchen at capacity, item unavailable, outside delivery zone, closing soon, duplicate from
the aggregator.

**Idempotency:** every inbound order carries `(provider, branch, orderId)` as the natural key. Every
outbound mutating call carries an idempotency key. Providers retry; assume every webhook arrives twice.

**Backoff:** exponential with jitter on `429` and `5xx`, and a circuit breaker that trips to `error`
state rather than retrying silently. Silent retry is how a channel is down for an hour without
anyone knowing.

**Clock:** prep estimates go out in minutes and are read from the branch's live prep clock, not a
static config. A channel promising 20 minutes while the kitchen runs at 40 is worse than being paused.

**Commission and payout** are accounting, not integration: each channel is a `pos.config` plus its
own sales journal, so commission, adjustments and payouts stay on their own accounts and reconcile
against a statement.

---

## Bilingual

Every state name, consequence line and action goes through `tr()`; counts and latencies through
`N()`. Provider names, account slugs, API versions and endpoint paths stay Latin — they are
identifiers.
