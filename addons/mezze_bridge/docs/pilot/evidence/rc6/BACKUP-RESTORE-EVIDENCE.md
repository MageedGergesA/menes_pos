# RC6 PILOT — BACKUP / RESTORE EVIDENCE

The RC5 pilot state was frozen **before** cutover, and the artifact was proved by restoring
it — not assumed valid because a file exists.

## Pre-cutover backup (the rollback artifact)

| | |
|---|---|
| Source database | `mezze_pilot_rc5` |
| Path | `/home/mageed/odoo_work_19/mezze-rc5-pilot-backups/mezze_pilot_rc5_PRE-RC6-CUTOVER_20260812-102327.zip` |
| Size | 6395068 bytes (6.2M) |
| Taken | 2026-08-12 10:23:29 |
| SHA-256 | `e04c53d50b5dc398e73ce6ad09b423196a49e9e4d13a95541c404a2186749e0f` |
| Method | `odoo-bin db dump` — filestore included (`--no-filestore` NOT used) |
| Contents | `dump.sql`, `manifest.json`, **446 filestore entries** |

This is distinct from the earlier original-source backup of `mezze_dev`; both are kept.

## Restore proof

Restored into a throwaway database `mezze_precutover_verify`:

| Check | Source | Restored |
|---|---|---|
| module version | 19.0.2.7.0 | 19.0.2.7.0 |
| pos_config | 1 | 1 |
| restaurant_table | 12 | 12 |
| product_template | 17 | 17 |
| ir_attachment | 526 | 526 |
| mezze_terminal | 2 | 2 |

Filestore: **446 files**. **Attachments missing on disk: 0** (of 525 stored).

**Restore: PASS. Filestore proof: PASS.**

The verification copy was destroyed. **The backup is retained** — and the RC6 pilot
database was created *from this very artifact*, so its provenance is demonstrated by the
deployment itself rather than asserted.

## Pre-shift / post-shift obligation still open

Gates 20 and 21 remain **PENDING**. This backup covers the pre-cutover state, not the
pre-shift state. A fresh DB+filestore backup must be taken immediately before the physical
shift, and a restore proved after it. Taking gate 20's backup early would make it
worthless.
