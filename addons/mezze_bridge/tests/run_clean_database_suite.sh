#!/usr/bin/env bash
# Hermetic clean-database runner for the Mezze suite (RC2 / D-2).
#
# Creates a UNIQUE empty database, installs mezze_bridge with --without-demo=all,
# runs the complete module suite, and drops the database again. It provisions NO
# business records — every business fixture is created by the test suite itself.
#
# Usage (no local absolute paths baked in — everything via env/args):
#   ODOO_BIN=/path/to/odoo-bin \
#   ODOO_CONF=/path/to/test.conf \
#   ADDONS_PATH=/path/a,/path/b \
#   [DB_PREFIX=mezze_clean] [KEEP_TEST_DB=1] [PGDATABASE_ADMIN=postgres] \
#   addons/mezze_bridge/tests/run_clean_database_suite.sh
#
# MEZZE_MASTER_KEY must be exported (base64 of 32 bytes) — its VALUE is never printed.
set -o pipefail
set -u

ODOO_BIN="${ODOO_BIN:-odoo-bin}"
ADMIN_DB="${PGDATABASE_ADMIN:-postgres}"
DB_PREFIX="${DB_PREFIX:-mezze_clean}"
# unique db name without Date/rand builtins from odoo; use $$ + nanoseconds
DB="${DB_PREFIX}_$$_$(date +%s%N 2>/dev/null || echo 0)"

if [ -z "${MEZZE_MASTER_KEY:-}" ]; then
  echo "ERROR: MEZZE_MASTER_KEY is not set (value never printed)." >&2
  exit 2
fi
echo "MEZZE_MASTER_KEY: present (value masked)"

# assemble odoo args
ODOO_ARGS=( -d "$DB" -i mezze_bridge --without-demo=all
            --test-enable --test-tags /mezze_bridge
            --stop-after-init --workers=0 --max-cron-threads=0 --log-level=test )
[ -n "${ODOO_CONF:-}" ] && ODOO_ARGS=( -c "$ODOO_CONF" "${ODOO_ARGS[@]}" )
[ -n "${ADDONS_PATH:-}" ] && ODOO_ARGS+=( --addons-path "$ADDONS_PATH" )

cleanup() {
  if [ "${KEEP_TEST_DB:-0}" = "1" ]; then
    echo "KEEP_TEST_DB=1 -> leaving database ${DB}"
  else
    dropdb --if-exists "$DB" 2>/dev/null \
      || psql -d "$ADMIN_DB" -c "DROP DATABASE IF EXISTS \"$DB\"" >/dev/null 2>&1 \
      || echo "WARN: could not drop ${DB}" >&2
  fi
}
trap cleanup EXIT

echo "==> creating empty database ${DB}"
createdb "$DB" 2>/dev/null || psql -d "$ADMIN_DB" -c "CREATE DATABASE \"$DB\"" >/dev/null 2>&1 || {
  echo "ERROR: could not create database ${DB}" >&2; exit 3; }

LOG="$(mktemp -t mezze_clean_suite.XXXXXX.log)"
echo "==> running suite (log: ${LOG})"
python3 "$ODOO_BIN" "${ODOO_ARGS[@]}" 2>&1 | tee "$LOG"
EXIT=${PIPESTATUS[0]}

echo "==================== RESULT ===================="
grep -E "odoo.tests.result:|post-tests in|tests.stats:" "$LOG" | tail -3
echo "ODOO_TEST_EXIT_CODE=${EXIT}"

# non-zero on any failure/error even if odoo exit was masked
if grep -qE "odoo.tests.result: [1-9][0-9]* failed|[1-9][0-9]* error\(s\)" "$LOG"; then
  echo "FAILED: test failures/errors detected" >&2
  exit 1
fi
exit "$EXIT"
