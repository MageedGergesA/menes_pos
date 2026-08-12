# RC7 — Hardware matrix

Re-inventoried on the current host for RC7. **Not copied from the RC6 report.**

| Device | Status | Evidence |
|---|---|---|
| Receipt printer | **MISSING** | CUPS exposes only `Generic-CUPS-PDF-Printer` and `PDF`; no thermal/ESC-POS device |
| Cash drawer | **MISSING** | no USB-serial adapter; only motherboard `ttyS0–ttyS9` |
| KDS physical device | **MISSING** | no second display or tablet attached |
| Staff tablet | **MISSING** | no tablet enumerated on USB or network |
| Customer phone | **MISSING** | none paired; and see the secure-context blocker in ENVIRONMENT.md |
| Payment terminal | **MISSING** | no terminal on USB or serial |
| UPS | **MISSING** | no UPS/HID power device |
| WAN outage handling | **PROCEDURE ONLY** | no controllable WAN link to interrupt on this host |

Enumerated USB: two keyboards (SINO WEALTH gaming KB, SHARKOON 2.4G mini keyboard/mouse),
an Intel Bluetooth radio, an integrated webcam, and root hubs. Input devices: keyboards
and a mouse only.

**Conclusion: the host still has no POS hardware.** RC7 is deployed and software-ready;
what is missing is devices, not software.
