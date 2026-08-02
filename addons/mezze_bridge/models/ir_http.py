# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Expose this addon's translations to the frontend JS bundle.

A custom module's translations are not shipped to the browser unless the module
is listed as a "frontend translation module". The standalone Owl cashier
(``/mezze/pos``) loads ``/web/webclient/translations`` at boot; adding
``mezze_bridge`` here makes its ``i18n/*.po`` terms available to that fetch so
the cashier chrome renders in the user's language (e.g. Arabic).
"""
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        modules = super()._get_translation_frontend_modules_name()
        if 'mezze_bridge' not in modules:
            modules = modules + ['mezze_bridge']
        return modules
