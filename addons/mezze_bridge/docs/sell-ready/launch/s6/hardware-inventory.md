# S6 — Hardware Inventory (PART 4)

Fill one row per physical device. **No device is CERTIFIED without physical
evidence** (photo + model/firmware + a real transaction). Mask serials.

| Role | Manufacturer | Model | Firmware/OS | Browser | Network | IP | Paper width | Serial (masked) | Cert scope | Evidence link |
|---|---|---|---|---|---|---|---|---|---|---|
| Cloud server | | | Ubuntu / hosted | — | — | | — | | Cloud Base | cloud/ |
| Edge Host A | | | Ubuntu 24.04 x86-64 | — | LAN | | — | | Edge Base | edge-host-a/ |
| Edge Host B | | | Ubuntu 24.04 x86-64 | — | LAN | | — | | Edge Base | edge-host-b/ |
| Cashier workstation | | | | Chromium __ | LAN | | — | | Base | cashier/ |
| Receipt printer | Epson (preferred) | TM-m30 (preferred) | | ePOS | Ethernet | | 80mm? | | Base | printer/ |
| Cash drawer | | | | via printer? | — | — | — | | Only if sold | drawer/ |
| KDS display | | | | (independent) | LAN | | — | | Base | kds/ |
| Waiter tablet | | | | | Wi-Fi | | — | | Base | tablet/ |
| Customer phone A | | | Android __ | | mobile/Wi-Fi | — | — | | Base | table-qr/ |
| Customer phone B | | | iOS __ (preferred) | | mobile/Wi-Fi | — | — | | Concurrency | table-qr/ |
| Router / AP | | | | — | LAN+WAN | | — | | Edge | wan/ |
| UPS | | | | — | — | — | — | | Edge (if continuity sold) | power/ |
| Kiosk | | | | | LAN | | — | | Only if sold | kiosk/ |
| Integrated terminal | | | | | | | — | | Only if sold | payments/ |
| Cash machine | | | | | | | — | | Only if sold | payments/ |

**Recommended targets (PART 3):** Epson TM-m30 series network ePOS, Ethernet,
static IP; drawer through the printer where supported; Edge host ≥4 vCPU / ≥8 GB
RAM / ≥80 GB disk on Ubuntu Server 24.04 LTS x86-64; real UPS if an offline
continuity claim is sold.
