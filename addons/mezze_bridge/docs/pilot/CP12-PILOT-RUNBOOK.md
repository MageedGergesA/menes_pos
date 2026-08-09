# CP12 — Mezze Pilot & Go-Live Field Runbook

Executable runbook for a **controlled real-world pilot** of the cumulative R2 build.
It complements (does not replace) the existing `docs/go-live/`, `docs/sell-ready/launch/s6/`
and `docs/customer/BACKUP-RESTORE.md` material — reuse those for depth.

> **Status of this build:** working tree on branch `review/w2`, module `19.0.2.7.0`,
> **uncommitted / no release tag**. This runbook authorises a **physical pilot**, not
> commercial certification. See `SOFTWARE-PREFLIGHT-RESULT.md` for the executed software gates.

Each physical step below records **Expected / Observed / PASS-FAIL / Evidence ref / Operator /
Timestamp**. Do **not** pre-fill Observed — the field team fills it live. Use the templates in
`evidence/`.

## 0. Software preflight gate (must be GREEN before travelling to site)
Run the read-only preflight against the pilot database:
```
odoo-bin shell -c <conf> --addons-path=...,.../mezze/addons -d <PILOT_DB> --no-http \
    < docs/pilot/mezze_preflight.py | tee evidence/preflight.out
grep -q 'PREFLIGHT_RESULT: GO' evidence/preflight.out    # exit 0 == GO
```
Expected: `CONFIG overall: PASS` (for the branch's profile) **and** `INTEGRITY overall: PASS`.
A `BLOCKED` here means the branch config is incomplete — fix config, do not travel.

## 1. Pre-pilot freeze
- Confirm module version + branch + HEAD (`/admin/version`).  Expected: matches the agreed build.
- Confirm `env_profile=production`, `api_security=enforce`, `shared_token_disabled=true`,
  `signing_mode.*=enforce`, `neutralized=false`, `demo_loaded=false`.  (Validator `full`/branch profile PASS.)
- Confirm `MEZZE_MASTER_KEY` is set in the service environment (validator `master_key_present` PASS).

## 2. Environment inventory  → `evidence/environment.md`
Odoo 19.0, Python 3.12, PostgreSQL ≥14, worker count, proxy (nginx), bus/gevent port,
filestore path, backup target, SSL/domain. Record actual values.

## 3. Hardware inventory  → `evidence/hardware.md` + `HARDWARE-MATRIX.md`
Cashier workstation, server tablet, KDS screen, receipt printer, cash drawer, payment terminal,
customer phone, router, UPS. Record model + firmware.

## 4. User / role accounts
Create `host`, `server/waiter`, `cashier`, `kitchen`, `manager` cashiers (PIN). Verify least
privilege: a `cashier` cannot refund/void/comp; a `host` cannot pay/refund. Expected: enforced server-side.

## 5. Opening shift
Open the POS session; start the cashier app (`/mezze/pos`). Expected: Register loads, no console errors.

## 6. Counter sale — cash
Add items → Charge → cash → receipt. Expected: paid; receipt prints (physical). Drawer opens (physical).

## 7. Table sale
Floor → tap free table → Register bound to table → add items → Send → guests set. Expected: floor shows occupied.

## 8. Reservation / waitlist
Reservations → create/confirm/arrive → **Seat** to a table → Register opens the seated order.
Add a walk-in → Notify → Seat. Expected: exactly one order per seat; no duplicate.

## 9. Kitchen send / ready / serve
KDS receives the fired ticket → mark preparing/ready/served. Expected: ticket appears once; no duplicate on retry.

## 10. Transfer / merge
Register → Move table → transfer to a free table; merge into an occupied one. Expected: money-bearing
merge blocked with a human message; no lost/duplicated lines.

## 11. Partial / mixed payment
Take a partial cash tender, then complete with card. Expected: remaining reflects paid; table releases on full pay.

## 12. Refund / void (only if the operator role is authorised)
Manager refund/void a line/order. Expected: capability-gated; audit recorded. **Do not test with a cashier PIN.**

## 13. Pickup / QR / delivery order (customer channels)
Pickup via storefront; QR at a table; delivery with a serviceable address. Expected: each becomes ONE
canonical order; server prices; 86'd item rejected at checkout; delivery zone/fee server-authoritative.

## 14. Printer / drawer test (PHYSICAL)
Print a receipt; open the drawer. Expected: legible receipt (incl. Arabic), drawer opens. → PENDING PHYSICAL.

## 15. Network interruption (PHYSICAL WAN cut)
Pull WAN briefly during operation. Expected: clear offline state, no silent order loss, converge on reconnect.
Software failure-injection is proven separately; a real WAN cut is PENDING PHYSICAL.

## 16. App / browser restart
Reload the cashier / floor / orders / reservations tabs. Expected: authoritative state reconstructs (server truth).

## 17. Server restart
Restart the Odoo service mid-shift. Expected: open orders, table occupancy, guest counts, KDS, payments all
persist (PostgreSQL-backed). *(Software-proven in `SOFTWARE-PREFLIGHT-RESULT.md`.)*

## 18. Power / UPS test (PHYSICAL)
Cut mains; run on UPS; graceful behavior. → PENDING PHYSICAL.

## 19. Closing shift
Close the POS session. Expected: session closes; expected vs counted cash captured.

## 20. Financial reconciliation  → `evidence/financial-reconciliation.md`
Reconcile gross orders, payments by tender, refunds, expected cash, session total. Any variance must be
**explained**. Unexplained variance = pilot BLOCKER. *(Software deterministic-shift reconciliation proven.)*

## 21. Backup  → `evidence/backup-restore.md`
Back up **BOTH** the PostgreSQL database **and the filestore** (`<data_dir>/filestore/<DB>`).
> ⚠ A DB-only backup is INSUFFICIENT — compiled cashier assets live in the filestore; a DB-only
> restore leaves the cashier unbootable. Record method, size, duration, exit code.

## 22. Restore
Restore DB + filestore into a spare DB name; start Odoo; run the preflight; open the cashier.
Expected: counts match; `INTEGRITY overall: PASS`; cashier boots.

## 23. Evidence capture
Screenshots / photos / logs per step into `evidence/`. No fabricated results.

## 24. Defect severity
CRITICAL (duplicate charge, lost sale, financial corruption, cross-tenant leak, cannot sell, wrong total/tax,
unauthorised money action) · MAJOR (core workflow blocked w/ workaround, KDS miss, seat duplicate, cannot close
session, restore unusable) · MINOR (cosmetic / low-frequency). Log in `evidence/defects.md`.

## 25. Stop / Go decision  → `evidence/go-no-go.md`
GO only with **0 unresolved CRITICAL**, an accepted MAJOR list, and all mandatory physical steps PASS.
