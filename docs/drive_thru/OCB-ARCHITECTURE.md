# OCB — architecture

The Order Confirmation Board shows a drive-thru guest their order **while the operator
is typing it**, so a wrong item or a surprising total is caught before anything is
cooked. It is an accuracy device. It is not signage, not a second POS, not a KDS and
not an order-status screen.

## The problem the design had to solve

The drive-thru cart is a JavaScript array in the operator's browser. No `pos.order`
and no `mezze.drivethru` record exists until **Send to kitchen** creates both in one
call. There is no draft, no cart id, nothing on the server to read
(`OCB-DATA-FLOW-AUDIT.md`).

So the operator's page **publishes** and the server **projects**:

```
Order Taker (browser cart)
        │  POST /ocb/publish   — the WHOLE cart, every change
        ▼
mezze.ocb.display              — server projection: state, revision, payload
        │  ^ money computed here, via the real pricelist + taxes.compute_all
        │
        │  POST /ocb/state     — the display's own credential, nothing else
        ▼
/mezze/ocb/<token>             — the customer's screen, polling every 900 ms
```

## Why each piece is the way it is

**The whole cart, every time.** There is no incremental protocol. A dropped publish
cannot leave a guest looking at half an order, and the next keystroke repairs
whatever was missed. It also means no reconciliation logic to get wrong.

**Money on the server.** The display never computes a price. `_price_lines` runs the
branch pricelist and each product's own taxes through Odoo's `compute_all` — the same
engine the eventual order uses, not a second implementation in display JavaScript.
Pricing is batched by quantity: a pricelist can have quantity breaks, so one price per
product would be wrong, but the distinct quantities in a cart are bounded by the menu
rather than by how much was typed, so the work stops growing with the order.

**State in the database.** Four workers, a page reload and an Odoo restart all have to
show the same order. Process-local state cannot do that. Pre-fire there is no
`pos.order`, so this projection is the only server copy — not a redundant one — and it
is erased the moment the order ends.

**A monotonic `revision`.** Polling can deliver responses out of order, and a customer
must never watch their order go backwards. The display drops anything not strictly
newer than what it has already applied.

**Polling, not the bus.** The board already polls, the payload is tiny, and a 900 ms
interval reads as immediate. The bus is available if measurement ever says otherwise;
introducing it now would be architecture without a reason.

## Lane binding

A display serves exactly one lane, and this is structural rather than checked. The
public read takes **one** input — an opaque credential that resolves to exactly one
display row, whose `lane` is the only lane it can ever report. There is no lane
parameter, no display id and no order reference in the contract to substitute. A test
throws `lane`, `display_id`, `config_id` and `order_id` at it and still gets Lane 1.

Publishing is lane-addressed by the operator (`config_id` + `lane`), authenticated as
staff, and resolves to that lane's display or to nothing at all.

## Display identity

Reuses `mezze.terminal`, the model that already stores an opaque token as a
non-reversible fingerprint and already carries branch, active and rotation. A parallel
device architecture would have duplicated all of it. The terminal is created at the
narrowest existing role rather than a station's, so a misused credential carries no
pay/fire/drawer rights.

Provisioning is a method, not a wizard — a display is set up once and then a kiosk
browser is pointed at the URL forever:

```python
display, token = env['mezze.ocb.display']._provision(config, lane=1, lang='en_US')
url = '/mezze/ocb/%s' % token          # the raw token is returned ONCE
```

## States

`booting → idle → ordering → confirmed → idle`, plus `reconnecting` (what the display
concludes when it cannot reach the server; never a stored state) and a 404 for a
credential that is unknown, disabled or revoked.

Confirmation holds for `CONFIRM_SECONDS` (8) and then returns to idle on its own, so a
thank-you never greets the next car.

## What the customer never sees

Employee identity, cashier or user ids, tokens, session data, product ids, cost,
margin, tax ids, KDS routing, database ids, POS config internals, vehicle free text.
The response is a fixed small contract — `display`, `state`, `revision`, `order` — and
a test asserts both the absent fields and the exact shape.

## Order Taker integration

One indicator and no redesign. A board that is configured but has not polled within
15 s reads **OFFLINE** rather than being assumed visible, because a confirmation
nobody can see is worse than none: the operator stops double-checking. A missing or
broken board never blocks order entry.

## Known limits, recorded

* **Modifiers render but the drive-thru Order Taker collects none.** The contract
  carries them and the display shows them; the drive-thru sheet sends
  `{product_id, qty}` only. Adding modifier entry is a later phase.
* **Pre-fire money is the best available truth, not the posted total.** It is computed
  from the same pricelist and taxes the order will use, but an order-level discount
  applied after Send would not appear on the confirmation the guest saw.
* The OCB binds to the **ordering** lane, deliberately, not to Payment's current-car
  recommendation — that debt stays where QA7 recorded it.
