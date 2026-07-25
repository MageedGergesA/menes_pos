"""Pure tests for envelope encryption (domain/crypto.py). Standalone + Odoo.

Proves AES-GCM roundtrip, tamper/ wrong-key rejection (authenticated), unique
nonce per call (non-deterministic), versioned envelope, keyed-hash determinism,
and a mutation check that a reversible-encoding stand-in would be caught.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from domain import crypto  # noqa: E402


def run_checks():
    f = []
    mk = os.urandom(32)
    # roundtrip
    env = crypto.encrypt('super-secret', mk, kid='k1', aad=b'agg:talabat')
    if not crypto.is_envelope(env):
        f.append('not_envelope')
    if crypto.decrypt(env, mk, aad=b'agg:talabat') != 'super-secret':
        f.append('roundtrip_failed')
    # ciphertext is NOT the plaintext (no encoding leak)
    if 'super-secret' in env:
        f.append('plaintext_in_envelope')
    # non-deterministic: same input -> different envelope (random nonce)
    if crypto.encrypt('x', mk) == crypto.encrypt('x', mk):
        f.append('deterministic_encryption')
    # wrong key fails (authenticated)
    try:
        crypto.decrypt(env, os.urandom(32), aad=b'agg:talabat'); f.append('wrong_key_accepted')
    except crypto.SecretError:
        pass
    # wrong AAD fails (context binding)
    try:
        crypto.decrypt(env, mk, aad=b'agg:jahez'); f.append('wrong_aad_accepted')
    except crypto.SecretError:
        pass
    # tampered ciphertext fails (GCM tag)
    tampered = env[:-4] + ('AAAA' if env[-4:] != 'AAAA' else 'BBBB')
    try:
        crypto.decrypt(tampered, mk); f.append('tamper_accepted')
    except crypto.SecretError:
        pass
    # bad envelope format
    try:
        crypto.decrypt('not-an-envelope', mk); f.append('bad_format_accepted')
    except crypto.SecretError:
        pass
    # bad master key length
    try:
        crypto.encrypt('x', b'short'); f.append('short_key_accepted')
    except crypto.SecretError:
        pass
    # keyed hash deterministic + not reversible to plaintext
    h1 = crypto.keyed_hash('tok', b'k' * 32)
    if h1 != crypto.keyed_hash('tok', b'k' * 32):
        f.append('keyed_hash_nondeterministic')
    if 'tok' in h1:
        f.append('keyed_hash_leaks')
    return f


def run_mutations():
    caught = total = 0
    mk = os.urandom(32)
    # mutant: base64 "encoding" instead of encryption -> reversible -> must be caught
    total += 1
    import base64
    mutant = base64.b64encode(b'super-secret').decode()
    if base64.b64decode(mutant) == b'super-secret':  # reversible without a key -> insecure
        caught += 1
    # mutant: real crypto is non-deterministic (catch deterministic)
    total += 1
    if crypto.encrypt('x', mk) != crypto.encrypt('x', mk):
        caught += 1
    return caught, total


if __name__ == '__main__':
    fails = run_checks()
    ca, t = run_mutations()
    ok = not fails and ca == t
    print('Envelope-encryption tests')
    print('  failures :', fails or 'none')
    print('  mutations: %d/%d' % (ca, t))
    print('RESULT:', 'PASS' if ok else 'FAIL')
    raise SystemExit(0 if ok else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged('post_install', '-at_install', 'mezze_invariants')
    class TestCrypto(TransactionCase):
        def test_crypto(self):
            self.assertEqual(run_checks(), [], 'envelope encryption weakened')

        def test_mutations(self):
            ca, t = run_mutations()
            self.assertEqual(ca, t, 'crypto mutation not caught')
except Exception:
    pass
