# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Restaurant modifier groups and options (design BE-010 / MENU_ENGINE §2).

Size, Spice level, Add-ons, Doneness, Preparation. The design is explicit that
these are NOT Odoo variants or Combo Choices: a variant creates a distinct
sellable product (rare here) and a Combo Choice bundles whole products, not
per-item options with a price delta. So this is the dedicated modifier-group
table the handoff calls for -- ONE definition, read identically by Register,
Kiosk, QR, Handheld and the Call Centre.

A COMBO SLOT IS THE SAME MODEL, tagged ``is_combo``. That is the design's own
decision (closure pass 17B), not a shortcut: "one required single-select group
with priced options" already describes a combo slot exactly, so no surface needs
new code to sell a combo.

Selections live on the order line as rows (``mezze.order.line.modifier``), never
as a joined label -- see ``domain/modifiers.py``. Free-text kitchen instructions
stay in core's own ``note`` field on the line and never enter this structure.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..domain import modifiers as mods


class MezzeModifierGroup(models.Model):
    _name = 'mezze.modifier.group'
    _description = 'Mezze Modifier Group'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    # The STABLE key a line's selection points at. Renaming `name` must never
    # detach a line already using it -- the defect the prototype flags in its
    # own §2a caveat, where the label is the identifier.
    code = fields.Char(required=True, index=True, copy=False,
                       help="Stable key (e.g. 'size'). Renaming the label must never move it.")
    sequence = fields.Integer(default=10)
    required = fields.Boolean(help="The guest must satisfy this group before the line is valid.")
    min_select = fields.Integer(default=0, help="0 = unbounded. Odoo has no native min/max.")
    max_select = fields.Integer(default=1, help="0 = unbounded.")
    is_combo = fields.Boolean(
        string="Combo slot",
        help="A combo slot (Main/Side/Drink) is this same model tagged — design pass 17B.")
    option_ids = fields.One2many('mezze.modifier.option', 'group_id')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique(code)', "A modifier group key must be unique.")

    @api.constrains('min_select', 'max_select', 'required')
    def _check_bounds(self):
        for g in self:
            if g.min_select < 0 or g.max_select < 0:
                raise ValidationError(_("Selection bounds cannot be negative."))
            if g.max_select and g.min_select > g.max_select:
                raise ValidationError(_(
                    "Group %s: minimum picks cannot exceed the maximum.") % g.name)

    def as_domain(self):
        """This group in the shape ``domain/modifiers`` validates against."""
        return [mods.Group(key=g.code, required=g.required,
                           min_select=g.min_select, max_select=g.max_select,
                           options={o.id: o.available for o in g.option_ids})
                for g in self]


class MezzeModifierOption(models.Model):
    _name = 'mezze.modifier.option'
    _description = 'Mezze Modifier Option'
    _order = 'sequence, id'

    group_id = fields.Many2one('mezze.modifier.group', required=True,
                               ondelete='cascade', index=True)
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    price_delta = fields.Float(digits='Product Price',
                               help="What choosing this adds to the line's unit price.")
    # 86 lives on the OPTION: a branch can run out of one size without
    # withdrawing the dish. Availability, never archiving -- an archived record
    # loses its history (MENU_ENGINE §1).
    available = fields.Boolean(default=True, string="Available")
    is_default = fields.Boolean(help="Pre-selected when the group opens.")
    # A combo slot's option names a real product, which is how each component
    # resolves its OWN kitchen station (design pass 17C).
    product_id = fields.Many2one('product.product', ondelete='set null',
                                 help="For a combo slot: the product this choice serves.")


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    mezze_modifier_group_ids = fields.Many2many(
        'mezze.modifier.group', 'mezze_product_modifier_group_rel',
        'product_tmpl_id', 'group_id', string="Modifier groups")
    mezze_is_combo = fields.Boolean(
        string="Combo product",
        help="Its modifier groups are combo slots — design pass 17B.")

    @api.constrains('mezze_modifier_group_ids', 'mezze_is_combo')
    def _check_combo_groups(self):
        """A combo's slots are combo slots; an ordinary product's are not.

        The design's group picker filters by this so a combo's slot list cannot
        accidentally pull in an ordinary modifier group. A picker is a
        convenience; this is the rule.
        """
        for p in self:
            for g in p.mezze_modifier_group_ids:
                if bool(g.is_combo) != bool(p.mezze_is_combo):
                    raise ValidationError(_(
                        "%s is a %s, so it cannot carry %r, which is a %s.")
                        % (p.name, "combo" if p.mezze_is_combo else "regular product",
                           g.name, "combo slot" if g.is_combo else "modifier group"))


class MezzeOrderLineModifier(models.Model):
    """One selection on one order line — the structured fact, never a label.

    ``price_delta`` and ``label`` are SNAPSHOTS taken when the line was added: a
    later price change or rename must not rewrite what the guest agreed to, and
    the receipt must still read the way it did at the till.
    """
    _name = 'mezze.order.line.modifier'
    _description = 'Mezze Order Line Modifier Selection'
    _order = 'id'

    line_id = fields.Many2one('pos.order.line', required=True,
                              ondelete='cascade', index=True)
    group_id = fields.Many2one('mezze.modifier.group', required=True, ondelete='restrict')
    option_id = fields.Many2one('mezze.modifier.option', required=True, ondelete='restrict')
    label = fields.Char(required=True, help="Display text as it read when chosen.")
    price_delta = fields.Float(digits='Product Price',
                               help="The delta as it was when the guest chose it.")


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    # `note` (core, "Product Note") stays the free-text kitchen instruction and
    # never holds a modifier -- two different facts with two different owners.
    mezze_modifier_ids = fields.One2many('mezze.order.line.modifier', 'line_id')
    mezze_modifier_label = fields.Char(
        compute='_compute_mezze_modifier_label',
        help="Derived on demand — never stored as the line's fact.")

    @api.depends('mezze_modifier_ids.label')
    def _compute_mezze_modifier_label(self):
        for line in self:
            line.mezze_modifier_label = mods.render([
                mods.Selection(g=m.group_id.code, t=m.option_id.id,
                               label=m.label, p=m.price_delta)
                for m in line.mezze_modifier_ids])

    def mezze_selections(self):
        """This line's selections in the shape ``domain/modifiers`` reads."""
        self.ensure_one()
        return [mods.Selection(g=m.group_id.code, t=m.option_id.id,
                               label=m.label, p=m.price_delta)
                for m in self.mezze_modifier_ids]
