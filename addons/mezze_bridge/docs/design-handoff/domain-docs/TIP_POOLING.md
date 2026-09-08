# Tip pooling

Contract between the prototype (`Mezze POS v3.dc.html` — **Tip pool**, on 25 On shift, and the
session close) and the Odoo 19 implementation.

**The principle:** a tip is **money owed to staff** — a liability from the moment it is captured, and
not the branch's to keep, spend or round. So it travels one path with a signature on it:

```
captured (card, with the tender)          ─┐
declared (cash, by the person who took it) ─┼─→ pool ─→ rule ─→ distribution ─→ approval ─→ payout
tip-out (hybrid: a % of direct tips)      ─┘                                        │
                                                                    cash from the drawer, or payroll
```

What was there before this document: `tipCard = 418` hardcoded on the staff screen, `240 + declared`
hardcoded on My shift, share arithmetic written inline in two branches of a ternary, and the tips the
handheld actually captured (`hhTipTaken`) feeding none of it. Four numbers for one liability, no
ledger, no approval, no payout. **Service charge is not a tip** and never enters this pool
(`docs/PAYMENT_VALUE_ENGINE.md` §3).

---

## 1. The ledger

One append-only table. Every figure any screen shows is derived from it.

| Kind | Sign | Written by | Carries |
| --- | --- | --- | --- |
| `capture` | + | the tender that took it | amount, **who served it**, surface, check ref, method |
| `declare` | + | the employee, for cash tips | amount, who — nobody else may edit it |
| `distribute` | ± | the approved run | run id, person, their share |
| `payout` | − | payout, per person | run id, person, `cash` or `payroll` |
| `adjust` | ± | a manager, with a reason | who, why |

Two rules that keep it honest: a capture names **the server who took it** (direct and hybrid rules
are meaningless otherwise), and a declaration is **only** writable by the person declaring — a
manager who can type someone's cash tips can also under-declare them.

`tipPool()` = captures + declarations, less nothing. It is the liability.

## 2. Distribution rules

One resolver, six rules, and the rule is recorded on the run — so a signed distribution can be
re-read next month and still explain itself.

| Rule | Weight | Use |
| --- | --- | --- |
| **Equal** | one share per eligible head | small teams, one job |
| **Hours worked** | minutes actually worked, breaks excluded | the default |
| **Role-weighted** | hours × role weight (Server 1.0 · Bar 0.8 · Kitchen 0.5 · Rider 0.5) | mixed front/back pools |
| **Custom percentage** | manager-set % per person | a rule the team agreed; **must total 100 or the run refuses** |
| **Direct to server** | each server keeps the tips captured on their own checks | table service, no pooling |
| **Hybrid** | direct, less a **tip-out** (`TIP_OUT_PCT`, 15%) into a support pool split by hours × role weight | the common real answer |

- **Eligibility** is being clocked in on the shift with a tipped role. Off-shift staff and managers
  are out; a person on a break still accrues the hours they worked.
- **Cash a person declared stays theirs** under Direct and Hybrid, and enters the pool under Equal,
  Hours, Role and Custom. This is stated on the screen, because it is the question every team argues
  about.
- **Rounding is allocated, not repeated.** Shares are computed in piastres and the remainder goes to
  the largest fractional parts (largest-remainder), so the distributed total **equals** the pool
  exactly. Rounding each share independently is how a pool ends up 0.40 LE short and nobody can say
  whose money it was.

## 3. Approval

Nothing pays out unsigned.

- A manager PIN signs the run. Approval takes a **snapshot**: rule, pool, and every person's share.
  The signed figures are the paid figures — a later clock-out cannot silently re-cut a distribution
  somebody already agreed to.
- Changing the rule or a custom percentage after signing is **refused**; the run must be voided
  (also PIN'd, also logged) and re-signed. Both events stay on the ledger.
- Custom percentages that do not total 100 block approval by name and by number.
- **The session cannot post with an unapproved pool.** Tips are one of the day's liabilities, so they
  close with the day — the same discipline as an uncounted drawer.

## 4. Payout

| Route | Effect |
| --- | --- |
| **Cash from the drawer** | a drawer movement, so the till reconciles; discharges `Tips payable` |
| **To payroll** | stays in `Tips payable` and rides the next payslip |

One `payout` row per person per run, keyed on `run|person`: a second tap pays nobody twice. A partial
payout (some in cash now, the rest on payroll) is two rows, and the person's outstanding balance is
derived — never stored.

## 5. Accounting

- Capture: `Tips payable` (a liability). **Never revenue, never in food-cost percentage, never in a
  server's sales figure.**
- Card tips arrive with the acquirer settlement, so the branch holds the cash before the money lands;
  paying them out of the drawer the same night is a **timing** decision, and the drawer movement is
  what makes it visible.
- Cash tips are already in the drawer — declaration is what makes them countable, not what makes
  them exist. An undeclared cash tip is a reconciliation difference, which is why the count and the
  declaration sit next to each other.
- Egypt: tips are not part of the service charge and are not subject to VAT; if the branch levies a
  service charge, Settings states whether it is distributed, and it is computed on the **net of
  comps** so staff are not paid on revenue never received.

## 6. Odoo mapping

| Design | Odoo 19 |
| --- | --- |
| Tip captured with a tender | POS tip line on `pos.order` (`tip_amount`), tips product posting to a liability |
| Tips payable | dedicated liability account, per branch |
| Employee | `hr.employee`; hours from `hr.attendance` — the same clock the rota reads |
| Pool run + approval | custom model: rule, period, snapshot lines, approver, state |
| Cash payout | `pos.session` cash-out movement |
| Payroll payout | payslip input line (`hr.payslip.input`) |
| Role weights, tip-out % | branch settings on the pool rule |

Hours must come from attendance, not from the rota: a person paid on a shift they did not work is the
same defect in tips as in wages.

## 7. What the prototype does

- `tipLog` / `tipPush` — the ledger. `tipPool()`, `tipOwn(who)`, `tipDeclared(who)` derive from it.
- `tipShares()` — **one** distribution function behind the pool table, the approval sheet, My shift's
  "mine this shift" and the payout rows. It returns the rule, the pool, every row's weight and share,
  the sum and the remainder, plus `err` when a rule cannot be applied (custom percentages off 100).
- The handheld's tip capture writes a `capture` row naming the server who took it; `hhTipTaken` is
  gone, and the handheld's own "tip collected" figure reads the ledger.
- `tipApprove` snapshots; `tipVoid` reverses with a PIN; `tipPayout('cash'|'payroll')` writes one row
  per person and posts the drawer movement for cash.
- `sessPost` refuses while the pool is unapproved.
- **Tip pool** on 25 On shift: composition (card / cash / pool), the six rules with what each means,
  the per-person table (hours, weight, %, share), the remainder line, approval, payout and the ledger.

## 8. Gaps

1. ~~The register has no tip prompt~~ — **closed, Pass 18A.** The Pay modal now carries a tip step
   (No tip / 5% / 10% / 15% / custom % / custom amount) for cash and card alike. The tip belongs to
   the **order** (`checkTipAmt`/`checkTipSet`), added once to the total; split and partial tenders
   just fund it down, so a cash+card split never double-counts. It reaches `tipPush` exactly once —
   on the tender that clears the check's remaining balance, the same idempotency guard the loyalty
   earn rule already used.
2. **Declaration is trust-based by design, and unenforced.** There is no reconciliation yet between
   declared cash and the drawer difference; §5 says where it belongs.
3. **One pool per shift.** Split pools (bar vs floor, lunch vs dinner) are a real requirement and are
   not modelled.
4. **Payout to payroll is a state, not an export.** The payslip input line is Claude Code's side.
5. ~~Refund policy for a tip~~ — **closed, Pass 18C.** A product/item refund does **not** touch the
   tip — the guest's tip decision is independent of a restaurant-caused product issue. A full-order
   refund shows an explicit, manager-facing **"Refund tip too"** toggle, default OFF; it is never
   inferred from the refunded amount. When checked, `ordRefundCommit` posts exactly one `reverse` row
   (`-amt`, linked to the original order ref) to this SAME ledger — never a second tip table — and
   sets `tipRefunded[ref]` so a repeat confirmation cannot reverse the same tip twice. If the tip was
   never captured (no tender cleared the check yet) there is nothing to reverse.

## 9. Acceptance

A handheld check settling with a 43.00 LE tip writes one `capture` row naming the server. The pool
reads card + declared cash and nothing else. Under **Hours worked**, four people on shift with 6.4 /
5.1 / 3.0 / 2.2 hours split the pool pro-rata, and the four shares **sum to the pool exactly**.
Switch to **Custom percentage** with figures totalling 90: the run names the shortfall and approval
is refused. Sign under **Role-weighted**: the snapshot holds, and a fifth person clocking in
afterwards does not change the signed figures. Pay out in cash: one row per person, a drawer movement
for the total, and a second tap pays nobody twice. Try to post the session with an unapproved pool:
refused, by name.
