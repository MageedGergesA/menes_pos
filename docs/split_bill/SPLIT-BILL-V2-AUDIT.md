# Split Bill V2 — audit of what exists today

Read before designing. Every claim below names the file and line it came from; nothing
here is inferred from how the feature "probably" works.

Branch `feature/split-bill-v2`, cut from `fe4eddc` (clean tree).

---

## 1. What does the current Mezze "Split" do?

**It opens the Payment screen. That is all.**

```
static/src/cashier/root.xml:299     onSplit="() => this.goToPayment()"

static/src/cashier/components/cart.js:138
    if (p.onSplit) {
        // the payment screen already does partial + mixed tender; "Split" is the
        // name a cashier looks for, so it points at the flow that exists
        out.push({ key: "split", glyph: "◫", label: _t("Split"), ... });
    }
```

The comment is honest about it. The verb exists because cashiers look for the word; it is
wired to mixed tender.

**So Mezze today has SPLIT PAYMENT and does not have SPLIT BILL at all.** There is no
child order, no quantity movement, no family, no server endpoint. This is not a weak
implementation to improve — it is an absent one, which is cleaner ground than it sounds.

## 2. Which parts are stock Odoo?

None of them, in the Mezze surfaces. But Odoo 19 **does** ship a real one that Mezze
users never see, because Mezze runs its own Owl app rather than the native POS UI:

`addons/pos_restaurant/static/src/app/screens/split_bill_screen/split_bill_screen.js`
(229 lines). It is worth reading closely, because it is both the reference for the
interaction and a demonstration of what this phase must **not** copy.

What native does well, and V2 should keep:

* `onClickLine` calls `line.getAllLinesInCombo()` — clicking one line of a combo selects
  the **whole combo**. That is configuration atomicity, already solved, and the same idea
  V2 needs.
* `handlePreparationHistory(original.last_order_preparation_change.lines, new..., line,
  newLine, qty)` — preparation history is **transferred**, not re-fired. That is the
  KDS-safety mechanism in native form.
* Quantity is a click-cycle `0 → 1 → … → max → 0` per line, tracked in `qtyTracker`.
* The split name is a **display** name (`floating_order_name` gets a letter suffix,
  `B`…`Z`), never the accounting sequence. Max 26 parts, enforced by throwing.

What native does that V2 **cannot** adopt:

* **The whole split is client-side.** Lines are created and deleted in the browser's model
  layer and then `syncAllOrders` pushes the result. The client is the source of truth.
* **The relationship is `uiState.splittedOrderUuid`** — UI state, *not a database field*.
  Reload the browser and the family is gone. There is no durable parent/child relation to
  extend, which answers the brief's "inspect stock Odoo's sub-order representation first":
  **there isn't one.**
* No server validation, no transaction lock, no idempotency key, no revision check. Two
  terminals splitting the same order would both win.
* `originalOrder.customer_count -= 1` — covers are decremented by one per split, with
  nothing added to the child. Covers are not conserved.

## 3. Which parts are custom (Mezze)?

Only the verb and its wiring to Payment. Nothing else.

## 4. Does it create a real child/sub-order?

**No.** Not in Mezze. Native does, but only through client-side model writes.

## 5. How are quantities handled today?

They are not. Nothing moves.

## 6. How are taxes recalculated?

Not applicable today. For V2 the relevant fact is that Mezze already refuses to trust
client money: order writes go through `pos.order.sync_from_ui`, so Odoo's own tax engine
produces the amounts (`controllers/main.py:9` design contract). V2 must keep that and send
**intent** (line + qty), never prices.

## 7. What happens to discounts?

An order-level discount in Mezze is **not an order field** — it is a discount *product
line* (`discount_product_id`, `controllers/main.py:1333`). That matters enormously for V2:
a discount is a line like any other, so a naive "move the lines" split would either leave
the whole discount on the root or let a cashier move 100% of it to a child. Policy has to
be explicit.

Line discounts ride on their own line and move with it.

## 8. What happens to already-fired KDS items?

The authoritative state is **`pos.order.mezze_fired`** — a JSON snapshot
`{product_id: cumulative_qty}` of what has been sent to the kitchen
(`models/pos_order.py:16`, written at `controllers/main.py:2159`).

Firing creates `mezze.kds.ticket` rows through `_make_station_tickets` and publishes them;
a re-fire sends only the delta against that snapshot.

**Therefore the V2 KDS invariant is a server-side snapshot transfer:** when qty moves from
root to child, the corresponding fired quantity must move from the root's `mezze_fired`
into the child's, so the child's lines are already "fired" on arrival and any later fire
computes a delta of zero. No new tickets, no UI flag.

## 9. Can the current split be reversed before payment?

No current split exists to reverse.

## 10. How are split orders represented in reporting?

They are not. There is no relation to report on.

## 11. Is seat ownership available?

**No, and the codebase says so in its own words.** The settings catalogue carries a
*disabled* entry:

```
domain/settings_catalog.py:58
('or_seat', 'Order Panel', 'bool', 'false', '', 'disabled',
 'Seat labels on lines — seat model not durable (see R1)', None),
```

`restaurant.table.seats` is a table's capacity integer, not per-line attribution, and
Odoo 19 has no seat field on `pos.order.line`.

**BY SEAT is therefore NOT AVAILABLE.** Per the brief it will be shown disabled with an
honest reason rather than faked.

## 12. Is partial/fractional quantity supported anywhere?

`pos.order.line.qty` is a Float, so fractional quantities are *representable*. But nothing
in Mezze produces them for a sale, and the tax/rounding path has never been exercised with
them. Splitting one bottle three ways would be the first fractional sale in the product.

**Recorded as `SB-DEBT-FRACTIONAL-ITEM` and deferred**, exactly as the brief permits.
Integer quantity movement first.

## 13. What happens if two terminals split the same order simultaneously?

Today: nothing, because there is no split. For V2 the house patterns already exist and
should be reused rather than invented:

* **Row locking** — `SELECT id FROM … FOR UPDATE` is already the pattern
  (`models/delivery.py:229`, `models/outbox_event.py:150`).
* **Idempotency** — `mezze.outbox.event.idempotency_key` with a unique constraint
  (`models/outbox_event.py:80,87`).

There is **no revision/version concept on `pos.order`** today; V2 needs one for the stale
client case.

---

## Other findings that shape the design

**Service charges do not exist in this product.** No model, no field, no code. The brief's
allocation-policy question is therefore **N/A** — there is nothing to allocate, and adding
a service-charge feature would be scope creep.

**Combos are already a parent/child line structure** (`combo_parent_id` /
`combo_line_ids`, native), and Mezze has `_split_combos` for building them
(`controllers/main.py:1080`). Configuration identity exists; V2 reuses it and must never
let a child component move without its parent.

**Covers** live on `pos.order.customer_count`. Native's split decrements it; V2 must not,
because covers have to be conserved across a family.

**Payment state** is `amount_paid` vs `amount_total` on the order; there is no
"partially paid" enum to reuse — it is derived.

---

## What V2 must build (and what it must not)

| Need | Reuse | Build |
|---|---|---|
| Configuration atomicity | `combo_parent_id` / `combo_line_ids` | selection expands to the combo family |
| KDS safety | `mezze_fired` snapshot | server-side snapshot transfer on split |
| Money truth | `sync_from_ui` + Odoo tax engine | never send client prices |
| Concurrency | `FOR UPDATE` precedent | order revision + stale-client UX |
| Idempotency | `idempotency_key` precedent | key on the split commit |
| Split family | — *(native has none)* | durable fields on `pos.order` |
| Authorization | `_security_gate`, capability model, manager elevation | a split capability |
| By seat | — | **nothing: not available, shown disabled** |
| Service charge | — | **nothing: feature does not exist** |
| Fractional item | — | **deferred: SB-DEBT-FRACTIONAL-ITEM** |

The single most important consequence of this audit: **native's relation is UI state, so
there is nothing to extend.** The split family has to be real database fields, and the
split itself has to be a server operation — which is also the only way to satisfy the
brief's concurrency, idempotency and KDS invariants.
