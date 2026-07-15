# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Demo seed — pizzas + a Half-&-Half base, so the half-and-half feature is
demoable out of the box.

This is a MANUAL demo seed, NOT wired into the manifest: `mezze_bridge` is a
generic POS bridge, so pizzas must never be force-installed on a real merchant.
Run it by hand against a demo database.

    ./odoo-bin shell -c <conf> -d <db> --no-http < \
        addons/mezze_bridge/demo/seed_pizza.py

Idempotent: re-running it updates the same records instead of duplicating them.
Portable: it copies its taxes from an existing menu product (so it matches
whatever Service/VAT the demo already uses) rather than hard-coding tax ids.
"""


def seed_pizzas(env):
    Category = env['pos.category']
    Template = env['product.template']

    # --- taxes: reuse whatever an existing menu product already carries, so the
    #     pizzas book the same Service + VAT as the rest of the demo (portable
    #     across DBs — no hard-coded tax ids). Fall back to all sale taxes.
    sample = Template.search(
        [('available_in_pos', '=', True), ('taxes_id', '!=', False),
         ('type', '!=', 'combo')], limit=1)
    taxes = sample.taxes_id if sample else env['account.tax'].search(
        [('type_tax_use', '=', 'sale')], limit=2)
    tax_cmd = [(6, 0, taxes.ids)]

    # --- Pizza POS category (find-or-create) ---
    category = Category.search([('name', '=', 'Pizza')], limit=1)
    if not category:
        category = Category.create({'name': 'Pizza'})

    # --- the pizzas: (name, sale price, food cost) ---
    pizzas = [
        ('Margherita Pizza', 80.0, 28.0),
        ('Pepperoni Pizza', 110.0, 42.0),
        ('Veggie Pizza', 95.0, 33.0),
    ]
    created, updated = [], []
    for name, price, cost in pizzas:
        tmpl = Template.search([('name', '=', name)], limit=1)
        vals = {
            'name': name, 'type': 'consu', 'available_in_pos': True,
            'list_price': price, 'standard_price': cost,
            'taxes_id': tax_cmd, 'pos_categ_ids': [(6, 0, [category.id])],
        }
        if tmpl:
            tmpl.write(vals)
            updated.append(name)
        else:
            Template.create(vals)
            created.append(name)

    # --- the Half-&-Half base: price/cost 0 (children carry both), flagged by
    #     default_code so the bridge can recognise it and drive the picker ---
    base = Template.search([('default_code', '=', 'HALFHALF')], limit=1)
    base_vals = {
        'name': 'Half & Half Pizza', 'default_code': 'HALFHALF', 'type': 'consu',
        'available_in_pos': True, 'list_price': 0.0, 'standard_price': 0.0,
        'taxes_id': tax_cmd, 'pos_categ_ids': [(6, 0, [category.id])],
    }
    if base:
        base.write(base_vals)
        updated.append('Half & Half Pizza')
    else:
        Template.create(base_vals)
        created.append('Half & Half Pizza')

    env.cr.commit()
    print("[seed_pizza] category 'Pizza' id=%s | taxes=%s"
          % (category.id, taxes.mapped('name')))
    if created:
        print("[seed_pizza] created: %s" % ', '.join(created))
    if updated:
        print("[seed_pizza] updated: %s" % ', '.join(updated))
    print("[seed_pizza] done — reload the POS; the ½+½ tile appears under Pizza.")


# When piped into `odoo-bin shell`, `env` is already in scope.
if 'env' in globals():
    seed_pizzas(env)  # noqa: F821
