# POS hardware — network ESC/POS printing + cash drawer

## Why server-side
The Mezze front-end is a browser app; a browser can't reach a USB/serial printer,
and Odoo **Community has no IoT Box**. So printing is driven from the **server**:
Odoo renders an ESC/POS byte stream and sends it over raw TCP (port 9100 /
JetDirect) to a **network thermal printer**. The cash drawer is kicked through
the receipt printer's drawer pin. Barcode scanners are keyboard-HID — handled in
the front-end, no server model.

## Model — `mezze.printer`
One network printer bound to a branch: `printer_type` (receipt/kitchen/label),
`config_id` (branch), `station` (kitchen printer → which prep station), `host` /
`port` (default 9100), `width` (48 for 80mm, 32 for 58mm), `open_drawer` (this
receipt printer controls the cash drawer). Unique `(name, config_id)`.

## Endpoints (`/mezze/hardware/*`, shared-token auth)
Every print endpoint takes `preview=true` and **falls back to a preview**
(rendered plain-text + byte count, never a 500) when no printer is configured or
the printer is unreachable — so the flow is demoable and testable without
hardware.

| Route | Does |
|---|---|
| `POST /printers` | roster for a branch (+ `configured` = has a host) |
| `POST /print/receipt` | render + send a customer receipt (order_id \| uuid); kicks the drawer if the printer `open_drawer` and the order was paid in cash |
| `POST /print/kitchen` | render + send a station ticket (filters lines by `station` via `_station_of`) |
| `POST /drawer/open` | kick the cash drawer via the branch receipt printer |
| `POST /test` | print a test ticket (verify wiring) |

## ESC/POS renderer (`Ticket`)
A tiny builder (`controllers/hardware.py`) renders the SAME row list to both
ESC/POS bytes and a plain-text preview. Commands used: init `ESC @`, align, bold
`ESC E`, double-size `GS !`, cut `GS V`, drawer-kick `ESC p 0 25 250`. Receipt =
branch header, terminal-scoped receipt no., lines (qty × name … incl price),
subtotal/tax/total, tenders, ETA e-invoice uuid when the order was cleared, then
cut (+ drawer on cash). Kitchen = station banner, order/table/time, bold items.

## Known limitation — Arabic
Receipts render in the printer's Latin codepage (cp437); Arabic characters become
`?`. A fully Arabic receipt needs a printer with an Arabic codepage + RTL
reshaping — tracked for a later pass. The English receipt is correct today.

## Validation (2026-07-14, curl + mock socket)
- Receipt + kitchen **preview** render correctly (48-char justified; receipt
  shows the terminal-scoped `M1-…` reference; kitchen filters to the station).
- **Real send**: a mock TCP listener on :9199 captured 211 bytes for a test
  print; byte-checks confirmed init / bold / double-size / cut / text present.
- **Graceful failure**: printing to an unreachable printer returns
  `printer_unreachable` + a preview, never a 500.
