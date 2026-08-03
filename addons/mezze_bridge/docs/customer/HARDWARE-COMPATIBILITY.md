# Mezze POS — Hardware Compatibility

**Honest position: no physical device is certified until it passes on-site during
your pilot.** Mezze's software orchestration of these devices is certified; the
physical device certification is **PHYSICAL CERT PENDING** until we test the exact
model on your hardware. This page is the customer-facing summary; the engineering
detail lives in `docs/sell-ready/hardware/HCL.md`.

## Status of every device class

| Device | Software status | Physical status | Notes |
|---|---|---|---|
| **Receipt printer** | SOFTWARE CERTIFIED (via Odoo) | PHYSICAL CERT PENDING | **Network** ESC/POS only (Epson TM-m30 / TM-T88 family is the reference target). **Bluetooth receipt printers are NOT SUPPORTED by policy.** |
| **Kitchen printer** | SOFTWARE CERTIFIED (via Odoo) | PHYSICAL CERT PENDING | Network ESC/POS; optional if you use KDS instead of printed tickets. |
| **Cash drawer** | SOFTWARE CERTIFIED | PHYSICAL CERT PENDING | RJ11/RJ12 drawer kicked by the receipt printer's DK port; wiring verified on-site. |
| **Integrated card terminal** | SOFTWARE CERTIFIED | PHYSICAL CERT PENDING | Orchestration via native Odoo terminal integration; the TEST simulator must never be live in production. |
| **Automated cash machine (Glory etc.)** | SOFTWARE CERTIFIED | PHYSICAL CERT PENDING | Software orchestration only; no cash-machine hardware on hand. Cashdro/Cashmatic also PHYSICAL CERT PENDING. |
| **Kiosk** | SOFTWARE CERTIFIED (pay-at-counter) | PHYSICAL CERT PENDING | No kiosk device tested; native card-terminal kiosk NOT claimed. |
| **Waiter tablet** | SOFTWARE CERTIFIED | PHYSICAL CERT PENDING | Reference: Android/iPad at 1024×768 landscape; verify Wi-Fi/resolution on-site. |
| **Cashier workstation** | SOFTWARE CERTIFIED | PHYSICAL CERT PENDING | Reference: x86 mini-PC/laptop on wired Ethernet. |

## What "PHYSICAL CERT PENDING" means for you

- The software talks to these devices and has been tested against simulators/native
  drivers; we will **not** claim your exact printer/terminal/cash machine is certified
  until it passes on your site.
- Certification happens during the on-site pilot: we install the device, run the
  device-acceptance checks, and record the model, firmware, connection, tested
  release, and PASS date in the HCL.
- **Buy to the reference targets** above to make on-site certification smooth. Avoid
  Bluetooth receipt printers entirely.

## Edge note

On Mezze Edge the go-live Edge validator reports host/hardware facts (printer, drawer,
NTP, nginx) as **NOT TESTED** — because they can only be confirmed on the physical
host, not from inside the software. That is by design, not a gap.
