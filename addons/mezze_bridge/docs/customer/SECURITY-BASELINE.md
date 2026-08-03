# Mezze POS — Production Security Baseline

A production checklist. The go-live validator enforces most of these in the
`production` environment profile — a **Fail** here blocks launch. Work top to bottom
before you go live.

| # | Control | Requirement | Enforced by |
|---|---|---|---|
| 1 | **Master key** | `MEZZE_MASTER_KEY` set **in the environment only** (never in code, config files, or git). | Validator `master_key_present` = FAIL if missing |
| 2 | **Shared-admin token** | The shared-admin machine token is **disabled** in production (`mezze_bridge.shared_token_disabled = true`); only a scoped, time-boxed emergency break-glass may admit it. | Validator `shared_admin_disabled` = FAIL if not disabled |
| 3 | **API security** | `mezze_bridge.api_security = enforce` (not `observe`). | Validator `api_security_enforced` = WARN if not enforced |
| 4 | **HTTPS base URL** | `web.base.url` is `https://…`, not localhost/127.0.0.1. | Validator `base_url` / `edge_https_base_url` |
| 5 | **Environment profile** | `mezze_bridge.env_profile = production` on production; staging stays `development` and **neutralized**. | Validator `env_profile`, `env_neutralized` |
| 6 | **No demo data** | Demo dataset never loaded on production (`mezze_bridge.demo_loaded` unset). | Validator `demo_data_absent` = FAIL if present in production |
| 7 | **No default logins** | No `admin/admin`; every admin and staff member has a personal account/PIN. Remove or disable default/shared accounts. | Operational |
| 8 | **DB manager secured** | Odoo's database-manager screen is protected (strong `admin_passwd`) or disabled; never publicly reachable. | Host/deploy config |
| 9 | **Secrets never in git** | Keys, tokens, provider credentials, QR signing secret live in the environment / secrets store — never committed. | Operational + review |
| 10 | **Simulators off** | Payment TEST simulators (terminal / cash machine) are **never** enabled in production. | Validator `terminal_simulator_not_production`, `cash_machine_simulator_absent` |
| 11 | **Release channel** | Production runs `stable`; never `dev` on a customer site. | `mezze_bridge.release_channel` |
| 12 | **Neutralize staging clones** | Any clone of production is neutralized (`data/neutralize.sql`) so it cannot fire real payments/webhooks/emails. | Validator (production + neutralized = FAIL) |

## How to verify

Run the go-live validator with your commercial profile:

```
POST /mezze/api/v1/admin/golive   { "profile": "full" }   # or counter/restaurant/...
```

Resolve every **Fail** in the security gate before launch. **NOT TESTED** host facts
(nginx, NTP, autostart, backup recency, physical devices) are confirmed on the Edge
host during the pilot — they are honest, not skipped.

## Edge specifics

- Run behind nginx with `proxy_mode` on and `workers >= 1`.
- Keep NTP/chrony in sync (timestamps and tokens depend on it).
- Confirm backups are recent and test-restored (see `BACKUP-RESTORE.md`).
