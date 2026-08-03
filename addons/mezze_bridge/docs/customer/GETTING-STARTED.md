# Mezze POS — Getting Started

Mezze is a restaurant operating system for MENA food & beverage businesses,
built on Odoo 19.0 Community (the `mezze_bridge` addon). It runs the counter, the
dining room, the kitchen, delivery, and customer self-ordering (QR menu, table-QR,
pickup, kiosk) — bilingual English/Arabic, right-to-left aware.

## The two editions

Mezze ships in two editions built from the **same** code. The edition is detected at
runtime and reported by the admin *Version* screen.

| | **Mezze Cloud** | **Mezze Edge** |
|---|---|---|
| Where it runs | Mezze-managed hosting of the custom code (this is **not** standard Odoo Online) | On hardware **at your branch** — Odoo Community + PostgreSQL on Ubuntu 24.04 LTS, behind nginx |
| Keeps selling if the internet drops | No — needs WAN | **Yes** — the LAN keeps taking orders, firing the kitchen, and printing through a WAN outage |
| Backups | Managed by Mezze | Local on the box + optional offsite copy |
| Updates | Rolled out by Mezze | You run the backup-gated `upgrade.sh` |
| Best for | Sites wanting zero on-site ops | High-volume / unreliable-connectivity sites that must never stop selling |

Online-only steps (online payment, aggregator webhooks, cross-branch reporting)
need WAN in **both** editions; on Edge they simply resume when the internet returns.

## First login

1. Open your Mezze URL. Admins land on the **Admin Console**; staff sign in to the
   POS / waiter / KDS surfaces with a personal PIN.
2. Never keep a default `admin/admin` login — see `SECURITY-BASELINE.md`.
3. Confirm you are on the right build: the admin *Version* screen shows product
   version, edition (Cloud/Edge), Odoo version, and commit.

## Onboarding — the setup checklist

Onboarding is a resumable, first-run checklist. Each step maps to a real Odoo
configuration screen, and **completion is proven by the live go-live validator**,
not a box you tick. Steps in order:

1. **Restaurant & company** — company, currency, timezone.
2. **Branch / POS point** — at least one POS configuration.
3. **Taxes & journals** — cash/bank journals and taxes.
4. **Payment methods** — cash, card, QR, account (each classified + cash gets a journal).
5. **Menu / products** — POS menu items with categories.
6. **Tables (dine-in)** — optional; needed for table service and table-QR.
7. **Kitchen display (KDS)** — optional; screen layout.
8. **Staff & PINs** — cashiers/managers/auditors with PINs.
9. **Payment devices** — optional; card terminals / cash machines.
10. **Pickup & delivery** — optional; zones, fees, COD.
11. **Self-order channels** — optional; QR menu, kiosk, Arabic language.
12. **Printers & drawer** — optional; receipt printer + cash drawer.
13. **Review & go-live** — the validator's overall verdict for your chosen format.

Optional steps never block go-live unless your commercial profile requires them
(e.g. choosing *Delivery* makes a delivery zone required).

## Go-live readiness is validated, not self-declared

You do not "declare" yourself ready. The **Go-Live validator** inspects your live
configuration and returns Pass / Warning / Fail per check against a commercial
profile (`counter`, `restaurant`, `restaurant_qr`, `delivery`, `full`, or `edge`).
A profile turns the capabilities that business format needs into hard requirements —
pick *Delivery* with no zone configured and the check **fails**. Any unresolved
**Fail** blocks the launch. Honest hardware/host facts stay **NOT TESTED** and are
never faked to Pass. Run it any time from the admin API
(`POST /mezze/api/v1/admin/golive` with your `profile`) or the Review step.

Next: `ADMIN-GUIDE.md` for the console, roles, audit, and staging.
