# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Tip pooling — the ledger and the pool run (design BE-008).

A tip is money owed to staff: a liability from the moment it is captured, never
the branch's to keep, spend or round. ``docs/TIP_POOLING.md`` sets the contract;
``domain/tip_pool.py`` holds the ONE distribution resolver. This module is the
persistence and the workflow around it, and deliberately owns no arithmetic of
its own -- four numbers for one liability is the defect the design set out to
remove.

Money is stored in the branch currency but distributed in PIASTRES (minor units)
so shares are integers and the remainder is allocated, never rounded away.

Staff here are ``mezze.cashier``, not ``hr.employee``: this platform keeps
front-of-house staff off Odoo user/employee records by design (see
``models/attendance.py``), and hours come from ``mezze.attendance`` -- the same
clock the rota reads, as the contract requires.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..domain import tip_pool as tp

# Roles that never share in a pool. The contract puts managers out; admin and
# auditor are administrative identities that are never on a tipped shift.
UNTIPPED_ROLES = ('manager', 'admin', 'auditor')


def _to_minor(amount, currency):
    """Currency amount -> integer minor units, via the currency's own rounding."""
    places = currency.decimal_places if currency else 2
    return int(round((amount or 0.0) * (10 ** places)))


def _from_minor(minor, currency):
    places = currency.decimal_places if currency else 2
    return (minor or 0) / float(10 ** places)


class MezzeTipEntry(models.Model):
    """Append-only tip ledger. Every figure any screen shows derives from here."""
    _name = 'mezze.tip.entry'
    _description = 'Mezze Tip Ledger Entry'
    _order = 'id desc'

    kind = fields.Selection(
        [('capture', "Captured with a tender"), ('declare', "Declared cash"),
         ('distribute', "Distributed"), ('payout', "Paid out"),
         ('adjust', "Manager adjustment"), ('reverse', "Reversed")],
        required=True, index=True)
    amount = fields.Monetary(required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', required=True)
    # WHO SERVED IT. A capture without a server makes the direct and hybrid
    # rules meaningless, so the contract requires it on every capture.
    cashier_id = fields.Many2one('mezze.cashier', ondelete='restrict', index=True)
    config_id = fields.Many2one('pos.config', required=True, ondelete='cascade', index=True)
    session_id = fields.Many2one('pos.session', ondelete='set null', index=True)
    order_id = fields.Many2one('pos.order', ondelete='set null', index=True)
    run_id = fields.Many2one('mezze.tip.run', ondelete='cascade', index=True)
    method = fields.Char(help="Tender method for a capture (cash/card/…).")
    route = fields.Selection([('cash', "Cash from the drawer"), ('payroll', "To payroll")],
                             help="Payout route, on payout rows only.")
    reason = fields.Char(help="Required on a manager adjustment.")
    # Idempotency: 'run|cashier|route' on payouts, 'order|kind' on captures.
    dedup_key = fields.Char(index=True, copy=False)

    # v19: `_sql_constraints` is no longer supported (models.py warns and drops
    # it) -- a constraint is a models.Constraint attribute now.
    _dedup_key_uniq = models.Constraint(
        'unique(dedup_key)',
        "That tip entry was already recorded — a second tap pays nobody twice.")

    @api.constrains('kind', 'cashier_id', 'reason')
    def _check_shape(self):
        for e in self:
            if e.kind in ('capture', 'declare') and not e.cashier_id:
                raise ValidationError(_(
                    "A %s names the person it belongs to.") % e.kind)
            if e.kind == 'adjust' and not (e.reason or '').strip():
                raise ValidationError(_("A manager adjustment carries a reason."))

    def write(self, vals):
        # Append-only: the trail cannot be altered after the fact. Linking a row
        # to the run that distributed it is the one permitted mutation.
        if set(vals) - {'run_id'}:
            raise UserError(_("The tip ledger is append-only."))
        return super().write(vals)


class MezzeTipRunLine(models.Model):
    """One person's SNAPSHOT share. Written by the run, never recomputed."""
    _name = 'mezze.tip.run.line'
    _description = 'Mezze Tip Run Line'
    _order = 'id'

    run_id = fields.Many2one('mezze.tip.run', required=True, ondelete='cascade', index=True)
    cashier_id = fields.Many2one('mezze.cashier', required=True, ondelete='restrict')
    currency_id = fields.Many2one(related='run_id.currency_id')
    minutes = fields.Integer(help="Minutes actually worked in the period.")
    weight = fields.Float(digits=(16, 4), help="The rule's weight for this person.")
    custom_pct = fields.Float(help="Manager-set percentage, under the Custom rule.")
    share = fields.Monetary(currency_field='currency_id')
    paid_cash = fields.Monetary(currency_field='currency_id')
    paid_payroll = fields.Monetary(currency_field='currency_id')
    outstanding = fields.Monetary(compute='_compute_outstanding', currency_field='currency_id',
                                  help="Derived, never stored — see the contract §4.")

    @api.depends('share', 'paid_cash', 'paid_payroll')
    def _compute_outstanding(self):
        for l in self:
            l.outstanding = l.share - l.paid_cash - l.paid_payroll


class MezzeTipRun(models.Model):
    """A distribution: rule, period, snapshot, approval, payout."""
    _name = 'mezze.tip.run'
    _description = 'Mezze Tip Pool Run'
    _order = 'id desc'

    name = fields.Char(compute='_compute_name', store=True)
    config_id = fields.Many2one('pos.config', required=True, ondelete='cascade', index=True)
    session_id = fields.Many2one('pos.session', ondelete='set null', index=True)
    currency_id = fields.Many2one('res.currency', required=True)
    rule = fields.Selection([(r, r.replace('_', ' ').title()) for r in tp.RULES],
                            required=True, default=tp.HOURS)
    date_from = fields.Datetime(required=True)
    date_to = fields.Datetime(required=True)
    state = fields.Selection(
        [('draft', "Draft"), ('approved', "Approved"), ('paid', "Paid"), ('void', "Void")],
        default='draft', required=True, index=True)
    # NOT `pool`: Odoo's registry uses ``cls.pool`` as its own handle, and
    # ``is_model_definition()`` tests ``getattr(cls, 'pool', None) is None`` --
    # a field of that name stops the class being recognised as a model at all.
    pool_amount = fields.Monetary(currency_field='currency_id',
                                  help="The liability distributed.")
    line_ids = fields.One2many('mezze.tip.run.line', 'run_id')
    approved_by = fields.Many2one('mezze.cashier', ondelete='restrict', copy=False)
    approved_at = fields.Datetime(copy=False)
    void_reason = fields.Char(copy=False)

    @api.depends('config_id', 'date_to', 'rule')
    def _compute_name(self):
        for r in self:
            r.name = "%s — %s" % (r.config_id.name or '?', r.date_to or '')

    # ---------------------------------------------------------------- compute
    def _eligible(self):
        """Who shares: clocked in during the period, with a tipped role.

        A person on a break still accrues the hours they worked, which falls out
        of reading attendance rather than the rota.
        """
        self.ensure_one()
        att = self.env['mezze.attendance'].sudo().search([
            ('config_id', '=', self.config_id.id),
            ('check_in', '<', self.date_to),
            '|', ('check_out', '=', False), ('check_out', '>', self.date_from),
        ])
        minutes = {}
        for a in att:
            if a.cashier_id.role in UNTIPPED_ROLES:
                continue
            start = max(a.check_in, self.date_from)
            end = min(a.check_out or self.date_to, self.date_to)
            if end > start:
                minutes[a.cashier_id] = minutes.get(a.cashier_id, 0) + \
                    int((end - start).total_seconds() // 60)
        return minutes

    def _ledger_by_cashier(self, kind):
        self.ensure_one()
        # _read_group, not read_group: the latter carries @api.deprecated in
        # v19 (odoo/orm/models.py:2748). Groups come back as recordsets here.
        rows = self.env['mezze.tip.entry'].sudo()._read_group(
            [('config_id', '=', self.config_id.id), ('kind', '=', kind),
             ('create_date', '>=', self.date_from), ('create_date', '<', self.date_to)],
            groupby=['cashier_id'], aggregates=['amount:sum'])
        return {cashier.id: total for cashier, total in rows if cashier}

    def action_compute(self, custom_pct=None):
        """Rebuild the snapshot from the clock and the ledger. Draft only."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("A %s run cannot be recomputed — void it and re-sign.")
                            % self.state)
        cur = self.currency_id
        minutes = self._eligible()
        captured = self._ledger_by_cashier('capture')
        declared = self._ledger_by_cashier('declare')
        people = [tp.Person(key=c.id, role=c.role, minutes=m,
                            captured=_to_minor(captured.get(c.id, 0.0), cur),
                            declared=_to_minor(declared.get(c.id, 0.0), cur))
                  for c, m in minutes.items()]
        pct = {int(k): v for k, v in (custom_pct or {}).items()}
        res = tp.distribute(people, self.rule, custom_pct=pct)
        self.line_ids.unlink()
        if res.err:
            self.pool_amount = _from_minor(res.pool, cur)
            return res.err
        self.pool_amount = _from_minor(res.pool, cur)
        self.env['mezze.tip.run.line'].create([{
            'run_id': self.id, 'cashier_id': row.key,
            'minutes': dict((p.key, p.minutes) for p in people)[row.key],
            'weight': row.weight, 'custom_pct': pct.get(row.key, 0.0),
            'share': _from_minor(row.share, cur),
        } for row in res.rows])
        return None

    # --------------------------------------------------------------- approval
    def action_approve(self, cashier, pin):
        """Sign the run. The signed figures are the paid figures."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only a draft run can be approved."))
        if not cashier or cashier.role not in ('manager', 'supervisor', 'admin'):
            raise UserError(_("A manager PIN signs a tip distribution."))
        if not cashier.check_pin(pin):
            raise UserError(_("That PIN was not accepted."))
        if not self.line_ids:
            raise UserError(_("There is nothing to approve — recompute the run first."))
        self.write({'state': 'approved', 'approved_by': cashier.id,
                    'approved_at': fields.Datetime.now()})
        self.env['mezze.audit.log'].sudo().log(
            'tip.run_approved', severity='info', cashier_id=cashier.id,
            config_id=self.config_id.id, res_model=self._name, res_id=self.id,
            amount=self.pool_amount)
        return True

    def action_void(self, cashier, pin, reason):
        """Unwind a signed run. Both events stay on the ledger."""
        self.ensure_one()
        if self.state == 'void':
            return True
        if not cashier or not cashier.check_pin(pin):
            raise UserError(_("That PIN was not accepted."))
        if not (reason or '').strip():
            raise UserError(_("Voiding a signed distribution carries a reason."))
        self.write({'state': 'void', 'void_reason': reason})
        self.env['mezze.audit.log'].sudo().log(
            'tip.run_voided', severity='warning', cashier_id=cashier.id,
            config_id=self.config_id.id, res_model=self._name, res_id=self.id,
            detail=reason)
        return True

    def write(self, vals):
        # Changing the rule or a share after signing is refused: a later
        # clock-out must not silently re-cut a distribution already agreed.
        locked = {'rule', 'pool_amount', 'date_from', 'date_to'}
        for r in self:
            if r.state in ('approved', 'paid') and (set(vals) & locked):
                raise UserError(_(
                    "This run is signed. Void it and re-sign to change the rule."))
        return super().write(vals)

    # ----------------------------------------------------------------- payout
    def action_payout(self, route):
        """Pay the run out. One row per person per run, keyed so a second tap
        pays once; a partial payout is two rows and the balance is derived.

        ``cash``    — a drawer movement, so the till reconciles, discharging the
                      Tips payable liability the same night.
        ``payroll`` — a STATE, not an export: the money stays in Tips payable and
                      rides the next payslip. This platform's staff are
                      ``mezze.cashier`` (never ``hr.employee``), so there is no
                      payslip input line to write here; producing one is the
                      payroll export's job (design BE-020) and is deliberately
                      not faked with a drawer movement, which would discharge a
                      liability nobody has actually paid.
        """
        self.ensure_one()
        if route not in ('cash', 'payroll'):
            raise UserError(_("Unknown payout route %r.") % route)
        if self.state not in ('approved', 'paid'):
            raise UserError(_("Only an approved run pays out."))
        Entry = self.env['mezze.tip.entry'].sudo()
        paid = 0.0
        for line in self.line_ids:
            outstanding = line.outstanding
            if outstanding <= 0:
                continue
            key = 'tiprun:%s|%s|%s' % (self.id, line.cashier_id.id, route)
            if Entry.search_count([('dedup_key', '=', key)]):
                continue
            Entry.create({
                'kind': 'payout', 'amount': -outstanding,
                'currency_id': self.currency_id.id, 'cashier_id': line.cashier_id.id,
                'config_id': self.config_id.id, 'session_id': self.session_id.id or False,
                'run_id': self.id, 'route': route, 'dedup_key': key,
            })
            if route == 'cash':
                line.paid_cash += outstanding
            else:
                line.paid_payroll += outstanding
            paid += outstanding
        if route == 'cash' and paid:
            self._post_drawer_movement(paid)
        if not any(l.outstanding > 0 for l in self.line_ids):
            self.state = 'paid'
        self.env['mezze.audit.log'].sudo().log(
            'tip.run_paid', severity='info', config_id=self.config_id.id,
            res_model=self._name, res_id=self.id, amount=paid, detail=route)
        return paid

    def _post_drawer_movement(self, amount):
        """Take the cash out of the till, so the drawer count still reconciles.

        Delegates to Odoo's own ``pos.session.try_cash_in_out`` -- the same call
        the cash-management endpoint uses -- rather than writing a statement line
        by hand. Without an open session there is no drawer to take it from, and
        the payout is refused rather than silently leaving the till over.
        """
        self.ensure_one()
        session = self.session_id or self.config_id.current_session_id
        if not session or session.state != 'opened':
            raise UserError(_(
                "Paying tips in cash needs an open session — the drawer it comes "
                "out of is what makes the payout visible in the count."))
        # ``extras['translatedType']`` is not optional: core composes the
        # statement line's payment_ref from it and raises KeyError without it.
        session.sudo().try_cash_in_out(
            'out', amount, _("Tip payout — run %s") % self.id, False,
            {'translatedType': 'Cash Out', 'formattedAmount': ''})
