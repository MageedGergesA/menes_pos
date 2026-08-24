# -*- coding: utf-8 -*-
"""The platform's own records, on screens a manager can open.

Mezze grew as an API with its own front ends and the back office was left behind:
fifty-odd models, four with any view at all. That is fine right up to the first time
something goes wrong on a Tuesday — a reservation nobody can find, a delivery stuck
on a courier who went home, an aggregator order that never landed — and the only way
to look is a shell and a SQL client.

These tests load every action the way the web client loads it. Measured, not
assumed: Odoo 19 validates a view's arch against its model at install time, so a
field typo already refuses the upgrade — the negative control for this file failed
the install rather than a test. What ``get_views`` adds on top is the runtime path
the installer does not walk: view inheritance, group filtering, and the actual
list/form mode pair each action declares.

The audit log is asserted read-only. A trail somebody can edit from the back office
is not a trail, and the value of those rows is precisely that nobody can tidy them
up afterwards.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'mezze_backend_ui')
class TestBackendViews(TransactionCase):

    #: Every action this module puts in front of a manager.
    ACTIONS = [
        'action_mezze_reservations', 'action_mezze_waitlist',
        'action_mezze_deliveries', 'action_mezze_delivery_zones',
        'action_mezze_couriers', 'action_mezze_aggregators',
        'action_mezze_campaigns', 'action_mezze_printers',
        'action_mezze_scales', 'action_mezze_payment_devices',
        'action_mezze_audit_log',
    ]

    def test_01_every_action_exists(self):
        for xmlid in self.ACTIONS:
            act = self.env.ref('mezze_bridge.%s' % xmlid, raise_if_not_found=False)
            self.assertTrue(act, 'missing action: %s' % xmlid)

    def test_02_every_view_actually_renders(self):
        """The test that catches a field name typo.

        A view referencing a field that does not exist installs without complaint
        and fails the moment a human opens it — which, for a back office nobody
        looks at until something is wrong, means it fails exactly when it is needed.
        ``get_views`` is what the web client calls, so this fails the same way.
        """
        for xmlid in self.ACTIONS:
            act = self.env.ref('mezze_bridge.%s' % xmlid)
            model = self.env[act.res_model]
            modes = [m.strip() for m in (act.view_mode or 'list').split(',')]
            views = [(False, m) for m in modes]
            try:
                model.get_views(views)
            except Exception as exc:  # noqa: BLE001
                self.fail('%s (%s) does not render: %s' % (xmlid, act.res_model, exc))

    def test_03_the_menus_are_reachable(self):
        root = self.env.ref('mezze_bridge.menu_mezze_root', raise_if_not_found=False)
        self.assertTrue(root, 'no Mezze menu root')
        self.assertTrue(root.parent_id, 'the Mezze menu hangs off nothing')
        for xmlid in ('menu_mezze_reservations', 'menu_mezze_deliveries',
                      'menu_mezze_couriers', 'menu_mezze_aggregators',
                      'menu_mezze_printers', 'menu_mezze_audit'):
            item = self.env.ref('mezze_bridge.%s' % xmlid, raise_if_not_found=False)
            self.assertTrue(item, 'missing menu: %s' % xmlid)
            self.assertTrue(item.action, '%s opens nothing' % xmlid)

    def test_04_the_back_office_is_manager_only(self):
        # These records carry customer phone numbers and money.
        root = self.env.ref('mezze_bridge.menu_mezze_root')
        # v19 renamed ir.ui.menu.groups_id -> group_ids; read whichever this
        # version actually has rather than assuming.
        field = 'group_ids' if 'group_ids' in root._fields else 'groups_id'
        groups = root[field]
        self.assertTrue(groups, 'the Mezze menu is visible to everyone')
        self.assertIn(self.env.ref('point_of_sale.group_pos_manager'), groups)

    def test_05_the_audit_log_cannot_be_edited_from_the_back_office(self):
        """A trail somebody can tidy up is not a trail."""
        view = self.env.ref('mezze_bridge.view_mezze_audit_log_list')
        arch = view.arch_db or ''
        for locked in ('create="false"', 'edit="false"', 'delete="false"'):
            self.assertIn(locked, arch,
                          'the audit log list is missing %s' % locked)

    def test_06_the_rows_the_row_named_all_have_a_screen(self):
        """The parity row named these by name; none of them had one."""
        wanted = {
            'mezze.reservation', 'mezze.waitlist', 'mezze.delivery',
            'mezze.delivery.zone', 'mezze.courier', 'mezze.aggregator',
            'mezze.campaign', 'mezze.audit.log',
        }
        covered = {self.env.ref('mezze_bridge.%s' % a).res_model
                   for a in self.ACTIONS}
        self.assertFalse(wanted - covered,
                         'still no back-office screen for: %r' % (wanted - covered))
