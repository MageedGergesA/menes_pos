#!/usr/bin/env bash
# Mezze Edge local-CA HTTPS helper (S1.1 §9). Generates a local CA + server cert
# for an isolated LAN deployment. Export the CA to trust on tablets/workstations.
#   make-cert.sh <hostname> <out-dir>
set -euo pipefail
HOST="${1:?hostname required}"; OUT="${2:?out-dir required}"
mkdir -p "$OUT"; cd "$OUT"; umask 077
if [ ! -f mezze-ca.key ]; then
    openssl genrsa -out mezze-ca.key 4096
    openssl req -x509 -new -nodes -key mezze-ca.key -sha256 -days 3650 \
        -subj "/O=Mezze Edge/CN=Mezze Edge Local CA" -out mezze-ca.crt
fi
openssl genrsa -out "${HOST}.key" 2048
openssl req -new -key "${HOST}.key" -subj "/O=Mezze Edge/CN=${HOST}" -out "${HOST}.csr"
cat > "${HOST}.ext" <<EXT
subjectAltName=DNS:${HOST}
extendedKeyUsage=serverAuth
EXT
openssl x509 -req -in "${HOST}.csr" -CA mezze-ca.crt -CAkey mezze-ca.key -CAcreateserial \
    -out "${HOST}.crt" -days 825 -sha256 -extfile "${HOST}.ext"
chmod 0600 ./*.key
echo "server cert: $OUT/${HOST}.crt"
echo "CA to install on client devices: $OUT/mezze-ca.crt (manual trust — see HTTPS.md)"
