# Terminal-state safety under a real concurrent HTTP race, workers=4

The in-suite test (`TestDriveThruTerminalState.test_17`) asserts the same invariant
by **landing order**, because a POS test cursor serialises and real threads there
would deadlock rather than test anything. This is the version with actual
parallelism, and it is the answer to the audit's question: *can a call-forward that
arrives at the same instant as a cancellation leave the car at a window?*

## Environment

| | |
|---|---|
| Odoo | 19.0 Community, `mezze_bridge` 19.0.2.8.1 |
| Runtime | `odoo-bin --workers=4`, isolated data-dir, **isolated database** (`mz_termrace`, a template copy — not the pilot, not production) |
| Auth | real per-terminal bearer token; no endpoint auth weakened |
| Client | barrier-aligned threads; every request a real HTTP POST |
| Worker PIDs that served a transition | **4 distinct** — 300963, 300964, 300966, 300968 |
| Transition requests served | 43 |
| Unexpected HTTP 5xx | **0** |

## A — cancel races call-forward, 12 cars at once

For each of 12 cars, `cancel` and `window` were released **in the same instant**:
24 simultaneous requests.

```
http                         200 ok                  18
                             409 invalid_transition   6
final stages                 cancelled               12
cancelled cars at a window                            0
resurrected                                          []
```

Both orderings occurred and both are correct. Where the call-forward landed first,
the car reached `payment_window` and the cancellation then legally ended it
(active → cancelled). Where the cancellation landed first, the call-forward was
refused with `invalid_transition`. **Every one of the 12 cars ended `cancelled`, and
none was left standing at a window.** That is the invariant.

## B — one car, eight simultaneous cancels

```
http            200 ok    8
final stage     cancelled
server errors   0
```

Repeating the action that ended the visit is a no-op by design, so a storm of them
is quiet rather than an error cascade — which matters, because a stale board is
exactly what generates one.

## C — a departed car stormed with eight transitions

`window`, `pickup`, `hold`, `cancel`, `window`, `collected`, `pay`, `ready`, all
released together against a car that had already been handed off:

```
http                   409 invalid_transition   7
                       200 ok                   1   (the repeated `collected`)
final stage            departed
timestamp unchanged    yes
```

## Reproduce

```
./tests/concurrency/dt_sequence_run.sh mz_termrace 8093 <path-to>/mezze/addons 40   # seed + serve
PORT=8093 python tests/concurrency/dt_terminal_race.py
```

The harness lives in `tests/concurrency/`, which this repo keeps out of version
control on purpose (see its siblings); this file is the committed evidence.
