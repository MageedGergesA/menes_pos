# ORIGINAL COMPONENT CATALOG (Primitive / Component / Compound / Workspace libraries)

5-tier architecture. Each documented component carries: composition tree · primitive deps · events · public API · accessibility/aria · tokens consumed · performance. Variant governance: Property · Modifier · Component · Pattern. 16-state universal model (every state = color + a second signal).

## Tier 1 — Primitives (Primitive Library: "15 primitives, vanilla ES modules", `createX()`)
- **Button** — variants primary / secondary / ghost / destructive / link; sizes sm/std/lg; states default/hover/focus-visible/loading("Processing")/disabled.
- **IconButton** — 44px target (search/tune/more_horiz/close/delete).
- **Input / Search / Textarea** — focus ring + error state ("Code has expired").
- **Select · Checkbox · Radio · Switch**
- **Badge (Status)** — icon+text tones Veg/Spicy/New/Popular/VIP/86/Info · **Avatar · Divider · Tooltip · Progress · Skeleton**

## Tier 2 — Compounds (Compound Library — restaurant layer, primitives only)
- **Product Card** — 6 display modes; name & price always mandatory; optional SKU/prep-time/station/stock; "Out of stock (86)"; lazy images; virtualization-friendly; category fallback (never an upload placeholder).
- **Category Chip** (Grills/Cold Mezze/Drinks) · **Quantity Stepper** · **Payment Method Tile** (Card/Cash/Wallet) · **Tabs / Segmented Control** (Dine-in/Takeaway/Delivery) · **Search Result**

## Tier 3 — Containers (Component Library)
- **Card / Panel** (Shift Summary, Current Order) · **Alert / Toast** (Printer connected, Low-stock warning, "Payment complete · Sent to kitchen") · **Dropdown / Dialog** (Customize modifier; Edit/Duplicate/Void) · **Toolbar** (undo/redo/discount/pause) · **Data Table + Empty State** ("tabular numerics · virtualization-ready", "No items yet").

## Tier 4 — Restaurant components
- **Order Line** — modes compact/standard/detailed/void/refund; qty/name/total mandatory; "Voided by manager", "Refunded"; destructive safeguards.
- **Order Ticket / Course Group / Modifier Group** — Table 12; Starters/Mains; Subtotal; VAT 15%; portion Required/Free.
- **KDS Ticket / Kitchen Timer / Status Row** — #1043, priority_high, count-up timer, allergen Badge.
- **Receipt Preview** — tabular · RTL-aware; Mezze Downtown · Terminal 3; Total SAR.

## Tier 5 — Compositions (Workspace Library — composition-only, <16ms render, AA)
**Cashier Workspace** + siblings: **Table Map / KDS / Reservations / CRM / Reporting**. Each carries migration metadata (legacy equivalent, difficulty, deps, rollback) and journey gates: "keyboard tab+arrow ✓ · touch 44px ✓ · RTL logical mirror ✓ · offline cache+outbox ✓".

## Coverage note for the current-vs-original comparison
The export defines **~11 primitive families, ~7 compounds, ~6 containers, ~7 restaurant components, ~6 workspaces**. Every family is icon+text/2-signal, 44px, RTL-gated, dark-authored, keyboard-complete BEFORE it is "Stable". This is the yardstick the shipped `components.css` (2 canonical families) is measured against.
