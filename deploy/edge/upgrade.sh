#!/usr/bin/env bash
# Mezze Edge upgrade (S1.1 §21). Mandatory backup first; reports failing stage.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; . "$HERE/lib/common.sh"
DB="${1:-${MEZZE_DB_NAME:?db required}}"
log "stage: preflight"; "$HERE/release-identity.sh" --db "$DB" || die "preflight failed"
log "stage: mandatory backup"; MEZZE_BACKUP_TS="${MEZZE_BACKUP_TS:?set ts}" "$HERE/backup.sh" "$DB" || die "backup failed — aborting upgrade"
log "stage: stop service"; systemctl stop mezze-edge || warn "not running"
log "stage: module upgrade"
load_secrets
sudo -u "$MEZZE_SERVICE_USER" MEZZE_MASTER_KEY="${MEZZE_MASTER_KEY:-}" \
  "${MEZZE_PREFIX}/venv/bin/python" "${MEZZE_PREFIX}/odoo/odoo-bin" -c "${MEZZE_ETC}/odoo.conf" \
  -d "$DB" -u mezze_bridge --stop-after-init || die "module upgrade FAILED (restore from the backup just taken)"
log "stage: restart"; systemctl start mezze-edge || warn "start manually"
log "stage: validate"; "$HERE/validate.sh" --db "$DB" || die "post-upgrade validation FAILED"
echo "UPGRADE_OK $DB"
