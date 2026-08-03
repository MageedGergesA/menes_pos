"""S2C-6 — Customer Account / Credit.

The receivable/credit ACCOUNTING is Odoo's and stays authoritative (see
docs/…/customer-credit-audit.md): exposure = the commercial partner's native
``credit`` (unreconciled posted receivables) + open-session pay_later; the limit is
the native, company-dependent ``credit_limit``. Mezze adds NO second balance/ledger.

Mezze adds only policy + UX primitives:
  * ``pos.payment.method.mezze_credit_policy`` — odoo_warning | manager_approval |
    hard_block (default odoo_warning: preserve the documented soft-warning behavior);
  * ``res.partner._mezze_credit_position`` — a safe, server-computed account summary;
  * deposit / settlement recorded as NATIVE inbound customer ``account.payment`` (a
    real cash/bank journal) which reduces ``partner.credit`` through Odoo's own
    posting — never a Mezze balance, never fake sales revenue.
"""
import json
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_CREDIT_POLICY = [
    ('odoo_warning', 'Warn (allow)'),
    ('manager_approval', 'Manager approval'),
    ('hard_block', 'Hard block'),
]


class PosPaymentMethodCredit(models.Model):
    _inherit = 'pos.payment.method'

    # Only meaningful for a Customer Account (pay_later) method. Default preserves the
    # documented soft-warning behavior so an upgrade never turns an existing install
    # into a hard-blocking credit system.
    mezze_credit_policy = fields.Selection(_CREDIT_POLICY, default='odoo_warning', required=True,
                                           help='Behaviour when a Customer Account sale would exceed the credit limit.')


class ResPartnerCredit(models.Model):
    _inherit = 'res.partner'

    def _mezze_credit_position(self, company, config=None, extra=0.0):
        """Authoritative account summary for the CUSTOMER (its commercial partner).
        Exposure = native ``credit`` (posted receivables) + open-session unsettled
        pay_later (which only posts at session close). Limit = native, company-
        dependent ``credit_limit`` (active only when the company + partner enable it).
        Everything derives from Odoo — no second balance is computed here."""
        self.ensure_one()
        commercial = self.commercial_partner_id
        cur = (config.currency_id if config else company.currency_id)
        prec = cur.decimal_places or 2
        comp = commercial.with_company(company).sudo()
        exposure_posted = comp.credit or 0.0
        # open-session pay_later charged to this commercial partner but not yet posted.
        # ``type`` is a non-stored compute → filter on the equivalent stored field:
        # a Customer Account method has a BLANK journal (see pos_payment_method
        # ._compute_type: pay_later ⇔ journal not cash/bank).
        Payment = self.env['pos.payment'].sudo()
        dom = [('payment_method_id.journal_id', '=', False),
               ('session_id.state', '!=', 'closed'),
               ('pos_order_id.partner_id.commercial_partner_id', '=', commercial.id),
               ('session_id.config_id.company_id', '=', company.id)]
        session_pl = sum(Payment.search(dom).mapped('amount'))
        exposure = round(exposure_posted + session_pl, prec)
        limit = comp.credit_limit or 0.0
        limit_active = bool(company.account_use_credit_limit and comp.use_partner_credit_limit and limit > 0)
        projected = round(exposure + (extra or 0.0), prec)
        over = round(projected - limit, prec)
        return {
            'partner_id': commercial.id,
            'name': commercial.name,
            'exposure': exposure,                 # what they currently owe (posted + in-session)
            'limit': round(limit, prec),
            'limit_active': limit_active,
            'available': round(limit - exposure, prec) if limit_active else None,
            'projected': projected,               # after this sale
            'over': over if (limit_active and over > 0) else 0.0,
            'currency': cur.name,
            'decimals': prec,
        }

    def _mezze_customer_payment(self, company, amount, journal, memo, settle=False):
        """Record a NATIVE inbound customer payment (deposit or settlement) via a real
        cash/bank journal. Reduces ``partner.credit`` through Odoo's own posting (an
        inbound payment posts a negative receivable residual). For a settlement, also
        reconcile against the outstanding receivable so the ledger nets cleanly. No
        sales revenue, no Mezze balance."""
        self.ensure_one()
        commercial = self.commercial_partner_id
        if journal.type not in ('cash', 'bank'):
            raise UserError("A deposit/settlement must be received via a cash or bank journal.")
        line = journal.inbound_payment_method_line_ids[:1]
        pay = self.env['account.payment'].sudo().create({
            'partner_id': commercial.id, 'partner_type': 'customer',
            'payment_type': 'inbound', 'amount': round(float(amount), 2),
            'journal_id': journal.id, 'company_id': company.id, 'memo': memo or '',
            'payment_method_line_id': line.id if line else False,
        })
        pay.action_post()
        if settle:
            self._mezze_reconcile_receivable(commercial, company)
        return pay

    @api.model
    def _mezze_reconcile_receivable(self, commercial, company):
        """Reconcile a customer's open receivable lines (FIFO) so a settlement nets
        the outstanding debt against the just-posted inbound payment."""
        lines = self.env['account.move.line'].sudo().search([
            ('partner_id', '=', commercial.id),
            ('company_id', '=', company.id),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
            ('amount_residual', '!=', 0.0),
        ])
        if len(lines) > 1:
            try:
                lines.reconcile()
            except Exception:  # noqa: BLE001 — partial/over states are still valid, credit already reflects it
                _logger.info("Mezze customer reconcile skipped (partner=%s)", commercial.id)
