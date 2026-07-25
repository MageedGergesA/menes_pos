"""Pure signing-policy state machine (P6.1). No Odoo, no I/O.

Resolves the effective signing handling (off / observe / enforce) for a request
from the deployment mode, the PRINCIPAL TYPE, and the route's sensitivity, and
provides the deterministic canonical signing string + production-safety checks.
The controller gate delegates every signing DECISION here so the policy lives in
one tested place; the crypto (hmac compare) stays in the gate.
"""

OFF = "off"
OBSERVE = "observe"
ENFORCE = "enforce"
_MODES = frozenset({OFF, OBSERVE, ENFORCE})

# principal types that are MACHINE clients — mandatory signing on sensitive routes.
MACHINE_PRINCIPALS = frozenset({"terminal", "integration", "admin"})


def default_mode_for(principal_type):
    """Default when no explicit config exists: OBSERVE (audit unsigned/invalid, do
    not block) so an un-migrated deployment is not broken. Mandatory ENFORCE for
    machine principals is required by the PRODUCTION profile (dangerous_config flags
    a machine type left below enforce in production), not by a silent global flip —
    that is the staged rollout the objective mandates (observe -> enforce)."""
    return OBSERVE


def mode_for(get_param, principal_type):
    """Resolve the signing mode for a principal type, most-specific first:
    per-type param -> global param -> secure default. ``get_param`` is a callable
    (str key -> value or None)."""
    v = get_param("mezze_bridge.signing_mode.%s" % principal_type)
    if v in _MODES:
        return v
    g = get_param("mezze_bridge.signing_mode")
    if g in _MODES:
        return g
    return default_mode_for(principal_type)


def effective(mode, endpoint, sig_required_set):
    """Given the resolved per-principal mode, return how signing is handled for
    this endpoint:
      * OFF     -> do not check
      * OBSERVE -> check; audit invalid/missing but do not block
      * ENFORCE -> check; block invalid/missing before business logic
    Sensitive routes (in sig_required_set) honour the mode directly; non-sensitive
    routes only require signing under a full ENFORCE mode."""
    if mode == OFF:
        return OFF
    if endpoint in sig_required_set:
        return mode                      # observe or enforce
    return ENFORCE if mode == ENFORCE else OFF


def canonical_string(method, path, body_sha256, timestamp, nonce, principal, kid, version="v1"):
    """Deterministic canonical signing input. Every field that changes request
    meaning is bound: algo version, key id, principal, method, exact route, body
    digest, timestamp, nonce. Equivalent legitimate requests -> identical string;
    any meaningful tamper -> different string."""
    return "\n".join((str(version), str(kid), str(principal), str(method).upper(),
                      str(path), str(body_sha256), str(timestamp), str(nonce)))


# --- production-configuration safety -----------------------------------------
def dangerous_config(profile, signing_global, per_type, nonce_required, skew_seconds,
                     shared_admin_enabled, breakglass):
    """Return a list of reasons a config is unsafe for the given profile
    ('production' is strict). Empty list == safe. Used by the startup/gate guard
    to FAIL CLOSED or loudly reject a silent weakening."""
    reasons = []
    prod = (profile == "production")
    # signing globally off in production is only allowed under explicit break-glass
    if prod and signing_global == OFF and not breakglass:
        reasons.append("signing_off_without_breakglass")
    # any machine principal type explicitly downgraded below enforce in production
    if prod and not breakglass:
        for pt in ("terminal", "integration", "admin"):
            if per_type.get(pt) in (OFF, OBSERVE):
                reasons.append("machine_signing_downgraded:%s" % pt)
    # nonce must be on whenever signing is being enforced anywhere
    enforcing = signing_global == ENFORCE or any(
        per_type.get(pt) == ENFORCE for pt in MACHINE_PRINCIPALS)
    if enforcing and not nonce_required:
        reasons.append("nonce_disabled_while_enforcing")
    # unbounded / absurd clock skew
    if skew_seconds is None or skew_seconds <= 0 or skew_seconds > 900:
        reasons.append("bad_clock_skew:%s" % skew_seconds)
    # indefinite universal shared-admin in production
    if prod and shared_admin_enabled:
        reasons.append("shared_admin_enabled_in_production")
    return reasons
