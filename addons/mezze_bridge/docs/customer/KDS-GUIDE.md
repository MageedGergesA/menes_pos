# Mezze POS — Kitchen Display (KDS) Guide

For the kitchen. The KDS shows fired items as live tickets and lets the line mark
progress without paper.

## Tickets

- A ticket appears when a waiter, cashier, or customer channel **fires** items.
- Each fired item shows exactly **once** — Mezze guarantees fire-once even if the
  network drops or someone double-taps, so the line never double-cooks.
- Tickets carry course, table/order reference, modifiers, and special notes.

## States and bump

- Work a ticket through its states (new → in progress → ready).
- **Bump** a ticket when it is done to clear it from the active board.
- Firing by course means later courses arrive as their own tickets when the front
  of house fires them.

## Recall

- **Recall** a bumped ticket if you need it back (a remake, a question from the
  server) — it returns to the board.

## Multiple stations

- If configured, tickets/items route to the relevant station (e.g. grill, cold,
  drinks). Layout is set once in the Admin Console.

## If tickets are not appearing

Items must be **fired** (not just added to a draft) to reach the KDS. If a fired
order is not showing, see `TROUBLESHOOTING.md` → "KDS not firing".
