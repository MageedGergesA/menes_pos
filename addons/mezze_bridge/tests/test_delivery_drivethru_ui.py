"""Delivery and drive-thru, reachable from the product at last.

Both existed as backend contracts and neither was reachable. The Register's
Delivery rail item was a read-only counter (it could not create, dispatch or
collect), and the drive-thru board had no Odoo route at all — static/drivethru.html
was an unreachable file whose only way to authenticate was ``?token=`` in the query
string, which puts a bearer token in access logs and browser history.

The interesting assertions here are the ones about who decides what: the till never
computes a delivery fee, never overrides a zone minimum, and never mints its own
credentials.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase

_PRELUDE = r"""
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const phase = () => ($('.mz-app') ? $('.mz-app').dataset.phase : null);
async function waitFor(fn, label, ms=20000){
  const t0 = Date.now();
  while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){} await new Promise(r=>setTimeout(r,120)); }
  throw new Error('timeout waiting for: ' + label + ' (phase=' + phase() + ')');
}
function assert(cond, msg){ if(!cond) throw new Error('assert failed: ' + msg); }
const ok = () => console.log('test successful');
const setv = (sel, v) => { const i = $(sel);
  const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
  s.call(i, v); i.dispatchEvent(new Event('input', {bubbles:true})); };
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_delivery_ui')
class TestDeliveryDriveThruUi(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.allow_manager_elevation', '1')
        cls.manager = cls.env['mezze.cashier'].create(
            {'name': 'Dalia Manager', 'code': 'DLMGR', 'role': 'manager'})
        cls.manager.set_pin('4321')
        Zone = cls.env['mezze.delivery.zone']
        vals = {'name': 'Zamalek', 'fee': 25.0, 'min_order': 50.0,
                'eta_minutes': 40, 'active': True}
        if 'config_id' in Zone._fields:
            vals['config_id'] = cls.pos_config.id
        if 'cod_allowed' in Zone._fields:
            vals['cod_allowed'] = True
        cls.zone = Zone.create(vals)
        cls.env.flush_all()

    # ---- order type ----------------------------------------------------------
    def test_01_order_type_control_is_present_and_switches(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $('[data-otype]'), 'order type control');
            const keys = $$('[data-otype]').map(b => b.dataset.otype);
            assert(keys.join(',') === 'eat_in,takeaway,delivery',
                   'Dine-in | Takeaway | Delivery, in that order (' + keys.join(',') + ')');
            assert($('[data-otype="eat_in"]').getAttribute('aria-pressed') === 'true',
                   'a counter order starts as dine-in');
            $('[data-otype="takeaway"]').click();
            await waitFor(() => $('[data-otype="takeaway"]').getAttribute('aria-pressed') === 'true',
                          'takeaway becomes the active choice');
            assert($('[data-otype="eat_in"]').getAttribute('aria-pressed') === 'false',
                   'exactly one choice is active');
            ok();
        """), login='admin')

    def test_02_delivery_needs_items_first(self):
        # An empty delivery is not a thing; say so rather than opening a form that
        # can only fail at the end.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $('[data-otype="delivery"]'), 'order type control');
            $('[data-otype="delivery"]').click();
            await new Promise(r => setTimeout(r, 800));
            assert(!$('[data-testid="mz-delivery-form"]'), 'no form for an empty order');
            assert($('[data-testid="mz-action-error"]'), 'the cashier is told why');
            ok();
        """), login='admin')

    def test_03_the_branch_decides_the_fee_and_the_minimum(self):
        # The till supplies zone + subtotal and DISPLAYS the answer. A one-item order
        # is under the 50 minimum, so the server refuses and Create stays disabled.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $('.mz-tile'), 'catalog');
            $('.mz-tile').click();
            await waitFor(() => $('.mz-line'), 'line');
            $('[data-otype="delivery"]').click();
            await waitFor(() => $('[data-testid="mz-delivery-form"]'), 'delivery form');
            const sel = $('[data-testid="mz-delivery-zone"]');
            sel.value = sel.options[1].value;
            sel.dispatchEvent(new Event('change', { bubbles: true }));
            await waitFor(() => $('[data-testid="mz-delivery-verdict"]'), 'server verdict');
            const verdict = $('[data-testid="mz-delivery-verdict"]').textContent;
            assert(/minimum/i.test(verdict),
                   'the refusal names the minimum (' + verdict + ')');
            setv('[data-testid="mz-delivery-phone"]', '+201000111222');
            setv('[data-testid="mz-delivery-address"]', '12 Sharia 26 July');
            await new Promise(r => setTimeout(r, 400));
            assert($('[data-testid="mz-delivery-create"]').disabled,
                   'Create stays disabled while the branch refuses the order');
            ok();
        """), login='admin')

    def test_04_an_eligible_order_shows_the_servers_fee_and_eta(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $('.mz-tile'), 'catalog');
            for (let i = 0; i < 6; i++) {
                $$('.mz-tile')[i % 3].click();
                await new Promise(r => setTimeout(r, 120));
            }
            await waitFor(() => $('.mz-line'), 'lines');
            $('[data-otype="delivery"]').click();
            await waitFor(() => $('[data-testid="mz-delivery-form"]'), 'delivery form');
            const sel = $('[data-testid="mz-delivery-zone"]');
            sel.value = sel.options[1].value;
            sel.dispatchEvent(new Event('change', { bubbles: true }));
            await waitFor(() => /25/.test(($('[data-testid="mz-delivery-verdict"]') || {}).textContent || ''),
                          "the zone's own fee is shown");
            const verdict = $('[data-testid="mz-delivery-verdict"]').textContent;
            assert(/40/.test(verdict), 'and its ETA (' + verdict + ')');
            ok();
        """), login='admin')

    # ---- drive-thru ----------------------------------------------------------
    def _lane_page(self):
        """The board as a signed-in operator gets it (the route is auth='user')."""
        self.authenticate('admin', 'admin')
        return self.url_open('/mezze/drivethru')

    def test_05_drivethru_has_a_real_route(self):
        r = self._lane_page()
        self.assertEqual(r.status_code, 200, r.text[:200])
        self.assertIn('mezze-boot', r.text, 'the page is served with a boot payload')

    def test_06_drivethru_never_takes_its_token_from_the_url(self):
        # A bearer token in a query string ends up in access logs, browser history
        # and any link an operator shares. The page must read the injected payload.
        r = self._lane_page()
        self.assertNotIn("Q.get('token')", r.text,
                         'the page no longer reads a token from the URL')
        start = r.text.index('id="mezze-boot"')
        boot = json.loads(r.text[r.text.index('>', start) + 1:r.text.index('</script>', start)])
        self.assertTrue(boot.get('ok'), boot)
        self.assertTrue(boot.get('token'), 'a token was minted for the lane')
        self.assertEqual(boot.get('config_id'), self.pos_config.id)

    def test_07_the_lane_token_is_stored_only_as_a_fingerprint(self):
        r = self._lane_page()
        start = r.text.index('id="mezze-boot"')
        boot = json.loads(r.text[r.text.index('>', start) + 1:r.text.index('</script>', start)])
        term = self.env['mezze.terminal'].sudo().with_context(active_test=False).search(
            [('identifier', '=', 'drivethru-%s' % self.pos_config.id)], limit=1)
        self.assertTrue(term, 'a dedicated drive-thru terminal exists')
        self.assertEqual(term.role, 'terminal')
        # the plaintext must not be recoverable from the database
        stored = json.dumps(term.read()[0], default=str)
        self.assertNotIn(boot['token'], stored,
                         'the plaintext token is not stored on the record')

    def test_08_the_page_is_never_cached(self):
        # The response carries a freshly minted bearer token.
        r = self._lane_page()
        self.assertIn('no-store', r.headers.get('Cache-Control', ''))
