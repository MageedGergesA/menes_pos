"""Every icon the Register asks for must exist in the font that ships with it.

The design draws its controls with Material Symbols. The face has been in our
bundle since P3 and no production surface referenced it — we drew text and emoji
glyphs instead. Turning it on is not a one-line change, and the reasons are both
invisible until they ship:

1. **The subsetter stripped the GSUB ligature table.** The normal way to write one
   of these icons is `<span class="ms">skillet</span>`, which relies on a ligature
   turning the letters into a glyph. With GSUB gone that renders the literal word
   "skillet" on the button. So `static/src/shell/icons.js` addresses them by
   CODEPOINT instead.
2. **The subset is partial.** It carries 150 codepoints; the design's Register asks
   for icons that are not among them. Those keep a text fallback rather than
   degrading to a word.

Both failure modes look fine in review and wrong on a till. This pins them:
every codepoint the client references is checked against the actual `.woff2`
that ships beside it, so re-subsetting the font can never quietly blank an icon,
and adding a name to the map without adding the glyph fails here rather than in a
branch.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

_HERE = os.path.dirname(os.path.abspath(__file__))
_ADDON = os.path.dirname(_HERE)
_FONT = os.path.join(_ADDON, 'static', 'fonts', 'MaterialSymbolsRounded-subset.woff2')
_ICONS = os.path.join(_ADDON, 'static', 'src', 'shell', 'icons.js')


@tagged('post_install', '-at_install', 'mezze_invariants')
class TestIconSubset(TransactionCase):

    def _font_codepoints(self):
        try:
            from fontTools.ttLib import TTFont
        except ImportError:
            self.skipTest('fontTools not installed in this environment')
        return set(TTFont(_FONT).getBestCmap().keys())

    def _declared(self):
        """name -> codepoint, parsed out of the client's own map."""
        src = open(_ICONS, encoding='utf-8').read()
        block = re.search(r'export const ICONS = \{(.*?)\n\};', src, re.S)
        self.assertTrue(block, 'the icon map is no longer parseable')
        return {m.group(1): int(m.group(2), 16)
                for m in re.finditer(r'(\w+):\s*"\\u([0-9A-Fa-f]{4})"', block.group(1))}

    def test_01_the_font_ships(self):
        self.assertTrue(os.path.exists(_FONT),
                        'the icon font referenced by foundation.css is not in the addon')

    def test_02_every_declared_icon_is_in_the_font(self):
        """The one that matters. A codepoint the font lacks renders as a blank box
        on the button — and nothing else fails."""
        cps = self._font_codepoints()
        declared = self._declared()
        self.assertTrue(declared, 'the icon map is empty')
        missing = {n: hex(c) for n, c in declared.items() if c not in cps}
        self.assertFalse(
            missing,
            'these icons are referenced by the Register and are NOT in the '
            'shipped subset: %r' % missing)

    def test_03_the_map_covers_every_icon_the_design_uses(self):
        """The map is not a hand-picked selection any more — it is the whole design
        vocabulary, and it has to stay that way.

        This replaced an earlier test that guarded a MISSING list, back when the
        subset carried 150 codepoints and could draw barely half of what the
        Register alone asked for. The face is now vendored in full, instanced and
        re-subset to exactly the icons the prototype renders, so there is nothing
        left to be missing — and the useful invariant became the opposite one:
        every icon the DESIGN uses must be addressable, or a screen built later
        silently falls back to a text glyph and nobody notices until it ships.

        Read from the prototype itself rather than a copied list, so adopting a new
        design screen cannot quietly outgrow the font.
        """
        proto = os.path.join(_ADDON, 'docs', 'design-handoff', 'Mezze POS v3.dc.html')
        if not os.path.exists(proto):
            self.skipTest('the design bundle is not vendored in this checkout')
        body = open(proto, encoding='utf-8').read()
        used = set(re.findall(r'class="ms"[^>]*>([a-z0-9_]+)', body))
        self.assertGreater(len(used), 50,
                           'the prototype scan found almost nothing — the regex has rotted')
        declared = self._declared()
        # Names the prototype renders that our map cannot address at all.
        missing = sorted(n for n in used if n not in declared)
        self.assertFalse(
            missing,
            'the design renders these and the client cannot address them: %r' % missing)

    def test_04_the_client_never_uses_the_ligature_form(self):
        """`class="ms"` with a word inside is the form that breaks silently on this
        font, because the subsetter removed GSUB. It must not creep back in."""
        offenders = []
        for root, _dirs, files in os.walk(os.path.join(_ADDON, 'static', 'src')):
            for name in files:
                if not name.endswith(('.xml', '.js')):
                    continue
                path = os.path.join(root, name)
                body = open(path, encoding='utf-8').read()
                # Strip comments first. This file's own docstring QUOTES the
                # broken form to explain why it is banned, and an assertion that
                # searched raw text would trip on the explanation — or, worse,
                # pass only because of where a comment happened to sit. That is
                # the same vacuity this suite has already been bitten by twice.
                code = re.sub(r'/\*.*?\*/', '', body, flags=re.S)
                code = re.sub(r'(?<![:\w])//[^\n]*', '', code)
                code = re.sub(r'<!--.*?-->', '', code, flags=re.S)
                if re.search(r'class="ms"[^>]*>\s*[a-z_]{3,}', code):
                    offenders.append(os.path.relpath(path, _ADDON))
        self.assertFalse(
            offenders,
            'these use the Material Symbols LIGATURE form, which this subset '
            'cannot resolve and which renders the icon name as text: %r' % offenders)
