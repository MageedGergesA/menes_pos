# GL bridge — POS takings → general ledger

## Principle: read native, never re-post
Odoo POS **already** posts the ledger. At session close it creates one
aggregated journal entry per session (`pos.session.move_id`) covering all
non-invoiced orders — sales income, tax, and the receivable/tender legs — plus
cash `account.bank.statement.line`s. Invoiced orders post their **own**
`account.move` (a customer invoice) and are excluded from the session
aggregate, so the two sets are disjoint.

The bridge does **not** create, post, or mutate any `account.move`. It reads
those native entries and surfaces them for three jobs an accountant needs:
a close check, a trial balance, and an external hand-off. If Odoo's accounting
is configured correctly, the bridge is correct for free.

## Endpoints (`controllers/w1.py`, prefix `/mezze/w1`)
All auth via the shared token (`X-Mezze-Token` header or `?token=`). Range
params `date_from` / `date_to` (`YYYY-MM-DD[ HH:MM:SS]`) default to **today**;
`config_id` optional (omit = all branches).

### `POST /gl/sessions` — financial close check
One row per POS session in the period (filtered by `start_at`):
`state`, `opened`/`closed`, order count + total, the journal entry (`move`,
`move_state`), its `gl_balance`, and the `cash_diff` (counted vs expected cash).
Three exception flags for the accountant to clear before locking the books:

| flag | meaning |
|------|---------|
| `unposted`   | session closed but its journal entry is not `posted` |
| `unbalanced` | `abs(sum(move.line_ids.balance)) > 0.01` (should never fire — Odoo checks it) |
| `cash_flag`  | `abs(cash_register_difference) > 0.01` — till short/over |

`exceptions` = count of sessions tripping any flag.

### `POST /gl/summary` — trial balance
Aggregates the period's POS journal lines (session moves ∪ invoiced-order
moves) into a by-account trial balance: `[{code, name, type, debit, credit,
balance}]` sorted by code, plus `totals{debit, credit, balanced}`, a
`tax{name: collected}` breakdown (from `account.move.line.tax_line_id`), and
session/move posted-vs-draft counts. This is the reconciliation of POS takings
against the GL.

### `GET /gl/export.csv` — accountant hand-off
One row per journal move line for import into an external accounting package:
`date, entry, journal, account_code, account_name, partner, label, debit,
credit, tax`. Attachment download.

## Range basis (known nuance)
`gl/sessions` filters sessions by `start_at`. `gl/summary` / `export` gather
moves from sessions (by `start_at`) **and** invoiced orders (by `date_order`)
in the window. A session that opens in one period and closes in the next is
attributed to the period it opened in. For strict close-date accounting, pass a
tight range aligned to the trading day. This is a reporting lens; the source of
truth remains the native `account.move`.

## Not in scope (native handles it, or later)
- Posting/reconciliation — native POS session close owns it.
- Multi-currency presentation — figures are in company currency.
- Chart-of-accounts remapping for a specific external package — the CSV is a
  neutral journal dump; remap downstream. A configurable mapping seam is a W3
  item alongside `w1.py::config_tax`.

## Validation
- `gl/sessions` verified against the live demo (both open sessions listed with
  correct totals, `cash_flag`, `move_state: none` while open).
- Trial-balance grouping + tax + CSV-row construction verified against a real
  posted `account.move` (balanced; `tax_line_id` present).
- Closed-session moves balance by construction (`account.move._check_balanced`).
