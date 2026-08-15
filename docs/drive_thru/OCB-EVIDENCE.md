# OCB — evidence

Captured against the committed HEAD on a real runtime with the branch's real
catalogue. No invented menu, no invented tax rate, no invented discount, no fake
vehicle. The tax shown ($22.26 on $148.40) is the demo products' own tax computed by
Odoo's engine, not a number typed into a mockup.

## Latency — staff action to customer-visible

Measured over the real endpoints, 12 repetitions per scenario:

| action | median | p95 | min |
|---|---|---|---|
| add item | 56.7 ms | 94.4 ms | 38.3 ms |
| quantity change | 43.1 ms | 53.8 ms | 39.0 ms |
| modifier change | 41.1 ms | 54.4 ms | 39.6 ms |
| remove line | 42.5 ms | 61.0 ms | 39.5 ms |

**Read this carefully:** that is how long until the change is *available to the
display*, polled as fast as the loop can ask. The display's own interval is what a
customer actually experiences, so the interval **is** the perceived latency — half of
it on average, all of it at worst.

It was 900 ms, which put worst-case perception near a second. It is now **500 ms**,
which with ~45 ms of server time puts the typical customer-visible change around
**300 ms** and the worst case just over **half a second**. The payload is one small
row read, so asking more often costs almost nothing.

## Query complexity

Pricing is bounded by distinct products and tax groups, not by line count. The test
asserts the shape rather than a number: **20 lines and 40 lines of the same products
produce the identical query count**, which an N+1 cannot do. An absolute count would
only pin today's ORM.

## Screenshots

All at a real fixed viewport (iframe with `innerWidth` asserted), not a scaled window.

| File | Shows |
|---|---|
| `ocb-1480x760-en-idle.png` | idle: brand, "Ready for your order", lane |
| `ocb-1480x760-en-ordering.png` | 3 real products, real tax, TOTAL dominant |
| `ocb-1480x760-en-long-order-20-lines.png` | 20 lines: items scroll, **total stays pinned**, page never scrolls |
| `ocb-1480x760-ar-rtl-ordering.png` | Arabic RTL, Arabic modifiers under their line, Latin product names bidi-isolated |
| `ocb-1480x760-ar-confirmed.png` | confirmation state in Arabic |
| `ocb-two-lane-isolation-ar-and-en.png` | **the isolation gate**: two displays side by side, Lane 1 (Arabic) $2.76, Lane 2 (English) $205.85, zero shared content |

The two-lane capture doubles as the per-display language evidence: one board is
configured Arabic and the other English, on the same branch, at the same moment.

## Verified but not captured as a screenshot

* **Reconnecting** — the display shows a worded reconnect state after three
  consecutive failed polls and keeps the last order on screen until then. Exercised
  in code; not photographed.
* **1366×768 and 1280×720** — the type scale is `clamp()` on `vw` with no breakpoint
  logic, and 1024 and 1480 were both captured cleanly, but the two intermediate
  widths were not photographed.
* **4-worker consistency and restart recovery** — the projection is a database row
  with no process-local state, and the tests exercise it through real HTTP, but a
  dedicated 4-worker OCB run was not performed in this phase.

These are gaps in the evidence, not known failures, and they are listed here rather
than implied to be done.

## Not sourceable today

The brief's headline example — `2 × Classic Burger / No onion / Extra cheese` — cannot
be produced by the drive-thru Order Taker, which collects no modifiers and sends
`{product_id, qty}`. The OCB renders modifiers faithfully when they exist (tested, and
visible in the Arabic capture where they were published through the contract), and
nothing is invented to fill the space. Adding modifier entry to the Order Taker is a
later phase.
