# F1 — PRODUCTION SURFACE INVENTORY

**Branch** `design/v1-uiux-completion` · **Baseline** `2a8fcb6` · **Method** repo truth (routes/templates/assets)
cross-checked against a live authenticated run on the verification server (port 8088, DB `mezze_ui`).

Route truth: 172 `@http.route` declarations, of which **5 render a page**; every other route is JSON API
(`/mezze/api/v1/*`, `/mezze/sync/v1/*`, `/mezze/hardware/*`, aggregator, W1). Customer surfaces are static
assets under `/mezze_bridge/static/*.html`, reached by a **server-minted token link** — never by typing a URL.

## A. Staff / operations

| # | Surface | Route | Prod? | Role | Primary job | Form factor | Nav path in | AR | Dark | HC | Keyboard | Touch | Major debt |
|---|---------|-------|-------|------|-------------|-------------|-------------|----|------|----|----------|-------|-----------|
| 1 | **Register (cashier)** | `/mezze/pos` `auth=user` | YES | cashier | sell, tender, park/recall | 1024–1440 desktop/tablet | entry point; from Floor | YES | YES | YES | high | high | nav contrast (F3-N1), nav 36px |
| 2 | **Orders** | in-app phase of `/mezze/pos` | YES | cashier | open/parked/completed | as Register | Register nav | YES | YES | YES | high | high | not reachable from Floor |
| 3 | **Reservations / Waitlist** | in-app phase of `/mezze/pos` | YES | host | book, seat, waitlist | as Register | Register nav | YES | YES | YES | med | high | not reachable from Floor |
| 4 | **Payment** | in-app phase of `/mezze/pos` | YES | cashier | tender, split, terminal, QR | as Register | Charge | YES | YES | YES | high | high | — |
| 5 | **Table assign / transfer / merge** | dialogs in `/mezze/pos` + `/mezze/floor` | YES | waiter/host | seat + move covers | tablet | Floor tap, Register | YES | YES | YES | med | high | — |
| 6 | **Customer picker** | dialog in `/mezze/pos` | YES | cashier | attach partner / credit | as Register | Cart | YES | YES | YES | med | med | — |
| 7 | **Floor / tables** | `/mezze/floor` `auth=user` | YES | waiter/host | live table map | tablet/desktop | Register nav | YES | YES | YES | med | high | **no focus ring**, 2-of-4 nav, shell drift |
| 8 | **KDS** | `/mezze/kds` `auth=user` | YES | kitchen | fire → accept → ready | 1024–1440 display | **none — URL only** | YES | YES | YES | low | high | unreachable from product |
| 9 | **Coursing board** | `courses.html` (token) | YES | waiter | hold / fire courses | tablet | token link | partial | YES | YES | med | high | own radius vocabulary |
| 10 | **Drive-thru** | `drivethru.html` (token) | YES* | cashier | lane orders | tablet | token link | partial | YES | YES | med | high | *deliberately unsurfaced in pilot nav (release-manifest D-1) |
| 11 | **Onboarding / Go-Live** | `onboarding.html` (token) | YES | manager/admin | setup + readiness | desktop | token link | **BROKEN** | **NO** | **NO** | med | low | no theme registry, Arabic font typo |
| 12 | **Design prototype** | `/mezze/design/pos` | **NOT PRODUCTION** | — | visual reference (11 mock views) | — | — | — | — | — | — | — | reference only — excluded from all scoring |

## B. Customer

| # | Surface | Entry | Prod? | Job | Form factor | AR | Dark | HC | Touch | Major debt |
|---|---------|-------|-------|-----|-------------|----|------|----|-------|-----------|
| 13 | **Online shop** | `shop.html?store=<token>` | YES | browse, cart, pay | 360–430 phone first | YES | YES | YES | high | own radius vocabulary |
| 14 | **QR table ordering** | `qr.html?table=&qr=<token>` | YES | scan → order → bill | 360–430 phone | YES | YES | YES | high | own radius vocabulary |
| 15 | **Checkout / order status hub** | `/checkout/s/<status_token>` (QWeb) | YES | pay + track | 360–430 phone | YES | YES | YES | med | — |
| 16 | **Kiosk** | `kiosk.html` (device) | YES | self-order, pay at counter | 1080 portrait kiosk | **BROKEN** | **NO** | **NO** | high | no theme registry, Arabic font typo |
| 17 | **CFD (customer display)** | `cfd.html` (second screen) | YES | mirror cart | secondary display | YES | YES | YES | none | — |
| 18 | **Feedback / rating** | `feedback.html?store=&order=` | YES | rate order | 360–430 phone | YES | YES | YES | med | — |

## C. Counts

- **Production UI surfaces: 17** (11 staff incl. 3 in-app phases + dialogs, 6 customer) + **1 explicitly NOT PRODUCTION** (`/mezze/design/pos`).
- Distinct **rendered documents**: 3 Owl apps + 1 QWeb page + 8 static HTML = **12 documents**.
- Prototype-only destinations from the old export IA (Reports, Manager/Settings, HQ/branches, Live-Ops,
  Central Kitchen, Coffee queue) exist **only** inside `static/pos.html` → they are NOT production and must
  never appear in production navigation.

## D. Findings carried into later phases

| ID | Finding | Phase |
|----|---------|-------|
| **F1-1** | KDS has no navigation entry anywhere in the product — reachable only by typing `/mezze/kds` | F2/F3 |
| **F1-2** | Floor exposes 2 nav destinations, Register exposes 4 → nav is not stable between workspaces | F2/F3 |
| **F1-3** | `kiosk.html` + `onboarding.html` load neither `mezze-design.css` (theme registry) nor `data-appearance` → **no dark, no High Contrast** | F7 |
| **F1-4** | `kiosk.html:30` + `onboarding.html:20` request font family `'IBM Plex Arabic'`; the vendored `@font-face` is `'IBM Plex Sans Arabic'` → **Arabic falls back on both surfaces** | F5 |
| **F1-5** | Customer HTML surfaces each carry a local radius vocabulary (9–24px) outside the 8/11/14/16/pill scale | F9 |
