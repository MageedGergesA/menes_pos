# Mezze KDS — domain state machine + V2C Phase-0 decisions

Authority = **`mezze.kds.ticket`** (NOT Odoo Enterprise `pos.prep.*`; see KDS-REUSE-DECISION).

## Ticket state machine (`models/kds_ticket.py`)
`fired → accepted → preparing → ready → served` (forward-only; skips allowed) · `cancel` reachable from
any live state · `served`/`cancel` are **terminal**. `action_recall` steps back one state (kitchen mis-bump;
refuses at `fired`). Every transition is row-locked (`SELECT … FOR UPDATE`) → concurrent bumps resolve to
one logical effect. State is **ticket/station-level**.

## V2C Phase-0 decisions
- **D–F Cancellation cascade (FIXED):** a **VOID** (item never made) now cascades to the kitchen.
  `cancel_for_order(order)` cancels every LIVE ticket to `cancel` — row-locked, idempotent, terminal-safe
  (served/cancel untouched; never destructively deletes a fired ticket). Exposed at **`POST /orders/void`**
  (manager `orders.void` capability, object-scoped to the order, signature-required), which publishes the
  cancellation batch through the **transactional outbox** (delivered after commit). Distinct from `/orders/
  comp` (made+served, money-only, KDS ticket stands).
- **G Item-level completion → DEFERRED for v1.** State stays ticket/station-level. Rationale: whole-order
  void is the safety-critical case and is covered; per-dish bump on a multi-dish station ticket needs a
  per-line state machine + stable pos.order.line↔kds.line linkage (absent today) — not worth the concurrency/
  reporting complexity for v1. Line-level void within a multi-dish ticket is deferred WITH item-level.
- **H Priority/rush → use existing late-by-time only.** The order model carries no priority/rush field;
  we do NOT invent a priority subsystem. Urgency = elapsed-vs-threshold (below).
- **I Allergen/note → use the existing free-text line `note`.** No structured allergen data exists; we do
  NOT synthesize medical/allergen semantics from free text. The UI shows the note as a special-instruction,
  not a certified allergen marker.
- **J–K Timer / Late → config threshold, separate from workflow state.** Late is `elapsed > threshold`, a
  timing CONDITION layered on the business state (`Preparing + Late`), never a replacement state. Threshold
  belongs to the KDS/branch config (reuse the settings mechanism), not hardcoded JS SLA numbers.
- **L Concurrency / M Realtime:** reuse the existing row-lock + transactional-outbox + bus + poll/reload;
  do NOT add a second realtime architecture. Bus event is advisory; the server snapshot is authoritative.

## Not changed
`/kds/transition` (kitchen-side accept/preparing/ready/recall/cancel), `/kds/state` (snapshot+cursor),
`/orders/fire` + `/courses/*` (held courses stay hidden until fired) — all unchanged.
