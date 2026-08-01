#!/usr/bin/env bash
# Mezze Edge installer (S1.1). Provisions a branch Edge deployment on a clean
# supported Linux host. Parameterized; no dev paths; no hardcoded secrets.
#
#   sudo ./install.sh --hostname mezze.local --db-name restaurant01 \
#        --branch-name "Main Branch" --odoo-source /opt/mezze/odoo \
#        --addons-source /opt/mezze/addons [--workers 2] [--dry-run]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$HERE/lib/common.sh"

DRY_RUN=0
MEZZE_HOSTNAME=""; MEZZE_DB_NAME=""; MEZZE_BRANCH_NAME=""
ODOO_SRC=""; ADDONS_SRC=""

while [ $# -gt 0 ]; do
    case "$1" in
        --hostname) MEZZE_HOSTNAME="$2"; shift 2;;
        --db-name) MEZZE_DB_NAME="$2"; shift 2;;
        --branch-name) MEZZE_BRANCH_NAME="$2"; shift 2;;
        --odoo-source) ODOO_SRC="$2"; shift 2;;
        --addons-source) ADDONS_SRC="$2"; shift 2;;
        --workers) MEZZE_WORKERS="$2"; shift 2;;
        --odoo-port) MEZZE_ODOO_PORT="$2"; shift 2;;
        --gevent-port) MEZZE_GEVENT_PORT="$2"; shift 2;;
        --dry-run) DRY_RUN=1; shift;;
        *) die "unknown argument: $1";;
    esac
done

[ -n "$MEZZE_HOSTNAME" ] || die "--hostname required"
[ -n "$MEZZE_DB_NAME" ] || die "--db-name required"
[ -n "$ODOO_SRC" ] || die "--odoo-source required"
[ -n "$ADDONS_SRC" ] || die "--addons-source required"
export MEZZE_HOSTNAME MEZZE_DB_NAME MEZZE_BRANCH_NAME
export MEZZE_ADDONS_PATH="${ODOO_SRC}/addons,${ADDONS_SRC}"
export MEZZE_CERT_PATH="${MEZZE_CERT_PATH:-${MEZZE_ETC}/tls/${MEZZE_HOSTNAME}.crt}"
export MEZZE_CERT_KEY="${MEZZE_CERT_KEY:-${MEZZE_ETC}/tls/${MEZZE_HOSTNAME}.key}"

run() { if [ "$DRY_RUN" = 1 ]; then echo "DRY-RUN> $*"; else eval "$@"; fi; }

log "Mezze Edge install — host=$MEZZE_HOSTNAME db=$MEZZE_DB_NAME dry_run=$DRY_RUN"

# ---- 1. prerequisites ----
log "checking prerequisites"
for c in psql pg_dump python3 nginx openssl envsubst systemctl; do
    command -v "$c" >/dev/null 2>&1 || warn "prerequisite missing (install before real run): $c"
done
[ "$DRY_RUN" = 1 ] || need_root
[ -d "$ODOO_SRC" ] || warn "odoo source not found at $ODOO_SRC (expected on a real host)"
[ -d "$ADDONS_SRC" ] || warn "addons source not found at $ADDONS_SRC"

# ---- 2. service user + directories ----
log "service user + directories"
run "id -u '$MEZZE_SERVICE_USER' >/dev/null 2>&1 || useradd --system --home '$MEZZE_PREFIX' --shell /usr/sbin/nologin '$MEZZE_SERVICE_USER'"
for d in "$MEZZE_PREFIX" "$MEZZE_VAR/$MEZZE_DB_NAME/filestore" "$MEZZE_VAR/$MEZZE_DB_NAME/backups" "$MEZZE_LOG" "$MEZZE_ETC" "$MEZZE_ETC/tls"; do
    run "mkdir -p '$d'"
done
run "chown -R '$MEZZE_SERVICE_USER':'$MEZZE_SERVICE_USER' '$MEZZE_VAR' '$MEZZE_LOG'"
run "chmod 0750 '$MEZZE_ETC'"

# ---- 3. python venv + deps ----
log "python venv + dependencies"
run "python3 -m venv '$MEZZE_PREFIX/venv'"
run "'$MEZZE_PREFIX/venv/bin/pip' install --upgrade pip wheel"
run "test -f '$ADDONS_SRC/mezze_bridge/requirements.txt' && '$MEZZE_PREFIX/venv/bin/pip' install -r '$ADDONS_SRC/mezze_bridge/requirements.txt' || true"
run "test -f '$ODOO_SRC/requirements.txt' && '$MEZZE_PREFIX/venv/bin/pip' install -r '$ODOO_SRC/requirements.txt' || true"
run "ln -sfn '$ODOO_SRC' '$MEZZE_PREFIX/odoo'"

# ---- 4. secrets (generated once, 0600, never printed) ----
log "secrets (generated once, 0600)"
if [ "$DRY_RUN" = 1 ]; then
    echo "DRY-RUN> generate ${MEZZE_ETC}/secrets.env + mezze.env (0600)"
else
    if [ ! -f "$MEZZE_ETC/secrets.env" ]; then
        umask 077
        { echo "MEZZE_DB_PASSWORD=$(gen_secret | tr -d '/+=' )"
          echo "MEZZE_ADMIN_PASSWD=$(gen_secret | tr -d '/+=' )"
        } > "$MEZZE_ETC/secrets.env"
        chmod 0600 "$MEZZE_ETC/secrets.env"
    fi
    if [ ! -f "$MEZZE_ETC/mezze.env" ]; then
        umask 077
        echo "MEZZE_MASTER_KEY=$(gen_secret)" > "$MEZZE_ETC/mezze.env"
        chmod 0600 "$MEZZE_ETC/mezze.env"
    fi
    chown "$MEZZE_SERVICE_USER":"$MEZZE_SERVICE_USER" "$MEZZE_ETC"/*.env
    load_secrets
fi
export MEZZE_DB_PASSWORD="${MEZZE_DB_PASSWORD:-__DRYRUN__}"
export MEZZE_ADMIN_PASSWD="${MEZZE_ADMIN_PASSWD:-__DRYRUN__}"

# ---- 5. PostgreSQL role ----
log "PostgreSQL role"
run "sudo -u postgres psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='$MEZZE_DB_USER'\" | grep -q 1 || sudo -u postgres psql -c \"CREATE ROLE $MEZZE_DB_USER LOGIN PASSWORD '\$MEZZE_DB_PASSWORD' CREATEDB\""

# ---- 6. render config + service + nginx + logrotate ----
log "rendering config/service/nginx/logrotate from templates"
run "render_template '$HERE/templates/odoo.conf.template'   '$MEZZE_ETC/odoo.conf'"
run "render_template '$HERE/templates/mezze-edge.service.template'   '/etc/systemd/system/mezze-edge.service'"
run "render_template '$HERE/templates/nginx.conf.template'  '/etc/nginx/sites-available/mezze-edge.conf'"
run "render_template '$HERE/templates/logrotate.template'   '/etc/logrotate.d/mezze-edge'"
run "render_template '$HERE/templates/backup.env.template'  '$MEZZE_ETC/backup.env'"
run "chmod 0640 '$MEZZE_ETC/odoo.conf' && chown '$MEZZE_SERVICE_USER':'$MEZZE_SERVICE_USER' '$MEZZE_ETC/odoo.conf'"
run "ln -sfn /etc/nginx/sites-available/mezze-edge.conf /etc/nginx/sites-enabled/mezze-edge.conf"

# ---- 7. HTTPS certificate (local CA path documented in HTTPS.md) ----
log "HTTPS certificate"
run "test -f '$MEZZE_CERT_PATH' || '$HERE/lib/make-cert.sh' '$MEZZE_HOSTNAME' '$MEZZE_ETC/tls' || true"

# ---- 8. database + module install (R-1 seeds the 101 catalog automatically) ----
log "database + mezze_bridge install (--without-demo=all)"
run "sudo -u '$MEZZE_SERVICE_USER' MEZZE_MASTER_KEY=\"\$MEZZE_MASTER_KEY\" '$MEZZE_PREFIX/venv/bin/python' '$MEZZE_PREFIX/odoo/odoo-bin' -c '$MEZZE_ETC/odoo.conf' -d '$MEZZE_DB_NAME' -i mezze_bridge --without-demo=all --stop-after-init"

# ---- 9. enable + start services ----
log "enabling services"
run "systemctl daemon-reload"
run "nginx -t"
run "systemctl enable --now postgresql nginx mezze-edge"

# ---- 10. validate ----
log "running Edge validator"
run "'$HERE/validate.sh' --db '$MEZZE_DB_NAME'"

log "install complete (dry_run=$DRY_RUN). Configure hardware next (see docs/sell-ready)."
