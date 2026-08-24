# -*- coding: utf-8 -*-
"""What the reporting workspaces put on screen.

``ops``, ``manager``, ``reports`` and ``hq`` each call a rich endpoint and each
declared ``rows: null`` with no entry in the component's ``stats``, so the template
fell through every branch and rendered NOTHING on a SUCCESSFUL call. That is worse
than an unbuilt feature: the data arrived and the manager was shown an empty panel.

**Where that fix is actually verified.** The derivation is pure and lives in
``static/src/cashier/summary_panels.js``; the HOOT suite exercises it directly (see
``Mezze Cashier · summary workspaces``), including the regression itself — a payload
with figures in it can no longer produce a blank panel.

It is NOT verified through this file, and the reason is worth writing down. A
Register terminal does not hold ``REPORTS_READ`` — correctly; a till is not a
reporting station — so on the surface these tests can drive, every one of these
workspaces answers with a permission notice and never reaches the rendering path at
all. An earlier version of this file asserted the panels through the browser and
passed while the renderer was disabled, because it was quietly taking the denial
branch every time. That is the failure mode this docstring exists to prevent
recurring.

What a browser CAN prove here is the other half, and it matters just as much: the
denial is explained rather than silent.
"""
from odoo.tests import tagged

from .common import MezzeHttpCase

_JS = r"""
const $ = (s) => document.querySelector(s);
async function waitFor(fn, label, ms=20000){
  const t0 = Date.now();
  while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){}
    await new Promise(r=>setTimeout(r,120)); }
  throw new Error('timeout waiting for: ' + label);
}
function assert(c,m){ if(!c) throw new Error('assert failed: ' + m); }
const settled = () => $('.mz-wsp') && !$('.mz-spinner');
"""


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_workspaces')
class TestReportingWorkspaces(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.env.flush_all()

    def _text(self, ws, body):
        self.browser_js('/mezze/pos?ws=%s' % ws, _JS + """
            (async () => {
            %s
            })().catch(e => { console.error(e.message || e); });
        """ % body, login='admin')

    def test_01_a_workspace_a_till_may_not_read_says_so(self):
        # Not a blank panel and not a raw error code: a sentence naming the
        # capability and where to go instead.
        self._text('hq', r"""
            await waitFor(settled, 'the workspace to settle');
            const t = $('.mz-wsp').innerText || '';
            assert(t.trim().length > 20,
                   'the workspace is blank rather than explaining itself: ' + t);
            assert(/not available|capability|manager|back office/i.test(t),
                   'the refusal does not say why: ' + t);
            assert(!/permission_denied|403|traceback/i.test(t),
                   'an internal code reached the screen: ' + t);
            console.log('test successful');
        """)

    def test_02_every_reporting_workspace_answers_something(self):
        # The property that failed before: whatever the outcome — figures, an empty
        # state, or a refusal — the panel is never silent.
        for ws in ('ops', 'manager', 'reports', 'hq'):
            self._text(ws, r"""
                await waitFor(settled, 'the workspace to settle');
                const t = ($('.mz-wsp').innerText || '').trim();
                assert(t.length > 0, 'this workspace rendered nothing at all');
                console.log('test successful');
            """)
