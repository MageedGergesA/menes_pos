# Mezze POS — Cashier Guide

For the person on the till: counter sales, taking payment, and the manager-approved
exceptions. Sign in with your personal PIN — your name is stamped on every order and
every sensitive action.

## A counter sale

1. Open a session (start of shift) — confirm the opening cash float in the drawer.
2. Add items: tap categories → products → modifiers/combos.
3. Prices, taxes, and combo pricing are computed by the server, not the screen — you
   cannot accidentally sell at the wrong price.
4. Review the order, then take **Payment**.

## Taking payment

| Tender | How it works |
|---|---|
| **Cash** | Enter amount tendered; Mezze shows change. Drawer kicks (if a drawer is wired). |
| **Card — integrated terminal** | Send the amount to the terminal; wait for the terminal's result. *(Software certified; the physical terminal is certified on-site during your pilot.)* |
| **Card — manual** | Run the card on a standalone machine, then record the reference/approval code. Mezze stores only a reference and the last 4 digits — never the full card number, CVV, or PIN. |
| **Bank / payment QR** | Show the customer a payment QR. *(Note: Egypt / InstaPay QR is not certified — do not present it as a certified tender.)* |
| **Customer account** | Charge to an identified customer's store account (pay later). Requires selecting the customer. |

Mezze **never** stores PAN, CVV, or PIN. See `PAYMENT-CAPABILITIES.md` for the full,
honest tender matrix.

## Split & partial payment

You can split a bill **by amount or by line** and mix tenders (e.g. part cash, part
card). Splitting a bill into per-seat identities is **not** in this version
(planned for V2) — use split-by-amount/line instead.

## Refunds, voids, and comps

These are exceptions and are gated:

1. Trigger the refund / void / comp / discount.
2. A **manager PIN** is required to approve.
3. The action is audited with a signature — who approved, what, and how much.

Never share manager PINs; the audit trail is only meaningful if PINs are personal.

## Drawer & cash control

- Cash movements (pay-ins, pay-outs, drops) are recorded against your session.
- At close, count the drawer and enter the closing figure; Mezze reconciles expected
  vs counted and records the variance for the manager.

## Receipts

Print or offer a digital receipt. Receipts render bilingual and are Odoo-native
(taxes, journal, and totals come from the accounting layer). If the printer does not
fire, see `TROUBLESHOOTING.md`.
