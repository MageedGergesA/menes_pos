# RC7 — Pre-cutover backup and restore proof

## Backup

| Field | Value |
|---|---|
| Path | `/home/mageed/odoo_work_19/mezze-rc7-pilot-backups/pre-rc7_mezze_pilot_rc6_20260812-173401.zip` |
| Source DB | `mezze_pilot_rc6` (the live RC6 pilot database) |
| Source release | RC6 / `1.0.0-rc.6` |
| Taken | 2026-08-12 17:34:01 local |
| Size | 6 676 857 bytes (6.4 MB) |
| SHA-256 | `3f96a20e8f71547033a37557d1e717f8233d62cdc1c2e5074b15c1406a66f81e` |
| Includes filestore | **YES** — 447 filestore entries + `dump.sql` + `manifest.json` (449 zip entries) |

This is a **DB + filestore** archive. A database-only dump was explicitly not accepted.

## Restore proof

Restored into a throwaway database (`mezze_prerc7_restoretest`) before it was trusted:

| Check | Result |
|---|---|
| `db load` exit | 0 |
| Database opens | yes |
| `mezze_bridge` | installed, `19.0.2.7.0` |
| Attachments | 528 (527 carrying `store_fname`) |
| Filestore files restored | 447 / 447 |
| `store_fname` rows missing on disk | **0 / 527** |
| POS configs / products / active users | 1 / 17 / 6 |

Three attachments were opened byte-for-byte off disk as spot checks. The verification
database and its filestore were then removed; **the backup itself is retained.**
