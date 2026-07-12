# Mezze Bridge API (`mezze_bridge`)

Backend bridge for the **Mezze POS platform**. It exposes **our own versioned
JSON HTTP API** (`/mezze/api/v1/`) so an external Mezze frontend can:

1. **Bootstrap** catalog + config (products, taxes, payment methods, categories)
   and get an **open POS session**, and
2. **Sync orders** into a real Odoo DB.

Orders are written through Odoo's **own `point_of_sale` machinery**, so real
`stock` moves happen and, on session close, real `account` journal entries post.

```
  Mezze frontend  ──HTTP JSON──►  mezze_bridge (/mezze/api/v1/)  ──►  Odoo core
   (never ORM-RPC)                 our versioned API                pos.load.mixin  (read)
                                                                    pos.order.sync_from_ui (write)
                                                                    pos.session close (accounting)
```

**The frontend NEVER touches Odoo ORM-RPC / JSON-RPC.** It only speaks this API.

## Architecture — the two reused seams

* **Read (`bootstrap`)** — curated `search_read` over the same field lists the
  `pos.load.mixin` uses. We return a *lean* projection (only what Mezze needs)
  rather than the full `load_data` payload, which is a large interdependent blob
  keyed by model and tied to the full session/UI context.
* **Write (`orders/sync`)** — builds the exact order dict that
  `pos.order.sync_from_ui` expects (shape mirrors
  `point_of_sale/tests/common.py::create_ui_order_data`) and calls it. Odoo
  computes/validates the order, creates the paid `pos.order`, and generates stock
  moves. **We do not reinvent order creation or the session close.**
* **Idempotency** — piggybacks on the native `pos.order.uuid`. `sync_from_ui`
  upserts by uuid; if an order with that uuid already exists we return it and do
  **not** duplicate. A `mezze.sync.log` row is written for every attempt (audit).

## v19 gotchas handled

* `@route(type='json')` is a **deprecated alias for `type='jsonrpc'`** in 19.0
  (JSON-RPC 2.0 envelope in/out). For a clean REST-JSON contract (bare body in,
  bare JSON out, curl/fetch friendly) we use the **new `type='json2'`**
  dispatcher. `/health` stays on `type='http'`.
* **CORS preflight `Access-Control-Allow-Headers` is hard-coded** by the
  framework and does **not** include `X-Mezze-Token`. A browser cross-origin call
  carrying that custom header is blocked at preflight. So the token is accepted
  from **either** the `X-Mezze-Token` header (curl path) **or** a `token` field in
  the JSON body / query string (browser path — see `test_client.html`).
* No `name_get`, no `attrs=`, no `groups_id` used. Security uses `group_id` refs
  in `ir.model.access.csv`.

`json2` routes require the request `Content-Type: application/json`.

---

## Install

1. Add the parent `addons` dir to `addons_path` (keep the addon out of the core
   tree):

   ```
   addons_path = /home/mageed/odoo_work_19/odoo/addons,/home/mageed/odoo_work_19/mezze/addons
   ```

2. Install / upgrade the module:

   ```bash
   ./odoo-bin -d YOUR_DB --addons-path=/home/mageed/odoo_work_19/odoo/addons,/home/mageed/odoo_work_19/mezze/addons -i mezze_bridge --stop-after-init
   # later changes:
   ./odoo-bin -d YOUR_DB -u mezze_bridge --stop-after-init
   ```

Depends on `point_of_sale`, `stock`, `account`. Make sure a **Point of Sale** is
configured (a `pos.config` with a sales journal, payment methods, and a warehouse
so pickings/accounting resolve).

## Set the API token

The API is guarded by a shared token stored in `ir.config_parameter`
`mezze_bridge.api_token`. Set it via `odoo shell`:

```bash
./odoo-bin shell -d YOUR_DB --addons-path=/home/mageed/odoo_work_19/odoo/addons,/home/mageed/odoo_work_19/mezze/addons <<'PY'
env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'CHANGE_ME_secret_token')
# optional: pin the internal user the API acts as (defaults to Mitchell Admin)
# env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_user_id', '2')
env.cr.commit()
PY
```

Or from the UI: **Settings → Technical → System Parameters → New**, key
`mezze_bridge.api_token`.

---

## Test with curl

Set shell vars (token must match what you stored):

```bash
BASE=http://localhost:8069
TOKEN=CHANGE_ME_secret_token
```

### 1. Health (no auth) — connectivity

```bash
curl -s $BASE/mezze/api/v1/health
# {"ok": true, "odoo": "19.0", "module": "mezze_bridge"}
```

### 2. Bootstrap — catalog + open session

```bash
curl -s -X POST $BASE/mezze/api/v1/bootstrap \
  -H "Content-Type: application/json" \
  -H "X-Mezze-Token: $TOKEN" \
  -d '{}'
```

Response (abridged):

```json
{
  "ok": true,
  "session_id": 3,
  "config": {"id": 1, "name": "Shop", "currency_id": 1, "company_id": 1, "pricelist_id": 1},
  "payment_methods": [{"id": 1, "name": "Cash"}, {"id": 2, "name": "Bank"}],
  "taxes": [{"id": 1, "name": "15%", "amount": 15.0}],
  "categories": [{"id": 1, "name": "Food"}],
  "products": [{"id": 5, "name": "Hummus", "list_price": 20.0, "barcode": false,
                "taxes_id": [1], "pos_categ_ids": [1], "uom_id": [1, "Units"]}]
}
```

Grab a `session_id`, a `products[].id`, and a `payment_methods[].id` for the next
call.

### 3. Sync an order (idempotent by `uuid`)

```bash
curl -s -X POST $BASE/mezze/api/v1/orders/sync \
  -H "Content-Type: application/json" \
  -H "X-Mezze-Token: $TOKEN" \
  -d '{
    "uuid": "mezze-demo-0001",
    "session_id": 3,
    "lines": [
      {"product_id": 5, "qty": 2, "price_unit": 20.0},
      {"product_id": 6, "qty": 1}
    ],
    "payments": [
      {"payment_method_id": 1, "amount": 40.0}
    ]
  }'
```

Response:

```json
{"ok": true, "duplicate": false, "order_id": 12,
 "pos_reference": "Order 00003-001-0001", "uuid": "mezze-demo-0001",
 "amount_total": 40.0, "amount_paid": 40.0, "synced_records": 1}
```

Re-run the **exact same** command → `"duplicate": true`, same `order_id`, no new
order (idempotency proven). Note: server recomputes taxes/subtotals — client
totals are never trusted. Omit `price_unit` to price from the pricelist; omit
`tax_ids` to use the product's taxes mapped through the fiscal position.

### 4. Close the session — post accounting

```bash
curl -s -X POST $BASE/mezze/api/v1/sessions/3/close \
  -H "Content-Type: application/json" \
  -H "X-Mezze-Token: $TOKEN" \
  -d '{}'
```

Response:

```json
{"ok": true, "session": "POS/00003", "session_id": 3, "state": "closed",
 "account_move_ids": [88], "account_move_names": ["POS/2026/07/0003"],
 "balance": 0.0}
```

## Verify in the Odoo UI

* **Order**: Point of Sale → Orders → Orders. The order appears with the
  `pos_reference` above, state *Paid* (then *Posted/Done* after close).
* **Stock move**: open the order → *Shipment* / stat button, or Inventory →
  Operations → Transfers filtered by the order reference. With
  *update stock at closing* the picking is created at session close.
* **Journal entry**: Accounting → Journal Entries → find the move name(s) from
  the close response (`account_move_names`). Debits/credits balance to 0.

## Endpoints

| Method | Path | Auth |
|--------|------|------|
| GET  | `/mezze/api/v1/health` | none |
| POST | `/mezze/api/v1/bootstrap` | token |
| POST | `/mezze/api/v1/orders/sync` | token |
| POST | `/mezze/api/v1/sessions/<int:session_id>/close` | token |

## Click-test page

Open `test_client.html` in a browser (double-click / `file://`, or serve it).
Enter the base URL + token, hit **Bootstrap** to load real products as tiles,
build a cart, pick a payment method, and **Send order**. It posts the token in
the JSON body (not a custom header) to sidestep the CORS preflight limitation.
