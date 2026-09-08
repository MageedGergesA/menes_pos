# P0 — Critical workflow contracts

Four chains that can silently lose or misstate money or stock. Each contract below is the
agreement between what **Claude Design** builds in `Mezze POS v3.dc.html` (screens, states,
labels, EN/AR) and what **Claude Code** builds in Odoo 19 (records, moves, postings).

Rule for design work: **every state in the state list must be reachable and visible in the
prototype.** If the ledger can be in a state the screen can't show, that's a P0 defect.

Rule for handoff: design never invents a state name. State names below are the contract.

---

## 1. Deposit → bill — **built in the prototype**

A booking takes a deposit. That money must appear on the check it belongs to, be applied at
payment, and be traceable when the booking is cancelled or no-shows.

### States

| State | Meaning | Where it shows |
| --- | --- | --- |
| `none` | Booking has no deposit | 30 Reservations |
| `held` | Deposit taken, booking not seated | 30 Reservations, 17 Cash |
| `applied` | Deposit consumed by a check | 01 POS check, bill, payment modal |
| `partial` | Deposit smaller than bill total | payment modal |
| `credit` | Deposit larger than bill total — remainder owed to guest | payment modal, 23 Exceptions |
| `refunded` | Returned to guest | 30 Reservations, 17 Cash, 23 Exceptions |
| `forfeited` | No-show / late cancel, kept as revenue | 30 Reservations, 28 Reports |

### Claude Design

- **30 Reservations** — deposit column shows amount + state chip, not just amount. `Link to
  check` action only enabled for `held`.
- **01 POS check** — when a seated table carries a linked booking, a deposit line sits above
  the subtotal: `Deposit held − SAR 200.00`, with the booking reference. Not a discount line;
  visually distinct from discounts.
- **Bill print view** — deposit shown as a separate line between subtotal/tax and amount due,
  labelled `Prepaid deposit`. Amount due is net.
- **Payment modal** — deposit appears as a pre-applied tender row that cannot be deleted, only
  unlinked (manager). Shows `Applied SAR 200.00 · Remaining SAR 0.00` or, when the deposit
  exceeds the total, `Credit SAR 45.00 → refund or gift card`.
- **Cancel path** — cancelling a booking with `held` deposit forces a choice: `Refund` /
  `Forfeit` / `Move to another booking`. No silent delete.
- Arabic: deposit states get real terms, not transliteration. Arabic-Indic numerals on all
  amounts.

### Built so far (design phase)

All seven states are reachable and visible. The book shows amount + state chip per booking (HELD /
APPLIED · BALANCE DUE / CREDIT TO RETURN / REFUNDED / FORFEITED); the detail panel carries the
state, the check it sits on, and what is left. A held deposit can be linked to any open check
without one, and unlinked again. On the check the deposit is a `Prepaid deposit −800.00 · booking ·
Farid party` line below the tax lines and above the total, in accent — not a discount — and the
amount due is net (verified: 6,048.60 bill → 5,248.60 due). Over-deposit shows
`Deposit credit to return +9,367.55` and settles the check with no tender. The payment modal
carries the deposit as a pre-applied row that cannot be deleted, only unlinked behind the manager
PIN. Cancelling a deposited booking cannot complete until a disposition is chosen — the CTA reads
"Decide the deposit" until Refund / Keep / Move is picked, and the choice lands on the state chip
and the booking log.

Still open here: the register's Bill button is decorative in this prototype, so the printed-bill
line is the on-screen check line; and a credit issued as a gift card mints a number and posts to
the liability in the log and toast, but the new card does not appear in the Gift cards list — that
list is static seed data, so the two ledgers only meet on the Odoo side.

### Claude Code

- `pos.order` ↔ booking relation (extend `restaurant.table` reservation or a custom
  `mezze.booking` model with `order_id`).
- Deposit as a **prepayment** — down-payment product or an Odoo payment on the partner, not a
  negative order line. Must not distort product sales or plate cost.
- Reversal rules: refund creates a counter-payment on the same journal; forfeit posts to a
  revenue account defined in Settings, not to product sales.
- Credit remainder: refund tender or gift-card issuance, both idempotent.
- Deposit cannot be applied to two orders. Enforce at the DB level, not the UI.

### Acceptance

Take a deposit, seat, add items under the deposit value, pay → guest owes nothing, ledger shows
`credit` and asks for disposition. Cancel a deposited booking → forced disposition, session
close reflects it, no orphaned cash.

---

## 2. Gift card → tender — **built in the prototype**

Gift cards exist on 25 Gift cards but do not discharge a balance anywhere. Six payment surfaces
must accept them identically.

### Surfaces (all six, same behaviour)

01 POS · 06 Orders (order drawer) · 23 Handheld · 24 Self-service kiosk · QR pay · 07 Drive-thru

### States

| State | UI |
| --- | --- |
| `lookup` | Scan / type card number, or pick from guest profile |
| `not_found` | Inline error, card number stays editable |
| `expired` / `void` | Blocked with reason, manager override optional |
| `sufficient` | Balance ≥ due — one tap tenders full amount, shows remaining balance |
| `insufficient` | Balance < due — applies full balance, order drops to split tender with remaining due highlighted |
| `zero` | Card valid, no balance — explicit message, not silent failure |
| `applied` | Tender row with card number masked to last 4 and balance after |

### Claude Design

- Gift card becomes a first-class tender button on every payment surface — same position, same
  icon (`card_giftcard`), same size as Cash/Card.
- **Balance lookup panel**: card number, balance, expiry, guest name if linked. Reachable
  before committing the tender.
- **Insufficient balance is the important screen.** Applying 45 of 180 must leave the modal in a
  clear split state: `Gift card SAR 45.00 applied · SAR 135.00 remaining` with the remaining
  tenders live. Never dismiss the modal.
- Kiosk and QR need a no-staff variant: on-screen keypad, no manager overrides, clear failure
  copy with a "get help" path.
- 25 Gift cards gains a transaction log per card (issued / topped up / redeemed / refunded /
  expired) so the redemption is visible from the card side too.
- Guest profile (16 Guests) card rows become tappable → same lookup panel.

### Built so far (design phase)

One shared panel (`GiftCardTender.dc.html`) is mounted once and opened from all six surfaces, so
the lookup, the verdict copy and the arithmetic cannot drift between them. States `lookup →
not_found / expired / void / zero / sufficient / insufficient` are all reachable; expiry is
computed against the session's business day, so one seeded card reads EXPIRED and one reads
SPENT. Insufficient balance applies the whole balance and leaves the panel open with the
remaining due live (verified: 3,898.35 due, 340.00 card → 3,558.35 remaining, card to 0.00).
Staff mode searches by number or holder; kiosk and QR get a keypad with no card list and no
manager overrides. Each redemption writes a ledger line naming the surface, and Gift card is now
a tender on the session close, system-counted against the liability rather than counted at a
drawer.

All six surfaces are driven and verified against the ledger: POS (3,898.35 → 340 card → 3,558.35
remaining), Orders (6,020 → 2,400 → 3,620, part payment logged), Drive-thru (car's own 395.00, not
the register's total), Handheld (behind the same "fire the held courses first" guard as every other
handheld tender), kiosk (3,283.20 → 340 → banner + header 2,943.20 → second card 120 → 2,823.20,
so re-opening nets off what is already applied) and QR (1,768.47 → 500 → banner −500.00, You pay
1,268.47). Guest surfaces resolve a card from digits alone, since a keypad has no letters.

Still open here: register-side tenders live on the check rather than the order board, so a POS
gift redemption doesn't reach session takings — the same gap Cash and Card already have there.

### Claude Code

- Odoo Loyalty gift-card program as the ledger; each redemption a `loyalty.card` history line.
- Debit is **idempotent per payment attempt** — an offline retry must not double-spend. Key on
  a client-generated tender UUID.
- Liability accounting: issuance credits a liability account, redemption debits it, expiry
  posts to breakage revenue.
- Offline behaviour: balance lookup requires network. Define the offline policy explicitly —
  recommend block with a clear message rather than optimistic redemption.
- Partial redemption leaves the remainder on the card, never a new card.

### Acceptance

Same card, same balance, redeemed on all six surfaces with identical arithmetic. Insufficient
balance always yields a split tender, never an abandoned order. Two rapid taps on kiosk debit
once.

---

## 3. Commissary receive — **built in the prototype**

19 Commissary dispatches. Nothing at the branch confirms arrival, so stock never lands and
shortages are invisible.

### States

| State | Meaning |
| --- | --- |
| `draft` | Being built at commissary |
| `sent` | Dispatched, in transit |
| `receiving` | Branch has opened the receipt, counting |
| `received` | Fully received, quantities match |
| `short` | Received less than sent — variance recorded with reason |
| `over` | Received more than sent |
| `damaged` | Received but unusable quantity recorded separately |
| `disputed` | Branch and commissary disagree; escalated |

### Claude Design

New branch-side surface (extends 19 Commissary as a `Receiving` tab, or a screen under 15
Stock — pick one and be consistent):

- **Inbound list** — transfers with `sent` state, dispatch time, item count, source kitchen.
- **Receipt sheet** — per line: item, unit, sent qty, **received qty** (editable, defaults to
  sent), **damaged qty**, variance auto-computed and colour-flagged.
- **Reason required** on any variance: `short-picked` / `damaged in transit` / `wrong item` /
  `temperature fail` / `other + note`. Cannot confirm without it.
- **Confirm** is a deliberate two-step with a summary: `18 lines · 2 short · 1 damaged`. After
  confirm the sheet is read-only and shows who received it and when.
- Photo attachment slot on damaged lines.
- Commissary side gains a variance inbox so shortages are answered, not just logged.
- Arabic: full RTL receipt sheet, numerals localised, variance sign unambiguous in RTL.

### Built so far (design phase)

19 Commissary gains a fourth tab, `Receiving`, holding the branch side of the transfer: an
inbound list (transfer id, source kitchen, driver, dispatch time, line count, state chip) and a
per-transfer receipt sheet. Each line shows sent, received (editable, defaults to sent), damaged,
usable and an auto-computed variance; any line with a variance or damage tints, demands a reason
from a fixed list, and offers a photo slot. Confirm is two-step with a summary
(`5 lines · 2 short · 1 damaged`), and a confirmed sheet is read-only with the receiver's name and
time on it. States `sent → receiving → received / short / over / damaged / disputed` are all
reachable, with two transfers seeded past confirmation so the read-only and variance states exist
without being staged. The commissary side gets a variance inbox: each unanswered discrepancy shows
its lines, reasons and photo marker, with Accept the loss / Dispute — a dispute moves the transfer
to `disputed` and holds valuation.

Still open here: receiving does not yet move 15 Stock's on-hand figures — the receipt records what
arrived, but the branch stock screen reads its own seed data, so the two only meet on the Odoo
side.

### Claude Code

- Odoo Inventory **internal transfer** (`stock.picking`, commissary warehouse → branch
  warehouse). `sent` = picking done at source; branch receipt is the destination picking.
- Partial receipt writes real `stock.move.line` quantities — not a note. Short quantities either
  stay in transit or post to a loss location per Settings.
- Damaged qty posts to a scrap location with the reason as the scrap reference.
- Dispute state blocks auto-valuation until resolved.
- Receipt confirmation is signed by `hr.employee`, timestamped, immutable.

### Acceptance

Send 20 units, receive 18 with 1 damaged → branch stock rises by 17, 1 in scrap, 2 in variance
with reason, commissary sees the discrepancy. Branch on-hand in 15 Stock matches the receipt.

---

## 4. Drawer per terminal — **built in the prototype**

08 Session treats the branch as one cash pool. Real branches have several terminals, each with
its own drawer and its own cashier, and each cashier counts only their own.

### Model shape

```
branch
 └── session (Odoo pos.session, one per branch per business day)
      ├── terminal A (pos.config)
      │    └── drawer shift · cashier · open float · movements · close count
      ├── terminal B
      │    └── drawer shift …
      └── terminal C (handheld / drive-thru window)
```

A drawer shift has its own lifecycle independent of the session: a cashier can close their
drawer mid-session at end of their shift, and the next cashier opens a new shift on the same
terminal.

### States

**Drawer shift:** `closed` → `open` (float declared) → `counting` → `reconciled` |
`variance_pending` → `closed_signed`
**Session:** `open` → `all_drawers_closed` → `reviewed` → `posted`

Session cannot post while any drawer is `open`, `counting`, or `variance_pending`.

### Claude Design

Rebuild 08 Session as three levels:

1. **Branch header** — session day, total expected vs counted, drawer status strip (one chip per
   terminal, colour = state), single blocking message when a drawer is holding the close.
2. **Terminal list** — each row: terminal name, current cashier, open float, sales by tender,
   cash movements in/out, expected cash, counted, variance. Row expands to the drawer's own
   movement log.
3. **Drawer count sheet** — per-denomination count for one drawer only, scoped to one cashier.
   Never shows another cashier's numbers. Variance above the Settings threshold requires a
   reason + manager approval; both are recorded on the sheet.

Also:
- **Cash movements (17 Cash)** get a terminal attribution column — every paid-in, paid-out, drop
  and pickup belongs to a drawer shift, not to "the branch".
- **Shift handover** — a mid-session close/open flow: outgoing cashier counts, signs; incoming
  cashier declares a new float. Both signatures visible.
- **23 Exceptions** variance rows link back to the specific drawer shift, cashier and terminal.
- Cashier-role view shows only their own drawer; manager sees all. Capability gating visible in
  the prototype, not implied.

### Claude Code

- `pos.config` per terminal; drawer shift as a new model (`mezze.drawer.shift`) with
  `session_id`, `config_id`, `employee_id`, float, movements, close count, signature.
- Session aggregation sums drawer shifts; `pos.session` close blocked until all shifts signed.
- Cash movements (`account.bank.statement.line` / POS cash-in-out) carry `drawer_shift_id`.
- Variance posts to the cash-difference account with the reason and approver on the entry.
- Access groups: cashier reads/writes own shift only; manager reads all, approves variance.
- Offline: drawer counts are local-first and sync on reconnect; conflicting counts for the same
  shift must surface as a dispute, never silently overwrite.

### Built so far (design phase)

08 Session now runs on three levels: branch header (expected / counted / variance / drawers signed,
plus a per-terminal status strip and the blocking message), a terminal list with one row per drawer
shift, and a per-drawer count sheet. Drawer states `open → counting → variance_pending →
closed_signed` are all reachable; a variance over ±25 LE demands a reason and a manager PIN.
Mid-session handover (count out, sign, declare the next float) lives on the in-service stage.
Cash at branch level is now the sum of the signed drawers — no branch recount — and the post
button is blocked while any drawer is unsigned. Cash movements carry a terminal and shift, shown
in 17 Cash. The access toggle (manager / cashier) masks other cashiers' figures.

Still open here: 23 Exceptions only carries the terminal on the seeded drawer event, and the
X/Z report views are not yet per drawer.

### Acceptance

Three terminals, five cashiers, two mid-shift handovers in one day → each cashier counts once,
every riyal of movement is attributable to a drawer shift, session total equals the sum of
shifts, close is blocked while any drawer is unsigned, and the posted journal entry reconciles.

---

## Ordering

Build in this order — each one unblocks the next in accounting terms:

1. **Drawer per terminal** — nothing else can be trusted while cash isn't attributable.
2. **Gift card tender** — biggest surface area, mostly repeated UI, immediate liability risk.
3. **Deposit → bill** — smaller volume, high embarrassment cost when wrong.
4. **Commissary receive** — a new surface, independent of the money chains.

## Definition of done for the design phase

- Every state in every table above is reachable in `Mezze POS v3.dc.html`.
- No control exists that doesn't change something visible.
- EN/AR parity with true RTL and Arabic-Indic numerals on all four flows.
- Each flow has at least one visible failure state, not just a happy path.
