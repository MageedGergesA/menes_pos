# Part of the Mezze POS platform. See LICENSE (LGPL-3).
{
    'name': "Mezze Bridge API",
    'summary': "Versioned JSON HTTP bridge between an external Mezze POS frontend "
               "and Odoo point_of_sale (catalog bootstrap + idempotent order sync).",
    'description': """
Mezze Bridge API
================
Exposes OUR OWN versioned JSON API (``/mezze/api/v1/``) so an external Mezze
frontend can bootstrap catalog/config and sync orders into a real Odoo DB while
REUSING Odoo's own ``point_of_sale`` machinery for stock deduction and
accounting. The frontend never touches Odoo ORM-RPC; it only speaks this API.

Two seams are reused verbatim:
  * loading  -> curated ``search_read`` over the ``pos.load.mixin`` fields
  * writing  -> ``pos.order.sync_from_ui`` (idempotent by native ``pos.order.uuid``)
""",
    'version': "19.0.2.0.0",
    'category': "Point of Sale",
    'author': "Teklines",
    'website': "https://teklines.com",
    'license': "LGPL-3",
    'depends': ['point_of_sale', 'pos_restaurant', 'stock', 'account', 'bus',
                'mrp', 'loyalty', 'payment_paymob',
                # S2C-5 — online customer payments reuse Odoo's native POS↔
                # payment.transaction bridge + the Demo provider (proven first).
                'pos_online_payment', 'payment_demo'],
    'data': [
        'security/ir.model.access.csv',
        'data/nonce_gc_cron.xml',
        'data/outbox_cron.xml',
        'data/settings_catalog_bootstrap.xml',
        'views/cashier_templates.xml',
        'views/checkout_templates.xml',
    ],
    'assets': {
        # Standalone Owl cashier app (S2C-1). Lightweight base: Odoo module loader
        # + Owl + @web/core (no full backend webclient). Served by /mezze/pos.
        'mezze_bridge.assets_cashier': [
            # Standalone base: module loader + Owl + @web/core JS/XML only. The core
            # components' SCSS is deliberately excluded (it assumes the full backend
            # variable chain, e.g. $o-datetime-picker-width); the cashier ships its
            # own plain-CSS styles, so none of that SCSS is needed.
            'web/static/src/module_loader.js',
            'web/static/lib/luxon/luxon.js',
            'web/static/lib/owl/owl.js',
            'web/static/lib/owl/odoo_module.js',
            'web/static/src/env.js',
            'web/static/src/session.js',
            'web/static/src/core/**/*.js',
            ('remove', 'web/static/src/core/emoji_picker/emoji_data.js'),
            'web/static/src/core/**/*.xml',
            'mezze_bridge/static/src/cashier/**/*',
        ],
        # Hoot unit tests for the pure cashier logic (order/change/idempotency).
        # The logic module under test is included so the tests can import it.
        'web.assets_unit_tests': [
            'mezze_bridge/static/src/cashier/order_store.js',
            'mezze_bridge/static/src/cashier/debug.js',
            'mezze_bridge/static/tests/**/*',
        ],
    },
    'application': False,
    'auto_install': False,
    'external_dependencies': {'python': ['cryptography']},
    'installable': True,
    'post_init_hook': 'post_init_generate_token',
}
