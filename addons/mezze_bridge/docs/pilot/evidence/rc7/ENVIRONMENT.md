# RC7 — Pilot environment

| | |
|---|---|
| Host | single Linux workstation (kernel 6.8), Odoo 19.0 |
| Canonical pilot | `http://<host>:8090` (gevent 8091), bound `0.0.0.0` |
| Shadow (retained) | `http://<host>:8092` (gevent 8093) |
| Host LAN address | `192.168.8.181` |
| Exposure | **LAN HTTP only** — no TLS listener, `proxy_mode = False` |
| Reverse proxy | nginx is running on the host but listens on **:80 only** and does not front the pilot |
| Workers | 4 + gevent + 2 cron |
| data_dir | `~/.local/share/Odoo` |
| Disk | **99% full, ~4.2 GB free** — sufficient for this deployment, but worth reclaiming before the physical pilot |

## Secure context

There is **no HTTPS**. Browser features gated on a secure context — camera / QR
scanning, service workers, geolocation, some clipboard APIs — are unavailable to any
origin other than `localhost`. A customer phone on the LAN reaching `http://192.168.8.181:8090`
is **not** a secure context.

**This is a deployment/network blocker for the customer-phone gates, not an RC7 product
defect.** Closing it needs TLS (a certificate plus `proxy_mode = True` behind a
terminating proxy), which is a hosting decision and was not performed here.

## Other services on the host (untouched by this deployment)

`:8071` mezze_dev · `:8077` bft_ui · `:8210` fidelity dev runtime · `:80` nginx
