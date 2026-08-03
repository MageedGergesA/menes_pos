# Mezze POS — Known Limitations

The single, honest list a salesperson can hand a prospect. Mezze is sold on honesty:
every boundary below is stated in plain language with the reason and the roadmap
status. Nothing here is hidden in fine print.

Status words: **DEFERRED V2** (planned, out of v1 scope) · **EXTERNAL CERT PENDING**
(needs a third-party account/credential we don't hold) · **PHYSICAL CERT PENDING**
(needs hardware we test on-site) · **NOT SUPPORTED** (explicitly not a capability).

| # | Limitation | Why | Status |
|---|---|---|---|
| 1 | **Split by seat identity** is not available. You can split a bill by amount or by line and mix tenders. | Per-seat identity is not modelled in v1. | **DEFERRED V2** |
| 2 | **Integrated card terminals** — the physical device is not yet certified. | Software orchestration is certified; no terminal hardware on hand. | **PHYSICAL CERT PENDING** |
| 3 | **Automated cash machines (Glory)** — physical device not certified. | Software orchestration only; no cash-machine hardware (Cashdro/Cashmatic also pending). | **PHYSICAL CERT PENDING** |
| 4 | **Egypt / InstaPay bank-app QR** is not certified. | The bank-QR path is built, but this scheme is not certified — do not present it as a certified tender. | **EXTERNAL CERT PENDING** |
| 5 | **Paymob online** — redirect-only; **refund, tokenization, and capture are not claimed**; neither sandbox nor live is certified. | Needs Paymob credentials + a certification pass; Odoo's Paymob provider does not support refunds. | **EXTERNAL CERT PENDING** |
| 6 | **Physical kiosk hardware** is not certified; kiosk v1 is **pay-at-counter** (no faked cash), no native card-terminal kiosk. | No kiosk device; native kiosk payment upstream is Adyen/Stripe-terminal-only. | **PHYSICAL CERT PENDING** |
| 7 | **Receipt printer, cash drawer, tablets, workstations** — physical devices certified on-site only. **Bluetooth receipt printers are not supported.** | Host/hardware facts can only be confirmed on the physical box during the pilot. | **PHYSICAL CERT PENDING** |
| 8 | **Cross-branch customer credit is NOT real-time** on Mezze Edge. | Edge branches run locally and reconcile; a balance changed at one branch is not instantly visible at another. | Edge boundary (real-time only on Cloud) |
| 9 | **Route optimisation** for delivery. | Delivery is manual dispatch by design in v1. | **NOT SUPPORTED** |
| 10 | **Live GPS courier tracking.** | Not included in v1; delivery tracks state, not location. | **NOT SUPPORTED** |
| 11 | **Storing PAN / CVV / PIN.** | Mezze never stores card data — by design, for PCI safety. | **NOT SUPPORTED** |
| 12 | **Explicit per-modifier min/max** beyond single-select enforcement. | Single-select modifiers are enforced server-side; richer min/max rules aren't natively modelled. | **DEFERRED V2** |
| 13 | **Per-channel product availability.** | Branch-global "86" + POS availability cover v1; per-channel menus not modelled. | **DEFERRED V2** |
| 14 | **Odoo 20** is not claimed. | Certified on Odoo 19.0 Community only; Odoo 20 needs its own certification pass. | Not certified |
| 15 | On **Mezze Cloud**, a WAN outage stops the branch. | Cloud requires the internet; only **Mezze Edge** keeps selling on the LAN through a WAN outage. | Edition boundary |

If a prospect needs any DEFERRED V2 / PENDING item as a hard requirement, say so up
front and align it with the roadmap or the on-site pilot — never imply it is already
certified.
