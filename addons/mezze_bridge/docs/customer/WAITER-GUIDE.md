# Mezze POS — Waiter Guide

For dine-in table service. Sign in with your PIN; your name follows the order.

## Open a table

1. From the floor plan, tap a table to open (or resume) its order.
2. Mezze keeps **one** live draft per table. Two waiters (or a waiter and a
   customer's phone) can add to the same table safely — the server serialises
   updates on the table, so nothing is lost or double-fired.

## Add items and fire courses

1. Add products, modifiers, and combos to the table's order.
2. **Fire** to send to the kitchen. Firing is idempotent: each fire has a unique id,
   so a lost connection or a double-tap will **not** fire the same items twice — the
   kitchen sees each item exactly once.
3. Fire by **course** to pace the meal (starters now, mains later). Re-open the table
   at any time to add more; only the newly added items fire.

## Transfer and merge

- **Transfer** an order to another table (guests move).
- **Merge** two tables' orders into one (parties combine).

## Bill and pay

1. Present the bill from the table.
2. Payment can be taken at the table or handed to the cashier. Split **by amount or
   by line** and mix tenders. *(Per-seat split identity is planned for V2.)*
3. Customers can also pay their own table bill online via the table QR — see
   `SELF-SERVICE-GUIDE.md`.

## Notes

- Item availability (an "86'd" item) is enforced branch-wide and in real time — a
  sold-out item is blocked at fire.
- If the kitchen display is not showing fired items, see `KDS-GUIDE.md` and
  `TROUBLESHOOTING.md`.
