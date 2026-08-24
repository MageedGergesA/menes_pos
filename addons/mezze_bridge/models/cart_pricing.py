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
        applied_taxes = []                 # names, in the order they were charged
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
        # Combo picks, resolved ONCE for the cart, the same way and for the same
        # reason: a pre-fire preview of a combo must carry the chosen items' extra
        # price, or the operator's panel and the customer's board would quote the
        # bare combo price and the order would land dearer. Each item is checked
        # against THIS product's own combo groups below — a browser cannot price a
        # meal with another combo's cheaper option.
        item_ids = {int(pick.get('item_id')) for line in (lines or [])
                    for pick in (line.get('combo') or []) if pick.get('item_id')}
        combo_items = self.env['product.combo.item'].sudo().browse(
            sorted(item_ids)).exists() if item_ids else self.env['product.combo.item']
        item_by_id = {i.id: i for i in combo_items}
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
            # The combo's own choices: same discipline as the attribute values —
            # an item that does not belong to this product's combo groups is
            # dropped rather than priced.
            own_combos = product.product_tmpl_id.combo_ids
            picks, pick_qty = [], {}
            for p in (line.get('combo') or []):
                iid = int(p.get('item_id') or 0)
                item = item_by_id.get(iid)
                if not item or item.combo_id not in own_combos:
                    continue
                if item not in picks:
                    picks.append(item)
                pick_qty[item.id] = pick_qty.get(item.id, 0) + max(1, int(p.get('qty') or 1))
            # Odoo's rule, mirrored: the meal's price covers qty_free items per
            # group; each item beyond that costs the group's base price. Plus every
            # chosen item's own extra_price, per unit taken.
            for combo in own_combos:
                in_group = [i for i in picks if i.combo_id == combo]
                taken = sum(pick_qty[i.id] for i in in_group)
                beyond = max(0, taken - combo.qty_free)
                price += beyond * combo.base_price
            price += sum(i.extra_price * pick_qty[i.id] for i in picks)
            taxes = product.taxes_id.filtered(lambda t: t.company_id == company) or product.taxes_id
            for tax in taxes:
                # Recorded HERE, where the tax is actually charged. A caller that
                # re-derives the names from the product afterwards can pick a
                # different set — a different company, or `company_id = False` — and
                # then name a tax on the customer's screen that was never applied.
                if tax.name and tax.name not in applied_taxes:
                    applied_taxes.append(tax.name)
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
                              + [('%s x%s' % (i.product_id.display_name, pick_qty[i.id])
                                  if pick_qty[i.id] > 1 else i.product_id.display_name)
                                 for i in picks]
                              or [m for m in (line.get('modifiers') or []) if m]),
                'note': (line.get('note') or '').strip() or None,
                'line_total': round(gross, 2),
            })
        return rows, {'subtotal': round(subtotal, 2),
                      'tax': round(tax_total, 2),
                      'total': round(subtotal + tax_total, 2),
                      # What to CALL the tax row, from the taxes this pass actually
                      # used. Empty when nothing was charged, so a caller cannot put a
                      # name on a row that does not exist.
                      'tax_names': applied_taxes if tax_total else []}
