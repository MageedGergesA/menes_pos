# Claude Code handoff — master index

Entry point for implementation. Every backend requirement below has an ID (BE-NNN); every ID
traces to a detailed doc. This file does not repeat their content — it routes to it.

**Design system**: `docs/MEZZE_DESIGN_SYSTEM.md` — Hanken Grotesk/IBM Plex Sans Arabic/JetBrains
Mono, warm-neutral tokens, RTL rules. Canonical; do not restyle to any other system.

**Native Odoo first.** Before adding a custom model, check whether POS orders/sessions, partners,
loyalty, gift cards/eWallet, products/variants, restaurant floors/tables, inventory locations/
transfers, BoMs, MRP work orders, accounting, `hr.employee`/attendance/payslip, or Self-Order
already represent the fact. Custom models exist only where restaurant-specific state genuinely
has no Odoo home (e.g. drive-thru lane stage timing, manager handover records).

## Domain index

| Domain | Docs | Screens |
|---|---|---|
| Order lifecycle | `ORDER_STATE_MACHINE.md` | Orders, KDS, Call centre, Delivery, Rider, Online Ordering, QR self-order |
| POS / Orders | `TABLE_LIFECYCLE.md`, `P0_CRITICAL_WORKFLOWS.md` | Register, Tables, Orders |
| Payments & value | `PAYMENT_VALUE_ENGINE.md`, `HOUSE_ACCOUNTS.md`, `TIP_POOLING.md` | Register, Session, Tips |
| Guests / loyalty / gift cards | `LOYALTY_ENGINE.md` | Guests, Register, CRM screens |
| Floor / bookings | `ARRIVAL_QUEUE.md` | Host, Floor editor |
| Kitchen / production | `KITCHEN_PRODUCTION_ENGINE.md`, `REFIRE_COSTING.md` | KDS, Kitchen production |
| Stock / commissary | `STOCK_COUNT_VARIANCE.md`, `INVENTORY_WASTE.md` | Stock, Commissary |
| Delivery / rider / call centre | `DELIVERY_ENGINE.md`, `CALL_CENTER.md` | Delivery, Rider, Call centre |
| Online ordering | `ONLINE_ORDERING.md` | Mezze Online Ordering.dc.html |
| Workforce | `WORKFORCE_WORKFLOWS.md` | Onboarding, Absence, Breaks, Clock-out |
| Session / EOD | `SESSION_LIFECYCLE.md` | Session |
| Group / HQ | `GROUP_GOVERNANCE.md` | HQ governance |
| Devices | `DEVICE_PLATFORM.md` | Devices |
| Integrations | `INTEGRATIONS.md` | Channels |
| Tax | `TAX_INTEGRATION.md` | Tax compliance |
| Payroll boundary | `PAYROLL_INTEGRATION.md` | Payroll handover |
| 86 / recovery / comp | `86_OPEN_ORDER_IMPACT.md`, `GUEST_RECOVERY.md`, `COMP_ACCOUNTING.md` | Menu (86), Guest recovery |
| Menu | `MENU_ENGINE.md` | Menu |
| Localization | `AR_KEY_COLLISIONS.md` | all |

## BE items — critical joins (highest priority for Claude Code)

| ID | Feature | Odoo models | Custom model | Doc |
|---|---|---|---|---|
| BE-001 | Deposit → real prepayment/accounting | `pos.order`, `account.payment` | no | `PAYMENT_VALUE_ENGINE.md` |
| BE-002 | Gift-card capture → ledger | Odoo gift card / eWallet program | no | `PAYMENT_VALUE_ENGINE.md` |
| BE-003 | Commissary receive → stock transfer | `stock.picking` (internal transfer) | no | `INVENTORY_WASTE.md` |
| BE-004 | Per-terminal drawer/X/Z → session accounting | `pos.session`, `account.move` | no (handover record is custom) | `SESSION_LIFECYCLE.md` |
| BE-005 | Payment capture → session takings | `pos.payment` | no | `SESSION_LIFECYCLE.md` |
| BE-006 | House account → receivable | `res.partner`, `account.move` | no | `HOUSE_ACCOUNTS.md` |
| BE-007 | Loyalty ledger persistence | Odoo Loyalty | no | `LOYALTY_ENGINE.md` |
| BE-008 | Tip persistence/distribution | `hr.payslip.input` | thin: pool/session tip record | `TIP_POOLING.md`, `PAYROLL_INTEGRATION.md` |
| BE-009 | Inventory/write-off posting | `stock.move` (scrap) | no | `INVENTORY_WASTE.md` |
| BE-010 | BoM/modifier consumption | `mrp.bom` | modifier-group/option structure if not modeled | `MENU_ENGINE.md` §2a — canonical OrderLine: `mods[]` structured selections only, `note` free-text instruction only, `qty`/`weight` own quantity only; Register+Handheld share the shape and one live fire-to-KDS path (`fireLinesToKds`), interactively confirmed on both incl. second-fire dedup and structured mods+note on the visible KDS ticket; option id is still a label; Kiosk/QR/Online/Call centre never capture mods |
| BE-011 | Comp accounting | `account.move` (discount/write-off line) | no | `COMP_ACCOUNTING.md` |
| BE-012 | Refund accounting + loyalty reversal | `pos.order` refund flow, Loyalty | no | `LOYALTY_ENGINE.md`, `COMP_ACCOUNTING.md` |
| BE-013 | Tax (ETA e-receipt) submission | custom localisation connector | yes — no native B2C e-receipt module | `TAX_INTEGRATION.md` |
| BE-014 | Order state machine, server-authoritative | extend `pos.order`/`sale.order` | thin: `state` enum + seq | `ORDER_STATE_MACHINE.md` |
| BE-015 | Delivery route/geocoding provider | external (Google/HERE/Mapbox) | yes — route/pin contract | `DELIVERY_ENGINE.md` |
| BE-016 | Ready-to-seat SMS/WhatsApp send | external provider (Twilio/WhatsApp BSP) | yes — send/status record | `ARRIVAL_QUEUE.md` |
| BE-017 | Device fleet MDM (push, firmware) | none native | yes | `DEVICE_PLATFORM.md` |
| BE-018 | Aggregator integrations (Talabat etc.) | none native | yes — per-provider connector | `INTEGRATIONS.md` |
| BE-019 | Forecast generation (prep board demand) | none native | yes — forecast service | see "Not yet built" below |
| BE-020 | Payroll export/send | `hr.payslip.input`, `hr.attendance` | no | `PAYROLL_INTEGRATION.md` |

**BE-014 addendum (closure pass 15F):** Park/Recall is a sub-case of BE-014's state machine, not
a new BE item. Map it to Odoo 19 POS's existing draft/active order list (reselect-and-reload into
the register) rather than a parallel "parked order" store. Internal line note (free text),
structured modifier selection, and refire reason are three independently-stored concepts — do not
collapse them into one Odoo field; see `ORDER_STATE_MACHINE.md` and `KITCHEN_PRODUCTION_ENGINE.md`
for the exact contract each surface now sends.

**BE-005/BE-0xx addendum (closure pass 16A — Kiosk/QR modifiers):** Odoo 19 ships native Kiosk and
QR self-ordering, products/categories, variants, and Combo Choices. Do not assume Mezze's
restaurant modifier groups map 1:1 onto either: a variant is for attributes that create a distinct
sellable product (rare here), and a Combo Choice is for bundling whole products, not per-item
options with a price delta. Most of Mezze's `this.MODS` groups (Size/Spice level/Add-ons) need a
dedicated modifier-group/option model extended onto `product.template`, consumed identically by
Register, Kiosk, QR, and (when built) Online/Call Centre — one backend definition behind the one
frontend owner (`this.MODS`/`item.groups`) this pass established.

**BE-012 addendum (closure pass 18B):** The frontend contract is now real, not a stub — build the
backend to this shape rather than inventing one:
- One refund poster, `ordRefundCommit(ref, qtyMap, reason, by)`, called by Orders, Guest Recovery's
  Refund remedy, and the 86-impact sheet's Refund action alike. It tracks cumulative refunded qty
  per line (`refundedQty`), reverses loyalty proportionally and cumulatively (`loyRefundReverse`),
  and posts a House-account credit note when that was the original tender. Map this to Odoo 19's
  order-based return (select the paid order and refunded quantities) plus a linked credit note —
  do not build a disconnected refund model.
- Loyalty reversal debt is allowed to go negative (Mezze policy — see `LOYALTY_ENGINE.md` §9). Do
  not clamp a partner's loyalty balance to zero server-side.
- Guest Recovery's Comp and Remake remedies now post into the SAME `compLog`/`rfLog` rows the
  handheld's comp/refire flows write (tagged with the recovery's own reference) — one cost ledger
  per type, read by Plate cost, not a parallel Recovery-cost ledger. Build the backend model the
  same way: a recovery record that references the comp/refund/refire it caused, rather than owning
  its own copy of the cost.
- **86 is not itself a financial event.** Only the comp/refund/waste consequence chosen for an
  affected order should post a cost — the availability flag alone must never create one.

**BE-012 addendum (closure pass 18C):**
- Refund destination is now a real choice: original tender, or a new gift card via `gcIssue` — map
  to Odoo 19's native "refund to gift card" POS capability where the platform version supports it.
  Loyalty reversal and House-account credit-notes are computed identically regardless of destination.
- Tip refund is explicit, never inferred: a manager-facing "Refund tip too" toggle on a full-order
  refund, default OFF, posts one `reverse` row on the SAME tip ledger (`docs/TIP_POOLING.md` §8).
- Recovery substitution pricing is a frozen MEZZE POLICY, not native Odoo:
  `charge = min(original price, replacement price)`. Build the backend rule the same way — do not
  let a POS return/exchange flow charge the replacement's own price.
- Loss category is now a first-class dimension (`COMP`, `REFIRE_REMAKE`, `WASTE_DISCARD`,
  `SPOILAGE`, `OVERPRODUCTION`, `RECOVERY_SUBSTITUTION`), derived from existing ledgers
  (`compLog`/`rfLog`/`wasteLog`) by source and, for waste, by parsing `reason` text — a real backend
  should carry this as a stored enum column on the waste/scrap model, not a string match.

Each doc above specifies, per its own items: user action, required inputs/outputs, accounting and
inventory impact, permission gating, offline behavior, idempotency, audit and error states, to the
level of detail that document was written at. Where a doc predates this BE numbering it does not
yet cite IDs inline — treat the table above as the index into it, not a replacement for reading it.

**BE-006/BE-007/BE-008 addendum (closure pass 18A — guest identity, value, tips):** Register now
carries the same guest attach/replace/remove flow as the handheld and Orders, all reading one
`state.guests` book (→ `res.partner`) through `tenderGuest(surface)`/`tenderCheckKey(surface)` —
map that pair directly to "customer on this order" in Odoo; do not give any surface its own
customer field. Drive-thru's vehicle-to-guest match (`DT_VEHICLES`) is a separate, smaller mapping
— plate/colour/body keyed to one or more partner ids — never the partner record itself; a plate
matching more than one partner must stay a confirm-before-attach choice, not an automatic pick.
**Credit-limit policy (BE-006):** the prototype implements a **hard block** — a House account
charge that would put exposure over the limit is refused outright, with no manager-override path
today. Odoo 19's native maximum-credit behavior is a warning, not a stop, so this is a deliberate
Mezze policy choice to confirm with the business before building: either keep the hard block (add
a manager-PIN override state so a real exception isn't just "no"), or relax to Odoo's warn-and-log
default. Whichever is chosen, implement it as one gate `tenderReady()` calls — not a second check
duplicated at the guest-record screen. **Tip capture (BE-008):** the tip is a single amount owned
by the order (`checkTipAmt`/`checkTipSet`), added to the total once; tender lines (cash, card, a
split of both) only fund that total down. Persist it the same way — one `tip_amount` on the order,
not one per payment line — or a cash/card split will double it.

## Not yet built this pass — genuinely open frontend work

These were requested in the final closure brief and are **not done**. Flagging explicitly rather
than silently dropping them:

- **A1 Kitchen multi-stage production** — **built** (Priority 3, Pass 2): Kitchen surface,
  “Production stages” layout tab. See `KITCHEN_PRODUCTION_ENGINE.md` §6.
- **A2 Forecast Prep board** — **built** (Priority 3, Pass 2): Kitchen surface, “Forecast prep”
  layout tab. Per-station forecast split still open. See `KITCHEN_PRODUCTION_ENGINE.md` §7.
- **A5 Structured modifiers** — **built for Register, Kiosk, QR, Handheld, and Call Centre**
  (closure passes 16A/16C): all five read the same `this.MODS`/`item.groups` owner and commit
  through the same `modLabel()`/`modDelta()`, writing `mods[]` as `[{g,t,p}]`, never a label
  string. `HH_MODGROUPS` is retired. **Mezze Online Ordering.dc.html carries a modifier-parity
  copy** (its own `this.MODS`, byte-identical, commented as a copy) since it's a separately-served
  static file — real backend must expose one modifier-group model consumed by both files, not two.
  **Call Centre had zero modifier capability before pass 16C** — built from the same shared
  frontend owner, no new BE item (BE-010 already covers modifier persistence).
- **Menu authoring (create-from-zero)** — **built, pass 17A**: Menu → Modifier groups/Products now
  have real Create/Edit/Publish, merged into the same `this.MODS()`/`itemsC()` runtime owner (no
  parallel authoring catalog). No persistence layer — authored content lives in React state only
  and is lost on reload; Claude Code's product/modifier-group backend (BE-010) is what makes this
  durable, not a gap in the authoring UI logic. Draft/Live is a boolean only — no scheduled
  publish, versioning, branch/daypart scope, or combo authoring yet (pass 17B+). Channel scope
  (`chans` field) is a minimal allowlist, not mapped to a real Odoo channel-availability model.
- **Combo authoring (pass 17B)** — **built**: a combo slot (Main/Side/Drink) is implemented as
  the SAME modifier-group model above, tagged `combo:true`; a combo product is the same product
  model tagged `isCombo:true`. Native mapping candidates: **Odoo Combo product** (Product Type =
  Combo) for the combo product itself; **Odoo Combo Choice** (reusable choice/slot, max items,
  included items, per-option Extra Price) for Main/Side/Drink — the prototype's shape (required,
  max 1, one option, one price delta) maps directly to a single-select Combo Choice.
  **Multi-station kitchen routing — built in pass 17C**: each selected component now resolves
  its OWN station via the existing product/category station owner (`itemStation()`), producing
  separate ticket entries (still one customer line/one price) — no new backend model implied
  beyond what already maps Register lines to preparation stations. **Fired-line edit — built in
  pass 17C, generalized to ALL lines**: `canDirectlyEditLine()` in Register is the one owner
  blocking direct modifier/note/qty mutation on any fired line (combo or not); a fired line's
  qty increase creates new demand rather than rewriting history. See `ORDER_STATE_MACHINE.md`
  "Fired-line amendment rule". Handheld needs no equivalent — fired lines already leave its only
  editable collection (`hhDraft`) at fire time, so the same bug class cannot occur there.
- **Menu governance (pass 17D)** — **built**: version model (`mnVersions`), branch override
  (`mnBranchOv`), and daypart (`MN_DAYPARTS`) already existed as admin UI; now wired to actually
  gate what Register's grid shows/prices via `mnSellableAtBranch()`/`mnDaypartOk()`/version-scoped
  `mnVerMods()`. Real backend requirements: persistent version records with audit history,
  ATOMIC publish (no partially-applied version), server-side scheduled activation (this
  prototype's "Publish it now" is manual — nothing auto-fires at a chosen time), schedule-conflict
  handling, stable option/group IDs across versions (this prototype keys patches by
  `group|option-label` — a real system needs stable IDs surviving a label rename), and ONE menu
  API serving both POS and the separate Online storefront (see pass 17A/17C Online note — two
  static files cannot share one runtime object without this). Odoo 19 branches already carry
  branch-specific pricelists/inventory locations — do not build a second branch master; Menu
  scope should reference Odoo's existing branch identities. Do not fold Menu governance into
  pricelists — availability/version/scope is a Menu concept, promotional/customer pricing is
  Odoo pricelist territory (see `MENU_ENGINE.md` "Pricing boundary"). Odoo POS category Service
  Hours may cover PART of daypart/channel scheduling for delivery-platform categories — inspect
  before assuming Mezze needs a fully separate daypart engine.
- **Menu governance (pass 17E)** — **built**: generalized version patches from one tracer field
  to three (`mnVerChan`/`mnVerDp` alongside `mnVerMods`), all reading through one public resolver
  `menuItemState(it,ctx)` returning `{sellable, reason}` (`reason` one of `86|WRONG_BRANCH|
  WRONG_CHANNEL|OUTSIDE_DAYPART`). Kiosk's grid calls it; Register/QR/Call Centre still call the
  underlying predicates directly (correct today, not yet one call site — real follow-up work).
  Schedule lifecycle completed: cancel-schedule, a same-time schedule-conflict block (scope is
  "all branches only" in this prototype — a real system must compare branch_scope too before
  flagging a collision), and a clearly-labeled DEMO activation button standing in for the
  server-side activation worker that must actually fire at the chosen time in production. Change
  summaries are derived from the same patch bags the runtime reads, never hand-typed — worth
  preserving that property in the backend model (a change log that can drift from the actual
  diff is worse than none). Still open: patch coverage is 3 demo fields, not a general
  "any Menu field can be Draft-scoped" system — extending it is real, undone work; branch
  overrides remain immediate/global, not version-scoped — a deliberate scope cut, not an oversight.
- **Menu governance (pass 17F) — MENU DESIGN DOMAIN FROZEN.** Generic change model: mnVerChanges(v)
  now reads all three patch bags through one diff loop emitting `{entity_type,entity_id,field,
  old_value,new_value}` — the shape a real backend audit/changelog table should mirror.
  `menuItemState(it,ctx)` is now the call site for Kiosk, Handheld, standalone QR, and Call Centre;
  Register uses the same function with `ctx.ignore86=true` (by design — Register dims 86'd items
  in place rather than hiding them, so its grid visibility and its sellability check are
  deliberately different questions, both still routed through one function). **Real bug found and
  fixed**: Register's `add()` only checked `item.out` (the incident-based 86 flag), never
  `cc86()`/`state.off86` (the fast KDS-ticket-level 86 flag) — meaning a kitchen worker's quick 86
  from an active ticket did not stop Register from re-selling the item. Fixed to check `cc86()`
  first, matching Handheld/Call Centre's existing guards. **Backend must guarantee the equivalent**:
  ANY operational-unavailability write (86, stockout, kitchen-side block) must be checked by EVERY
  order-entry point before accepting a line — a single source of truth for "can we sell this right
  now" that every channel's checkout/POS/kiosk/call-centre backend call goes through, not a
  per-surface reimplementation of the same check. Overnight daypart wraparound
  (`to>1440` in `mnDaypartOk`) is interactively proven correct (23:00/01:00/03:00) — a real backend
  scheduler must handle the same wraparound, likely via UTC-normalized ranges rather than
  minutes-since-midnight. Backend-only work remaining: persistent version records + audit history,
  atomic publish, real server-side scheduled activation (current "Publish it now"/DEMO button is
  manual), schedule-conflict enforcement that accounts for branch scope (this prototype's conflict
  check assumes all-branches), stable option/group/product IDs surviving a label rename, one Menu
  API serving POS + the separate Online storefront, and Odoo pricelist vs. Menu-governance boundary
  enforcement (see `MENU_ENGINE.md` "Pricing boundary"). None of these are Design blockers — the
  Menu DESIGN domain is frozen; future Menu work extends this contract, it does not redefine it.
- **A4 Unified guest attachment** on Orders + Drive-thru — still open. Register/Handheld/Orders all
  resolve the check's guest through the shared `tenderGuest(surface)`/`tenderCheckKey(surface)`
  pair; Drive-thru reads `state.guests` directly via `dtGuest(id)` from its vehicle match instead —
  same book, inconsistent access path.
- **C1/C2 Ready-to-seat notification states, computed wait quote** — not built. No wait-time
  computation or notification-state exists; Arrival Queue only derives stage (Arriving/Waiting/
  Late/Ready to seat/Seated/No-show).

**Closed this pass (confirmed already built, corrected from a prior stale gap list):**
- **B1 Register tip prompt → shared tip pool** — wired. Register's settlement posts one
  `tipPush({k:'capture',sur:'pos',...})` on the tender that clears the check, into the same
  `tipLog`/`tipPool()` Handheld and QR already write to.
- **B3/B4 86 & recovery downstream consequences, cost-reason breakdown in Plate Cost** — wired.
  `lossCatTotals()` aggregates `compLog`/`rfLog`/`wasteLog` into the six loss categories, and the
  86-impact sheet's comp/refund/refire actions post into those same ledgers.
- **C3 Floor editor** — built: add/duplicate/delete, drag-move, capacity/shape, zones, undo/redo,
  preview, save-as-layout. Recommend one live click pass before sign-off, but no code gap remains.
- **D1 Map-pin interaction** — the frontend simulation is built: clickable zone pins and rider
  markers that move along a route by elapsed-time progress. What remains is real geocoding/live GPS
  (BE-015) — always backend scope, not a frontend gap.

See `docs/MEZZE_FINAL_FROZEN_AUDIT.md` for the full reconciliation against the prior audit.
