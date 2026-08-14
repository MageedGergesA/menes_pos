"""DT-CORE6 — backfill the vehicle journey onto existing drive-thru records.

`vehicle_stage`, `lane_sequence` and `service_sequence` are new. Existing rows
would otherwise all read as `lane` with sequence 0, which would put historical
cars ahead of live ones in any ordering.

What can be recovered honestly:

  collected  -> departed          (unambiguous)
  cancelled  -> cancelled         (unambiguous)
  at_window  -> payment_window    (see the limit below)
  preparing  -> lane              these were KITCHEN values written onto the
  ready      -> lane              vehicle record; they say nothing about position

LIMIT, recorded rather than papered over: a historical `at_window` row cannot say
whether the car was at PAYMENT or at PICKUP — the old model had one flag for both,
which is the very gap this phase closes. They are mapped to `payment_window`,
which is exactly right for a combined-window branch and is the first window in a
two-window branch. No payment/pickup history is invented for records that never
recorded it.

`lane_sequence` is backfilled in arrival order per lane, which IS recoverable
(placed_at, then id). `service_sequence` is deliberately left at 0 for historical
rows: the order in which old cars merged was never recorded, and inventing one
would be a fabrication that later reads as fact.
"""
from odoo import api, SUPERUSER_ID

STAGE_FROM_STATE = {
    'collected': 'departed',
    'cancelled': 'cancelled',
    'at_window': 'payment_window',
    'ready': 'lane',
    'preparing': 'lane',
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Drivethru = env['mezze.drivethru'].with_context(active_test=False)
    cars = Drivethru.search([], order='lane asc, placed_at asc, id asc')
    if not cars:
        return

    # 1. physical stage, derived from what the old state can actually tell us
    for state, stage in STAGE_FROM_STATE.items():
        batch = cars.filtered(lambda c, s=state: c.state == s and not c.vehicle_stage_set())
        if batch:
            batch.write({'vehicle_stage': stage})

    # 2. arrival order per lane — recoverable, so recovered
    seq_by_lane = {}
    for car in cars:
        if car.lane_sequence:
            continue
        lane = car.lane or 1
        seq_by_lane[lane] = seq_by_lane.get(lane, 0) + 1
        car.write({'lane_sequence': seq_by_lane[lane]})

    # 3. keep the live sequence ahead of everything backfilled, so a new car never
    #    collides with a historical number
    highest = max(cars.mapped('lane_sequence') or [0])
    if highest:
        cr.execute("SELECT 1 FROM pg_class WHERE relkind = 'S' AND relname = %s",
                   ('mezze_drivethru_lane_seq',))
        if not cr.fetchone():
            cr.execute("CREATE SEQUENCE IF NOT EXISTS mezze_drivethru_lane_seq START 1")
        cr.execute("SELECT setval('mezze_drivethru_lane_seq', %s)", (highest + 1,))
