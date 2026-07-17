# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Demo seed — a few promotions/coupons so the promo engine is demoable.

Creates native ``loyalty.program`` records the bridge's promo engine reads:
  - an AUTOMATIC promotion:      spend 200, get 25 off the order
  - a DISCOUNT CODE (reusable):  WELCOME10 -> 10% off
  - a single-use COUPON:         code SAVE15X -> 15% off (one use)

A real merchant creates these in Odoo's Loyalty UI; this just seeds demo data.
Idempotent by program name / coupon code. Run by hand:

    ./odoo-bin shell -c <conf> -d <db> --no-http < \
        addons/mezze_bridge/demo/seed_promos.py
"""


def _discount_product(env):
    """A tax-free service product to carry discount lines (find-or-create)."""
    Product = env['product.product'].sudo()
    p = Product.search([('default_code', '=', 'PROMO_DISC')], limit=1)
    if not p:
        tmpl = env['product.template'].sudo().create({
            'name': 'Discount', 'default_code': 'PROMO_DISC', 'type': 'service',
            'available_in_pos': True, 'list_price': 0.0, 'taxes_id': [(6, 0, [])]})
        p = tmpl.product_variant_id
    return p


def _ensure_reward_product(env, program):
    """Guarantee every discount reward has a discount_line_product_id set."""
    dp = _discount_product(env)
    for r in program.reward_ids:
        if r.reward_type == 'discount' and not r.discount_line_product_id:
            r.discount_line_product_id = dp.id


def seed_promos(env):
    Program = env['loyalty.program'].sudo()

    def make(name, vals):
        prog = Program.search([('name', '=', name)], limit=1)
        if prog:
            return prog, False
        return Program.create(dict(vals, name=name)), True

    # 1. Automatic promotion — spend 200 -> 25 off
    auto, a_new = make('Spend 200, save 25', {
        'program_type': 'promotion', 'trigger': 'auto', 'applies_on': 'current',
        'rule_ids': [(0, 0, {'minimum_amount': 200.0, 'mode': 'auto'})],
        'reward_ids': [(0, 0, {'reward_type': 'discount', 'discount': 25.0,
                               'discount_mode': 'per_order', 'discount_applicability': 'order'})],
    })
    _ensure_reward_product(env, auto)

    # 2. Reusable discount code — WELCOME10 -> 10% off
    code, c_new = make('Welcome 10%', {
        'program_type': 'promo_code', 'trigger': 'with_code', 'applies_on': 'current',
        'rule_ids': [(0, 0, {'mode': 'with_code', 'code': 'WELCOME10'})],
        'reward_ids': [(0, 0, {'reward_type': 'discount', 'discount': 10.0,
                               'discount_mode': 'percent', 'discount_applicability': 'order'})],
    })
    _ensure_reward_product(env, code)

    # 3. Single-use coupon program + one issued coupon (SAVE15X -> 15% off)
    coup, cp_new = make('Coupon 15%', {
        'program_type': 'coupons', 'trigger': 'with_code', 'applies_on': 'current',
        'rule_ids': [(0, 0, {'mode': 'with_code'})],
        'reward_ids': [(0, 0, {'reward_type': 'discount', 'discount': 15.0,
                               'discount_mode': 'percent', 'discount_applicability': 'order'})],
    })
    _ensure_reward_product(env, coup)
    Card = env['loyalty.card'].sudo()
    if not Card.search([('code', '=', 'SAVE15X')], limit=1):
        Card.create({'program_id': coup.id, 'code': 'SAVE15X', 'points': 1.0})

    env.cr.commit()
    print("[seed_promos] auto promo 'Spend 200, save 25' id=%s (%s)"
          % (auto.id, 'new' if a_new else 'existing'))
    print("[seed_promos] code WELCOME10 (10%%) id=%s (%s)"
          % (code.id, 'new' if c_new else 'existing'))
    print("[seed_promos] coupon SAVE15X (15%%, single-use) program id=%s (%s)"
          % (coup.id, 'new' if cp_new else 'existing'))
    print("[seed_promos] done — try them at checkout or via /promo/apply.")


if 'env' in globals():
    seed_promos(env)  # noqa: F821
