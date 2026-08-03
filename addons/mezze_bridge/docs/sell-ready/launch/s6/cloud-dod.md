# S6 — Definition of Done: Mezze Cloud Base (PART 62)

Cloud is **COMMERCIAL GO** only when every mandatory row is **PASS** with real
evidence for the selected Cloud commercial profile. Optional disabled integrations
do not block.

| # | Gate | PART | Result |
|---|---|---|---|
| 1 | Certified RC identity (runtime == ad32f3e) | 1 | PENDING |
| 2 | Real hosted deployment (not localhost) | 5 | PENDING |
| 3 | Clean install `-i --without-demo=all` | 6 | PENDING |
| 4 | Go-Live validator: 0 blocking FAIL for profile | 6 | PENDING |
| 5 | HTTPS + secure DB manager + no admin/admin | 5/53 | PENDING |
| 6 | Cashier device (auth→sale→close, EN/AR) | 11 | PENDING |
| 7 | Waiter/tablet (real device) | 12 | PENDING |
| 8 | KDS (independent display, fire-once) | 13/14 | PENDING |
| 9 | Receipt printer (real print, EN+AR) | 15/16 | PENDING |
| 10 | Table-QR (printed QR, tamper reject) | 18 | PENDING |
| 11 | Two-phone concurrency | 19 | PENDING |
| 12 | Pickup (if sold) | 20 | PENDING |
| 13 | Delivery (if sold) | 21 | PENDING |
| 14 | Payments matrix (cash/manual/mixed/refund) | 31/42 | PENDING |
| 15 | Arabic full-shift smoke | 55 | PENDING |
| 16 | Staff UAT (real roles) | 35/36 | PENDING |
| 17 | Full service shift (≥4h) | 37 | PENDING |
| 18 | Session close (production flow) | 43 | PENDING |
| 19 | **Financial reconciliation difference = 0** | 44 | PENDING |
| 20 | DB integrity after shift | 46 | PENDING |
| 21 | Backup | 47 | PENDING |
| 22 | Restore + RTO | 48 | PENDING |
| 23 | Support drill (no creds) | 49 | PENDING |
| 24 | Support-bundle secret scan (leakage=0) | 50 | **PASS (software, dev host)** |
| 25 | Security smoke | 53 | PARTIAL (software PASS; deploy-time HTTPS/hardening PENDING) |
| 26 | No Critical defects | 56 | PENDING |
| 27 | No unresolved financial Major | 56 | PENDING |

**Cloud Base readiness = 100%** only when rows 1–27 PASS on the real hosted profile.
