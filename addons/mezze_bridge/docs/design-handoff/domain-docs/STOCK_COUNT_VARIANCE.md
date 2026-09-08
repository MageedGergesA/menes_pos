# Stock count → variance → approval → post

Contract between the prototype (`Mezze POS v3.dc.html`, screen 15 Stock) and the Odoo 19
implementation. This is the transition the audit named as missing: a physical count previously
overwrote on-hand the instant it was keyed.

**The principle:** a count is a **claim**, not a fact. It opens a variance that someone explains and
someone signs before any quantity moves. Overwriting on-hand from a count destroys the evidence of
the discrepancy — the branch loses the ability to ask why, and food cost silently absorbs it.

---

## 1. The chain

```
count            a counter keys the physical figure against a hidden expected
  ↓
review           the variance is computed and shown: qty, cost, %
  ↓
explain          a reason from the fixed list is attached
  ↓
approve          a person signs; over tolerance that person must be a manager
  ↓
posted           NOW the stock move is written; the record locks
```

Two properties matter and are both built:

- **On-hand does not change until `posted`.** The count sits in the queue with the old figure live.
- **Approve and post are separate.** Approval is a person accepting the number; posting is a ledger
  action. Collapsing them hides who accepted what.

### States

| State | Meaning | Who can move it on |
| --- | --- | --- |
| `review` | Counted, variance computed, no reason yet | Anyone who can count |
| `explained` | Reason attached | Counter, or manager |
| `approved` | Signed, not yet in the ledger | Manager (or anyone, inside tolerance) |
| `posted` | Stock move written, record immutable | — |

A zero-variance count is seeded straight to `approved` with `Miscount — recounted`: there is nothing
to explain, but it still requires the explicit post, so the ledger action always has an author.

## 2. What the screen shows

Every open variance carries all six figures, because a reason cannot be chosen sensibly without
them:

| Field | Note |
| --- | --- |
| Expected | System on-hand at the moment of counting — stored on the record, not recomputed |
| Counted | The physical figure |
| Difference | Signed quantity, in the item's UoM |
| Cost difference | `difference × product cost` — the number finance cares about |
| Variance % | `difference ÷ expected` — the number a chef cares about |
| Reason | Fixed list (below) |
| Approval requirement | Whether this one needs a manager, and who signed |

**Reasons** — fixed, with a fault class so reporting can group them:
`Miscount — recounted` (count) · `Unrecorded waste` (process) · `Unrecorded transfer` (process) ·
`Delivery never received` (supply) · `Recipe over-portioning` (kitchen) · `Theft suspected` (loss) ·
`Unit of measure error` (data) · `Other`

Two of these should trigger work elsewhere and are the reason the list is fixed:
`Unrecorded waste` means the waste flow was bypassed, and `Delivery never received` means a
commissary receipt is wrong. Both are cross-references, not just labels.

## 3. Tolerance and approval

- Inside tolerance — **±2% and under 300 LE** — any user may approve and post. The prototype ships
  these; both belong in Settings, per role.
- Outside either bound, a manager PIN is required. Percentage and value are **OR**, not AND: 0.4% of
  a lamb delivery is real money, and 30% of a mint bunch is not, so neither test alone is enough.
- A reason is required before approval regardless of size. An approved variance with no reason
  teaches the branch nothing.
- The counter may not approve their own out-of-tolerance count. Enforce
  `approver_id != counted_by_id` server-side.

## 4. Odoo mapping

- The count is an `stock.inventory` / `stock.quant` adjustment, but **not applied on create**. Model
  the queue as a `mezze.stock.count` record holding `product_id`, `expected_qty`, `counted_qty`,
  `reason`, `state`, `counted_by`, `approved_by`, `posted_by` and timestamps.
- On post, write the inventory adjustment through the normal Odoo path so valuation follows: the
  difference posts to the **inventory-difference** account (a stock-loss account), never to COGS.
- `expected_qty` is frozen at count time. If stock moves between counting and posting — a sale, a
  delivery — the variance must be recomputed and the record sent back to `review` rather than posted
  against a stale expectation. This is the one race worth handling explicitly.
- A posted count is immutable. A wrong one is corrected by a new count, leaving both in history.
- Blind counting: the counter should not see `expected` while keying. The prototype's count sheet
  shows the current figure today — for a real blind count, gate it behind a Settings flag, the way
  the drawer count already hides expected until signing.

## 5. Permissions

| Role | Can |
| --- | --- |
| Line staff | Count; explain; approve and post inside tolerance |
| Shift lead | Same, plus approve out-of-tolerance up to a higher bound |
| Manager | Approve and post anything; cannot approve their own count |
| Accountant | Read-only, plus the resulting journal entries |

## 6. Reporting

Once counts are a queue rather than an overwrite, the useful numbers appear:

- Variance by item, by reason, by counter, by period — and the **value** of it, not just quantity.
- Shrinkage trend per item: repeated negative variance on one product with `Miscount` attached every
  time is a UoM or a portioning problem, not a counting problem.
- Time-to-post: counts left unapproved are the same class of problem as an unsigned drawer.

## 7. Blind counting — decided

**Counts are blind by default.** The sheet opens at **zero**, not at the book figure (seeding the
field with the answer is the same defect as showing it), and the expected quantity is hidden until
the count is saved.

A manager can reveal it with a PIN. The reveal is a logged event *and* is carried on the variance
row, so a count taken with the answer in view can never afterwards be mistaken for a blind one:
every row reads either *counted blind* or *book figure was visible*.

**Recount threshold: 10%.** A single count further out than that lands in state *Recount required*
rather than *Variance to review*. It cannot be approved — and attaching a reason does **not**
discharge it, because explaining a 28%-out claim would otherwise make it quietly signable. The
recount **replaces** the claim on the same row (`first` keeps the original figure for the audit)
rather than opening a second variance for one shelf; two rows for one count is how a shelf gets
adjusted twice.

Rejected: a fixed 5% threshold (too noisy for weighed goods), and blinding only high-value
categories (the counter then learns which shelves are watched).

## 8. Acceptance

Count 10 kg of lamb against an expected 12.5: the row shows −2.5 kg, −1,025.00 LE, −20%, state
*Variance to review*, and **on-hand stays 12.5**. Approving without a reason is refused. With
`Recipe over-portioning` attached, approval still demands a manager PIN because the variance is
outside both bounds. After approval the state reads *Approved — not posted* and on-hand is still
12.5. Posting sets on-hand to 10, writes −1,025.00 LE to the inventory-difference account, and locks
the record with the poster's name and time.

Blind: opening a count sheet shows no expected figure and starts at zero. Counting 9 kg of lamb
against an expected 12.5 (28% out) lands in *Recount required*; attaching `Theft suspected` leaves
it there; counting again at 9.2 replaces the figure on the same row, keeps 9 as the first count, and
moves it to *Variance to review*, where approval still demands a manager PIN.
