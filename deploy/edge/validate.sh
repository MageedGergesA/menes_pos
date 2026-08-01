#!/usr/bin/env bash
# Mezze Edge validator wrapper (S1.1 §11). Runs mezze.golive.validator edge profile.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; . "$HERE/lib/common.sh"
DB=""; CONF="${MEZZE_ETC}/odoo.conf"
while [ $# -gt 0 ]; do case "$1" in --db) DB="$2"; shift 2;; --conf) CONF="$2"; shift 2;; *) shift;; esac; done
[ -n "$DB" ] || die "--db required"
load_secrets
"${MEZZE_PREFIX}/venv/bin/python" "${MEZZE_PREFIX}/odoo/odoo-bin" shell -c "$CONF" -d "$DB" --no-http <<'PY'
print(self.env['mezze.golive.validator'].report_text(profile='edge'))
r = self.env['mezze.golive.validator'].run(profile='edge')
print('EDGE_VALIDATOR_FAILS=%d' % r['fails'])
PY
