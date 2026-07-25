# Migration (P1 §6)
Migration scripts under `migrations/19.0.1.1.0 … 19.0.1.6.0` are **idempotent** (each re-seeds/upserts; safe to re-run).
Versions 19.0.1.7.0 and 19.0.1.8.0 add NO schema migration script: the new columns
(`mezze_channel`, `mezze_status_token` (now hash), `mezze_status_expiry`, `mezze_status_revoked`)
are created by Odoo's ORM auto-schema on `-u mezze_bridge`. Applying `-u` on the existing DB
completed cleanly (0 errors) and the 218-test suite passes post-upgrade.
**Rollback of a migration:** restore the pre-upgrade `pg_dump -Fc` (see backup-restore/). Data columns are additive, so a downgrade is a restore, not a destructive DDL.
