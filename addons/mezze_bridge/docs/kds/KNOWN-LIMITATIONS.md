# Mezze KDS — known limitations (V2C, honest scope)

The production KDS UI (`/mezze/kds`) is software-complete and browser-certified. These
are the deliberate v1 boundaries — none is a defect; each is an evidence-driven choice.

1. **Item-level completion is DEFERRED (ticket/station-level workflow only).** A ticket
   is accepted/prepared/ready/served as a unit. Per-dish strike/bump within a multi-dish
   station ticket is not in v1 (needs a per-line state machine + stable
   pos.order.line↔kds.line linkage the domain does not carry). Decision recorded in
   `STATE-MACHINE.md` (D-G). Do not add it silently.

2. **Channel badge = real order channel where present, else derived.** The badge uses
   `pos.order.mezze_channel` (qr/pickup/delivery/drivethru/aggregator/kiosk/pos) when
   set; otherwise dine-in (has table) vs counter. No channel is invented. Orders created
   without an explicit channel show "Dine-in"/"Counter" — correct for the data present.

3. **Notes are free-text special instructions, NOT certified allergens.** The card shows
   the line `note` as a kitchen instruction. There is no structured allergen data model,
   so there is no allergen badge (inventing one would be unsafe). See `STATE-MACHINE.md` (I).

4. **Priority/rush = late-by-time only.** No priority subsystem; urgency is elapsed-vs-
   threshold (`kds_late_minutes`, default 15). See `STATE-MACHINE.md` (H).

5. **Realtime uses bus poll-reconcile (LAN-first), not a raw websocket.** The board polls
   the real Odoo bus (`/bus/poll`) every 4s and re-seeds the full snapshot on reconnect.
   This is deliberately simpler and more robust than a second socket layer; the server
   snapshot is always authoritative. A push websocket can be layered later without
   changing the reconcile contract.

6. **`prefers-contrast` / OS `forced-colors` are NOT auto-detected.** High-Contrast is the
   real Mezze APP theme (`?mztheme=highcontrast` / `ac_contrast`), same as the rest of the
   product. Honouring the OS forced-colors media query is a product-wide gap, not KDS-specific.

7. **Physical certification = NOT EXECUTED (S6).** No real kitchen monitor, physical
   touchscreen, restaurant LAN, WAN cut, power-recovery, staff UAT, or shift simulation
   has been run. Software browser acceptance ≠ physical certification. Edge readiness is
   unchanged by V2C.

8. **Two-client convergence is proven via the server's row-locked single-logical-effect
   guarantee** (concurrent `/kds/transition` → exactly one `changed=true`, both converge),
   exercised from the real board, plus the snapshot-authoritative reconcile. A literal
   two-window race on physical screens is part of S6 physical certification.
