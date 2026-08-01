# Mezze Edge v1.0 — WAN Capability Matrix (S1 §9)

**Design/policy classification** of each feature's behavior when the branch **WAN (Internet) is
unavailable but the restaurant LAN and Edge server remain up**. This is the contract the WAN 2-hour
outage certification (§19) must verify on real hardware — it is **design intent until certified**, not a
test result. The Edge database is the authoritative branch DB, so LAN operations do not depend on WAN.

Legend: **Fully local** (works entirely on the branch, no WAN) · **Queued until WAN** (recorded locally,
outbound effect deferred) · **Temporarily unavailable** (needs WAN, disabled during outage with clear
status) · **Manual fallback** (staff procedure per runbook) · **Not supported Edge v1**.

| Feature | WAN-unavailable behavior | Classification |
|---|---|---|
| Counter order | Created + served on the Edge DB | Fully local |
| Dine-in order | Full lifecycle on Edge | Fully local |
| Reservation | Create/seat locally | Fully local |
| Waitlist | Local | Fully local |
| KDS | Local bus over LAN | Fully local |
| Table transfer | Local | Fully local |
| Table merge (safe, unpaid) | Local; paid-merge still blocked (409) | Fully local |
| Course hold/fire | Local | Fully local |
| Cash payment | Local | Fully local |
| Local terminal (LAN card reader) payment | Only if the reader is LAN-local and needs no WAN gateway | Fully local *if LAN-local*, else Temporarily unavailable |
| Receipt printing | LAN/USB printer | Fully local |
| Refund (cash / in-app engine) | Local | Fully local |
| Session open | Local | Fully local |
| Session close | Local | Fully local |
| QR ordering — on branch LAN (customer on restaurant Wi-Fi) | Reaches Edge over LAN — **conditional on §16 LAN-QR certification** | Fully local *(pending §16)* / else Not supported Edge v1 |
| QR ordering — public Internet (off-premise) | Requires WAN | Temporarily unavailable |
| Pickup (off-premise online) | Requires WAN | Temporarily unavailable |
| Delivery order intake (online) | Requires WAN | Temporarily unavailable |
| Delivery dispatch | Manual procedure (advanced routing deferred) | Manual fallback |
| Aggregator callbacks | Inbound from Internet — cannot arrive during outage; resume on reconnect | Temporarily unavailable → Queued (outbound status) on reconnect |
| Email | Needs WAN SMTP | Queued until WAN |
| SMS | Needs WAN gateway | Queued until WAN |
| Cloud/off-site backup upload | Needs WAN; **local backup still runs** | Queued until WAN |
| Remote support | Needs WAN | Temporarily unavailable |
| HQ dashboard / cloud rollup | Needs WAN | Temporarily unavailable (Edge v1 has no cloud sync) |
| External online payment gateway | Needs WAN | Temporarily unavailable |
| Online card checkout | Not built | Not supported Edge v1 (S2) |
| Drive-thru | Gated (D-1) | Not supported Edge v1 |
| True split-by-seat | Not modelled | Not supported Edge v1 |

## Invariants the outage + reconnect certification must prove (§19–20)
On reconnect: lost orders = 0 · duplicate orders = 0 · duplicate payments = 0 · duplicate KDS items = 0 ·
incorrect table states = 0 · unexplained financial difference = 0. Queued outbound (email/SMS/offsite
backup/aggregator status) retries idempotently; no duplicate business event.

> **Marketing boundary (§33):** claims may not exceed this matrix. Allowed: "core restaurant operations
> keep running on the branch LAN when the Internet is down." Forbidden: "everything works offline."
