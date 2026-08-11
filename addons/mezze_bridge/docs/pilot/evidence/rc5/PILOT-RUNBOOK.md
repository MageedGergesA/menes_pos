# RC5 PILOT RUNBOOK

Operating instructions for the prepared RC5 pilot runtime. This runbook is for the
**RC5** candidate only; earlier runbooks describe earlier candidates and were not altered.

**Deploy exactly `mezze-v1.0-rc5` / `4b0feb1e4794134d57466bc17e6dc2ea5f4080b6`.**
Never the branch head, never `review/w2`, never `main`, never RC4. Branch drift
invalidates physical evidence.

---

## 1. Start / stop / restart

```bash
# start
nohup bash /home/mageed/odoo_work_19/mezze-rc5-pilot-runtime/start-pilot.sh \
      > /home/mageed/odoo_work_19/mezze-rc5-pilot-runtime/log/stdout.log 2>&1 &

# stop  (master pid; children follow)
kill "$(pgrep -f 'odoo-mezze-rc5-pilot.conf' | head -1)"

# endpoint
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/web/login   # expect 200
```

Endpoint for devices on the same Wi-Fi: **`http://192.168.8.181:8090`**

## 2. Verify you are running RC5 — do this before every shift

Do not trust the branch. Three checks must agree:

```bash
# 1. the checkout
git -C /home/mageed/odoo_work_19/mezze-rc5-pilot describe --tags --exact-match HEAD
#    expect: mezze-v1.0-rc5
git -C /home/mageed/odoo_work_19/mezze-rc5-pilot status --porcelain   # expect: empty

# 2. what the running application says about itself
#    (env['mezze.productization'].release_identity() via odoo shell)
#    expect git_commit 4b0feb1e4794134d57466bc17e6dc2ea5f4080b6, module_version 19.0.2.7.0

# 3. where the running process actually imported the module from
#    expect /home/mageed/odoo_work_19/mezze-rc5-pilot/addons/mezze_bridge/__init__.py
```

Note: the identity panel will display **product_version `1.0.0-rc.1`** — that string is
stale in RC5 (DEFECT-02). Trust `git_commit` and the tag, not the product-version string.

## 3. Pilot logins

Six accounts exist. Passwords are in
`mezze-rc5-pilot-runtime/conf/.pilot_credentials.json` (`0600`) — read them there, do not
copy them into notes or chat.

| Role | Login | Rights |
|---|---|---|
| Cashier | `pilot_cashier` | Internal User + POS User |
| Host | `pilot_host` | Internal User + POS User |
| Waiter / server | `pilot_waiter` | Internal User + POS User |
| Kitchen | `pilot_kitchen` | Internal User + POS User |
| Manager | `pilot_manager` | Internal User + POS User + **POS Manager** |
| Admin | `admin` | pre-existing administrator |

Real permission boundaries are in force: only the manager holds POS Manager, and **none of
the five pilot roles holds Settings/system access**. Run each scenario as its own role —
do not run the whole pilot as `admin`, or the pilot proves nothing about permissions.

## 4. Pilot data

Inherited from the configured `mezze_dev` restaurant and preserved intact by the upgrade:

* 1 company, 1 POS config, 1 floor, **12 tables**
* **15 POS products** in 4 categories (Arabic Coffee, Ayran, Fattoush, Hummus Beiruti,
  Jallab, Lamb Kofta, Manakish Cheese/Zaatar, Mint Lemonade, Mixed Grill, Muhammara,
  Shish Tawook…)
* 2 payment methods, 4 taxes, 5 partners

To reset between runs, restore the pilot database from a fresh backup (§6) rather than
hand-editing records.

## 5. Known behaviour to plan around

**One Register per POS config.** Opening the Register a second time on the same config
invalidates the first session's token and that device starts showing "Couldn't load …"
(DEFECT-01). If two staff devices are needed, give each its own POS config. Do not
misread this as a network fault.

## 6. Backups — gates 20 and 21

```bash
# pre-shift, immediately before the shift starts
odoo-bin db -c <pilot conf> --db_host=/var/run/postgresql -r odoo -w odoo \
        dump mezze_pilot_rc5 /home/.../mezze-rc5-pilot-backups/pre-shift-<ts>.zip

# post-shift, prove it restores into a THROWAWAY database, then drop that copy
odoo-bin db ... load mezze_pilot_restore_check <that file>
```

Never pass `--no-filestore`. Verify the archive contains `dump.sql`, `manifest.json` and
`filestore/` entries, record its SHA-256, and confirm every `store_fname` resolves on disk
before calling gate 21 passed.

## 7. WAN-outage procedure (gates 13–14) — prepared, not executed

The host reaches the Internet through `wlo1` → gateway `192.168.8.1`.

A **real** outage must break the uplink while leaving the restaurant LAN intact, so the
POS, KDS and devices can still see each other and the server. Do it at the router: disable
the WAN/PPPoE interface, or unplug the modem uplink — **not** by disabling Wi-Fi on the
host (that severs the LAN too and tests nothing) and **not** with the browser's offline
toggle (that simulates one tab, not the site).

Record: time offline, what each device showed, what queued, what reconciled on recovery,
and any duplicate or lost order.

## 8. Power-loss procedure (gates 17) — prepared, not executed

No UPS is present, so this cannot be run as intended today. When one exists:

1. announce the test; ensure a pre-shift backup exists (§6)
2. the **operator** physically cuts mains power to the server and one device
3. observe UPS hold-up, then let the UPS drain or shut down cleanly
4. restore power; start the pilot runtime (§1); verify identity (§2)
5. verify open orders, KDS tickets and cash state reconcile
6. record what was lost, what recovered, and how long recovery took

Do not cut power during preparation.

## 9. Receipt / drawer (gates 1–3) — configuration only

No printer or drawer is attached. Before these gates: attach the intended thermal printer,
confirm the Arabic code page or graphics-mode path prints Arabic correctly, set the paper
width, and configure the drawer kick through the printer. **Do not mark them passed until
paper actually emerges and the drawer actually opens.**

## 10. If something breaks mid-pilot

* **Environment/config problem** — fix the pilot environment and re-run the §2 identity
  checks before continuing.
* **Genuine RC5 product defect** — STOP. Do not edit the RC5 worktree. Record
  reproduction, logs, expected vs actual, and the affected gate in `DEFECTS.md`. Remediation
  is RC5 → minimal fix branch → regression → **RC6**, on operator authorisation.
  **Never move the RC5 tag.**
