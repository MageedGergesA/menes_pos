# RC5 PILOT — BACKUP / RESTORE EVIDENCE

A backup is not pilot-ready because a file exists. It was restored and proved.

## Backup

| | |
|---|---|
| Source database | `mezze_dev` (read-only; never modified) |
| Source filestore | `/home/mageed/.local/share/Odoo/filestore/mezze_dev` (18 MB) |
| Method | `odoo-bin db dump` — the product's own mechanism, **filestore included** (`--no-filestore` NOT used) |
| Path | `/home/mageed/odoo_work_19/mezze-rc5-pilot-backups/mezze_dev_pre-rc5_20260811-214030.zip` |
| Size | 6067105 bytes (5.8M) |
| Timestamp | 2026-08-11 21:40:32 |
| SHA-256 | `dfe336ee3b8954c13cfef0a46853d55f198de73cdd4220328d4e522cd00a96a1` |

Archive contents: `dump.sql` (18,064,585 bytes), `manifest.json`, and
**430 `filestore/` entries**.

## Restore proof

Restored into a throwaway database `mezze_restore_verify`:

| Check | Source `mezze_dev` | Restored | Verdict |
|---|---|---|---|
| module version | 19.0.2.2.0 | 19.0.2.2.0 | match |
| pos_config | 1 | 1 | match |
| restaurant_table | 12 | 12 | match |
| POS products | 15 | 15 | match |
| ir_attachment | 501 | 501 | match |
| attachments with `store_fname` | 500 | 500 | match |
| filestore files on disk | — | **430** | present |

**Attachment resolution: every one of the 500 stored attachments was resolved on disk —
0 missing.** Two spot-checked files opened at 9,152 and 15,497 bytes.

```
attachments checked: 500
missing on disk:     0
```

**Restore: PASS. Filestore proof: PASS.**

The verification database and its filestore were then destroyed. **The backup itself is
retained** and is the artifact the pilot database was built from — the pilot DB was
restored *from this zip*, not copied from the live source, so the backup's provenance is
proven by the deployment itself.

## Pre-shift / post-shift obligation

Gates 20 and 21 (pre-shift backup, post-shift restore proof) are **PENDING**. This backup
covers the *pre-deployment* state only. A fresh DB+filestore backup must be taken
immediately before the physical shift and a restore proved after it.
