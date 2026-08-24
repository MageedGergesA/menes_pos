# -*- coding: utf-8 -*-
"""Who may authorise somebody else's discount.

Found by mutation, and the finding is subtler than a bug. Deleting the capability
check in the over-ceiling approval path —

    if _appr and authz.ORDERS_DISCOUNT in authz.capabilities_for(_appr.role):

— broke **no test in the suite**. That is not because the check is unguarded; it is
because it is currently *redundant*. Two gates stand in front of that line, and they
happen to coincide today:

* ``_verify_inline_approver(..., min_rank=APPROVER_MIN_RANK)`` refuses any PIN whose
  role ranks below supervisor, and ``rank_of`` gives an unknown role 0;
* every role that reaches that rank — supervisor, manager, admin, administrator —
  also holds ``orders.discount``.

So no principal exists that the rank gate admits and the capability gate would
reject, and no test can tell the two apart. The check is defence in depth.

The coincidence is the fragile part. It holds because of the *current* contents of
two tables that live in different modules, and nothing connects them. Add a
``shift_lead`` at rank 1 for reservations, or a ``finance_manager`` who should never
touch a price, and the capability check silently becomes load-bearing — at which
point deleting it would still break no test, and an over-ceiling discount would be
approvable by someone with no authority to give one.

This file tests the coincidence itself rather than the branch, because the coincidence
is the thing that can quietly stop being true.
"""
from odoo.tests import TransactionCase, tagged

from ..domain import authz, discount as discount_policy


@tagged('post_install', '-at_install', 'mezze_invariants')
class TestApproverInvariant(TransactionCase):

    def test_01_every_approver_may_actually_discount(self):
        """A role senior enough to approve must hold the right it is approving.

        If this fails, someone added a role that outranks the approval threshold
        without giving it ``orders.discount``. That is not necessarily wrong — but
        it means the capability check in the over-ceiling path has just become the
        only thing standing between that role and authorising a discount, so it
        must not be removed as "redundant".
        """
        offenders = sorted(
            role for role in authz.ROLE_CAPS
            if discount_policy.can_approve(role)
            and authz.ORDERS_DISCOUNT not in authz.ROLE_CAPS[role])
        self.assertEqual(
            offenders, [],
            'these roles can approve an over-ceiling discount but hold no '
            'discount right of their own: %r — the capability check in '
            'controllers/main.py is now load-bearing, not redundant' % offenders)

    def test_02_the_rank_floor_is_above_a_plain_cashier(self):
        # Nobody authorises their own over-ceiling discount.
        self.assertGreater(discount_policy.APPROVER_MIN_RANK,
                           discount_policy.rank_of('cashier'))
        self.assertFalse(discount_policy.can_approve('cashier'))

    def test_03_an_unknown_role_never_approves(self):
        # rank_of defaults to 0, so a typo or a role from a newer version cannot
        # accidentally inherit approval authority.
        for role in ('shift_lead', 'finance_manager', '', None, 'ADMIN'):
            self.assertFalse(discount_policy.can_approve(role),
                             '%r was treated as an approver' % (role,))

    def test_04_the_roles_that_do_approve_are_the_expected_three(self):
        # Pins the set, so widening it is a deliberate edit with a test to update
        # rather than a side effect of touching the rank table.
        approvers = sorted(r for r in authz.ROLE_CAPS
                           if discount_policy.can_approve(r))
        self.assertEqual(approvers, ['admin', 'administrator', 'manager', 'supervisor'])
