"""D1.1 — re-seed the setting catalog so catalog effect metadata (e.g. catStyle
now 'live') stays consistent after the completion pass. Idempotent."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['mezze.setting.def'].seed_catalog()
