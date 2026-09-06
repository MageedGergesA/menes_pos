"""The rail lock — design v3 `tillBarred`.

A branch can keep its Servers off the till. The design's rule, verbatim:

    TILL_ONLY=['register','orders','drivethru','eod','ops','exc','tax','chan',
               'inv','commissary']
    tillBarred(id){ return on && TILL_ONLY.indexOf(id)>=0 && role==='Server'; }

It is a STAFFING policy, not a capability: the same person signed in as a
cashier reaches the till normally. That distinction is the reason these tests
assert the trigger is a SETTING and a ROLE, and never a capability — an earlier
reading of this feature had it gating on REPORTS_READ, which would have been a
different feature wearing the same icon.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

from ..domain import settings_catalog

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIL_JS = os.path.join(ROOT, 'static/src/shell/rail.js')
RAIL_XML = os.path.join(ROOT, 'static/src/shell/rail.xml')


def _rail_src():
    with open(RAIL_JS, encoding='utf-8') as f:
        return f.read()


@tagged('post_install', '-at_install', 'mezze_shell')
class TestRailLock(TransactionCase):

    def test_01_the_policy_is_a_branch_field_and_defaults_off(self):
        """It lives on pos.config, NOT in the 101-setting catalog.

        That catalog is a frozen authoritative mirror of Settings.html, pinned by
        an import-time assertion and by the bootstrap tests. Adding a 102nd id
        broke module load — correctly. The policy is branch scope by its own
        wording ("THIS branch keeps servers off the till") and belongs here.
        """
        field = self.env['pos.config']._fields.get('mezze_servers_off_till')
        self.assertTrue(field, "the branch policy field is missing")
        self.assertEqual(field.type, 'boolean')
        # Ask the ORM what a NEW branch would get, rather than inspecting
        # whatever pos.config the database happens to contain — the tests here
        # are hermetic and must not discover ambient records
        # (see TestNoArbitraryDiscovery).
        defaults = self.env['pos.config'].default_get(['mezze_servers_off_till'])
        self.assertFalse(defaults.get('mezze_servers_off_till'),
                         "a branch must opt IN to locking its staff out")
        self.assertEqual(len({c[0] for c in settings_catalog.CATALOG_101}), 101,
                         "the frozen catalog was widened")

    def test_01b_the_boot_payload_tells_the_till(self):
        """A till cannot honour a policy it was never told about."""
        # TWO boot payloads exist: the /bootstrap API's config block AND the
        # cashier PAGE's own smaller object. The Owl shell only ever sees the
        # second — putting the policy solely in the first left the rail blind.
        page = open(os.path.join(ROOT, 'controllers/cashier.py'), encoding='utf-8').read()
        self.assertIn("'servers_off_till'", page,
                      "the cashier page boot does not carry the policy")
        shell = open(os.path.join(ROOT, 'static/src/cashier/root.js'), encoding='utf-8').read()
        self.assertIn('this.boot.branch', shell,
                      "the shell reads a payload it is not served")

    def test_02_the_rail_reads_that_setting_and_the_role(self):
        src = _rail_src()
        self.assertIn('serversOffTill', src, "the rail never reads the policy")
        self.assertIn("toLowerCase() === 'server'", src,
                      "the rail must bar the Server role specifically")

    def test_03_the_locked_set_matches_the_design(self):
        """Our rail keys differ from the prototype's, but the SET of destinations
        must be the same idea: the till and the day's money."""
        src = _rail_src()
        m = re.search(r'TILL_ONLY\s*=\s*\[(.*?)\]', src, re.S)
        self.assertTrue(m, "TILL_ONLY is gone")
        keys = set(re.findall(r"'([a-z]+)'", m.group(1)))
        for expected in ('register', 'orders', 'drivethru', 'ops', 'reports', 'close'):
            self.assertIn(expected, keys,
                          "%r must be closed to a barred Server" % expected)
        # The policy's whole point: these stay OPEN.
        for open_key in ('floor', 'kds', 'book', 'queue'):
            self.assertNotIn(open_key, keys,
                             "%r must stay open — the design keeps their own "
                             "shift, tables and handheld reachable" % open_key)

    def test_04_a_barred_item_is_shown_locked_not_hidden(self):
        src = _rail_src()
        self.assertIn('this.icons.lock', src, "a barred item keeps no lock icon")
        self.assertIn('out.href = false', src, "a barred item is still navigable")
        with open(RAIL_XML, encoding='utf-8') as f:
            xml = f.read()
        self.assertIn('mz-rail__item--barred', xml, "the template cannot show it")
        self.assertIn('aria-disabled', xml, "a locked control must say so to AT")

    def test_05_pressing_it_refuses_rather_than_navigating(self):
        src = _rail_src()
        self.assertIn('ev.preventDefault()', src, "a barred item still navigates")
        self.assertIn('Not on your role', src, "the refusal is unnamed")
        self.assertIn('This branch keeps servers off the till', src,
                      "the refusal does not explain itself")

    def test_06_the_lock_is_a_policy_not_a_capability(self):
        """Guards the mistake this feature was nearly built as."""
        src = _rail_src()
        window = src[src.index('barred(key)'):src.index('barred(key)') + 400]
        for cap in ('REPORTS_READ', 'capability', 'permission', '403'):
            self.assertNotIn(cap, window,
                             "the lock is gating on %r — it is a staffing "
                             "policy, not a capability" % cap)

    def test_07_the_refusal_is_translated(self):
        with open(os.path.join(ROOT, 'i18n/ar.po'), encoding='utf-8') as f:
            po = f.read()
        for en in ('Not on your role',
                   'This branch keeps servers off the till. '
                   'Ask a cashier or a manager.',
                   'Keep servers off the till'):
            self.assertIn('msgid "%s"' % en, po, "%r has no Arabic" % en)
