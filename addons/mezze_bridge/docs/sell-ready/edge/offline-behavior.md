# Mezze Edge — Four Distinct Outage Types (S1 §32)

Sell-ready documentation must never conflate these. They have different causes, symptoms, and staff actions.

| Outage | What is down | What still works | Staff signal | Action |
|---|---|---|---|---|
| **WAN outage** | Internet only | **All local branch operations** (orders, KDS, cash, receipts, refunds, sessions) on the Edge LAN | `Internet OFFLINE` · `Local server ONLINE` | Keep serving; Internet-dependent services queue/pause (see wan-capability-matrix.md) |
| **LAN outage** | Restaurant network path between clients and Edge | Edge DB intact; a client off the LAN can't reach it | Client shows `LOCAL SERVER UNAVAILABLE` (not "Internet offline") | Restore Wi-Fi/switch/cabling; clients reconnect, authoritative state returns |
| **Edge server outage** | The Edge server (Odoo/PG) itself | Nothing until it restarts | All clients `LOCAL SERVER UNAVAILABLE` | Restart Edge server; systemd auto-recovery (PG→Odoo→proxy); state returns |
| **Power outage** | Whole stack loses power | Nothing until power/UPS restores | Devices dark | UPS gives clean-shutdown runtime; on power-on the stack auto-starts and PostgreSQL recovers crash-safely |

**Key sell-ready message:** a **WAN outage is not a local-server outage.** Mezze Edge is designed so the
branch keeps operating on the LAN through a WAN outage; LAN/server/power outages are separate failure modes
with their own recovery. Each of the above rows is **design intent until certified** by the §19/§21/§22
on-hardware tests.
