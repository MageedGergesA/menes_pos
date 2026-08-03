# Mezze POS — Implementation Partner Checklist

Step-by-step for a partner deploying a new Mezze site, from edition choice to go-live
sign-off. Do the steps in order; each ends in a verifiable state.

## 1. Pick the edition

- [ ] **Mezze Cloud** — Mezze-managed hosting; needs WAN; zero on-site ops.
- [ ] **Mezze Edge** — branch-local on Ubuntu 24.04 LTS; keeps selling on the LAN
      through a WAN outage; operator owns the host.
- Decide by connectivity reliability and volume. See `docs/product/EDITIONS.md`.

## 2. Provision

- **Cloud:** request the managed deployment from Mezze; confirm the URL, HTTPS, and the
  `stable` release channel.
- **Edge:** run `deploy/edge/install.sh` on the certified target (Ubuntu 24.04 LTS
  x86-64) — Odoo Community + PostgreSQL + `mezze_bridge` behind nginx. Confirm
  `proxy_mode`, `workers >= 1`, and HTTPS base URL.
- [ ] Set `MEZZE_MASTER_KEY` in the environment; secure the DB manager; no `admin/admin`.

## 3. Run onboarding

- [ ] Work the onboarding checklist (`/admin/onboarding`): Restaurant & company →
      Branch/POS → Taxes & journals → Payment methods → Menu → Tables → KDS →
      Staff & PINs → Payment devices → Pickup & delivery → Self-order channels →
      Printers & drawer → Review.
- [ ] Each step's completion is **derived from the live validator** — configure the
      real Odoo screen, don't just tick.

## 4. Configure the business-format profile

Choose the commercial profile that matches the site and configure to satisfy it:

| Profile | Requires (beyond baseline) |
|---|---|
| `counter` | POS config, payment methods, cash journal, journals |
| `restaurant` | + menu catalog |
| `restaurant_qr` | + table QR ordering |
| `delivery` | + delivery zone + COD cash method |
| `full` | + table QR + delivery + COD + online provider |
| `edge` | Edge host/Postgres/proxy/WAN checks |

## 5. Run the go-live validator to green

- [ ] `POST /mezze/api/v1/admin/golive` with the chosen `profile`.
- [ ] Resolve **every Fail** (a required capability left N/A becomes a Fail for that
      profile).
- [ ] On Edge, also run the `edge` profile.
- [ ] Confirm remaining **NOT TESTED** items are only physical hardware/host facts to
      certify on-site — never force them to pass.
- [ ] Security gate: master key set, shared-admin disabled, `api_security=enforce`,
      HTTPS, no demo data, simulators off (see `docs/customer/SECURITY-BASELINE.md`).

## 6. On-site hardware certification

- [ ] Certify the physical devices (receipt printer, drawer, terminal, cash machine,
      kiosk) against the HCL; record model, firmware, connection, tested release, PASS
      date. See `docs/customer/HARDWARE-COMPATIBILITY.md` and `docs/sell-ready/hardware/HCL.md`.

## 7. Staff training

- [ ] Train by role using the customer guides: cashier, waiter, host, KDS, manager,
      delivery, self-service.
- [ ] Confirm personal PINs and that manager-gated actions (refund/void/comp) prompt
      correctly and audit.

## 8. Backup verification

- **Cloud:** confirm with Mezze that scheduled backups + offsite are running.
- **Edge:** confirm `deploy/edge/backup.sh` is scheduled; do a **test restore** with
  `restore.sh` on a staging box (RTO ≈ 14s recorded) and confirm it comes up.

## 9. Go-live sign-off

- [ ] Owner completes `docs/customer/UAT.md`.
- [ ] Validator overall is not Fail for the profile; security gate clean.
- [ ] Backups verified; hardware certified on-site or explicitly deferred with the
      owner's awareness.
- [ ] Record the release identity (`/admin/version`) as the launched build.

Partner: ____________  Owner: ____________  Go-live date: __________
