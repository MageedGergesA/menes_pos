# Mezze POS — Payment Capabilities

The honest, customer-facing payment matrix. Mezze converges every tender on Odoo's
native payment/accounting layer — it does not run its own bank protocols. **Mezze
never stores PAN, CVV, or PIN.**

## Status words (exact meaning)

- **SOFTWARE CERTIFIED** — code path tested and browser-proven; works on the software.
- **SUPPORTED VIA ODOO** — delivered by native Odoo configuration.
- **EXTERNAL CERT PENDING** — built and tested against a simulator/sandbox; live use
  needs a third-party credential/account we do not yet hold.
- **PHYSICAL CERT PENDING** — orchestration certified; the physical device is certified
  on-site.
- **NOT SUPPORTED** / **DEFERRED V2** — explicitly not a capability / planned later.

## The matrix

| Tender | Status | What that means for you |
|---|---|---|
| **Cash** | SOFTWARE CERTIFIED | Full cash handling, change, drawer, session reconciliation. |
| **Manual card (record reference)** | SOFTWARE CERTIFIED | Run the card on a standalone machine; record reference + last 4 only. No PAN/CVV/PIN stored. |
| **Integrated card terminal** | SOFTWARE CERTIFIED (software) / **PHYSICAL CERT PENDING** | Mezze sends the amount and reads the terminal's result; your exact terminal is certified on-site. |
| **Bank / payment QR** | SOFTWARE CERTIFIED (software) / **EXTERNAL CERT PENDING** | Built and separate from table-QR ordering. **Egypt / InstaPay QR is NOT CERTIFIED — do not present it as certified.** |
| **Online payment (QR-table / pickup / delivery)** | SOFTWARE CERTIFIED | Native online-payment path; customer pays online where WAN is available. |
| **Paymob (online provider)** | **EXTERNAL CERT PENDING** | Redirect-only. Refund, tokenization, and capture are **NOT claimed**. Neither sandbox nor live is certified — needs Paymob credentials + a certification pass. |
| **Customer account / store credit** | SOFTWARE CERTIFIED | Charge an identified customer's pay-later account; optional manager approval + credit limits. |
| **Automated cash machine (Glory etc.)** | SOFTWARE CERTIFIED (software) / **PHYSICAL CERT PENDING** | Orchestration only; no cash-machine hardware on hand (Cashdro/Cashmatic also pending). |
| **Stored PAN / CVV / PIN** | **NOT SUPPORTED** | Mezze never stores card data. See `PRIVACY-DATA.md`. |

## Split payments

- Split a bill **by amount or by line** and **mix tenders** — SOFTWARE CERTIFIED.
- **True split-by-seat identity** — **DEFERRED V2** (not modelled in v1).

## Refunds & exceptions

- Refunds, voids, comps, and discounts are SOFTWARE CERTIFIED, manager-PIN gated, and
  audited with a signature.
- Note that **Paymob refunds are not claimed** — a Paymob online charge is not
  refunded through the provider in v1.
