"""Structural regression guards for the P6.1 activation (Phase 14).

Fail the build if the activation is silently undone: signing policy removed, nonce
verification removed, durable telemetry removed, client-supplied scope trusted for
authorization, terminal principals granted all capabilities, production hardening
removed, or an unsafe sudo() bypass introduced around the protected target lookup.
"""
import glob
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
import sys as _sys
_sys.path.insert(0, _ROOT)


def _read(rel):
    with open(os.path.join(_ROOT, rel), encoding='utf-8') as fh:
        return fh.read()


def run_checks():
    f = []
    main = _read('controllers/main.py')
    seccfg = _read('models/security_config.py')

    # 1) signing policy state machine is wired into the gate
    if 'signing_policy.effective' not in main or 'signing_policy.mode_for' not in main:
        f.append('signing_policy_not_wired')
    # 2) nonce verification present (durable claim on a valid signature)
    if "env['mezze.api.nonce'].claim(" not in main:
        f.append('nonce_verification_removed')
    # 3) canonical signing binds method + route + body + kid + principal + nonce + ts
    if 'signing_policy.canonical_string' not in main:
        f.append('canonical_signing_removed')
    # 4) durable denial telemetry via an independent cursor
    if 'db_connect(env.cr.dbname).cursor()' not in main or 'api.security_denied' not in main:
        f.append('durable_denial_telemetry_removed')
    # 5) the gate must NOT trust a client-supplied company/branch for AUTHORIZATION
    #    (scope is derived from the authoritative target record / principal only)
    gate = re.search(r"def _security_gate\(.*?def _audit_security", main, re.S)
    resolve = re.search(r"def _resolve_principal\(.*?def _resolve_signing_key", main, re.S)
    for name, blob in (('gate', gate), ('resolve_principal', resolve)):
        if blob and re.search(r"params\.get\(['\"](company_id|branch_id)['\"]\)", blob.group(0)):
            f.append('client_scope_trusted_in_%s' % name)
    # 6) terminal principals get least privilege (role caps), never ALL for a terminal
    if 'authz.capabilities_for(principal_type)' not in main:
        f.append('terminal_least_privilege_removed')
    # 7) production configuration hardening present + fails closed
    if ('_is_weakening' not in seccfg or 'raise UserError' not in seccfg
            or 'env_profile' not in seccfg):
        f.append('production_hardening_removed')
    # 8) no sudo() bypass introduced around the protected order target lookup in the
    #    money endpoints (the gate resolves scope from the record, not a sudo peek)
    for eid in ('order_pay', 'order_refund'):
        m = re.search(r"def %s\(.*?(?=\n    @http\.route|\n    def [a-z])" % eid, main, re.S)
        if m and re.search(r"pos\.order'\]\.sudo\(\)\.(browse|search)", m.group(0)):
            f.append('sudo_target_bypass_in_%s' % eid)

    # --- P6.2 secret-closure guards ---
    agg = _read('models/aggregator.py')
    secstore = _read('models/secret_store.py')
    crypto_src = _read('domain/crypto.py')
    # 9) the aggregator HMAC secret must be a NON-STORED, redacted, compute field —
    #    never a plaintext stored Char
    if "secret = fields.Char(compute='_compute_secret'" not in agg or 'store=False' not in agg:
        f.append('secret_not_write_only_redacted')
    # 10) the ciphertext column must be group-restricted (not read by ordinary ORM)
    if "secret_enc = fields.Char(" not in agg or "groups='base.group_system'" not in agg:
        f.append('secret_enc_not_restricted')
    # 11) verification retrieves via the centralized store only (no direct ciphertext use)
    if "self.env['mezze.secret.store'].decrypt(" not in agg:
        f.append('secret_access_not_centralized')
    # 12) master key loaded from the ENVIRONMENT, never DB/source
    if "os.environ.get(env_var)" not in crypto_src and "os.environ.get('MEZZE_MASTER_KEY')" not in crypto_src:
        f.append('master_key_not_from_env')
    if 'get_param' in secstore and 'master' in secstore.lower() and 'environ' not in secstore:
        f.append('master_key_from_db')
    # 13) real authenticated encryption (AES-GCM), not reversible encoding
    if 'AESGCM' not in crypto_src:
        f.append('not_authenticated_encryption')
    # 14) shared-admin disabled in the production profile at auth time (only a live
    #     scoped emergency activation admits it)
    if "profile == 'production' and not emergency" not in main:
        f.append('shared_admin_not_disabled_in_production')
    # 15) the gate wires the atomic rate limiter for sensitive flows
    if 'rate_policy.RATE_LIMITED_ENDPOINTS' not in main or "rate.limit'].hit(" not in main:
        f.append('rate_limiter_not_wired')
    # 16) high-risk routes must carry a limiter policy
    from domain import rate_policy as _rp
    for hr in ('orders/refund', 'orders/comp', 'orders/void', 'drawer/open'):
        if hr not in _rp.RATE_LIMITED_ENDPOINTS:
            f.append('high_risk_route_unlimited:%s' % hr)

    # --- P6.3 guards ---
    from domain import route_scope as _rs
    hw = _read('controllers/hardware.py')
    allsrc = main + hw
    # 17) every object-scoped route actually calls the gate with a target
    for eid in _rs.OBJECT_SCOPED:
        if eid in ('orders/pay', 'orders/refund', 'orders/comp', 'orders/fire', 'orders/void'):
            if "target_order=" not in allsrc:
                f.append('money_route_target_removed')
        elif ("'%s', target=" % eid) not in allsrc and ('"%s", target=' % eid) not in allsrc:
            f.append('object_scope_removed:%s' % eid)
    # 18) high-risk limiter failure must be FAIL_CLOSED (never globally fail-open)
    for op in ('orders/refund', 'orders/void', 'drawer/open', 'gl/export.csv', 'breakglass'):
        if _rp.failure_mode(op) != _rp.FAIL_CLOSED:
            f.append('high_risk_not_fail_closed:%s' % op)
    if 'fail_mode=rate_policy.FAIL_CLOSED' not in _read('models/rate_limit.py') and \
            "fail_mode=" not in main:
        f.append('limiter_failure_mode_not_wired')
    # 19) cryptography dependency is declared (not the obsolete version)
    man = _read('__manifest__.py')
    if "'python': ['cryptography']" not in man:
        f.append('crypto_dependency_not_declared')

    # --- Pilot P6.5 guards ---
    term = _read('models/mezze_terminal.py')
    emerg = _read('models/emergency_access.py')
    # 20) terminal bearer token is fingerprinted, never stored plaintext
    if 'token_fingerprint' not in term or '_secure_token_vals' not in term:
        f.append('terminal_token_not_fingerprinted')
    if "vals[src] = False" not in term:      # plaintext blanked on write
        f.append('terminal_plaintext_not_blanked')
    # 21) principal resolver looks up by fingerprint (not plaintext-first)
    if "token_hash(token)" not in main or "token_fingerprint" not in main:
        f.append('principal_lookup_not_by_fingerprint')
    # 22) emergency access is scoped + expiring + revocable (not a bare flag)
    for needle in ('expires_at', 'MAX_HOURS', 'def revoke', 'def caps', 'capabilities'):
        if needle not in emerg:
            f.append('emergency_missing:%s' % needle)
    if "env['mezze.emergency.access'].current()" not in main:
        f.append('emergency_not_wired')
    return f


if __name__ == '__main__':
    fails = run_checks()
    print("P6.1 structural guards")
    print("  failures:", fails if fails else "none")
    print("RESULT:", "PASS" if not fails else "FAIL")
    raise SystemExit(0 if not fails else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestP61Structural(TransactionCase):
        def test_structural(self):
            self.assertEqual(run_checks(), [], "P6.1 structural guards failed")
except Exception:
    pass
