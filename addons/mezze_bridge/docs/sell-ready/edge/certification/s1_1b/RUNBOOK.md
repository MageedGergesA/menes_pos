# S1.1B — Clean Host Certification Runbook

**Status: NOT EXECUTED here** (dev laptop: no root, disk 97%, no VM tooling). Execute on a **clean
Ubuntu Server 22.04 LTS host or VM** with sudo and ≥20 GB free. Certifies the code + deploy pack at the
commit under test (currently `4735030`, on top of RC3 `8ad8ed9`). Do **not** cut `mezze-edge-rc1` until
every gate below is PASS. Store outputs under the sibling evidence folders.

## 0. Prerequisites (record in `install-A/environment.txt`)
```bash
lsb_release -a; nproc; free -h; df -h /
sudo apt-get update
sudo apt-get install -y postgresql nginx python3-venv gettext-base openssl git
git clone <repo> /opt/mezze/src && cd /opt/mezze/src && git checkout 4735030
git rev-parse HEAD    # must equal the commit under test
```
Provide the Odoo 19 source at `/opt/mezze/odoo` and the addons at `/opt/mezze/src/addons` (or symlink).

## Gate A — Clean install #1  → `install-A/`
```bash
sudo MEZZE_DEPLOYMENT_MODE=edge MEZZE_WAN_PROBE_URLS=https://www.cloudflare.com,https://example.com \
  /opt/mezze/src/deploy/edge/install.sh \
  --hostname mezze.local --db-name restaurant01 --branch-name "Branch 1" \
  --odoo-source /opt/mezze/odoo --addons-source /opt/mezze/src/addons | tee install-A/install.log
```
**PASS:** installer exit 0; secrets in `/etc/mezze-edge/{secrets.env,mezze.env}` `0600`; DB `restaurant01`
created; `mezze_bridge` installed; catalog **101 (18/76/7)**:
```bash
sudo -u postgres psql restaurant01 -tAc "SELECT count(*) FROM mezze_setting_def"   # 101
/opt/mezze/src/deploy/edge/release-identity.sh --db restaurant01 | tee install-A/release-identity.txt
```

## Gate B — systemd live  → `systemd/`
```bash
systemctl is-enabled mezze-edge; systemctl status mezze-edge --no-pager | tee systemd/status.txt
sudo systemctl restart mezze-edge && sleep 5 && systemctl is-active mezze-edge   # active
sudo reboot    # then after boot:
systemctl is-active postgresql nginx mezze-edge | tee systemd/after-reboot.txt   # all active, no manual step
```
**PASS:** enabled + auto-starts after reboot; PG→Odoo→proxy come up unattended.

## Gate C — nginx live  → `nginx/`
```bash
sudo nginx -t | tee nginx/nginx-t.txt                 # syntax OK
curl -sI http://mezze.local/ | tee nginx/http-redirect.txt   # 301 -> https
```
**PASS:** `nginx -t` ok; HTTP→HTTPS redirect; db-manager routes return 404.

## Gate D — HTTPS live  → `https/`
```bash
# local-CA path (Option B): install.sh already generated the cert; export CA for clients
openssl s_client -connect mezze.local:443 -servername mezze.local </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -dates | tee https/cert.txt
curl --cacert /etc/mezze-edge/tls/mezze-ca.crt -sI https://mezze.local/web/login | tee https/https-login.txt  # 200
```
**PASS:** valid TLS; authenticated Odoo not served over plaintext; secure cookies set.

## Gate E — websocket live  → `websocket/`
```bash
# from a browser on the LAN, open the POS shell over https and confirm the bus connects;
# capture the /websocket 101 Switching Protocols in devtools/network -> websocket/ws-upgrade.png
```
**PASS:** `/websocket` upgrades (101); KDS/bus updates propagate over the proxy.

## Gate F — Edge validator 0 FAIL (excluding hardware/disk-host)  → `validator/`
```bash
sudo -u odoo MEZZE_MASTER_KEY=$(sudo grep MEZZE_MASTER_KEY /etc/mezze-edge/mezze.env|cut -d= -f2-) \
  /opt/mezze/src/deploy/edge/validate.sh --db restaurant01 | tee validator/edge-validator.txt
```
**PASS:** 0 FAIL (WAN offline = WARNING only; printer/drawer = NOT TESTED; the host disk check must be
green on a properly-sized host — the dev-laptop disk FAIL does not apply here).

## Gate G — Clean install #2 (repeatability)  → `install-B/`
Repeat Gate A on a **second** clean VM/snapshot with `--db-name restaurant02`. **PASS:** equivalent result,
101 catalog, no leaked state, no dev paths — proves determinism (deployment analogue of D-2).

## Gate H — Live upgrade  → `upgrade/`
```bash
# seed sample data, then upgrade to the next candidate commit:
sudo MEZZE_BACKUP_TS=$(date +%Y%m%d-%H%M%S) /opt/mezze/src/deploy/edge/upgrade.sh restaurant01 | tee upgrade/upgrade.log
```
**PASS:** mandatory backup taken first; `-u` clean; validator PASS post-upgrade; products/settings/orders/
payments/users/tables/config preserved; rollback = restore the pre-upgrade backup (proven 0-loss).

## Final  → `final/`
Consolidate all gate results. **Only if A–H all PASS**, cut the immutable candidate:
```bash
git tag -a mezze-edge-rc1 -m "Mezze Edge v1.0 hardware certification candidate 1"
```
Then S1.2 (physical hardware) may begin against `mezze-edge-rc1`. Never move RC1/RC2/RC3.
```
lost orders = 0 · duplicate orders = 0 · duplicate payments = 0 · unexplained financial diff = 0
```
