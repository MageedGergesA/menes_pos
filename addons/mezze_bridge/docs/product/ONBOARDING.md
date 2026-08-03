# Mezze POS — First-Run Onboarding

Onboarding is a **real, resumable, idempotent** setup flow that configures a
restaurant using the production UI only — no Python/XML/SQL edits, no factories,
no demo fixtures.

## Design principles

- **Reuses Odoo models.** Each step maps to an existing model
  (`res.company`, `pos.config`, `account.journal`, `product.product`,
  `restaurant.table`, `mezze.cashier`, `pos.payment.method`, `mezze.delivery.zone`).
  There is **no** duplicate `mezze.restaurant` shadow model.
- **Completion is derived, never a boolean.** A step is "done" only when its
  underlying go-live validator check actually passes. You cannot tick a box to
  fake readiness.
- **Resumable.** Progress is read from live config each time; close the console
  and come back — it reflects reality.
- **Idempotent.** Re-running never creates duplicate records. The only stored
  state is per-step "acknowledged" markers (JSON in `ir.config_parameter`) for
  informational steps (e.g. KDS layout) that have no validator check.

## Steps

| # | Step | Backed by | Completion signal |
|---|---|---|---|
| 1 | Restaurant & company | `res.company` | currency + timezone set |
| 2 | Branch / POS point | `pos.config` | ≥1 POS config |
| 3 | Taxes & journals | `account.journal` | cash/bank journals |
| 4 | Payment methods | `pos.payment.method` | methods classified + journaled |
| 5 | Menu / products | `product.product` | POS-available products |
| 6 | Tables (dine-in) | `restaurant.table` | *optional* — QR tokens mint lazily |
| 7 | Kitchen display | `mezze.kds.ticket` | *optional* — informational ack |
| 8 | Staff & PINs | `mezze.cashier` | staff + a manager PIN |
| 9 | Payment devices | `mezze.payment.device` | *optional* — devices for required methods |
| 10 | Pickup & delivery | `mezze.delivery.zone` | *optional* — zones/fees/COD |
| 11 | Self-order channels | params + `res.lang` | *optional* — QR/pickup/kiosk + Arabic |
| 12 | Printers & drawer | hardware | *optional* — verified on-site (physical) |
| 13 | Review & go-live | validator | overall not FAIL for the chosen profile |

## API

```
POST /mezze/api/v1/admin/onboarding       { token, profile } -> { steps, complete, overall, ... }
POST /mezze/api/v1/admin/onboarding/ack    { token, step_id, done }  (informational steps only)
```

`complete` is true only when the validator does not FAIL for the chosen profile
**and** every required step is satisfied. Operator console:
`/mezze_bridge/static/onboarding.html`.
