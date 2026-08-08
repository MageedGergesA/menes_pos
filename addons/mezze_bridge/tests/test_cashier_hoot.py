"""R1B — run the Mezze CASHIER HOOT unit suite headlessly.

The pure cashier logic tests live in ``static/tests/cashier_logic.test.js`` (bundle
``web.assets_unit_tests``): money/cart/tender helpers, connectivity semantics, favorites
per-(branch,user) storage isolation, and exact-line remove/undo. This runner drives
Odoo's HOOT page filtered to the ``Mezze Cashier ·`` suites, so it executes ONLY those.
Tagged ``mezze_hoot`` so it runs alongside the KDS HOOT runner.
"""
from odoo.tests import HttpCase, tagged

try:
    from odoo.addons.web.tests.test_js import unit_test_error_checker
except Exception:  # noqa: BLE001
    unit_test_error_checker = None


@tagged('post_install', '-at_install', 'mezze_hoot')
class TestCashierHoot(HttpCase):
    def test_cashier_hoot_suite(self):
        self.browser_js(
            '/web/tests?headless&loglevel=2&preset=desktop&timeout=30000&filter=Mezze%20Cashier',
            "", "", login='admin', timeout=600,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker)
