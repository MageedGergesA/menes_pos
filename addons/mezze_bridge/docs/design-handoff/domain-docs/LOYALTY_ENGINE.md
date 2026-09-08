# Loyalty engine

Contract between the prototype (`Mezze POS v3.dc.html`) and the Odoo 19 implementation, covering
every movement of a point: **earn, redeem, expire, reverse, adjust** — plus the promotion and branch
rules that scale them.

**The principle:** points are a **liability the branch issues**, not a number a manager types. So
nothing about them is manual. An order settles, one earn rule executes, one ledger row is written,
and every screen that shows a balance derives it from that ledger.

What the audit found, and what this document fixes: the customer display announced
`You earn 80 points on this order` from its own inline arithmetic (`sub/10`) while accrual never
happened, and the Guests screen carried an **Add 50 points** button that moved a balance no rule had
produced and no ledger explained. Two sources of truth for one number, and neither was the engine.

---

## 1. The one lifecycle

```
order settles ─→ earn rule executes ─→ ledger row (earn, with its expiry) ─→ balance derives
                                                    │
guest redeems ──────────────────────────────────────┼─→ ledger row (burn, FIFO on oldest bucket)
bucket ages out (session close) ────────────────────┼─→ ledger row (expire)
order refunded ─────────────────────────────────────┼─→ ledger row (reverse, keyed to the earn)
manager intervenes (exception, with a reason) ──────┘─→ ledger row (adjust)
```

Five row kinds, one table, one balance:

| Kind | Sign | Written by | Carries |
| --- | --- | --- | --- |
| `opening` | + | migration / seed | the balance the guest arrived with |
| `earn` | + | **the rule, at settlement** | base spend, multiplier, which rule fired, expiry date, idempotency key |
| `burn` | − | redemption as a tender | surface, check, value discharged |
| `expire` | − | session close sweep | which earn bucket aged out |
| `reverse` | − | refund of the original order | the earn's reference, and any shortfall |
| `adjust` | ± | a manager, with a reason | who, why — the only human-entered row |

**The balance is `sum(pts)` over the ledger.** It is never stored beside it. `loyBal(id)` is the only
function any screen calls; there is no `points` field to drift.

## 2. Earn — the rule, not the button

Executed once, at **settlement**, by `loyEarn({guest, net, sur, ref})`:

```
points = floor( net × base_rate × branch_mult × tier_mult × promo_mult )
```

| Input | Value in the prototype | Notes |
| --- | --- | --- |
| `net` | the bill's **eligible net**: subtotal after discounts, **before** VAT and service | the surface passes the figure it already computed for that bill |
| `base_rate` | `LOY_EARN_PER_LE = 0.1` — 1 point per 10 LE | with a 10-point = 1 LE burn, that is **1% back** |
| minimum spend | `LOY_MIN_SPEND = 50` LE | under it, no accrual, and the surface says why |
| `branch_mult` | per branch, group default 1.0 | §6 |
| `tier_mult` | Member 1.0 · Regular 1.25 · VIP 1.5 | derived from 12-month earned base, never assigned by hand |
| `promo_mult` | product of active promotions | §5 |
| rounding | `floor` | never round a liability up |

**Not eligible, ever:** VAT, service charge, tips, gift-card purchases (that is deferred revenue, not
a sale), deposits taken, comped lines, and the value of points already burned on the same bill.
Earning on tax means the branch is issuing liability against money it collects for the state.

**Idempotency.** Every earn row carries `key = surface|order-ref`. A second attempt with the same key
is refused, not re-posted — part payments, offline replays and double taps all collapse to one
accrual. Accrual happens on **full settlement**, not per part payment, so a split bill cannot earn
twice.

**No guest, no accrual.** A check with nobody attached earns nothing, and the surface must say so
rather than compute a number nobody receives. That is exactly the defect on the customer display:
the quote and the accrual now come from the same `loyQuote()`, so the display cannot promise points
the ledger will not issue — with no guest attached it asks for the number instead of announcing an
earn.

## 3. Redeem

Redemption is a **tender**, not a discount — it discharges the loyalty liability, the way a gift card
does (`docs/PAYMENT_VALUE_ENGINE.md` §3). It does not reduce the bill.

- Rate: `LOYALTY_PER_LE = 10` — 10 points discharge 1 LE.
- **Partial is the normal case.** Points rarely cover a whole bill; the gate is *any* points, and the
  remainder stays due on another tender.
- Never more than the guest holds, and never more than the bill can absorb: points that will not fit
  are **kept**, not spent.
- **FIFO on the oldest live bucket**, so redemption always spends the points closest to expiring.
  Allocation is derived by walking the ledger; it is not stored, so it cannot disagree with the rows.
- Offline: **blocked**. A points balance that cannot be checked is a balance that may not exist.
- Reversal: refunding a bill that was part-paid with points re-credits them, matched to the burn.

## 4. Expire

- Life: `LOY_EXPIRE_DAYS = 365` from the earn, per bucket — not one expiry date per account.
- Warning: a bucket inside `LOY_EXPIRE_WARN = 30` days surfaces on the guest record **and** at the
  point of charging, not only in a report.
- The sweep runs at **session close** (`sessPost`), the same moment the day's other liabilities are
  posted, and writes one `expire` row per aged bucket naming the earn it consumed.
- Accounting: expiry is **breakage** — a liability release to income, not a sale.
- A bucket already spent cannot expire; FIFO guarantees the oldest is spent first, so expiry only
  ever takes points nobody used.

## 5. Promotions

A promotion is a **multiplier with a window and a scope**, declared once and resolved by
`loyPromosActive()`; it never re-implements the earn rule.

| Field | Meaning |
| --- | --- |
| `mult` | multiplier applied on top of branch and tier |
| `from` / `to` | window, in days relative to the business date |
| `scope` | `all`, a category, a channel, or a daypart |
| `on` | scheduled but switched off is a real state — an expired promotion is not deleted |

Rules that hold: multipliers **compound** (branch × tier × promo), the earn row records **which** rule
fired, and a promotion is never applied retroactively — a bill that settled yesterday earned under
yesterday's rules, which is why the rule name lives on the row rather than being recomputed.

## 6. Branch rules

| Level | Owns |
| --- | --- |
| Group | base rate, expiry, minimum spend, tier thresholds — one currency of points across the estate |
| Branch | its own `mult`, and whether it participates in a promotion |

Points earned at one branch are spendable at any branch: the liability belongs to the group, so a
branch cannot fork the rate. What a branch *can* do is pay more (a `mult` above 1.0 to build a new
site's regulars) — and its ledger rows carry the branch, so the group can see who issued what.

## 7. Odoo mapping

| Design | Odoo 19 |
| --- | --- |
| Guest | `res.partner` |
| Programme, rules, rewards | `loyalty.program`, `loyalty.rule`, `loyalty.reward` |
| Ledger row | `loyalty.history` (one per movement) |
| Balance | `loyalty.card.points` — **derived** from history, never edited |
| Earn at settlement | POS order confirmation hook |
| Burn | reward application on the POS order, as a tender line |
| Expiry sweep | scheduled action, run at session close here |
| Reversal | refund order's own history entry, linked to the original |
| Tiers | programme rules on 12-month accrued base |
| Branch multiplier | per-`pos.config` programme variant |

Points are a liability account, mirroring gift cards: accrual on earn, release on burn, **breakage on
expiry**. Never revenue, never a discount, never netted into food cost.

## 8. What the prototype now does

- `loyLog(id)` / `loyPush` — the ledger. `loySeed(id)` derives each guest's opening row from their
  seeded balance, so the derived total equals the seed exactly and there is no second number.
- `loyQuote(net, ctx)` — the rule. One function behind accrual **and** every quote shown to a guest.
- `loyEarn(ctx)` — idempotent accrual at settlement. Wired into the handheld's single capture
  (`hhSettleAmt` on close) and the register's tender confirm.
- `loyBurn` / `loyReverse` / `loyExpireAll` / `loyAdjust` — the other four kinds, each the only way
  to write its row.
- `loyBal` / `loyBuckets` / `loyExpiring` / `loyTier` — all derived from the ledger.
- Allocation has one rule with one exception, and the exception is what keeps expiry honest: burns,
  reversals and adjustments consume the **oldest live bucket** (FIFO), while an `expire` row is
  applied to the **bucket it names** (`bkey`). Letting an expiry fall through the FIFO queue aged out
  a bucket it never mentioned and left the same points looking expirable twice — so the sweep is
  idempotent: running it again moves nothing.
- The Guests screen shows balance, tier, next expiry and the ledger itself; **Add 50 points** is gone,
  replaced by a goodwill `adjust` that records who and why.
- The customer display quotes the same rule that will accrue, names the promotion, and asks for the
  guest's number when there is nobody to credit.

## 9. Gaps — Pass 18A closure

1. ~~Orders and Drive-thru cannot attach a guest~~ — **closed.** Register now carries the same
   attach/replace/remove flow as the handheld (`regAttach`/`regRemove`/`regNewGuest`), Orders attaches
   against the specific order's own ref (`tenderCheckKey('orders')`, not the till's active check), and
   Drive-thru resolves `car.cust` to a real guest id instead of a copied name/phone/visits snapshot.
   House account and Loyalty are no longer handheld-only — see `PAYMENT_VALUE_ENGINE.md` §6.3, now
   updated.
2. ~~Refund reversal is wired to the ledger, not yet to the Orders refund flow~~ — **closed, Pass
   18B.** `loyReverse` is replaced by `loyRefundReverse(id, ref, cumEligibleRefunded, cumEligibleBase)`,
   called from the one canonical poster, `ordRefundCommit()` — used by Orders' own refund sheet, Guest
   Recovery's Refund remedy, and the 86-impact sheet's Refund action alike. It is:
   - **Proportional and cumulative.** Reversal = `earnRow.pts × (total eligible refunded so far ÷
     original eligible base)`, rounded, capped to the earn. A second partial refund on the same order
     reverses only the delta still owed — re-submitting the same refunded amount reverses nothing.
   - **Idempotent** on the order ref: the already-reversed total is read back from the `reverse` rows
     on the ledger before computing the delta, so there is no separate "already refunded" flag to drift.
   - **Debt-carrying, not clamped.** If the guest already spent the points a refund would take back,
     the balance goes negative. Mezze policy: **allow loyalty debt.** Clamping to zero or silently
     forgiving the shortfall would misstate what the guest owes; a negative balance is shown as a plain
     number, not an alarm. Future earning clears the debt first — no separate mechanism, `loyBal` just
     sums the ledger.
   - **Eligibility today = every menu line.** No exclusion class (e.g. a non-food or gift-card line)
     exists in the prototype yet, so §11 of the closure spec (non-eligible item refund → 0 reversal)
     has no real case to test against. Claude Code should map this to whichever lines Odoo's loyalty
     programme configuration excludes, and pass that as a narrower `cumEligibleBase`.
   - **Refund destination is independent of the loyalty consequence.** Whether the refunded money
     returns to the original tender or is issued as a gift card (`ordRefundCommit`'s `dest` option,
     Pass 18C), the SAME `loyRefundReverse` call runs against the SAME eligible-refund basis. Money
     destination and loyalty reversal are two separate facts and neither infers the other.
   - **Expired points are not re-penalised.** Reversal only ever removes points that are still
     represented by the earn row's un-reversed remainder; it does not chase points that already left
     the balance via `expire` — that would double-charge the guest for a decision (the 365-day sweep)
     the refund had nothing to do with.
   - **Original earning basis, always.** The reversal reads the ORIGINAL `earn` row's `.pts` and
     `.base` — never today's multiplier — so a promo or tier change since the sale cannot change what
     a refund gives back.
3. **Category and daypart promotion scopes are declared but not enforced**: the surfaces pass a net
   figure, not a line breakdown, so only `all`-scope promotions multiply today.
4. **Tier changes are silent.** Crossing into VIP should notify the guest and the branch.

## 10. Acceptance

Settle an 800 LE net bill for a Member at Downtown with no promotion: **80 points**, one `earn` row
carrying base 800, multiplier 1.0, rule *Base rate*, expiry 365 days, key `hh|T12`. Settle the same
check again: refused as a duplicate, balance unchanged. A 40 LE bill earns nothing and says why. With
*Iftar double points* live, the same 800 LE earns 160 and the row names the promotion. Redeem 250
points: one `burn` row, 25.00 LE against the bill as a tender, oldest bucket first, remainder still
due. Run the session close with a bucket 4 days overdue: one `expire` row for exactly its unspent
remainder, breakage posted, and the balance every screen shows drops by that amount — because they
all read the same ledger.
