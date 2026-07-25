# Rollback Plan (P1 §21)

## Decision points (in order of least→most disruptive)
1. **Rollback release only** — a UI/logic defect, no data corruption.
2. **Stop public ordering** — QR/online/aggregator issue; POS keeps operating.
3. **Continue offline POS** — connectivity/backend degraded; sales keep ringing, sync later.
4. **Close branch operation** — safety/financial integrity at risk.
5. **Restore database** — data corruption (last resort; see below).

## Application / module rollback (release only)
- Redeploy the previous addon tag (previous `mezze_bridge` version); restart workers.
- Frontend assets roll back with the addon (checksums in the release manifest).
- **Migrations:** the pilot migrations (19.0.1.x.0) are forward-only re-seeds/upserts of catalog/config;
  they do NOT rewrite financial data. There is **no reverse DB migration** — for a schema-level rollback
  use the restore-based procedure below. Downgrading the addon without restoring is only safe when the
  newer migration added optional columns (status token, channel) that the old code ignores.

## Restore-based rollback (irreversible-migration / data-corruption path)
1. Stop workers + public ordering.
2. Restore the last good `pg_dump` into a clean DB (`../backup-restore/backup-restore.txt`: ~14s RTO).
3. Restore the filestore snapshot.
4. Deploy the matching addon version.
5. Reconcile any orders taken after the recovery point from the offline journal / receipts.

## Integration suspension / pause switches
- Aggregator: deactivate the `mezze.aggregator` channel.
- QR / online: disable the channel in branch config (temporary suspension).
- Payment: switch tenders to cash (runbook) if a provider is unhealthy.
- Branch fallback: offline POS mode (sales queue + idempotent sync).

## Do not
Promise reversible DB migrations. The pilot migrations are forward-only; rollback of schema changes is
restore-based only.
