# Multi-Device & Tablet Acceptance (P1 §13–14)
**Multi-device (separate cashier + KDS + manager clients):** PROVEN via live **2-worker** execution
(`--workers=2`, 3 worker children) driving concurrent HTTP clients with DB assertions
(tests/concurrency: r11_run.sh, o1, mw_replay, p52_race, double_pay_race). Seat→fire→pay→merge→aggregator
each resolve to exactly one logical operation across workers (idempotent). Role boundaries
(host/server/cashier/kitchen/manager) enforced and tested.
**Physical tablet (1024×768, 100%/120%, Arabic RTL):** the CI host is hi-DPI and `resize_window` no-ops
(frames stuck ~1568px), so a true tablet viewport is **not forceable here**. Responsive CSS + RTL are present in the assets.
**Classification:** multi-client concurrency = Pilot supported (proven). Physical-tablet viewport = Pilot supported with on-site verification (must re-verify on the pilot tablet before launch).
