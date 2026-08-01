# Mezze Edge — Connectivity Status Contract (S1.1A)

Three independent concepts, never collapsed into one `online` boolean.

## LOCAL SERVER — client-derived
The server never reports itself unavailable while answering. The frontend derives it:
- status RPC succeeds → **ONLINE**
- status RPC times out / network error → **UNAVAILABLE**

There is deliberately **no `local_server` field** in the backend response.

## WAN / INTERNET — backend-derived (`mezze.edge.connectivity`)
Probes multiple configurable HTTPS targets (`MEZZE_WAN_PROBE_URLS` env or
`mezze_bridge.wan_probe_urls` param), cached per worker (`mezze_bridge.wan_probe_interval`, default 20s;
timeout `wan_probe_timeout`, default 3s). Read-only probes (HEAD), no auth, no vendor lock-in.
- any target succeeds → **ONLINE**
- all configured targets fail → **OFFLINE**
- none configured / probe subsystem error → **UNKNOWN** (never coerced to OFFLINE)

Returns `checked_at` and `last_success_at`.

## EXTERNAL SERVICES — backend-derived from ACTUAL configured integrations
- none configured → **N/A**
- WAN OFFLINE → configured WAN-dependent services **PAUSED**
- WAN ONLINE + all healthy → **ONLINE**
- WAN ONLINE + a configured service unhealthy/misconfigured → **DEGRADED**
- WAN UNKNOWN → **UNKNOWN**

A third-party service is never marked healthy merely because the Internet works.

## Endpoint
`POST /mezze/api/v1/edge/status` — authenticated (terminal principal), **read-only**, no secrets. Contract:
```json
{ "ok": true, "deployment_mode": "edge|cloud",
  "wan": {"state":"online|offline|unknown","checked_at":"...","last_success_at":"..."},
  "external_services": {"state":"online|degraded|paused|n/a|unknown","services":{}} }
```

## Deployment mode
`MEZZE_DEPLOYMENT_MODE` (env) → `mezze_bridge.deployment_mode` (param) → default `cloud`. **Never** inferred
from hostname / db name / printer / path. The connectivity indicator shows only when mode is `edge`.

## Staff messaging
- WAN OFFLINE: "Internet unavailable. Local restaurant operations can continue. Internet-dependent services are temporarily paused."
- LOCAL UNAVAILABLE: "Local Mezze server is unavailable. Reconnect to the restaurant network or contact support." (never labelled "Internet offline")
- SERVICES DEGRADED: "Some external services are delayed. Local restaurant operations are unaffected."

## Capability enforcement
WAN status **must not** block fully-local operations (counter/dine-in/tables/reservations/waiter/KDS/
courses/cash/receipt/transfer/safe-merge/manager-approval/session). WAN-required operations fail fast with
a clear message or queue only where the existing outbox already supports safe replay — never a silent
success. `UNKNOWN` is not treated as `OFFLINE`.

## Local backup independence (§M)
Local backup is WAN-independent and is never marked failed because an off-site upload could not run;
off-site copy is a separate "waiting for WAN" state.
