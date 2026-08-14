DT-PERF6.1 — drive-thru service sequence under concurrent REAL HTTP, workers=4
=============================================================================

Closes the evidence gap DT-CORE6 recorded honestly: sequence allocation had been
proved at the database level (20 independent processes claiming nextval, 20
distinct values, 0 collisions) but never through the controller, because the
4-worker fixture of that day had no POS config to race against.

Environment
-----------
Odoo                19.0 (Community), mezze_bridge 19.0.2.8.1
PostgreSQL          isolation: read committed
Runtime             odoo-bin, workers=4, max-cron-threads=0, isolated data-dir
                    isolated database (template copy), not the pilot runtime
Auth                real per-terminal bearer token (mezze.terminal, role=terminal).
                    No endpoint auth was weakened for the test.
Endpoint            POST /mezze/api/v1/drivethru/stage  {action: "window"}
Client              barrier-aligned threads; every request a real HTTP POST.
                    No model method is called in-process anywhere in this proof.

Worker PIDs that served a call-forward: 4 distinct
    3125866  3125869  3125872  3125875
Call-forward requests served: 32
Unexpected HTTP 5xx: 0

Scenario 1 — 20 DISTINCT cars, both lanes, released in one instant
------------------------------------------------------------------
    requests                      20
    HTTP                          200 x 20
    unique sequences returned     20
    unique sequences persisted    20
    unassigned (0) sequences      0
    collisions                    0
    lanes involved                1, 2
    stage after                   payment_window (all)
    cars lost                     0

Scenario 2 — the SAME car, 8 simultaneous call-forwards
-------------------------------------------------------
    requests                      8
    HTTP                          200 x 8
    distinct sequences observed   [62]      <- one, across all eight responses
    logical assignments           1
    final persisted sequence      62
    final stage                   payment_window
    all responses agree           yes

    The idempotent claim holds under a real race: seven callers observe the
    assignment the first one made rather than renumbering the car behind vehicles
    that merged after it, and no caller sees an error for arriving second.

Scenario 3 — lane 1 and lane 2 released together
------------------------------------------------
    requests                      4
    HTTP                          200 x 4
    lanes involved                1, 2
    sequences                     [64, 63, 66, 65]
    unique                        4
    collisions                    0
    merged order is a total order yes

Global state afterwards
-----------------------
    cars on board                 40
    cars carrying a sequence      25
    DUPLICATE SEQUENCES           0

Window occupancy — NOT TESTED, and deliberately reported as such
----------------------------------------------------------------
The brief asks for an occupancy race only if the topology contract actually
enforces single occupancy. It does not: /drivethru/stage has no occupancy check,
and scenario 1 put twenty cars into payment_window at once without objection.
There is therefore no contract to race against, and asserting a pass here would
be inventing one. Recorded as a design gap for whoever takes on pull-forward or
a second physical window with enforced capacity.

Rate limiting
-------------
Untouched by this phase. TestRateLimit.test_atomic_under_real_concurrency remains
what DT-CORE6 reported: green at workers=0, reproducing 15 != 25 at workers=4,
with the RateLimit code byte-identical to RC7.

Reproduce
---------
    ./dt_sequence_run.sh <db-with-pos-config> <free-port> <path-to>/mezze/addons 40
