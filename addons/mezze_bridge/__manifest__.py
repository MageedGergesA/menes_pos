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
    'version': "19.0.1.0.0",
    'category': "Point of Sale",
    'author': "Teklines",
    'website': "https://teklines.com",
    'license': "LGPL-3",
    'depends': ['point_of_sale', 'pos_restaurant', 'stock', 'account', 'bus',
                'mrp', 'loyalty', 'payment_paymob'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'application': False,
    'auto_install': False,
    'installable': True,
    'post_init_hook': 'post_init_generate_token',
}
