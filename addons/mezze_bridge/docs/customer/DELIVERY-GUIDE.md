# Mezze POS — Delivery Guide

Mezze delivery is first-party: your own zones, fees, and couriers, with real
cash-on-delivery. It is **manual dispatch** — you assign couriers yourself.

## Zones, fees, minimums, ETA

Configured in the Admin Console and enforced by the server (never by the customer's
phone):

- **Zones** — the areas you deliver to.
- **Delivery fee** — added as a real order line (a delivery-fee product), so it flows
  into accounting correctly.
- **Minimum order** and **ETA** per zone.
- **Operating hours** — orders outside hours are refused.

## COD (cash on delivery)

- A COD order is a **real unpaid order** until the courier collects — Mezze does not
  fake it as prepaid.
- On return, record collection via the collect step (`/delivery/collect`); the cash
  lands in a cash method, so COD reconciles like any other cash.
- A branch that allows COD must have a cash method configured, or the go-live check
  fails.

## Dispatch and courier assignment

- New delivery orders enter a guarded lifecycle (received → preparing → ready →
  dispatched → delivered / collected).
- Assign a courier manually and mark dispatch; the order tracks its state and a
  customer-facing status token.

## Aggregator channels

- Third-party aggregators (Talabat-style) integrate via a normalised webhook: their
  orders arrive as canonical Mezze orders and flow through the same kitchen/status
  pipeline, with reliable outbound delivery of updates.
- Specific aggregator go-live is **supported via Odoo / external cert pending** — it
  needs that aggregator's credentials/account and their certification, which is done
  during onboarding.

## NOT in this version

- **Route optimisation** — NOT SUPPORTED in v1.
- **Live GPS courier tracking** — NOT SUPPORTED in v1.

Delivery is manual dispatch by design. These are named, not hidden — see
`KNOWN-LIMITATIONS.md`.
