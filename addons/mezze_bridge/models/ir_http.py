# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Two request-level concerns: frontend translations, and station shift enforcement.

The second one is the load-bearing half of WS-1. A station's staff session is an
ordinary Odoo cookie, and an ordinary Odoo cookie has neither a short life nor a
boundary. Both are added here, before dispatch, so that:

* a shift ends when the clock says so, when the till goes idle, when the device is
  revoked or when the person is deactivated — not whenever the page next asks;
* a session opened for a till can reach the Mezze surfaces and nothing else.

That second rule is why this lives in ``_authenticate_explicit`` rather than in a
menu or a template. Hiding navigation is not authorization: the station runs a
browser, and a browser can be pointed anywhere. The server has to be the one that
says no.
"""
import logging

import werkzeug.exceptions

from odoo import api, models
from odoo.http import request

from ..domain import station_surface
from . import mezze_station

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    # ---------------------------------------------------------------- translations
    @classmethod
    def _get_translation_frontend_modules_name(cls):
        """Expose this addon's translations to the frontend JS bundle.

        A custom module's translations are not shipped to the browser unless the
        module is listed as a "frontend translation module". The standalone Owl
        cashier (``/mezze/pos``) loads ``/web/webclient/translations`` at boot;
        adding ``mezze_bridge`` here makes its ``i18n/*.po`` terms available to
        that fetch so the cashier chrome renders in the user's language.
        """
        modules = super()._get_translation_frontend_modules_name()
        if 'mezze_bridge' not in modules:
            modules = modules + ['mezze_bridge']
        return modules

    # -------------------------------------------------------------- station shifts
    @classmethod
    def _authenticate_explicit(cls, auth):
        # BEFORE super(), deliberately. ``_auth_method_user`` only asks whether a
        # uid is present; if we invalidated the shift afterwards the request would
        # already have been authenticated as the service user. Ending it first
        # means the standard method sees no uid and raises SessionExpired, which
        # is the behaviour every Odoo client already understands.
        cls._mezze_enforce_station_shift()
        super()._authenticate_explicit(auth)

    @classmethod
    def _mezze_enforce_station_shift(cls):
        """Validate and confine a session that was opened by a Mezze Station.

        Runs on every request, so it does nothing at all — not even a query — for
        the ordinary Odoo user, who has no station stamp in their session.
        """
        session = getattr(request, 'session', None)
        if not session:
            return
        shift_id = session.get('mezze_surface_id')
        if not shift_id:
            return                      # not a station session; nothing to enforce

        shift = request.env(su=True)['mezze.station.surface.session'].resolve(shift_id)
        if not shift:
            # Expired, idle, clocked out, device revoked or staff deactivated —
            # ``resolve`` decides which and records it. From here they are all the
            # same answer: this cookie is no longer a shift.
            cls._mezze_end_station_session()
            return

        path = request.httprequest.path or ''

        # A station opens the surface its role was enrolled for, and no other.
        # Without this the confinement below would happily let a register open
        # the kitchen display: "the server decides which surface a station owns"
        # was a policy that existed and was never asked.
        refusal = station_surface.surface_refusal(
            shift.station_role, path, mezze_station.ROLE_SURFACE)
        if refusal:
            _logger.info("station shift %s (%s) refused surface %s",
                         shift.id, shift.station_role, path)
            raise werkzeug.exceptions.Forbidden(
                "This station is enrolled for a different surface.")

        if not station_surface.path_allowed(path):
            # Deliberately NOT a redirect to the backend: a till that wanders is
            # told no, and the shift survives, so a stray request does not sign a
            # cashier out mid-order.
            _logger.info("station shift %s refused off-surface path %s", shift.id, path)
            raise werkzeug.exceptions.Forbidden(
                "This station is confined to the Mezze surfaces.")

        shift.touch()

    @classmethod
    def _mezze_end_station_session(cls):
        """Drop a station session that is no longer valid, and keep serving.

        Both halves matter: clearing the session stops the cookie being a shift,
        and resetting the environment stops the request finishing as the service
        user on an environment that was built before we said no.
        """
        try:
            request.session.logout(keep_db=True)
        except Exception:  # noqa: BLE001 — never turn a stale shift into a 500
            _logger.debug('station session logout failed', exc_info=True)
        try:
            request.env = api.Environment(request.env.cr, None, request.session.context)
            request.env.transaction.default_env = request.env
        except Exception:  # noqa: BLE001
            _logger.debug('station session env reset failed', exc_info=True)
