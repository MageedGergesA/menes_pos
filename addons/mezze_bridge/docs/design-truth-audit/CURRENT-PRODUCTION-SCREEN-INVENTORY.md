# CURRENT PRODUCTION SCREEN / SURFACE INVENTORY (recounted from code, HEAD 96a72e1)

**Only 3 controller-rendered HTML routes exist** (`request.render` across `controllers/*.py`); everything else is a raw static file or JSON/CSV/webhook.

| Route | Controller | Renders | Class | Auth | Browser-tested |
|---|---|---|---|---|---|
| `/mezze/pos` | `cashier.py:60` | Owl cashier `static/src/cashier/**` (`assets_cashier`) | **PRODUCTION-STAFF** | user | **YES** — `test_cashier_browser.py` (8) |
| `/mezze/kds` | `kds.py:63` | Owl KDS `static/src/kds/**` (`assets_kds`) | **PRODUCTION-STAFF** | user | **YES** — `test_kds_browser.py` (11) |
| `/checkout/s/<status_token>` | `checkout.py:224` | QWeb `checkout_status` (server-rendered, RTL/i18n) | **PRODUCTION-CUSTOMER** | public (token) | **NO** |

**9 raw static HTML files** (served at `/mezze_bridge/static/<name>.html`, wired to the JSON API; NO rendering controller of their own):

| File | Class | Wiring | Theme registry? | Browser-tested |
|---|---|---|---|---|
| `pos.html` (5016 ln) | **PROTOTYPE/REFERENCE** (self-labeled; `/mezze/design/pos` launcher) | real API | own @font-face + registry (proto) | NO |
| `shop.html` | PRODUCTION-CUSTOMER | link-minted (`main.py:2741`) | **YES** (bridged) | NO |
| `qr.html` | PRODUCTION-CUSTOMER | link-minted (`main.py:2496`) | **YES** (bridged) | NO |
| `kiosk.html` | PRODUCTION-CUSTOMER | raw static | **NO** (own lavender, mode-only) | NO |
| `cfd.html` | PRODUCTION-CUSTOMER (2nd screen) | raw static | **YES** (bridged) | NO |
| `feedback.html` | PRODUCTION-CUSTOMER | raw static | **YES** (bridged) | NO |
| `drivethru.html` | PRODUCTION-STAFF (operator board) | raw static | **YES** (bridged) | NO |
| `courses.html` | PRODUCTION-STAFF (waiter coursing) | raw static | **YES** (bridged) | NO |
| `onboarding.html` | ADMIN-TOOL (go-live console) | admin API | **NO** (own lavender, mode-only) | NO |

## Exact counts
- **Production-staff screens:** 2 hardened Owl (pos, kds) + 2 raw static (drivethru, courses) = **4** (or **2** if counting only controller-hardened Owl).
- **Production-customer screens:** 5 static (shop, qr, kiosk, cfd, feedback) + 1 rendered checkout hub = **6**.
- **Prototype/reference:** **1** (`pos.html`, internally containing 11 `data-view` mockups: pos/floor/ops/kds/bds/manager/reports/reservations/delivery/hq/ck).
- **Admin surfaces:** **1** (`onboarding.html`; backend Odoo `res.config.settings` excluded as BACKEND-ODOO-VIEW).
- **Browser-verified production surfaces: 2 / (12 production surfaces)** — only `/mezze/pos`, `/mezze/kds`. All customer surfaces + the checkout hub have ZERO executed browser evidence.

## Critical resolutions
- **Floor / Reservations / Delivery / Ops / Manager / BDS are NOT production screens.** They exist ONLY as `data-view` mockups inside prototype `pos.html:1421-1431` and as headless JSON endpoints in `main.py` (`/floors`, `/reservations/*`, `/delivery/*`, `/ops/summary`, `/manager/dashboard`, `/bds/queue`). No production Owl app renders them.
- **`/mezze/design/pos` = prototype** (explicit non-production launcher → `static/pos.html`).
- The export designed **6 staff workspaces** (Cashier, Table-Map/Floor, KDS, Reservations, CRM, Reporting). Production ships **2** (Cashier, KDS). The other 4 are prototype-only / unbuilt.

## Navigation / IA
The two Owl apps are **isolated islands**: `grep '/mezze/kds|/mezze/pos' static/src/` shows they never link to each other; the only `href` is `/web/login`. No production staff nav shell. The real 11-destination rail + role gating (`gateManager()`) exists ONLY in prototype `pos.html`. **IA verdict: MAJOR-RESTRUCTURE** (production has no cross-surface navigation).
