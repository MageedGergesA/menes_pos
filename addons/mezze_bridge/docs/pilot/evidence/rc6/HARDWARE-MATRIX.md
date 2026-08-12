# RC6 PILOT — HARDWARE MATRIX

**Re-checked on 2026-08-12 against the current host — not copied forward from RC5.**
Nothing here is marked PASS: enumeration is discovery, not certification.

## Headline

The host is still a **developer workstation, not a restaurant**. Re-enumeration found two
keyboards, a webcam, a Bluetooth adapter, earbuds and two *virtual* PDF printers. **No
point-of-sale peripheral of any kind is attached.**

| Category | Present | Evidence | Status |
|---|---|---|---|
| Receipt printer | NO | `lsusb`: no printer-class device. CUPS lists only `Generic-CUPS-PDF-Printer` and `PDF`, both virtual. No `/dev/usb/lp*`. | **MISSING** |
| Arabic physical receipt | NO | requires the above | **MISSING** |
| Cash drawer | NO | no serial/USB device; drawers are kicked via the receipt printer, which is absent | **MISSING** |
| KDS display / device | NO | no second display or tablet enumerated | **MISSING** |
| Staff tablet | NO | none on the LAN | **MISSING** |
| Customer phone | NO | 1 reachable LAN neighbour, and it is the gateway `192.168.8.1` | **MISSING** |
| Payment terminal | NO | no USB/serial/network terminal; no provider configured | **MISSING** |
| UPS | NO | no UPS device or service | **MISSING** |
| WAN-outage capability | PARTIAL | host on `wlo1 192.168.8.181/24` via gateway `192.168.8.1`; a real outage can be produced at the router, but that is a physical act and was not performed | **PROCEDURE ONLY** |

## Raw evidence (2026-08-12)

```
USB          SINO WEALTH Gaming KB
             SHARKOON Mediatrack Edge Mini Keyboard
             Intel Bluetooth 9460/9560
             Sunplus Integrated_Webcam_HD
CUPS         Generic-CUPS-PDF-Printer (idle) ; PDF (idle)     <- virtual only
serial/tty   /dev/ttyUSB*, /dev/ttyACM*, /dev/usb/lp*  -> none present
bluetooth    oraimo SpaceBuds Z ; soundcore P20i             <- audio only
network      lo 127.0.0.1/8 ; wlo1 192.168.8.181/24
neighbours   1 reachable (gateway)
```

Change since RC5: a second keyboard and a webcam are now enumerated. **Neither is POS
hardware**, so no gate status changes.

## Consequence

RC6 software is deployed and healthy, but **the physical pilot still cannot be executed on
this host**. Gates 1–19 need at minimum: a thermal receipt printer with an Arabic-capable
path, a cash drawer wired to it, a KDS display, a staff tablet, a separate customer phone,
and the intended payment terminal with its provider account.

The endpoint is LAN-reachable at `http://192.168.8.181:8090`, so devices can reach it once
they exist — subject to the secure-context caveat in `PROVIDER-MATRIX.md`.
