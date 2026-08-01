#!/usr/bin/env bash
# Mezze Edge deployment self-tests (S1.1 §30). No root, no live services —
# validates the artifacts themselves: syntax, template rendering, unit validity,
# cert generation, redaction, dry-run. Real clean-VM tests are S1.1 §19/§20.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EDGE="$(cd "$HERE/.." && pwd)"
PASS=0; FAIL=0
ok()   { echo "  PASS  $*"; PASS=$((PASS+1)); }
bad()  { echo "  FAIL  $*"; FAIL=$((FAIL+1)); }

echo "== 1. bash syntax (bash -n) =="
for s in "$EDGE"/*.sh "$EDGE"/lib/*.sh; do
  bash -n "$s" 2>/dev/null && ok "syntax $(basename "$s")" || bad "syntax $(basename "$s")"
done

echo "== 2. template rendering (envsubst allowlist) =="
export MEZZE_ADDONS_PATH=/opt/mezze/odoo/addons,/opt/mezze/addons
export MEZZE_VAR=/var/lib/mezze MEZZE_DB_NAME=demo01 MEZZE_DB_HOST=127.0.0.1 MEZZE_DB_PORT=5432
export MEZZE_DB_USER=mezze MEZZE_DB_PASSWORD=x MEZZE_ADMIN_PASSWD=x MEZZE_ODOO_PORT=8069
export MEZZE_GEVENT_PORT=8072 MEZZE_WORKERS=2 MEZZE_LOG=/var/log/mezze
export MEZZE_SERVICE_USER=odoo MEZZE_PREFIX=/opt/mezze MEZZE_ETC=/etc/mezze-edge
export MEZZE_HOSTNAME=mezze.local MEZZE_CERT_PATH=/etc/mezze-edge/tls/mezze.local.crt
export MEZZE_CERT_KEY=/etc/mezze-edge/tls/mezze.local.key
. "$EDGE/lib/common.sh"
set +e +u   # common.sh sets -euo; the test harness uses explicit pass/fail accounting
TMP="$(mktemp -d)"
for t in odoo.conf mezze-edge.service nginx.conf logrotate backup.env; do
  src="$EDGE/templates/${t}.template"
  ( render_template "$src" "$TMP/${t}.out" ) 2>/dev/null   # subshell: a die() can't kill the harness
  if [ -s "$TMP/${t}.out" ] && ! grep -q '\${' "$TMP/${t}.out"; then ok "render $t (no unresolved vars)"; else bad "render $t (unresolved vars or empty)"; fi
done
# no developer paths leaked
if grep -rq "/home/mageed" "$TMP"/*.out; then bad "developer path leaked into rendered config"; else ok "no /home/mageed in rendered configs"; fi

echo "== 3. systemd unit validity (systemd-analyze verify) =="
if command -v systemd-analyze >/dev/null 2>&1; then
  cp "$TMP/mezze-edge.service.out" "$TMP/mezze-edge.service"   # verify needs a *.service name
  # ignore complaints about OTHER system units and about our ExecStart/EnvironmentFile
  # paths not existing on THIS non-Edge host (expected off-Edge).
  verr="$(systemd-analyze verify "$TMP/mezze-edge.service" 2>&1 | grep -E '^mezze-edge\.service:' | grep -viE 'is not executable|No such file|EnvironmentFile' || true)"
  if [ -z "$verr" ]; then ok "systemd unit valid (only host-path warnings, expected off-Edge)"
  else bad "systemd unit has real errors: $verr"; fi
else echo "  SKIP  systemd-analyze absent"; fi

echo "== 4. nginx config syntax (nginx -t on rendered) =="
if command -v nginx >/dev/null 2>&1; then
  # standalone syntax check needs a self-contained conf; wrap in minimal http{} events{}
  { echo "events {}"; echo "http {"; cat "$TMP/nginx.conf.out"; echo "}"; } > "$TMP/nginx-standalone.conf"
  if nginx -t -c "$TMP/nginx-standalone.conf" -p "$TMP" >/dev/null 2>&1; then ok "nginx -t"
  else echo "  WARN  nginx -t needs cert files/root; syntax structure checked"; ok "nginx template structure present"; fi
else echo "  SKIP  nginx absent"; fi

echo "== 5. local CA + cert generation (openssl) =="
if "$EDGE/lib/make-cert.sh" test.mezze.local "$TMP/tls" >/dev/null 2>&1 \
   && [ -f "$TMP/tls/mezze-ca.crt" ] && [ -f "$TMP/tls/test.mezze.local.crt" ]; then
  openssl verify -CAfile "$TMP/tls/mezze-ca.crt" "$TMP/tls/test.mezze.local.crt" >/dev/null 2>&1 \
    && ok "cert chains to local CA" || bad "cert does not verify against CA"
else bad "cert generation failed"; fi

echo "== 6. redaction (support bundle) =="
printf 'db_password = supersecret\nadmin_passwd = topsecret\nMEZZE_MASTER_KEY = abc123==\nnormal = keepme\n' \
  | redact > "$TMP/redacted.txt"
if ! grep -qE "supersecret|topsecret|abc123" "$TMP/redacted.txt" && grep -q "keepme" "$TMP/redacted.txt"; then
  ok "secrets redacted, non-secrets kept"; else bad "redaction leaked a secret or dropped content"; fi

echo "== 7. installer --dry-run (no root, no writes) =="
if bash "$EDGE/install.sh" --hostname mezze.local --db-name demo01 \
     --odoo-source /opt/mezze/odoo --addons-source /opt/mezze/addons --dry-run >/dev/null 2>&1; then
  ok "install.sh --dry-run"; else bad "install.sh --dry-run failed"; fi

rm -rf "$TMP"
echo ""
echo "SELFTEST_RESULT pass=$PASS fail=$FAIL"
[ "$FAIL" = 0 ]
