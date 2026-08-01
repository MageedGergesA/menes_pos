#!/usr/bin/env bash
# Mezze Edge release identity (S1.1 §10). Answers "what build is this branch running?"
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; . "$HERE/lib/common.sh"
DB=""; while [ $# -gt 0 ]; do case "$1" in --db) DB="$2"; shift 2;; *) shift;; esac; done
ADDONS="${MEZZE_ADDONS_SRC:-}"
GITDIR=""
for d in "$ADDONS" "${MEZZE_PREFIX}/mezze" "$HERE/../.."; do [ -d "$d/.git" ] && GITDIR="$d" && break; done
echo "mezze_release_tag=$( [ -n "$GITDIR" ] && git -C "$GITDIR" describe --tags --always 2>/dev/null || echo n/a )"
echo "git_commit=$( [ -n "$GITDIR" ] && git -C "$GITDIR" rev-parse HEAD 2>/dev/null || echo n/a )"
echo "odoo_version=$("${MEZZE_PREFIX}/venv/bin/python" "${MEZZE_PREFIX}/odoo/odoo-bin" --version 2>/dev/null | awk '{print $NF}' || echo n/a)"
echo "postgres_version=$(psql -tAq -c 'show server_version' 2>/dev/null || echo n/a)"
echo "host=$(hostname)"
[ -n "$DB" ] && echo "module_version=$(psql -tAq -h "${MEZZE_DB_HOST}" -U "${MEZZE_DB_USER}" -d "$DB" -c "SELECT latest_version FROM ir_module_module WHERE name='mezze_bridge'" 2>/dev/null | tr -d ' ' || echo n/a)"
[ -n "$DB" ] && echo "branch_db=$DB"
