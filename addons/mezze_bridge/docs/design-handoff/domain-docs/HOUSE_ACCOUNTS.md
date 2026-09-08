# House accounts

Contract between the prototype (16 Guests → guest → **Account** tab, and `House account` as a value
type on the payment surfaces) and the Odoo 19 implementation.

**The principle:** a balance is not an account. An account has a **limit**, **exposure** that includes
charges not yet invoiced, an **age profile**, the **statements** it was invoiced on, and the
**payments** made against them. Until those five exist, "charge to account" is an IOU nobody can
chase.

---

## 1. Charge to account as a payment method

`House account` is a registered value type in the payment engine
(`docs/PAYMENT_VALUE_ENGINE.md`), kind `credit`, offered on POS, Orders and Handheld.

It is **gated on its prerequisite** and the test runs again at capture, not only when the chip is
tapped:

| Condition | Refusal |
| --- | --- |
| No guest attached to the check | *No guest on this check · Attach a guest before using stored value or credit* |
| Guest has no open account | *No house account · Open one on the guest record — it needs a credit limit* |
| Charge would exceed the limit | *Over the credit limit · 13,240 / 12,000 · take a payment before charging more* |

When available, the chip carries the headroom: *Omar Nabil · 5,140.00 left on the limit*. Refusing
before the charge is the whole point — a limit checked after the fact is not a limit.

## 2. What the account profile shows

Verified in the prototype on the seeded corporate (limit 12,000):

| Figure | Value | Meaning |
| --- | --- | --- |
| Credit limit | 12,000.00 | Set per partner, not global |
| Invoiced, unpaid | 3,100.00 | On a statement, still owed |
| Pending, not yet invoiced | 3,760.00 | Charged since the last statement |
| **Total exposure** | 6,860.00 | invoiced + pending |
| Available credit | 5,140.00 | limit − exposure |

**Exposure, not balance, is what the limit tests.** A branch that only counts invoiced amounts will
happily let a corporate run 4,000 past its limit between statement runs. This is the single most
common error in POS house accounts.

**Aging** — invoiced and unpaid, bucketed: `Current` · `31–60` · `61–90` · `Over 90`. The seeded
account shows 3,100 sitting in 31–60, which is the row a finance team acts on. Buckets sum exactly
to *Invoiced, unpaid*.

**Statements** — one row per invoice with its amount, what remains open, its date, its due date and a
state: `Open` · `Part paid` · `Overdue` · `Paid`. Seeded: INV-0724 paid in full; INV-0725 part paid,
5,100 raised, 2,000 received, 3,100 open.

**Transactions** — the ledger: charges (with the order reference), invoices, payments. Each charge
shows whether it is on a statement or still `unbilled`, so the pending figure is traceable to its
lines rather than asserted.

**Payments** appear in the same ledger, negative and green, tagged to the invoice they settle.

## 3. Corporate terms

Both are per-account and editable in the panel:

- **Invoice period** — `Weekly` · `Fortnightly` · `Monthly` (seeded Monthly). Unbilled charges are
  gathered onto one invoice at the end of the period.
- **Payment terms** — `Due on receipt` · `Net 15` · `Net 30` · `Net 60` (seeded Net 30). Sets the due
  date and therefore the aging clock.

Changing terms applies to invoices raised from the **next** period, never retroactively — a due date
that moves after the fact makes aging meaningless.

`Raise an invoice now` closes the period early, moving pending charges onto a statement and starting
the clock. It refuses when nothing is pending.

## 4. Odoo mapping

| Design | Odoo |
| --- | --- |
| Guest / corporate | `res.partner` (`customer_rank > 0`) |
| Credit limit | `credit_limit` on the partner, with `use_partner_credit_limit` enabled |
| Charge to account | `pos.order` settled to a **receivable** payment method (`account.payment.method` of type receivable), not cash/bank |
| Charge line | `account.move.line` on the partner's receivable account |
| Invoice / statement | `account.move` (`out_invoice`), one per period per partner |
| Payment terms | `account.payment.term` — Net 15/30/60 |
| Invoice period | scheduled action grouping unbilled POS orders into one `account.move` |
| Aging | `account.aged.receivable` report — buckets are Odoo's, not ours |
| Payment | `account.payment` reconciled against the invoice |
| Credit note | `account.move` (`out_refund`) — the only way to reverse a charge |

**Accounting rules that are violated most often:**

1. A house-account sale is **revenue on the day of service**, with the receivable as the balancing
   entry. It is not deferred until the invoice is paid.
2. The receivable is per **partner**, not per branch — a corporate eating at three branches has one
   balance and one limit.
3. `Trade receivables` is never used as a clearing account for card settlement. Different accounts,
   different reconciliation.
4. A charge is reversed by a **credit note**, never by editing or deleting the original line.

## 5. Permissions

| Role | Can |
| --- | --- |
| Server | Charge to an account that is open and inside its limit |
| Manager | Open/close an account, take a payment, raise an invoice early |
| Head office / finance | Set the limit, terms and invoice period; issue credit notes |
| Accountant | Read the ledger and the aged report; reconcile payments |

A manager should not be able to raise a limit to push a charge through — limit changes belong to
finance, and the audit trail must show who changed it and when. In the prototype the limit is
displayed, not editable at branch level, which reflects that.

## 6. Acceptance

Attach the corporate to a check and charge 2,000: exposure rises to 8,860, available credit falls to
3,140, the charge appears in Transactions as `unbilled`, and the aging buckets do not move. Charge
6,000 instead: refused, naming the limit. Raise an invoice: the two unbilled charges move onto a new
statement with a Net 30 due date, pending falls to zero, invoiced rises by the same amount, and
exposure is unchanged. Record a payment against INV-0725: its state moves from `Part paid` to `Paid`,
the 31–60 bucket empties, and exposure falls by the payment.

## 7. Known gaps

1. ~~The debit is not wired~~ — **closed, Pass 18A.** Capturing `House account` at any till (Register,
   Orders or the handheld) now posts the same `charge` row to the receivable ledger the guest record
   writes to, snapshotted before the write — see `docs/PAYMENT_VALUE_ENGINE.md` §6.3.
1a. ~~Partial was declared but not honoured~~ — **closed, 18A-V.** The tender was gated and captured
   as all-or-nothing: `tenderReady` refused the whole chip unless the *entire* remaining due fit
   under the limit, and confirm posted the full due regardless. It now mirrors Loyalty exactly —
   ready whenever any room remains, captures `min(due, room)`, and the note says when the rest
   stays due.
2. The ledger is seeded for one partner. Multi-partner and multi-branch consolidation is Claude Code's
   side, and item 2 of §4 is the rule to build against.
3. Aging ages are seeded rather than computed from real dates, because the prototype has no calendar
   beyond the business day. The bucket logic is real; the input dates are not.
4. Statement PDF/email delivery is out of scope here — Odoo's invoice sending covers it.
