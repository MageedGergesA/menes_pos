# OCB — security model

The customer display is a public route, because a screen bolted to a post in a lane
cannot log in. That makes the credential the entire boundary, so it is designed as one
rather than checked as one.

## The shape of the boundary

```
POST /mezze/api/v1/ocb/state     { token }          ← ONE input
GET  /mezze/ocb/<display_token>                     ← token in the path
```

The read endpoint accepts **no lane, no display id, no config id and no order
reference**. There is nothing to increment and nothing to substitute. A Lane 1
credential cannot express a request for Lane 2's order, because the request has no way
to say "Lane 2".

This is the difference between *isolation that is enforced* and *isolation that is
structural*. `/ocb?order_id=123` — the shape the brief warns against — is not
tightened here; it does not exist.

| Attack | Result |
|---|---|
| Unknown token | 404 `display_unavailable` |
| Token under 24 chars | 404, without a lookup |
| Disabled display | 404, the **same** answer as unknown |
| Revoked terminal | 404 |
| `{token: lane1, lane: 2, display_id: N, order_id: N}` | Lane 1's order, unchanged |
| Guessing at scale | rate-limited, 240/min per token prefix |

Unknown, disabled and revoked deliberately return one indistinguishable answer.
Different errors would tell a prober which guesses were closer.

## The credential

A `mezze.terminal`: 32 bytes from `secrets.token_urlsafe`, stored **only** as a
non-reversible fingerprint, with the platform's existing rotation and revocation. The
raw value is returned once, at provisioning, and never again.

The terminal is created at the narrowest existing role rather than a station's, so a
credential that escapes carries no pay, fire, drawer or admin capability. In practice
the display never calls a capability-gated endpoint at all — but "it does not use the
rights" is a weaker guarantee than "it does not have them".

## What crosses to the customer

A fixed contract, asserted by test both for the fields it must not contain and for its
exact shape:

```json
{"ok": true,
 "display": {"name": …, "lane": …, "lang": …},
 "state": "idle|ordering|confirmed",
 "revision": 12,
 "order": {"lines": [{"qty","name","modifiers","note","line_total"}],
           "money": {"subtotal","tax","total"},
           "currency": {"name","symbol","position","decimals"}}}
```

Never present: employee identity, cashier or user ids, tokens or fingerprints, session
data, product ids, cost, margin, tax ids, KDS routing, database ids, POS config
internals, vehicle free text. It is not a serialized `pos.order`; it is a screen's
worth of order.

## Transience and cache

`Cache-Control: no-store, no-cache, must-revalidate, private` plus `Pragma: no-cache`
and `Referrer-Policy: no-referrer` on the page, so Back, reload or a shared kiosk
cannot resurrect the previous guest's transaction.

Nothing is written to `localStorage` or `sessionStorage` — asserted by test against
the page source, not by inspection.

On clear and on confirm the projection is **erased from the row**, not merely stopped
from rendering. That distinction was found by a negative control: an earlier sabotage
kept the payload and every test still passed, because `_snapshot` only reads it while
ordering. Never served is not the same as gone, and a finished guest's order should
not sit in a database waiting for the next bug.

## CORS

Deliberately **not** opened on the customer read, unlike some older endpoints in this
module. A display appliance loads the page from the same origin it polls; nothing
needs cross-origin access to a customer's order.

## Read-only by construction

The customer surface has no buttons and calls no mutating endpoint. It cannot change
an order, a payment, a vehicle stage or a KDS ticket. Publishing is a separate,
staff-authenticated endpoint carrying `ORDERS_WRITE`.
