"""Runtime proof of HMAC-secret envelope encryption (P6.2 Phases 12-15).

Tagged mezze_runtime. Requires MEZZE_MASTER_KEY in the environment. Proves the
aggregator integration secret is ciphertext at rest, redacted on ORM read, never
serialized in plaintext, decryptable only via the secret store, fail-closed on a
bad key, and migratable from legacy plaintext.
"""
import os

from odoo.tests import common, tagged

from odoo.addons.mezze_bridge.domain import crypto


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestSecretEncryption(common.TransactionCase):

    def setUp(self):
        super().setUp()
        if not os.environ.get('MEZZE_MASTER_KEY'):
            self.skipTest('MEZZE_MASTER_KEY not set in this run')
        self.cfg = self.env['pos.config'].search([], limit=1)
        self.ch = self.env['mezze.aggregator'].create({
            'code': 'sec-test', 'name': 'Sec', 'config_id': self.cfg.id, 'secret': 'sekret-value'})

    def test_ciphertext_at_rest(self):
        self.env.flush_all()
        self.env.cr.execute("SELECT secret_enc FROM mezze_aggregator WHERE id=%s", (self.ch.id,))
        enc = self.env.cr.fetchone()[0]
        self.assertTrue(crypto.is_envelope(enc), 'secret not enveloped at rest')
        self.assertNotIn('sekret-value', enc)
        # no legacy plaintext 'secret' column value
        self.env.cr.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='mezze_aggregator' AND column_name='secret'")
        self.assertIsNone(self.env.cr.fetchone(), 'plaintext secret column still present')

    def test_orm_read_is_redacted(self):
        self.assertEqual(self.ch.secret, '***')
        data = self.ch.read(['secret', 'code', 'name'])[0]
        self.assertEqual(data['secret'], '***')
        self.assertNotIn('sekret-value', str(data))

    def test_secret_accessor_decrypts(self):
        self.assertEqual(self.ch._secret(), 'sekret-value')

    def test_fail_closed_on_bad_ciphertext(self):
        # a corrupted envelope decrypts to None (fail closed), never raises out
        self.ch.sudo().write({'secret_enc': 'v1:AESGCM:k:bad:bad'})
        self.assertIsNone(self.ch._secret())

    def test_migration_encrypts_legacy_plaintext(self):
        # simulate a legacy plaintext value sitting in the column (pre-encryption)
        self.ch.sudo().write({'secret_enc': 'legacy-plaintext'})
        self.env.flush_all()   # persist so the raw-SQL migration reads it
        n = self.env['mezze.aggregator']._migrate_plaintext_secrets()
        self.assertGreaterEqual(n, 1)
        self.env.flush_all()   # persist the migration's encryption write
        self.env.cr.execute("SELECT secret_enc FROM mezze_aggregator WHERE id=%s", (self.ch.id,))
        enc = self.env.cr.fetchone()[0]
        self.assertTrue(crypto.is_envelope(enc))
        self.ch.invalidate_recordset(['secret_enc'])
        self.assertEqual(self.ch._secret(), 'legacy-plaintext')

    def test_hmac_uses_decrypted_secret(self):
        import hashlib
        import hmac
        body = b'{"external_id":"x"}'
        expected = hmac.new(b'sekret-value', body, hashlib.sha256).hexdigest()
        server = hmac.new(self.ch._secret().encode(), body, hashlib.sha256).hexdigest()
        self.assertEqual(expected, server)

    def test_terminal_token_no_plaintext_at_rest(self):
        term = self.env['mezze.terminal'].create({
            'name': 'FP', 'identifier': 'FP-1', 'token': 'plain-bearer-token',
            'branch_id': self.cfg.id, 'role': 'terminal', 'active': True})
        self.env.flush_all()
        self.env.cr.execute("SELECT token, prev_token, token_fingerprint "
                            "FROM mezze_terminal WHERE id=%s", (term.id,))
        tok, prev, fp = self.env.cr.fetchone()
        self.assertFalse(tok, "plaintext bearer token stored at rest")
        self.assertFalse(prev)
        self.assertTrue(fp, "token fingerprint not stored")
        self.assertNotIn('plain-bearer-token', fp)   # fingerprint is not the token
        # the fingerprint is the keyed hash used for lookup
        self.assertEqual(fp, self.env['mezze.secret.store'].token_hash('plain-bearer-token'))
        # a generic ORM read never returns the bearer token
        self.assertFalse(term.read(['token'])[0]['token'])

    def test_terminal_migration_fingerprints_legacy_plaintext(self):
        term = self.env['mezze.terminal'].create({
            'name': 'LG', 'identifier': 'LG-1', 'token': 'x',
            'branch_id': self.cfg.id, 'role': 'terminal', 'active': True})
        # simulate a legacy plaintext value left in the column (pre-fingerprint)
        self.env.cr.execute("UPDATE mezze_terminal SET token=%s, token_fingerprint=NULL "
                            "WHERE id=%s", ('legacy-plain', term.id))
        n = self.env['mezze.terminal']._migrate_plaintext_tokens()
        self.assertGreaterEqual(n, 1)
        self.env.cr.execute("SELECT token, token_fingerprint FROM mezze_terminal WHERE id=%s", (term.id,))
        tok, fp = self.env.cr.fetchone()
        self.assertFalse(tok, "legacy plaintext not cleared")
        self.assertEqual(fp, self.env['mezze.secret.store'].token_hash('legacy-plain'))
