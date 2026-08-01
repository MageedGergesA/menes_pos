# Mezze Edge v1.0 — Product Definition

## Editions
- **Mezze Cloud** — central cloud-hosted Odoo/PostgreSQL; requires WAN for server access. POS/browser
  clients tolerate *temporary* connectivity blips, but Cloud is **not** marketed as indefinitely offline.
- **Mezze Edge** — standalone per-branch deployment. Odoo 19 + PostgreSQL run on a local Edge server on
  the restaurant LAN. **WAN is optional for local branch operation.** The local Edge database is the
  authoritative database for that branch.

```
Waiter tablets · Cashier · KDS · Manager · Printer · Cash drawer · Customer display
        │  (restaurant LAN)
        ▼
   Edge server  →  Odoo 19 + PostgreSQL  (authoritative branch DB)
```

## Explicit v1 boundary
Mezze Edge v1.0 **MUST NOT** claim real-time bidirectional cloud synchronization. During WAN outage the
LAN stays operational; Internet-dependent services are unavailable or queued — see
`wan-capability-matrix.md`. Out of Edge v1 scope: online card checkout (S2), drive-thru (D-1), true
split-by-seat, advanced delivery routing, cloud↔edge bidirectional sync, cloud HQ rollup.

## WAN status model (§8) — design
Clients must show **three distinct signals**, never one vague "Offline":
```
Local server       ONLINE | UNAVAILABLE
Internet (WAN)     ONLINE | OFFLINE
External services  ONLINE | PAUSED/WAITING   (aggregator, cloud backup, online payment, email/SMS)
```
Rules: WAN loss must **not** be shown as local-server loss (§21 distinguishes them). If the Edge server is
down, show `LOCAL SERVER UNAVAILABLE`; if only WAN is down, show `Internet OFFLINE` with local `ONLINE`.
*(Status-model UI is a production-code item; when built it lands in an Edge release, not RC3.)*

## Network architecture (§5) — certified topology
```
Internet/WAN → Router → Restaurant LAN ─┬─ Edge server (Ethernet, static/DHCP-reserved IP)
                                        ├─ Receipt printer (Ethernet where possible)
                                        ├─ Cashier (Ethernet where possible)
                                        ├─ KDS (Ethernet/Wi-Fi)
                                        └─ Waiter tablets (operations Wi-Fi SSID)
```
Requirements to record per install: server static IP, printer IP, gateway, local DNS/hostname, ops SSID,
subnet, firewall rules, internal ports (Odoo HTTP, gevent/websocket, PostgreSQL local-only). **No Internet
DNS dependency for local branch operation.**

## HTTPS (§6) — strategy
Edge runs Odoo behind a reverse proxy (nginx) terminating TLS on the LAN. Supported cert options: an
internally-managed certificate or a local CA trusted on branch devices (a public-domain cert only where a
real domain is available). Proxy must: set Odoo `proxy_mode = True`, proxy the gevent/websocket path,
redirect HTTP→HTTPS, and set secure cookies. Authenticated Odoo sessions must not traverse untrusted
plaintext. The Edge validator (§25) checks `proxy_mode` + HTTPS base URL.

## Marketing claims (§33) — allowed only if certified
- ✅ "Mezze Edge keeps core restaurant operations running on the local branch network when Internet
  connectivity is unavailable."
- ❌ "Everything works offline." — forbidden. Always list exactly which capabilities require Internet
  (see `wan-capability-matrix.md`). No claim may exceed the certified matrix. Until the §19 2-hour outage
  is certified on real hardware, the offline claim is **design intent, not a certified claim**.
