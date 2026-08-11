# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""RC6 DEFECT-01 — one Register/Floor client = one terminal identity.

Before this, the Register and the Floor both resolved their ``mezze.terminal`` by
``cashier-web-<pos_config_id>`` — an identifier derived from the **configuration**
alone. A POS config is configuration identity, not client-session identity, so every
browser opening the Register on the same config found the *same* terminal row, minted a
fresh bearer token onto it and silently evicted whoever held the previous one. The
symptom was a workspace that rendered and then failed every API call with 401
("Couldn't load reservations."), with nothing to tell the user another device had taken
over.

The fix keeps the existing architecture and adds no schema:

* the terminal identifier becomes ``cashier-web-<config_id>-<rid>``, where ``rid`` is an
  opaque, server-issued **register-instance locator**. ``mezze.terminal.identifier``
  already carries a UNIQUE constraint, so distinct clients get distinct rows for free —
  no new model, no new column, no migration.
* ``rid`` is a LOCATOR, never a credential. Presenting one never returns an existing
  token: the server always mints a new secret for the page, and the route itself is
  ``auth='user'``, so an anonymous caller cannot mint anything at all. Knowing another
  client's ``rid`` therefore authenticates nothing.
* it is issued by the server (72 bits from ``secrets``), not by the browser, and is
  carried in an HttpOnly cookie scoped to ``/mezze``. HttpOnly because the page has no
  reason to read it — this deliberately does NOT widen token exposure, and no bearer
  secret is placed in ``localStorage``/``sessionStorage``, which was not part of the
  existing design and is not introduced here.
* re-opening an existing instance now goes through the model's own ``rotate_token()``
  instead of a raw ``write({'token': ...})``. That was the second half of the defect: the
  raw write replaced ``token_fingerprint`` without preserving the outgoing one, so the
  bounded grace window the model already implements never applied. A reload now leaves
  the outgoing token briefly valid instead of hard-killing an in-flight page.

**Policy, stated rather than implied:** the locator lives in a cookie, so it is scoped to
a browser profile. Two *different* devices or browsers on the same POS config get
independent terminals and never evict each other — that is the pilot-critical contract.
Two tabs of the *same* browser profile deliberately share one terminal identity: they are
one physical register, and the rotation grace window keeps the older tab working across a
reload.
"""
import secrets

RID_COOKIE = 'mezze_rid'
RID_PATH = '/mezze'
# a locator, not a secret: enough entropy to be unguessable, short enough to read in a log
RID_BYTES = 9


def _clean(raw):
    """Accept only our own shape — never trust a client-supplied identifier fragment."""
    if not raw:
        return None
    raw = str(raw).strip()
    if 8 <= len(raw) <= 64 and all(c.isalnum() or c in '-_' for c in raw):
        return raw
    return None


def resolve_rid(request):
    """Return (rid, is_new) for this browsing context. Never raises."""
    rid = _clean(request.httprequest.cookies.get(RID_COOKIE))
    if rid:
        return rid, False
    return secrets.token_urlsafe(RID_BYTES), True


def stamp_rid(response, rid, is_new):
    """Persist the locator for subsequent loads of this browsing context."""
    if not is_new or response is None or not hasattr(response, 'set_cookie'):
        return response
    response.set_cookie(RID_COOKIE, rid, path=RID_PATH, httponly=True, samesite='Lax')
    return response


def terminal_identifier(config_id, rid):
    return 'cashier-web-%s-%s' % (config_id, rid)


def mint_for_instance(env, config, rid, name_hint='Cashier Web'):
    """Find-or-create THIS client's terminal and hand its page a fresh secret.

    Returns (plaintext_token, terminal). Least privilege is unchanged
    (``role='terminal'``, branch-scoped) and no broader principal is introduced.
    """
    Term = env['mezze.terminal'].sudo()
    identifier = terminal_identifier(config.id, rid)
    term = Term.with_context(active_test=False).search(
        [('identifier', '=', identifier)], limit=1)
    if term:
        # Rotate through the model so the outgoing key survives its grace window.
        # A revoked terminal stays revoked: reopening a page must not silently
        # re-activate a principal an operator disabled on purpose.
        if not term.active:
            return None, term
        token = term.rotate_token()
        term.write({'branch_id': config.id, 'role': 'terminal'})
        return token, term
    token = secrets.token_urlsafe(24)
    term = Term.create({
        'name': '%s — %s' % (name_hint, config.name),
        'identifier': identifier,
        'token': token,
        'branch_id': config.id,
        'active': True,
        'role': 'terminal',
    })
    return token, term
