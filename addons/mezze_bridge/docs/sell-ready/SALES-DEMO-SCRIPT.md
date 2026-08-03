# Mezze POS — Sales Demo Script (15–20 min)

A tight, honest demo runbook. The rule that keeps Mezze sellable: **never demo an
un-certified device or a live payment provider as if it were certified.** If you
follow the guardrails, everything you show is real and true.

## Before the demo

- Use a **non-production** database on the `development` profile.
- Optionally load the demo restaurant so the menu is populated (never on production):
  see `demo/README.md` — run `seed_pizza.py`, then `seed_promos.py`, then
  `seed_images.py` via `odoo-bin shell`. `seed_pizza.py` sets the `demo_loaded`
  marker, which the go-live validator will **FAIL** in production — that is a feature
  to mention, not a bug.
- Confirm the build on the **Version** screen (product version, edition).

## Story beats

1. **The pitch (1 min).** "One restaurant OS on Odoo 19 Community — counter, dine-in,
   kitchen, delivery, and customer self-ordering — bilingual EN/AR, and on **Edge** it
   keeps selling even if the internet drops."
2. **Counter cash sale (2 min).** Ring items, take cash, print a receipt. Point out
   server-side pricing/tax — the screen can't sell at the wrong price.
3. **Dine-in (3 min).** Open a table, add items, **fire** a course, add more, fire
   again — show the KDS getting each item **exactly once**. Bill and pay.
4. **Table-QR ordering (3 min).** Scan a table QR on a phone, add an item, watch it
   join the same table and hit the kitchen once. Emphasise: table QR ≠ payment QR, and
   the customer can't inject a price.
5. **Delivery COD (2 min).** Place a COD order (real unpaid), assign a courier, record
   collection — cash reconciles.
6. **Manager controls (2 min).** Refund with a **manager PIN**; show the audit line.
7. **Go-live validator (2 min).** Run it for the `full` profile — show Pass/Warn/Fail
   and that honest **NOT TESTED** hardware facts are never faked. This is the trust
   moment: "we tell you exactly what's certified."
8. **Editions (1 min).** Cloud vs Edge; Edge survives a WAN outage on the LAN.
9. **Close (1 min).** Onboarding is validated, not self-declared; two editions; roadmap
   for anything not in v1.

## What to SAY vs what NOT to claim

| Say | Do NOT claim |
|---|---|
| "Integrated terminal orchestration is software-certified; your device is certified on-site." | "This card terminal is certified." (it's PHYSICAL CERT PENDING) |
| "Cash machine orchestration is built." | "Glory is certified." (no hardware — PHYSICAL CERT PENDING) |
| "Online payment via Paymob is redirect-based, pending certification." | Demoing a live Paymob charge, or claiming refund/tokenization/capture. |
| "Bank-app QR is built." | "Egypt/InstaPay QR works." (NOT CERTIFIED) |
| "Split by amount or line." | "Split by seat." (DEFERRED V2) |
| "Delivery tracks order state." | "Live GPS / route optimisation." (NOT SUPPORTED) |
| "Certified on Odoo 19 Community." | "Runs on Odoo 20." (not claimed) |

If asked for a not-yet-certified capability, be direct: point to
`KNOWN-LIMITATIONS.md` and align it with the pilot/roadmap. Honesty is the sale.
