# Mezze POS — Admin Guide

The Admin Console is where you configure the business, manage people, read the
audit trail, and confirm what build is running. Every admin action is server-gated
and audited.

## Roles

Human administrative access is scoped. Cashier/staff records carry a role
(`cashier` / `manager` / `admin` / `auditor`); admin-console access is further
scoped server-side into these effective roles:

| Role | Can do |
|---|---|
| **org_admin** | Full configuration across the organisation: companies, branches, settings, people, payment devices. |
| **store_manager** | Manage a store/branch's operations and settings within their scope. |
| **role_manager** | Manage staff and their PIN/role assignments. |
| **auditor** | **Read-only** — reads admin/settings/compliance/finance/reports and exports the audit log; writes are refused server-side. |

Give each person the narrowest role that lets them do their job. Auditors can see
everything relevant for compliance but cannot change anything.

## Settings & the admin console

Settings are governed by a catalog of documented setting definitions (each keyed,
with a `working` / `disabled` / `hidden` status). The console groups them into
categories; the go-live validator checks the catalog is intact so a fresh install
that failed to seed is caught, not silently shipped.

## Audit log + export

Every sensitive action (refund, void, comp, discount, credit approval, config
change, break-glass access) writes an immutable audit line: who, what, when,
terminal, amount, and a redacted detail. Export it from the admin API:

```
POST /mezze/api/v1/admin/audit/export   { "event": "<optional filter>", "limit": 500 }
```

The export returns audit **metadata only** — never order contents or customer PII —
and detail fields are redaction-filtered. Use it for reconciliation and compliance
reviews. See `PRIVACY-DATA.md` for retention.

## Release / version identity

Confirm exactly what is deployed:

```
POST /mezze/api/v1/admin/version
```

returns product version, edition (Mezze Cloud / Mezze Edge), deployment mode,
module version, Odoo version, git commit, release channel (`stable`/`rc`/`dev`),
and build id. On Edge you can also get the same identity from the host without a
running server via `deploy/edge/release-identity.sh`. Production sites run the
`stable` channel; `dev` must never be on a customer site.

## Staging vs production

Run a **staging** copy for testing and training and keep it clearly separated from
production. The environment profile (`mezze_bridge.env_profile`) is `development` or
`production`; production turns on the hardening the go-live validator enforces
(shared-admin token disabled, master key present, API security enforced, HTTPS
base URL, no demo data).

## Neutralization for staging

When you clone production to make a staging copy, **neutralize** it
(`data/neutralize.sql`) so it can never fire real outbound side effects (payments,
webhooks, emails). A neutralized database reports `is_neutralized()` true, and the
validator will **FAIL** any database that is both `production` and neutralized —
a staging copy must never masquerade as production. Keep staging on the
`development` profile.
