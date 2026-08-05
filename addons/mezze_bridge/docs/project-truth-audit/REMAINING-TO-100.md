# REMAINING TO 100% (prioritized backlog — remaining work only)

Audit 2026-08-05, HEAD `5ec05b1`. Blocks: Cloud / Edge / Both / Neither. Scope: SMALL/MEDIUM/LARGE. No time estimates.

## P0 — SELL BLOCKERS
| Item | Current evidence | What must be done | Scope | Blocks |
|---|---|---|---|---|
| Edge physical certification | 0% executed; module's own report = "NOT SELL-READY" | Run S1.2/S6 on a clean Ubuntu 24.04 host: install→autostart→nginx→HTTPS→printer→drawer→tablet→KDS→WAN-cut(5/30/120m)→reboot→backup/restore→shift UAT | LARGE | Edge |
| Live PSP certification (if selling online payments) | Paymob wired, **never executed**; only Demo proven | Execute a real Paymob sandbox→live transaction incl. refund; capture evidence; certify per-country | MEDIUM | Cloud (online-pay) |
| Managed hosting rehearsal (Cloud) | not evidenced | Stand up Odoo.sh/self-host, HTTPS, `web.base.url=https`, bus/websocket live; smoke the customer pages | MEDIUM | Cloud |
| Executed browser/UAT of customer + cashier UI | **zero** browser tests; manual prototype-only | Add HttpCase.browser_js/tour for the Owl cashier + a staff UAT of the real POS loop | MEDIUM | Both |

## P1 — REQUIRED BEFORE GENERAL SALE
| Item | Evidence | Do | Scope | Blocks |
|---|---|---|---|---|
| Object-scope wiring for non-money Category-A routes | "wiring pending" (route_scope.py:149) | gate-wire target records for the remaining Category-A routes | MEDIUM | Both |
| At least one real aggregator partner | HMAC/idempotency tested; per-partner payload shim = TODO | implement + certify one partner (payload normalize + outbound status) | MEDIUM | Cloud |
| Wallet acquirer driver | `mezze.payment.transaction` driver = TODO stub | wire or remove the acquirer registry (avoid dead/overlapping payment abstraction) | SMALL | Neither (hygiene) |
| Doc reconciliation | stale 403 / 22.04 / rc1-pin / "no HC" (STALE-DOCS) | single-source count/version/OS; retract wrong claims | SMALL | Neither |

## DESIGN POLISH (P3 continuation — none are sell-blockers)
| Item | Evidence | Do | Scope |
|---|---|---|---|
| P3A finish | 3 legacy button pages + cashier `.mz-btn` drift | migrate drivethru/feedback/courses to `.mz-btn`; reconcile cashier button base | MEDIUM |
| P3B finish | prototype-migrated; cashier + 2 conn palettes + catalog chips remain; `.mz-badge` unadopted | migrate production Owl cashier status to canonical; kill legacy conn palettes | MEDIUM |
| kiosk + onboarding theme engine | no mezze-design.css / engine → no dark/HC | load the registry so they get dark + HC | SMALL |
| P3C–P3I families | NOT STARTED | Alerts/Inputs/Quantity/Dialogs/Cards/Empty-Loading/Tabs | LARGE (7 families) |
| prefers-contrast / forced-colors | NO | add OS-contrast a11y support | MEDIUM |

## EXTERNAL / PHYSICAL CERTIFICATION (tracked separately — see PHYSICAL-CERTIFICATION-TRUTH)
Real terminals, cash machines, printers, drawers, tablets, KDS hardware, WAN outage, staff shift — all NOT EXECUTED.

## NOTE
Core POS + payments (cash/manual/mixed/customer-account) + delivery + security + productization are
software-complete and server-tested — they are NOT on this list except for the specific gaps above.
