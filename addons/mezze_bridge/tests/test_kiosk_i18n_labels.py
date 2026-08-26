# -*- coding: utf-8 -*-
"""The last English a guest could meet on an Arabic kiosk.

Two labels stayed English inside an otherwise fully Arabic screen: the service
choice ("Eat in" / "Takeaway") and the whole pay-at-counter card, title and
explanatory sentence both. The kiosk translates its own chrome from a dictionary
in the page — the rest of the screen was Arabic — but these came from the server
as finished English strings, so there was nothing to translate.

Fixing it server-side would not have worked. The kiosk's language toggle is
**client-side**: a guest switches mid-order and the screen flips with no round
trip, so a label translated when the config was fetched would stay in whichever
language that fetch happened to use. The server therefore sends a CODE
(``service_mode`` / ``kind``, and ``code`` / ``at_table`` for payment) and the
page renders the words.

One thing deliberately not translated: a branch's own ``pos.preset`` name. That is
the shop's data, not our label, and a kiosk that rewrote it would be showing the
guest something the branch did not write.
"""
import json

from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_kiosk')
class TestKioskLabelContract(MezzeHttpCase):
    """The payload has to carry a code, or the page has nothing to translate from."""
    fixture_profile = 'POS'

    STORE = 'kiosk-i18n-tok'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'ki-tok')
        icp.set_param('mezze_bridge.store_token_%s' % cls.pos_config.id, cls.STORE)
        cls.env.flush_all()

    def _config(self):
        r = self.url_open('/mezze/api/v1/kiosk/config',
                          data=json.dumps({'token': 'ki-tok', 'store': self.STORE}),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def test_01_a_service_option_names_its_mode_not_just_a_label(self):
        cfg = self._config()
        opts = cfg.get('service_options') or []
        self.assertTrue(opts, 'the kiosk is offered no service choice at all')
        for o in opts:
            self.assertIn(o.get('kind'), ('preset', 'service_mode'), o)
            if o['kind'] == 'service_mode':
                self.assertIn(o.get('service_mode'), ('eat_in', 'takeaway'),
                              'a generic service mode with no code for the page to '
                              'translate from: %r' % o)

    def test_02_the_payment_option_names_its_code_and_where_it_is_paid(self):
        cfg = self._config()
        opts = cfg.get('payment_options') or []
        self.assertTrue(opts, 'the kiosk is offered no way to pay')
        pay = opts[0]
        self.assertEqual(pay.get('code'), 'pay_at_counter')
        self.assertIn('at_table', pay,
                      'the page cannot tell "at the counter" from "at your table" '
                      'without being told which this branch is')
        self.assertIsInstance(pay['at_table'], bool)

    def test_03_the_english_stays_as_a_fallback_for_a_client_with_no_dictionary(self):
        """The codes are the contract; the English is still sent so a bare client
        renders something, rather than nothing."""
        cfg = self._config()
        self.assertTrue((cfg['payment_options'][0].get('name') or '').strip())
        for o in cfg['service_options']:
            self.assertTrue((o.get('name') or '').strip())


@tagged('post_install', '-at_install', 'mezze_kiosk')
class TestKioskRendersItsOwnWords(TransactionCase):
    """Guarded in the source: the page must render through its translator.

    A behavioural check has to walk five screens to reach the payment card, and the
    thing that actually broke was a render site printing the server's English
    directly. That is visible by reading the page.
    """

    def _page(self):
        with file_open('mezze_bridge/static/kiosk.html', 'r') as fh:
            return fh.read()

    def test_10_every_service_label_goes_through_the_translator(self):
        page = self._page()
        self.assertIn('function svcLabel(', page,
                      'the kiosk has no translator for the service choice')
        self.assertNotIn('esc(svc.name)', page,
                         'a service label is printed straight from the server, so it '
                         'stays English on an Arabic screen')
        self.assertNotIn("esc(o.name)", page,
                         'a choice or payment label is printed straight from the '
                         'server rather than through the translator')

    def test_11_the_payment_card_goes_through_the_translator(self):
        page = self._page()
        for fn in ('function payLabel(', 'function payHint('):
            self.assertIn(fn, page, 'the kiosk cannot translate the payment card')
        self.assertIn('esc(payLabel(o))', page)
        self.assertIn('esc(payHint(o))', page)
        self.assertNotIn("esc(o.hint||'')", page,
                         'the payment hint is printed straight from the server')

    def test_12_both_languages_carry_every_new_key(self):
        page = self._page()
        for key in ('eatIn', 'takeaway', 'payCounter', 'payCounterHint',
                    'payTable', 'payTableHint'):
            self.assertEqual(page.count(key + ':'), 2,
                             '%s is not defined in exactly both languages — a key in '
                             'one dictionary only falls back to English silently'
                             % key)

    def test_13_a_branchs_own_preset_name_is_never_rewritten(self):
        """The line between our label and the shop's data. A preset is the branch's
        own record; translating it would show a guest something nobody wrote."""
        page = self._page()
        start = page.index('function svcLabel(')
        body = page[start:page.index('}', page.index('return o.name', start))]
        self.assertIn("o.kind==='service_mode'", body,
                      'svcLabel translates by kind, so a preset keeps its own name')
        self.assertIn('return o.name', body,
                      'svcLabel has no fallback to the name the server sent')
