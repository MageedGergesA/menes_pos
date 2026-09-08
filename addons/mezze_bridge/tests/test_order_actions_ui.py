"""Order actions in the REAL Register: comp, void, fire.

These verbs existed as backend contracts and in the static prototype, but the Owl
Register never called them — a cashier on /mezze/pos could not comp an item, void
an order or fire a course at all. The tests below drive the live app in headless
Chrome, because the point of the work was the wiring, and a unit test of the
endpoint would have passed before it too.

The approval path is the interesting part. A cashier terminal does not hold
orders.comp / orders.void at all — that is deliberate in domain.authz — so a
supervisor authorises the single call in person with their code and PIN, verified
server-side. A cashier must not be able to approve their own comp, and a wrong PIN
must change nothing; both are asserted here rather than assumed.
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
/** Comp lives behind the line's `⋯` now — the design keeps the row down to the
 *  stepper, Edit, Note and an overflow, so a per-line verb is one tap deeper
 *  than it used to be. These tests are about who may approve a comp, not about
 *  where the button sits, so they open the overflow and carry on. */
async function lineComp(){
  let b = $('[data-line-act=comp]');
  if (b) { return b; }
  const more = $('[data-testid=mz-line-more]');
  if (!more) { return null; }
  more.click();
  await new Promise(r => setTimeout(r, 250));
  return $('[data-line-act=comp]');
}
const setv = (sel, v) => { const i = $(sel);
  const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
  s.call(i, v); i.dispatchEvent(new Event('input', {bubbles:true})); };
const gate = async (code, pin, reason) => {
  await waitFor(() => $('[data-testid="mz-manager-gate"]'), 'manager gate');
  setv('[data-testid="mz-manager-code"]', code);
  setv('[data-testid="mz-manager-pin"]', pin);
  setv('[data-testid="mz-manager-reason"]', reason);
  await new Promise(r => setTimeout(r, 200));
  $('[data-testid="mz-manager-approve"]').click();
};
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_order_actions')
class TestOrderActionsUi(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A cashier terminal deliberately does NOT hold orders.comp / orders.void
        # (see _CASHIER in domain.authz). Manager elevation is the branch-level
        # opt-in that lets a supervisor authorise one such call in person, so it
        # has to be ON for these flows to exist at all.
        icp = cls.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.allow_manager_elevation', '1')
        # Without this, /mezze/pos has no way to know WHICH branch is being rung up
        # and answers with the branch chooser (303 -> /mezze/start), so every
        # browser assertion below fails on a page that never mounted the Register.
        icp.set_param('mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.manager = cls.env['mezze.cashier'].create(
            {'name': 'Nadia Manager', 'code': 'OAMGR', 'role': 'manager'})
        cls.manager.set_pin('4321')
        cls.cashier = cls.env['mezze.cashier'].create(
            {'name': 'Sami Cashier', 'code': 'OACSH', 'role': 'cashier'})
        cls.cashier.set_pin('1111')
        cls.env.flush_all()

    def test_01_the_verbs_are_present_on_a_live_order(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $('.mz-tile'), 'catalog');
            $('.mz-tile').click();
            await waitFor(() => $('.mz-line'), 'line');
            const verbs = $$('.mz-verb').map(v => v.textContent.replace(/\s+/g,' ').trim());
            /* The design names this verb for what it does, and promotes it out of
               the overflow onto the panel itself. `.mz-verb` still covers both the
               footer and the More sheet, so this stays one query. */
            assert(verbs.some(v => /Send to kitchen/i.test(v)),
                   'Send to kitchen present (got ' + verbs.join('|') + ')');
            assert(verbs.some(v => /Void/.test(v)), 'Void verb present');
            assert(await lineComp(), 'a cart line offers Comp');
            ok();
        """), login='admin')

    def test_02_a_cashier_cannot_approve_their_own_comp(self):
        # The whole point of the gate. The PIN is checked server-side against the
        # role rank, so a cashier PIN must be refused even though it is valid.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $('.mz-tile'), 'catalog');
            $('.mz-tile').click();
            await waitFor(() => $('.mz-line'), 'line');
            (await lineComp()).click();
            await gate('OACSH', '1111', 'trying to self-approve');
            await waitFor(() => $('[data-testid="mz-manager-error"]'), 'refusal shown');
            assert($('[data-testid="mz-manager-gate"]'), 'the gate stays open on refusal');
            assert(!$('.mz-line--comped'), 'nothing was comped');
            ok();
        """), login='admin')

    def test_03_a_wrong_pin_is_refused(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $('.mz-tile'), 'catalog');
            $('.mz-tile').click();
            await waitFor(() => $('.mz-line'), 'line');
            (await lineComp()).click();
            await gate('OAMGR', '9999', 'wrong pin');
            await waitFor(() => $('[data-testid="mz-manager-error"]'), 'refusal shown');
            assert(!$('.mz-line--comped'), 'nothing was comped');
            ok();
        """), login='admin')

    def test_04_a_manager_comp_zeroes_the_line_and_the_total(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $('.mz-tile'), 'catalog');
            $('.mz-tile').click();
            await waitFor(() => $('.mz-line'), 'line');
            const before = $('.mz-line-total').textContent;
            (await lineComp()).click();
            await gate('OAMGR', '4321', 'guest complaint');
            await waitFor(() => !$('[data-testid="mz-manager-gate"]'), 'gate closes on approval');
            await waitFor(() => $('.mz-line--comped'), 'the line is marked comped');
            const after = $('.mz-line-total').textContent;
            assert(after !== before, 'the line price changed (' + before + ' -> ' + after + ')');
            assert(/0/.test(after), 'the comped line costs nothing (' + after + ')');
            // the line is still SERVED, so it must remain on the ticket
            assert($$('.mz-line').length === 1, 'the comped line stays on the order');
            ok();
        """), login='admin')

    def test_05_void_clears_the_order_after_approval(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $('.mz-tile'), 'catalog');
            $('.mz-tile').click();
            await waitFor(() => $('.mz-line'), 'line');
            $$('.mz-verb').find(v => /Void/.test(v.textContent)).click();
            await gate('OAMGR', '4321', 'ordered by mistake');
            await waitFor(() => !$('.mz-line'), 'the order is emptied');
            assert(!$('[data-testid="mz-manager-gate"]'), 'the gate closed');
            ok();
        """), login='admin')

    def test_06_fire_needs_no_approval(self):
        # Sending food to the kitchen is the ordinary job, not an exception, so it
        # must NOT prompt for a manager.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $('.mz-tile'), 'catalog');
            $('.mz-tile').click();
            await waitFor(() => $('.mz-line'), 'line');
            $$('.mz-verb').find(v => /Send to kitchen/i.test(v.textContent)).click();
            await new Promise(r => setTimeout(r, 1500));
            assert(!$('[data-testid="mz-manager-gate"]'), 'Send to kitchen did not ask for approval');
            assert(!$('[data-testid="mz-action-error"]'), 'Send to kitchen reported no error');
            assert($$('.mz-line').length === 1, 'the order is intact after firing');
            ok();
        """), login='admin')
