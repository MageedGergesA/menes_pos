# Kitchen production engine

## Order → KDS firing

Register's course Fire, its "Send to kitchen" tile, and Handheld's `hhFire()` all call one shared
builder, `fireLinesToKds()` — **BUILT + INTERACTIVELY VERIFIED on both surfaces.** Register and
Handheld second-fire dedup: VERIFIED (re-firing sends only new lines, no duplicate ticket).
Different-station second fire on Handheld: VERIFIED (a new line on a different station
creates/updates only that station's ticket, leaving the first untouched).

Each KDS ticket item carries `mods` (structured modifier array) and `note` (free-text kitchen
instruction) as two independent fields, both rendered on the ticket card with their own visual
treatment — never flattened into one string. See `docs/MENU_ENGINE.md` §2a for the canonical
OrderLine contract.

Contract between the prototype (`Mezze POS v3.dc.html` — 03 Kitchen) and the Odoo 19 implementation.
The competitive audit names these three as Syrve's real advantage, and they are all the same idea: a
kitchen does not only *assemble tickets to order*, it **produces** — ahead of service, in batches,
through stages that take hours.

The five existing views (ticket grid, station lanes, expo, all-day, prep) stay exactly as they are.
This is depth added beneath them, not a sixth view competing for the same screen.

**The principle:** a ticket is demand. Production is supply. Every defect in a kitchen at 20:00 is a
supply decision made — or not made — at 11:00.

---

## 1. Multi-stage production

Some things a kitchen sells are not cooked when ordered; they are *moved through stages*, and a stage
can take twelve hours.

```
Frozen ─→ Thaw ─→ Prep ─→ Cook ─→ Hold ─→ Pass
```

| Stage | Owns | Clock |
| --- | --- | --- |
| `frozen` | in the freezer, unavailable today unless it moves now | — |
| `thaw` | in the chiller, unavailable until it finishes | **hours**, and it cannot be hurried |
| `prep` | portioned, marinated, trayed | minutes |
| `cook` | on the line | minutes, per station |
| `hold` | cooked and holding, with a **discard-by** clock | minutes, and expiry is a waste record |
| `pass` | on the pass, plated to a ticket | seconds |

Rules that make it a state machine rather than a label:

- **A stage is entered by a person, with a time.** The clock on `thaw` and `hold` is the whole point:
  thaw started at 09:40 is available at 21:40, and knowing that at 11:00 is what prevents an 86.
- **Forward only.** Cooked cannot go back to prep; frozen re-thawed is a food-safety incident, not an
  undo. A mistake is a waste record (`docs/INVENTORY_WASTE.md`), which is the honest reversal.
- **`hold` carries an expiry.** When it passes, the batch is not "still there" — it is waste, and the
  engine writes it as waste rather than quietly letting the line serve it.
- **Availability reads the chain, not the freezer.** A dish whose component is `frozen` with no thaw
  started is **not available today**, and that is exactly the 86 the branch takes at 19:00 without
  knowing why. This is the join into `docs/86_OPEN_ORDER_IMPACT.md`: the chain is what lets 86 be
  predicted instead of discovered.

## 2. Forecast prep

The question every kitchen answers badly: *how much of this do we need before service?*

```
Chicken breast          Expected 84 portions
                        Prepared 50
                        Required  +34        ← the only number that matters
```

| Input | From |
| --- | --- |
| Expected | forecast portions for the service — velocity by daypart × cover forecast, with bookings on the book already counted |
| Prepared | what production has actually credited: closed batches plus prep-stage quantities |
| Required | `expected − prepared`, floored at zero, **rounded up to the batch size** — a kitchen cannot make 34 portions of a 40-portion batch |

Rules:

- **Required is derived, never typed.** The moment someone can type it, it stops agreeing with either
  the forecast or the production floor.
- **Forecast is stated with its basis**, so a chef can disagree with it: "84 = 12 covers/hour × 7
  hours × 1.0 attach, plus 2 bookings of 8". A number with no basis gets ignored, then blamed.
- **Under-prep and over-prep are both flagged.** Over-prep is tomorrow's waste; the audit only ever
  looks at the shortage.
- **It is a prep list, not a report**: each row's Required is one tap away from a planned batch, which
  is where §3 begins.

## 3. Batch production

`Prepare 6 kg hummus → assign → start → complete → yield`

Already built in this prototype and shown on the Kitchen surface: `CM_PREP` carries the recipe, batch
size, BoM and expected loss; `cmBatchInputs` values the draw through the same per-line rounding the
waste ledger uses; `cmBatchStart` refuses a batch the store cannot cover and consumes the inputs;
`cmBatchStep` records the weighed output; `cmBatchClose` divides real input cost by real output to set
the prepared product's unit cost and posts the yield variance.

| Step | State | What it writes |
| --- | --- | --- |
| plan | `planned`, no `by` | quantity against a prep recipe — raised by **Plan a batch** on the board, or by the forecast (§2) |
| **assign** | `planned` + `by` | the cook who owns it — added by this piece of work, on the batch's existing `by` field rather than a second one |
| start | `cooking` | inputs consumed out of commissary stock, at cost |
| complete / weigh | `yielded` | actual output, off the scale |
| yield | `closed` | unit cost = input cost ÷ actual output; variance vs expected loss |

The rule that matters, and the one Syrve is bought for: **unit cost is what the batch actually cost,
not what the recipe hoped**. A 40 kg batch that yields 36 kg costs 11% more per kilo, and every plate
made from it should carry that.

**Assign** is not administrative. An unassigned batch is the one nobody starts; the assignment is what
makes "why is the hummus not ready?" a question with an answer.

One field, not two: the batch already carried `by`, and the board already printed it in the card
header. Writing assignment to a new `who` put a cook's name and the word *unassigned* on the same card
four lines apart, and gated the start on the empty one. The chips use the **same name form as the seed
and the header** — full names — because two spellings of one person is that defect in a different
coat. The list is every line cook and bar hand, off-shift ones marked and still selectable: a batch
for the evening is often assigned to whoever comes in for it.

## 4. How the three connect

```
forecast (§2) ─ required ─→ planned batch (§3) ─ assigned ─→ started ─→ yielded
                                                                 │
                            stages (§1) ─────────────────────────┴─→ hold ─→ pass ─→ ticket
```

One direction, one set of quantities. The forecast's *prepared* figure reads closed batches and
prep-stage quantities — it is not a second tally — and a dish's availability reads the stage chain, so
the kitchen, the menu and the 86 sheet cannot disagree about whether something can be sold.

## 5. Odoo mapping

| Design | Odoo 19 |
| --- | --- |
| Prep recipe | `mrp.bom` on the prepared product |
| Batch | `mrp.production` (MO), quantity + assignee |
| Inputs consumed | stock moves on MO start, from the production warehouse |
| Weighed output | MO finished-product quantity, actual |
| Unit cost from real yield | MO cost analysis → product cost update (this is where Odoo needs help: it will happily keep the standard cost) |
| Stages | MO work orders (`mrp.routing.workcenter`) — Thaw and Hold are workcentres with durations |
| Hold expiry | lot/serial expiry on the finished product; expiry → scrap |
| Forecast | custom: velocity × cover forecast, per prepared product |
| Assignment | `user_id` on the MO / work order |

Two things Odoo will not do out of the box and must be built: **thaw and hold as timed stages that
gate availability**, and **forecast-driven required quantities** that raise MOs.

## 6. What the prototype does today

- **Batch production** — the whole chain (§3), on the Kitchen surface, with input cost, expected loss,
  weighed yield, real unit cost and the variance. **Assign** now records the cook against the batch
  and refuses a start on an unassigned one.
- **Multi-stage production** — **built and interactively verified** (Thaw→Prep advance,
  Discard→waste, manager override with reason, Flag-as-86 wired to the real `toggle86()`). New
  Kitchen layout tab “Production stages”
  (`cmStData()`/`cmStAdvance`/`cmStAssign`/`cmStDiscard`/`cmStOverride`). Tracks the raw proteins
  (chicken, lamb, kofta — the same `stock` ids Inventory already owns, not a second catalog)
  through Frozen→Thaw→Prep→Cook→Hold→Pass. Thaw and hold each carry their own clock and go
  late against it; prep/cook refuse to advance with nobody assigned; hold past its clock is
  **Discard**, which writes to the same `wasteLog` Inventory’s waste ledger already owns — not a
  second waste array. **Manager override** skips a stage with a required reason, written to the
  audit log (`stLog`) with the approver’s name. A component sitting at `frozen` with no batch past
  it surfaces a **Flag as 86** action that calls the existing `toggle86()` — the same 86 flag every
  other screen reads, never a parallel prediction flag.
- **Forecast prep** — **built**. New Kitchen layout tab “Forecast prep” (`cmFcData()`). Reads
  `AN_DAYPART` (the same velocity Analytics trusts) for expected demand, and `cmBatches()`/`CM_PREP`
  (the same batch-production records §3 already owns) for prepared and in-production quantities.
  Required is `max(0, expected − prepared − in-production)`, suggested batch rounds that up to the
  recipe’s batch size, and a manager adjustment or dismissal is recorded with a required reason
  rather than silently overwriting the number. Risk (`Healthy`/`Prep soon`/`Shortfall expected`/
  `Already short`/`Over-prepared`) is derived from the same three quantities plus the need-by clock
  — never a separate flag someone sets by hand.

## 7. Gaps, in build order

1. ~~Stage board~~ — built (§6).
2. ~~Forecast board~~ — built (§6). Per-station forecast breakdown (item below) still open.
3. **Availability from the chain, beyond the manual flag** — the stage board *offers* the 86 flag
   as an explicit action; it does not yet auto-set it. Whether that should be automatic or always
   a confirmed human action is a product call, not a build gap — left as a manual action on
   purpose this round.
4. ~~Hold expiry → waste~~ — built (§6): Discard writes to `wasteLog`.
5. **Per-station forecast** — a grill forecast and a cold-section forecast are different shifts of
   people. Not built; the current forecast board is per-item, not yet split by station.

## 8. Acceptance

Open the planned Pita dough batch (60 kg): the card header and the ASSIGNED TO line show the **same**
cook, and it starts. Tap **Plan a batch → Hummus base · 40 kg**: a new batch appears reading *Planned*
with **unassigned** in both places, and Start refuses — *"an unassigned batch is the one that never
gets made"*. Assign a cook from the chips, including one who is off shift, and it starts: chickpeas,
tahini or flour leave commissary stock at cost, and a batch the store cannot cover is refused by name.
Weigh 55.9 kg off the line against a 6% expected loss: the yield variance and a unit cost of input ÷
55.9 are written to the prepared product — so every plate made from it carries what it actually cost,
not what the recipe hoped. The forecast row for chicken breast reads
`Expected 84 · Prepared 50 · Required +34`, states its basis, and rounds the requirement up to the
batch size. A component sitting at `frozen` with no thaw started reports the dish as unavailable today
— before service, not during it.

## Closure pass 15F — Handheld → KDS with note, Refire → KDS

**Handheld modifiers + note → KDS.** `fireLinesToKds()` is unchanged as the single ticket
builder; Handheld's `hhFire()` now maps `note` through in its line payload alongside `mods`, so
a Handheld ticket shows structured modifiers and free-text note as two separate rows on the
KDS item (`i.m` / `i.hasNote`+`i.note`), exactly as Register's lines do. Second-fire dedup is
unchanged (same-check/same-station open-ticket append) — an empty second `Send` adds nothing.

**Refire → KDS.** `refireConfirm()` previously only wrote `wasteLog`/`rfLog` and toasted the
manager — nothing reached Kitchen. It now also calls the shared `fireLinesToKds()` with a single
line built from the *original* fired line's `mods`, `note`, `seat` and `course`, under a
`checkRef` of `'RF-'+timestamp` (always a fresh ticket — never silently merged into the original
order's still-open ticket) and a title of `Refire · <reason> · Table <n>`. Kitchen sees the
remake as a distinct, explicitly-labelled ticket, not a duplicated original order. Dedup rides
the existing "sheet closes on success" guard — `refireConfirm()` cannot be invoked twice for the
same event without reopening the Refire sheet and re-picking reason/station.

**Refire payload semantics, restated:** three independent facts survive a refire —
`hit.line.mods`/`hit.line.note` (untouched on the original line), `cfg.k` (the refire reason,
written only to `rfLog[]` and the new ticket's title), and the waste/cost consequence
(`wasteLog[]`, `stock` decrement). None is ever written into another.

## Closure pass 17C — combo lines derive per-component station work

`fireLinesToKds()` gained one branch: when the fired line's product is `isCombo`, it does not
emit one ticket entry under the combo's own category — it emits one entry PER selected
component (`l.mods`), each routed via the same `itemStation()`/`ITEM_STATION` every ordinary
line already uses. A component resolves its station through the real product it names (`pid`,
matched by name at group-authoring time) or, failing that, a category inferred from the choice
group's own name ("Drink"/"Side"/"Main") — same `ITEM_STATION` map, no combo-specific routing
table, no hardcoded per-item station guess. Each derived entry carries `comboCtx` ("Grill Meal ·
Main") so the station operator understands why the item is there. The combo stays ONE customer
order line — this only changes what Kitchen sees, never billing, quantity, or the OrderLine
contract. Second-fire dedup needs no new mechanism: a combo line's `status` field gates re-send
exactly like any other line's.

Bug found and fixed during interactive verification: a component with no real menu-product
match (e.g. a "Cola" Drink choice with no Cola product on the menu) intermittently fell back to
the COMBO's own station instead of the category inferred from its choice group. Fixed by
recomputing that category fallback live inside `fireLinesToKds()` rather than trusting only the
value captured at group-save time — still the same `ITEM_STATION` lookup, just made resilient to
where in the pipeline the category is actually available.

## Closure pass 17C — Kitchen consequence principle: fired lines are historical instruction

A fired line is what Kitchen was told to make; a Send after that must never silently rewrite it.
Register previously allowed direct modifier/note edits and free qty decrement on ANY fired line
(the combo-only guard from pass 17B was the exception, not the rule) — generalized in
`docs/ORDER_STATE_MACHINE.md` §"Fired-line amendment rule" to every line. Consequence for this
doc: `fireLinesToKds()` only ever receives genuinely NEW demand — a fired line's quantity
increase creates a separate NEW line rather than mutating the fired one, so a second Send still
fires only what is actually new, never a re-send of history dressed up as a quantity bump.
