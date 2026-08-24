# -*- coding: utf-8 -*-
"""Courses, from the till.

``/courses/board|hold|fire`` have worked since they were written. The only surface
that reached them was ``static/courses.html`` — a page no route serves, which reads
the API token out of the URL query string. A token in a URL ends up in browser
history, in the server's access log, and in the ``Referer`` header of anything the
page links to; it is the wrong way to authenticate even on a page that worked, and
this one could not be opened at all.

The screen now lives inside the Register, so it authenticates the way every other
call does and no token is ever written into a location bar.

``static/courses.html`` is deliberately left in place. It is unreachable, but six
test files still describe it, and the token-in-URL pattern it uses is shared by
``drivethru.html``, ``cfd.html`` and ``pos.html`` — removing one page would neither
fix the pattern nor be honest about its scope. That is a decision to take across all
four, not a side effect of building this screen.

The property worth testing is the one that makes courses a feature rather than a
label: **a held course is one the kitchen has not seen.** Starters go now, mains
wait, and the waiter fires them when the table is ready. If holding put items on the
kitchen's board anyway, the whole thing is decorative.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_courses')
class TestCoursesFromTill(MezzeHttpCase):
    # RESTAURANT, not POS. A course is a TABLE's sequence, so on the POS profile
    # there was no table, and four of the five tests below skipped — leaving the row
    # signed off on the one negative case that needs no table. A suite that reports
    # green while never running is worse than a red one.
    fixture_profile = 'RESTAURANT'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'co-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.table = env['restaurant.table'].sudo().search(
            [('floor_id.pos_config_ids', 'in', cls.pos_config.ids)], limit=1)
        cls.starter = env['product.product'].sudo().create({
            'name': 'CO Soup', 'available_in_pos': True, 'list_price': 30.0,
            'type': 'consu'})
        cls.main = env['product.product'].sudo().create({
            'name': 'CO Steak', 'available_in_pos': True, 'list_price': 90.0,
            'type': 'consu'})
        (cls.starter | cls.main).write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='co-tok')),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _board(self):
        return self._post('/courses/board', {'table_id': self.table.id})

    # -- holding vs firing -------------------------------------------------
    def test_10_a_held_course_is_not_on_the_kitchen_board(self):
        # THE property. If holding fired anyway, courses would be a label.
        before = self.env['mezze.kds.ticket'].sudo().search_count([])
        d = self._post('/courses/hold', {
            'table_id': self.table.id, 'seq': 1, 'name': 'Starters',
            'lines': [{'product_id': self.starter.id, 'qty': 1}]})
        self.assertTrue(d.get('ok'), d)
        after = self.env['mezze.kds.ticket'].sudo().search_count([])
        self.assertEqual(after, before,
                         'holding a course sent it to the kitchen anyway')

    def test_11_the_board_reports_it_as_held(self):
        self._post('/courses/hold', {
            'table_id': self.table.id, 'seq': 2, 'name': 'Mains',
            'lines': [{'product_id': self.main.id, 'qty': 2}]})
        d = self._board()
        self.assertTrue(d.get('ok'), d)
        held = [c for c in d['courses'] if c.get('held')]
        self.assertTrue(held, 'the held course is not on the board: %s' % d)
        self.assertIn('CO Steak', json.dumps(held))

    def test_12_courses_come_back_in_sequence(self):
        # A waiter reads this top to bottom; out of order it is worse than nothing.
        self._post('/courses/hold', {'table_id': self.table.id, 'seq': 3,
                                     'lines': [{'product_id': self.main.id, 'qty': 1}]})
        self._post('/courses/hold', {'table_id': self.table.id, 'seq': 1,
                                     'lines': [{'product_id': self.starter.id, 'qty': 1}]})
        seqs = [c['seq'] for c in self._board()['courses']]
        self.assertEqual(seqs, sorted(seqs))

    def test_13_an_unknown_table_is_refused(self):
        d = self._post('/courses/board', {'table_id': 99999999})
        self.assertEqual(d.get('error'), 'no_table')

    def test_14_a_course_needs_a_number(self):
        d = self._post('/courses/hold', {'table_id': self.table.id,
                                         'lines': [{'product_id': self.main.id, 'qty': 1}]})
        self.assertEqual(d.get('error'), 'no_seq')
