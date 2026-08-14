# Kitchen readiness — semantics audit before batching (DT-PERF6.1)

Written **before** any optimisation, so the refactor has a written contract to be
measured against. Performance work must not redefine readiness; everything below is
what the code does *today*, at `d8eca31`, including the parts that look wrong.

## Where readiness is defined

Two models carry a byte-identical copy of the same algorithm:

| Model | Method | File |
|---|---|---|
| `mezze.drivethru` | `_kitchen_ready()` | `models/drivethru.py:243` |
| `mezze.delivery` | `_kitchen_ready()` | `models/delivery.py:157` |

```python
def _kitchen_ready(self):
    """True when every KDS ticket for this order is ready/served."""
    self.ensure_one()
    tickets = self.env['mezze.kds.ticket'].search([('pos_order_id', '=', self.pos_order_id.id)])
    if not tickets:
        return True
    return all(t.state in ('ready', 'served') for t in tickets)
```

There is no third copy. Two copies of one algorithm is already a latent divergence
risk; this phase does not merge the models, but it does give them **one
implementation** to delegate to.

## Exact definition

- **Model queried:** `mezze.kds.ticket` only. Ticket *lines*
  (`mezze.kds.ticket.line`) are never consulted — readiness is a ticket-level fact.
- **Relation:** `mezze.drivethru.pos_order_id` → `mezze.kds.ticket.pos_order_id`.
  One order fans out to N tickets (one per station per fire event).
- **Domain:** `[('pos_order_id', '=', <one id>)]`. **No** state filter, **no**
  `config_id`/`company_id` filter, **no** `active` filter, **no** limit.
- **Ready states:** `ready`, `served`.
- **Quantifier:** `all()`. Every ticket must be ready/served — one ticket short and
  the order is not ready.
- **Empty set:** `True`. An order with no KDS tickets at all counts as ready. This
  is deliberate: a drink-only order that routes to no station must not be trapped
  behind a kitchen that was never asked to cook anything.

## Edge cases, as they behave today

| Case | Today | Note |
|---|---|---|
| No tickets | **ready** | early return |
| One `fired` / `accepted` / `preparing` ticket | not ready | |
| One `ready` ticket | **ready** | |
| Many tickets, all `ready`/`served` | **ready** | |
| Many tickets, one still `preparing` | not ready | `all()` |
| **Cancelled ticket present** | **not ready** | `cancel` ∉ `('ready','served')` |
| Multiple stations | every station must be ready | one station finishing is not the order |
| Mixed drive-thru / non-drive-thru | isolated by `pos_order_id` | one order's tickets only |
| Different POS configs / companies | isolated by `pos_order_id` | see below |

### The cancelled-ticket behaviour is preserved, not fixed

A cancelled ticket blocks readiness forever. Arguably a cancelled station slice
should be *excluded* rather than *blocking* — but that is a **product decision about
what "ready" means**, and this is a performance phase. Changing it here would mean a
behaviour change smuggled in under a perf commit, which is exactly the kind of change
nobody can later find. It is recorded here as an open product question and carried
through the batch implementation **unchanged**, with a parity test pinning it
(case F) so it cannot drift silently either.

### Isolation is structural, not filtered

Neither company nor POS config appears in the domain, and that is safe rather than
lucky: the domain keys on a **single `pos_order_id`**, and a `pos.order` belongs to
exactly one config and one company. Tickets of another branch's order can never enter
the result. `mezze.kds.ticket` declares no `company_id` field and this addon declares
no `ir.rule` for it (`security/ir.model.access.csv` carries ACLs only), so there is no
record rule to preserve either.

The batching consequence is the important one: widening the domain from `=` one order
to `in` a **list** of orders keeps this property **only if the list is derived from
the caller's own already-scoped recordset**. The board's recordset is scoped by
`_mezze_scope_base()` (CP11 branch scoping) before this point, so deriving order ids
from `self` — never from a fresh search — keeps isolation identical.

### Access rights

The search runs **unsudoed**, as the API user resolved by `_api_env()`
(`controllers/main.py:735`) — a real internal user with POS rights, not `SUPERUSER`.
The batch implementation must stay unsudoed for the same reason: replacing an ORM
query with `sudo()` to make it cheaper would broaden data access as a side effect of
a performance change.

## Where readiness is consumed

| Call site | File | Cardinality |
|---|---|---|
| Board auto-advance `preparing → ready` | `controllers/main.py:6688` | once per `preparing` car |
| `_dt_payload()` | `controllers/main.py:6147` | **once per car** |
| `_delivery_payload()` | `controllers/main.py:6600` | once per delivery |
| Handoff gate | `controllers/main.py:6801` | once, single record |

The board request therefore executes **two** readiness passes, not one: the
compatibility loop and then the payload loop. Both must be fed by a single
computation, or the N+1 merely moves.

## Legacy `state` still mirrors kitchen readiness

`/drivethru/board` writes `state = 'ready'` for any `preparing` car whose kitchen is
done. After DT-CORE6, `vehicle_stage` is the authority for **where the car is**, and
`state` is the legacy projection — except for `preparing`/`ready`, which are *kitchen*
values that DT-CORE6 deliberately left alone (`_STAGE_FROM_STATE` maps only
`at_window`, `collected`, `cancelled`).

So today:

- `vehicle_stage` — authoritative physical position, never derived from the kitchen.
- `state` in (`at_window`, `collected`, `cancelled`) — legacy projection of
  `vehicle_stage`, kept in step by `write()`/`create()`.
- `state` in (`preparing`, `ready`) — **kitchen readiness cached on the vehicle row**.

That last line is the remaining overload. A future cleanup can drop `preparing`/`ready`
from `state` once every reader (the HTML board's `c.state === 'ready'` fallbacks, the
Register delivery rail, the certified tests) reads `kitchen_ready` instead. **Not this
phase** — this phase only guarantees the mirror costs one query instead of N.

## What batching must therefore guarantee

1. `batch[car.id] == car._kitchen_ready()` for every record, every case above.
2. One readiness computation per board request, shared by both consumers.
3. Domain derived from `self`, unsudoed, no company/config widening.
4. No stored/cached readiness field — the KDS stays the single authority.
