# Part of the Mezze POS platform. See LICENSE (LGPL-3).
from odoo import fields, models


class MezzePaymentProvider(models.Model):
    """A configured card/wallet acquirer (Paymob, Fawry, HyperPay, mada, Geidea).

    The presence of an active provider for a tender is what makes that non-cash
    button 'live' in the POS. Credentials live in ``ir.config_parameter`` / a
    secrets store (pointed to by ``credential_param``), never in plaintext here.
    See ``docs/W1.md``.
    """
    _name = 'mezze.payment.provider'
    _description = "Mezze Payment Provider"
    _order = 'sequence, id'

    name = fields.Char(required=True)
    code = fields.Selection(
        selection=[('paymob', "Paymob"), ('fawry', "Fawry"), ('hyperpay', "HyperPay"),
                   ('mada', "mada"), ('geidea', "Geidea")],
        required=True, index=True)
    config_id = fields.Many2one('pos.config', string="Branch", ondelete='set null',
                                help="Leave empty to apply to all branches.")
    tender = fields.Selection(
        selection=[('card', "Card"), ('wallet', "Wallet"), ('gift', "Gift card")],
        default='card', required=True,
        help="Which POS tender button this provider powers.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    credential_param = fields.Char(
        string="Credential Param Key",
        help="ir.config_parameter key holding this provider's secrets.")


class MezzePaymentTransaction(models.Model):
    """A single acquirer charge/refund attempt tied to a POS order.

    Created when the cashier picks a live card/wallet tender; the provider
    integration (TODO) drives it to authorized/captured/failed and stores the
    reference for reconciliation + refunds. See ``docs/W1.md``.
    """
    _name = 'mezze.payment.transaction'
    _description = "Mezze Payment Transaction"
    _order = 'id desc'

    provider_id = fields.Many2one('mezze.payment.provider', ondelete='set null', index=True)
    payment_transaction_id = fields.Many2one(
        'payment.transaction', string="Odoo Payment Transaction", ondelete='set null', index=True,
        help="The native payment.transaction (e.g. Paymob) this POS charge delegates to.")
    order_id = fields.Many2one('pos.order', string="POS Order", ondelete='set null', index=True)
    order_uuid = fields.Char(index=True)
    amount = fields.Float(required=True)
    currency = fields.Char(default='EGP')
    kind = fields.Selection(
        selection=[('charge', "Charge"), ('refund', "Refund")],
        default='charge', required=True)
    state = fields.Selection(
        selection=[('pending', "Pending"), ('authorized', "Authorized"),
                   ('captured', "Captured"), ('failed', "Failed"), ('refunded', "Refunded")],
        default='pending', required=True, index=True)
    provider_reference = fields.Char(string="Provider Ref", index=True, copy=False)
    error_message = fields.Text()
