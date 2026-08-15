# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Drive-thru lane — a car's trip through the lane on top of a real pos.order.

A drive-thru order is a normal ``pos.order`` fired to the kitchen like any other
(no table — it's an off-counter order), plus this record tracking the CAR through
the lane: which lane, a vehicle label, and a stage lifecycle

    preparing -> ready -> at_window -> collected
                                    \\-> cancelled

Kitchen readiness is derived from the order's KDS tickets (same as delivery), so
the lane board reflects real prep state. Payment is taken at the window: the
order is fired as a draft and settled when the car reaches the window, then
handed off (collected). Position-in-lane is derived FIFO from ``placed_at``.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

FLOW = ['preparing', 'ready', 'at_window', 'collected']

# ---------------------------------------------------------------------------
# DT-CORE6 — the VEHICLE journey, which is not the kitchen journey.
#
# `state` above answers two questions with one value: `preparing`/`ready` are
# written back from _kitchen_ready() (see /drivethru/board), while `at_window`/
# `collected` describe where the car physically is. That made a two-window branch
# impossible to express — a car at payment and a car at pickup are both merely
# "at_window" — and left "which car is next" to a timer heuristic.
#
# VEHICLE_STAGES is the authority for physical position. `state` is kept in step
# as a legacy projection so every existing reader (board filters, the HTML board,
# the certified tests) keeps working unchanged.
VEHICLE_STAGES = [
    ('lane', 'In lane'),                  # arrived, not yet called forward
    ('called', 'Called forward'),         # entered the merged path; service order assigned
    ('payment_window', 'At payment window'),
    ('pickup_window', 'At pickup window'),
    ('holding', 'Holding / pulled forward'),   # reserved; see the audit doc
    ('departed', 'Departed'),             # handed off and gone
    ('cancelled', 'Cancelled'),
]
VEHICLE_STAGE_KEYS = [k for k, _label in VEHICLE_STAGES]

#: Stages where a car is still physically in the drive-thru.
ACTIVE_STAGES = ('lane', 'called', 'payment_window', 'pickup_window', 'holding')

#: Stages a car can never leave. A departed car has its food and has driven away; a
#: cancelled visit is void. Both are HISTORY, and nothing an operator does at a lane
#: window may put either back into the queue — the audit found that two authenticated
#: calls (cancel -> window -> collected) could resurrect a cancelled visit and hand
#: food out against it, because the transition layer only checked that the record
#: existed.
TERMINAL_STAGES = ('departed', 'cancelled')

#: The full movement contract for ``vehicle_stage``: stage -> the stages it may move
#: to. Written out rather than implied, so the guard has something to be checked
#: against and so a reader can see what the product actually permits.
#:
#: The ACTIVE region is deliberately open — every active position may reach every
#: other. That is the branch's reality, not laziness: an operator waves a car from
#: the lane straight to pickup when payment is already done, sends it back to pay
#: when a card fails, or parks it. Modelling a corridor here would refuse movements
#: real lanes make daily, and the checks that actually protect the customer are not
#: positional but conditional — handing off requires paid AND kitchen-ready AND the
#: topology's handoff window, and those keep their own gates below.
#:
#: The TERMINAL region is closed. That is the whole of this contract's teeth.
LEGAL_TRANSITIONS = dict(
    {stage: ACTIVE_STAGES + TERMINAL_STAGES for stage in ACTIVE_STAGES},
    **{stage: () for stage in TERMINAL_STAGES},
)

#: A COMBINED-window branch serves payment and pickup at one physical window, so
#: both map onto the same position; a TWO_WINDOW branch keeps them distinct. The
#: model expresses both rather than forcing every restaurant into one topology.
TOPOLOGY_COMBINED = 'combined'
TOPOLOGY_TWO_WINDOW = 'two_window'


class MezzeDrivethru(models.Model):
    _name = 'mezze.drivethru'
    _inherit = ['mezze.kitchen.readiness.mixin']
    _description = 'Mezze Drive-Thru Car'
    _order = 'lane asc, placed_at asc, id asc'

    name = fields.Char(compute='_compute_name', store=True)
    pos_order_id = fields.Many2one('pos.order', required=True, ondelete='cascade', index=True)
    config_id = fields.Many2one('pos.config', related='pos_order_id.config_id', store=True, index=True)
    partner_id = fields.Many2one('res.partner', ondelete='set null')
    customer_name = fields.Char()
    lane = fields.Integer(default=1, index=True, help="Which drive-thru lane the car is in.")
    vehicle = fields.Char(help="Car description or plate, called out at the window.")
    state = fields.Selection(
        [('preparing', 'Preparing'), ('ready', 'Ready'),
         ('at_window', 'At window'), ('collected', 'Collected'),
         ('cancelled', 'Cancelled')],
        default='preparing', required=True, index=True)
    note = fields.Char()

    # ---- DT-CORE6 authoritative physical position ----
    vehicle_stage = fields.Selection(
        VEHICLE_STAGES, default='lane', required=True, index=True,
        help="Where the CAR physically is. Independent of kitchen readiness "
             "(_kitchen_ready) and of payment (_paid).")
    #: Arrival order within a lane. Assigned once, at creation, and never rewritten
    #: — a car's place in the line it joined is a historical fact. Gaps are normal
    #: (a cancelled car keeps its number); active position is derived, not stored.
    lane_sequence = fields.Integer(index=True, copy=False, readonly=True)
    #: Order in the MERGED path, assigned when the car is called forward. This is
    #: the number Payment, Pickup and the expeditor can trust: with two lanes,
    #: arrival order cannot say which car actually merged first.
    service_sequence = fields.Integer(index=True, copy=False, readonly=True)

    called_at = fields.Datetime(help="Entered the merged path (call forward).")
    pickup_window_at = fields.Datetime()
    held_at = fields.Datetime()

    placed_at = fields.Datetime(default=fields.Datetime.now, index=True)
    ready_at = fields.Datetime()
    window_at = fields.Datetime()
    collected_at = fields.Datetime()

    @api.depends('lane', 'vehicle', 'pos_order_id')
    def _compute_name(self):
        for d in self:
            tag = d.vehicle or (d.pos_order_id.tracking_number or d.pos_order_id.pos_reference or '')
            d.name = 'Lane %s · %s' % (d.lane or 1, tag)

    # ---- DT-CORE6 sequence assignment ------------------------------------
    # Two terminals can call cars forward in the same instant, so `max(...) + 1`
    # is not safe: both would read the same maximum and mint the same number.
    # A PostgreSQL sequence settles it in the database — nextval is atomic and
    # never returns the same value twice, whatever the workers are doing.
    #
    # Gaps are fine and expected (a cancelled car keeps its number). Nothing in
    # the product needs contiguity: it needs ORDER, and a monotonic counter gives
    # exactly that. Active position is DERIVED from the live set, so a gap never
    # shows up as "car #4" with no car #3 in front of it.
    _SEQ_LANE = 'mezze_drivethru_lane_seq'
    _SEQ_SERVICE = 'mezze_drivethru_service_seq'

    @api.model
    def _next_sequence(self, name):
        """Atomically claim the next value from a PostgreSQL sequence."""
        self.env.cr.execute(
            "SELECT 1 FROM pg_class WHERE relkind = 'S' AND relname = %s", (name,))
        if not self.env.cr.fetchone():
            # CREATE SEQUENCE IF NOT EXISTS is itself safe under concurrency
            self.env.cr.execute("CREATE SEQUENCE IF NOT EXISTS %s START 1" % name)
        self.env.cr.execute("SELECT nextval(%s)", (name,))
        return int(self.env.cr.fetchone()[0])

    @api.model_create_multi
    def create(self, vals_list):
        """Stamp arrival order at creation — the one moment it is true."""
        for vals in vals_list:
            if not vals.get('lane_sequence'):
                vals['lane_sequence'] = self._next_sequence(self._SEQ_LANE)
            # same compatibility rule as write(): a record created with the legacy
            # state gets the physical stage that state implies
            if vals.get('state') and not vals.get('vehicle_stage'):
                stage = self._STAGE_FROM_STATE.get(vals['state'])
                if stage:
                    vals['vehicle_stage'] = stage
        return super().create(vals_list)

    #: legacy `state` value -> the physical stage it implies. The inverse of
    #: _LEGACY_STATE, used when something writes the OLD field directly.
    _STAGE_FROM_STATE = {
        'collected': 'departed',
        'cancelled': 'cancelled',
        'at_window': 'payment_window',
    }

    def write(self, vals):
        """Keep the physical stage in step when the LEGACY field is written.

        The audit promised that nothing reading `state` has to change. Writers
        deserve the same: existing code, fixtures and any integration that still
        sets state='at_window' must not silently leave vehicle_stage behind, or the
        car would read as "in lane" to the new gate while looking "at the window" to
        the old one — the two fields disagreeing is worse than either alone.

        An explicit vehicle_stage in the same write always wins; this only fills a
        gap. `preparing`/`ready` are deliberately ignored: they are kitchen values
        and say nothing about where the car is.
        """
        if 'state' in vals and 'vehicle_stage' not in vals:
            stage = self._STAGE_FROM_STATE.get(vals['state'])
            if stage:
                # The same door, from the other side. Deriving a stage from the
                # legacy field is exactly how a terminal visit could be walked back
                # into the queue without ever calling _set_stage, so the contract has
                # to hold here too. Re-asserting the terminal stage a record already
                # carries stays fine; moving it anywhere else does not.
                trapped = self.filtered(
                    lambda r: r.vehicle_stage in TERMINAL_STAGES
                    and r.vehicle_stage != stage)
                if trapped:
                    raise UserError(
                        "A %s drive-thru visit cannot be moved to %s."
                        % (dict(VEHICLE_STAGES).get(trapped[0].vehicle_stage,
                                                    trapped[0].vehicle_stage).lower(),
                           dict(VEHICLE_STAGES).get(stage, stage).lower()))
                vals = dict(vals, vehicle_stage=stage)
        return super().write(vals)

    def _claim_service_sequence(self):
        """Assign merged/service order ONCE, when the car enters the shared path.

        Idempotent by design: a second call forward must not renumber the car and
        push it behind vehicles that merged after it.
        """
        self.ensure_one()
        # serialise against another terminal touching this same car
        self.env.cr.execute(
            "SELECT id FROM mezze_drivethru WHERE id = %s FOR UPDATE", (self.id,))
        self.invalidate_recordset(['service_sequence'])
        if self.service_sequence:
            return self.service_sequence
        seq = self._next_sequence(self._SEQ_SERVICE)
        self.sudo().write({'service_sequence': seq})
        return seq

    # ---- DT-CORE6 physical transitions -----------------------------------
    #: vehicle_stage -> the legacy `state` value kept in step for existing readers
    _LEGACY_STATE = {
        'departed': 'collected',
        'cancelled': 'cancelled',
        'payment_window': 'at_window',
        'pickup_window': 'at_window',
        'holding': 'at_window',
    }

    def _topology(self):
        """COMBINED (one window) or TWO_WINDOW. Branch configuration, not a guess."""
        value = self.env['ir.config_parameter'].sudo().get_param(
            'mezze_bridge.drivethru_topology', TOPOLOGY_COMBINED)
        return value if value in (TOPOLOGY_COMBINED, TOPOLOGY_TWO_WINDOW) else TOPOLOGY_COMBINED

    def vehicle_stage_set(self):
        """True when this record already carries an explicit physical stage.

        A brand-new row defaults to 'lane', which is also the value the backfill
        assigns to historical kitchen-only states — so the migration needs a way to
        tell "never migrated" from "legitimately in lane". Anything that is not the
        default counts as set.
        """
        self.ensure_one()
        return self.vehicle_stage not in (False, 'lane')

    def _handoff_stage(self):
        """The physical position where food actually leaves the building.

        Two-window branches hand off at the PICKUP window; a combined branch hands
        off at its single window. Asking "is the car at the handoff position?"
        therefore depends on the branch topology, not on a hardcoded stage.
        """
        return 'pickup_window' if self._topology() == TOPOLOGY_TWO_WINDOW else 'payment_window'

    def _at_handoff_position(self):
        self.ensure_one()
        return self.vehicle_stage == self._handoff_stage()

    def _is_terminal(self):
        """True when this visit is over — departed or cancelled."""
        self.ensure_one()
        return self.vehicle_stage in TERMINAL_STAGES

    @api.model
    def _stage_ended_by(self, action):
        """The terminal stage ``action`` ESTABLISHES, or None.

        Lets a caller tell *repeating the action that ended this visit* — harmless,
        and something a stale board will do — from *undoing* it, which must not be
        possible at all.
        """
        return {'cancel': 'cancelled', 'collected': 'departed'}.get(action)

    def _set_stage(self, stage, **stamps):
        """Move the CAR. Never touches kitchen or payment truth — those have their
        own authorities (_kitchen_ready / _paid) and this method must not pretend
        to know them.

        This is the one place ``vehicle_stage`` moves, so it is where the movement
        contract is enforced: :data:`LEGAL_TRANSITIONS` decides, and a car that has
        departed or been cancelled has nowhere left to go. Re-asserting the stage a
        car is already in is a no-op rather than an error — a second handoff tap on
        a stale board should change nothing, not raise.
        """
        self.ensure_one()
        current = self.vehicle_stage
        if current in TERMINAL_STAGES and stage == current:
            return self          # already over; repeating it must not restamp history
        if stage not in LEGAL_TRANSITIONS.get(current, ()):
            raise UserError(
                "A %s drive-thru visit cannot be moved to %s."
                % (dict(VEHICLE_STAGES).get(current, current).lower(),
                   dict(VEHICLE_STAGES).get(stage, stage).lower()))
        vals = {'vehicle_stage': stage}
        legacy = self._LEGACY_STATE.get(stage)
        if legacy:
            vals['state'] = legacy
        for field, value in stamps.items():
            # first stamp wins: a repeated transition must not rewrite history
            if not self[field]:
                vals[field] = value
        self.write(vals)
        return self

    def _who(self):
        self.ensure_one()
        return self.customer_name or self.partner_id.name or (self.vehicle or 'Car')

    # _kitchen_ready() / _kitchen_ready_map() come from mezze.kitchen.readiness.mixin.
    # The lane board asks for a whole queue at once, so the batch form is the one the
    # board must use; the scalar form remains for single-car call sites (the handoff
    # gate, the create/stage responses) and delegates to the same algorithm.

    def _paid(self):
        self.ensure_one()
        o = self.pos_order_id
        return o.state in ('paid', 'done', 'invoiced') or (o.amount_paid >= o.amount_total - 0.01)
