# Online ordering

Contract for Mezze's **own-channel** ordering — the web storefront the branch owns, as opposed to the
aggregators it rents. Two halves: the **guest journey** (16 steps) and the **restaurant-side
configuration** that makes it a product rather than a page.

**Why it matters commercially:** screen 26 already carries the number — an aggregator order pays
20–25% commission, an own-channel order pays a payment fee of about 2.4%. Every order moved from
Talabat to `mezze.eg` keeps roughly a fifth of its value. The storefront is not a marketing site; it
is the highest-margin till in the business.

**The principle:** the storefront is a *client of the same engines as the POS* — one menu, one price
book, one loyalty ledger, one payment registry, one order board. It renders differently because a
guest is not a cashier; it decides nothing on its own.

---

## 1. The guest journey

| # | Step | The one job | Fails when |
| --- | --- | --- | --- |
| 1 | **Landing** | say what this is, in one screen, and let a returning guest reorder in one tap | it sells the brand instead of the food |
| 2 | **Branch** | pick the kitchen that will cook it — by distance, and honest about closed ones | a closed branch is selectable and fails at payment |
| 3 | **Delivery or pickup** | set the fulfilment mode, because it changes price, time and required fields | mode is asked after the address |
| 4 | **Menu** | browse fast: categories, photos, prices, what is unavailable **now** | 86'd items are still listed |
| 5 | **Item** | one dish, its description, allergens, kcal, and a clear price | allergens are a footnote |
| 6 | **Modifiers** | required and optional groups with min/max enforced, price deltas visible | the total changes without saying why |
| 7 | **Cart** | what it costs, in full, before login — subtotal, fee, VAT, minimum-order gap | fees appear only at payment |
| 8 | **Login or guest** | let them continue as a guest; ask for a phone, not a password | account creation is compulsory |
| 9 | **Address** | pin on a map, zone resolved from it, saved for next time | free-text address with no zone |
| 10 | **Delivery slot** | ASAP or a slot, with **real capacity** and a promise time | a slot is offered that the kitchen cannot make |
| 11 | **Promo** | one code, validated with a reason when it fails | "invalid code" with no reason |
| 12 | **Loyalty** | points balance, what they are worth, what is left after — from the one ledger | points shown that redemption will not honour |
| 13 | **Payment** | the value types this surface may take, per the payment registry, with a wallet/card/cash split | offering a method the branch cannot settle |
| 14 | **Confirmation** | order number, promise time, receipt, and what happens next | a thank-you page with no order number |
| 15 | **Tracking** | live state from the kitchen's own stages: accepted → preparing → ready → rider → delivered | a fake progress bar on a timer |
| 16 | **Reorder** | one tap from history to a filled cart, re-priced today | reorders at yesterday's prices |

Rules that hold across the journey:

- **Nothing is asked twice.** Mode, branch, address and phone are asked once, kept, and shown as
  editable chips afterwards.
- **Every price is complete.** Subtotal, delivery fee, VAT and service are on screen from the cart
  onwards; the total at step 7 equals the total at step 13.
- **Unavailability is honest at the point of choice.** An 86'd item is not orderable
  (`docs/86_OPEN_ORDER_IMPACT.md`), a full slot is not selectable, a branch outside the zone is not
  offered — each with the reason in words.
- **Guest checkout is first-class.** A phone number and an address are enough. The account is offered
  *after* the order, when it has value ("save this address").
- **Arabic and English, RTL both ways** — the storefront inherits the same bilingual rule as the POS,
  including Arabic-Indic numerals on prices.

## 2. What the storefront reads, and never re-implements

| Needs | Reads from |
| --- | --- |
| Menu, categories, photos, modifier groups, min/max | the menu engine (`docs/MENU_ENGINE.md`) — published version only |
| Prices, per-channel pricelist | the same price book as the till |
| Availability / 86 | the availability flag and, when built, the production stage chain |
| Promise times | kitchen load + `flTurnAvg` for pickup, rider capacity for delivery |
| Loyalty balance and burn | the loyalty ledger (`docs/LOYALTY_ENGINE.md`) |
| Payment methods | `VALUE_TYPES` with surface `qr`/`web` (`docs/PAYMENT_VALUE_ENGINE.md`) |
| Order state | the order board — the same rows the kitchen and Orders screens read |
| Guest, addresses, history | `res.partner` |

**A second menu is the failure mode this document exists to prevent.** Aggregator menus already drift
because they are maintained twice; the own storefront must not become a third.

## 3. Restaurant-side configuration

| Setting | What it controls | Rule |
| --- | --- | --- |
| **Domain** | `mezze.eg`, or a branded subdomain per brand | verified before it can go live; HTTPS not optional |
| **Branding** | logo, one accent colour, typography, hero image, tone of copy | inherits the brand; the storefront is not a place to invent a second identity |
| **Opening hours** | per branch, per fulfilment mode, plus exceptions (Ramadan, holidays) | closed means *not orderable*, with the next opening stated |
| **Zones** | delivery polygons per branch, each with fee and promise | an address outside every zone gets pickup offered, not a dead end |
| **Minimum order** | per zone | shown as a **gap** in the cart ("add 40 LE more"), never as a rejection at payment |
| **Delivery fee** | per zone, with free-over threshold | in the cart total from the first item |
| **Slot capacity** | orders per slot, per branch — the kitchen's real throughput | a full slot disappears; capacity is not advisory |
| **Menu publishing** | which menu version the storefront serves, and when | scheduled, previewable, and reversible — the same versioning the till uses |
| **SEO / page setup** | title, description, OpenGraph image, structured data (Restaurant, Menu), sitemap | a storefront nobody can find is a storefront nobody uses |

Two further settings that belong here and are usually missed: **prep-time buffer** (the honest gap
between "accepted" and "ready") and **pause ordering** — which screen 26 already has, and which must
show the guest a closed notice rather than silently accepting orders nobody will cook.

## 4. Odoo mapping

| Design | Odoo 19 |
| --- | --- |
| Storefront | Website + Self-Order / eCommerce, per company |
| Branch choice | `pos.config` / warehouse per branch |
| Menu | published `product.template` set, POS categories |
| Modifiers | attributes + values with `price_extra` |
| Zones, fees, minimums | delivery carriers per zone, or custom zone model |
| Slots | custom capacity model per `pos.config` and time window |
| Guest checkout | `res.partner` created on order, phone as the key |
| Payment | payment providers (Paymob/Fawry/Instapay), plus cash on delivery |
| Order state | `pos.order` / `sale.order` state, exposed to the tracking page |
| Loyalty | `loyalty.program` shared with the POS |
| SEO | website page metadata + structured data |

## 5. What is designed here versus built

- **Built:** the guest journey as a working prototype — `Mezze Online Ordering.dc.html` — covering all
  sixteen steps as a single state machine on a phone-width storefront, reading the same shapes the POS
  uses (menu items with modifier groups, zone fees and minimums, slot capacity, loyalty points,
  payment methods) so it can be pointed at the real engines without redesign.
- **Built already, restaurant-side:** screen 26 Ordering — own-channel versus aggregator economics,
  commission per channel, pause ordering.
- **Built, restaurant-side configuration:** screen 26 Ordering now carries two tabs — *Today* (the
  channel economics and live pre-order slots) and *Storefront setup*, covering §3: domain and
  verification, branding, guest checkout, delivery zones with editable fee/minimum/free-over and a
  promise cap that pushes an over-distance polygon to pickup, opening hours per branch per mode with
  Ramadan/Eid/Friday exceptions, menu publishing (live version, scheduled, own-channel pricelist),
  search and sharing checks, and the slot-capacity producer below.

## 6. Gaps

1. ~~Slot capacity has no producer.~~ **Closed.** Capacity per half-hour window is now derived on
   screen 26 from the line: cooks on the food stations × plate rate ÷ plates per order, trimmed by the
   station running behind its target (bottleneck factor), minus the dine-in orders the floor has
   already committed to that window, minus a safety buffer. Published capacity can be overridden per
   window, and an override above the derived ceiling is flagged as selling more than the line can
   make. Prep buffer is set in the same card and moves every zone promise with it.
3. **Tracking is stubbed against a demo clock** rather than subscribing to the order board. The
   POS-side half of this is now done — the call centre writes real orders onto the board
   (`docs/CALL_CENTER.md` §6) — but the storefront is a separate surface and still runs its own
   clock; it needs the board as a feed, not a copy of the state machine.
4. **Address is a picker, not a map.** A real pin, zone resolution from the pin, and building/floor
   fields are needed before a rider can find it.
5. ~~No SEO surface.~~ **Closed** — the checks live in Storefront setup; Arabic pages still carry no
   hreflang, which the panel reports rather than hides.

## 7. Acceptance

Land, pick a branch that is open, choose delivery, add a dish whose required modifier group refuses to
be skipped, and watch the cart show subtotal, fee, VAT and the **minimum-order gap** before any login.
Continue as a guest with a phone number, pick a saved address whose zone sets the fee, take the last
slot in a window and see it disappear for the next guest. Enter a bad promo and get told *why*. Redeem
points and see the balance, its cash value and what remains. Pay by card, land on a confirmation
carrying an order number and a promise time, watch tracking move accepted → preparing → ready →
rider → delivered, and reorder the whole basket in one tap at today's prices.
