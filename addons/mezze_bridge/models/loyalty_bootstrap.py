# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Create the Mezze loyalty programme once, at install/upgrade time.

Mezze read a programme named ``Mezze Rewards`` on every loyalty call and nothing in
the addon ever created it — not the data files, the post-init hook, onboarding or
the migrations. On a fresh install loyalty was therefore inert: no points earned, an
always-empty rewards list, and ``"no loyalty programme configured"`` from offline
sync. Gift cards self-provisioned; loyalty did not.

Provisioning belongs HERE and not in a request. The obvious lazy fix — create it on
first read — puts an INSERT inside routes like ``/loyalty/search`` that Odoo runs on
a **read-only cursor**, which does not merely fail: it aborts the transaction, so the
search that prompted it fails too. That is the same class of defect as a read route
that quietly writes a config parameter.
"""
PROGRAM_NAME = 'Mezze Rewards'


def ensure_loyalty_program(env):
    """Find-or-create the programme. Idempotent; never overwrites an existing one."""
    Program = env['loyalty.program'].sudo()
    prog = Program.search(
        [('name', '=', PROGRAM_NAME), ('program_type', '=', 'loyalty')], limit=1)
    if prog:
        return prog
    # One point per unit of currency — the shape ``_loyalty_earn`` already assumed
    # when it read ``rule_ids[:1]``. A branch that wants different economics edits
    # the programme in Odoo; nothing here touches it again.
    return Program.create({
        'name': PROGRAM_NAME,
        'program_type': 'loyalty',
        'applies_on': 'both',
        'trigger': 'auto',
        'rule_ids': [(0, 0, {'reward_point_mode': 'money',
                             'reward_point_amount': 1.0})],
        'reward_ids': [(0, 0, {'reward_type': 'discount',
                               'discount': 10.0,
                               'discount_mode': 'per_order',
                               'discount_applicability': 'order',
                               'required_points': 100.0})],
    })


def ensure_giftcard_payment_method(env):
    """Make sure every branch can actually TAKE a gift card or a wallet.

    The gift-card ``pos.payment.method`` was found-or-created on first use, inside
    the payment call — and Odoo refuses to change a ``pos.config``'s payment methods
    while one of its sessions is open. So on a live till the method existed but was
    not linked to the config, and ``pos.payment`` rejected it with "The payment
    method selected is not allowed in the config of the POS session." The first gift
    card of the day failed, every day, and the only cure was closing the session.

    Provisioning belongs at install/upgrade for the same reason the programme does:
    it is a one-off structural change, and doing it inside a request means doing it
    at the one moment Odoo forbids it.

    Two details worth keeping:

    * a journal is set. A ``pos.payment.method`` without one is typed ``pay_later``,
      which Mezze classifies as a customer account — so the credit gate demanded a
      customer before it would take a gift card, and an anonymous guest was refused.
      A gift card is prepaid; the money arrived when the card was sold.
    * the link is skipped for a config with an open session rather than forced. This
      runs at install/upgrade, when that is rare, and a forced write would raise and
      take the whole upgrade down over one till someone left open.
    """
    PM = env['pos.payment.method'].sudo()
    Journal = env['account.journal'].sudo()
    linked = []
    for config in env['pos.config'].sudo().search([]):
        company = config.company_id
        has_open = env['pos.session'].sudo().search_count(
            [('config_id', '=', config.id), ('state', '!=', 'closed')])
        # Both PREPAID instruments: a gift card the guest is holding, and a wallet
        # that belongs to them. Neither is credit, so neither may be typed pay_later.
        for name in ('Gift Card', 'eWallet'):
            pm = PM.search([('name', '=', name),
                            ('company_id', '=', company.id)], limit=1)
            if not pm:
                journal = Journal.search(
                    [('type', 'in', ('bank', 'cash')), ('company_id', '=', company.id)],
                    limit=1)
                vals = {'name': name, 'company_id': company.id}
                if journal:
                    vals['journal_id'] = journal.id
                pm = PM.create(vals)
            if pm.id in config.payment_method_ids.ids or has_open:
                continue
            config.sudo().write({'payment_method_ids': [(4, pm.id)]})
            linked.append((config.id, name))
    return linked
