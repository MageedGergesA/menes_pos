# S2C-6 — Customer Account / Credit Audit (Odoo 19 source)

> Audited against the installed **Community** source before any code was written.
> Every claim cites a file. Headline: the receivable/credit **accounting** is native
> and authoritative; the POS **credit-limit warning, deposit-money, and settle-due**
> features are **Enterprise (`pos_settle_due`) and are NOT present in this repo** —
> so Mezze builds deposit/settlement on native `account.payment` + the customer
> receivable (native accounting authority, no second ledger) and owns the credit
> policy UX.

## 1. Customer Account method (ODOO CORE)

`pos.payment.method.type='pay_later'` (Customer Account) is derived purely from a
**blank/non-cash-non-bank journal** (`point_of_sale/models/pos_payment_method.py:111`
`_compute_type`: `pm.type = journal.type if cash/bank else 'pay_later'`). The
receivable it books to is `receivable_account_id` or the company default POS
receivable (`_get_receivable_account`, `pos_session.py:1651`). **`split_transactions`
("Identify Customer", `:43`) is what forces a customer and books to the PARTNER's own
receivable** — without it a pay_later payment posts to the generic company POS
receivable with **no partner** (`_get_combine_receivable_vals`, `pos_session.py:1356`),
so per-customer debt is NOT tracked. ⇒ **A per-customer Customer Account method MUST
have Identify Customer ON + journal blank.**

## 2. Receivable / credit authority (ODOO CORE — do not duplicate)

`account/models/partner.py`:
- `partner.credit` (`:500`, `_credit_debit_get :358`) = SUM of **unreconciled posted**
  `account.move.line.amount_residual` in `asset_receivable` across the company tree =
  the customer's **debt to us (exposure)**. Company-scoped.
- `partner.credit_limit` (`:507`) = the limit, **`company_dependent=True`**.
- `use_partner_credit_limit` (`:511`) = active when `credit_limit` differs from the
  company default. `show_credit_limit` = `company.account_use_credit_limit` (`:674`).
- Company toggle **`account_use_credit_limit`** (`account/models/company.py:158`,
  "Enable the use of credit limit on partners").
- `total_due` / `total_overdue` are **NOT in Community** (Enterprise account_followup).

**Accounting partner is the commercial partner**: `_find_accounting_partner(p) =
p.commercial_partner_id` (`partner.py:694`); receivable line partner + account come
from the commercial partner (`pos_session.py:1342`), and `credit_limit` /
`property_account_receivable_id` are `_commercial_fields` (`:698`) — they propagate
from the company (parent) to child contacts. ⇒ Mezze computes exposure/limit on the
**commercial partner**.

**In-session nuance**: a pay_later pos.payment becomes a receivable move line only at
**session close** (`pos_session.py:897,1064`). So `partner.credit` does NOT reflect
open-session unsettled pay_later. ⇒ Mezze's live exposure = `commercial.credit`
(posted) **+ open-session pay_later payments** to that commercial partner.

## 3. Credit-limit warning (ENTERPRISE — NOT PRESENT → Mezze owns policy)

Base Community POS has **no** credit warning: the partner-balance cell is a stub
(`partner_list.js:145` `isBalanceDisplayed → false`; `partner_line.xml:60` FIXME
"this should be in pos_settle_due"), and there is **no `pos_settle_due` module**
(`ls addons/pos_settle_due` → absent). The documented "orange over-limit warning,
sale still allowed" is an Enterprise soft warning. ⇒ There is **no native Community
warning to preserve**; Mezze provides all three policies, and its `ODOO_WARNING`
default mirrors the documented soft-warning behavior (warn, allow).

## 4. Customer-required (ODOO CORE)

Base POS forces a customer for **`split_transactions`** methods, client
(`utils/order_payment_validation.js:390` `_askForCustomerIfRequired`) + server
(`pos_session.py:1342` raises UserError on split receivable with no customer). Mezze
enforces customer-required for the Customer Account tender in both the cashier UI and
`/orders/pay` before any financial effect.

## 5. Deposit money & settle-due (ENTERPRISE — NOT PRESENT → Mezze builds on native accounting)

No deposit or settle-due exists in Community (`grep deposit|settle` in
`point_of_sale/static` → none; both are `pos_settle_due`). Mezze implements them with
**native accounting primitives** (`account.payment`, inbound customer payment, a REAL
cash/bank journal, reconciled against the customer receivable) — this reduces/creates
`partner.credit` through Odoo's own posting, **not** a Mezze balance. Deposit ⇒ an
inbound customer payment that leaves an available credit (negative receivable);
settlement ⇒ an inbound customer payment reconciled against the outstanding
receivable. No sales revenue is created; no second ledger.

## 6. Refund + pay_later (ODOO CORE)

Base POS puts no restriction on a pay_later method on a refund
(`payment_screen.js:148`, terminal-only guard at `:151`); a pay_later line on a
refund posts a **negative** amount to the receivable (credits the customer's account).
Mezze's existing refund ceilings/linkage stay authoritative.

## 7. Mezze extension (MEZZE EXTENSION REQUIRED)

- `pos.payment.method.mezze_credit_policy` = `odoo_warning` (default) | `manager_approval`
  | `hard_block`.
- `res.partner._mezze_credit_position(company, config, extra)` → exposure (native
  `commercial.credit` + open-session pay_later) / limit (`credit_limit`) / available /
  projected / over. Native fields only.
- `/orders/pay` Customer Account: require partner; row-lock the commercial partner;
  re-read exposure; apply policy (warn / manager-PIN approval reusing the existing
  role-ranked `mezze.cashier` framework — cashier can't self-approve / hard block);
  audit. Credit check applies only to the amount charged to the account (partial /
  mixed).
- `/customer/search`, `/customer/summary` (cashier selector + safe account panel);
  `/customer/deposit`, `/customer/settle` (native `account.payment`).
- Validator + manager reporting + admin policy; Arabic/dark/a11y cashier UX.

## 8. Multi-company / cross-branch (ACCOUNTING REQUIREMENT / scope)

`credit` and `credit_limit` are company-scoped/`company_dependent` — exposure obeys the
current company. **Cross-branch real-time global credit across independent (offline
Edge) databases is NOT claimed**: within one shared DB, exposure is global to that DB;
disconnected Edge branches do not share live credit. Documented honestly.

## Classification summary

| Concern | Class |
|---|---|
| pay_later method, receivable at session close, `partner.credit`/`credit_limit`, commercial partner | **ODOO CORE** |
| `mezze_mode='customer_account'` classification | **MEZZE ALREADY** |
| Credit policy (warn/approval/block), exposure incl. open-session, cashier UX, deposit, settlement, reporting, validator | **MEZZE EXTENSION REQUIRED** |
| Per-customer debt tracking needs Identify Customer + Accounting posting at session close | **ACCOUNTING REQUIREMENT** |
| Native POS deposit/settle/credit-warning (Enterprise `pos_settle_due`) | **NOT PRESENT** (Mezze rebuilds on native accounting) |
| Real-time cross-branch global credit on disconnected Edge DBs | **NOT SUPPORTED / NOT CLAIMED** |
