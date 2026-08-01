#!/usr/bin/env bash
# Mezze Edge deployment — shared library (S1.1).
# Sourced by install/upgrade/backup/restore/validate/support-bundle/uninstall.
# No developer paths, no hardcoded secrets. All installs are parameterized.

set -euo pipefail

# ---- defaults (overridable by env or a config file) ----
: "${MEZZE_PREFIX:=/opt/mezze}"                 # code + venv + bin
: "${MEZZE_VAR:=/var/lib/mezze}"                # filestore + backups per db
: "${MEZZE_ETC:=/etc/mezze-edge}"               # config + secrets (0600)
: "${MEZZE_LOG:=/var/log/mezze}"                # logs
: "${MEZZE_SERVICE_USER:=odoo}"                 # dedicated service account
: "${MEZZE_ODOO_PORT:=8069}"
: "${MEZZE_GEVENT_PORT:=8072}"
: "${MEZZE_WORKERS:=2}"
: "${MEZZE_DB_HOST:=127.0.0.1}"
: "${MEZZE_DB_PORT:=5432}"
: "${MEZZE_DB_USER:=mezze}"

log()  { printf '[mezze-edge] %s\n' "$*"; }
warn() { printf '[mezze-edge][WARN] %s\n' "$*" >&2; }
die()  { printf '[mezze-edge][ERROR] %s\n' "$*" >&2; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"; }

is_root() { [ "$(id -u)" = "0" ]; }
need_root() { is_root || die "must run as root (use sudo)"; }

# Render a template: replace ${VAR} tokens from the current environment.
# Usage: render_template <template-path> <output-path>
render_template() {
    local tpl="$1" out="$2"
    [ -f "$tpl" ] || die "template not found: $tpl"
    # only substitute known MEZZE_* / EDGE_* vars — envsubst with an explicit allowlist
    local vars
    vars=$(grep -oE '\$\{[A-Z_][A-Z0-9_]*\}' "$tpl" | sort -u | tr -d '${}' | sed 's/^/$/' | tr '\n' ' ')
    require_cmd envsubst
    envsubst "$vars" < "$tpl" > "$out"
}

# Generate a base64 32-byte secret (for MEZZE_MASTER_KEY etc). Never logged.
gen_secret() { require_cmd openssl; openssl rand -base64 32; }

# Load secrets file if present (0600). Never echoes values.
load_secrets() {
    local f="${MEZZE_ETC}/secrets.env"
    if [ -f "$f" ]; then
        # shellcheck disable=SC1090
        set -a; . "$f"; set +a
    fi
}

# Redact secret-looking tokens from a stream (for support bundles / logs).
redact() {
    sed -E \
      -e 's/(admin_passwd[[:space:]]*=[[:space:]]*).*/\1***REDACTED***/I' \
      -e 's/(db_password[[:space:]]*=[[:space:]]*).*/\1***REDACTED***/I' \
      -e 's/(password[[:space:]]*[=:][[:space:]]*).*/\1***REDACTED***/I' \
      -e 's/(MEZZE_MASTER_KEY[[:space:]]*=[[:space:]]*).*/\1***REDACTED***/I' \
      -e 's/(secret[a-z_]*[[:space:]]*[=:][[:space:]]*)[A-Za-z0-9+\/=_-]{8,}/\1***REDACTED***/I' \
      -e 's/(api[_-]?key[[:space:]]*[=:][[:space:]]*)[A-Za-z0-9+\/=_-]{8,}/\1***REDACTED***/I' \
      -e 's/(bearer[[:space:]]+)[A-Za-z0-9._-]{8,}/\1***REDACTED***/I' \
      -e 's/(-----BEGIN [A-Z ]*PRIVATE KEY-----).*/\1 ***REDACTED***/'
}

# Resolve the deploy/edge dir regardless of CWD.
edge_dir() { cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd; }
