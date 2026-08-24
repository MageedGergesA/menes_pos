# -*- coding: utf-8 -*-
"""Keeping an order through a crash.

A cart lived in memory and nowhere else, so a tablet whose OS reclaimed the tab, a
browser that fell over, or a cashier who hit refresh lost twelve items with a guest
standing at the counter. Park existed, but Park is a decision somebody has to make
BEFORE the thing they could not predict.

**This is not offline mode and must not be read as one.** What is kept is the
cashier's INTENT — which products, how many, which modifiers, whose seat — and never
money. No total, no tax, no payment is stored or restored: a recovered cart is
re-synced and the server prices it exactly as it would have priced it the first
time. A stored total would create a second source of truth for money on the one
device that must never have one.

**What these tests do and do not prove.** Odoo's ``browser_js`` gives every script a
fresh browser context — verified, not assumed — so a real page reload cannot be
driven across two calls: the storage is gone by the second one. An earlier draft of
this file was written that way and three of its tests passed for that reason and no
other, which is worse than failing. Each test below therefore runs in ONE context and
simulates the restart the way the restart does: the in-memory cart is discarded
without touching storage, and the app's own recovery path is invoked. What is
exercised is the recovery logic; the boot CALL SITE is one line
(``_recoverDraft()`` in ``bootstrap``) and is not covered here.
"""
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
const handle = async () => { await waitFor(() => window.__mezzeCashier, 'debug handle');
                             return window.__mezzeCashier; };
const draftKeys = () => Object.keys(localStorage).filter(k => k.startsWith('mzDraft.'));

async function addLines(n){
  await waitFor(() => $$('.mz-tile').length > 0, 'catalog');
  for (let i = 0; i < (n || 1); i++) {
    $$('.mz-tile')[0].click();
    await new Promise(r => setTimeout(r, 140));
  }
  await waitFor(() => $$('.mz-line').length > 0, 'a line in the cart');
}

/** What a crash does, and nothing else: the memory goes, the storage stays.
 *  Deliberately NOT order.clear() — that forgets the draft, which is the whole
 *  point of clear() and the opposite of a crash. */
function crash(h){
  h.order.state.lines.splice(0, h.order.state.lines.length);
  h.root.state.orderUuid = null;
  h.root.state.recovered = "";
}
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_draft')
class TestDraftRecovery(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product.write({'available_in_pos': True, 'list_price': 40.0,
                           'taxes_id': [(5, 0, 0)]})
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.env.flush_all()

    # ── what is written ──────────────────────────────────────────────────
    def test_01_a_cart_is_backed_up_as_it_is_rung_up(self):
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            localStorage.clear();
            await addLines(2);
            const keys = draftKeys();
            assert(keys.length === 1, 'expected one draft, got ' + keys.length);
            const saved = JSON.parse(localStorage.getItem(keys[0]));
            assert(saved.lines.length >= 1, 'the draft holds no lines');
            assert(saved.lines[0].qty >= 1, 'the draft holds no quantity');
            ok();
        """), login='admin')

    def test_02_no_money_is_ever_written_down(self):
        # THE rule. A stored total is a second source of truth for money on the one
        # device that must never have one.
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            localStorage.clear();
            await addLines(1);
            const raw = localStorage.getItem(draftKeys()[0]) || '';
            for (const forbidden of ['amount_total', 'price_subtotal', 'tax', 'payment', 'paid']) {
                assert(!raw.includes(forbidden),
                       'the draft carries "' + forbidden + '": ' + raw);
            }
            ok();
        """), login='admin')

    def test_03_an_emptied_cart_leaves_nothing_behind(self):
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            localStorage.clear();
            await addLines(1);
            assert(draftKeys().length === 1, 'a draft was written');
            const h = await handle();
            h.order.clear();
            await new Promise(r => setTimeout(r, 200));
            assert(draftKeys().length === 0, 'a cleared cart left a draft behind');
            ok();
        """), login='admin')

    def test_04_every_edit_is_backed_up_not_just_the_first(self):
        # A backup that only catches the first tap is one that is missing on exactly
        # the path nobody thought about.
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            localStorage.clear();
            await addLines(1);
            const h = await handle();
            const key = draftKeys()[0];
            h.order.setQty(h.order.state.lines[0], 7);
            await new Promise(r => setTimeout(r, 150));
            assert(JSON.parse(localStorage.getItem(key)).lines[0].qty === 7,
                   'a quantity change was not backed up');
            h.order.setNote(h.order.state.lines[0], 'no onions');
            await new Promise(r => setTimeout(r, 150));
            assert(JSON.parse(localStorage.getItem(key)).lines[0].note === 'no onions',
                   'a note was not backed up');
            ok();
        """), login='admin')

    # ── recovery ─────────────────────────────────────────────────────────
    def test_10_a_crash_gets_the_order_back(self):
        # The whole point: twelve items and a guest at the counter.
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            localStorage.clear();
            await addLines(3);
            const h = await handle();
            const lines = h.order.state.lines.length;
            const qty = h.order.state.lines[0].qty;
            crash(h);
            assert(h.order.state.lines.length === 0, 'the cart really was lost');
            h.root._recoverDraft();
            await new Promise(r => setTimeout(r, 250));
            assert(h.order.state.lines.length === lines,
                   'recovered ' + h.order.state.lines.length + ', expected ' + lines);
            assert(h.order.state.lines[0].qty === qty, 'the quantity did not survive');
            ok();
        """), login='admin')

    def test_11_the_cashier_is_told_it_was_recovered(self):
        # A cart that reappears without explanation is one they have to audit
        # against the guest in front of them.
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            localStorage.clear();
            await addLines(1);
            const h = await handle();
            crash(h);
            h.root._recoverDraft();
            await waitFor(() => $('[data-testid="mz-recovered"]'), 'the recovery notice');
            assert($('[data-testid="mz-recovered"]').textContent.trim().length > 0,
                   'the notice says nothing');
            ok();
        """), login='admin')

    def test_12_an_untouched_till_shows_no_notice(self):
        # Guard against a notice that appears on every boot and stops being read.
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            localStorage.clear();
            const h = await handle();
            h.root._recoverDraft();
            await new Promise(r => setTimeout(r, 300));
            assert(!$('[data-testid="mz-recovered"]'),
                   'a clean till claimed to have recovered something');
            assert(h.order.state.lines.length === 0, 'a clean till has an order in it');
            ok();
        """), login='admin')

    def test_13_a_draft_from_another_shift_is_not_offered(self):
        # Somebody else's shift, and possibly somebody else's drawer.
        #
        # The SCOPE is changed, not the key string. An earlier version of this test
        # renamed the stored key and passed with the scoping removed entirely — it
        # was checking its own string edit rather than the rule.
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            localStorage.clear();
            await addLines(2);
            const h = await handle();
            assert(draftKeys().length === 1, 'a draft was written for this shift');
            crash(h);
            // the next shift opens on the same till
            h.order.setDraftScope(h.root.boot.config_id, 999999,
                                  () => h.root.state.orderUuid);
            h.root._recoverDraft();
            await new Promise(r => setTimeout(r, 300));
            assert(h.order.state.lines.length === 0,
                   'a cart from a closed shift came back');
            assert(!$('[data-testid="mz-recovered"]'), 'and it announced itself');
            ok();
        """), login='admin')

    def test_13b_a_draft_from_another_branch_is_not_offered(self):
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            localStorage.clear();
            await addLines(1);
            const h = await handle();
            crash(h);
            h.order.setDraftScope(987654, h.root.state.sessionId,
                                  () => h.root.state.orderUuid);
            h.root._recoverDraft();
            await new Promise(r => setTimeout(r, 300));
            assert(h.order.state.lines.length === 0,
                   "another branch's cart came back");
            ok();
        """), login='admin')

    def test_14_the_recovered_cart_keeps_its_order_uuid(self):
        # Otherwise one guest gets two bills.
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            localStorage.clear();
            await addLines(1);
            const h = await handle();
            h.root.state.orderUuid = 'draft-uuid-under-test';
            h.order.saveDraft();
            crash(h);
            h.root._recoverDraft();
            await new Promise(r => setTimeout(r, 250));
            assert(h.root.state.orderUuid === 'draft-uuid-under-test',
                   'the recovered cart forgot which order it was: '
                   + h.root.state.orderUuid);
            ok();
        """), login='admin')

    def test_15_a_withdrawn_product_is_dropped_and_said(self):
        # Silently handing back a SHORTER order is worse than not recovering it.
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            localStorage.clear();
            await addLines(1);
            const h = await handle();
            const key = draftKeys()[0];
            const saved = JSON.parse(localStorage.getItem(key));
            // a line for something that is not on the menu any more
            saved.lines.push(Object.assign({}, saved.lines[0], {product_id: 99999999}));
            localStorage.setItem(key, JSON.stringify(saved));
            crash(h);
            h.root._recoverDraft();
            await waitFor(() => $('[data-testid="mz-recovered"]'), 'the notice');
            const said = $('[data-testid="mz-recovered"]').textContent;
            assert(/1/.test(said), 'the notice does not say what was left out: ' + said);
            assert(h.order.state.lines.length === 1,
                   'a product that is gone from the menu was resurrected');
            ok();
        """), login='admin')

    def test_16_an_authoritative_order_beats_a_draft(self):
        # A table's real order is the truth; the draft is stale by definition and
        # must not overwrite it — nor double it by running twice.
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            localStorage.clear();
            await addLines(2);
            const h = await handle();
            const n = h.order.state.lines.length;
            h.root._recoverDraft();
            await new Promise(r => setTimeout(r, 250));
            assert(h.order.state.lines.length === n,
                   'recovery ran over a live cart: ' + h.order.state.lines.length);
            assert(!$('[data-testid="mz-recovered"]'),
                   'it announced a recovery that never happened');
            ok();
        """), login='admin')

    def test_17_the_seat_survives_the_crash(self):
        # Whose burger it is is part of the intent, not part of the money.
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            localStorage.clear();
            await addLines(1);
            const h = await handle();
            h.order.setSeat(h.order.state.lines[0], 4);
            await new Promise(r => setTimeout(r, 150));
            crash(h);
            h.root._recoverDraft();
            await new Promise(r => setTimeout(r, 250));
            assert(h.order.state.lines[0].seat === 4,
                   'the seat was lost: ' + h.order.state.lines[0].seat);
            ok();
        """), login='admin')
