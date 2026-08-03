# Mezze POS — Support Bundle & Diagnostics

One call gives support everything needed to diagnose a site **without DB
archaeology**, and it is **secret- and PII-safe by construction**.

## Getting a bundle

- **Operator console:** `/mezze_bridge/static/onboarding.html` → *Generate bundle*.
- **API:** `POST /mezze/api/v1/admin/support_bundle { token, profile }` (admin-gated).
- **Edge host (no running app):** `deploy/edge/support-bundle.sh` → one `tar.gz`
  (adds journald/systemctl/nginx facts the app can't see).

## What it contains

| Section | Content |
|---|---|
| `release` | product/module/Odoo version, git commit, edition, deployment mode, channel, neutralized flag |
| `deployment` | mode, neutralized, base URL, DB name |
| `validator` | full go-live report for the profile (checks + statuses) |
| `config_summary` | safe operational params + record **counts** (never contents) |
| `log_tail` | last 200 log lines, redacted (or a note if logging to stdout/journal) |

## What it NEVER contains

- No database dump.
- No orders, customers, or PII rows.
- No credentials, secrets, tokens, API keys, or private keys.

## Redaction (leakage = 0)

Every text field passes through `domain/redaction.redact()` / `redact_json()`
before it leaves the process. Redacted patterns include: passwords, `db_password`,
`admin_passwd`, `MEZZE_MASTER_KEY`, any `*secret*` / `*token*` / `api_key` / `*hmac*`
/ `private_key` / Paymob key, `Authorization` / bearer headers, PEM private keys,
and PII (PAN → redacted, CVV/PIN, customer email). `redact_json` additionally blanks
any value whose **key name** denotes a secret, so structured data can't leak a bare
token that carries no inline `key=` context. The property is covered by a test
(`TestRedaction`, `TestSupportBundle`) that plants synthetic secrets and asserts
none survive.

## Audit export

`POST /mezze/api/v1/admin/audit/export { token, event?, limit }` returns the full
audit trail (metadata only, redacted `detail`) — bounded and admin-gated. Use it to
reconstruct who did what without opening the DB.
