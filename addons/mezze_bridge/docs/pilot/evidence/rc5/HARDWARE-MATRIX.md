# RC5 PILOT — HARDWARE MATRIX

Inventory of hardware **actually present** on the prepared pilot host, taken by
enumerating USB, CUPS, serial/tty, Bluetooth and the network — not by assumption.

**Nothing here is marked PASS. Discovery is not certification.**

## The headline

The prepared host is a **developer workstation**, not a restaurant. Enumeration found a
keyboard, two *virtual* PDF printers, and a pair of Bluetooth earbuds. **No point-of-sale
peripheral of any kind is attached.**

| Category | Present | Detail | Status |
|---|---|---|---|
| Receipt printer | **NO** | `lsusb`: no printer class device. CUPS lists only `Generic-CUPS-PDF-Printer` and `PDF` — both virtual PDF sinks, not thermal receipt printers. No `/dev/usb/lp*`. | **MISSING** |
| Arabic receipt printing | **NO** | requires the above | **MISSING** |
| Cash drawer | **NO** | no serial/USB device; drawers are normally kicked via the receipt printer, which is absent | **MISSING** |
| KDS display / device | **NO** | no second display or tablet enumerated | **MISSING** |
| Staff tablet | **NO** | none on the LAN inventory | **MISSING** |
| Customer phone (separate device) | **NO** | none enumerated; 1 reachable LAN neighbour, which is the gateway `192.168.8.1` | **MISSING** |
| Payment terminal | **NO** | no USB/serial/network terminal; no provider configured (see `PROVIDER-MATRIX.md`) | **MISSING** |
| WAN-outage capability | **PARTIAL** | the host is on Wi-Fi `wlo1 192.168.8.181/24` via gateway `192.168.8.1`; a *real* WAN outage can be produced at the router/uplink, but that action is physical and was not performed | **PROCEDURE ONLY** |
| UPS / power-loss | **NO** | no UPS enumerated; no battery/UPS service present | **MISSING** |

## Raw evidence

```
USB (filtered)   Bus 001 Device 003: ID 258a:002a SINO WEALTH Gaming KB
CUPS             Generic-CUPS-PDF-Printer (idle) ; PDF (idle)      <- virtual only
serial/tty       /dev/ttyUSB*, /dev/ttyACM*, /dev/usb/lp*  -> none present
bluetooth        oraimo SpaceBuds Z ; soundcore P20i              <- audio only
network          lo 127.0.0.1/8 ; wlo1 192.168.8.181/24
LAN neighbours   1 reachable (gateway 192.168.8.1)
```

## Consequence

The software runtime is deployed and healthy, but **the physical pilot cannot be executed
on this host** as it stands. Executing gates 1–19 requires, at minimum:

* a thermal receipt printer (ideally the exact model intended for the site) with an
  Arabic-capable code page or graphics-mode printing,
* a cash drawer wired to that printer,
* a second display or tablet for KDS,
* a staff tablet,
* a separate customer phone,
* the intended payment terminal with its provider account.

Moving the pilot to the actual restaurant — or attaching the intended peripherals to this
host — is a prerequisite, not a formality. The endpoint is already LAN-reachable
(`http://192.168.8.181:8090`), so separate devices on the same Wi-Fi can reach it once
they exist.

## Network caveat for device testing

The pilot endpoint is **plain HTTP**, bound `0.0.0.0:8090`, not proxied by nginx and not
TLS-terminated. On a LAN-only pilot that is usually acceptable, but note:

* browsers restrict **camera access** (QR scanning) and service workers to secure
  contexts — a customer phone pointed at `http://192.168.8.181:8090` may be unable to use
  the camera, which would block the QR-ordering gate through no fault of the product;
* whether this host is port-forwarded to the Internet **cannot be determined from inside
  it** and is recorded as **UNKNOWN**. Before any device testing, confirm the endpoint is
  LAN-only, or place it behind HTTPS.
