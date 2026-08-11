# F5 — ARABIC TRANSLATION COVERAGE GAP (measured, NOT fixed here)

**This is a reported finding, not a defect introduced by this program.** Arabic *rendering*
(font, direction, bidi isolation, mirrored back/forward glyphs, RTL layout) is certified PASS —
see the F5 section of the certification report. What is incomplete is *translation coverage* of
the Owl staff apps.

## Measurement

Extracted every translatable UI string from the Owl templates (text nodes +
`placeholder` / `title` / `aria-label` / `alt` / `label` attributes) and diffed against
`i18n/ar.po`.

| Metric | Value |
|---|---|
| Translatable UI strings in `static/src/**/*.xml` | **201** |
| Present in `i18n/ar.po` | **57** |
| **Missing** | **144** |
| **Coverage** | **28%** |

Product *data* (product names, category names, branch names, user names) is correctly excluded —
those are per-record translations in Odoo, not UI copy.

## Why this is not fixed in this program

Wording is a native-speaker decision, and getting it wrong is worse than leaving English. This
program already hit a concrete example: with no explicit entry, "Register" fell through to an
incidental core translation **تسجيل** (= *registration / signing up*) instead of **الكاشير**
(= *cash register*) — actively misleading on a POS. The five workspace/search strings were
therefore given explicit entries; the remaining list below needs the same deliberate treatment.

## Recommendation

One native-speaker translation pass over the list below, then re-run the F5 browser check.
Until then, an Arabic-market release ships a mixed Arabic/English staff UI.

## Missing strings (144)

### `static/src/cashier/components/cart.xml` (6)

- `Assign table`
- `Charge (Ctrl+Enter or F2)`
- `Move table`
- `Park order`
- `Remove line`
- `Send to table`

### `static/src/cashier/components/cash_machine.xml` (6)

- `Cancel payment`
- `Cash received`
- `Change returned`
- `Inserted`
- `Send this amount to the cash machine. The machine counts the cash and returns any change.`
- `statusTitle`

### `static/src/cashier/components/integrated_terminal.xml` (1)

- `statusTitle`

### `static/src/cashier/components/manual_tender.xml` (2)

- `props.method.name + ' payment'`
- `— Select device —`

### `static/src/cashier/components/payment_screen.xml` (32)

- `Account for`
- `After this sale`
- `Amount to account`
- `Back to order`
- `Charge anyway`
- `Charge to account`
- `Charging to account`
- `Close`
- `Credit limit`
- `Customer account`
- `Customer over credit limit`
- `Deposit`
- `Manager approval for credit`
- `Manager approval — over limit`
- `Method`
- `No customer`
- `No customers`
- `Over by`
- `Over credit limit`
- `Owes now`
- `Search customer by name or phone`
- `Search name or phone`
- `Searching…`
- `Select a customer to charge this sale to their account.`
- `Select customer`
- `Settle due`
- `Use this customer`
- `is over their credit limit — a manager must authorize this sale.`
- `would exceed their credit limit with this sale.`
- `· Company`
- `⚠ Over limit by`
- `＋ Add customer`

### `static/src/cashier/components/qr_pay.xml` (1)

- `Payment QR code`

### `static/src/cashier/root.xml` (91)

- `+ Add walk-in`
- `+ New reservation`
- `Add to waitlist`
- `Add walk-in`
- `Assign table`
- `Back to Floor`
- `Choose an available table…`
- `Clear (Esc)`
- `Clear search`
- `Close`
- `Combined`
- `Completed`
- `Confirm`
- `Confirm cancel`
- `Confirm move`
- `Current table`
- `Date`
- `Day`
- `Dest T`
- `Fewer guests`
- `Floors`
- `Guest count`
- `Guest name *`
- `Guests`
- `Late`
- `Load more`
- `Loading orders…`
- `Loading reservations…`
- `Loading waitlist…`
- `Mark no-show`
- `Merge into T`
- `Merge tables`
- `Mezze`
- `More guests`
- `Move`
- `Move this order and its kitchen tickets to
                                T`
- `Move to T`
- `New reservation`
- `No table`
- `Note`
- `Occupied`
- `Occupied · merge`
- `Open`
- `Open another order`
- `Open ·`
- `Order filter`
- `Park &amp; open`
- `Park current order?`
- `Parked`
- `Party size`
- `Phone`
- `Quoted`
- `Quoted wait (min)`
- `Reserved`
- `Save reservation`
- `Search name, phone or reference`
- `Search orders`
- `Search orders — reference, table, or customer`
- `Search reservations`
- `Seat at…`
- `Seated ·`
- `Seated · T`
- `Source T`
- `Table *`
- `Table T`
- `That table isn’t available on this branch.`
- `This order is completed and read-only.`
- `Time`
- `Today`
- `Tomorrow`
- `Transfer order`
- `VIP`
- `View`
- `Waiting`
- `Waitlist`
- `Yesterday`
- `Your current order will be parked so nothing is lost,
                            then`
- `auto`
- `connLabel`
- `covers`
- `due`
- `favLabel`
- `guests`
- `min`
- `min quote`
- `paid ·`
- `state.assignPicker.mode === 'move' ? 'Move table' : (state.assignPicker.mode === 'seat' ? 'Seat guest' : 'Assign table')`
- `tableLabel`
- `waiting`
- `wanLabel`
- `will open.`

### `static/src/floor/root.xml` (13)

- `Available`
- `Avg dwell`
- `Covers`
- `Floors`
- `Loading floor…`
- `Mezze`
- `No tables configured on this floor.`
- `Occupied`
- `Open`
- `Reserved`
- `Service summary`
- `Table states`
- `connLabel`

### `static/src/kds/components/ticket_card.xml` (1)

- `recallLabel`

