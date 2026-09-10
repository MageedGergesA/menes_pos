# -*- coding: utf-8 -*-
"""Two surfaces that shipped with no colour, found by looking at them.

Both defects were the absence of a rule rather than a wrong one, which is why no
behavioural test caught either: the markup rendered, the buttons worked, and the
only thing wrong was that a person could not read them.

**The upsell chips had no stylesheet at all.** ``mz-upsell`` appeared exactly once
in the addon — in ``cart.xml``, the markup — and in no CSS file anywhere. The
chips therefore rendered as default browser buttons, grey with black text, inside
a dark Register, with the name and the reason running together as
"Shish TawookGoes with Tabbouleh".

**The storefront's dish names were invisible in dark mode.** ``.prod`` is a
``<button>``, and a button does not inherit ``color`` — it takes the user agent's
black. The card set a themed ``background`` and left the text at that default, so
the dish name measured **1.38:1** against the card. In light mode the same
omission measures 21:1, because black on white happens to look right, which is
how it shipped. ``.pdesc`` and ``.pp`` escaped it only because they set their own
colour.

Guarded structurally: the failure was a missing declaration, so the test that
catches it is one that reads the source. Contrast itself is measured in the
browser during a real run, not here.
"""
import re

from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open


@tagged('post_install', '-at_install', 'mezze_styling')
class TestUpsellIsStyled(TransactionCase):

    def _css(self):
        with file_open('mezze_bridge/static/src/cashier/cashier.css', 'r') as fh:
            return fh.read()

    def _chip_block(self):
        """The .mz-upsell__chip declarations, or a clean failure saying they are
        missing — a stylesheet with no such rule should read as a failed
        expectation, not a ValueError from a string search."""
        css = self._css().replace(' {', '{')
        marker = '.mz-upsell__chip{'
        self.assertIn(marker, css, 'the upsell chip has no style rule at all')
        block = css[css.index(marker) + len(marker):]
        return block[:block.index('}')]

    def test_01_the_upsell_chips_have_styles_at_all(self):
        """THE bug: the class existed only in the markup."""
        css = self._css()
        for sel in ('.mz-upsell', '.mz-upsell__chip',
                    '.mz-upsell__n', '.mz-upsell__w'):
            self.assertIn(sel + '{', css.replace(' {', '{'),
                          '%s has no styles: the chips fall back to default browser '
                          'buttons — grey on black — inside a dark Register' % sel)

    def test_02_the_chip_takes_the_theme_rather_than_the_browser_default(self):
        """A button with no background/colour of its own is the actual failure."""
        block = self._chip_block()
        bg = re.search(r'background\s*:\s*var\(\s*(--mz-[a-z0-9-]+)', block)
        self.assertTrue(bg, 'the chip does not take its background from the theme')
        self.assertIn('color:var(--mz-', block.replace(' ', ''),
                      'the chip does not take its colour from the theme')

    def test_03_the_name_and_the_reason_are_not_run_together(self):
        """They are two spans with no separator in the markup, so the layout has to
        put them on separate lines — otherwise it reads 'Shish TawookGoes with…'."""
        block = self._chip_block()
        self.assertIn('flex-direction:column', block.replace(' ', ''),
                      'the name and its reason render on one line with nothing '
                      'between them')

    def test_04_the_chip_is_keyboard_visible(self):
        css = self._css()
        self.assertIn('.mz-upsell__chip:focus-visible', css.replace(' {', '{'),
                      'the chip has no focus ring')


@tagged('post_install', '-at_install', 'mezze_styling')
class TestStorefrontCardTakesTheTheme(TransactionCase):

    def _shop(self):
        with file_open('mezze_bridge/static/shop.html', 'r') as fh:
            return fh.read()

    def _rule(self, src, selector):
        """Every declaration block whose selector list mentions this class, joined.

        A class is styled by more than one rule — `.chip` also appears in a shared
        `touch-action` rule — so reading only the first match answers the wrong
        question and fails on a page that is perfectly fine.
        """
        css = src[src.index('<style>'):src.index('</style>')]
        out = []
        for m in re.finditer(r'([^{}]+)\{([^}]*)\}', css):
            sels = [x.strip() for x in m.group(1).split(',')]
            if any(x == selector or x.startswith(selector + ':')
                   or x.endswith(' ' + selector) for x in sels):
                out.append(m.group(2))
        self.assertTrue(out, 'no rule styles %s at all' % selector)
        return ' ; '.join(out)

    def test_10_the_product_card_sets_a_text_colour(self):
        """THE bug. `.prod` is a <button>, which does NOT inherit color: it takes
        the UA's black. With only a themed background set, the dish name rendered
        black on a near-black card in dark mode."""
        src = self._shop()
        self.assertIn("createElement('button'); el.className='prod'", src,
                      'the card is no longer a <button> — if it became a div this '
                      'guard is obsolete, because a div inherits colour')
        rule = self._rule(src, '.prod')
        self.assertIn('color:var(--ink)', rule.replace(' ', ''),
                      'the product card sets a themed background but leaves its text '
                      'at the browser default, so the dish name is unreadable in dark '
                      'mode (measured 1.38:1)')

    def test_11_every_button_the_page_builds_states_its_colour(self):
        """The general rule behind it. A <button> the page creates must set a colour,
        or it silently takes the UA's black whatever the theme is."""
        src = self._shop()
        built = set(re.findall(r"createElement\('button'\);\s*\w+\.className='([\w-]+)'",
                               src))
        self.assertTrue(built, 'no buttons found — has the page changed shape?')
        for cls in sorted(built):
            rule = self._rule(src, '.' + cls)
            self.assertIn('color:', rule.replace(' ', ''),
                          '.%s is a <button> with no colour of its own: it will render '
                          'in the browser default black on whatever the theme paints '
                          'behind it' % cls)
