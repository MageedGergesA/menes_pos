"""S1-07 — the menu health card at the foot of the category rail.

The design puts a small card under the categories on screen 01:

    MENU HEALTH
    100%  with photos
    0 monogram tiles · Favorites clean

Every figure is the catalogue in front of the cashier, COUNTED. It is not a
score to interpret and not a target to chase, which is why it is read-only: a
missing photo is Menu work, and a Fix button here would take a cashier off the
till in the middle of service.

"Monogram tiles" is literally what is on the screen, not a proxy for it — the
product grid picks an <img> on `has_image` and otherwise draws the item's
initials, so an item without a photo IS a monogram tile. The demo catalogue
proves the point: Baba Ghanoush and Falafel Sandwich both render as BG and FS.

The third figure needed a definition rather than a guess. The prototype says
"Favorites clean" and nothing about what dirty means. Favourites here are
remembered as ids and resolved against the live catalogue with `.filter(Boolean)`,
so an id that no longer sells is dropped IN SILENCE: the cashier's one-tap row
quietly gets shorter and nothing says why. That is the fact worth surfacing, so
a favourite counts as stale when its product has left the catalogue or is 86'd
off it.
"""
import os

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestMenuHealthCard(MezzeHttpCase):
    fixture_profile = 'CORE'

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _src(self, rel):
        with open(os.path.join(self.ROOT, rel), encoding='utf-8') as f:
            return f.read()

    def test_01_the_card_is_on_the_rail(self):
        xml = self._src('static/src/cashier/root.xml')
        self.assertIn('mz-menu-health', xml, 'the card is never drawn')
        # it must sit inside the category rail, not float somewhere else
        rail = xml[xml.index('mz-catside'):xml.index('mz-catalog')]
        self.assertIn('mz-menu-health', rail,
                      'the card is not at the foot of the category rail')
        for part in ('menuHealthPct', 'withPhotosLabel', 'menuHealthNote'):
            self.assertIn(part, xml, 'the card is missing %s' % part)

    def test_02_it_counts_rather_than_scores(self):
        js = self._src('static/src/cashier/root.js')
        self.assertIn('has_image', js, 'photos are not counted from the catalogue')
        self.assertIn('staleFavorites', js, 'stale favourites are not counted')
        # an empty catalogue must not read as perfect health
        self.assertIn('total ? Math.round', js,
                      'an empty catalogue would divide by zero or report 100%')

    def test_03_a_stale_favorite_is_one_that_cannot_be_rung(self):
        """Gone from the catalogue, or present but 86'd. Both leave the cashier
        with a favourites row that silently lost a button."""
        js = self._src('static/src/cashier/root.js')
        i = js.index('get menuHealth()')
        block = js[i:i + 1400]
        self.assertIn('favoriteIds(Infinity)', block,
                      'only the visible top-8 favourites are checked')
        self.assertIn('p.available === false', block,
                      "an 86'd favourite is not counted as stale")

    def test_04_the_card_is_read_only(self):
        """A Fix button here would take a cashier off the till mid-service."""
        xml = self._src('static/src/cashier/root.xml')
        i = xml.index('mz-menu-health')
        card = xml[i:xml.index('</div>', xml.index('mz-mhealth__n', i))]
        for interactive in ('<button', 't-on-click'):
            self.assertNotIn(interactive, card,
                             'the card offers an action it should not')

    def test_05_the_card_is_translated(self):
        po = self._src('i18n/ar.po')
        for en in ('Menu health', 'with photos', '%s monogram tiles',
                   'Favorites clean', '%s stale favorites'):
            self.assertIn('msgid "%s"' % en, po, '%r has no Arabic' % en)
        # the design's own Arabic for the two it names
        self.assertIn('msgstr "جودة القائمة"', po)
        self.assertIn('msgstr "بصور"', po)

    def test_06_the_styles_live_with_the_rail_they_belong_to(self):
        """The rail only exists at >=1280px and the card belongs to it, so the
        card must be inside that same query — otherwise it renders on a narrow
        till where its container is display:none."""
        css = self._src('static/design/category-nav.css')
        self.assertIn('.mz-mhealth{', css, 'the card has no styles on the rail')
        i = css.index('@media (min-width:1280px)')
        self.assertGreater(css.index('.mz-mhealth{'), i,
                           'the card is styled outside the rail media query')
