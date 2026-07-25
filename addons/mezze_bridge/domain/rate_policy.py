"""Pure rate-limit policy (P6.2 Phase 9-10). No Odoo, no I/O.

Defines the narrow per-operation limits for sensitive flows and the deterministic
limiter key (authoritative identity dimensions — never only an IP). The atomic
store lives in models/rate_limit.py; the gate consults these policies.
"""

# op -> (limit, window_seconds). Fixed-window counters. Tuned for restaurant peak
# (a busy terminal never legitimately refunds 30x/min or opens the drawer 60x/min).
LIMITS = {
    'orders/refund':   (10, 60),     # refund velocity per principal
    'orders/comp':     (10, 60),
    'orders/void':     (10, 60),
    'drawer/open':     (20, 60),     # drawer velocity per terminal
    'reports/refunds.csv': (5, 300),  # export velocity
    'gl/export.csv':   (5, 300),
    'breakglass':      (3, 300),     # break-glass activation attempts
    'auth_fail':       (30, 60),     # invalid-sig / unknown-principal storms
}

# endpoints checked by the gate AFTER authz (business-flow limits)
RATE_LIMITED_ENDPOINTS = frozenset({
    'orders/refund', 'orders/comp', 'orders/void', 'drawer/open',
    'reports/refunds.csv', 'gl/export.csv',
})


# --- risk-specific limiter failure policy (P6.3 Phase 14) --------------------
FAIL_CLOSED = 'closed'      # limiter unavailable -> DENY (high-risk / physical)
DEGRADED = 'degraded'       # limiter unavailable -> conservative process-local ceiling
FAIL_OPEN = 'open'          # limiter unavailable -> allow (never for high-risk)

FAILURE_MODE = {
    # financial mutations + physical control + data exfiltration -> fail closed
    'orders/refund': FAIL_CLOSED, 'orders/comp': FAIL_CLOSED, 'orders/void': FAIL_CLOSED,
    'drawer/open': FAIL_CLOSED,
    'reports/refunds.csv': FAIL_CLOSED, 'gl/export.csv': FAIL_CLOSED,
    'breakglass': FAIL_CLOSED,
    # auth-failure storms may degrade (never block real terminals) but stay bounded
    'auth_fail': DEGRADED,
}


def failure_mode(op):
    """Limiter-unavailable behaviour for an op. Default FAIL_CLOSED (safe): a new
    limited op is denied on limiter failure unless explicitly relaxed."""
    return FAILURE_MODE.get(op, FAIL_CLOSED)


def limit_for(op):
    return LIMITS.get(op)


def limit_key(op, principal, terminal=None, company=None, branch=None):
    """Deterministic limiter key from AUTHORITATIVE identity (principal/terminal),
    never a client-supplied or raw-forwarded value."""
    dims = [op, principal or 'anon']
    if terminal:
        dims.append('t:%s' % terminal)
    if company:
        dims.append('c:%s' % company)
    return '|'.join(dims)
