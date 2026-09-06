"""An audit trail must not lose rows on a read-only request.

Odoo 19 serves ``auth='none'`` routes on a READ-ONLY cursor by default
(``odoo/http.py``: ``default_mode = ... get('readonly', default_auth == 'none')``),
so an INSERT from one of those requests is refused by Postgres. ``log()`` used to
swallow that: the request returned 200 and the audit row was silently dropped --
the one failure mode a trail like this must not have, because the events reaching
it on a read-only request are the security and authorization ones.

Proves here:
  * a read-only request still persists its audit row (durably, out of band)
  * ``/mezze/w1/audit/log`` -- an endpoint whose entire job is an INSERT --
    writes IN the request's own transaction, i.e. is declared read/write
"""

import json
import uuid

from odoo.sql_db import db_connect
from odoo.tests import tagged

from .common import MezzeHttpCase

BASE = '/mezze/w1'
API = '/mezze/api/v1'


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestAuditReadOnly(MezzeHttpCase):

    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.shared = 'audit-ro-shared-token'
        ICP.set_param('mezze_bridge.api_token', self.shared)
        ICP.set_param('mezze_bridge.api_security', 'observe')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        self.env.flush_all()

    def _post_api(self, path, body):
        return self._raw(API + path, body)

    def _post(self, path, body):
        return self._raw(BASE + path, body)

    def _raw(self, url, body):
        r = self.url_open(url, data=json.dumps(body),
                          headers={'Content-Type': 'application/json'}, timeout=60)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def test_01_a_read_only_request_still_keeps_its_audit_row(self):
        """A read-only route must not silently lose the row it audits.

        Drives the exact case the suite log showed: an ``auth='none'`` route
        (hence read-only) authenticating with the legacy shared token, which
        appends ``api.legacy_shared_token``. Postgres refuses that INSERT on the
        read-only cursor, so the row has to be made durable out of band.

        Read back on an INDEPENDENT connection, because that is the only place
        it exists: cursors are REPEATABLE READ, so a row committed after this
        test's snapshot opened is deliberately invisible to ``self.env``.
        """
        event = 'api.legacy_shared_token'
        before = self._durable_count(event)

        status, body = self._post_api('/orders/recent', {'token': self.shared})
        self.assertEqual(status, 200, body)

        self.assertGreater(
            self._durable_count(event), before,
            "the read-only request's audit row was dropped instead of being "
            "written durably")

    def _durable_count(self, event):
        """Count rows on a connection of our own -- see test_01's docstring."""
        with db_connect(self.env.cr.dbname).cursor() as cr:
            cr.execute("SELECT count(*) FROM mezze_audit_log WHERE event = %s",
                       (event,))
            return cr.fetchone()[0]

    def test_02_the_audit_endpoint_writes_in_the_request_transaction(self):
        """/w1/audit/log exists to INSERT, so it must not run read-only.

        Asserted by VISIBILITY, not by reading the decorator: cursors are
        REPEATABLE READ, so a row this test can see in its own snapshot is one
        the request wrote in the shared transaction. A row that had to go out of
        band would be invisible here -- which is what makes this fail if the
        route loses its readonly=False.
        """
        event = 'test.endpoint.%s' % uuid.uuid4().hex[:10]
        status, body = self._post('/audit/log', {
            'token': self.shared, 'event': event, 'severity': 'info',
            'detail': '{"src": "test"}'})

        self.assertEqual(status, 200, body)
        self.assertTrue(body.get('ok'), body)
        self.assertTrue(body.get('id'), "the endpoint reported no row id: %s" % body)

        self.env.invalidate_all()
        found = self.env['mezze.audit.log'].sudo().search([('event', '=', event)])
        self.assertEqual(
            len(found), 1,
            "the endpoint's audit row is not in this transaction -- the route is "
            "running read-only and the row was written out of band")
        self.assertEqual(found.id, body['id'], "the endpoint reported the wrong id")
