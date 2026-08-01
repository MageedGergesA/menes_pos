#!/usr/bin/env bash
# Mezze Edge local backup (S1.1 §12). WAN NOT required. Optional off-site after.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; . "$HERE/lib/common.sh"
[ -f "${MEZZE_ETC}/backup.env" ] && { set -a; . "${MEZZE_ETC}/backup.env"; set +a; }
DB="${1:-${MEZZE_DB_NAME:?db required}}"
BDIR="${MEZZE_BACKUP_DIR:-${MEZZE_VAR}/${DB}/backups}"
TS="${MEZZE_BACKUP_TS:?pass MEZZE_BACKUP_TS=YYYYmmdd-HHMMSS}"   # caller supplies (no Date builtin in some ctx)
DEST="${BDIR}/${DB}-${TS}"
mkdir -p "$DEST"
log "backing up DB $DB -> $DEST"
pg_dump -Fc -h "${MEZZE_DB_HOST}" -U "${MEZZE_DB_USER}" "$DB" -f "${DEST}/db.dump"
FS="${MEZZE_VAR}/${DB}/filestore"
[ -d "$FS" ] && tar czf "${DEST}/filestore.tgz" -C "$(dirname "$FS")" "$(basename "$FS")" || warn "no filestore at $FS"
# version metadata (no secrets)
{ echo "db=$DB"; echo "timestamp=$TS";
  echo "module_version=$(psql -tAqh "$MEZZE_DB_HOST" -U "$MEZZE_DB_USER" -d "$DB" -c "SELECT latest_version FROM ir_module_module WHERE name='mezze_bridge'" 2>/dev/null | tr -d ' ')";
} > "${DEST}/manifest.txt"
( cd "$DEST" && sha256sum db.dump filestore.tgz manifest.txt 2>/dev/null > SHA256SUMS || true )
touch "${DEST}/.complete"    # atomic completion marker
du -sh "$DEST" | awk '{print "backup_size="$1}'
# retention prune
if [ -n "${MEZZE_BACKUP_RETENTION_DAYS:-}" ]; then
    find "$BDIR" -maxdepth 1 -type d -name "${DB}-*" -mtime +"${MEZZE_BACKUP_RETENTION_DAYS}" -exec rm -rf {} + 2>/dev/null || true
fi
# optional off-site (never fails the local backup)
if [ "${MEZZE_OFFSITE_ENABLED:-false}" = "true" ] && [ -n "${MEZZE_OFFSITE_TARGET:-}" ]; then
    rsync -a "$DEST" "${MEZZE_OFFSITE_TARGET}/" 2>/dev/null && log "off-site copy ok" || warn "off-site copy failed (local backup still valid)"
fi
echo "BACKUP_OK $DEST"
