# OCB — what the order-entry flow actually is today (DT-UX6 Phase 0)

Read-only audit of the real drive-thru order-entry path at `dbb6a20`, done before
any OCB design, because the design depends entirely on where order truth lives. Two
findings change the shape of the work and both are stated up front.

## Finding 1 — the pre-fire cart is 100% browser-local

`static/drivethru.html` holds the whole order in a plain array inside the page's IIFE:

```js
var … cart=[], lane=1, …                                   // line 473
function addToCart(p){ var f=cart.find(x => x.id===p.id);
  if(f) f.qty++; else cart.push({id:p.id, name:p.name, price:p.price, qty:1});
  renderCart(); }                                          // line 962
```

Quantity steppers mutate that array in place; removal is `cart.filter(...)`. Nothing
reaches the server until the operator presses **Send to kitchen**:

```js
call('/drivethru/create', {session_id:SID, lane:lane, vehicle:…,
     lines: cart.map(it => ({product_id:it.id, qty:it.qty}))})
```

Consequences, all of which the OCB must handle rather than assume away:

* There is **no server-side draft order**, no `pos.order`, and no `mezze.drivethru`
  record until Send. The car and the order are created by that one call.
* There is **no cart identifier** of any kind — nothing a second screen could name.
* `lane` is a browser variable set by two hardcoded buttons (`[1,2].forEach`).
* A page reload loses the cart entirely. There is nothing to reconstruct from.

**So an OCB cannot read the in-progress order from anywhere.** Something has to
publish it. The brief's instruction applies: *"If the current pre-fire cart is not
server-backed: design the smallest safe real-time projection mechanism."*

## Finding 2 — the drive-thru order taker collects no modifiers, and computes no money

The fire contract *does* support per-line notes and structured items — `_do_fire`
reads `line.get('note') or line.get('mod')`, and `_split_combos` handles combo and
half-and-half carts. The **drive-thru sheet uses none of it**: `grep -c modifier
static/drivethru.html` → **0** (the Register, `pos.html`, has 6). The cart line
schema it sends is exactly `{product_id, qty}`.

There is also no money anywhere in the sheet: `#sfoot` contains only the Send button.
No subtotal, no tax, no total. The per-item price shown in the menu grid is
`product.list_price` from the boot payload.

This matters for the brief's headline example:

```
2 × Classic Burger
    No onion
    Extra cheese
```

The drive-thru Order Taker **cannot produce that data**. Rendering it would mean
either adding modifier entry to the Order Taker — explicitly out of scope
("Do not redesign Order Taker") — or fabricating it, which is forbidden
("No commercial mockup data"). The OCB therefore **renders modifiers faithfully when
they exist and shows nothing when they do not**, and the evidence set will honestly
show orders without modifiers until a later phase adds modifier entry.

## Where money truth can come from

| Stage | What exists |
|---|---|
| While entering | nothing on the server; `list_price` in the browser |
| After Send | a real `pos.order` with `amount_total`, `amount_tax`, real taxes and pricelist |

The customer needs the total *before* Send, which is the whole point of an OCB. The
only honest source is to compute it **server-side from the same inputs the order will
use** — the config's pricelist and the product's `taxes_id`, through Odoo's own
`compute_all` — rather than reimplementing arithmetic in OCB JavaScript. That is the
same calculation path, not a second one. Any residual difference from the eventual
posted order (e.g. an order-level discount applied later) must be disclosed, not
smoothed over.

## Device identity — reuse, do not rebuild

`mezze.terminal` is already the device-identity model and already does everything the
brief asks of a "display identity":

| Brief wants | `mezze.terminal` has |
|---|---|
| token / scoped credential | `token`, stored only as a non-reversible `token_fingerprint` |
| name, id | `name`, `identifier` |
| branch | `branch_id` (`pos.config`) |
| enabled | `active` |
| last_seen | `last_seen` |
| capability scoping | `role` → `authz.ROLE_CAPS` |

The drive-thru board itself already mints one (`identifier='drivethru-<config_id>'`,
`role='terminal'`) in `controllers/drivethru.py:_mint_lane_token`. A parallel device
model would be duplicate architecture, so the OCB display record links to a terminal
for its credential instead of inventing one.

Note the capability sets: `_TERMINAL` is the fully-capable front-of-house station
(pay, fire, drawer). A customer-facing display must not hold any of that — it needs a
read-only principal, which none of the existing roles provides.

## Real-time transport already in the product

| Surface | Mechanism |
|---|---|
| Drive-thru board | `setInterval(poll, 2000)` — HTTP polling |
| KDS | Odoo `bus.bus` + snapshot reconcile (`last_bus_id`) |

The board's 2 s poll is too slow for "the customer sees it as you type", but the
pattern is proven and cheap. A short-interval poll on a tiny payload is the smallest
architecture compatible with the app; the bus is available if measurement says
polling cannot feel immediate. Measure before choosing.

## What the OCB therefore needs

1. A **publish** step: the Order Taker sends its cart snapshot to the server on every
   change (add / qty / remove / clear / send).
2. A **server-side projection** holding the current state per display, so it survives
   a reload, a second worker, and a restart — nothing process-local.
3. A **server-computed** money block, using the real pricing and tax path.
4. A **read** endpoint scoped to one display's own lane, reachable by an opaque
   credential and nothing else.
5. Rendering that shows modifiers when present, and no invented rows when not.
