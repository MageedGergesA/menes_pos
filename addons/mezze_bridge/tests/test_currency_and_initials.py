# -*- coding: utf-8 -*-
"""One shop, one currency — and a tile that says what the dish is.

Both found by looking at the running product rather than by the suite.

**The currency disagreed with itself.** The Register renders the currency's
``symbol`` — "LE" for Egypt — while every customer surface sent ``name``, the ISO
code. So the till showed a guest "320.00 LE" and the shop's own storefront, kiosk
and table menu showed the same dish as "EGP 320". Whichever a shop prefers, both
sides of the counter have to agree, and the operator has already chosen: ``symbol``
is the configured display, so a branch that sets it to "ج.م" now gets that
everywhere instead of only on the till.

Machine-facing payloads deliberately keep the ISO code. A payment provider is
entitled to ISO 4217 and would reject "LE", so checkout, the charge payloads and
the outbound order events are pinned to ``name`` here — that separation is the
point of the change, not an oversight in it.

**A tile called a dish "B(".** The placeholder initials split the name on spaces
and took ``charAt(0)`` of the first two words, so "Baklava (per kg)" became "B" +
"(" — a bracket standing in for a dish on a card a cashier taps under pressure.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_currency')
class TestOneShopOneCurrency(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'cur-tok')
        # A currency whose symbol is NOT its code, which is the whole point: with
        # symbol == name the bug is invisible.
        cls.pos_config.currency_id.sudo().write({'symbol': 'LE'})
        cls.sess = cls._open_session_for(cls.pos_config)
        env.flush_all()

    def _post(self, path, body=None):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body or {}, token='cur-tok')),
                          headers={'Content-Type': 'application/json'})
        try:
            return r.status_code, r.json()
        except Exception:                                        # noqa: BLE001
            return r.status_code, {'raw': r.text[:200]}

    STORE = 'curshoptok'

    def _store(self):
        # The storefront credential is a config parameter the branch mints; set it
        # directly rather than through /shop/link, as the rest of the suite does.
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.store_token_%s' % self.pos_config.id, self.STORE)
        return self.STORE

    # ── what a guest reads ───────────────────────────────────────────────
    def test_01_the_storefront_shows_what_the_till_shows(self):
        """THE bug: the till said LE and the shop's own storefront said EGP."""
        _c, cfg = self._post('/shop/config', {'store': self._store()})
        self.assertEqual(cfg.get('currency'), 'LE',
                         'the storefront labels money differently from the Register')

    def test_02_the_table_menu_agrees_too(self):
        table = self.env['restaurant.table'].sudo().search(
            [('active', '=', True)], limit=1)
        if not table:
            self.skipTest('no restaurant table in this profile')
        _c, link = self._post('/qr/table_link',
                              {'config_id': self.pos_config.id, 'table_id': table.id})
        _c, menu = self._post('/qr/menu', {'table_id': table.id,
                                           'qr': link.get('qr_token')})
        self.assertEqual(menu.get('currency'), 'LE')

    def test_03_the_kiosk_is_handed_both_and_can_prefer_the_symbol(self):
        """The kiosk takes an object rather than a string, so the fix there is in
        the page — but the payload has to carry the symbol for it to render one."""
        _c, cfg = self._post('/kiosk/config', {'store': self._store()})
        cur = cfg.get('currency') or {}
        self.assertEqual(cur.get('symbol'), 'LE')
        self.assertEqual(cur.get('name'), self.pos_config.currency_id.name)

    def test_04_a_shop_that_configures_a_symbol_gets_it_everywhere(self):
        """Not hard-coded to Egypt: whatever the operator sets is what shows."""
        self.pos_config.currency_id.sudo().write({'symbol': 'ج.م'})
        self.env.flush_all()
        _c, cfg = self._post('/shop/config', {'store': self._store()})
        self.assertEqual(cfg.get('currency'), 'ج.م')

    def test_05_a_currency_with_no_symbol_falls_back_to_its_code(self):
        """A blank symbol must not label the money with an empty string."""
        self.pos_config.currency_id.sudo().write({'symbol': ''})
        self.env.flush_all()
        _c, cfg = self._post('/shop/config', {'store': self._store()})
        self.assertEqual(cfg.get('currency'), self.pos_config.currency_id.name)

    # ── what a machine reads ─────────────────────────────────────────────
    def test_10_payment_payloads_stay_on_the_iso_code(self):
        """The other half of the change, and the reason it is not global: a payment
        provider is entitled to ISO 4217 and would reject "LE"."""
        from odoo.tools import file_open
        for path in ('mezze_bridge/controllers/checkout.py',
                     'mezze_bridge/controllers/w1.py'):
            with file_open(path, 'r') as fh:
                src = fh.read()
            self.assertNotIn('_display_currency', src,
                             '%s sends a guest-facing SYMBOL to a payment provider; '
                             'ISO 4217 is what a provider accepts' % path)
            self.assertIn('currency_id.name', src,
                          '%s no longer sends the ISO currency code' % path)


@tagged('post_install', '-at_install', 'mezze_currency')
class TestTileInitials(MezzeHttpCase):
    """A tile with no photo falls back to initials. It has to spell something."""
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._open_session_for(cls.pos_config)
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        # Rename a product the fixture already puts in the catalogue rather than
        # creating one: a new product needs a POS category to reach the grid, and
        # this test is about the NAME, not about catalogue membership.
        cls.weighed = cls.product
        cls.weighed.sudo().write({'name': 'Baklava (per kg)'})
        cls.env.flush_all()

    def test_20_a_parenthetical_is_not_a_word_of_the_name(self):
        """THE bug: "Baklava (per kg)" put a bracket on the card as "B(" — the
        qualifier was read as the second word of the dish."""
        self.browser_js('/mezze/pos', r"""
            (async () => {
                async function waitFor(f, l, ms = 20000) {
                    const t0 = Date.now();
                    while (Date.now() - t0 < ms) {
                        try { if (f()) return true; } catch (e) {}
                        await new Promise(r => setTimeout(r, 120));
                    }
                    throw new Error("timeout waiting for: " + l);
                }
                const $$ = (s) => Array.from(document.querySelectorAll(s));
                await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
                const tile = $$('.mz-tile').find(
                    (t) => /Baklava/.test(t.textContent));
                if (!tile) { throw new Error("the weighed dish is not on the menu"); }
                const ph = tile.querySelector('.mz-tile__ph');
                if (!ph) { throw new Error("the tile has no placeholder to read"); }
                const ini = (ph.textContent || '').trim();
                if (/[^\p{L}\p{N}]/u.test(ini)) {
                    throw new Error("the tile spells the dish with punctuation: "
                                    + JSON.stringify(ini));
                }
                if (ini !== 'B') {
                    throw new Error("expected B for 'Baklava (per kg)', got "
                                    + JSON.stringify(ini));
                }
                console.log("test successful");
            })();
        """, login='admin')

    def test_21_an_ordinary_two_word_dish_is_unchanged(self):
        """The guard on the fix: it must not have changed the common case."""
        self.browser_js('/mezze/pos', r"""
            (async () => {
                async function waitFor(f, l, ms = 20000) {
                    const t0 = Date.now();
                    while (Date.now() - t0 < ms) {
                        try { if (f()) return true; } catch (e) {}
                        await new Promise(r => setTimeout(r, 120));
                    }
                    throw new Error("timeout waiting for: " + l);
                }
                const $$ = (s) => Array.from(document.querySelectorAll(s));
                await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
                const withPh = $$('.mz-tile').filter(
                    (t) => t.querySelector('.mz-tile__ph'));
                if (!withPh.length) { throw new Error("no placeholder tiles at all"); }
                for (const t of withPh) {
                    const ini = (t.querySelector('.mz-tile__ph').textContent || '').trim();
                    if (!ini) { throw new Error("a tile has an EMPTY placeholder"); }
                    if (ini.length > 2) {
                        throw new Error("a placeholder is longer than two letters: "
                                        + JSON.stringify(ini));
                    }
                    if (/[^\p{L}\p{N}]/u.test(ini)) {
                        throw new Error("a placeholder contains punctuation: "
                                        + JSON.stringify(ini));
                    }
                }
                console.log("test successful");
            })();
        """, login='admin')
