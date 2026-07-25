"""Runtime proof of the P6.1 activation + scope-closure deltas.

Two classes:
  * TestP61Model (TransactionCase) — key rotation/revocation model + production
    config-hardening (weakening rejected + audited) + key resolver grace math.
  * TestP61Http (HttpCase) — signed requests: rotation grace / after-grace /
    unknown key, least-privilege (a terminal principal cannot refund), signed
    cross-branch object-scope denial, durable read-only denial audit.
"""
import hashlib
import hmac
import json
import time
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.mezze_bridge.controllers.main import MezzeBridgeController

from .common import MezzeHttpCase, MezzePosCase

BASE = '/mezze/api/v1'


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestP61Model(MezzePosCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        self.ICP = self.env['ir.config_parameter'].sudo()
        self.ctrl = MezzeBridgeController()
        self.cfg = self.pos_config
        self.term = self.env['mezze.terminal'].create({
            'name': 'KL', 'identifier': 'KL1', 'token': 'tok-active',
            'branch_id': self.cfg.id, 'role': 'terminal', 'active': True})

    def test_key_rotation_and_revocation(self):
        self.assertTrue(self.term.kid)
        old_kid = self.term.kid
        old_fp = self.term.token_fingerprint
        self.assertFalse(self.term.token, "plaintext bearer token must not be stored")
        self.assertTrue(old_fp, "token fingerprint must be stored")
        new_tok = self.term.rotate_token('tok-new')
        self.assertEqual(new_tok, 'tok-new')                     # returned once
        self.assertFalse(self.term.token)                        # never persisted
        self.assertEqual(self.term.prev_token_fingerprint, old_fp)
        self.assertEqual(self.term.prev_kid, old_kid)
        self.assertTrue(self.term.key_rotated_at)
        # within grace: previous key id is accepted (secret = presented token)
        ok, reason = self.ctrl._resolve_signing_key(self.env, self.term, old_kid)
        self.assertEqual((ok, reason), (True, None))
        # after grace: previous key is revoked
        self.term.key_rotated_at = fields.Datetime.now() - timedelta(seconds=10000)
        ok, reason = self.ctrl._resolve_signing_key(self.env, self.term, old_kid)
        self.assertEqual((ok, reason), (False, 'revoked_key'))
        # unknown kid
        ok, reason = self.ctrl._resolve_signing_key(self.env, self.term, 'k-bogus')
        self.assertEqual((ok, reason), (False, 'unknown_key'))
        # active key always resolves
        ok, reason = self.ctrl._resolve_signing_key(self.env, self.term, self.term.kid)
        self.assertEqual((ok, reason), (True, None))

    def test_production_rejects_weakening(self):
        self.ICP.set_param('mezze_bridge.env_profile', 'production')
        self.ICP.set_param('mezze_bridge.signing_mode', 'enforce')
        self.ICP.set_param('mezze_bridge.signing_mode.terminal', 'enforce')
        self.ICP.set_param('mezze_bridge.signing_mode.integration', 'enforce')
        self.ICP.set_param('mezze_bridge.signing_mode.admin', 'enforce')
        # a weakening change is refused (fail closed) in production without break-glass
        with self.assertRaises(UserError):
            self.ICP.set_param('mezze_bridge.signing_mode', 'off')
        # break-glass permits it (still audited)
        self.ICP.set_param('mezze_bridge.breakglass', '1')
        self.ICP.set_param('mezze_bridge.signing_mode', 'off')  # now allowed
        self.assertEqual(self.ICP.get_param('mezze_bridge.signing_mode'), 'off')

    def test_config_change_is_audited(self):
        n0 = self.env['mezze.audit.log'].sudo().search_count(
            [('event', 'in', ('security.policy_change', 'security.policy_weakening'))])
        self.ICP.set_param('mezze_bridge.clock_skew_seconds', '120')
        self.assertGreater(
            self.env['mezze.audit.log'].sudo().search_count(
                [('event', 'in', ('security.policy_change', 'security.policy_weakening'))]), n0)


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestP61Http(MezzeHttpCase):
    fixture_profile = 'POS'

    def _draft_order(self, cfg):
        s = self.open_test_session(cfg)
        p = self.product
        return self.env['pos.order'].create({
            'session_id': s.id, 'company_id': cfg.company_id.id,
            'lines': [(0, 0, {'product_id': p.id, 'qty': 1, 'price_unit': 10.0,
                              'price_subtotal': 10.0, 'price_subtotal_incl': 10.0, 'tax_ids': [(6, 0, [])]})],
            'amount_total': 10.0, 'amount_paid': 0.0, 'amount_tax': 0.0, 'amount_return': 0.0,
            'pricelist_id': cfg.pricelist_id.id or False})

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('mezze_bridge.api_security', 'enforce')
        ICP.set_param('mezze_bridge.env_profile', 'development')  # baseline: shared-admin allowed
        ICP.set_param('mezze_bridge.signing_mode.terminal', 'enforce')
        ICP.set_param('mezze_bridge.api_token', 'p61-shared')
        self.cfg = self.pos_config
        self.cfg2 = self.make_second_pos_config()
        self.term = self.env['mezze.terminal'].create({
            'name': 'PT', 'identifier': 'PT1', 'token': 'p61-term',
            'branch_id': self.cfg.id, 'role': 'terminal', 'active': True})
        self.order = self._draft_order(self.cfg)
        self.order2 = self._draft_order(self.cfg2)
        self.env.flush_all()

    def _sign(self, path, body, nonce, token, kid, ts=None):
        ts = str(int(ts if ts is not None else time.time()))
        raw = json.dumps(body)
        body_sha = hashlib.sha256(raw.encode()).hexdigest()
        principal = 'terminal:%s' % self.term.identifier
        canonical = '\n'.join(('v1', kid or '', principal, 'POST', BASE + path, body_sha, ts, nonce))
        sig = hmac.new(token.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        headers = {'Content-Type': 'application/json', 'X-Mezze-Timestamp': ts,
                   'X-Mezze-Nonce': nonce, 'X-Mezze-Signature': sig, 'X-Mezze-Key-Id': kid or ''}
        r = self.url_open(BASE + path, data=raw, headers=headers, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:150]}

    def test_signed_pay_ok(self):
        body = {'uuid': self.order.uuid, 'token': 'p61-term'}
        st, b = self._sign('/orders/pay', body, 'p61-ok', 'p61-term', self.term.kid)
        self.assertNotIn(b.get('error'), ('invalid_signature', 'signature_required',
                                          'permission_denied', 'branch_mismatch', 'unknown_key'))

    def test_previous_key_within_grace(self):
        old_kid = self.term.kid
        self.term.rotate_token('p61-term-new')
        self.env.flush_all()
        # sign with the OLD key + OLD kid -> accepted during grace
        body = {'uuid': self.order.uuid, 'token': 'p61-term'}
        st, b = self._sign('/orders/pay', body, 'p61-grace', 'p61-term', old_kid)
        self.assertNotIn(b.get('error'), ('invalid_signature', 'revoked_key', 'unknown_key'))

    def test_previous_key_after_grace_rejected(self):
        old_kid, old_tok = self.term.kid, 'p61-term'
        self.term.rotate_token('p61-term-new2')
        self.term.key_rotated_at = fields.Datetime.now() - timedelta(seconds=10000)
        self.env.flush_all()
        body = {'uuid': self.order.uuid, 'token': old_tok}
        st, b = self._sign('/orders/pay', body, 'p61-old', old_tok, old_kid)
        self.assertEqual(b.get('error'), 'revoked_key')

    def test_unknown_key_rejected(self):
        body = {'uuid': self.order.uuid, 'token': 'p61-term'}
        st, b = self._sign('/orders/pay', body, 'p61-uk', 'p61-term', 'k-does-not-exist')
        self.assertEqual(b.get('error'), 'unknown_key')

    def test_terminal_principal_cannot_refund(self):
        # least privilege: a bare terminal principal has POS caps but NOT orders.refund
        body = {'uuid': 'p61-refund', 'session_id': self.order.session_id.id,
                'original_order_id': self.order.id, 'token': 'p61-term'}
        st, b = self._sign('/orders/refund', body, 'p61-ref', 'p61-term', self.term.kid)
        self.assertEqual(b.get('error'), 'permission_denied')

    def test_signed_cross_branch_denied(self):
        # a perfectly signed request for an order in ANOTHER branch is still denied
        # by authoritative object scope
        body = {'uuid': self.order2.uuid, 'token': 'p61-term'}
        st, b = self._sign('/orders/pay', body, 'p61-xb', 'p61-term', self.term.kid)
        self.assertEqual(b.get('error'), 'branch_mismatch')

    def test_readonly_denial_is_durably_audited(self):
        from odoo.sql_db import db_connect

        def _count():
            with db_connect(self.env.cr.dbname).cursor() as cr:
                cr.execute("SELECT count(*) FROM mezze_audit_log WHERE event='api.security_denied'")
                return cr.fetchone()[0]
        n0 = _count()
        # a read-only route (w1 reports/summary) denied with a bad token -> the
        # denial is durably recorded via the independent-cursor audit even though
        # the request ran in a read-only transaction.
        self.url_open('/mezze/w1/reports/summary', data=json.dumps({'token': 'nope'}),
                      headers={'Content-Type': 'application/json'}, timeout=30)
        self.assertGreaterEqual(_count() - n0, 1)
