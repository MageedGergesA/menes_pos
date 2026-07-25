"""D1 Design Platform migration — idempotent.

Seeds the setting catalog and the four initial admin templates (Cashier Standard,
Server / Floor, Manager, Drive-thru). Re-running is safe: catalog upserts by key,
templates upsert by name. Existing personal/scoped values are never discarded.
"""
from odoo import api, SUPERUSER_ID

# name -> (kind, [(setting_key, value, policy), ...])
DEFAULT_TEMPLATES = {
    'Cashier Standard': ('role', [
        ('density', 'standard', 'free'), ('cardMode', 'standard', 'free'),
        ('gridCols', 'auto', 'free'), ('panelSide', 'right', 'free'),
        ('landingView', 'pos', 'free'),
    ]),
    'Server / Floor': ('role', [
        ('landingView', 'floor', 'free'), ('density', 'comfortable', 'free'),
        ('cardMode', 'compact', 'free'),
    ]),
    'Manager': ('role', [
        ('landingView', 'manager', 'free'), ('density', 'standard', 'free'),
        ('showProvenance', 'true', 'free'),
    ]),
    'Drive-thru': ('role', [
        ('landingView', 'pos', 'free'), ('cardMode', 'text', 'free'),
        ('gridCols', '3', 'free'), ('uiScale', '110', 'free'),
    ]),
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['mezze.setting.def'].seed_catalog()
    Tpl = env['mezze.config.template'].sudo()
    Line = env['mezze.config.template.line'].sudo()
    for name, (kind, lines) in DEFAULT_TEMPLATES.items():
        t = Tpl.search([('name', '=', name)], limit=1)
        if not t:
            t = Tpl.create({'name': name, 'kind': kind, 'state': 'published', 'version': 1})
        have = {ln.setting_key for ln in t.line_ids}
        for key, val, pol in lines:
            if key not in have:
                Line.create({'template_id': t.id, 'setting_key': key, 'value': val, 'policy': pol})
