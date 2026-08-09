# CP12 — Device / Hardware Matrix

Software support = proven by CP1–CP12 software tests. **Physical Test Status is PENDING PHYSICAL
until a real device supplies evidence — never "CERTIFIED" from a software test.**

| Device | Expected profile | Software support | Physical test | Evidence | Blocker? | Notes |
|---|---|---|---|---|---|---|
| Cashier workstation | Chrome/Chromium, cashier app `/mezze/pos` | PASS (Owl app mounts, HOOT+browser tests) | PENDING PHYSICAL | none | — | Fresh-install browser smoke passes headless |
| Server tablet | Chrome, floor/register/host | PASS (headless browser tests) | PENDING PHYSICAL | none | — | Touch targets ≥44px in CSS |
| KDS screen | Chrome, `/mezze/kds` | PASS (KDS store HOOT tests) | PENDING PHYSICAL | none | — | Idempotent fire proven in software |
| Receipt printer | ESC/POS / configured | SOFTWARE READY (print/receipt route + hw job model) | PENDING PHYSICAL | none | — | Paper/Arabic appearance NOT certified |
| Cash drawer | kick via printer/driver | SOFTWARE READY (drawer/open, audited) | PENDING PHYSICAL | none | — | Physical kick NOT certified |
| Payment terminal | integrated (S2C-3) | SOFTWARE READY (terminal orchestration) | PENDING PHYSICAL | none | — | Device cert = provider work |
| Customer phone | mobile browser (QR/pickup/status) | PASS (public routes + status token) | PENDING PHYSICAL | none | — | Real device layout NOT certified |
| Router / network | LAN + WAN | SOFTWARE FAILURE-INJECTION only | PENDING PHYSICAL | none | — | Real WAN/LAN cut NOT certified |
| UPS / power | mains + battery | N/A (software) | PENDING PHYSICAL | none | — | Power-loss NOT certified |
