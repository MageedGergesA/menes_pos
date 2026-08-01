#!/usr/bin/env bash
# Mezze Edge support bundle (S1.1 §15). Redacts secrets. One archive for upload.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; . "$HERE/lib/common.sh"
DB="${1:-${MEZZE_DB_NAME:-}}"
TS="${MEZZE_BUNDLE_TS:?pass MEZZE_BUNDLE_TS=YYYYmmdd-HHMMSS}"
TMP="$(mktemp -d)"; OUT="/tmp/mezze-support-${TS}.tar.gz"
{ echo "timestamp=$TS"; echo "host=$(hostname)"; echo "db=${DB:-n/a}";
  echo "odoo=$("${MEZZE_PREFIX}/venv/bin/python" "${MEZZE_PREFIX}/odoo/odoo-bin" --version 2>/dev/null || echo n/a)";
  echo "postgres=$(psql -V 2>/dev/null || echo n/a)"; } > "$TMP/identity.txt"
"$HERE/release-identity.sh" ${DB:+--db "$DB"} > "$TMP/release-identity.txt" 2>/dev/null || echo "n/a" > "$TMP/release-identity.txt"
systemctl status mezze-edge nginx postgresql --no-pager > "$TMP/services.txt" 2>&1 || true
[ -f "${MEZZE_ETC}/odoo.conf" ] && redact < "${MEZZE_ETC}/odoo.conf" > "$TMP/odoo.conf.redacted"
nginx -t > "$TMP/nginx-test.txt" 2>&1 || true
df -h > "$TMP/disk.txt" 2>&1 || true; free -h > "$TMP/memory.txt" 2>&1 || true
ip -brief addr > "$TMP/network.txt" 2>&1 || true
[ -f "${MEZZE_LOG}/${DB}.log" ] && tail -n 500 "${MEZZE_LOG}/${DB}.log" | redact > "$TMP/odoo.log.tail" || true
[ -f "${MEZZE_LOG}/nginx-error.log" ] && tail -n 200 "${MEZZE_LOG}/nginx-error.log" | redact > "$TMP/nginx-error.tail" || true
"$HERE/validate.sh" --db "$DB" > "$TMP/validator.txt" 2>&1 || true
tar czf "$OUT" -C "$TMP" .
rm -rf "$TMP"
echo "SUPPORT_BUNDLE $OUT"
