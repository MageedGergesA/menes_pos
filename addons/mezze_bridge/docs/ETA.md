# Egypt ETA e-invoicing — reuse the native module

We do **not** build ETA. Odoo 19 Community ships `l10n_eg_edi_eta` ("Egypt
E-Invoicing", LGPL-3) — real USB-token **CAdES-BES** signing, ETA submission,
clearance UUID, and the signed QR, all on `account.move` via `account_edi`.
`mezze_bridge` treats it as an **optional dependency** (runtime-detected) so a
non-Egyptian deployment isn't forced to install Egyptian localization.

## Path

```
POS card/cash sale (with a customer)
   │  /mezze/w1/einvoice/submit {order_id | order_uuid}
   ▼
mezze_bridge:  order.action_pos_order_invoice()  → account.move (posted)
   ▼
l10n_eg_edi_eta (native):  sign via thumb-drive token → submit to ETA → clearance
   ▼
account.move carries  l10n_eg_uuid (cleared id) · l10n_eg_submission_number ·
                      l10n_eg_qr_code · l10n_eg_is_signed
   ▼
/mezze/w1/einvoice/status → real state; receipt prints the REAL ETA QR (no fake badge)
```

## The e-invoice vs e-receipt decision (READ THIS)

`l10n_eg_edi_eta` is **e-INVOICE (B2B, account.move)** — it needs a **customer**
on the order. Anonymous B2C walk-ins (most restaurant sales) belong to Egypt's
separate **e-receipt** system, which native Odoo does **not** cover.

So per merchant, confirm with a tax advisor:
- **Invoice-per-order** (customer captured) → fully covered by native ETA here.
- **B2C e-receipts** → a real remaining gap (custom or a 3rd-party e-receipt
  module). `einvoice/submit` returns `error:'no_customer'` for these — by design.

## One-time merchant setup (Egypt)

1. Install `l10n_eg_edi_eta` (+ `l10n_eg`).
2. Configure the company: ETA registration number, activity code, branch data.
3. Install/point the **thumb-drive signing tool** (`l10n_eg_eta.sign.host`,
   default `http://localhost:8069`) and load the USB token.
4. Set ETA credentials (client id/secret) on the company/journal.

Until installed, `einvoice/submit` still invoices the order and returns
`eta_available:false` with a clear note — never a fake "cleared".

## Endpoints (mezze side)

| Route | Does |
|---|---|
| `/mezze/w1/einvoice/submit` | invoice the POS order, return native ETA status |
| `/mezze/w1/einvoice/status` | poll the invoice's ETA UUID / signed / submission |

## Frontend (next)

On pay-complete for an invoiced sale, call `einvoice/submit`, then render the
receipt QR from `l10n_eg_qr_code` once `cleared`. Drop the simulated ETA badge —
show it only when the native UUID exists.
