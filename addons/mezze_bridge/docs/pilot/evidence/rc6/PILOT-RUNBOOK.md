# RC6 PILOT RUNBOOK

Operating instructions for the RC6 pilot runtime. Supersedes the RC5 runbook **as the
deployment target**; the RC5 document is left in place as history.

**Deploy exactly `mezze-v1.0-rc6` / `e85be35c31a3ae285494f68ecc67aaed493fd687`.**
Never a branch head — not `fix/rc6-pilot-defects`, not `evidence/rc6-pilot`, not
`design/v1-uiux-completion`, not `main`. Branch drift invalidates physical evidence.

---

## 1. Start / stop / restart

```bash
# start
nohup bash /home/mageed/odoo_work_19/mezze-rc6-pilot-runtime/start-rc6-pilot.sh \
      > /home/mageed/odoo_work_19/mezze-rc6-pilot-runtime/log/pilot-stdout.log 2>&1 &

# stop (master only; children follow)
kill "$(ps -eo pid,cmd | grep -F 'odoo-mezze-rc6-pilot.conf' | grep -v grep | awk 'NR==1{print $1}')"

# health
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/web/login    # expect 200
```

Endpoint for devices on the same Wi-Fi: **`http://192.168.8.181:8090`**

> When searching for the process, use `grep -F <pattern> | grep -v grep`. A pattern that
> also matches your own command line will make `kill` target your shell — that happened
> once during this deployment.

## 2. Verify you are on RC6 — before every shift

Three sources must agree; do not trust the branch:

```bash
git -C /home/mageed/odoo_work_19/mezze-rc6-pilot describe --tags --exact-match HEAD
#   expect: mezze-v1.0-rc6
git -C /home/mageed/odoo_work_19/mezze-rc6-pilot status --porcelain      # expect: empty

# what the running application says about itself
#   env['mezze.productization'].release_identity() via odoo shell
#   expect product_version 1.0.0-rc.6, git_commit e85be35c…, module_version 19.0.2.7.0

# where the process actually imported the module from
#   expect /home/mageed/odoo_work_19/mezze-rc6-pilot/addons/mezze_bridge/__init__.py
```

Unlike RC5, `product_version` is now correct — if it ever reads `1.0.0-rc.1` again you are
running RC5 or older.

## 3. Pilot logins

Six accounts. Passwords are in
`mezze-rc6-pilot-runtime/conf/.pilot_credentials.json` (`0600`) — read them there, never
copy them into notes or chat.

| Role | Login | Rights |
|---|---|---|
| Cashier | `pilot_cashier` | Internal User + POS User |
| Host | `pilot_host` | Internal User + POS User |
| Waiter / server | `pilot_waiter` | Internal User + POS User |
| Kitchen | `pilot_kitchen` | Internal User + POS User |
| Manager | `pilot_manager` | + **POS Manager** |
| Admin | `admin` | administrator |

Only the manager holds POS Manager; **none of the five pilot roles holds Settings/system
access**. Run each scenario as its own role — running everything as `admin` proves nothing
about permissions.

## 4. Pilot data

1 company · 1 POS config · 1 floor · **12 tables** · **15 POS products** in 4 categories
(Arabic Coffee, Ayran, Fattoush, Hummus Beiruti, Jallab, Lamb Kofta, Manakish
Cheese/Zaatar, Mint Lemonade, Mixed Grill, Muhammara, Shish Tawook…) · 2 payment methods ·
4 taxes · 10 partners · 526 attachments.

To reset between runs, restore from a backup rather than hand-editing records.

## 5. What changed for you since RC5

**Multiple devices on one POS config now work.** RC5's rule — "one Register per POS config"
— is withdrawn. Two staff devices can hold the Register and the Floor on the same config
simultaneously without knocking each other offline, proven on this runtime.

Two caveats worth knowing:

* **Two tabs in the same browser profile are one register** by design (the instance
  locator is a cookie). Different devices, or different browsers/profiles, are independent.
* **Every new browsing context creates a `mezze.terminal` row.** They are inert, least-
  privilege and revocable, but they accumulate — over a long pilot with many reconnects,
  expect the table to grow. There is no automatic pruning; clean up deliberately if needed.

## 6. Backups — gates 20 and 21

```bash
# pre-shift, immediately before the shift starts
odoo-bin db -c <rc6 conf> --db_host=/var/run/postgresql -r odoo -w odoo \
        dump mezze_pilot_rc6 /home/.../mezze-rc5-pilot-backups/pre-shift-<ts>.zip

# post-shift, restore into a THROWAWAY database, then drop that copy
odoo-bin db ... load mezze_pilot_restore_check <that file>
```

Never `--no-filestore`. Verify the zip carries `dump.sql`, `manifest.json` and
`filestore/` entries, record its SHA-256, and confirm every `store_fname` resolves on disk
before calling gate 21 passed.

## 7. WAN outage (gates 13–14) — prepared, not executed

Break the **uplink**, not the LAN: disable the WAN/PPPoE interface on the router at
`192.168.8.1`, or unplug the modem uplink. Do **not** disable Wi-Fi on the host (that
severs the LAN and tests nothing) and do **not** use the browser's offline toggle (one tab
is not the site). Record: time offline, what each device showed, what queued, what
reconciled, and any duplicate or lost order.

## 8. Power loss (gate 17) — prepared, not executed

No UPS is present, so this cannot run as intended today. When one exists: announce, ensure
a pre-shift backup, have the **operator** physically cut mains power, observe hold-up,
restore power, restart (§1), verify identity (§2), then check open orders, KDS tickets and
cash state reconcile. Never cut power during preparation.

## 9. Receipt / drawer (gates 1–3) — configuration only

No printer or drawer is attached. Attach the intended thermal printer, confirm the Arabic
code page or graphics path prints Arabic correctly, set paper width, and configure the
drawer kick through the printer. **Do not mark them passed until paper emerges and the
drawer opens.**

## 10. If something breaks mid-pilot

* **Environment/config** — fix the environment, re-run the §2 identity checks, continue.
* **Genuine RC6 product defect** — STOP. Do not edit the RC6 worktree. Record reproduction,
  logs, expected vs actual, and the affected gate. Remediation is RC6 → minimal fix branch
  → regression → **RC7**, on operator authorisation. **Never move the RC6 tag.**
* **Retreat to RC5** — see `ROLLBACK.md`. RC5 is fully preserved, but rolling back
  reinstates DEFECT-01.
