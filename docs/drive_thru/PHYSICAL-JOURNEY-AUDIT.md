# Drive-Thru physical journey — audit before design (DT-CORE6 Phase 0)

Audited at `c9b3043`. Every claim read from source.

## 1. The state field is OVERLOADED — measured, not suspected

`mezze.drivethru.state` holds five values: `preparing`, `ready`, `at_window`,
`collected`, `cancelled`. They are **not the same kind of fact**:

| Value | What it really is | Source of truth |
|---|---|---|
| `preparing` | **kitchen** | `_kitchen_ready()` → KDS tickets |
| `ready` | **kitchen** | same |
| `at_window` | **vehicle position** | operator's Call forward |
| `collected` | **vehicle position** (departed) | operator's handoff |
| `cancelled` | terminal exception | operator |

The proof is in `/drivethru/board`:

```python
# auto-advance preparing -> ready when the kitchen is done
for c in cars.filtered(lambda x: x.state == 'preparing' and x._kitchen_ready()):
    c.write({'state': 'ready', 'ready_at': fields.Datetime.now()})
```

`preparing`/`ready` are *derived from KDS and written back onto the vehicle record*
— duplicated kitchen truth. So the field answers "where is the car?" and "is the
food done?" with one value, and cannot answer either precisely.

## 2. What `at_window` cannot express

One flag has to stand for every physical position:

- called forward but not yet at a window
- at the **payment** window
- left payment, heading to **pickup**
- at the **pickup** window
- pulled forward / holding

A two-window branch cannot be represented at all: a car at payment and a car at
pickup are both simply `at_window`.

## 3. Position is derived per request, not owned

```python
pos = {}
for c in cars:
    if c.state in live:
        pos.setdefault(c.lane, 0); pos[c.lane] += 1
```

Recomputed on every board call from `_order = 'lane asc, placed_at asc, id asc'`.
That is **arrival order within a lane**, and only that. It cannot express:

- **merged order** — which car actually entered the shared path first. Two lanes
  called `A, D, E, B` produce merged order `A D E B`; `placed_at` yields `A B D E`.
- a car that was called forward out of arrival order
- a car parked/pulled forward

## 4. Concurrency precedent in this codebase

`SELECT … FOR UPDATE` row locking is the established mechanism
(`kds_ticket.py`, `delivery.py`, `mezze_terminal_txn.py`, `mezze_payment_qr.py`).
No `ir.sequence` use exists in the addon. Any sequence assignment must not be
`max(...)+1` without protection: two terminals can call cars forward at the same
moment.

## 5. Compatibility surface — what reads `state`

- `/drivethru/board` (live filter, auto-advance, position)
- `/drivethru/stage` (`ready` / `window` / `collected` / `cancel`)
- `drivethru.html` (queue filter, payment & pickup selection, verdicts)
- `TestDriveThruHandoffGate`, `TestDriveThruUx`, `TestDriveThruKdsIdentity`

`state` therefore cannot be deleted or repurposed in this phase.

## 6. Decision

Add an authoritative **`vehicle_stage`** alongside `state`, and keep `state`
maintained for compatibility rather than reinterpreting it. New physical
transitions write both: `vehicle_stage` is the authority, `state` is the legacy
projection. Nothing that reads `state` today has to change to keep working.

**Pull-forward:** not required by any current code path, so not implemented as UX.
A `holding` stage is reserved in the vocabulary so it can be introduced later
without renumbering sequences — recorded as **EXTENSIBLE**, not supported.
