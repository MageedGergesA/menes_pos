# S6 — Hardware Purchase Checklist

Buy the **base** kit for the profile(s) you are certifying. Do **not** buy optional
integration hardware unless you intend to sell that specific integration immediately.

| Item | Base Cloud? | Base Edge? | Optional? | Exact model acquired | Status |
|---|---|---|---|---|---|
| Network Epson TM-m30-series ePOS printer (Ethernet preferred, static IP) | **Required** | **Required** | | | |
| Cash drawer (through the printer where supported) | If in SKU | If in SKU | | | |
| 10-inch-class tablet (touch, Wi-Fi) | **Required** | **Required** | | | |
| Independent KDS display / tablet (separate device) | **Required** | **Required** | | | |
| Customer phone A (Android) | **Required** | **Required** | | | |
| Customer phone B (iOS preferred) | **Required** | **Required** | | | |
| Router / access point (LAN survives WAN loss) | **Required** | **Required** | | | |
| UPS (host + router) | — | **Required** (if continuity sold) | | | |
| Edge host ×2 (Ubuntu 24.04 x86-64, ≥4 vCPU / ≥8 GB / ≥80 GB) | — | **Required** | | | |
| Cashier workstation (Chromium desktop or POS terminal) | **Required** | **Required** | | | |

## Do NOT purchase (unless selling that exact optional integration now)
```
☐ kiosk hardware      — only if selling kiosk
☐ integrated card terminal (Stripe/Adyen/etc) — only the exact certified device
☐ Cashdro / Cashmatic / Glory cash machine    — only if selling it
```
Each optional device is **independently** certified against the exact
model/provider (PART 33/34). One device does not certify a category.

## Notes / policy
- **Bluetooth receipt printers are UNSUPPORTED** — do not buy for certification.
- USB/ESC-POS printing requires an **IoT box dependency** — record it; it is not
  equivalent to direct network ePOS.
- Prefer Ethernet + static/reserved IPs for printer, KDS, and Edge hosts.
