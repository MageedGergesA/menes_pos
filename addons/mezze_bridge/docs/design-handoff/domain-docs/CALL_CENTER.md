# Call centre

Contract for **phone ordering** — the channel the competitive audit found entirely absent from the
system despite being, in Egypt and the wider region, still one of the largest delivery channels a
branch has. A guest who calls is not a worse guest than one who taps; they are usually the *older,
richer, more loyal* one, and today they are served by a notebook beside the till.

**The principle:** the call centre is another *client of the same engines* — one guest record, one
menu, one price book, one zone map, one payment registry, one order board. The agent screen exists
because a person on a phone cannot see; it decides nothing on its own.

**Built:** screen 33 Call centre in `Mezze POS v3.dc.html`.

---

## 1. The call, as one flow

Seven steps, shown as a strip across the top of the agent screen; the strip marks what is done, what
is current, and refuses to move on what is missing.

| # | Step | The one job | Fails when |
| --- | --- | --- | --- |
| 1 | **Number** | show the incoming number, the line it arrived on, and a live call timer | the agent types the number the switch already knows |
| 2 | **Guest** | look the number up and put the record on screen — name, visits, lifetime spend, points, tags | the agent asks a twelve-visit regular for their name |
| 3 | **Address** | saved addresses first, each with its zone, fee and promise; a new one is taken *with its zone* | a free-text address with no zone, priced later |
| 4 | **Previous orders** | last orders with a one-tap **Repeat**, re-priced at today's menu | reorders at yesterday's prices, or retyped by ear |
| 5 | **Order** | build or amend the basket: usual items, favourites, quantities, 86 refused at the point of choice | an 86'd dish is promised on the phone |
| 6 | **Branch** | the nearest branch that can *actually* take it — open, and serving the address zone | the call is taken by a branch that cannot cook it |
| 7 | **Payment → Send** | a value type the registry allows on a phone order, then send to the kitchen with a number and a promise | the guest hangs up without an order number |

Rules that hold across the call:

- **Nothing is asked twice.** Number, name, address and history come from the record; the agent
  confirms, they do not collect.
- **Every refusal names itself.** A closed branch, a zone no branch serves, an 86'd item, a basket
  under the zone minimum — each blocks the send with the reason in the agent's words, above the Send
  button, before the guest is told anything.
- **The minimum is a gap, not a rejection.** "Forty pounds more" is something an agent can *sell*;
  "under the minimum" at the end of a call is a lost order.
- **The promise is the zone promise plus the prep buffer** — the same arithmetic the storefront and
  screen 26 use, so the phone cannot promise what the web would not.
- **An abandoned call is a record.** Every call is logged against the number whether it ordered or
  not, so the queue produces a call-back list rather than a blank in the report.
- **Arabic and English, RTL both ways**, including Arabic-Indic numerals on the phone numbers.

## 2. What the call centre reads, and never re-implements

| Needs | Reads from |
| --- | --- |
| Guest, phone, visits, spend, points, tags | the guest record — `res.partner` (`docs/LOYALTY_ENGINE.md`) |
| Saved addresses and their zones | the address book on the partner, zones from the zone map |
| Zone fee, minimum, free-over, promise | the same `ORD_ZONES` the storefront reads (`docs/ONLINE_ORDERING.md` §3) |
| Prep buffer | screen 26 Storefront setup — one buffer for every channel |
| Menu, prices, favourites | the menu engine, published version only (`docs/MENU_ENGINE.md`) |
| Availability / 86 | both availability sources — the product flag the Menu screen's 86 control writes and the name-keyed map the kitchen sets from a ticket — refused at the point of choice (`docs/86_OPEN_ORDER_IMPACT.md`) |
| Payment methods | `VALUE_TYPES` filtered on the `call` surface — Cash, Card, Wallet, Loyalty and House account carry it; nothing else is offered (`docs/PAYMENT_VALUE_ENGINE.md`) |
| Branch list, distance, opening state | the branch/`pos.config` records |
| Sent orders | the order board — one order, the same rows the Orders screen and the bill read — plus a KDS ticket per station |

**A second guest database is the failure mode this document exists to prevent.** Phone orders
written into a notebook — or into a call-centre tool with its own customer list — are how a chain
ends up with three versions of the same guest and none of them loyal.

## 3. Agent-side, beyond one call

| Surface | What it carries |
| --- | --- |
| **Queue** | waiting calls, longest first, each showing whether the number is known; answer takes the call and loads the record |
| **Header** | calls waiting, calls handled this shift, average handle time, abandoned count |
| **Call log** | the last calls closed by this agent, with order reference or "no order", and how long each took |

## 4. Odoo mapping

| Design | Odoo 19 |
| --- | --- |
| Agent screen | POS session on a call-centre `pos.config` (no drawer, delivery channel) |
| Caller lookup | `res.partner` search on `phone` / `mobile` |
| Saved addresses | child partners of type *delivery*, each tagged with a zone |
| Basket | `pos.order` lines on the delivery channel pricelist |
| Repeat last order | previous `pos.order` re-priced against the live pricelist |
| Branch routing | `pos.config` / warehouse per branch, zone served per branch |
| Payment | payment methods from the same registry — cash on delivery, card at the door, payment link, loyalty, house account |
| Loyalty | `loyalty.program` shared with the POS |
| Sent order | `pos.order` on the order board (written on send), then the delivery screen and the rider |
| Call log | `mail.activity` / a call model on the partner |

## 5. Designed here, not built

- **CTI integration.** The screen assumes the number arrives from the switch. Which switch, and how
  (SIP header, softphone popup, webhook) is an integration decision, not a design one.
- **Call recording and consent.** Required in several of the markets Mezze wants; needs a consent
  line at answer and a retention rule.
- **Outbound**: the call-back list the log implies, and the "your order is at the door" call.
- **Agent scripts** for upsell — deliberately left out until the basics are honest, because a script
  on top of a wrong promise only makes the wrong promise faster.

## 6. Gaps

1. ~~The sent order does not write to the shared order board.~~ **Closed.** Send now writes one
   order onto the same board the Orders screen, the bill and the settle flow read — with the real
   lines (not synthesised ones), the guest and phone number on the order, and a note carrying the
   address, zone, tender and promise — and fires **one kitchen ticket per station**
   onto the KDS, the way the line actually receives an order. A tender captured on the call
   (loyalty, house account) posts with the order; cash and card at the door leave it unpaid until
   the rider settles. **The delivery fee is a line on the order**, not prose in a note, and phone
   prices are quoted VAT-inclusive — so the total the agent reads out, the amount on the board and
   the money the rider collects are the same number. The kitchen ticket carries the fulfilment
   channel, so a phone delivery reads as *Delivery* on the KDS, never as a counter order.
2. **Distance is a static number per branch,** not computed from the address pin. The map pin is the
   same gap the storefront carries (`ONLINE_ORDERING.md` §6).
3. **Modifiers are not on the call yet.** The basket takes items and quantities; required modifier
   groups — the ones the storefront enforces — need the same enforcement here before a call can
   order a dish that has them.
4. **No hold, transfer or conference** — real call handling, not order handling.

## 7. Acceptance

Answer the top call from a known number and watch the guest, their tags (including an allergy), their
usual items and their last two orders arrive without a question being asked. Repeat the last order in
one tap, see it re-priced at today's menu, and watch an 86'd line refuse to be sent with the reason
named. Choose delivery, pick the saved address, and see the zone set the fee, the minimum and the
promise; drop the basket under the minimum and watch the gap appear as pounds to add rather than a
refusal. Switch to the address in a zone only the closed branch serves, and watch every branch
explain itself. Pick cash on delivery, send, and read back an order number and a promise time. Hang
up, and find the call in the log — then answer an unknown number, take a name and an address with its
zone, and end with a guest record that did not exist when the phone rang.
