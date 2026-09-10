"""CONV-3 — product configuration is ONE contract, applied by both surfaces.

"No onion, extra cheese, large" is the same question wherever an operator is
standing, and until this pass Mezze answered it in one place only. The drive-thru
had the whole capability; the Register had none of it — and the gap was not just a
missing dialog, it was a chain of five:

  1. the product map dropped `modifiers` from /bootstrap, so the till never knew a
     product was configurable;
  2. a tap always added straight to the cart;
  3. cart lines had no attribute values, and `_findLine` merged on product + note —
     its own comment said modifiers make lines distinct, and nothing implemented it;
  4. `toSyncLines()` could not carry a choice even if one existed;
  5. `/orders/sync` was a second, modifier-blind line builder beside `_build_lines`,
     so a configured line would have reached the kitchen as a plain one.

What is asserted here is that the RULES are shared as code (design/product-config.js),
that the PANEL is shared as one stylesheet, and that the Register now carries a
configuration end to end — including through the write path, where the consequence
of getting it wrong is a wrong plate rather than a wrong pixel.
"""
import json
import os
import re

from odoo.tests import tagged

from .common import MezzeHttpCase

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(ADDON, 'static', 'design', 'product-config.js')
PANEL = os.path.join(ADDON, 'static', 'design', 'product-config.css')
DRIVETHRU = os.path.join(ADDON, 'static', 'drivethru.html')
CASHIER_CSS = os.path.join(ADDON, 'static', 'src', 'cashier', 'cashier.css')
STORE = os.path.join(ADDON, 'static', 'src', 'cashier', 'order_store.js')
MANIFEST = os.path.join(ADDON, '__manifest__.py')

_PRELUDE = r"""
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
async function waitFor(fn, label, ms=20000){
  const t0 = Date.now();
  while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){} await new Promise(r=>setTimeout(r,120)); }
  throw new Error('timeout waiting for: ' + label);
}
function assert(cond, msg){ if(!cond) throw new Error('assert failed: ' + msg); }
const ok = () => console.log('test successful');
const PC = () => window.MezzeProductConfig;
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_conv3')
class TestProductConfigSource(MezzeHttpCase):
    """One definition of the rules, and no surface keeping its own copy."""
    fixture_profile = 'POS'

    def _read(self, path):
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def test_01_the_rules_are_one_shared_module(self):
        js = self._read(RULES)
        for fn in ('groups', 'isConfigurable', 'defaultSelection', 'selectionFrom',
                   'toggle', 'isOn', 'chosen', 'extraPrice', 'missingRequired',
                   'isComplete', 'lineKey', 'describe'):
            self.assertIn(fn + ':', js, '%s belongs to the shared contract' % fn)
        self.assertIn('MezzeProductConfig', js)
        # pure: the rules may not touch the DOM, the network or a framework
        for forbidden in ('document.', 'fetch(', 'window.addEventListener', '@odoo-module'):
            self.assertNotIn(forbidden, js,
                             'the rules must stay pure — found %r' % forbidden)

    def test_02_both_surfaces_load_the_same_rules(self):
        self.assertIn('design/product-config.js', self._read(DRIVETHRU),
                      'the drive-thru board loads the shared rules')
        manifest = self._read(MANIFEST)
        self.assertIn('design/product-config.js', manifest,
                      'the cashier bundle loads the shared rules')
        self.assertLess(manifest.index('design/product-config.js'),
                        manifest.index('static/src/cashier/**'),
                        'the rules must load BEFORE the app that consumes them')

    def test_03_neither_surface_reimplements_the_rules(self):
        """A second copy of a rule is how two screens start disagreeing."""
        dt = self._read(DRIVETHRU)
        # the board delegates; it does not carry its own arithmetic any more
        self.assertIn('PC.toggle(', dt)
        self.assertIn('PC.extraPrice(', dt)
        self.assertIn('PC.missingRequired(', dt)
        self.assertIn('PC.lineKey(', dt)
        # the old private implementations are gone
        self.assertNotIn("cur=(cur.length===1&&cur[0]===id)?[]:[id]", dt,
                         'the drive-thru still toggles on its own')
        self.assertNotRegex(dt, r"function cfgExtra\(\)\{[^}]*price_extra",
                            'the drive-thru still sums price_extra on its own')

    def test_04_the_panel_is_one_definition(self):
        css = self._read(PANEL)
        for rule in ('.mz-cfg{', '.mz-cfg__group{', '.mz-cfg__opts{', '.mz-cfg-opt{',
                     '.mz-cfg__warn{', '.mz-cfg__foot{'):
            self.assertIn(rule, css, '%s belongs to the canonical panel' % rule)
        # the drive-thru keeps ONLY placement, and the cashier keeps nothing
        dt_rules = re.findall(r'\.mz-cfg[^{]*\{([^}]*)\}', self._read(DRIVETHRU))
        for body in dt_rules:
            self.assertNotIn('background:', body,
                             'the board is restyling the shared panel: %s' % body)
        self.assertNotIn('.mz-cfg', self._read(CASHIER_CSS),
                         'the cashier bundle must not define the panel')
        # and the retired private classes are really gone
        self.assertNotIn('.cfgopt', self._read(DRIVETHRU))

    def test_05_the_store_keys_lines_by_configuration(self):
        store = self._read(STORE)
        self.assertIn('_lineKey', store, 'the store has a line identity')
        self.assertIn('attribute_value_ids', store,
                      'and the identity includes the chosen values')
        # the old product+note-only lookup is gone
        self.assertNotIn("l.product.id === productId && (l.note || \"\") === (note || \"\")",
                         store, 'the store still merges on product + note alone')


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_conv3')
class TestRegisterConfigurator(MezzeHttpCase):
    """The Register can now sell a configured product — end to end.

    The fixture is a product configured through Odoo's own POS-time attributes, and
    it serves BOTH surfaces: the last test here drives the drive-thru with it, so a
    single broken rule in the shared module fails a BEHAVIOURAL test on each side
    rather than a source-shape check on one.
    """
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product.write({'available_in_pos': True, 'list_price': 100.0, 'taxes_id': [(5, 0, 0)]})
        cls.pos_config.write({'payment_method_ids': [(4, cls.cash_payment_method.id)]})
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        sess = cls.pos_config.current_session_id
        if sess:
            if sess.state == 'opening_control':
                try:
                    sess.set_opening_control(0, None)
                except Exception:  # noqa: BLE001
                    pass
            if sess.state != 'opened':
                sess.sudo().write({'state': 'opened'})

        # A product configured through ODOO's OWN model: POS-time attributes
        # (create_variant='no_variant') with real price_extra. No invented menu.
        Attr = cls.env['product.attribute'].sudo()
        size = Attr.create({'name': 'Portion', 'create_variant': 'no_variant',
                            'display_type': 'radio'})
        extras = Attr.create({'name': 'Extras', 'create_variant': 'no_variant',
                              'display_type': 'multi'})
        Val = cls.env['product.attribute.value'].sudo()
        regular = Val.create({'name': 'Regular', 'attribute_id': size.id})
        large = Val.create({'name': 'Large', 'attribute_id': size.id})
        cheese = Val.create({'name': 'Extra cheese', 'attribute_id': extras.id})
        # a POS category is required by the menu domain, and the taxes are cleared
        # explicitly AFTER create because the company default is applied on create
        categ = cls.env['pos.category'].sudo().search([], limit=1) \
            or cls.env['pos.category'].sudo().create({'name': 'CONV3 Test'})
        cls.configurable = cls.env['product.product'].sudo().create({
            'name': 'Mezze Test Burger', 'available_in_pos': True,
            'list_price': 50.0, 'pos_categ_ids': [(6, 0, categ.ids)],
        })
        cls.configurable.write({'taxes_id': [(5, 0, 0)]})
        tmpl = cls.configurable.product_tmpl_id
        cls.env['product.template.attribute.line'].sudo().create([{
            'product_tmpl_id': tmpl.id, 'attribute_id': size.id,
            'value_ids': [(6, 0, [regular.id, large.id])],
        }, {
            'product_tmpl_id': tmpl.id, 'attribute_id': extras.id,
            'value_ids': [(6, 0, [cheese.id])],
        }])
        ptavs = tmpl.attribute_line_ids.product_template_value_ids
        cls.v_large = ptavs.filtered(lambda v: v.product_attribute_value_id == large)
        cls.v_cheese = ptavs.filtered(lambda v: v.product_attribute_value_id == cheese)
        cls.v_regular = ptavs.filtered(lambda v: v.product_attribute_value_id == regular)
        cls.v_large.price_extra = 5.0
        cls.v_cheese.price_extra = 3.0
        cls.env.flush_all()

    def test_10_a_configurable_product_asks_and_a_plain_one_does_not(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            assert(PC(), 'the shared rules are loaded');
            // a plain product goes straight in — one tap, nothing opens
            const plain = $$('.mz-tile').find(t => !/Mezze Test Burger/.test(t.textContent));
            plain.click();
            await waitFor(() => $$('.mz-line').length === 1, 'a line');
            assert(!$('.mz-cfg'), 'a product with no choices never opens the panel');
            // a configurable one asks
            $$('.mz-tile').find(t => /Mezze Test Burger/.test(t.textContent)).click();
            await waitFor(() => $('.mz-cfg'), 'the configurator');
            assert($$('.mz-line').length === 1, 'and does NOT add before it is answered');
            assert($$('.mz-cfg__group').length === 2, 'both groups are offered');
            ok();
        """), login='admin')

    def test_11_a_required_group_blocks_add_until_it_is_answered(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            $$('.mz-tile').find(t => /Mezze Test Burger/.test(t.textContent)).click();
            await waitFor(() => $('.mz-cfg'), 'the configurator');
            // a single-choice group starts answered, so the common order is one confirm
            assert($$('.mz-cfg-opt--on').length === 1, 'the implied choice is pre-selected');
            assert(!$('.mz-cfg__add').disabled, 'so Add is available immediately');
            // clear it and the panel says which group, on the group itself
            $('.mz-cfg-opt--on').click();
            await waitFor(() => $('.mz-cfg__add').disabled, 'Add is blocked');
            assert($('.mz-cfg__warn'), 'a reason is shown');
            assert(/Portion/.test($('.mz-cfg__warn').textContent),
                   'and it names the group: ' + $('.mz-cfg__warn').textContent);
            assert($('.mz-cfg__gh--need'), 'the group itself is marked');
            // answering it releases the button
            $$('.mz-cfg-opt')[1].click();
            await waitFor(() => !$('.mz-cfg__add').disabled, 'Add is released');
            ok();
        """), login='admin')

    def test_12_the_live_total_follows_the_choices(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            $$('.mz-tile').find(t => /Mezze Test Burger/.test(t.textContent)).click();
            await waitFor(() => $('.mz-cfg__price-v'), 'the configurator');
            const money = () => parseFloat($('.mz-cfg__price-v').textContent.replace(/[^0-9.]/g, ''));
            const base = money();
            $$('.mz-cfg-opt').find(b => /Large/.test(b.textContent)).click();
            await waitFor(() => money() !== base, 'the total moved');
            const withLarge = money();
            assert(Math.abs(withLarge - base - 5) < 0.01,
                   'Large adds its real price_extra (' + base + ' -> ' + withLarge + ')');
            $$('.mz-cfg-opt').find(b => /Extra cheese/.test(b.textContent)).click();
            await waitFor(() => money() !== withLarge, 'the total moved again');
            assert(Math.abs(money() - withLarge - 3) < 0.01, 'Extra cheese adds its own');
            ok();
        """), login='admin')

    def test_13_the_configuration_reaches_the_line(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            $$('.mz-tile').find(t => /Mezze Test Burger/.test(t.textContent)).click();
            await waitFor(() => $('.mz-cfg'), 'the configurator');
            $$('.mz-cfg-opt').find(b => /Large/.test(b.textContent)).click();
            $$('.mz-cfg-opt').find(b => /Extra cheese/.test(b.textContent)).click();
            $('.mz-cfg__add').click();
            await waitFor(() => $$('.mz-line').length === 1, 'the line');
            assert(!$('.mz-cfg'), 'the panel closes on confirm');
            const note = $('.mz-line .mz-line-note');
            assert(note, 'the line shows what was chosen');
            assert(/Large/.test(note.textContent) && /Extra cheese/.test(note.textContent),
                   'both choices are on the line: ' + note.textContent);
            assert($('[data-testid=mz-line-edit]'), 'and the choice can be corrected');
            ok();
        """), login='admin')

    def test_14_configuration_is_part_of_line_identity(self):
        """The whole point: a no-onion burger is not the same thing as a plain one."""
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            const tile = () => $$('.mz-tile').find(t => /Mezze Test Burger/.test(t.textContent));
            const configure = async (extra) => {
                tile().click();
                await waitFor(() => $('.mz-cfg'), 'the configurator');
                if (extra) {
                    $$('.mz-cfg-opt').find(b => /Extra cheese/.test(b.textContent)).click();
                    await new Promise(r => setTimeout(r, 120));
                }
                $('.mz-cfg__add').click();
                await waitFor(() => !$('.mz-cfg'), 'confirmed');
            };
            await configure(true);
            await waitFor(() => $$('.mz-line').length === 1, 'the first line');
            await configure(true);                       // the SAME configuration
            await new Promise(r => setTimeout(r, 400));
            assert($$('.mz-line').length === 1,
                   'an identical configuration merges (' + $$('.mz-line').length + ' lines)');
            assert($('.mz-stepper__value').textContent.trim() === '2', 'to a quantity');
            await configure(false);                      // a DIFFERENT configuration
            await waitFor(() => $$('.mz-line').length === 2, 'a distinct second line');
            const notes = $$('.mz-line .mz-line-note').map(n => n.textContent);
            assert(notes.length === 2 && notes[0] !== notes[1],
                   'and the two lines say different things: ' + notes.join(' | '));
            ok();
        """), login='admin')

    def test_15_a_choice_can_be_corrected_without_starting_again(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            $$('.mz-tile').find(t => /Mezze Test Burger/.test(t.textContent)).click();
            await waitFor(() => $('.mz-cfg'), 'the configurator');
            $$('.mz-cfg-opt').find(b => /Extra cheese/.test(b.textContent)).click();
            $('.mz-cfg__add').click();
            await waitFor(() => $$('.mz-line').length === 1, 'the line');
            assert(/Extra cheese/.test($('.mz-line-note').textContent), 'cheese is on it');

            $('[data-testid=mz-line-edit]').click();
            await waitFor(() => $('.mz-cfg'), 'the configurator reopened');
            // it reopens on EXACTLY what the line carries
            const on = $$('.mz-cfg-opt--on').map(b => b.textContent.trim());
            assert(on.some(t => /Extra cheese/.test(t)), 'the existing choice is restored: ' + on.join(','));
            assert(/save/i.test($('.mz-cfg__add').textContent), 'and the action says Save');
            // remove the cheese and save
            $$('.mz-cfg-opt').find(b => /Extra cheese/.test(b.textContent)).click();
            $('.mz-cfg__add').click();
            await waitFor(() => !$('.mz-cfg'), 'saved');
            await new Promise(r => setTimeout(r, 300));
            assert($$('.mz-line').length === 1, 'still ONE line, corrected — not two');
            const note = $('.mz-line .mz-line-note');
            assert(!note || !/Extra cheese/.test(note.textContent),
                   'and the removed option is gone: ' + (note ? note.textContent : '(none)'));
            ok();
        """), login='admin')

    def test_17_the_lane_applies_the_same_identity_rule(self):
        """The same rule, exercised through the OTHER surface's UI.

        The drive-thru's client-side line identity was covered only by a source-shape
        assertion — which a negative control exposed: breaking the shared rule failed
        the Register behaviourally and the lane only textually. This drives the lane's
        real configurator and asserts the same merge/split behaviour.
        """
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the lane catalogue');
            const tile = () => $$('.mz-tile').find(t => /Mezze Test Burger/.test(t.textContent));
            assert(tile(), 'the configurable product is on the lane menu too');
            const configure = async (withCheese) => {
                tile().click();
                await waitFor(() => !$('#cfg').hidden, 'the configurator');
                if (withCheese) {
                    $$('#cfg .mz-cfg-opt').find(b => /Extra cheese/.test(b.textContent)).click();
                    await new Promise(r => setTimeout(r, 150));
                }
                $('#cfgadd').click();
                await waitFor(() => $('#cfg').hidden, 'confirmed');
            };
            await configure(true);
            await waitFor(() => $$('.mz-line').length === 1, 'the first line');
            await configure(true);                        // the SAME configuration
            await new Promise(r => setTimeout(r, 400));
            assert($$('.mz-line').length === 1,
                   'an identical configuration merges (' + $$('.mz-line').length + ')');
            assert($('.mz-stepper__value').textContent.trim() === '2', 'to a quantity');
            await configure(false);                       // a DIFFERENT configuration
            await waitFor(() => $$('.mz-line').length === 2, 'a distinct second line');
            const notes = $$('.mz-line .mz-line-note').map(n => n.textContent.trim());
            assert(new Set(notes).size === notes.length,
                   'and the two lines say different things: ' + notes.join(' | '));
            ok();
        """), login='admin')

    def test_16_the_choice_travels_to_the_server(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            $$('.mz-tile').find(t => /Mezze Test Burger/.test(t.textContent)).click();
            await waitFor(() => $('.mz-cfg'), 'the configurator');
            $$('.mz-cfg-opt').find(b => /Large/.test(b.textContent)).click();
            $('.mz-cfg__add').click();
            await waitFor(() => $$('.mz-line').length === 1, 'the line');
            const store = window.__mezzeCashier && window.__mezzeCashier.order;
            assert(store, 'the debug handle exposes the store');
            const sync = store.toSyncLines();
            assert(sync.length === 1, 'one line to sync');
            assert(Array.isArray(sync[0].attribute_value_ids) && sync[0].attribute_value_ids.length,
                   'and it carries the chosen values: ' + JSON.stringify(sync[0]));
            ok();
        """), login='admin', debug=True)


    def test_18_the_till_quotes_the_price_it_is_about_to_charge(self):
        """The figure read to the guest and the figure charged are ONE number.

        The first cut of this pass shipped the values but not their surcharge into the
        line: the panel previewed $58, the cart line and the Charge button said $50,
        and only the payment screen — after the guest had been quoted — showed the
        server's $58. The server was never wrong; the till was, at the only moment the
        guest can hear it. Asserted end to end: panel -> line -> order total -> the
        server's own amount_total on the payment screen.
        """
        self.browser_js('/mezze/pos', _js(r"""
            const money = (el) => parseFloat(el.textContent.replace(/[^0-9.]/g, ''));
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            $$('.mz-tile').find(t => /Mezze Test Burger/.test(t.textContent)).click();
            await waitFor(() => $('.mz-cfg'), 'the configurator');
            $$('.mz-cfg-opt').find(b => /Large/.test(b.textContent)).click();
            $$('.mz-cfg-opt').find(b => /Extra cheese/.test(b.textContent)).click();
            await new Promise(r => setTimeout(r, 150));
            const previewed = money($('.mz-cfg__price-v'));
            assert(Math.abs(previewed - 58) < 0.01, 'the panel previews 50 + 5 + 3: ' + previewed);

            $('.mz-cfg__add').click();
            await waitFor(() => $$('.mz-line').length === 1, 'the line');
            const lineTotal = money($('.mz-line .mz-line-total'));
            assert(Math.abs(lineTotal - previewed) < 0.01,
                   'the LINE costs what the panel previewed, not the list price: ' + lineTotal);
            const orderTotal = money($('.mz-total-amt'));
            assert(Math.abs(orderTotal - previewed) < 0.01,
                   'and so does the order total: ' + orderTotal);
            assert(new RegExp(previewed.toFixed(2)).test($('.mz-btn--charge').textContent),
                   'the Charge button quotes it too: ' + $('.mz-btn--charge').textContent);

            // and the SERVER agrees — this is the number the guest is actually asked for
            $('.mz-btn--charge').click();
            await waitFor(() => $('.mz-amt-row--total .mz-amt'), 'the payment screen');
            const charged = money($('.mz-amt-row--total .mz-amt'));
            assert(Math.abs(charged - previewed) < 0.01,
                   'quoted ' + previewed + ' but charging ' + charged);
            ok();
        """), login='admin')


    def test_19_the_primary_action_is_the_wide_one_at_the_till(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            $$('.mz-tile').find(t => /Mezze Test Burger/.test(t.textContent)).click();
            await waitFor(() => $('.mz-cfg__add'), 'the configurator');
            const add = $('.mz-cfg__add').getBoundingClientRect().width;
            const cancel = $('.mz-cfg__cancel').getBoundingClientRect().width;
            const foot = $('.mz-cfg__foot').getBoundingClientRect().width;
            assert(add > cancel,
                   'Add must be the wider control (add=' + add + ' cancel=' + cancel + ')');
            assert(add >= 100,
                   'Add must not be squeezed to a sliver (add=' + add + ')');
            assert(cancel < foot * 0.5,
                   'Cancel must not take the row (cancel=' + cancel + ' foot=' + foot + ')');
            ok();
        """), login='admin')

    def test_19b_the_primary_action_is_the_wide_one_in_the_lane(self):
        """The same foot, on the surface where it actually broke.

        The lane's own `.btn{width:100%}` ties with the shared `.mz-cfg__acts > *`
        on specificity and is declared later in its page, so after the panel was
        extracted the lane rendered Cancel across the whole row and squeezed Add
        into a ~40px sliver — the button an operator hits on every single order.
        The shared rule now names both children, so source order cannot decide it.
        """
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the lane catalogue');
            $$('.mz-tile').find(t => /Mezze Test Burger/.test(t.textContent)).click();
            await waitFor(() => !$('#cfg').hidden, 'the configurator');
            const add = $('#cfgadd').getBoundingClientRect().width;
            const cancel = $('#cfgcancel').getBoundingClientRect().width;
            const foot = $('.mz-cfg__foot').getBoundingClientRect().width;
            assert(add > cancel,
                   'Add must be the wider control (add=' + add + ' cancel=' + cancel + ')');
            assert(add >= 100,
                   'Add must not be squeezed to a sliver (add=' + add + ')');
            assert(cancel < foot * 0.5,
                   'Cancel must not take the row (cancel=' + cancel + ' foot=' + foot + ')');
            ok();
        """), login='admin')


    #: One specification, run against each surface in its OWN test.
    #:
    #: This was a single test looping over both surfaces, and it was the only test
    #: in the class to start two browsers inside one method. Every ``browser_js``
    #: call constructs a fresh ChromeBrowser and stops it on the way out, so a
    #: second call in the same method races the first browser's teardown: the new
    #: Chrome is spawned, its CDP endpoint is not answering yet, and setup dies in
    #: ``Network.setCookie`` before a line of this script runs — leaving an orphaned
    #: Chrome for the harness to reap. It failed that way once in a full run and
    #: never in isolation, which is the shape of a race and not of a defect.
    #:
    #: Split, each launch gets its own test lifecycle, with the harness's teardown
    #: and child-process reaping in between. It also makes a failure say WHICH
    #: surface broke, which "both surfaces" never did.
    #:
    #: Keep the assertions here rather than inlining them twice: the claim is that
    #: the two surfaces interrupt the cashier the SAME way, and that is only really
    #: asserted if both are measured by one script.
    _MODAL_JS = r"""
                const PANEL = "%s", SCRIM = "%s";
                await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
                $$('.mz-tile').find(t => /Mezze Test Burger/.test(t.textContent)).click();
                await waitFor(() => $(PANEL) && !$(PANEL).hidden, 'the configurator');
                const s = $(SCRIM), p = $(PANEL);
                assert(getComputedStyle(s).position === 'fixed', 'the scrim is fixed to the viewport');
                const sr = s.getBoundingClientRect(), pr = p.getBoundingClientRect();
                assert(sr.width >= innerWidth - 1 && sr.height >= innerHeight - 1,
                       'and covers it (' + sr.width + 'x' + sr.height + ')');
                assert(pr.width < sr.width * 0.6,
                       'the panel is a dialog, not a pane takeover (' + pr.width + ' of ' + sr.width + ')');
                assert(pr.left > 4 && pr.right < sr.width - 4, 'it floats clear of both edges');
                // the workspace is still THERE behind it — that is the point of a modal
                assert($('.mz-grid').getBoundingClientRect().width > 0, 'the catalogue is still laid out');
                // a click on the dim area backs out; a click inside must not
                p.click();
                await new Promise(r => setTimeout(r, 200));
                assert(!$(PANEL).hidden, 'clicking inside the panel keeps it open');
                s.click();
                // the Register REMOVES its panel (Owl t-if), the lane hides it — both are closed
                await waitFor(() => !$(PANEL) || $(PANEL).hidden, 'the scrim click closed it');
                ok();
    """

    def _assert_asks_in_a_modal(self, page, panel, scrim):
        """Asking for a size is an interruption, and it must read like one.

        The lane used to DOCK the configurator: absolutely positioned across the whole
        catalogue pane, which reads as navigating to another screen mid-order. It now
        floats in the same canonical scrim the Register uses. Asserted as geometry and
        behaviour, not as a class name: a scrim that covers the viewport, a panel far
        narrower than it, the workspace still laid out behind, and a click on the dim
        area backing out.
        """
        self.browser_js(page, _js(self._MODAL_JS % (panel, scrim)), login='admin')

    def test_19c_the_till_asks_in_a_modal_over_the_workspace(self):
        self._assert_asks_in_a_modal('/mezze/pos', '.mz-cfg', '.mz-modal-scrim')

    def test_19d_the_lane_asks_in_a_modal_over_the_workspace(self):
        self._assert_asks_in_a_modal('/mezze/drivethru', '#cfg', '#cfgscrim')


@tagged('post_install', '-at_install', 'mezze_conv3')
class TestSyncRecordsConfiguration(MezzeHttpCase):
    """The write path: a configured line must reach the ORDER, not just the screen."""
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'conv3-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session()
        Attr = self.env['product.attribute'].sudo()
        size = Attr.create({'name': 'Size', 'create_variant': 'no_variant',
                            'display_type': 'radio'})
        Val = self.env['product.attribute.value'].sudo()
        small = Val.create({'name': 'Small', 'attribute_id': size.id})
        big = Val.create({'name': 'Big', 'attribute_id': size.id})
        categ = self.env['pos.category'].sudo().search([], limit=1) \
            or self.env['pos.category'].sudo().create({'name': 'CONV3 Sync'})
        self.prod = self.env['product.product'].sudo().create({
            'name': 'Sync Test Dish', 'available_in_pos': True,
            'list_price': 40.0, 'pos_categ_ids': [(6, 0, categ.ids)]})
        self.prod.write({'taxes_id': [(5, 0, 0)]})
        self.env['product.template.attribute.line'].sudo().create({
            'product_tmpl_id': self.prod.product_tmpl_id.id,
            'attribute_id': size.id, 'value_ids': [(6, 0, [small.id, big.id])]})
        ptavs = self.prod.product_tmpl_id.attribute_line_ids.product_template_value_ids
        self.v_small = ptavs.filtered(lambda v: v.product_attribute_value_id == small)
        self.v_big = ptavs.filtered(lambda v: v.product_attribute_value_id == big)
        self.v_big.price_extra = 7.0
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='conv3-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:200]}

    def _sync(self, lines, uuid):
        return self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'lines': lines, 'draft': True})

    def test_20_sync_records_the_chosen_values_and_the_surcharge(self):
        code, res = self._sync([{'product_id': self.prod.id, 'qty': 1,
                                 'attribute_value_ids': [self.v_big.id]}], 'conv3-sync-1')
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('ok'), res)
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'conv3-sync-1')], limit=1)
        self.assertTrue(order, 'the order was created')
        line = order.lines[0]
        self.assertEqual(line.attribute_value_ids, self.v_big,
                         'the chosen value is ON the order line')
        self.assertAlmostEqual(line.price_extra, 7.0, 2, 'and its surcharge is recorded')
        self.assertAlmostEqual(line.price_unit, 47.0, 2,
                               'the unit price is base + the SERVER-side surcharge')
        self.assertIn('Big', line.full_product_name or '',
                      'and the line names what was chosen: %r' % line.full_product_name)

    def test_21_a_plain_line_is_unchanged(self):
        """The path most orders take must not move."""
        code, res = self._sync([{'product_id': self.prod.id, 'qty': 2}], 'conv3-sync-2')
        self.assertEqual(code, 200, res)
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'conv3-sync-2')], limit=1)
        line = order.lines[0]
        self.assertFalse(line.attribute_value_ids, 'no values')
        self.assertAlmostEqual(line.price_unit, 40.0, 2, 'and no surcharge')

    def test_22_sync_rejects_over_selecting_a_single_choice_group(self):
        """A browser is not an authority on how many sizes a dish can have."""
        code, res = self._sync([{'product_id': self.prod.id, 'qty': 1,
                                 'attribute_value_ids': [self.v_small.id, self.v_big.id]}],
                               'conv3-sync-3')
        self.assertFalse(res.get('ok'),
                         'two values from one single-choice group must be refused: %s' % res)
        self.assertFalse(self.env['pos.order'].sudo().search([('uuid', '=', 'conv3-sync-3')]),
                         'and nothing may be persisted')

    def test_23_a_value_from_another_product_is_not_priced(self):
        """Values are filtered to the product's OWN template before they count."""
        other = self.env['product.product'].sudo().create({
            'name': 'Other Dish', 'available_in_pos': True, 'list_price': 10.0,
            'taxes_id': [(5, 0, 0)]})
        code, res = self._sync([{'product_id': other.id, 'qty': 1,
                                 'attribute_value_ids': [self.v_big.id]}], 'conv3-sync-4')
        self.assertEqual(code, 200, res)
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'conv3-sync-4')], limit=1)
        line = order.lines[0]
        self.assertFalse(line.attribute_value_ids,
                         "another product's option may not attach")
        self.assertAlmostEqual(line.price_unit, 10.0, 2,
                               'and it may not add its surcharge either')
