# Payment & value engine

Contract for every surface that moves money in Mezze POS: **01 POS**, **06 Orders**, **23
Handheld**, **07 Drive-thru**, **24 Kiosk**, **QR at the table**, **33 Call centre**.

**The principle:** these seven surfaces are *clients*. They do not each define what a payment is.
There is one engine, one registry of value types, one lifecycle, one audit trail. A surface decides
only two things: which value types it offers, and how the interaction looks on its hardware.

Enforced in the prototype: `VALUE_TYPES` is a single registry and each surface calls
`tenderMenu(surface, due)` for its set. POS, Orders, Drive-thru **and Handheld** tender lists are
all derived, not authored — no surface carries a list of its own any more. Adding a value type makes
it appear on every surface that claims it, in one edit — the class of bug that left gift card wired
on two surfaces out of six.

**Surfaces that offer a type must be able to satisfy it.** House account and Loyalty need a guest on
the check, and only the handheld can attach one, so only the handheld claims them. A chip that can
never go ready is worse than an absent one.

---

## 1. The registry

| Value type | Kind | Drawer | Partial | Journal | Surfaces |
| --- | --- | --- | --- | --- | --- |
| Cash | cash | yes | yes | Cash — branch till | POS, Orders, Handheld, Drive-thru, Kiosk, Call centre |
| Card | card | no | yes | Bank — card acquirer | all |
| Wallet | card | no | yes | Bank — wallet clearing | all |
| Instapay | card | no | yes | Bank — Instapay clearing | POS, Orders, Handheld, Drive-thru, QR |
| Meeza | card | no | yes | Bank — Meeza acquirer | POS, Orders, Handheld, Drive-thru, Kiosk, QR |
| Fawry | card | no | **no** | Bank — Fawry clearing | POS, Orders, Handheld, QR |
| ValU | credit | no | **no** | Bank — ValU settlement | POS, Orders, Handheld |
| Gift card | stored | no | yes | Gift-card liability | all |
| Deposit | stored | no | yes | Customer deposits held | POS, Orders, Handheld |
| House account | credit | no | yes | Trade receivables | POS, Orders, Handheld, Call centre |
| Loyalty redemption | stored | no | yes | Loyalty liability | POS, Orders, Handheld, Call centre |
| Comp | adjust | no | no | Service recovery — comps | POS, Orders, Handheld |
| Refund | adjust | yes | yes | follows the original tender | POS, Orders, Handheld, Drive-thru |
| Tip | adjust | yes | no | Tips payable | all |

**Kind** decides accounting and drawer behaviour, and is the only thing the engine branches on:

- `cash` — physical money; affects a drawer shift (`docs/P0_CRITICAL_WORKFLOWS.md` §4)
- `card` — an acquirer or provider settles later; needs a clearing account and reconciliation
- `stored` — value the branch already holds as a liability; redemption *discharges* it
- `credit` — the branch is owed money after service
- `adjust` — not a tender; changes what is owed or owing. Excluded from `tenderMenu` deliberately: a
  comp, a refund and a tip each have their own flow with their own approval.

**Partial = no** is a real constraint, not an omission. Fawry and ValU authorise a specific amount
against an external reference; they cannot part-settle a bill.

## 2. Shared lifecycle

Every tender moves through the same states. A surface renders them; it does not define them.

```
quote → authorize → capture → settle
                 ↘ decline
      any point:  → void (before capture)
      after:      → refund (partial or full)
```

| Stage | Meaning | Who owns it |
| --- | --- | --- |
| `quote` | Amount due computed, nothing committed | Engine |
| `authorize` | Funds or value confirmed available | Provider / ledger |
| `capture` | Value taken; the bill is reduced | Engine |
| `settle` | Money reaches the bank or the drawer reconciles | Bank / session close |
| `void` | Cancelled before capture; no ledger entry survives | Engine |
| `refund` | Reversal after capture; a new, linked entry | Engine |

Cash collapses `authorize`/`capture`/`settle` into one moment at the drawer. Card separates all
three: authorised at the terminal, captured on the order, settled overnight by the acquirer. The
engine must not pretend these are the same, because reconciliation depends on the difference.

## 3. Per-method behaviour

Read with §2. Only the deviations are listed — anything unstated follows the shared lifecycle.

### Cash
- **Auth/capture**: simultaneous. Amount tendered may exceed due; change is computed and owed.
- **Partial**: yes. Remainder stays due and the modal must not dismiss.
- **Reversal**: counter-payment on the same drawer shift, never an edit.
- **Refund**: cash out of the same drawer; needs a reason and, above the threshold, a manager.
- **Idempotency**: client tender UUID. A double tap must not double-count the drawer.
- **Offline**: fully available — cash needs no network.
- **Accounting**: `Cash — branch till`; belongs to a **drawer shift**, not a branch.
- **Audit**: cashier, terminal, drawer shift, time.
- **UI**: keypad, quick denominations, change due prominent. Never auto-close on exact tender.

### Card / Wallet / Meeza
- **Auth**: terminal or provider returns an approval + reference. Store the reference, not the PAN.
- **Capture**: on approval for card-present; explicitly for card-not-present.
- **Settle**: acquirer batch; reconciled against the bank, **not** against the drawer.
- **Partial**: yes — split tender is the normal case, not an edge one.
- **Reversal**: void before batch close, refund after. The UI must not offer "void" once settled.
- **Idempotency**: the acquirer reference. Never retry with a new reference on timeout — query first.
- **Offline**: Card and Meeza *queue* (store-and-forward, with the branch carrying the risk and a
  visible queue count); Wallet **blocks** — a wallet balance cannot be assumed.
- **Accounting**: clearing account per provider; fees posted separately, never netted into revenue.
- **UI**: waiting state with a cancel that is honest about whether it can still cancel. Show last-4
  and auth code on the settled row.

### Instapay
As Card, except: **blocks offline** (bank-rail confirmation is the whole point), and reversal is a
provider refund with a longer window. Reference is mandatory on the tender row.

### Fawry
- **Partial: no.** A Fawry reference is for one amount.
- **Auth**: guest pays against a reference, possibly off-premises; the order waits.
- **UI**: the order must show a *pending* state that is clearly not paid, and a way to check.
- **Offline**: blocked.

### ValU (buy-now-pay-later)
- **Kind `credit`**: the provider pays the branch; the guest owes the provider.
- **Partial: no.** Minimum basket rules apply — surface the minimum before the guest commits.
- **Reversal**: provider cancellation within a window; after that, a refund to the provider.
- **Accounting**: settlement account plus provider commission as an expense. **Commission is the
  largest gap between what a guest pays and what the branch keeps** — never net it into revenue.

### Gift card
- **Auth**: balance lookup. Requires network; the offline policy is *block with a clear message*,
  not optimistic redemption.
- **Capture**: debit the `loyalty.card` balance; partial redemption leaves the remainder on the card,
  never issues a new one.
- **Partial**: yes, and it is the important case — applying a 45 balance to a 180 bill must leave a
  live split tender with the remainder highlighted.
- **Reversal**: re-credit the same card, idempotent on the tender UUID.
- **Accounting**: issuance credits `Gift-card liability`; redemption debits it; expiry posts to
  breakage revenue.
- **Audit**: card (masked to last 4), balance before and after, surface, employee.
- **UI**: `lookup / not_found / expired / void / zero / sufficient / insufficient / applied` — all
  eight reachable. Guest-facing surfaces (Kiosk, QR) get a keypad and no manager override.

### Deposit
- **Auth**: the deposit already exists against a booking; "authorization" is *linking* it to a check.
- **Capture**: applied at payment as a **pre-applied tender row** that cannot be deleted, only
  unlinked by a manager.
- **Partial**: yes in both directions — smaller than the bill leaves a balance due; larger leaves a
  **credit the guest is owed**, which must be refunded or issued as a gift card before the check
  closes.
- **Reversal**: unlink and re-hold against the booking; refund and forfeit are separate dispositions.
- **Idempotency**: booking id. A deposit **cannot** be applied to two orders — enforce at the DB
  level, not the UI.
- **Accounting**: `Customer deposits held` (a liability), not revenue, until applied. Forfeited
  deposits post to their own revenue account.
- **UI**: state chip on the booking (`held / applied / partial / credit / refunded / forfeited`), a
  deposit line on the check distinct from a discount, forced disposition on cancel.

### House account
- **Auth**: credit-limit check. Refuse over limit rather than warning after the fact.
- **Capture**: charge posts to the partner's receivable; the check settles.
- **Settle**: invoiced periodically; payment against the invoice is a separate flow.
- **Reversal**: credit note, never a deletion.
- **Accounting**: `Trade receivables` per partner. Ageing matters — surface overdue balances at the
  point of charging, not only in a report.
- **UI**: account name, limit, current balance, remaining credit, all before confirming.

### Loyalty redemption
- **Auth**: points balance and the conversion rule.
- **Capture**: burn points; the discharge is a liability reduction, not a discount.
- **Partial**: yes — points rarely cover a whole bill.
- **Reversal**: re-credit points on refund, matched to the original burn.
- **Accounting**: `Loyalty liability`. Accrual on earn, release on burn, breakage on expiry.
- **UI**: points balance, value in currency, and what is left after. Never show points without their
  cash value.

### Comp (`adjust`)
See `docs/COMP_ACCOUNTING.md`. Not a tender: the line keeps its full price and a negative comp line
offsets it, so gross sales are unchanged. **Stock stays consumed.** Always a manager decision, with a
senior threshold. Never posted as a discount or a void.

### Refund (`adjust`)
- **Returns to the original tender** by default. Refunding a card sale to cash is a fraud pattern and
  needs manager approval plus a reason.
- **Partial**: yes, per line or per amount.
- **Idempotency**: refund id. A retried refund must not pay twice.
- **Offline**: blocked — a refund needs the original tender's record.
- **Accounting**: mirrors the original journal; never a negative sale against today's revenue if the
  sale was yesterday's.
- **Audit**: original order, original tender, reason, approver.

### Tip (`adjust`)
- Not a tender for the bill; it is money **owed to staff**.
- **Capture**: with the tender for card tips, or declared for cash tips.
- **Accounting**: `Tips payable`, a liability — never revenue, never in food-cost percentage.
- **Service charge is not a tip.** If the branch levies one, state in Settings whether it is
  distributed, and compute it on the **net** of comps so staff are not paid on revenue never received.
- **Audit**: employee, shift, declared vs card-captured.

## 4. Cross-cutting rules

**Partial payment.** The engine holds a running `due`. Any partial capture reduces it and leaves the
payment surface open with the remainder live. No surface may dismiss its own modal on a partial.

**Idempotency.** Every capture carries a client-generated UUID. Retries — offline replay, double tap,
network timeout — key on it. This is the single most important defence in the engine: the flows most
likely to be retried (kiosk, QR, queued card) are exactly the ones a guest cannot see the state of.

**Offline behaviour**, three policies, and each type must declare one:
- `full` — works offline (Cash, Deposit, House account, Comp, Tip)
- `queue` — store-and-forward with visible risk (Card, Meeza)
- `block` — refuse with a clear message (Wallet, Instapay, Fawry, ValU, Gift card, Loyalty, Refund)

Never optimistically redeem stored value offline. A gift card or points balance that cannot be
checked is a balance that may not exist.

**Audit.** Every capture and reversal records: order, surface, terminal, drawer shift (where cash is
involved), employee, approver where required, value type, amount, provider reference, timestamp, and
the idempotency key. An entry is never edited; corrections are new linked entries.

**Accounting.** One journal per value type as tabled above. Three rules that are violated most often:
provider fees are an expense and never netted into revenue; stored-value redemption is a liability
discharge and never a discount; tips are a liability and never revenue.

**UI states.** Every surface must be able to render: `idle`, `quoting`, `awaiting provider`,
`declined (with reason)`, `partial (remainder live)`, `captured`, `voided`, `refunded`, `offline —
queued`, `offline — blocked`. Guest-facing surfaces additionally need a *get help* path, because
there is no cashier to interpret a failure.

## 5. Acceptance

The same 180 LE bill settles identically on all seven surfaces for every type each offers. A 45 gift
card leaves a 135 remainder on every one of them. Two rapid taps capture once. Pulling the network
mid-tender produces the declared policy for that type — queued, or blocked with a message, never a
silent success. A refund returns to the original tender without a manager, and to a different tender
only with one. The session close (`docs/P0_CRITICAL_WORKFLOWS.md` §4) reconciles cash against drawer
counts and every other type against its own journal.

## 6. Known gaps in the prototype

1. Register-side tenders live on the check rather than the order board, so a POS capture does not
   reach session takings. Affects Cash and Card equally; pre-existing.
2. `Comp`, `Refund` and `Tip` are excluded from `tenderMenu` by design, but only Comp and Refund have
   built flows — tip declaration exists on the staff surface, not as an engine-level capture.
3. **Prerequisites travel with the menu.** `tenderMenu(surface, due)` returns
   `{k, g, ready, why, how, note}` for each type, so **every** surface renders the blocked state from
   one place rather than each remembering to call `tenderReady`. POS, Orders and Drive-thru all read
   it; a failing chip greys out and refuses by name. The check runs again at capture.

   `Deposit` is offered on POS and Orders and gated on a linked booking deposit — that prerequisite is
   satisfiable today, so the chip works.

   `House account` and `Loyalty` require **a guest attached to the check**, and both are now live on
   the handheld — the one surface that reads the registry *and* has an attach flow. The handheld's
   hardcoded `HH_TENDER` is gone: it calls `tenderMenu('hh', hhShare())` like everyone else, which
   also gave it the Instapay, Meeza, Fawry, ValU and Deposit it had been silently missing.

   Three things that unification forced, each collapsing a value that existed twice:

   - **One guest book.** The handheld had its own seeded guest list, with points the register had
     never heard of. `hhBook()` now derives from `state.guests` (res.partner), an attachment stores
     the record **id**, and a guest created on the device is a book record like any other. So
     `tenderGuest(surface)` resolves the same partner the receivable and the booking read.
   - **One check key.** `tenderCheckKey(surface)` answers *which bill* a surface is settling — the
     register's `state.check`, or the handheld's own table. Testing a handheld prerequisite against
     `state.check` was reading a different bill entirely.
   - **One capture.** `hhSettleAmt` is the only place a handheld tender reduces the principal, takes
     the tip and clears the table; the gift-card path had carried its own copy. `hhGuard` applies the
     shared refusals from the registry — partial rules (Fawry and ValU refuse to part-settle),
     offline policy, and the type's prerequisite, re-tested at capture.

   Loyalty's readiness gate was also wrong in the same way: it tested whether points covered the
   **whole** amount, which contradicts `partial: true` and blocked the chip on any real bill. It now
   gates on *any* points and says what they cover — the remainder stays due on another tender.

   The **debits now post**: House account writes a `charge` row to the partner's receivable ledger
   (exposure snapshotted before the write) and Loyalty burns points off the book balance. Points are
   captured as a **tender**, not a discount — they no longer reduce `hhBill` through `hhCut`, so the
   bill stays a true gross-less-agreed-reductions figure. A linked booking deposit is spendable once:
   `depFree`/`depSpend` derive what is left from the spend, and the register's check reads the same
   figure, so two surfaces cannot each apply it.

   **Fixed:** `tenderMenu('orders')` and `tenderMenu('dt')` now pass `due` (both calls already sat
   below its declaration; the earlier temporal-dead-zone hang came from hoisting the call above it,
   not from the argument). The Orders *filter* row passes `0` deliberately — it lists method names and
   never tests readiness.

   **Pass 18A:** the register no longer lacks an attach flow — House account and Loyalty are now
   offered on `pos`, `orders`, `hh` and `call` alike, all reading `state.checkGuest` through the one
   `tenderCheckKey(surface)`/`tenderGuest(surface)` pair (register keys off `state.check`, Orders off
   the specific order's own ref via `S.ordSel`, so opening a different order never inherits the till's
   guest). Register's flat, anonymous "Apply points" checkbox — a second, unaudited loyalty
   discount with no ledger behind it — is removed; redemption on every surface now goes through the
   one Loyalty tender. Still Claude Code's side: handheld captures still live in `hhPaid` rather than
   in session takings (gap 1).

4. **Offline policy is enforced at capture** from the registry: any type declaring `offline: 'block'`
   refuses while the terminal is offline rather than queueing value it cannot verify.
