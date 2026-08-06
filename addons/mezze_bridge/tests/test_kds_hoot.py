"""V2C — run the Mezze KDS HOOT unit suite headlessly.

The pure KDS logic tests live in ``static/tests/kds_logic.test.js`` (bundle
``web.assets_unit_tests``). This runner drives Odoo's own HOOT page filtered to the
``Mezze KDS ·`` suites, so it executes ONLY our deterministic frontend tests (not the
whole Odoo web unit suite). Tagged ``mezze_hoot`` to select/skip independently.
"""
from odoo.tests import HttpCase, tagged

try:  # the error checker lives in the web module's JS test harness
    from odoo.addons.web.tests.test_js import unit_test_error_checker
except Exception:  # noqa: BLE001
    unit_test_error_checker = None


@tagged('post_install', '-at_install', 'mezze_hoot')
class TestKdsHoot(HttpCase):
    def test_kds_hoot_suite(self):
        # filter=Mezze KDS → only our prefixed suites run; success signal is HOOT's own.
        self.browser_js(
            '/web/tests?headless&loglevel=2&preset=desktop&timeout=30000&filter=Mezze%20KDS',
            "", "", login='admin', timeout=600,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker)
