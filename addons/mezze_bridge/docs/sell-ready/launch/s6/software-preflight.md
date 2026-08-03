# S6 — Software Preflight Results (dev host)

These are the S6 gates that are **software-executable without physical hardware**,
run on a dev host against the certified release code. They are a *precondition*,
not a substitute for the physical pilot.

- **Release under test:** `mezze-v1.0-rc1` / `ad32f3ea533912e01cacaa92e3427f808ff1a92e`
- **DB:** `mezze_s5acc` (fresh `-i mezze_bridge --without-demo=all`, factory-empty)
- **Host:** developer environment (NOT the certified Cloud/Edge host)

| Gate | Check | Result |
|---|---|---|
| PART 1 | Release freeze — tree clean, `0 0`, HEAD==RC peeled==`ad32f3e` | **PASS** |
| PART 50 | Support-bundle secret scan — 5 synthetic secrets planted (token, password, Paymob key, HMAC, bearer); bundle regenerated | **PASS — leakage = 0**; bundle contains no orders |
| PART 46 | DB integrity: overpaid orders=0, orphan payments=0, orphan KDS=0, stuck outbox=0, dead-letter=0 | **PASS** (0 critical integrity defects) |
| PART 53 | Security-smoke (software): all `admin/*` endpoints present in both `authz.ENDPOINT_CAPABILITY` and `route_scope.ROUTE_SCOPE`; demo not loaded; not neutralized | **PASS** (route coverage intact) |
| PART 6 | Validator wiring — profiles `counter` / `full` / `edge` execute and return structured reports | **RUNS CORRECTLY** |

## Important nuance on PART 6

On this **factory-empty, unconfigured** DB the validator returns **FAIL** for
`counter` (3 fails), `full` (5 fails), and `edge` (4 fails). **This is the correct,
honest behavior** — no payment methods, journals, menu, zones, or production
hardening are configured, and `env_profile=development`. It demonstrates the
validator does not hand out a false PASS. In the physical pilot, each environment
must be **onboarded to zero blocking FAILs for its chosen commercial profile**
before the physical gates begin.

## Security-smoke facts observed (dev host)

| Fact | Value | Note |
|---|---|---|
| `env_profile` | development | production hardening is a **deploy-time** gate (PART 5/53) |
| `demo_loaded` | False | correct — demo never auto-loads |
| neutralized | False | correct for a live (non-staging) DB |
| `api_security` | observe | must be `enforce` in production (deploy-time) |
| `shared_token_disabled` | False | must be `True` in production (deploy-time) |
| route coverage | complete | authz == route_scope for all endpoints |

The `env_profile`/`api_security`/`shared_token` values above are **dev defaults**;
the production Cloud/Edge deploy (PART 5, PART 8) must set them to
production-hardened values, which the validator then checks.
