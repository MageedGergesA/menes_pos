# CURRENT PAGE INVENTORY (recalculated — NOT "11 pages")

Audit 2026-08-05. **Exact shipped surfaces = 9 static HTML + 1 Owl cashier app = 10.** Foundation =
`foundation.css`+`components.css` (all 9 HTML load it via `<link>`; the Owl cashier loads it via its bundle).

| Surface | Route / serving | Auth | Role | Prod/Proto | Foundation | mz-btn | mz-status | Arabic | Dark | HC theme | Browser evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Owl cashier** (`static/src/cashier/**`) | `/mezze/pos` (cashier.py:60) | user | staff | **PRODUCTION POS** | ✓ | ✓ (but 2nd drifted base) | own vocab (not `.mz-status`) | via engine | ✓ | ✓ | **NONE (auth; no browser test)** |
| pos.html | `/mezze/design/pos` (main.py:2448) | user | staff | **PROTOTYPE** | ✓ | ✓ 59 | ✓ 50 | ✓ full | ✓ | ✓ | manual this session |
| shop.html | `…/shop.html?store=` (main.py:2741) | public | customer | production | ✓ | ✓ 22 | ✓ 6 | partial | ✓ | ✓ | rendered (audit) |
| qr.html | `…/qr.html?table=&qr=` (main.py:2496) | public | customer | production | ✓ | ✓ 21 | ✗ | partial | ✓ | ✓ | — |
| cfd.html | customer display (main.py:4162) | public | customer | production | ✓ | 0 (no buttons) | ✗ | minimal | ✓ | ✓ | — |
| kiosk.html | direct static URL | public | customer | production | ✓ | ✓ 18 | ✗ | minimal | **✗ no engine** | **✗** | rendered (audit) |
| onboarding.html | direct static URL | public | admin | production | ✓ | ✓ 6 | ✓ 12 | minimal | **✗ no engine** | **✗** | rendered (audit) |
| drivethru.html | direct static URL | public | staff | debt (legacy `.btn`) | ✓ | ✗ legacy | ✗ | minimal | ✓ | ✓ | — |
| feedback.html | direct static URL | public | customer | debt (legacy `.btn`) | ✓ | ✗ legacy | ✗ | minimal | ✓ | ✓ | — |
| courses.html | direct static URL | public | staff/KDS | debt (legacy `.btn`) | ✓ | ✗ legacy | ✗ | minimal | ✓ | ✓ | — |

Key: (1) the SHIPPED cashier is the Owl app; pos.html is a prototype. (2) kiosk + onboarding load **no theme
engine** → no dark/HC. (3) drivethru/feedback/courses = design-debt trio (legacy buttons, no mz-status).
(4) Only pos.html + the Owl cashier have gated launcher routes; the rest are tokenized/direct static URLs.
