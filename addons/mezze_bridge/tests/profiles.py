"""Hermetic test fixture PROFILES for the Mezze suite (RC2 / D-2).

A profile is a named, minimal set of provisioning COMPONENTS. A test class declares
``fixture_profile = "PAYMENTS"`` and the fixture mixin provisions exactly those
components — never more. This keeps fast unit tests cheap and only pays for POS /
restaurant / omnichannel provisioning when a test genuinely needs it.

Test-only. Never imported by production code or install hooks.
"""

# --- component flags (atomic provisioning units) ---
C_COMPANY = 'company'          # company, currency, tz, base test users, branch, test secrets
C_ACCOUNTING = 'accounting'    # chart (journals + accounts) via AccountTestInvoicingCommon
C_POS = 'pos'                  # pricelist, category, products, cash+card payment methods, POS config
C_RESTAURANT = 'restaurant'    # restaurant-enabled config, floor, tables
C_KDS = 'kds'                  # KDS stations + routing + kitchen user
C_OMNICHANNEL = 'omnichannel'  # QR, pickup, delivery zone, aggregator, customer-status secret
C_ADMIN = 'admin'             # settings catalog assertion, templates, assignments, governance users

# --- profiles -> the components they expand to (dependencies included explicitly) ---
PROFILES = {
    'CORE':             {C_COMPANY},
    'POS':              {C_COMPANY, C_ACCOUNTING, C_POS},
    'PAYMENTS':         {C_COMPANY, C_ACCOUNTING, C_POS},
    'RESTAURANT':       {C_COMPANY, C_ACCOUNTING, C_POS, C_RESTAURANT},
    'KDS':              {C_COMPANY, C_ACCOUNTING, C_POS, C_RESTAURANT, C_KDS},
    'OMNICHANNEL':      {C_COMPANY, C_ACCOUNTING, C_POS, C_OMNICHANNEL},
    'ADMIN_GOVERNANCE': {C_COMPANY, C_ADMIN},
    'FULL':             {C_COMPANY, C_ACCOUNTING, C_POS, C_RESTAURANT, C_KDS, C_OMNICHANNEL, C_ADMIN},
}

# Profiles that require the real accounting chart (drive base-class selection).
POS_PROFILES = {name for name, comps in PROFILES.items() if C_ACCOUNTING in comps}


def resolve(profile):
    """Return the frozenset of components for a profile name (raises on unknown)."""
    if profile not in PROFILES:
        raise ValueError(
            "Unknown Mezze fixture_profile %r. Valid: %s" % (profile, sorted(PROFILES)))
    return frozenset(PROFILES[profile])


def needs(profile, component):
    return component in PROFILES.get(profile, set())
