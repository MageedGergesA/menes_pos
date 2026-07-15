# Front-of-house — enabling the 3A features on a real catalog

The Wave-3A features layer onto **native Odoo** records + a few Mezze config
params — nothing here needs custom setup screens. This is the merchant's guide to
turning each one on with their own products. (`X` below = a branch's `pos.config`
id; params are per-branch so one store's setup never leaks to another.)

## Tips / gratuity
Native. Set **`pos.config.tip_product_id`** on the branch (a service product) — or
let Mezze find/create a `TIPS` product on first use. Tips post as a tax-free line
and reconcile through `pos.order.tip_amount` + `is_tipped`. No Mezze config.

## Combos / meal deals
Native **`product.combo`**. Create a product with `type = 'combo'` and attach one
or more `combo_ids` (each a group of `product.combo.item`s with an `extra_price`).
The bridge exposes it on the menu (`is_combo`) and reprices server-side using
Odoo's own proration, so the customer always pays combo price + chosen extras. Each
chosen item stays a real product line → **per-component food cost survives**.

## Comp (free item)
No product setup. A comp is a manager-approved 100%-off on an OPEN order line,
audited as its own `order.comp` event (tracked apart from discounts). Approval is
**required by default**; disable per-branch with:

    mezze_bridge.require_approval_comp = 0        # (any of 0/false/no/off)

## 86 — mark unavailable (per branch, live)
No product setup. Managers 86 an item from the POS (long-press → *86*); it greys
on every terminal instantly (Odoo bus) and the server blocks ordering it. It is a
**temporary stockout**, so it never touches the global `product.available_in_pos`
— the 86'd set is stored per branch:

    mezze_bridge.eightysix_<X> = [product_id, …]  # managed by the endpoint

## Quick keys — Favourites strip (per branch)
No product setup. Managers pin fast-movers from the POS (long-press → *Pin to
Favourites*); pinned ids live in an ordered per-branch list and surface as a
`★ Favorites` tab. Distinct from the AI *Suggested* strip (which is data-driven).

    mezze_bridge.quickkeys_<X> = [product_id, …]  # ordered; managed by the endpoint

## Half-and-half (split pizza)
Two conventions the merchant replicates on their own catalog — no code:

1. **The base** — one product with **`default_code = 'HALFHALF'`**, `list_price 0`,
   `standard_price 0`, no BoM, `available_in_pos`. The bridge flags it (`half_base`)
   and its tile opens the two-half picker.
2. **Eligible halves** — any products in a **POS category named "Pizza"** (the base
   itself excluded). These become the half options.

The parent line carries the charged price + tax; two child lines carry qty **0.5**
of the real pizzas at price 0, so each half books **half its BoM food cost**. The
kitchen gets ONE ticket, "½ A / ½ B". Pricing rule per branch (default = the
pricier half sets the price):

    mezze_bridge.halfhalf_pricing = max            # or: avg

A ready demo seed (Pizza category + 3 pizzas + the `HALFHALF` base) lives at
`demo/seed_pizza.py` — run it by hand against a demo DB (it is **not** manifest-
loaded, so it never installs onto a real merchant):

    ./odoo-bin shell -c <conf> -d <db> --no-http < addons/mezze_bridge/demo/seed_pizza.py

## Where these live in code
All six are in `controllers/main.py` (endpoints + the `_combo_apply` /
`_halfhalf_apply` grafters + the bootstrap flags) and `static/pos.html` (the
pickers + the long-press manager sheet). See `docs/FEATURE_MATRIX.md` for status.
