# S6 — Commercial Certification Matrix (PART 61)

For every feature at final signoff, mark each column. Statuses:
**SOFTWARE CERTIFIED / PHYSICAL CERTIFIED / EXTERNAL CERTIFIED / SUPPORTED BUT NOT
CERTIFIED / NOT INCLUDED**. Physical/External start as **PENDING** until the pilot
produces real evidence — never pre-fill them.

| Feature | Software | Physical | External | Notes |
|---|---|---|---|---|
| Counter cash sale | CERTIFIED (403/0/0) | PENDING | — | PART 11/20/31 |
| Dine-in table service | CERTIFIED | PENDING | — | PART 12/39/41 |
| KDS fire-once + recovery | CERTIFIED | PENDING | — | PART 13/14 |
| Table-QR ordering | CERTIFIED | PENDING | — | PART 18/19 |
| Two-phone concurrency | CERTIFIED | PENDING | — | PART 19 |
| Pickup self-order | CERTIFIED | PENDING | — | PART 20 |
| Delivery + COD + dispatch | CERTIFIED | PENDING | — | PART 21 |
| Kiosk (pay-at-counter) | CERTIFIED | PENDING (no kiosk ⇒ NOT CERTIFIED) | — | PART 22 — must not block non-kiosk sales |
| Cash payment | CERTIFIED | PENDING | — | PART 31/45 |
| Manual card (record) | CERTIFIED | PENDING | — | PART 31 |
| Mixed tender | CERTIFIED | PENDING | — | PART 31 |
| Refund / void / comp | CERTIFIED | PENDING | — | PART 42 |
| Receipt printing (EN/AR) | CERTIFIED | PENDING | — | PART 15/16 |
| Cash drawer | CERTIFIED | PENDING (N/A if not sold) | — | PART 17 |
| Integrated card terminal | CERTIFIED (S2C-3) | PENDING | PENDING per device | PART 33 — only the exact device/provider tested |
| Bank-app payment QR | CERTIFIED (S2C-4) | PENDING | Egypt/InstaPay NOT CERTIFIED | PART 65 |
| Online payment (Paymob) | CERTIFIED (S2C-5) | — | PENDING (sandbox+live) | PART 32 |
| Customer account / credit | CERTIFIED (S2C-6) | PENDING | — | cross-branch Edge NOT real-time |
| Automated cash machine (Glory/Cashdro/Cashmatic) | CERTIFIED orchestration | PENDING per device | PENDING | PART 34 — each device independently |
| Aggregators (Talabat/Careem/UrbanPiper) | SUPPORTED VIA ODOO | — | PENDING per channel | not required unless sold |
| Edge WAN-independent operation | CERTIFIED (probe/queue) | PENDING | — | PART 23–27 (the flagship Edge gate) |
| Support bundle (redacted) | CERTIFIED (leakage=0) | PENDING drill | — | PART 49/50 |
| Backup / restore | CERTIFIED (scripts, RTO≈14s) | PENDING live-shift | — | PART 7/47/48 |

**Rule:** an optional integration that is disabled and not sold to a customer does
**not** block that customer's Cloud/Edge Base launch (PART 59/60/64). But if Sales
advertises it, it must be certified first.
