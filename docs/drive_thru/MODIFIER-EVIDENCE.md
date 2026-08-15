# Drive-thru product customization — evidence

Captured on a real runtime against the branch's real catalogue, with a product
configured through Odoo's own models (POS-time attributes, `create_variant='no_variant'`,
real `price_extra`). No invented menu and no invented option names.

## Interaction cost

The configurator is local DOM work — no network on open, on selection, or on a simple
add — which is why the fast path feels instant. Median of 12, measured in the page:

| | median |
|---|---|
| configurator open | **1.9 ms** |
| option selection (re-render + live price) | **0.5 ms** |
| simple product → cart | **0.4 ms** |

Menu: 172 products, 11 configurable, 14 modifier groups, 10 options on the test product.

## Taps

| | taps after the product tap |
|---|---|
| simple product | **0** |
| product + one modifier | **2** (option, Add) |
| product + three modifiers | **4** (three options, Add) |
| edit one modifier on an existing line | **3** (Edit, option, Save) |

## Live price, measured in the browser

Base **147** → Large (+5) **152** → Extra cheese (+3) **155**, and the same
configuration re-priced by the server on the customer board.

## Money parity, observed end to end

One configured line, qty 2, `Large + No onion + Extra cheese`:

| surface | figure |
|---|---|
| configurator preview | 155 per item |
| customer board line | **356.50** (155 × 2, taxed) |
| customer board total | **525.55** with the second line |
| POS order | asserted equal in `test_06`: unit price = list + 8, order total = line total |

Removing Extra cheese: board line went **356.50 → 174.80**, and the modifier
disappeared from the customer's screen in the same poll.

## Line identity, observed

```
Corner Desk Right Sit · Large · No onion · Extra cheese   qty 1
Corner Desk Right Sit · Regular · No pickles              qty 1     ← two lines
Corner Desk Right Sit · Large · No onion · Extra cheese   qty 2     ← same config merges
```

## Boot payload — the pre-existing cost, measured rather than assumed

The audit flagged that `/bootstrap` builds modifier groups **per product**. Measured
over 10 requests, 172 products:

| | |
|---|---|
| payload | 59.2 KB |
| median | **1577.8 ms** |
| p95 | 1749.1 ms |

This predates the phase — the call was already there for the Register — but the
drive-thru now depends on it, so it is recorded as a real number rather than a
suspicion. It is a **once-per-page** cost at board boot, not a per-tap cost; the
interaction figures above are unaffected. Worth attention before a branch with a
larger menu, and deliberately not optimised here: this phase does not own it, and
changing the shared bootstrap would have put the Register in scope.

## Screenshots

| File | Shows |
|---|---|
| `ux7a-configurator-wide-en-final.jpg` | the configurator docked beside the queue — **sixteen cars, lanes and timers still readable**, real groups from Odoo (Portion / Remove / Extras / Options), live item total, actions inside the panel |
| `ux7a-configurator-footer-price-and-actions.png` | the footer after the fix: ITEM TOTAL on its own line, Cancel and Add side by side |

## Not captured

Recorded as gaps rather than implied:

* **Arabic configurator screenshot.** The panel uses the same logical properties and
  translated dictionaries as the rest of the board (70/70 key parity, verified), and
  Arabic RTL is captured for the board and the OCB, but the configurator itself was
  not photographed in Arabic.
* **1024 and 1440 fixed-viewport captures of the configurator.** Only the wide viewport
  was photographed; the touch-floor and tabindex checks were asserted programmatically
  in `test_26` rather than visually.
* **KDS screenshot showing a configured item.** The path is asserted in `test_14` (the
  chosen values reach the ticket as words) but not photographed.
* **Combos.** Published and kept by the board, not yet configurable from the lane —
  stated as a limit, not implied as done.
