# Mezze POS — Self-Service Guide

Mezze's customer channels let guests browse and order themselves: QR menu, table-QR
ordering, pickup, and kiosk. All are bilingual (English/Arabic, RTL) and mobile-first.
Prices, taxes, combos, and modifiers are always recomputed on the server — a customer
cannot inject a price or discount.

## QR menu (browse)

- A QR code opens your **real** catalog (categories, products, options) — no mock
  data. Great as a contactless menu even without ordering.

## Table-QR ordering

- Each table has its own QR. Scanning it lets the guest add items to **that table's**
  open order, which fire to the kitchen exactly once.
- The table QR is a validated bearer token — a guest cannot tamper with the table
  number.
- **Table QR (ordering) is separate from Payment QR (bank)** — different codes,
  different purpose.
- Guests can add more through the meal, then pay at the table or online.
- Two guests scanning the same table at once is safe (server serialises the table).

## Pickup

- A guest orders for pickup from the menu and pays **at the counter**; the order
  becomes a canonical Mezze order, fires to the kitchen, and the guest follows a
  status link.

## Kiosk (pay-at-counter)

- The in-store kiosk (`kiosk.html`) supports eat-in and takeaway ordering, with an
  inactivity reset and a privacy clear between guests.
- Kiosk v1 is **pay-at-counter**: the order is created **unpaid** and paid at the
  till. Mezze never fakes "customer chose cash → pretend collected."
- Native card-terminal kiosk payment is **not** claimed (upstream native kiosk is
  Adyen/Stripe-terminal-only). Physical kiosk hardware is **PHYSICAL CERT PENDING**.

## Channel pause / resume

- Pause or resume any self-order channel (e.g. stop table-QR during a rush). A paused
  channel refuses new orders and will not auto-open a session.
- **By-channel analytics** report orders, revenue, average order value, payment mix,
  cancellations, and top items per channel.

## Availability

- An "86'd" (sold-out) item is blocked across **all** self-order channels in real
  time, revalidated at checkout.
