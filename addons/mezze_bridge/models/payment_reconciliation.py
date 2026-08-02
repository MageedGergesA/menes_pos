"""S2 Slice 2 — cashier payment runtime policy + operational POS settlement reconciliation.

- Runtime enforcement (device / reference / duplicate) BEFORE any financial effect.
- External-refund provenance (Mezze recorded ≠ bank confirmed).
- mezze.payment.reconciliation(.line): operational settlement reconciliation (NOT accounting
  journal reconciliation). Expected amounts come from finalized payments, never hand-edited.

All tenders still converge on pos.payment / pos.order + the existing money/refund invariants.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_DEVICE_POLICY = [('disabled', 'Disabled'), ('optional', 'Optional'), ('required', 'Required')]
_DUP_POLICY = [('allow', 'Allow'), ('warn', 'Warn'),
               ('manager_approval', 'Manager approval'), ('block', 'Block')]
_CONF_SRC = [('manual', 'Manual'), ('integrated', 'Integrated terminal'), ('provider', 'Provider')]
_EXT_REFUND = [('not_required', 'Not required'), ('pending_external', 'Pending external'),
               ('confirmed_external', 'Confirmed external'), ('failed_external', 'Failed external')]
_RECON_STATUS = [('matched', 'Matched'), ('over', 'Over'), ('short', 'Short'),
                 ('missing_settlement', 'Missing settlement'), ('unreconciled', 'Unreconciled')]
_SETTLE_SOURCE = [('cash_count', 'Cash count'), ('manual_terminal_settlement', 'Terminal settlement'),
                  ('bank_transfer_confirmation', 'Bank transfer confirmation'),
                  ('provider_import', 'Provider import'), ('automated_provider', 'Automated provider')]


class PosPaymentMethodS2(models.Model):
    _inherit = 'pos.payment.method'

    device_policy = fields.Selection(_DEVICE_POLICY, default='disabled', required=True,
                                     help='Whether a payment device must be selected for this method.')
    duplicate_policy = fields.Selection(_DUP_POLICY, default='warn', required=True,
                                        help='Behaviour when a duplicate external reference is detected.')
    settlement_basis = fields.Selection([('gross', 'Gross'), ('net', 'Net (minus refunds)')],
                                        default='gross', required=True)
    reconciliation_tolerance = fields.Float(default=0.0,
                                            help='Absolute difference tolerated before manager approval is required.')

    def mezze_validate_payment(self, device=None, reference=None, allow_duplicate=False):
        """Enforce device/reference/duplicate policy BEFORE any pos.payment is created.
        Raises UserError with an actionable message; never a silent pass. Returns a
        dict {'duplicates': recordset, 'needs_manager': bool} for the warn/approval flow."""
        self.ensure_one()
        ref = (reference or '').strip()
        # device policy
        if self.device_policy == 'required' and not device:
            raise UserError("Payment method %r requires a payment device to be selected." % self.name)
        if device:
            if not device.active:
                raise UserError("Payment device %r is inactive." % device.name)
            if device.config_id and self.env.context.get('mezze_branch_id') \
                    and device.config_id.id != self.env.context['mezze_branch_id']:
                raise UserError("Payment device %r belongs to another branch." % device.name)
            if device.payment_method_ids and self not in device.payment_method_ids:
                raise UserError("Payment device %r is not compatible with method %r." % (device.name, self.name))
        # reference policy
        if self.reference_policy == 'required' and not ref:
            raise UserError("Payment method %r requires an external reference / approval id." % self.name)
        # duplicate policy
        result = {'duplicates': self.env['pos.payment'], 'needs_manager': False}
        if ref and self.duplicate_policy != 'allow':
            dups = self._mezze_find_reference_dups(ref, device)
            if dups:
                result['duplicates'] = dups
                if self.duplicate_policy == 'block' and not allow_duplicate:
                    raise UserError("Reference %r was already used (duplicate blocked by policy)." % ref)
                if self.duplicate_policy == 'manager_approval' and not allow_duplicate:
                    result['needs_manager'] = True
        return result

    def _mezze_find_reference_dups(self, ref, device=None):
        self.ensure_one()
        dom = [('payment_ref_no', '=', ref)]
        scope = self.reference_scope
        if scope == 'method_ref':
            dom.append(('payment_method_id', '=', self.id))
        elif scope == 'device_ref':
            dom.append(('mezze_device_id', '=', device.id if device else False))
        elif scope == 'branch_ref' and self.env.context.get('mezze_branch_id'):
            dom.append(('session_id.config_id', '=', self.env.context['mezze_branch_id']))
        return self.env['pos.payment'].sudo().search(dom)


class PosPaymentS2(models.Model):
    _inherit = 'pos.payment'

    mezze_confirmation_source = fields.Selection(_CONF_SRC, default='manual',
                                                 help='Provenance — manual confirmation is NOT provider-verified.')
    mezze_external_refund_status = fields.Selection(_EXT_REFUND, default='not_required')
    mezze_external_refund_ref = fields.Char(string='External refund reference')
    # S2C-2 — per-tender idempotency key (client-minted, one per Confirm). Lets a
    # partial/mixed tender be safely retried (double-click / network retry) without
    # creating a second pos.payment. NULLs are allowed and non-conflicting.
    mezze_tender_key = fields.Char(string='Tender idempotency key', index=True, copy=False)

    _mezze_tender_key_uniq = models.Constraint(
        'unique(pos_order_id, mezze_tender_key)',
        'A tender with this idempotency key already exists on this order.')

    def mezze_confirm_external_refund(self, reference=None, note=None, actor=None):
        """Mark a manual/external refund as confirmed at the bank/terminal. Manager action;
        never edits the original payment amount. Idempotent (re-confirm = same state)."""
        for p in self:
            if p.mezze_external_refund_status == 'confirmed_external':
                continue
            p.write({'mezze_external_refund_status': 'confirmed_external',
                     'mezze_external_refund_ref': reference or p.mezze_external_refund_ref})
            try:
                p.env['mezze.audit.log'].sudo().log(
                    'payment.external_refund_confirmed', severity='info',
                    detail='{"payment":%d,"ref":%r,"actor":%r}' % (p.id, reference or '', actor or ''))
            except Exception:  # noqa: BLE001
                pass
        return True


class MezzePaymentReconciliation(models.Model):
    _name = 'mezze.payment.reconciliation'
    _description = 'Mezze operational POS payment settlement reconciliation'
    _order = 'create_date desc'

    name = fields.Char(compute='_compute_name', store=True)
    config_id = fields.Many2one('pos.config', string='Branch', index=True, ondelete='cascade')
    session_id = fields.Many2one('pos.session', index=True, ondelete='cascade')
    state = fields.Selection([('draft', 'Draft'), ('finalized', 'Finalized')], default='draft', required=True)
    reconciled_by = fields.Many2one('res.users')
    approved_by = fields.Many2one('res.users')
    note = fields.Char()
    opened_at = fields.Datetime(default=fields.Datetime.now)
    closed_at = fields.Datetime()
    line_ids = fields.One2many('mezze.payment.reconciliation.line', 'reconciliation_id')
    overall_status = fields.Selection(_RECON_STATUS, compute='_compute_overall', store=True)
    total_difference = fields.Float(compute='_compute_overall', store=True)

    _session_uniq = models.Constraint('unique(session_id)',
                                      'A reconciliation already exists for this session.')

    @api.depends('config_id', 'session_id')
    def _compute_name(self):
        for r in self:
            r.name = 'RECON/%s/%s' % (r.config_id.name or '?', r.session_id.id or r.id or '?')

    @api.depends('line_ids.status', 'line_ids.difference')
    def _compute_overall(self):
        for r in self:
            r.total_difference = sum(r.line_ids.mapped('difference'))
            statuses = set(r.line_ids.mapped('status'))
            if not statuses or statuses == {'matched'}:
                r.overall_status = 'matched'
            elif 'missing_settlement' in statuses:
                r.overall_status = 'missing_settlement'
            elif 'short' in statuses:
                r.overall_status = 'short'
            elif 'over' in statuses:
                r.overall_status = 'over'
            else:
                r.overall_status = 'unreconciled'

    @api.model
    def build_for_session(self, session):
        """Get-or-create the reconciliation for a session and (re)build expected lines from
        FINALIZED payments. Never edits payments; expected is derived, not entered."""
        recon = self.search([('session_id', '=', session.id)], limit=1)
        if not recon:
            recon = self.create({'session_id': session.id, 'config_id': session.config_id.id})
        if recon.state == 'finalized':
            return recon
        # aggregate finalized payments by (method, device)
        Payment = self.env['pos.payment'].sudo()
        payments = Payment.search([('session_id', '=', session.id),
                                   ('pos_order_id.state', 'in', ('paid', 'done', 'invoiced'))])
        agg = {}
        for p in payments:
            key = (p.payment_method_id.id, p.mezze_device_id.id or False)
            basis = p.payment_method_id.settlement_basis
            amt = p.amount
            # gross = all positives; net = positives minus refund negatives (amount<0)
            if basis == 'gross' and amt < 0:
                continue
            agg.setdefault(key, 0.0)
            agg[key] += amt
        LineModel = self.env['mezze.payment.reconciliation.line'].sudo()
        recon.line_ids.filtered(lambda l: not l.settlement_amount).unlink()  # refresh un-settled only
        existing = {(l.payment_method_id.id, l.device_id.id or False): l for l in recon.line_ids}
        for (pm_id, dev_id), expected in agg.items():
            pm = self.env['pos.payment.method'].browse(pm_id)
            if (pm_id, dev_id) in existing:
                existing[(pm_id, dev_id)].expected_amount = expected
            else:
                LineModel.create({
                    'reconciliation_id': recon.id, 'payment_method_id': pm_id,
                    'mezze_mode': pm.mezze_mode, 'device_id': dev_id or False,
                    'expected_amount': expected})
        return recon

    def record_settlement(self, line, amount, reference=None, source='manual_terminal_settlement',
                          operator=None, note=None):
        """Record actual settlement/count against a line. Does NOT touch payments."""
        self.ensure_one()
        line.write({'settlement_amount': amount, 'settlement_reference': reference or line.settlement_reference,
                    'source': source, 'settlement_operator': operator or self.env.user.id, 'note': note or line.note})
        return line

    def finalize(self, approved_by=None):
        """Idempotent, concurrency-safe finalize. A second worker either sees the lock and
        then the finalized state (idempotent same result), or is rejected. Manager approval
        required when any line exceeds its method tolerance."""
        self.ensure_one()
        # row lock to serialize concurrent finalizes
        self.env.cr.execute("SELECT state FROM mezze_payment_reconciliation WHERE id=%s FOR UPDATE", (self.id,))
        self.invalidate_recordset(['state'])
        if self.state == 'finalized':
            return True   # idempotent
        # tolerance gate
        needs_approval = any(
            abs(l.difference) > (l.payment_method_id.reconciliation_tolerance or 0.0)
            for l in self.line_ids)
        if needs_approval and not approved_by:
            raise UserError("Reconciliation difference exceeds tolerance — manager approval required.")
        self.write({'state': 'finalized', 'closed_at': fields.Datetime.now(),
                    'reconciled_by': self.env.user.id, 'approved_by': approved_by or False})
        try:
            self.env['mezze.audit.log'].sudo().log(
                'payment.reconciliation_finalized', severity='info',
                detail='{"recon":%d,"diff":%s,"approved_by":%r}'
                       % (self.id, self.total_difference, approved_by or ''))
        except Exception:  # noqa: BLE001
            pass
        return True


class MezzePaymentReconciliationLine(models.Model):
    _name = 'mezze.payment.reconciliation.line'
    _description = 'Mezze reconciliation line (per method / device)'

    reconciliation_id = fields.Many2one('mezze.payment.reconciliation', required=True, ondelete='cascade', index=True)
    payment_method_id = fields.Many2one('pos.payment.method', required=True)
    mezze_mode = fields.Char()
    device_id = fields.Many2one('mezze.payment.device')
    expected_amount = fields.Float()          # derived from finalized payments — not hand-edited
    settlement_amount = fields.Float()        # actual count / settlement input
    difference = fields.Float(compute='_compute_diff', store=True)
    settlement_reference = fields.Char()
    source = fields.Selection(_SETTLE_SOURCE)
    settlement_operator = fields.Many2one('res.users')
    status = fields.Selection(_RECON_STATUS, compute='_compute_diff', store=True)
    note = fields.Char()

    @api.depends('expected_amount', 'settlement_amount')
    def _compute_diff(self):
        prec = 0.01
        for l in self:
            if not l.settlement_reference and l.settlement_amount == 0.0 and l.source not in ('cash_count',):
                l.difference = 0.0
                l.status = 'missing_settlement'
                continue
            diff = round(l.settlement_amount - l.expected_amount, 2)
            l.difference = diff
            if abs(diff) < prec:
                l.status = 'matched'
            elif diff > 0:
                l.status = 'over'
            else:
                l.status = 'short'
