# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Demo seed — put real food photos on the menu products so the online
storefront (``shop.html``) shows photography instead of the illustrated
fallback tile.

The images are Odoo's OWN demo food photos, shipped in the ``pos_restaurant``
addon (``pos_restaurant/static/img/th-*.png`` etc.) — a hard dependency of
``mezze_bridge``, so they are always present. Each menu item is matched to the
closest demo photo by a name keyword; anything without a good match is left
image-less on purpose (the storefront falls back to its clean glyph tile rather
than showing a wrong/branded photo).

This is a MANUAL demo seed, NOT wired into the manifest: a real merchant uploads
their own product photos in Odoo (Product -> image), which the storefront picks
up automatically. Run it by hand against a demo database:

    ./odoo-bin shell -c <conf> -d <db> --no-http < \
        addons/mezze_bridge/demo/seed_images.py

Idempotent: re-running re-applies the same images. Portable: it resolves the
``pos_restaurant`` image directory from the installed module path, so it works
regardless of where the addon lives.
"""
import base64
import os


# menu-item name keyword -> pos_restaurant demo image file (best visual match).
# Deliberately partial: Cheesecake / Croissant / Cold Brew have no good demo
# photo, so they are omitted and keep the storefront's illustrated glyph tile.
IMAGE_MAP = [
    ('Margherita', 'th-pizza-ma.png'),
    ('Pepperoni', 'th-pizza.png'),
    ('Veggie', 'th-pizza-ve.png'),
    ('Half', 'th-pizza-fu.png'),          # Half & Half Pizza
    ('Cappuccino', 'th-espresso.png'),
    ('Espresso', 'th-espresso.png'),
    ('Flat White', 'th-espresso.png'),
    ('Avocado', 'th-salmon-avocado.png'),
    ('Breakfast', 'combo-hamb.png'),      # Breakfast Combo
]


def _img_dir(env):
    """Absolute path to pos_restaurant's demo image folder."""
    mod = env['ir.module.module'].sudo().search(
        [('name', '=', 'pos_restaurant')], limit=1)
    if not mod:
        raise RuntimeError("pos_restaurant is not installed")
    # get_module_path is available on the module record's env in a shell run
    from odoo.modules.module import get_module_path
    path = get_module_path('pos_restaurant')
    return os.path.join(path, 'static', 'img')


def seed_images(env):
    Product = env['product.product']
    img_dir = _img_dir(env)
    done, missing_prod, missing_file = [], [], []
    for kw, fn in IMAGE_MAP:
        prod = Product.search(
            [('available_in_pos', '=', True), ('name', 'ilike', kw)], limit=1)
        if not prod:
            missing_prod.append(kw)
            continue
        path = os.path.join(img_dir, fn)
        if not os.path.exists(path):
            missing_file.append(fn)
            continue
        with open(path, 'rb') as fh:
            prod.image_1920 = base64.b64encode(fh.read())
        done.append('%s <- %s' % (prod.name, fn))

    env.cr.commit()
    print("[seed_images] img dir: %s" % img_dir)
    for d in done:
        print("[seed_images]   %s" % d)
    if missing_prod:
        print("[seed_images] no product matched: %s" % ', '.join(missing_prod))
    if missing_file:
        print("[seed_images] demo file missing: %s" % ', '.join(missing_file))
    imaged = Product.search(
        [('available_in_pos', '=', True)]).filtered(lambda p: p.image_256)
    print("[seed_images] done — %d menu products now have a photo. Reload shop.html."
          % len(imaged))


# When piped into `odoo-bin shell`, `env` is already in scope.
if 'env' in globals():
    seed_images(env)  # noqa: F821
