"""Which overlay wins when two are open.

Every dialog in this app shared one z-index, so the winner was whichever the
template happened to render last. That is harmless for a confirm box and not
harmless for the MANAGER APPROVAL prompt: it is asked for BY another modal — a
comp, a void, a discount over the limit — so the modal most likely to be on
screen beside it is exactly the one that could cover it. A manager cannot approve
what they cannot read, and a tap that lands on the layer underneath approves
nothing while looking like it did.

The design states the order explicitly (MEZZE_DESIGN_TOKENS.json → zIndex, where
managerApproval is the highest at 40 and the only one marked `position: fixed`).
These tests pin the ORDER, not the numbers — ours live in a different range, and
a test that asserted 40 would fail for a reason nobody cares about.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

_ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _css(*parts):
    return open(os.path.join(_ADDON, 'static', *parts), encoding='utf-8').read()


@tagged('post_install', '-at_install', 'mezze_invariants')
class TestOverlayStacking(TransactionCase):

    def _ladder(self):
        """name -> number, read from the tokens rather than from each rule."""
        src = _css('design', 'foundation.css')
        return {m.group(1): int(m.group(2))
                for m in re.finditer(r'--mz-z-(\w+):\s*(\d+)', src)}

    def test_01_the_ladder_is_declared_once(self):
        ladder = self._ladder()
        for name in ('sheet', 'modal', 'tender', 'giftcard', 'approval'):
            self.assertIn(name, ladder,
                          'the overlay ladder does not define %r: %r' % (name, ladder))

    def test_02_approval_sits_above_every_other_overlay(self):
        """The one the design is explicit about."""
        ladder = self._ladder()
        top = ladder['approval']
        for name, value in ladder.items():
            if name == 'approval':
                continue
            self.assertGreater(
                top, value,
                'the approval prompt (%s) does not outrank %r (%s) — the modal that '
                'asked for it could cover it' % (top, name, value))

    def test_03_the_order_matches_the_design(self):
        """sheet < modal < tender < giftcard < approval."""
        ladder = self._ladder()
        order = ['sheet', 'modal', 'tender', 'giftcard', 'approval']
        values = [ladder[k] for k in order]
        self.assertEqual(values, sorted(values),
                         'the ladder is out of the design order: %r' % dict(zip(order, values)))

    def test_04_the_approval_backdrop_actually_claims_the_top(self):
        """A ladder nothing references is a comment. The approval dialog must carry
        the modifier that reads the top rung."""
        comp = _css('design', 'components.css')
        self.assertRegex(
            comp, r'\.mz-modal-backdrop--approval\{[^}]*z-index:var\(--mz-z-approval',
            'no rule raises the approval backdrop to the top of the ladder')
        markup = open(os.path.join(_ADDON, 'static', 'src', 'cashier', 'root.xml'),
                      encoding='utf-8').read()
        gate = re.search(r'<div t-if="state\.managerGate"[^>]*class="([^"]*)"', markup)
        self.assertTrue(gate, 'the manager-approval dialog is no longer recognisable')
        self.assertIn('mz-modal-backdrop--approval', gate.group(1),
                      'the approval dialog does not claim the top rung: %r' % gate.group(1))

    def test_05_no_dialog_hardcodes_a_z_index_past_the_ladder(self):
        """A stray number beats the ladder silently, which is how this started."""
        offenders = []
        for rel in (('design', 'components.css'), ('src', 'cashier', 'cashier.css')):
            src = _css(*rel)
            body = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
            for m in re.finditer(r'z-index:\s*(\d+)', body):
                if int(m.group(1)) >= self._ladder()['approval']:
                    offenders.append((os.path.join(*rel), m.group(1)))
        self.assertFalse(
            offenders,
            'these sit at or above the approval rung with a literal number: %r' % offenders)
