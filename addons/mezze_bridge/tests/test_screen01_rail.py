"""S1-09/S1-10/S1-11 — the three screen-01 features the first pass missed.

These were not found by reading the design and writing down what looked missing;
that method produced two false rows earlier. They came from a systematic sweep of
the 36 `L.*` labels the prototype's Register markup actually references.

* **S1-09 open-checks strip** — the other open checks, a tap away, without
  leaving the till. The Orders workspace lists the same rows but it is a SCREEN,
  and a cashier mid-service will not leave the till to look.
* **S1-10 dietary filter** — chips on the rail, on Odoo's own `product.tag`
  rather than a new model, curated by one boolean so that "Summer menu" and
  "Supplier: Nile Foods" do not become diets.
* **S1-11 merged badge** — a line carried in by `/tables/merge` is badged on the
  check it lands on. The merge unlinks the source, so the reference is stored
  rather than linked: a foreign key would be null exactly when it mattered.
"""
import json
import os

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestDietaryTags(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.shared = 'screen01-token'
        ICP.set_param('mezze_bridge.api_token', self.shared)
        ICP.set_param('mezze_bridge.api_security', 'observe')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session(self.pos_config)
        Tag = self.env['product.tag']
        self.diet = Tag.create({'name': 'No shellfish', 'mezze_is_dietary': True})
        # the discriminating case: an ordinary catalogue tag
        self.admin_tag = Tag.create({'name': 'Summer menu', 'mezze_is_dietary': False})
        tmpl = self.product.product_tmpl_id
        tmpl.product_tag_ids = [(6, 0, (self.diet | self.admin_tag).ids)]
        self.env.flush_all()

    def _boot(self):
        r = self.url_open('/mezze/api/v1/bootstrap',
                          data=json.dumps({'token': self.shared,
                                           'config_id': self.pos_config.id}),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        return r.status_code, r.json()

    def test_01_only_dietary_tags_reach_the_rail(self):
        """Every product tag as a chip would put the branch's filing system on the
        cashier's rail as though it described the food."""
        code, res = self._boot()
        self.assertEqual(code, 200, res)
        names = [t['name'] for t in res.get('diet_tags', [])]
        self.assertIn('No shellfish', names, 'a dietary tag is missing from the rail')
        self.assertNotIn('Summer menu', names,
                         'an ordinary catalogue tag was offered as a diet')

    def test_02_a_product_carries_only_its_dietary_tags(self):
        code, res = self._boot()
        self.assertEqual(code, 200, res)
        row = next((p for p in res['products'] if p['id'] == self.product.id), None)
        self.assertTrue(row, 'the fixture product is not in the payload')
        self.assertIn(self.diet.id, row.get('diet_tag_ids') or [])
        self.assertNotIn(self.admin_tag.id, row.get('diet_tag_ids') or [],
                         'a non-dietary tag leaked onto the product')

    def test_03_the_seeded_tags_are_the_ones_the_design_names(self):
        for xmlid in ('tag_diet_veg', 'tag_diet_vegan',
                      'tag_diet_no_gluten', 'tag_diet_no_nuts'):
            tag = self.env.ref('mezze_bridge.%s' % xmlid, raise_if_not_found=False)
            self.assertTrue(tag, 'seeded dietary tag %s is missing' % xmlid)
            self.assertTrue(tag.mezze_is_dietary,
                            '%s was seeded without the dietary flag' % xmlid)

    def test_04_the_filter_is_applied_after_the_search(self):
        """A category is a browsing choice and a search overrides it. A diet is a
        fact about the guest: if searching while "No nuts" is picked returned a
        dish with nuts, the filter would be actively dangerous, because the
        cashier believes the list in front of them is already safe."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, 'static/src/cashier/root.js'), encoding='utf-8') as f:
            js = f.read()
        i = js.index('get filteredProducts()')
        block = js[i:i + 400]
        self.assertIn('_applyDiet(base)', block,
                      'the diet filter does not survive a search')
        self.assertIn('filterProducts(this.state.products, this.state.search)', block)


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestMergedProvenance(MezzeHttpCase):
    fixture_profile = 'RESTAURANT'

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.shared = 'merged-token'
        ICP.set_param('mezze_bridge.api_token', self.shared)
        ICP.set_param('mezze_bridge.api_security', 'observe')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session(self.pos_config)
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token=self.shared)),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def _sync(self, uuid, **extra):
        return self._post('/orders/sync', dict(
            {'uuid': uuid, 'session_id': self.session.id, 'draft': True,
             'lines': [{'product_id': self.product.id, 'qty': 1}]}, **extra))

    def test_10_a_merged_line_remembers_where_it_came_from(self):
        self.assertGreaterEqual(len(self.tables), 2)
        src_t, dst_t = self.tables[0], self.tables[1]
        self._sync('prov-src', table_id=src_t.id)
        self._sync('prov-dst', table_id=dst_t.id)
        src = self.env['pos.order'].search([('uuid', '=', 'prov-src')], limit=1)
        src_ref = src.pos_reference
        code, res = self._post('/tables/merge', {
            'session_id': self.session.id,
            'from_table_id': src_t.id, 'to_table_id': dst_t.id})
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('merged'), res)
        dst = self.env['pos.order'].search([('uuid', '=', 'prov-dst')], limit=1)
        dst.invalidate_recordset()
        stamped = dst.lines.filtered(lambda l: l.mezze_merged_from)
        self.assertTrue(stamped, 'the carried-in lines are not marked')
        self.assertEqual(stamped[0].mezze_merged_from, src_ref,
                         'the badge cannot name the check it came from')
        # the destination's OWN line must not be badged
        self.assertTrue(dst.lines.filtered(lambda l: not l.mezze_merged_from),
                        "the destination's own line was marked as merged too")

    def test_11_the_till_is_told(self):
        """A badge the client never receives is a badge nobody sees."""
        self.assertGreaterEqual(len(self.tables), 2)
        src_t, dst_t = self.tables[0], self.tables[1]
        self._sync('prov2-src', table_id=src_t.id)
        self._sync('prov2-dst', table_id=dst_t.id)
        self._post('/tables/merge', {
            'session_id': self.session.id,
            'from_table_id': src_t.id, 'to_table_id': dst_t.id})
        code, res = self._post('/orders/get', {'uuid': 'prov2-dst'})
        self.assertEqual(code, 200, res)
        merged = [l for l in res['lines'] if l.get('merged_from')]
        self.assertTrue(merged, 'the payload never mentions the merge')


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestScreen01RailSurface(MezzeHttpCase):
    """The three surfaces, held to the shape the design draws."""
    fixture_profile = 'CORE'

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _src(self, rel):
        with open(os.path.join(self.ROOT, rel), encoding='utf-8') as f:
            return f.read()

    def test_20_the_open_checks_strip_reuses_the_recall_guard(self):
        """onRecall refuses to silently discard a non-empty cart and offers Park &
        open instead. A strip that added its own shortcut would lose that."""
        xml = self._src('static/src/cashier/root.xml')
        self.assertIn('mz-open-checks', xml, 'the strip is never drawn')
        i = xml.index('mz-open-checks')
        strip = xml[i:i + 900]
        self.assertIn('this.onRecall(ck)', strip,
                      'the strip bypasses the discard guard')

    def test_21_the_strip_never_offers_the_check_already_open(self):
        js = self._src('static/src/cashier/root.js')
        i = js.index('async loadOpenChecks()')
        block = js[i:i + 700]
        self.assertIn('r.uuid !== this.state.orderUuid', block,
                      'the till offers to recall the check it is already on')

    def test_22_the_strip_never_blocks_the_menu(self):
        """A convenience strip must not hold up the catalogue the cashier is
        waiting for, nor break the Register when /orders/list is unavailable."""
        js = self._src('static/src/cashier/root.js')
        i = js.index('async loadOpenChecks()')
        block = js[i:i + 700]
        self.assertIn('catch', block, 'a failed strip load would surface as an error')
        self.assertIn('this.state.openChecks = []', block)

    def test_23_the_dietary_chips_are_on_the_rail(self):
        xml = self._src('static/src/cashier/root.xml')
        self.assertIn('mz-diets', xml, 'the chips are never drawn')
        rail = xml[xml.index('mz-catside'):xml.index('mz-catalog')]
        self.assertIn('mz-diets', rail, 'the chips are not on the category rail')
        self.assertIn('pickDiet(d.id)', xml)

    def test_24_the_merged_badge_follows_the_comped_pattern(self):
        xml = self._src('static/src/cashier/components/cart.xml')
        self.assertIn('mz-line-merged', xml, 'the badge is never drawn')
        self.assertIn('isMerged(line)', xml)
        # provenance must survive a resume, which is exactly when it is needed
        js = self._src('static/src/cashier/root.js')
        self.assertIn('mergedFrom: l.merged_from', js,
                      'the badge disappears the moment a merged check is resumed')

    def test_26_new_never_discards_the_cashiers_work(self):
        """`newOrder()` clears the cart outright — correct after a charge or a
        park, silent destruction when someone presses "New". Recall solved this
        by parking first; this must use the same answer."""
        js = self._src('static/src/cashier/root.js')
        i = js.index('async newCheck()')
        block = js[i:i + 600]
        self.assertIn('this.parkCurrent()', block,
                      '"New" throws away the check the cashier was ringing up')
        self.assertIn('this.order.isEmpty', block,
                      'an empty cart is parked pointlessly')

    def test_27_the_seeded_tag_names_are_translated_as_DATA(self):
        """The chips render `product.tag.name` out of the database, not a _t()
        call. A `code:` msgid does not bind to a record, so the rail rendered
        "Veg / Vegan / No gluten / No nuts" in English on an Arabic till — which
        is exactly what the staff-surface render test caught. Data needs a
        `model:` reference."""
        po = self._src('i18n/ar.po')
        for xmlid in ('tag_diet_veg', 'tag_diet_vegan',
                      'tag_diet_no_gluten', 'tag_diet_no_nuts'):
            self.assertIn('#: model:product.tag,name:mezze_bridge.%s' % xmlid, po,
                          '%s is not bound to its record, so it stays English' % xmlid)

    def test_28_the_chips_are_declared_as_record_data(self):
        """A diet chip shows `product.tag.name` — a row a restaurant types and can
        rename to anything, in any language. The Arabic render contract skips
        record data (`.mz-catside__data`, the same marker category names carry)
        and flags everything else as untranslated English. Without the marker the
        chips read as a translation bug on every Arabic till."""
        xml = self._src('static/src/cashier/root.xml')
        i = xml.index('mz-diets__chip')
        self.assertIn('mz-catside__data', xml[i:i + 200],
                      'the chips are not declared as record data')

    def test_25_the_three_surfaces_are_translated(self):
        po = self._src('i18n/ar.po')
        for en in ('Dietary', 'Open checks', 'Merged',
                   'Veg', 'Vegan', 'No gluten', 'No nuts'):
            self.assertIn('msgid "%s"' % en, po, '%r has no Arabic' % en)
