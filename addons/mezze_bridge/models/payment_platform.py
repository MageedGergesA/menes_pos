"""S2 — Universal Payments Platform (Slice 1: modes, policy, device registry).

Does NOT create a new payment engine — it adds Mezze-facing classification + policy
metadata on top of Odoo's native pos.payment.method / pos.payment, so every tender
still converges on pos.payment / pos.order and the existing money/refund invariants.
External-terminal metadata REUSES native pos.payment fields (payment_ref_no,
payment_method_authcode, card_no last-4) — no PAN/CVV/PIN/track ever stored.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Mezze-facing payment modes (classification only; native Odoo config is authoritative).
MEZZE_MODES = [
    ('cash', 'Cash'),
    ('manual', 'Manual tender'),
    ('external_terminal', 'External terminal (manual confirm)'),
    ('odoo_terminal', 'Odoo integrated terminal'),
    ('bank_qr', 'Bank / payment QR'),
    ('online_provider', 'Online provider'),
    ('customer_account', 'Customer account'),
    ('cash_machine', 'Cash machine'),
]
_REF_POLICY = [('disabled', 'Disabled'), ('optional', 'Optional'), ('required', 'Required')]
_REF_SCOPE = [('device_ref', 'Device + reference'), ('method_ref', 'Method + reference'),
              ('branch_ref', 'Branch + reference')]


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    # auto-classified from native fields, but admin-overridable (editable stored compute).
    mezze_mode = fields.Selection(MEZZE_MODES, string='Mezze Mode',
                                  compute='_compute_mezze_mode', store=True, readonly=False)
    reference_policy = fields.Selection(_REF_POLICY, default='disabled', required=True,
                                        help='Whether a cashier must supply an external reference/approval id.')
    reference_scope = fields.Selection(_REF_SCOPE, default='method_ref', required=True,
                                       help='Scope for duplicate-reference detection.')
    mezze_require_customer = fields.Boolean(string='Require customer')
    mezze_allow_partial = fields.Boolean(string='Allow partial', default=True)
    mezze_allow_mixed = fields.Boolean(string='Allow mixed tender', default=True)
    mezze_allow_refund = fields.Boolean(string='Allow refund', default=True)
    mezze_manager_approval = fields.Boolean(string='Manager approval required')
    mezze_reconciliation_required = fields.Boolean(string='Reconciliation required')
    mezze_device_ids = fields.Many2many('mezze.payment.device', string='Payment devices')

    @api.depends('is_cash_count', 'type', 'use_payment_terminal', 'qr_code_method', 'payment_method_type')
    def _compute_mezze_mode(self):
        for m in self:
            if m.is_cash_count:
                mode = 'cash'
            elif m.type == 'pay_later':
                mode = 'customer_account'
            elif m.use_payment_terminal:
                mode = 'odoo_terminal'
            elif m.qr_code_method:
                mode = 'bank_qr'
            elif m.payment_method_type == 'online':
                mode = 'online_provider'
            else:
                mode = 'manual'
            # never downgrade an explicit external_terminal/cash_machine override on recompute
            if m.mezze_mode in ('external_terminal', 'cash_machine'):
                continue
            m.mezze_mode = mode


class MezzePaymentDevice(models.Model):
    _name = 'mezze.payment.device'
    _description = 'Mezze payment device (terminal / register / cash machine)'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    config_id = fields.Many2one('pos.config', string='Branch', index=True, ondelete='cascade')
    register = fields.Char(string='Register / POS')
    mode = fields.Selection(MEZZE_MODES, required=True, default='external_terminal')
    acquirer_label = fields.Char(string='Provider / acquirer')
    integration_type = fields.Selection(
        [('manual', 'Manual'), ('odoo_terminal', 'Odoo terminal'), ('online', 'Online'),
         ('cash_machine', 'Cash machine')], default='manual', required=True)
    active = fields.Boolean(default=True)
    payment_method_ids = fields.Many2many('pos.payment.method', string='Payment methods')
    reconciliation_required = fields.Boolean(default=False)
    # certification status is descriptive only — never implies hardware certification here
    certification_status = fields.Selection(
        [('manual', 'Manual'), ('supported_via_odoo', 'Supported via Odoo'),
         ('not_tested', 'Not tested'), ('certified', 'Certified'), ('unsupported', 'Unsupported')],
        default='not_tested', required=True)

    _code_uniq = models.Constraint('unique(code)', 'Payment device code must be unique.')


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    mezze_device_id = fields.Many2one('mezze.payment.device', string='Payment device', ondelete='set null')

    @api.constrains('payment_ref_no', 'payment_method_id')
    def _mezze_check_reference_policy(self):
        """Enforce reference_policy=required using the NATIVE payment_ref_no field."""
        for p in self:
            pm = p.payment_method_id
            if pm and pm.reference_policy == 'required' and not (p.payment_ref_no or '').strip():
                raise ValidationError(
                    "Payment method %r requires an external reference / approval id." % pm.name)

    def mezze_duplicate_references(self):
        """Return other pos.payment rows reusing this payment's reference within the
        method's configured scope — for a warn + manager-override flow (wired in a later
        slice). Empty recordset when no reference or policy=disabled."""
        self.ensure_one()
        ref = (self.payment_ref_no or '').strip()
        pm = self.payment_method_id
        if not ref or not pm or pm.reference_policy == 'disabled':
            return self.browse()
        dom = [('id', '!=', self.id), ('payment_ref_no', '=', ref)]
        scope = pm.reference_scope
        if scope == 'method_ref':
            dom.append(('payment_method_id', '=', pm.id))
        elif scope == 'device_ref':
            dom.append(('mezze_device_id', '=', self.mezze_device_id.id or False))
        elif scope == 'branch_ref':
            dom.append(('session_id.config_id', '=', self.session_id.config_id.id if self.session_id else False))
        return self.sudo().search(dom)
