# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""WS-1 — policy for turning a device-authenticated station into a staff session.

WS-0 answered "which machine is this?" with a key the machine cannot export. It
deliberately stopped there, because Mezze's staff surfaces (``/mezze/pos``,
``/mezze/kds``, ``/mezze/floor``, ``/mezze/drivethru``) are ``auth='user'`` and a
device key is not a person.

The rule this module encodes:

    the DEVICE proves the machine (its private key),
    the PERSON proves themselves (a PIN against ``mezze.cashier``),
    and the SERVER mints a short, path-confined Odoo session bound to both.

No Odoo user password is ever typed on a till, and no user credential is ever
stored on the station — which is the whole property WS-0 exists to protect. What
the station holds afterwards is a cookie that expires, that an operator can kill
from the console, and that cannot reach anything outside the POS surfaces.

Everything here is pure policy: no ORM, no request, no clock. That keeps the
decisions testable on their own and keeps the controller free of judgement calls.
"""

# --------------------------------------------------------------------- windows
# A shift, not a day. An absolute ceiling means a till that nobody clocks out of
# is signed out by morning regardless of activity.
SURFACE_TTL_SECONDS = 8 * 3600

# And an idle cut-off, because the real risk is not a long shift, it is a till
# left unattended at a counter. 20 minutes is long enough not to punish a quiet
# Tuesday and short enough that an abandoned station is not an open register.
SURFACE_IDLE_SECONDS = 20 * 60

# Writing last_seen on every request would be a write per page-load per station.
# One a minute is enough to enforce a 20-minute idle rule and costs nothing.
SURFACE_TOUCH_SECONDS = 60

# ------------------------------------------------------------------- throttling
# A PIN is four digits. Without a ceiling that is ten thousand guesses, and an
# unattended till gives an attacker all night. Both limits are per rolling window
# and FAIL CLOSED: if the shared limiter is unavailable we refuse the sign-in
# rather than let an outage become unlimited attempts.
#
# Only FAILURES are counted, and that distinction is load-bearing. Counting every
# attempt is simpler, and it turns the control into an outage: a manager approving
# ten comps in a busy quarter-hour would be locked out of the eleventh. A successful
# PIN therefore costs nothing.
#
# Doing that safely needs a check that does not itself consume budget, which is why
# mezze.rate.limit grew a peek(): look first, verify second, count only on failure.
# The naive alternative — verify first, then decide whether to count — hands an
# attacker unlimited PBKDF2 work and a timing signal.
#
# Ten failures per window turns 10,000 combinations into roughly 250 hours, against
# a device an operator can revoke from the console in seconds.
PIN_WINDOW_SECONDS = 15 * 60
PIN_MAX_PER_STAFF = 10     # this station, this staff code
PIN_MAX_PER_DEVICE = 30    # this station, any code — stops code enumeration

# Approvals (void, refund, discount override) are guarded by the same kind of
# PIN, and today they have no ceiling at all — a pre-existing gap that matters
# more now that the same PIN opens a shift. Same shape, same reasoning.
APPROVAL_WINDOW_SECONDS = 15 * 60
APPROVAL_MAX_PER_STAFF = 10
APPROVAL_MAX_PER_SOURCE = 30


def pin_keys(device_uuid, staff_code):
    """The two rate-limit keys for one PIN attempt.

    Keyed on the DEVICE, never on the client's IP: a till behind NAT shares an
    address with the whole restaurant, and an attacker who can pick their source
    address could otherwise reset their own budget.
    """
    dev = device_uuid or 'unknown-device'
    code = (staff_code or '').strip().lower() or 'unknown-code'
    return (
        ('mezze.pin:%s:%s' % (dev, code), PIN_MAX_PER_STAFF),
        ('mezze.pin.device:%s' % dev, PIN_MAX_PER_DEVICE),
    )


def approval_keys(source, staff_code):
    """Rate-limit keys for a manager-approval PIN prompt."""
    src = source or 'unknown-source'
    code = (staff_code or '').strip().lower() or 'unknown-code'
    return (
        ('mezze.approval:%s:%s' % (src, code), APPROVAL_MAX_PER_STAFF),
        ('mezze.approval.source:%s' % src, APPROVAL_MAX_PER_SOURCE),
    )


# ------------------------------------------------------- which roles need a human
# Customer-facing stations are unattended by design: a kiosk with a sign-in
# screen is a kiosk nobody uses. They stay on the device session alone and must
# NOT be able to mint a staff session, because a self-order terminal in a lobby
# is the least supervised device in the building.
CUSTOMER_ROLES = frozenset({'kiosk', 'ocb'})

STAFF_ROLES = frozenset({
    'register', 'kds', 'floor',
    'drivethru_order', 'drivethru_ops', 'drivethru_payment', 'drivethru_pickup',
})


def requires_staff_session(station_role):
    """True when this station's surface is ``auth='user'`` and needs a person."""
    return station_role in STAFF_ROLES


def may_open_staff_session(station_role):
    """Refusal reason for a station that must never mint a staff session, else None."""
    if station_role in CUSTOMER_ROLES:
        return 'customer_surface'
    if station_role not in STAFF_ROLES:
        return 'unknown_role'
    return None


# ------------------------------------------------- what a station session may reach
# The service user behind a station session is least-privilege by group, but
# groups alone would still leave the Odoo backend reachable by URL. So a stamped
# session is CONFINED to the paths a POS surface actually needs, server-side.
#
# This is authorization, not chrome-hiding: the check runs before dispatch and
# returns 403 no matter what the client asks for. Typing /odoo into a station
# gets you nothing.
ALLOWED_PREFIXES = (
    '/mezze/',              # the product itself
    '/web/assets/',         # bundles
    '/web/static/',
    '/web/image',           # product images (also /web/image/...)
    '/web/binary/',         # attachments the surfaces render
    '/web/webclient/',      # translations, versioned bundles
    '/websocket',           # bus, for live KDS/floor updates
    '/longpolling/',        # bus fallback
    '/web/health',
)

# Exact paths that must stay reachable so a station can end its own session and
# so Odoo can serve the basics.
ALLOWED_EXACT = frozenset({
    '/web/session/logout',
    '/web/session/get_session_info',
    '/favicon.ico',
    '/robots.txt',
})


def path_allowed(path):
    """True when a station-confined session may reach ``path``."""
    if not path:
        return False
    if path in ALLOWED_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES)


# ----------------------------------------------------------------- surface match
# A station opens the surface its ROLE was enrolled for. A KDS that asks for the
# register is not a mistake to be forgiven; it is either misconfigured or lying,
# and both deserve the same answer.
#
# Only the SURFACE PAGES are policed here. API routes under /mezze/api are
# capability-checked by the canonical gate, and assets have no identity at all —
# blocking those would break the very page we just allowed.
def surface_paths(role_surface_map):
    """Every surface path any station role can own, as bare paths."""
    return {v[1].split('?')[0] for v in role_surface_map.values() if v and v[1]}


def surface_refusal(station_role, path, role_surface_map):
    """Refusal reason when this station asks for a surface that is not its own.

    Returns None to allow. A path that is not a station surface at all (an API
    call, an asset, the kiosk's static entry) is not this rule's business.
    """
    if not path:
        return None
    bare = path.split('?')[0].rstrip('/') or '/'
    owned = role_surface_map.get(station_role or '')
    owned_path = owned[1].split('?')[0].rstrip('/') if owned and owned[1] else None
    known = {p.rstrip('/') for p in surface_paths(role_surface_map)}
    if bare not in known:
        return None                      # not a surface page — not our decision
    if owned_path and bare == owned_path:
        return None
    return 'wrong_surface'
