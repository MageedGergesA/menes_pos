# Payroll integration — the boundary

Screen **48 Payroll handover**, the last tab on Team Admin. Deliberately **not** a payroll system.

The POS is the only thing that knows what happened on the floor. Odoo is the only thing that knows
what a person is contractually owed. This screen closes the gap between those two facts and then
stops — it produces one locked file per period and hands over.

---

## What the screen is for

The workflow the audit wanted finished:

**Team Admin → Pay period → Hours → Overtime → Tips → Advances → Expenses → Export / Send to payroll**

Three periods on the strip: one already **Sent** (16–31 Aug, with its reference and approver), one
**Open** (01–15 Sep), one **Not started**. Selecting a period rescopes everything.

## Nothing is typed twice

Every column is derived from the screen that already owns it. That is the whole design:

| Column | Derived from | Owner screen |
|---|---|---|
| Ordinary hours | shift plan − taken unpaid meal breaks | Roster + `brkOf()` |
| Overtime | hours over 48/week × 1.5 | same |
| Missed break, paid | `brkWaive` — recorded miss, paid as worked time | 46 Break compliance |
| Tips | `tipMine(id)` — the signed distribution | Tips (`docs/TIP_POOLING.md`) |
| Advances | approved `hr.advance` requests | Requests inbox |
| Expenses | approved `hr.expense` claims | Requests inbox |

`prHours()` calls the same `brkOf()` the compliance screen renders, so hours and break compliance
**cannot disagree**. If a manager records a missed break, the paid minutes appear here on the same
render — no sync, no second source.

## The estimate is labelled an estimate

The right-hand total says **Branch estimate**, and the note under the table says why in plain terms:
the POS has no contract, no tax table and no insurance base. It knows hours, tips and cash
movements. Gross and net are Odoo's to compute.

This matters operationally: *a branch that argues with the payslip argues from this file, not
against it.* The file is the branch's evidence, not a competing calculation.

## Blockers, not a warning banner

A period cannot be closed while any of these is open. Each names the number, the consequence, and
the screen that fixes it:

1. **Tip distribution not signed** — an unsigned pool is a number that can still change; sending it
   puts a figure on a payslip the branch has not agreed
2. **Staff still on the clock** — minutes are still accruing, so their hours are not final
3. **Breaks neither taken nor recorded** — a missed break is paid as worked time, so until it is
   recorded the hours are wrong, *and wrong in the branch's favour*
4. **Advances and claims still pending** — an undecided claim rolls to the next period, which is how
   a rider waits two months for money they spent

## Close, then send — in that order

`Close the period` freezes hours and tips against the approver's name. Export and Send are **refused
until it is closed**: *an export that can still change is not a handover.*

After the close, a correction is a line on the **next** period — never an edit to a period that has
already been paid. This is the same discipline as the drawer close in `docs/SESSION_LIFECYCLE.md`
and for the same reason: a record that can be edited after it is acted on is not a record.

## Odoo mapping — where the handover lands

- **Hours** → `hr.attendance` intervals (already written as staff clock in and out)
- **Overtime, tips, missed-break pay, expenses** → `hr.payslip.input` lines on the employee's open
  payslip
- **Advances** → a **negative** `hr.payslip.input` recovered from this period — not a deduction the
  POS calculates
- **Period reference** → carried on every line so a payslip can be traced back to a branch file
- **Nothing writes a payslip.** Odoo computes gross, tax, social insurance and net from the
  contract, and issues the bank file

Two export routes, both from the same locked data: a **file** (one line per employee, with the
period reference) for a payroll bureau or a manual import, and **Send to payroll** for the direct
Odoo write.

## What is deliberately absent

- No pay rates of record — the rate shown is the roster rate, used only for the estimate
- No tax, insurance, or deduction logic
- No payslip, no bank file, no year-to-date
- No leave accrual balances (leave requests live in the Requests inbox; balances are HR's)
- No employee bank details anywhere in the POS

If any of these appear in a later round, the boundary has been crossed and this document is the
thing to argue with.

## Bilingual

Every label, blocker, consequence line and boundary statement goes through `tr()`; hours, money,
counts and multipliers through `N()`. Odoo model names (`hr.attendance`, `hr.payslip.input`) and the
period reference stay Latin — they are identifiers a developer and an accountant both read.
