#!/usr/bin/env bash
# Mezze Edge customer exit (S1.1 §23). Exports data BEFORE any removal. Guarded.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; . "$HERE/lib/common.sh"
DB=""; PURGE=0
while [ $# -gt 0 ]; do case "$1" in --db) DB="$2"; shift 2;; --purge-software) PURGE=1; shift;; *) shift;; esac; done
[ -n "$DB" ] || die "--db required"
log "final export (customer keeps this regardless of subscription)"
MEZZE_BACKUP_TS="${MEZZE_BACKUP_TS:?set ts}" "$HERE/backup.sh" "$DB"
log "stopping + disabling service"; systemctl disable --now mezze-edge 2>/dev/null || true
log "removing nginx site"; rm -f /etc/nginx/sites-enabled/mezze-edge.conf; nginx -t && systemctl reload nginx 2>/dev/null || true
if [ "$PURGE" = 1 ]; then
    warn "purging software (data export already taken above)"
    rm -f /etc/systemd/system/mezze-edge.service /etc/logrotate.d/mezze-edge; systemctl daemon-reload
    log "left in place for customer handover: ${MEZZE_VAR}/${DB}/backups"
else
    log "software left installed; use --purge-software to remove binaries (data export retained)"
fi
echo "UNINSTALL_DONE $DB"
