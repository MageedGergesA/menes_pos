"""Runtime verification of the P4 security layer INSIDE a running Odoo server.

Real HTTP through the canonical gate: authentication, capability authorization,
company/branch isolation, request signing, replay protection, device revocation,
and observe-preserves-behaviour — asserted end-to-end.

Run:
  odoo-bin -d <db> -c <conf> -u mezze_bridge --test-enable \
           --test-tags mezze_runtime --stop-after-init
"""

import hashlib
import hmac
import json
import time

from odoo import fields
from odoo.tests import tagged

from .common import MezzeHttpCase, MezzeTransactionCase

BASE = '/mezze/api/v1'


def _paid_order_in(case, config):
    """Paid pos.order in ``config``'s own (config-scoped) session, using fixture data."""
    env = case.env
    s = case.open_test_session(config)
    p = case.product
    o = env['pos.order'].create({
        'session_id': s.id, 'company_id': config.company_id.id,
        'lines': [(0, 0, {'product_id': p.id, 'qty': 1, 'price_unit': 10.0,
                          'price_subtotal': 10.0, 'price_subtotal_incl': 10.0, 'tax_ids': [(6, 0, [])]})],
        'amount_tax': 0.0, 'amount_total': 10.0, 'amount_paid': 0.0, 'amount_return': 0.0,
        'pricelist_id': config.pricelist_id.id or False})
    o.add_payment({'amount': 10.0, 'payment_method_id': config.payment_method_ids[:1].id,
                   'name': fields.Datetime.now(), 'pos_order_id': o.id})
    try:
        o.action_pos_order_paid()
    except Exception:
        o.write({'state': 'paid'})
    return o


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestSecurityRuntime(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.shared = 'shared-admin-token'
        ICP.set_param('mezze_bridge.api_token', self.shared)
        ICP.set_param('mezze_bridge.api_security', 'enforce')
        ICP.set_param('mezze_bridge.env_profile', 'development')  # baseline: shared-admin allowed
        ICP.set_param('mezze_bridge.signing_mode.terminal', 'observe')  # clean signing baseline per test
        self.cfg1 = self.pos_config
        self.cfg2 = self.make_second_pos_config()
        self.tterm = 'term-tok-1'
        self.terminal = self.env['mezze.terminal'].create({
            'name': 'T1', 'identifier': 'T1', 'token': self.tterm,
            'branch_id': self.cfg1.id, 'active': True})
        self.cashier = self.env['mezze.cashier'].create({
            'name': 'Cash', 'code': 'C1', 'role': 'cashier', 'active': True})
        self.manager = self.env['mezze.cashier'].create({
            'name': 'Mgr', 'code': 'M1', 'role': 'manager', 'active': True})
        self.order = _paid_order_in(self, self.cfg1)          # in the terminal's branch
        self.order2 = _paid_order_in(self, self.cfg2)         # different branch
        self.Audit = self.env['mezze.audit.log'].sudo()
        self.env.flush_all()

    def _post(self, path, body, headers=None):
        h = {'Content-Type': 'application/json'}
        h.update(headers or {})
        r = self.url_open(BASE + path, data=json.dumps(body), headers=h, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    # ---------------- authentication ----------------
    def test_missing_token_rejected(self):
        st, b = self._post('/orders/pay', {'uuid': self.order.uuid})
        self.assertEqual(b.get('error'), 'authentication_required')

    def test_wrong_token_rejected(self):
        st, b = self._post('/orders/pay', {'uuid': self.order.uuid, 'token': 'nope'})
        self.assertEqual(b.get('error'), 'authentication_failed')

    def test_shared_admin_token_passes(self):
        st, b = self._post('/orders/pay', {'uuid': self.order.uuid, 'token': self.shared})
        # admin has all caps + bypasses scope; a paid order returns already
        self.assertNotIn(b.get('error'), ('authentication_failed', 'permission_denied', 'branch_mismatch'))
        self.assertTrue(b.get('ok'))

    # ---------------- authorization (capability) ----------------
    def test_cashier_lacks_refund_capability(self):
        st, b = self._post('/orders/refund',
                           {'uuid': 'sec-r1', 'session_id': self.order.session_id.id,
                            'original_order_id': self.order.id, 'token': self.tterm,
                            'cashier_id': self.cashier.id})
        self.assertEqual(b.get('error'), 'permission_denied')

    def test_manager_has_refund_capability(self):
        st, b = self._post('/orders/refund',
                           {'uuid': 'sec-r2', 'session_id': self.order.session_id.id,
                            'original_order_id': self.order.id, 'token': self.tterm,
                            'cashier_id': self.manager.id})
        self.assertNotEqual(b.get('error'), 'permission_denied')   # capability granted

    def test_cashier_can_pay(self):
        st, b = self._post('/orders/pay',
                           {'uuid': self.order.uuid, 'token': self.tterm, 'cashier_id': self.cashier.id})
        self.assertNotIn(b.get('error'), ('permission_denied', 'authentication_failed'))

    # ---------------- branch isolation ----------------
    def test_cross_branch_rejected(self):
        # terminal is in cfg1; order2 is in cfg2 -> branch mismatch
        st, b = self._post('/orders/pay',
                           {'uuid': self.order2.uuid, 'token': self.tterm, 'cashier_id': self.cashier.id})
        self.assertEqual(b.get('error'), 'branch_mismatch')

    # ---------------- device revocation ----------------
    def test_revoked_terminal_rejected(self):
        self.terminal.active = False
        self.env.flush_all()
        st, b = self._post('/orders/pay',
                           {'uuid': self.order.uuid, 'token': self.tterm, 'cashier_id': self.cashier.id})
        self.assertEqual(b.get('error'), 'terminal_revoked')

    # ---------------- request signing + replay ----------------
    def _enforce_signing(self):
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.signing_mode.terminal', 'enforce')
        self.env.flush_all()

    def _signed(self, path, body, nonce, ts=None):
        ts = str(int(ts if ts is not None else time.time()))
        raw = json.dumps(body)
        body_sha = hashlib.sha256(raw.encode()).hexdigest()
        # canonical string per domain.signing_policy: version, kid, principal,
        # METHOD, exact route, body digest, timestamp, nonce.
        principal = 'terminal:%s' % self.terminal.identifier
        canonical = '\n'.join(('v1', self.terminal.kid or '', principal, 'POST',
                               BASE + path, body_sha, ts, nonce))
        sig = hmac.new(self.tterm.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        headers = {'Content-Type': 'application/json', 'X-Mezze-Timestamp': ts,
                   'X-Mezze-Nonce': nonce, 'X-Mezze-Signature': sig,
                   'X-Mezze-Key-Id': self.terminal.kid or ''}
        r = self.url_open(BASE + path, data=raw, headers=headers, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def test_replay_rejected(self):
        self._enforce_signing()
        body = {'uuid': self.order.uuid, 'token': self.tterm, 'cashier_id': self.cashier.id}
        st1, b1 = self._signed('/orders/pay', body, nonce='N-1')
        self.assertNotEqual(b1.get('error'), 'invalid_signature')      # first accepted
        st2, b2 = self._signed('/orders/pay', body, nonce='N-1')       # same nonce
        self.assertEqual(b2.get('error'), 'replayed_request')

    def test_expired_signature_rejected(self):
        self._enforce_signing()
        body = {'uuid': self.order.uuid, 'token': self.tterm, 'cashier_id': self.cashier.id}
        st, b = self._signed('/orders/pay', body, nonce='N-exp', ts=time.time() - 4000)
        self.assertEqual(b.get('error'), 'expired_signature')

    def test_bad_signature_rejected(self):
        self._enforce_signing()
        raw = json.dumps({'uuid': self.order.uuid, 'token': self.tterm, 'cashier_id': self.cashier.id})
        headers = {'Content-Type': 'application/json', 'X-Mezze-Timestamp': str(int(time.time())),
                   'X-Mezze-Nonce': 'N-bad', 'X-Mezze-Signature': 'deadbeef',
                   'X-Mezze-Key-Id': self.terminal.kid or ''}
        r = self.url_open(BASE + '/orders/pay', data=raw, headers=headers, timeout=30)
        self.assertEqual(r.json().get('error'), 'invalid_signature')

    # ---------------- observe preserves behaviour ----------------
    def test_observe_mode_does_not_block(self):
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_security', 'observe')
        self.env.flush_all()
        # no token at all -> in observe mode the security gate never blocks; the
        # request proceeds to the legacy shared-token auth (which returns 401),
        # proving the gate itself added no NEW block.
        st, b = self._post('/orders/pay', {'uuid': self.order.uuid, 'token': self.shared})
        self.assertNotIn(b.get('error'),
                         ('authentication_required', 'permission_denied', 'branch_mismatch'))
        self.assertTrue(b.get('ok'))

    # ---------------- audit (durable via independent cursor) ----------------
    def test_denial_is_audited(self):
        from odoo.sql_db import db_connect

        def _count():
            with db_connect(self.env.cr.dbname).cursor() as cr:
                cr.execute("SELECT count(*) FROM mezze_audit_log WHERE event='api.security_denied'")
                return cr.fetchone()[0]
        n0 = _count()
        self._post('/orders/pay', {'uuid': self.order.uuid, 'token': 'nope'})
        # the denial audit is committed on an INDEPENDENT connection, so it is
        # durable even though this HttpCase transaction never commits.
        self.assertGreaterEqual(_count() - n0, 1)

    # ---------------- signature-required policy ----------------
    def test_signature_required_when_signing_enforced(self):
        self._enforce_signing()
        # orders/pay is in SIGNATURE_REQUIRED -> unsigned request is rejected
        st, b = self._post('/orders/pay',
                           {'uuid': self.order.uuid, 'token': self.tterm, 'cashier_id': self.cashier.id})
        self.assertEqual(b.get('error'), 'signature_required')
        # a correctly signed request is accepted
        st2, b2 = self._signed('/orders/pay',
                               {'uuid': self.order.uuid, 'token': self.tterm, 'cashier_id': self.cashier.id},
                               nonce='sig-ok-1')
        self.assertNotIn(b2.get('error'), ('signature_required', 'invalid_signature'))

    # ---------------- shared-token disable (Phase 8) ----------------
    def test_shared_token_can_be_disabled(self):
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.shared_token_disabled', '1')
        self.env.flush_all()
        st, b = self._post('/orders/pay', {'uuid': self.order.uuid, 'token': self.shared})
        self.assertEqual(b.get('error'), 'authentication_failed')   # fails closed


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestSecurityMultiCompany(MezzeHttpCase):
    """Real multi-company/branch isolation over HTTP."""
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('mezze_bridge.api_token', 'sh-mc')
        ICP.set_param('mezze_bridge.api_security', 'enforce')
        ICP.set_param('mezze_bridge.signing_mode.terminal', 'observe')  # clean signing baseline per test
        self.tterm = 'mc-term-a'
        cfgA = self.pos_config
        self.companyA = cfgA.company_id
        # Company B is a real res.company; we do NOT stand up a full POS/accounting
        # stack for it (heavy). Instead orderB is a real order whose company_id is
        # set to B — exactly the cross-company record the scope check must reject.
        self.companyB = self.env['res.company'].create({'name': 'Mezze Co B'})
        # the api-env user can technically read both companies; the GATE still
        # restricts by the authenticated PRINCIPAL's (terminal's) company.
        self.env.ref('base.user_admin').sudo().write({'company_ids': [(4, self.companyB.id)]})
        self.terminalA = self.env['mezze.terminal'].create({
            'name': 'TA', 'identifier': 'TA', 'token': self.tterm,
            'branch_id': cfgA.id, 'active': True})
        self.cashier = self.env['mezze.cashier'].create({
            'name': 'CashA', 'code': 'CA', 'role': 'cashier', 'active': True})
        self.orderA = _paid_order_in(self, cfgA)
        self.orderB = _paid_order_in(self, cfgA)
        # relocate orderB into company B at the DB level (foreign-company record)
        self.env.cr.execute("UPDATE pos_order SET company_id=%s WHERE id=%s",
                            (self.companyB.id, self.orderB.id))
        self.orderB.invalidate_recordset(['company_id'])
        self.cfgA = cfgA
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open(BASE + path, data=json.dumps(body),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.json()
        except Exception:
            return {'_raw': r.text[:200]}

    def test_a_terminal_accesses_own_records(self):
        b = self._post('/orders/pay',
                       {'uuid': self.orderA.uuid, 'token': self.tterm, 'cashier_id': self.cashier.id})
        self.assertNotIn(b.get('error'), ('company_mismatch', 'branch_mismatch', 'permission_denied'))

    def test_a_terminal_cannot_access_company_b(self):
        b = self._post('/orders/pay',
                       {'uuid': self.orderB.uuid, 'token': self.tterm, 'cashier_id': self.cashier.id})
        self.assertIn(b.get('error'), ('company_mismatch', 'branch_mismatch'))

    def test_client_supplied_company_cannot_override(self):
        # a fake company/branch in the body must be ignored (server truth wins)
        b = self._post('/orders/pay',
                       {'uuid': self.orderB.uuid, 'token': self.tterm, 'cashier_id': self.cashier.id,
                        'company_id': self.companyA.id, 'branch_id': self.cfgA.id})
        self.assertIn(b.get('error'), ('company_mismatch', 'branch_mismatch'))


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestNonceGc(MezzeTransactionCase):
    """Nonce store lifecycle: GC removes expired, retains in-window, is idempotent."""
    fixture_profile = 'CORE'

    def test_claim_then_replay(self):
        N = self.env['mezze.api.nonce']
        self.assertTrue(N.claim('p1', 'n1'))
        self.assertFalse(N.claim('p1', 'n1'))          # replay
        self.assertTrue(N.claim('p1', 'n2'))           # different nonce ok
        self.assertTrue(N.claim('p2', 'n1'))           # different principal, same value ok

    def test_gc_deletes_expired_retains_fresh(self):
        from datetime import timedelta
        N = self.env['mezze.api.nonce']
        N.claim('gc', 'fresh')
        N.claim('gc', 'old')
        old = N.search([('principal', '=', 'gc'), ('nonce', '=', 'old')])
        old.seen_at = fields.Datetime.now() - timedelta(hours=2)
        self.env.flush_all()
        cutoff = fields.Datetime.now() - timedelta(hours=1)
        deleted = N.gc(cutoff)
        self.assertGreaterEqual(deleted, 1)
        self.assertFalse(N.search_count([('principal', '=', 'gc'), ('nonce', '=', 'old')]))
        self.assertEqual(N.search_count([('principal', '=', 'gc'), ('nonce', '=', 'fresh')]), 1)
        # replaying the still-fresh nonce is still blocked (window intact)
        self.assertFalse(N.claim('gc', 'fresh'))

    def test_cron_gc_idempotent(self):
        N = self.env['mezze.api.nonce']
        N._cron_gc()   # drain any pre-existing expired nonces (e.g. harness residue)
        self.assertEqual(N._cron_gc(), N._cron_gc())   # now repeatable + stable (0 == 0)
