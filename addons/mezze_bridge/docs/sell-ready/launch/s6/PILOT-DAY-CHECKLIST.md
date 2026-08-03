# MEZZE PILOT DAY — ONE-PAGE CHEAT SHEET

Release `mezze-v1.0-rc1` · commit `ad32f3e…` · Date ________ · Lead ________

> Full detail is in `FIELD-RUNBOOK.md`. This page is the day-of sequence for the team lead.

```
RELEASE
  ☐ runtime /admin/version.git_commit == ad32f3e   (STOP if not)
  ☐ product 1.0.0-rc.1 · module 19.0.2.0.0 · channel rc

DEVICES
  ☐ cashier · tablet · KDS (separate) · printer · drawer(if sold)
  ☐ router · phone A · phone B · UPS(edge) · staff present
  ☐ hardware-inventory.md filled

OPENING
  ☐ deploy exact RC (Cloud and/or Edge A + B)
  ☐ onboarding → validator 0 blocking FAIL for the profile
  ☐ HTTPS · DB manager secured · demo off · debug hidden

CORE SMOKE
  ☐ cashier: sale, cash, card, mixed, refund, reprint (console 0 errors)
  ☐ tablet: order + transfer + Arabic + reconnect (real device)
  ☐ KDS: each channel appears ONCE

CUSTOMER FLOWS
  ☐ table QR (printed) + tamper reject
  ☐ two-phone concurrency
  ☐ pickup · delivery COD + collection

FAILURE TESTS
  ☐ KDS disconnect → converge (0 lost / 0 dup)
  ☐ printer disconnect → no financial rollback → reprint
  ☐ local server down ≠ internet down (no demo fallback)
  ☐ worker kill (if >1)

WAN TESTS (EDGE)
  ☐ WAN 5m · ☐ WAN 30m · ☐ WAN 2h (flagship)
  ☐ reconnect: outbox converges, 0 dup callbacks/orders/payments
  ☐ UPS / power

SHIFT (≥4h)
  ☐ 30+ counter · 15+ dine-in · 10+ QR · 5+ pickup · 5+ delivery
  ☐ 86 · transfer · safe merge · paid-merge BLOCK · courses · approval · refund

CLOSE
  ☐ session close via UI (no SQL)

RECONCILE  ⛔ HARD GATE
  ☐ unexplained financial difference = 0   (else COMMERCIAL FAIL)
  ☐ cash physical count reconciled

BACKUP / RESTORE
  ☐ backup (duration/size) · ☐ restore to clean target (0 loss, RTO)

SUPPORT / SECURITY
  ☐ support drill (no creds) · ☐ support-bundle secrets = 0 · ☐ security checklist

SIGNOFF
  ☐ per-profile GO/CONDITIONAL/NO-GO
  ☐ Technical · Operations · Finance · Restaurant Manager (named + signed)
```

**STOP the pilot** for: wrong money · duplicate charge/payment · lost paid/kitchen
order · data corruption · unauthorized access · unrecoverable DB · unexplained
financial difference. Log CRITICAL in `defects/`, escalate.

**Never** move `mezze-v1.0-rc1`. Code fix → new `mezze-v1.0-rc2` (see runbook).
