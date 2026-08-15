# -*- coding: utf-8 -*-
"""Money for a cart that has not been fired yet.

This algorithm was written for the customer's Order Confirmation Board and lived on
``mezze.ocb.display``, which meant only a lane that HAS a customer screen could get a
priced cart. The operator's own order panel needs the same figures — and it must not
depend on whether a display appliance exists in that lane — so the algorithm moved
here and the display now delegates to it.

Nothing about the calculation changed. It is still the same pass: one batched read,
Odoo's own pricelist and ``compute_all``, values validated against their own product's
template, and no row invented that the branch does not actually charge.

There is exactly ONE place in Mezze that prices a pre-fire cart, and this is it.
"""
from odoo import api, models


class MezzeCartPricing(models.AbstractModel):
    _name = 'mezze.cart.pricing'
    _description = 'Mezze — pre-fire cart pricing'

    @api.model
    def _price_cart(self, config, lines):
        """Price a pre-fire cart for ``config``.

        Pre-fire there is no pos.order to ask, so the cart is priced from the branch's
        pricelist and each product's own taxes via Odoo's ``compute_all`` — the engine,
        not a reimplementation of it. Read in ONE batch: callers poll, and a per-line
        product read would be an N+1 on a screen.

        Returns ``(rows, money)``. Only rows that exist are reported: a branch with no
        tax gets no tax row, because inventing "VAT 15%" on a customer's screen is a
        lie with a number on it.
        """
        rows, subtotal, tax_total = [], 0.0, 0.0
        ids = [int(l.get('product_id')) for l in (lines or []) if l.get('product_id')]
        if not ids:
            return rows, {'subtotal': 0.0, 'tax': 0.0, 'total': 0.0}
        products = self.env['product.product'].sudo().browse(ids).exists()
        by_id = {p.id: p for p in products}
        products.mapped('taxes_id')                       # one prefetch for the batch
        # Chosen product.template.attribute.value ids, resolved ONCE for the whole
        # cart. Each is checked against its own product's template before it counts —
        # the same rule the fire path applies — so a browser cannot price a line with
        # another product's options or with ids it invented.
        ptav_ids = {int(v) for line in (lines or [])
                    for v in (line.get('attribute_value_ids') or [])}
        ptavs = self.env['product.template.attribute.value'].sudo().browse(
            sorted(ptav_ids)).exists() if ptav_ids else self.env['product.template.attribute.value']
        ptav_by_id = {v.id: v for v in ptavs}
        pricelist = config.sudo().pricelist_id
        company = config.sudo().company_id
        # Price in BATCHES, one per distinct quantity. A pricelist can have quantity
        # breaks, so a single price per product would be wrong; but the distinct
        # quantities in a cart are bounded by the menu, not by how many lines the
        # operator types, so the work stops growing with the order.
        price_by = {}
        if pricelist:
            by_qty = {}
            for line in (lines or []):
                pid = int(line.get('product_id') or 0)
                qty = float(line.get('qty') or 0)
                if pid in by_id and qty > 0:
                    by_qty.setdefault(qty, set()).add(pid)
            for qty, pids in by_qty.items():
                try:
                    priced = pricelist._get_products_price(
                        products.filtered(lambda p: p.id in pids), qty)
                except Exception:      # noqa: BLE001 — a pricelist must never blank the board
                    priced = {}
                for pid, value in (priced or {}).items():
                    price_by[(pid, qty)] = value
        for line in (lines or []):
            product = by_id.get(int(line.get('product_id') or 0))
            if not product:
                continue
            qty = float(line.get('qty') or 0)
            if qty <= 0:
                continue
            price = price_by.get((product.id, qty), product.list_price)
            # The customization the operator chose, priced and named from the values
            # themselves. Anything that does not belong to THIS product's template is
            # dropped rather than trusted — a browser is not an authority on which
            # options a burger has.
            chosen = [ptav_by_id[int(v)] for v in (line.get('attribute_value_ids') or [])
                      if int(v) in ptav_by_id
                      and ptav_by_id[int(v)].product_tmpl_id == product.product_tmpl_id]
            price += sum(v.price_extra for v in chosen)
            taxes = product.taxes_id.filtered(lambda t: t.company_id == company) or product.taxes_id
            if taxes:
                computed = taxes.compute_all(price, currency=company.currency_id,
                                             quantity=qty, product=product)
                net, gross = computed['total_excluded'], computed['total_included']
            else:
                net = gross = price * qty
            subtotal += net
            tax_total += gross - net
            rows.append({
                # `name`, not display_name: an internal code like "[GIFTCARD]" is
                # noise on a screen a customer is reading from a car.
                'name': product.name,
                'qty': qty,
                # The chosen options, named from the product's own translated
                # attribute values — never a label the browser supplied. A caller may
                # still pass plain strings (the OCB contract predates the drive-thru
                # configurator and other channels may use it), but a validated value
                # always wins.
                'modifiers': ([v.product_attribute_value_id.name for v in chosen]
                              or [m for m in (line.get('modifiers') or []) if m]),
                'note': (line.get('note') or '').strip() or None,
                'line_total': round(gross, 2),
            })
        return rows, {'subtotal': round(subtotal, 2),
                      'tax': round(tax_total, 2),
                      'total': round(subtotal + tax_total, 2)}
