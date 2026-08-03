# Mezze POS — Go-Live Readiness & Commercial Profiles

Go-Live readiness is **validated, not self-declared**. The validator
(`mezze.golive.validator.run(profile)`) inspects the live configuration and returns
a structured report; the operator console (`/mezze_bridge/static/onboarding.html`)
and the API (`POST /mezze/api/v1/admin/golive`) surface it.

## Status policy (never softened)

| Status | Meaning | Blocks go-live? |
|---|---|---|
| **PASS** | capability configured and correct | no |
| **WARNING** | works but sub-optimal / dev-only setting | no (review) |
| **FAIL** | misconfiguration or a required capability missing | **yes** |
| **N/A** | capability not configured and not required by this profile | no |
| **NOT TESTED** | a host/hardware fact not inspectable from inside Odoo | no |

**Hard rule:** NOT TESTED is an honest "we cannot confirm this from software" —
it is **NEVER** converted to PASS by any profile, the UI, or a report. Physical
printers, drawers, NTP, nginx, and real payment devices stay NOT TESTED until the
S6 on-site pilot verifies them.

## Commercial profiles

A profile declares which capabilities a business **format** must have configured.
The same checks always run; the profile decides which are **required**. A required
capability that is only N/A (never configured) is upgraded to **FAIL** for that
profile — "you chose Delivery but configured no delivery zone" is a real block.

| Profile | Requires (must be PASS/WARNING) |
|---|---|
| `counter` | POS config, payment methods, cash journal, journals |
| `restaurant` | counter + menu catalog |
| `restaurant_qr` | restaurant + table-QR tokens |
| `delivery` | restaurant + delivery zone + COD cash method |
| `full` | restaurant + table-QR + delivery + COD + online providers |
| `edge` | (engineering) adds host/Postgres/proxy/WAN/disk checks |
| `golive` | (engineering) baseline: report all configured capabilities |

Pick the profile that matches what the branch is selling. Green for that profile =
that format is fully configured. The validator also flags two safety conditions
regardless of profile:

- `env_neutralized` → **FAIL** if the DB is neutralized but `env_profile=production`
  (a staging copy must not run as production).
- `demo_data_absent` → **FAIL** if the optional demo dataset is loaded in a
  production profile.

## Reading a report

```
POST /mezze/api/v1/admin/golive   { "token": "<admin>", "profile": "full" }
-> { ok, overall, fails, warnings, total, profile, profile_label,
     checks:[{name, status, detail, required}], profiles:[...] }
```

Resolve every FAIL before go-live. WARNINGs are reviewed and either fixed or
consciously accepted. NOT TESTED items are verified physically during the pilot.
