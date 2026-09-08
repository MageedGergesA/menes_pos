"""The bill has to say how much of it is tax.

The cart's totals block has always CONTAINED a Subtotal row, guarded by
`hasBreakdown`, which read:

    const sub = this.order.subtotal;
    return typeof sub === "number" && ...

`order.subtotal` was never defined anywhere on the order store. `typeof undefined
=== "number"` is false, so the guard was false on every order ever rung up and the
row it guards has never once rendered. The Register showed a single Total and
named no tax at all — on a market where the VAT line is not decoration.

The amounts here are not arithmetic this browser invented. `price_excl` and
`price_incl` come from the server's own `compute_all`, already carrying the
branch's fiscal position, price-included flags and multiple taxes; the client
only apportions that difference across the lines and groups it. Where a product
carries two taxes the difference is their COMBINED amount, so those group under a
joined label rather than being split by guesswork.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase

_JS = r"""
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
async function waitFor(fn, label, ms=20000){
  const t0 = Date.now();
  while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){}
    await new Promise(r=>setTimeout(r,120)); }
  throw new Error('timeout waiting for: ' + label);
}
function assert(c,m){ if(!c) throw new Error('assert failed: ' + m); }
const ok = () => console.log('test successful');
const handle = async () => { await waitFor(() => window.__mezzeCashier, 'handle');
                             return window.__mezzeCashier; };
/** Add the TAXED product by name. Clicking the first tile added whichever
 *  product the fixture happened to order first — usually an untaxed one — so the
 *  breakdown was legitimately empty and the test read as a failure of the
 *  feature rather than of its own aim. */
async function addNamed(name){
  await waitFor(() => $$('.mz-tile').length > 0, 'catalog');
  const t = $$('.mz-tile').find(el => el.innerText.includes(name));
  assert(t, 'the taxed product "' + name + '" is on the menu');
  t.click();
  await waitFor(() => $$('.mz-line').length > 0, 'a line');
}
"""


def _js(body, taxed="Mezze"):
    head = _JS + "\nconst TAXED = " + json.dumps(taxed) + ";\n"
    return head + "(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser')
class TestVatLine(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A taxed catalogue: without one there is nothing to break down, and a test
        # on a tax-free menu would pass while saying nothing.
        tax = cls.env['account.tax'].create({
            'name': 'VAT 14%', 'amount': 14.0, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'price_include_override': 'tax_included',
            'company_id': cls.pos_config.company_id.id})
        cls.tax = tax
        cls.product.write({'available_in_pos': True, 'list_price': 114.0,
                           'taxes_id': [(6, 0, [tax.id])]})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.shared = 'vatline-token'
        ICP.set_param('mezze_bridge.api_token', cls.shared)
        ICP.set_param('mezze_bridge.api_security', 'observe')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.env.flush_all()

    def test_00_bootstrap_returns_the_branchs_tax_LIST(self):
        """The defect underneath this feature, and the reason it stayed hidden.

        `/bootstrap` binds `taxes` to the branch's tax list, then the product loop
        fifty lines below rebound the SAME name to a recordset for `compute_all`.
        After the loop the payload shipped the last product's recordset in place
        of the list. Nothing read the field, so nothing complained — until this
        feature became its first consumer and the till failed to boot with
        "(list || []).map is not a function".

        A shadowed loop variable is invisible in review and silent in production.
        This asserts the SHAPE, which is what nobody was checking.
        """
        r = self.url_open('/mezze/api/v1/bootstrap',
                          data=json.dumps({'token': self.shared,
                                           'config_id': self.pos_config.id}),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        res = r.json()
        self.assertTrue(res.get('ok'), res)
        taxes = res.get('taxes')
        self.assertIsInstance(taxes, list, 'the tax payload is not a list: %r' % (taxes,))
        self.assertTrue(taxes, 'a taxed catalogue reported no taxes at all')
        for t in taxes:
            self.assertIsInstance(t, dict, 'a tax entry is not a record: %r' % (t,))
            for key in ('id', 'name', 'amount'):
                self.assertIn(key, t, 'the tax entry cannot name itself: %r' % (t,))

    def test_01_the_tax_row_is_on_the_bill(self):
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => $('.mz-workspace'), 'register');
            await addNamed(TAXED);
            await new Promise(r => setTimeout(r, 400));
            const rows = $$('[data-testid=mz-tax-row]');
            assert(rows.length >= 1, 'the bill names no tax at all');
            const txt = rows.map(r => r.innerText.replace(/\n/g,' ')).join(' | ');
            assert(/VAT/i.test(txt), 'the tax row is not named by the branch: ' + txt);
            ok();
        """, self.product.name), login='admin')

    def test_02_the_numbers_add_up(self):
        """Subtotal + tax must equal the total the Charge button asks for. A
        breakdown that does not reconcile is worse than none: it invites the
        cashier to argue with the screen in front of a guest."""
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => $('.mz-workspace'), 'register');
            await addNamed(TAXED);
            const h = await handle();
            await new Promise(r => setTimeout(r, 300));
            const o = h.order;
            const tax = o.taxBreakdown.reduce((s,r) => s + r.amount, 0);
            const diff = Math.abs((o.subtotal + tax) - o.grandTotal);
            assert(diff < 0.011,
                   'subtotal ' + o.subtotal + ' + tax ' + tax
                   + ' != total ' + o.grandTotal);
            assert(tax > 0, 'a taxed catalogue reported no tax');
            ok();
        """, self.product.name), login='admin')

    def test_03_a_tax_free_menu_shows_no_tax_row(self):
        """The guard has to discriminate. A row that always appears would put a
        zero VAT line on a bill that carries no VAT."""
        self.env['product.template'].browse(
            self.product.product_tmpl_id.id).write({'taxes_id': [(5, 0, 0)]})
        self.env.flush_all()
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => $('.mz-workspace'), 'register');
            await addNamed(TAXED);
            await new Promise(r => setTimeout(r, 400));
            assert($$('[data-testid=mz-tax-row]').length === 0,
                   'a tax-free menu was given a tax line');
            ok();
        """, self.product.name), login='admin')

    def test_04_the_discount_reduces_the_tax_with_it(self):
        """Tax follows the money actually charged. Taxing a price nobody pays
        overstates what the branch owes."""
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => $('.mz-workspace'), 'register');
            await addNamed(TAXED);
            const h = await handle();
            await new Promise(r => setTimeout(r, 300));
            const before = h.order.taxBreakdown.reduce((s,r)=>s+r.amount, 0);
            h.order.state.lines[0].discount = 50;
            h.order._touch();
            await new Promise(r => setTimeout(r, 300));
            const after = h.order.taxBreakdown.reduce((s,r)=>s+r.amount, 0);
            assert(after < before - 0.01,
                   'a 50% discount did not reduce the tax (' + before + ' -> ' + after + ')');
            ok();
        """, self.product.name), login='admin')
