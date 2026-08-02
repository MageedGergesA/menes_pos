# Live Cashier Migration — S2C-1

The production cashier is a **standalone Odoo 19 Owl application** served by the
`mezze_bridge` addon. It replaces the demo/mock behaviour of `static/pos.html`
for real transactions. `pos.html` is retained as a **design reference only**
(non-transactional) and is NOT reachable from the production route.

## 1. Frontend audit — `static/pos.html` (253 KB single-file prototype)

| Aspect | Classification | Action |
|---|---|---|
| Terracotta "Classic" palette, `--mz-*` tokens, themes/modes/accents (`mezze-design.css`) | DESIGN TO PRESERVE / REUSABLE CSS | Reuse token names + values in the Owl bundle |
| Fonts (Hanken Grotesk, IBM Plex Arabic, Material Symbols) in `static/fonts/` | REUSABLE ASSET | `@font-face` in cashier bundle → `/mezze_bridge/static/fonts/*` |
| Product grid / cart / payment / receipt layout | DESIGN TO PRESERVE | Rebuilt as real Owl components, same visual language |
| `demoMode: true`, mock restaurant arrays, `MezzeDesign` globals | MOCK DATA/STATE TO REMOVE | Not carried into production; app never fabricates data |
| "Bridge offline — demo data" banner | MOCK STATE TO REMOVE | Replaced by real connectivity + explicit error states |
| Cart-add / payment dialogs (non-functional) | REAL COMPONENT TO BUILD | Built and wired to backend contracts |

## 2. Backend contract audit (reused, not duplicated)

| Need | Route | Status |
|---|---|---|
| Authenticated bootstrap: config, currency, categories, products, 86, payment methods | `POST /mezze/api/v1/bootstrap` | EXISTS — **small extension**: add `is_cash_count` to the payment-method projection so the cash method is discoverable without hardcoded IDs |
| Create draft order (server-authoritative totals) | `POST /mezze/api/v1/orders/sync` | EXISTS (idempotent by client `uuid`) |
| Take payment (financial path) | `POST /mezze/api/v1/orders/pay` | EXISTS — remains the only money path |
| Payment breakdown (receipt) | `POST /mezze/api/v1/payment/breakdown` | EXISTS |
| Connectivity (local/wan/external) | `GET /mezze/api/v1/edge/status` | EXISTS |

No new financial/order endpoints were created.

## 3. Authentication (canonical, not invented)

- Page route `GET /mezze/pos` is `auth='user'` → the cashier authenticates with
  **Odoo's own session**. Not logged in ⇒ Odoo redirects to `/web/login`; that is
  the real *authentication-required* state (never demo data).
- The render controller mints a **least-privilege per-terminal token**
  (`mezze.terminal`, `role='terminal'` → capability set includes `orders.pay`;
  branch-scoped) and injects it into the page for the JSON API. No shared-admin
  token is exposed to the browser; no new bearer architecture is introduced.

## 4. No production demo fallback

The Owl app has **no mock catalog**. On auth/catalog/config/network failure it
shows an explicit production state (`Authentication required`, `Unable to load
menu`, `POS is not ready for sales`, `Local Mezze server unavailable`) — it never
silently populates a fake restaurant. `AUTH FAILURE ≠ DEMO MODE`.

## 5. Price authority

The browser is never the financial source of truth. The cart shows an *estimated*
line total for UX; the authoritative amount is (re)computed by `/orders/sync`
server-side and shown on the payment screen. `/orders/pay` charges the server's
`amount_total`; cash `tendered`/`change` are display-only (payment amount = amount
due, never the tendered value).

## 6. Prototype disposition

`static/pos.html` stays in the tree, marked **DESIGN PROTOTYPE — NON-TRANSACTIONAL**,
for visual parity reference. It is not served by `/mezze/pos`. Archival happens
after Owl parity is complete.
