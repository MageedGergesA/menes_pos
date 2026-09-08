# Session lifecycle

Screen **08 Session** is one workflow in six stages, not a screen with a close button:

**Opening control → In service → Manager handover → Terminal closing → Branch closing → Posted**

The strip at the top is navigable in both directions (except Posted, which is terminal), because a
real close does not happen in order — a manager hands over mid-service, comes back to the terminals,
and finishes the branch close later.

---

## 1. Opening control

Four facts, each refusable, before a float can move:

| Fact | Source | Refused when |
|---|---|---|
| Terminal | `TERMINALS` (Counter 1, Bar, Drive-thru window, Handheld pool) | it has no drawer (card/wallet only), or it already has an open drawer |
| Cashier | `CASHIERS` — the person who signs | they already signed for another open drawer |
| Drawer | Drawer A / B / C-spare | — |
| Float | counted on the keypad, standard 1,500 LE | — |

A float that differs from the standard is shown as a delta on the way in (`+250.00 LE against the
standard float — the reason is asked for at the close`), so the variance has a history before it is
a variance.

Opening writes a **drawer shift** (`shifts`) for that terminal — id, cashier, drawer, float, start
time, state `open` — plus the session's first cash-movement line. Everything downstream (expected,
counted, variance, the close checklist) reads those shifts, so there is one source for "whose
drawer is this".

## 2. In service

Five things at once, all live: **payments** (per-method takings and share), **movements** (cash in /
cash out with a reason, each posting to the cash journal with a name), **drawers** (every terminal
with expected-in-the-drawer and state), **staff** (who is still on the clock, with a clock-out
button per person), **exceptions** (e-receipts queued/rejected, drawers holding the close).

Cash in and cash out are the only way money moves without a sale, and each one belongs to a drawer
shift — never to "the branch".

## 3. Manager handover

The audit's second named gap. A handover is a record with five parts:

- **outgoing** — the signed-in manager
- **incoming** — picked from the manager list; the same name twice is refused
- **spot count** — what is physically in the drawers *now*, counted in front of both; compared
  against expected and shown as over/short before signing
- **time** — stamped, not typed
- **note** — free text; **required** when the spot count is more than the drawer limit out

Beside it, **what the incoming manager accepts**: open checks, card holds and their value, drawers
still open, cash expected in the drawers, staff on the clock. That list is the point — the incoming
manager is inheriting exposure, not a shift.

Signed handovers stay on the session with both names, the counted figure, the variance and the
note, so anything found later is measured from the handover, and the shortfall lands on the shift
that had it.

## 4. Terminal closing

Per terminal, in its own row: cashier, drawer, hours, **expected**, **counted**, **variance**,
state, and the action the state allows — start the blind count, count on the drawer pad, sign and
close, or approve a variance over the limit.

Expected is float + cash taken on that terminal + that terminal's own movements. It reads
`hidden until signed` while the count is open: the cashier counts blind, signs, and only then sees
the difference. A variance over the limit needs a manager's approval on that drawer, not a
branch-level shrug.

The totals strip carries expected, counted (or `incomplete`), variance, and drawers signed (`1/4`).

## 5. Branch closing

The method reconciliation (cash from the signed drawers, card/wallet/Instapay against their
journals, gift card against the liability) **plus the checklist**. Seven lines, each live, each with
its own list and a way to resolve it:

1. **All drawers closed and signed** — names the terminals still open → Terminal closing
2. **All payment methods reconciled** — names the uncounted methods, or the gap in LE
3. **Open checks resolved** — the actual refs and values → the order board
4. **Pre-authorisations resolved** — every card hold still open on a tab, each with **Capture** or
   **Release**, and what each one means (a hold that survives the close captures tomorrow at a
   stale amount, or expires and the money is gone)
5. **Staff clocked out** — who is still accruing hours → break compliance
6. **Tax receipts submitted** — how many are queued for the ETA, with the 24-hour window named
7. **Manager approval** — last, on a PIN

Approval is refused while any of lines 1–5 is open (tax is allowed to lag, and the toast says the
queued receipts stay in the approver's name). Posting is refused without approval, and the button
says which of the two is missing. Approval writes the manager's name and time into the audit log
and the Z report.

## 6. Posted

Journal entries per method, sales and VAT, the X/Z/journal reports, and the session is read-only.
Reopening it is an accounting action with its own trail.

---

## Odoo mapping

- One `pos.session` per branch day; each drawer is a cashier's session within it.
- Opening writes the session's opening balance and a `cash.statement` line per movement.
- Terminal counts are the per-cashier closing balances; the variance posts to the cash-difference
  account.
- Card, wallet and Instapay reconcile against their own journals — the POS never treats them as
  cash.
- Gift cards discharge a liability the branch already holds; they are system-counted, not counted
  at the drawer.
- Pre-authorisations are payment-terminal holds: capture or release, never "leave it".
- The manager handover is an extension — Odoo has no handover object, so it is stored on the
  session with both employee references.

## Bilingual

Every string goes through `tr()` / `N()`. Bare words already owned by other surfaces (`Terminal`,
`Expected`, `Counted`, `Variance`, `Drawers signed`, `queued`, `Approve`, `Time`) reuse the
existing entry where the meaning matches; the rest carry their own keys per
`docs/AR_KEY_COLLISIONS.md`.
