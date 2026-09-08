# Order state machine — one lifecycle, everywhere

This is the canonical order lifecycle every surface reads: Orders/POS, KDS, Call centre, Delivery,
Rider, Storefront/Online Ordering tracking, Kiosk/QR self-order. No surface owns a second timer.

## Canonical states

```
draft → accepted → sent_to_kitchen → preparing → ready
  → assigned → picked_up → out_for_delivery → delivered
```
Pickup/dine-in orders skip `assigned`/`picked_up`/`out_for_delivery` and go `ready → delivered`
(collected/served) or `ready → picked_up` for a pickup counter handoff.

Side states, reachable from anywhere before `delivered`:
- `cancelled` — guest or branch cancelled before it left the kitchen
- `failed` — a delivery attempt failed (see `docs/DELIVERY_ENGINE.md` for the failure taxonomy)
- `partially_refunded` — settled, then part of the value returned (see `docs/GUEST_RECOVERY.md`,
  `docs/COMP_ACCOUNTING.md`)

## One record, many translations

Every surface reads the same order record's `state` and translates it into its own vocabulary:

| Canonical state | Orders board | KDS | Guest tracking (storefront/online) |
|---|---|---|---|
| accepted | Open | — | "We have your order" |
| sent_to_kitchen | In kitchen | New ticket | "The kitchen has it" |
| preparing | In kitchen | Cooking | "On the line" |
| ready | Ready | Bump | "Ready" |
| assigned | Dispatched | — | "Rider assigned" |
| out_for_delivery | On the way | — | "On its way" |
| delivered | Closed | — | "Delivered" |

No surface stores its own copy of "where the order is." `Mezze Online Ordering.dc.html`'s guest
tracker (`TRACK`) is a display-only translation of these five stages — in this standalone demo
file it advances a local `trackAt` because there is no live backend to subscribe to, but the
comment on `TRACK` states explicitly that production reads the order's own `state` by reference.
The same rule applies to the main prototype's QR self-order tracker (`isTrack` in
`Mezze POS v3.dc.html`) — it already reads `S.tick`/board data, not an independent clock.

## Backend requirement (Claude Code)

- One `state` field on the order record (Odoo: extend `pos.order` / `sale.order` with this
  enumeration rather than inventing a parallel status table).
- State transitions are server-authoritative and versioned (a monotonic `state_seq` or timestamp)
  so two surfaces polling/subscribing never show conflicting "current" states.
- Guest-facing surfaces (storefront, SMS, WhatsApp) subscribe to the same record — push over
  polling where the channel supports it (websocket/long-poll for storefront tracking, provider
  webhook for SMS/WhatsApp delivery receipts).
- `cancelled`/`failed`/`partially_refunded` are terminal-adjacent: reachable from most states,
  each with its own required audit fields (who, when, why) already specified in
  `docs/GUEST_RECOVERY.md` and `docs/DELIVERY_ENGINE.md`.

## Park/Recall (closure pass 15F)

`Active → Parked → Active (recalled)` is a side-branch of the same order state, not a separate
lifecycle. Park means: temporarily remove a check from the register's active working set while
the complete order — lines, structured modifiers, notes, seat, course, prices, discounts,
part-payment, fired status, timestamps, employee — is preserved unchanged and exactly as-is.
It is not cancellation, payment, kitchen completion, or deletion, and it never rebuilds a line
from rendered text — the parked and recalled record is the same object.

In Claude Design, `checks{}` is the single canonical owner (`state:'Open'|'Parked'`,
`parkedAt`); Register's tab bar and Orders → Parked both read off it live — Orders never holds
its own independently-editable copy of a parked check.

**Odoo mapping (Claude Code):** do not build a separate "parked order" backend model. Odoo 19's
POS already lists active/in-progress orders (draft `pos.order` records) that can be reselected
and loaded back into the register — map Park to leaving the order in that draft/active state,
and Recall to loading it back into the session UI, rather than introducing a parallel store.

**Keep separate:** the Kitchen Preparation Display's own "Recall" (undoing a preparation-stage
bump, e.g. `recallLast()`/`bumped` stack in Claude Design) is an unrelated concept — a KDS
station action, not an order lifecycle transition. Do not conflate the two in naming or in the
backend model.

## Fired-line amendment rule (closure pass 17C)

Within a check, each LINE (not just the order as a whole) carries its own `status`. The rule,
one owner, everywhere:

```
NEW / HELD  → freely editable (modifiers, note, qty, combo selection, direct decrease)
FIRED (or any later state) → historical Kitchen instruction. Direct mutation of anything
  Kitchen-relevant is blocked. Change happens only through:
    - an explicit ADDITIONAL fire (new unfired qty/line)
    - Cancel (existing void workflow)
    - Refire/Remake (existing recovery workflow)
```

`canDirectlyEditLine(l)` (Register, `Mezze POS v3.dc.html`) is the one predicate every entry
point calls — line Edit, the qty stepper's `+`/`-`, and the qty keypad. There is no
`comboCanEdit`/`hhCanEdit`/`registerCanEdit` split; the combo-only guard built in pass 17B was
folded into this general rule, not kept alongside it. Increasing a fired line's quantity does
not rewrite the historical line — it creates or merges into a separate NEW line for the same
item/mods/note (`addAnother()`), so the next Send fires only the new demand, never re-sending
what Kitchen already has. Decreasing or editing a fired line is blocked outright with "Already
sent to kitchen — use Cancel, Refire, or add another item to change the kitchen order."

Handheld needs no equivalent guard — it is safe by construction, not by a parallel check: a
fired line is removed from `hhDraft` (the only editable collection) the moment it fires and
lives on only in read-only `hhLog`; there is no code path that reopens or mutates it. Verifying
Handheld's fired-line safety is a non-finding, not a gap — its data shape makes the bug this
pass fixed in Register structurally impossible there.
