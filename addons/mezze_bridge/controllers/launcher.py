# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""The check-in page: sign in as yourself, then pick the register you work on.

Until now the only way into a Mezze surface was to know its URL and, worse, to
know its ``?config_id=``. That is fine for a test harness and wrong for a person:
a shift starts by choosing where you are standing, not by editing a query string.

Two rules shape this page.

* **It shows what YOU can reach, not what exists.** The branch list is read with
  the *user's own* environment, so Odoo's record rules and allowed companies do
  the filtering — the page never widens access, it only offers what the user
  already had. When the user is also a ``mezze.cashier`` with branches assigned,
  the list narrows further to those.
* **A station never sees a chooser.** A Windows station is enrolled to exactly one
  branch and one surface, decided by the manager who cut its code, so this page
  sends it straight there rather than asking a question it is not allowed to
  answer.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MezzeLauncher(http.Controller):

    # Surfaces a person can be sent to from here, in the order they are offered.
    # 'restaurant' entries only appear for a branch that actually runs tables.
    _SURFACES = (
        ('pos',       "Register",         '/mezze/pos',        False),
        ('floor',     "Floor",            '/mezze/floor',      True),
        ('kds',       "Kitchen",          '/mezze/kds',        False),
        ('drivethru', "Drive-thru",       '/mezze/drivethru',  False),
        ('ocb',       "Customer display", '/mezze/ocb',        False),
    )

    def _user_branches(self, env):
        """The pos.config records this user may actually open.

        Read with the USER's environment on purpose: company rules and record
        rules apply for free, and there is no way for this page to hand out a
        branch the user could not already read.
        """
        configs = env['pos.config'].search([], order='name')
        # A cashier with explicit branches is narrowed to them. An empty list keeps
        # the existing meaning of the field — unrestricted — and is not a filter.
        cashier = env['mezze.cashier'].sudo().search(
            [('user_id', '=', env.uid), ('active', '=', True)], limit=1)
        if cashier and cashier.config_ids:
            configs = configs.filtered(lambda c: c in cashier.config_ids)
        return configs

    def _branch_entry(self, config):
        session = config.current_session_id
        restaurant = bool(getattr(config, 'module_pos_restaurant', False))
        surfaces = [
            {'key': key, 'label': label, 'url': '%s%sconfig_id=%s' % (
                path, '&' if '?' in path else '?', config.id)}
            for key, label, path, needs_restaurant in self._SURFACES
            if not needs_restaurant or restaurant
        ]
        return {
            'id': config.id,
            'name': config.name,
            'company': config.company_id.name or '',
            'restaurant': restaurant,
            'session_open': bool(session and session.state in ('opened', 'opening_control')),
            'session_name': session.name if session else '',
            'surfaces': surfaces,
        }

    # ONE canonical entry point. A second alias path on the same decorator is not
    # independently introspectable, so the endpoint-coverage gate correctly refuses
    # to see it — and an endpoint the security registry cannot enumerate is exactly
    # the kind of thing that gate exists to catch.
    @http.route('/mezze/start', type='http', auth='user',
                methods=['GET'], website=False, readonly=True)
    def start(self, **kw):
        env = request.env

        # A station is not asked where it is. It was told at enrolment, and the
        # answer is server truth (WS-2) — showing it a chooser would invite exactly
        # the branch-switching the confinement exists to prevent.
        bound = env['mezze.station.surface.session'].sudo().branch_for_request()
        if bound:
            shift = env['mezze.station.surface.session'].sudo().resolve(
                request.session.get('mezze_surface_id'))
            target = shift.terminal_id.sudo().entry_surface() if shift else None
            if target:
                return request.redirect(target)

        branches = self._user_branches(env)
        return request.render('mezze_bridge.launcher_page', {
            'mz_user': env.user,
            'mz_lang': env.user.lang or env.context.get('lang') or 'en_US',
            'mz_branches': [self._branch_entry(c) for c in branches],
            'mz_is_pos_manager': env.user.has_group('point_of_sale.group_pos_manager'),
        })
