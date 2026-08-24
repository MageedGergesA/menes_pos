# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Provision the loyalty programme on databases installed before it existed.

The post-init hook only runs on a fresh install, so an existing branch would have
upgraded into the same inert loyalty it had before: a programme that every code path
looked for and nothing had ever created.
"""
from odoo import api, SUPERUSER_ID

from odoo.addons.mezze_bridge.models.loyalty_bootstrap import ensure_loyalty_program


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ensure_loyalty_program(env)
