# S6 — Definition of Done: Mezze Edge Base (PART 63)

Everything Cloud Base requires (see `cloud-dod.md`), **plus** the Edge-specific
gates below. Edge is **COMMERCIAL GO** only when all are **PASS** with real
evidence. These gates certify **offline restaurant operation**.

| # | Gate | PART | Result |
|---|---|---|---|
| E1 | Host A clean install (full S1.1B runbook) | 8 | PENDING |
| E2 | Host B clean install (separate clean env, not a clone) | 9 | PENDING |
| E3 | systemd / nginx / HTTPS / WebSocket | 8 | PENDING |
| E4 | Reboot: PG+Odoo+nginx auto-start, clients reconnect | 10 | PENDING |
| E5 | LAN-only operation (WAN physically cut) | 23 | PENDING |
| E6 | WAN outage 5 min — 0 lost / 0 dup orders / 0 dup pay | 24 | PENDING |
| E7 | WAN outage 30 min (multi-channel) | 25 | PENDING |
| E8 | **WAN outage ~2 h (flagship: 20+ counter, 10+ dine-in, 5+ QR, mixed, refund)** | 26 | PENDING |
| E9 | WAN reconnect: outbox converges, no dup callbacks/orders/payments | 27 | PENDING |
| E10 | Local server failure distinguished from Internet loss | 28 | PENDING |
| E11 | One worker failure — no double financial effect | 29 | PENDING |
| E12 | Power/UPS — PG integrity valid, clean recovery | 30 | PENDING |
| E13 | Edge backup (local + offsite) | 47 | PENDING |
| E14 | Edge restore + RTO | 48 | PENDING |
| E15 | No Critical defects | 56 | PENDING |
| E16 | No unresolved financial Major | 56 | PENDING |

**Edge Base readiness = 100%** only when Cloud rows 1–27 (minus Cloud-hosting
specifics) **and** E1–E16 PASS on real hardware.

> Note: `deploy/edge/*` scripts (install/backup/restore/upgrade/validate/
> support-bundle) are software-certified via `deploy/edge/tests/selftest.sh`; the
> **clean-host two-host certification (E1/E2) is the outstanding item** carried from
> `docs/sell-ready/edge/certification/s1_1b/RUNBOOK.md` (marked NOT EXECUTED).
