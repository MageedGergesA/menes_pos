# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Migrate POS-time product attributes onto Mezze modifier groups (BE-010).

Restaurant modifiers used to ride Odoo ``product.attribute`` lines with
``create_variant='no_variant'``. The design handoff is explicit that this is the
wrong home for Size/Spice/Add-ons: a variant is for attributes that create a
distinct sellable product, and a Combo Choice bundles whole products — neither
describes a per-item option with a price delta.

This converts the existing data in place. It is IDEMPOTENT (a group already
carrying its source attribute id is skipped) and it does NOT delete the
attribute lines: the old reader still falls back to them, so a half-finished
migration serves a menu rather than an empty one. Removing them is a separate,
later step once nothing reads them.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    Group = env['mezze.modifier.group'].sudo()
    Option = env['mezze.modifier.option'].sudo()

    lines = env['product.template.attribute.line'].sudo().search(
        [('attribute_id.create_variant', '=', 'no_variant')])
    if not lines:
        return

    converted = attached = 0
    for al in lines:
        attr = al.attribute_id
        code = 'attr_%s' % attr.id          # stable, derived from the source id
        group = Group.search([('code', '=', code)], limit=1)
        if not group:
            multi = attr.display_type == 'multi'
            group = Group.create({
                'name': attr.name,
                'code': code,
                # A single-select attribute was required-exactly-one and a multi
                # was optional-any -- the rule the old reader encoded. Carried
                # over verbatim so the migration changes no behaviour.
                'required': not multi,
                'min_select': 0 if multi else 1,
                'max_select': 0 if multi else 1,
                'sequence': al.sequence or 10,
            })
            converted += 1
        for ptav in al.product_template_value_ids:
            name = ptav.product_attribute_value_id.name
            if not Option.search_count([('group_id', '=', group.id), ('name', '=', name)]):
                Option.create({
                    'group_id': group.id,
                    'name': name,
                    'price_delta': ptav.price_extra,
                    # ptav_active is Odoo's own "offered on this product" flag;
                    # an option switched off there must not come back available.
                    'available': bool(ptav.ptav_active),
                })
        tmpl = al.product_tmpl_id
        if group not in tmpl.mezze_modifier_group_ids:
            tmpl.mezze_modifier_group_ids = [(4, group.id)]
            attached += 1

    _logger.info("Mezze BE-010: converted %s attribute group(s), %s product link(s)",
                 converted, attached)
