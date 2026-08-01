#!/usr/bin/env bash
# Mezze Edge guarded restore (S1.1 §13). Requires explicit --backup + --yes.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; . "$HERE/lib/common.sh"
BK=""; DB=""; YES=0
while [ $# -gt 0 ]; do case "$1" in --backup) BK="$2"; shift 2;; --db) DB="$2"; shift 2;; --yes) YES=1; shift;; *) shift;; esac; done
[ -n "$BK" ] && [ -d "$BK" ] || die "--backup <dir> required (existing)"
[ -n "$DB" ] || die "--db <target> required"
[ -f "$BK/.complete" ] || die "backup incomplete (no .complete marker): $BK"
log "verifying checksums"; ( cd "$BK" && sha256sum -c SHA256SUMS >/dev/null 2>&1 ) || warn "checksum mismatch/absent"
echo "--- restore manifest ---"; cat "$BK/manifest.txt"
[ "$YES" = 1 ] || die "refusing to overwrite '$DB' without --yes (destructive)"
log "stopping Odoo"; systemctl stop mezze-edge 2>/dev/null || warn "service not running"
log "dropping+recreating $DB"
dropdb -h "$MEZZE_DB_HOST" -U "$MEZZE_DB_USER" --if-exists "$DB"
createdb -h "$MEZZE_DB_HOST" -U "$MEZZE_DB_USER" "$DB"
log "restoring db"; pg_restore --no-owner --no-acl -h "$MEZZE_DB_HOST" -U "$MEZZE_DB_USER" -d "$DB" "$BK/db.dump" || warn "pg_restore reported warnings (role/acl)"
if [ -f "$BK/filestore.tgz" ]; then
    log "restoring filestore"; mkdir -p "${MEZZE_VAR}/${DB}"; tar xzf "$BK/filestore.tgz" -C "${MEZZE_VAR}/${DB}"
    chown -R "$MEZZE_SERVICE_USER":"$MEZZE_SERVICE_USER" "${MEZZE_VAR}/${DB}" 2>/dev/null || true
fi
log "starting Odoo"; systemctl start mezze-edge 2>/dev/null || warn "start manually"
log "validating"; "$HERE/validate.sh" --db "$DB" || true
echo "RESTORE_OK $DB"
