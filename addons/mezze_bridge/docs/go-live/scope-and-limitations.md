# Pilot Scope & Honest Limitations (P1 §1)

## Pilot-approved capabilities (Pilot supported)
Counter sales · dine-in tables · reservations & walk-ins · waitlist · course hold/fire ·
KDS preparation · partial payment · mixed tender · refunds · table transfer · **safe** table
merge (blocks merging orders with payments) · QR table ordering · pickup ordering ·
pay-on-delivery · **prepaid aggregator orders** · secure customer order status · manager
approvals · branch reports · offline/reconnect · user & device customization · Admin Console
governance. All backed by 218 green tests + live multi-worker proofs (R1.1, O1).

## Explicit limitation classification
| Limitation | Classification | Note |
|---|---|---|
| No proven public **online card-payment** journey (no live PSP redirect proven) | **Disabled for pilot** | Pickup pays at counter; delivery pays on delivery; aggregator is prepaid. No card-online path is exposed. |
| Advanced **delivery dispatch** operations partial | **Pilot supported with manual procedure** | Order/zone/fee/ETA + accepted/preparing/ready work; driver assignment/dispatch is manual (runbook). |
| **Drive-thru** operational acceptance partial | **Disabled for pilot** | Canonical order engine exists but not operationally accepted; hidden from the pilot branch. |
| True **seat-level order-line identity** | **Disabled for pilot** | Guest count is durable; per-seat line identity is not modelled. Split-by-seat is **not** claimed. |
| **Split-by-seat** | **Disabled for pilot** | Only split by item / equal / custom amount (durable). |
| Public **cancellation** full state coverage | **Pilot supported with manual procedure** | Before-fire cancel + refund-engine path proven; fired/preparing cancels require staff/manager decision (runbook). |
| **Status-token** expiry/revocation policy | **Pilot supported** | Implemented in P1 (hash storage, 24h expiry, manual revocation). |
| Real **tablet** & **3-independent-device** evidence | **Pilot supported with manual on-site verification** | Not forceable in the CI host (resize no-ops on hi-DPI). Responsive CSS present; **must be re-verified on the physical pilot tablet before launch**. |
| Real **hardware** (printer/drawer/payment terminal) | **Pilot supported with on-site verification** | Not present in the build environment; the printing/drawer flows exist (outbox hardware jobs) but **must be exercised on the pilot hardware**. |
| **cryptography** runtime is 3.4.8 (target ≥42) | **Pilot supported** | App runs green; the ≥42 upgrade is a coordinated deployment-host task (pyOpenSSL>=24 + urllib3>=2), documented, not app code. |

## Not marketed
Online card checkout, drive-thru, seat-level split, and driver dispatch are **not** presented
to customers or staff in the pilot. No unsupported behavior is advertised.
