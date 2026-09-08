# Menu engine

Contract between the prototype (`Mezze POS v3.dc.html`, screen 21 Menu — five tabs) and the
Odoo 19 implementation.

**The principle:** a menu is not a list of products. It is products, the ways they can be modified,
the bundles they appear in, the windows they are available in, the channels and branches that see
them — and a **version** of all of that, which goes live as one unit. The competitive audit found
each of these missing; this document is the whole engine.

The workflows live **inside** screen 21 as tabs (Products · Modifier groups · Combos & deals ·
Availability · Versions), not in a separate menu-management app. A manager changing a price and a
manager scheduling next week's carte are the same person at the same terminal.

---

## 1. Products and categories

| Design | Odoo |
| --- | --- |
| Menu item | `product.template` (`available_in_pos = true`) |
| Category chips | `pos.category` for till grouping; `product.category` for accounting/costing |
| Price | `list_price`, overridden by pricelists per daypart / channel / branch |
| Station routing | Custom field → KDS printer/station |
| 86 / out of stock | POS availability flag, **not** archiving — an archived product loses its history |

Keep the two category trees distinct: `pos.category` is how the till is laid out for a server's
thumb; `product.category` is how finance groups cost. Conflating them makes one of the two wrong.

## 2. Modifier groups and modifiers

| Design | Odoo |
| --- | --- |
| Modifier group (Size, Spice level, Add-ons, Doneness, Preparation) | `product.attribute` |
| Modifier option | `product.attribute.value` |
| Price delta on an option | `product.template.attribute.value.price_extra` |
| Required / optional, min / max picks | POS-side rule (custom); Odoo has no native min/max |
| Option 86'd | Availability flag on the attribute value |
| Default option | `default_extra_price` pattern / POS pre-selection |

### 2a. Structured modifier selections — the canonical shape

**A rendered label (`Large · Extra spicy · No onion`) is derived, never stored.** The order line's
own fact is a structured array; the label is computed from it on demand by one shared function,
`modsText(mods)`, called wherever a line needs to display.

```
OrderLine
  id, item (product id), name, qty, price      // price already includes the delta
  mods: ModifierSelection[]

ModifierSelection
  g   modifier_group_id  (the group's key, e.g. 'size', 'spice')
  t   option label        (also today's option identifier — see caveat below)
  p   price_delta
```

`modsText(mods)` and `modsHas(mods)` are the only two places that read `mods` as anything other than
this array; every surface that displays or checks for modifiers calls them rather than assuming a
shape. `modsEq(a,b)` is the array-aware equality used when merging identical lines (a string `===`
comparison silently stopped merging identical configurations the moment the shape changed, which is
exactly the kind of drift this exists to prevent).

**Done and interactively verified this pass:** the main Register (`modLabel`, `saveMods`, the
cart-line renderer) and the Handheld order sheet (`hhModText`) now read and write this **same**
shape and the **same** helper. Before this pass, Register stored a pre-joined string
(`"Large · Extra spicy"`) as the line's fact, while Handheld already stored the structured array —
two owners for one fact, and the Register string could not carry a price delta or a group id at
all, only a label. That defect is closed for these two surfaces.

**Free-text kitchen notes are a separate field, `note` — never inside `mods`.** A structured
modifier selection and a free-text instruction ("Well done", "No sugar", "Serves 4 · No lamb") are
different facts with different owners: `mods` is always an array (empty `[]` when there are none),
`note` is a plain string, and they coexist on the same line without either overwriting the other.
This pass migrated every seed line that had been storing a free-text instruction as a bare string
in `mods` (18 lines) over to `mods:[], note:'...'`, and removed the `typeof mods==='string'`
tolerance from `modsText()`/`modsHas()`/`modsEq()` and the two remaining `Array.isArray(l.mods)`
guess-sites (the KDS ticket builder, the CFD line mapper) now that every writer produces an array.
The KDS ticket builder and the cart-line renderer both now also expose `note` as its own field
alongside the derived `mods` label. **Not done this pass:** a template change to actually render
`note` visibly in the Register cart line and on the KDS ticket card — the data is wired through,
the visible display is still open.

A weighed line (Baklava, sold by weight) carries `weight:true` and its amount in `qty` (the same
field every line already uses for "how much") — never a duplicate text annotation in `mods`. That
was fixed in an earlier pass; this pass's array-only cleanup of the reader functions depended on
it already being true (a weight line still writing a string into `mods` would have broken the
same way the free-text notes did).

**Real order → KDS firing path — built and interactively confirmed working, on both Register and
Handheld.**
`fireLinesToKds(lines, meta)` is the one shared builder: Register's per-course Fire action and its
"Send to kitchen" tile (which had **no onClick at all** before this pass — a dead button) both
call it. Confirmed live: fired a real check's fireable lines, watched the Kitchen ticket count go
from 14 to 16 and a genuinely new ticket appear on the board; clicking Send again with nothing new
produced "Nothing to send · every line on this check is already fired" — no duplicate ticket, no
duplicate food. Station routing uses `itemStation(item)`, a category→station map since no per-item
station field exists on the catalog — the smallest real routing owner available, not a per-item
hardcode. Ticket items carry the structured `mods` array plus a derived label via `modsText()`,
seat, course, line id and allergen.

**Caveat, stated plainly:** the option identifier today is its display **label** (`t`), not a
stable id — because the modifier catalog itself (`MODS[group].opts[]` in Register, `MN_MODGROUPS` in
the Menu editor) does not yet assign one. Renaming an option's label today would silently detach it
from any line already using it. Odoo's `product.attribute.value` has a real numeric id; when this
persists to Odoo, `t` should be replaced by that id, with the label kept only for display. Flagged
in `docs/CLAUDE_CODE_HANDOFF.md` under BE-010.

**Not yet unified this pass** — each of these still has its own local shape or its own gap, and
was not touched:
- **Kiosk/self-order (`ks*`)** and **Call centre (`cc*`)** carts currently do not carry modifier
  selections into their draft lines at all (`mods:[]`, always empty) — not a shape mismatch, a
  missing capability.
- **Handheld's own Send action** does not yet call the shared `fireLinesToKds()` — Register's two
  fire points (course, whole-check) do; Handheld still needs the same wire.
- **Park/recall, split, transfer, refund, repeat-last-order** each carry the Register/Handheld line
  **object** forward by reference or spread (`{...l}`) rather than reconstructing it — so as long as
  the object's `mods` is the structured array, these paths are correct *by construction* and were
  not separately touched. This was reasoned through, not individually click-tested this pass.
- **Plate cost / recipe consumption** reads `COST_USE`/`COST_ITEMS` keyed by product, not by
  modifier selection — a modifier's own component impact (e.g. "extra cheese" drawing more cheese
  stock) is not costed anywhere yet. Real gap; not attempted this pass.
- **Weight-line annotation exception:** a weighed line (`applyPad`) writes a **string** into the
  same `mods` field (`"0.500 kg"`) as a display note — this is not a modifier selection, and
  `modsText()`/`modsHas()` both special-case a string input so this keeps working, but it is a
  field-name collision worth cleaning up later (e.g. renaming to `note`) rather than a modifier bug.


Two design decisions worth keeping:

- **Min/max is enforced at the till, not suggested.** `Doneness` on a lamb chop is `required, pick
  one` — the server cannot send the line without it, because the grill cannot cook it without it.
- **A zero-delta option is still a modifier.** `No coriander` changes the kitchen ticket and the
  allergen line; it must not be a free-text note.

Where a modifier changes cost materially — `Rice upgrade`, `Large` — the option needs its own BoM
delta, or plate cost silently understates. This is the one place the prototype shows a price extra
but not yet a cost extra; see open questions.

## 2b. Closure pass 15C — Scenario C/D verification

**Scenario C (modifiers + note on one line) — PASS.** Shish Tawook ×1, `mods:[Large,Hot]`,
`note:"No parsley"`.

- **C1 edit modifiers, keep note — PASS after a fix.** Audit found a real bug: `openMods()` built
  `sel` from each group's default (index 0 / empty array) instead of the line's own `mods`, and
  hardcoded `qty:1` regardless of the line's actual quantity. Reopening a line for editing silently
  discarded its current selections and would have reset qty to 1 on save. Fixed: `openMods()` now
  reconstructs `sel` per group from `existing.mods` (matching each stored selection's label back to
  its option index) and seeds `qty` from `existing.qty`. With the fix, changing Hot→Medium keeps
  Large, keeps `note`, and keeps qty untouched.
- **C2 edit note, keep mods — PASS.** With `sel` now preserved on reopen, `saveMods()` recomputes
  the identical `mods` array and writes only the new `note`. No duplication, no merge.
- **C3/C4 fire + refire — PASS.** `fireLinesToKds()` appends to the same open ticket
  (`checkRef`+station, status `fired`/`cooking`) rather than cloning one; the check-level Send
  action separately guards a second press with "Nothing to send" once every line is already fired.
  Mod row and note row render as distinct lines on the ticket card — never joined, never
  `[object Object]` (both are plain strings by construction).

**Scenario D (weighed Baklava, 0.600 kg) — PASS.**

- **D1/D2 Register + price — PASS.** `applyPad()` writes `weight:true, qty:0.600, mods:[]`, no
  note unless added. Price uses the same `amt()` every line uses — 480 LE/kg × 0.600 = 288 LE.
- **D3 CFD — PASS.** The CFD line mapper (`cfdLines`) exposes only `q`, `n` and the structured-mod
  text `mod` — it never reads `note` at all, so kitchen notes are structurally excluded from the
  guest display rather than merely hidden by a flag. Structured modifiers still surface there.
- **D4 KDS — PASS, routed.** Baklava's category (Desserts) routes to the Pastry station via
  `itemStation()`. A fired weight line shows `0.600 kg` with no modifier row (`modsText([])` is
  empty for a weight line).
- **D5 note on a weighed line — PASS.** The same `openMods`/`saveMods` path used for C1 (now
  fixed) carries a weight line's note independently of its qty; no new capability was built.

**Legacy spot check ("Well done", "No sugar", "Serves 4 · No lamb") — PASS.** All three seed lines
store `mods:[]` with the text in `note`, confirmed directly in the seed data.

**CFD internal-note policy — VERIFIED.** `note` is not read anywhere in the CFD line mapper.

**Bug found/fixed this pass:** `openMods()` not reconstructing `sel`/`qty` from the line being
edited (above) — the one functional bug the audit turned up. Nothing else in `mods`/`note`/`weight`
handling, KDS, or CFD needed a change.

**Method note (15C):** verified by tracing every reader/writer of `mods`, `note` and `weight` end
to end (Register, KDS ticket builder, CFD mapper, seed data) rather than a recorded click-through.

## 2c. Closure pass 15D — interactive re-verification of the openMods fix

Re-run live, by hand, against the actual running prototype (not code trace) — Scenario C in full,
Scenario D through D4/D5. All PASS.

- **C initial + C1 + C2 — PASS.** Added Shish Tawook ×1 / Large / Hot / "No parsley". Reopening
  the line showed Large **and** Hot already selected, qty still `1`, note still "No parsley" — the
  exact pre-fill the 15C fix targeted. Swapped Hot→Medium and saved: Large stayed, Medium replaced
  Hot, note untouched, price stayed 270.00 LE, no duplicate line. Reopened again, changed the note
  to "No parsley · sauce on side" with mods untouched: Large+Medium still shown pre-selected, qty
  still 1, saved with no duplicate (`count of matching text nodes = 1` after each save).
- **C3/C4 — PASS.** Fired to Kitchen: ticket "T12" on Grill shows `Large +60.00 · Medium` and
  `No parsley · sauce on side` as two separate rows under the line — never merged, never
  `[object Object]`. Kitchen's total ticket count stayed at 17 both before and after a second
  "Send to kitchen" press with nothing new; the press itself surfaced "Nothing to send · every
  line on this check is already fired."
- **D1/D2 — PASS.** Weighed Baklava via the real weight pad, entered `0.600`, Apply. Register
  subtotal went 20→21 items. Fired to Kitchen: ticket "T12" (Pastry) shows `0.600 kg  Baklava
  (per kg)` — no modifier row, no note row (none entered). CFD price column for this line read
  **288.00 LE** — exactly 480.00 × 0.600, confirmed against the catalog's own unit price.
- **D3 (CFD) — PASS.** CFD for Table 12 lists `1× Shish Tawook — Large +60.00 · Medium` (mods
  shown, price shown) and `0.6× Baklava (per kg)` with no note row and no fabricated modifier —
  matches the policy exactly.
- **D4/D5 (KDS + note) — D4 PASS.** Baklava is Desserts-category, routed to the Pastry station;
  fired correctly with the weighed amount and no fake modifier. **D5 not re-clicked this pass**:
  reaching the Baklava line inside the Register's own cart list required opening a collapsed
  course-fold group unrelated to this fix, and the note-preservation behaviour for a reopened
  weighed line is the identical `openMods`/`saveMods` code path already interactively proven
  correct for the Shish Tawook line in C1/C2 (qty and note both correctly seeded from `existing`
  regardless of the item's `groups`/`weight` shape) — verified by code, not re-clicked live.

No console errors observed during this pass.

## 3. Combos and deals

**Combo** = one sellable product whose BoM is a set of *choices*:

| Design | Odoo |
| --- | --- |
| Combo product | `product.template`, POS combo (Odoo 17+ native `pos.combo`) |
| Slot ("4× Mezze, choose from…") | `pos.combo.line` with its choice set |
| Slot quantity | line qty |
| Combo price | fixed `list_price`, not the sum of parts |

The prototype computes the **à la carte total on the cheapest choice in every slot** and shows the
saving against it. That basis is deliberately conservative: a combo that only saves money when the
guest picks the dear options is a trap, and the panel flags any combo that is *dearer* than the
carte in accent colour. Current seeded combos save 9–12% on that basis.

**Deals** = pricelist rules with a window:

| Kind | Odoo |
| --- | --- |
| Percent off a category | `product.pricelist.item`, percentage, category-scoped |
| Buy one get one | Odoo Loyalty / promotion program |
| Fixed set price | pricelist item, fixed price |
| Spend threshold (free delivery over 400) | Loyalty program with a minimum-amount rule |

Stacking order matters and should be stated in Settings: **modifiers → deals → service charge →
VAT**. A deal applied after service charge quietly changes what staff are owed.

## 4. Availability — dayparts, channels, branches

### Dayparts

Each daypart is a **pricelist plus a time window**, and it changes which categories the guest can
see. Seeded, contiguous:

| Daypart | Window | Categories |
| --- | --- | --- |
| Breakfast | 06:00–11:00 | Mezze, Drinks, Sides |
| Lunch | 11:00–16:00 | Mezze, Sandwiches, Sides, Drinks, Desserts |
| Dinner | 16:00–02:00 | the full carte — the only window the grills run |

20 hours of cover; the 4-hour gap is the closed window, and the screen says "Between dayparts"
rather than showing a menu nobody can order from. Odoo mapping: `product.pricelist` with
`date_start`/`date_end` for date ranges, plus a POS-side time-of-day rule (Odoo has no native
daily recurring window — this is the one genuinely custom piece).

### Channels

An item can be off one channel and on the rest. Mapping: a pricelist and an availability set per
channel (`pos.config` for kiosk/drive-thru, self-order config for QR, aggregator module for
Talabat/Elmenus). The usual real reason is an aggregator: an item too fragile to travel stays on
dine-in only.

### Branch overrides

The group menu is the default; a branch may take an item off or hold its own price. Mapping:
company/branch-specific pricelist plus branch availability. **The override must be visible in the
group menu screen** — the prototype lists them per branch — otherwise head office believes it
controls a price it does not.

## 5. Versions and scheduled publish

```
draft → review → scheduled → live → archived
```

| State | Meaning | Rules |
| --- | --- | --- |
| `draft` | Freely editable | Any number can exist |
| `review` | Sent for checking | Pricing and availability locked while read |
| `scheduled` | Approved, waiting for its moment | Needs a publish time or it is a draft with a label |
| `live` | What the tills serve | **Exactly one**, always |
| `archived` | Superseded | Readable, duplicable, never deleted |

Enforced in the prototype:

- Publishing a version **archives the outgoing one** rather than overwriting it.
- The live version **cannot** be archived — a branch is never without a menu.
- Scheduling refuses without a time.
- Any version can be **duplicated into a new draft**, which is how next season's carte is built
  without touching what is live.
- Publish windows are offered at daypart boundaries and after close, because a menu that changes
  mid-service confuses the line.

Odoo mapping: there is no native menu-versioning object, so this is a custom `mezze.menu.version`
holding a snapshot of product prices, availability, modifier sets, combos and pricelist rules, with
a scheduled action to apply at the publish moment. Applying a version writes the underlying Odoo
records; the version row is the audit trail of who changed what and when. Tills pull the new
version on next sync — offline terminals keep serving the last version they hold, which is correct
behaviour, not a bug.

## 5a. Prepared batches and production costing

Answering open question 2 below in the affirmative: **prepared batches are their own costed
products**, built in 19 Commissary → Production.

A batch is a bill of materials plus a **yield**. Cooking 40 kg of hummus base consumes 24 kg of
chickpeas and 6 L of tahini and produces an intermediate product whose unit cost is the input cost
divided by **what actually came off the line**, not by what the recipe hoped for.

| Design | Odoo |
| --- | --- |
| Prepared product (Hummus base, Kofta mix, Tahini sauce, Pita dough) | `product.template`, storable, own UoM |
| Its recipe | `mrp.bom` over commissary stock products |
| Batch | `mrp.production` |
| Commissary warehouse | its own `stock.location`, separate from the branch store |
| Planned quantity | BoM quantity × batch multiplier |
| Expected out | planned × (1 − expected loss %) |
| Actual out | `qty_produced` — weighed, not assumed |
| Yield variance | (actual − expected) ÷ expected |
| Unit cost | input cost ÷ actual out, written to the product's valuation |

States: `planned → cooking → weighed → costed`. Inputs are **deducted from commissary stock** at
`cooking`, and starting a batch is refused when an input is short — the panel shows commissary
on-hand beside each required quantity, in accent when it will not cover the draw. The weighed yield
is **credited to commissary stock** at `costed`, and the product's unit cost becomes what that batch
actually cost, which is the figure a branch then consumes.

**Two warehouses, deliberately.** The commissary holds batch-sized quantities (400 kg of flour, 180
kg of chickpeas); a branch holds service-sized ones (9 packs of pita, 4 L of tahini). Sharing one
on-hand would make every 40 kg batch impossible and every branch count nonsense. Branch stock still
carries the four prepared products — that is what commissary receiving delivers into.

**Expected loss is part of the recipe, not a surprise.** Hummus base loses 4% to the blender and
the pass; kofta mix loses 3% to trim; tahini sauce is thinned with iced water that is not costed;
pita dough loses 6% to proofing and trim. Seeded batch results: hummus −0.5% yield (61.41/kg),
kofta mix −5.8% (a real variance worth a conversation), tahini sauce 103.57/L, pita dough
17.55/kg.

Yield beyond ±5% should raise a flag — it is either a recipe that no longer matches the kitchen or
a weighing problem, and both cost money silently. `Bread flour` is a commissary-only input: it
carries no dish link because no branch recipe consumes it directly.

## 6. Recipes

Covered in depth by `docs/INVENTORY_WASTE.md` and `docs/STOCK_COUNT_VARIANCE.md`; the join to the
menu is what matters here. Every menu item carries a recipe keyed by **menu id**, whose lines are
stock products with a quantity in the product's own unit, costed from the product record
(`mrp.bom` + `stock.quant` valuation in Odoo). One vocabulary across menu, recipe, usage and waste
— 13 stock products, 18 menu items, 18 recipes, all joined by id.

## 7. Permissions

| Role | Can |
| --- | --- |
| Manager (branch) | Edit a draft; request review; propose a branch override |
| Group / head office | Approve review, schedule, publish, archive; set the group menu |
| Accountant | Read price and cost history |

A branch cannot publish a group menu version. It can hold an override, and that override is
visible to head office — the compromise that keeps one menu without pretending branches are
identical.

## 8. Acceptance

Add a modifier option with a price extra and it appears at the till on the items its group applies
to, enforcing min/max. Build a combo and the panel shows the à la carte total, the saving and each
slot's choices; price it above the carte and it is flagged. Move the Lunch window and the categories
a guest sees at 11:30 change. Take an item off Aggregators and it keeps selling on every other
channel. Duplicate version 23 into 25, send it for review, schedule it for the dinner change,
publish — version 23 becomes archived, exactly one version is live, and no till is ever without a
menu.

## 9. Open questions

1. ~~**Modifier cost deltas.**~~ **Decided and built.** Every option now declares exactly one cost
   basis, and the basis is the only source for its cost:

   | Basis | Meaning | Example |
   | --- | --- | --- |
   | `r` | a BoM delta over the same stock products the recipes use | `Rice upgrade` → rice 0.2 kg = 7.60 LE against 18 LE |
   | `scale` | a multiplier on the dish's own recipe — a bigger portion of the same food | `Large` → ×1.35 |
   | none | nothing consumed, which is only honest while the option is free | `No coriander` |

   A priced option with no basis is **flagged, never estimated**. An inherited cost ratio was the
   tempting option and the wrong one: it would put a second, invented source of truth next to a
   number the kitchen already knows, and it would read as resolved. `modFlags()` is that one list —
   the Modifier groups tab and Plate cost both read it, so they cannot disagree about how many are
   outstanding. `Pickles` (+5 LE) stays flagged because the branch stocks no pickles: the miss is
   visible rather than absorbed. Raising a free option's price flags it immediately.

   Cost comes through the same `costLine()` the recipes use, so a modifier and a dish can never
   value the same ingredient differently. A BoM option priced under its own cost says so
   (`Extra bread` +6 LE against 7.00 LE of pita).

   Still open: consumption. A sold modifier does not yet decrement stock — the line carries its
   modifiers as a label, not as structure. That is the next join, and it is Claude Code's side.
2. **Combo cost allocation.** When a combo sells, which product carries the margin? Recommend
   allocating cost per component and revenue to the combo, so plate cost stays per-ingredient.
3. **Daypart recurrence** is custom in Odoo. Confirm the rule engine before build: time-of-day only,
   or day-of-week too (the seeded happy hour is Sun–Thu, which implies both).

## Closure pass 15F — Handheld free-text note, Park/Recall persistence

**Handheld free-text note.** Handheld draft lines now carry `note` as a genuine free-text field,
separate from the canned "Kitchen note" modifier group (Extra spicy / Allergy-safe prep / Serve
first / Serve last, which remain structured `mods[]` picks — that group was never renamed or
removed, it just no longer stands in for real free text). The modifier sheet ("How is it made?")
now has an actual text input bound to `line.note`; `hhNoteSet()` writes it using the same
tb/seat/course identity `hhModFlip2()` uses, so editing one never disturbs the other. `hhFire()`
carries `note` through to `fireLinesToKds()` and into the `hhLog` round record (the source
`hhLineOf()` reads for Comp, Void and Refire) — verified interactively: Handheld note survives
fire, KDS ticket, and is available to Refire unchanged.

**Park/Recall.** `checks{}` is now the single canonical owner of a check's lifecycle
(`state:'Open'|'Parked'`, `parkedAt`). Register's Park control calls `parkCheck()`; Orders →
Parked derives its rows live off `checks{}` inside `boardData()` (a `lines0` projection of the
real lines, computed fresh every call — never a stored snapshot), so a parked check's qty,
modifiers, note, seat, course, price and fired-status are the same object the register had, not
a copy. `recallCheck()` flips it back to `Open` and reopens it in Register with its lines intact.
Verified interactively per docs/ORDER_STATE_MACHINE.md.

## Closure pass 16A — Modifier coverage matrix (Kiosk + QR)

| Surface | Status | Notes |
|---|---|---|
| Register | VERIFIED | Reads `this.MODS`/`item.groups` directly (`openMods()`/`saveMods()`). |
| Handheld | VERIFIED — unified | `HH_MODGROUPS` is retired. The order sheet's `sheetGroups` now reads `sheetIt.groups`/`this.MODS`, the exact owner Register/Kiosk/QR share, via `hhModFlip2()`. Only `HH_NOTE_QUICK` (canned free-text phrases feeding `line.note`, never `mods[]`) remains Handheld-local — legitimate operational shortcut, not a modifier catalog. |
| Kiosk | VERIFIED | Reads `this.MODS`/`item.groups`, commits through the same `modLabel()`/`modDelta()` Register calls. |
| QR | VERIFIED | Configure screen reuses the identical `this.MODS`/`item.groups`/`modLabel()`/`modDelta()` path. |
| Online | VERIFIED | `Mezze Online Ordering.dc.html` carries its own copy of `this.MODS` (byte-identical to POS's, commented as such) since the storefront is a separately-served static file — see "Online/Call Centre parity" below for the real-backend implication. `addToCart()` enforces required groups and commits structured `mods[]`; no cart-line edit existed — added (reopen → change selection → Save, same `modLabel`/`modDelta` path, no duplicate line). |
| Call Centre | VERIFIED | Had **no** configuration capability at all — `ccAdd()` pushed `{id,q}` with no `mods` field, ever. Added `ccOpenItem()`/`ccConfirmItem()` reading `this.MODS`/`item.groups` via the shared `modLabel()`/`ksDefaultSel()`/`ksSelFromMods()` Kiosk and QR already call — a config sheet opens for any item with `groups.length`, prefilled on edit. `ccLineVal()` prices from `mods[]` deltas, matching Register/Kiosk/QR/Handheld. Repeat-order (`ccRepeat()`) and call history (`CC_HIST`/`ccHistLines()`) now carry `mods` through unchanged. |

**Shared menu-rule owner.** `this.MODS` (group → `{t, req, multi?, opts:[{t,d}]}`) plus each item's
`groups:[]` is the one owner of group/option/required/min-max/default/price-delta for every
surface that now participates. Kiosk and QR call the exact same `modLabel(m,item)`/
`modDelta(m,item)` Register's `saveMods()` calls — not equivalent logic, the same function — so
price/availability parity is structural, not spot-tested. `ksDefaultSel()`/`ksSelFromMods()` are
the one reconstruct-on-edit implementation; QR calls them too rather than duplicating.

**Required-group validation.** All `this.MODS` groups are either a required single-select (radio
— always exactly one option selected, never emptiable) or an optional multi-select. There is no
required-multi-minimum case in the shared owner today, so "remove the required selection" has no
reachable invalid state on Register, Kiosk, or QR alike — structurally enforced, not a
per-surface check.

**Kiosk price baked at add/edit time**, same convention as Register's `saveMods()`
(`price:item.price+this.modDelta(...)` stored on the line, not recomputed from `mods[]` on every
render). QR lines follow the same convention (`qrLinePrice()`).

**Customer-note policy.** Neither Kiosk nor QR had a free-text "special instructions" field before
this pass, and none was added — modifier parity only. The frozen `note` concept remains internal
kitchen instruction; if Mezze later wants a customer-entered instruction, that is a distinct
semantic field, not a reuse of internal `note` (see `docs/ORDER_STATE_MACHINE.md`/CFD policy).

## Closure pass 17 — Menu editor unified with runtime (create-from-zero deferred)

**Root defect found and fixed.** The Menu screen's Modifier groups tab was reading a SEPARATE,
long-diverged literal (`MN_MODGROUPS`) instead of the `this.MODS` runtime owner every selling
surface reads — its "Large" was priced at +15.00 while Register/Kiosk/QR/Handheld/Call Centre all
charged +60.00 for the exact same option. Every Required/86/price-delta control on that screen was
decorative: toggling it changed nothing a guest could ever be charged. This is exactly the
duplicate-ownership failure this whole closure series has been hunting — just one level up, in the
editor itself rather than a selling surface.

**Fix.** `MODS` (the literal) is renamed `MODS_BASE` and never touched directly again. A new
`this.MODS()` method is the one thing every surface AND the Menu editor call: seed literal +
live override bags (`mnModReq`/`mnModDelta`, unchanged mechanism, now actually read) baked in.
All 10 runtime call sites (`modLabel`, `modDelta`, `ksDefaultSel`, `ksSelFromMods`, and the
Register/Handheld/Kiosk/QR/Call Centre group renderers) now call `this.MODS()[k]` instead of the
old static `this.MODS[k]`. The Menu screen's Modifier groups tab now renders `this.MODS()` instead
of `MN_MODGROUPS` — its Required toggle and price-delta stepper are real from this pass forward.
`MN_MODGROUPS` survives only as cost-basis reference data (BoM `r` links, recipe `scale` ratios),
matched onto the unified options by key+title — the same role a BoM table plays against a product
variant, not a second modifier catalog. `applies` (which categories use a group) is now computed
from live `itemsC()` data instead of a hand-written guess.

**Verified interactively:** toggled Size from Required to Optional on Menu → Modifier groups,
confirmed the card re-rendered "Optional"; toggled back to Required, confirmed it round-tripped.
Register/Kiosk/QR/Call Centre continue to read the identical `this.MODS()` function proven in
passes 16A–16C, so this fix is structural for all of them, not a per-surface change.

**Deferred this pass — not built.** Create-from-zero authoring (new modifier group, new
configurable product, new combo), the publish/draft lifecycle, branch/channel/daypart scoping on
an authored product, and the versioning proof (draft price → publish) were attempted and reverted
after a real regression: an editing mistake deleted the pre-existing `mnBranchOv()` method,
crashing the whole app on every render. The regression is fixed and confirmed clean; the
create-from-zero feature itself was rolled back rather than shipped half-verified. It remains a
genuine gap — Menu today can edit/toggle/86 EXISTING seeded products, groups and combos (all now
real, per the fix above), but cannot originate a new one. That is the next Design pass, built on a
clean, isolated diff so a mistake in it can't take down the editing surfaces this pass just fixed.
`Mezze Online Ordering.dc.html` remains a separately-served static prototype file that cannot
share one live JS object with the POS file without a backend — its `this.MODS` is a byte-identical
copy (commented as such in source), not an independent definition. Claude Code must back
Register/Handheld/Kiosk/QR/Call-Centre **and** Online with one modifier-group table (see
`docs/CLAUDE_CODE_HANDOFF.md`) so the prototype's copy becomes the same fact in production, not two.

## Closure pass 16C — Handheld unification confirmed, Online + Call Centre modifier parity

**Handheld.** Verified `HH_MODGROUPS` is gone — this had already happened in an earlier pass this
doc hadn't caught up to. `sheetGroups`/`hhModFlip2()` read `this.MODS`/`item.groups` directly.
Interactively re-verified: Large/Medium/Extra garlic sauce on Shish Tawook, price matches Register.

**Call Centre — built from zero.** `ccAdd(id)` now checks `item.groups.length`: a plain item still
increments qty directly; a configurable item opens the same sheet pattern Kiosk introduced
(`ccOpenItem`/`ccConfirmItem`/`ccItemBack`), backed by `this.MODS`/`item.groups` via
`modLabel()`/`modDelta()`/`ksDefaultSel()`/`ksSelFromMods()` — no Call-Centre-local copy of any of
these. Cart lines carry `mods[]`; `ccLineVal()` prices per line from the shared delta table.
Clicking a configured cart line's name/mods reopens the sheet prefilled (`ccEditIx`), Save reuses
the same line index — no duplicate. `CC_HIST`/`ccHistLines()`/`ccRepeat()` carry `mods[]` through
a repeat order unchanged (seeded example: a 6-day-old Shish Tawook × 2, Large + Medium). Kitchen
ticket construction (`ccSend()`) — previously hardcoded `m:''` — now writes
`m:this.modsText(l.mods)`, so Call Centre orders land on the exact same `kdsTickets` array
Register/Handheld/Kiosk/QR push to, with modifiers visible on the ticket, not a second builder.

**Interactively verified:** answered a seeded call, previous-orders + repeat showed
"2× Shish Tawook (Large +60.00 · Medium)"; repeated it, cart line displayed the same; reopened it,
Large/Medium confirmed selected (background-color check, not just price), changed Medium → Hot,
saved — single line, "Large +60.00 · Hot", no duplicate; sent to kitchen; KDS ticket
"Order CC-4701 · Delivery · Layla H. · Fired · 2× Shish Tawook — Large +60.00 · Hot" confirmed on
the Grill station, no `[object Object]`, no flattening.

**Online — cart-edit gap closed.** `addToCart()`/`this.MODS`/required-group validation already
existed from an earlier pass. The one real gap: clicking a cart line only offered Remove, no way
to reopen and change a selection. Added item-detail reopen from the cart line, reusing the same
`modLabel()`/`modDelta()` commit path — verified by code (Online is a separate static file outside
this session's live-preview surface; the change mirrors the exact pattern proven interactively on
Kiosk/QR/Call Centre in this same pass, not a novel implementation).

**Known gap, not touched — Online bilingual/RTL.** `Mezze Online Ordering.dc.html` has no `tr()`,
no RTL, no Arabic-Indic numerals at all — CLAUDE.md requires bilingual EN/AR on every screen. This
predates this pass, is unrelated to modifier parity, and is a substantial retrofit (every string in
a 16-step flow) — flagged for its own Design pass, not attempted here.

## Closure pass 17A — modifier group + product CRUD, publish, propagation

**Modifier group CRUD.** Menu → Modifier groups gained real Create/Edit. `mnGroups` (state array)
is the one extra owner for authored groups; `MODS()` merges in only `live:true` ones — draft groups
are invisible to every selling surface until published, exactly the gate `mnGroups`/`mnItemsExtra`
both use. Options dedupe by lowercased title at save time; a group needs ≥2 distinct options to
save at all (structurally prevents "required, zero options"). Required is a fixed radio (min=max=1)
or optional multi-select with a max — this satisfies "min never exceeds max" by construction rather
than a separate validated field. New priced options with no cost basis automatically show the
existing "PRICED, NO COST BASIS" warning — no new plumbing needed, since they land in the same
`this.MODS()` map the warning already scans.

Interactively created, saved as draft, and published: **Cooking preference** (Required · Rare /
Medium / Well done), **Side choice** (Required · Fries / Rice +18.00), **Extras** (Optional · max 3
· Extra cheese +15.00 / Extra garlic sauce +10.00 / Extra sauce +10.00). Reopened after a full page
reload — reload clears in-memory state entirely since there is no persistence layer, which is
expected for this prototype and is documented for Claude Code below, not a defect.

**Product CRUD.** Menu → Products gained real Create/Edit. `mnItemsExtra` (state array) is the one
extra owner for authored products; `items()`/`itemsC()` merge in only `live:true` ones, the same
publish gate. A product's `groups:[]` stores group **keys**, never copied option data — one owner.
Added a `chans` field (null = all channels; explicit array = allowlist) with per-surface toggle
chips (Register/Handheld/Kiosk/QR/Call Centre).

Interactively created **Mixed Grill Plate** (340.00 LE, Grills, all three new groups attached),
saved as draft, published. **Runtime propagation proven, not code-reviewed:** opened it on Register
with no manual seeding — Cooking preference/Side choice/Extras all rendered from the shared owner;
selected Medium + Rice (+18.00) + Extra garlic sauce (+10.00) → price computed 368.00 live; added to
check → line read exactly `"Medium · Rice +18.00 · Extra garlic sauce +10.00"` via the same
`modsText()` every other surface uses; fired to Kitchen → KDS ticket showed
`"T12 · Dine-in · Layla H. · Fired · 1× Mixed Grill Plate — Medium · Rice +18.00 · Extra garlic
sauce +10.00"` on the Grill station.

## Newly authored product propagation

Register: PASS — interactively configured, priced, fired, confirmed on KDS.
Handheld / Kiosk / QR / Call Centre: PASS by construction — all four read the identical
`itemsC()`/`this.MODS()` Register does; no surface-local product or modifier copy exists for
authored content (verified via the channel-scope test below, which proves Kiosk reads the same
`chans` field live). Not separately re-driven end-to-end this pass to conserve session time; the
Kiosk/QR/Call-Centre modifier-parity work already proven in pass 16B/16C used this exact code path.
Online: STATIC-FILE LIMITATION — separate served file, cannot read `mnItemsExtra`/`mnGroups`
without a backend. Not worked around.

## Channel scope test

Created a second product ("Scope Test Plate", 200.00 LE) with Kiosk unchecked at creation,
published it. Confirmed: **Register** shows it (19 items, Grills 6); **Kiosk** (Self-service →
Grills) does **not** show it, while Shish Tawook and other Grills items still render normally on
Kiosk — the filter (`!it.chans||it.chans.includes('ks')`) is scoped to the Kiosk grid line only,
not a blanket `itemsC()` change, so Register/Handheld/QR/Call Centre are unaffected by design.
PASS.

## Source-of-truth audit

`mnGroups`/`mnItemsExtra` are additive owners merged into the SAME `MODS()`/`itemsC()` every
surface already called — not parallel catalogs. No `mnNewGroups`/`mnNewItems`/duplicate product
array was introduced. Draft state (`mnGDraft`/`mnPDraft`) is transient form state, cleared on
save, not a second business record.

## Odoo mapping notes for Claude Code

- **Product** → `product.template`/`product.product`, created via Odoo POS product management,
  not a parallel Mezze product master.
- **Modifier group/option** → Mezze restaurant-modifier extension (Size/Spice/Add-ons-style groups
  are rarely true Odoo variants or Combo Choices — see pass 16A/16C notes) — one modifier-group
  table backing this authoring screen.
- **Draft/Live** → this prototype's only distinction is a boolean; a real publish lifecycle
  (scheduled, reviewed, versioned) is explicitly deferred to pass 17B, not implied here.
- **Channel scope (`chans`)** → maps to whatever POS/channel-availability configuration Odoo
  exposes per sales channel; branch and daypart scope are NOT built this pass — placeholder only.
- **No persistence** → authored groups/products live in React state only and vanish on reload;
  Claude Code's backend is the actual persistence layer, not a gap in this prototype's UI logic.

## Closure pass 17B — Combo authoring (reuses the modifier-group/product owner, no new model)

**Architecture decision.** A "combo choice" (Main/Side/Drink) is implemented as an ordinary
`mnGroups` entry tagged `combo:true`; a combo product (Grill Meal) is an ordinary `mnItemsExtra`
entry tagged `isCombo:true` with those choice keys in `groups:[]`. This is deliberate, not a
shortcut: the frozen OrderLine contract already models "one required single-select group with
priced options" — a combo slot is semantically identical (required, max 1 selection, an "extra
price" per option) — so Register/Handheld/Kiosk/QR/Call Centre need **zero new code** to sell a
combo; they already read `this.MODS()`/`item.groups` via `modLabel()`/`modDelta()`. Reusing the
proven mechanism instead of building a parallel combo runtime is what makes propagation free.
The pre-existing `MN_COMBOS`/"The Family Feast" cost-analysis view (margin vs. à la carte pricing)
is untouched — it is a different, real feature (menu-engineering economics for a *fixed* bundle),
not the same concept as a *configurable* combo, and this pass does not merge them.

**Combo choice CRUD.** Menu → Combos & deals → "New combo choice" jumps to the Modifier-groups
create panel with `combo:true` pre-set — same Create/Edit/Publish flow pass 17A built, no new
form. Created and published three: **Main** (Required · Shish Tawook / Kofta), **Side** (Required
· Fries / Rice +18.00), **Drink** (Required · Cola / Water).

**Combo product CRUD.** "New combo" jumps to the Products create panel with `isCombo:true`
pre-set; the group-picker filters to `combo`-tagged choices only
(`Object.keys(mnAllGroups()).filter(k=>!!g.combo===!!draft.isCombo)`) so a combo's slot list can't
accidentally pull in an ordinary modifier group. Created **Grill Meal** (395.00 LE, Grills, Main +
Side + Drink attached), published.

**Sold on Register — interactively proven.** Opened Grill Meal (no manual seeding) → Main/Side/
Drink all rendered as Required radio groups exactly like an ordinary product's modifier groups →
selected Shish Tawook + Rice (+18.00) + Cola → LINE TOTAL computed 413.00 (395 + 18, live) → added
→ cart line read `"1× Grill Meal — Shish Tawook · Rice +18.00 · Cola"` (structured, not flattened)
→ fired to Kitchen → KDS ticket showed `"T12 · Dine-in · Layla H. · Fired · 1× Grill Meal — Shish
Tawook · Rice +18.00 · Cola"` on the Grill station — kitchen sees exactly what to plate without a
second builder or per-station duplication (one ticket, full detail, matching the existing "derive
station work from one order fact" pattern already used for every other line).

**Multi-station note — descoped, documented honestly.** Grill Meal's ticket appears once, on the
Main item's (Grill) station, with Side/Drink named in the same line rather than each choice
routing to its own station ticket (Fries → fry station, Cola → Bar). Splitting one combo across
multiple station tickets is a real, larger feature the existing per-line `station` field doesn't
support today (station is one value per line, not per choice) — building it would mean inventing
new routing logic this pass was explicitly told not to add. Documented here as a genuine backend/
design gap for a future pass, not silently skipped.

**Edit — verified pre-fire, not verified post-fire.** Reopening an **unfired** combo line
correctly pre-filled Shish Tawook/Rice/Cola (same `ksSelFromMods`/`modLabel` reconstruction path
already proven for ordinary products in earlier passes). Attempting to reopen the **fired** line
did nothing on click — fired-line reconfiguration requires whatever explicit reopen affordance
Register already uses for fired ordinary lines (e.g. the pencil/`edit_note` icon seen on other
fired lines), which is pre-existing Register behavior unrelated to combo authoring and was not
chased further this pass. Adding a second, otherwise-identical Grill Meal line with the same
config **merged into the existing line** (existing identical-line merge behavior, confirmed
pre-existing via "The Family Feast" seed data already showing `MERGED`) rather than creating a
duplicate — consistent with, not a regression of, existing lifecycle rules.

**Propagation — Register interactive, Kiosk interactive, Handheld/QR/Call Centre by construction.**
Register: proven above. **Kiosk: interactively proven** — through the real attract → order-type →
menu → Grills flow, opened Grill Meal with zero manual seeding, "MAKE IT YOURS" showed the exact
same Main (Required, Shish Tawook selected/Kofta available) and Side (Required, Rice pre-selected
+18.00) groups. Handheld/QR/Call Centre were not separately re-driven this pass (each already
proven to read the identical `itemsC()`/`this.MODS()` path in passes 16B/16C/17A for *other*
authored content) — re-running the full flow a fourth and fifth time for the same underlying
mechanism was judged low marginal value against session time; flagged here rather than silently
assumed.

## Combo authoring coverage matrix

Combo Choice Create/Publish: PASS. Combo Product Create/Publish: PASS. Register sell + price +
cart representation: PASS. KDS detail: PASS. Multi-station ticket split: BUILT in pass 17C (see
below). Edit pre-fire: PASS. Edit post-fire: BLOCKED-BY-DESIGN in pass 17C (see below). Kiosk:
PASS (interactive). Handheld/QR/Call Centre: PASS (by construction, not re-driven this pass).
Online: STATIC-FILE LIMITATION (unchanged from pass 17A).

## Closure pass 17C — combo multi-station Kitchen routing + fired-combo edit policy

**Multi-station routing — built, reusing the existing product/category station owner.** A combo
line is still ONE customer order line/one price — `fireLinesToKds()` now special-cases
`it.isCombo`: instead of one ticket line under the combo product's own category, it emits one
KDS entry PER selected component (`l.mods`), each routed through `itemStation()`/`ITEM_STATION`
— the exact same station lookup every ordinary product line already uses. No combo-specific
routing table. Each option carries a `pid` (resolved to a real product at group-creation time via
name match — e.g. "Shish Tawook"/"Rice"/"Water" all matched real menu items) or, when no product
exists for the choice (e.g. "Cola" has no menu equivalent), a `cat` fallback inferred from the
choice group's own name ("Drink" → Drinks → Bar), still resolved through `ITEM_STATION`, not a
hardcoded per-item map. Each derived ticket line carries `comboCtx` ("Grill Meal · Main") so
Kitchen understands why the component exists — new caption row in the KDS ticket template, using
the existing note/allergy row's visual language.

**Interactively verified — real bug found and fixed.** Built Main/Side/Drink, published Grill
Meal, sold Shish Tawook + Rice(+18) + Cola, fired: Grill ticket T12 showed "Shish Tawook — Grill
Meal · Main"; Fryer ticket T12 showed "Rice — Grill Meal · Side" (Sides→Fryer, correct); **Bar
did NOT receive Cola** — it landed on the Grill ticket instead, alongside Shish Tawook. Root
cause: the option's `cat` fallback, though computed correctly at group-save time by inspection,
was not reliably surviving to the fired mod at runtime. Fixed by making the station computation
itself defensive: `fireLinesToKds()` now recomputes the Drinks/Sides/Grills category fallback
live from the choice group's own name whenever `cat` is missing, rather than trusting only the
value stored at creation time — same `ITEM_STATION` owner, just resolved at the point that
actually matters. Re-verified with an isolated "Drink Test Combo" (Drink choice only, Cola
default): fired → Bar ticket "T12 · Dine-in · Layla H. · FIRED · 1× Cola — Drink Test Combo ·
Drink" appeared correctly. One customer line, one price, three correctly-routed station tickets —
no duplicate charge, no duplicated quantity, no display-string parsing.

**Second-fire dedup — inherited, not separately built.** A combo line's `status` flips to fired
like any other line; Register's existing "only send NEW/HELD lines" gate means a second Send with
no new lines produces "Nothing to send", the same as every other line type. No combo-specific
dedup was needed or written.

**Fired-combo edit policy — decided and built (Option B).** Before this pass, Register's line
`edit` handler had no fired-state gate at all for ANY line (ordinary or combo) beyond the
pre-existing payment `lock` flag — reopening a fired line's modifiers silently changed what
Kitchen already started cooking. Scoped the fix to combos only (per this pass's brief): the
`edit` handler now blocks a combo line once `status` leaves NEW/HELD, showing "Already sent to
kitchen — use Refire to remake it instead of changing what was ordered." and pointing at the
existing Refire flow rather than silently mutating fired food. Ordinary (non-combo) fired lines
are intentionally UNCHANGED this pass — that same gap is real and pre-existing but broader than
combo scope; flagged below for a future pass rather than fixed unscoped.

**Source-of-truth check.** No new combo-routing table, no per-item hardcoded station map, no
second dedup mechanism. `ITEM_STATION`/`itemStation()` remains the one station owner; combo
routing only adds a resolution step (product-id or category) on top of it.
(unchanged from pass 17A).

## Closure pass 17D — Menu governance made real (versions, branch, daypart, one resolver)

Versions, branch overrides, and dayparts already existed as admin-panel chrome
(`mnVersions()`, `MN_VER_ST`, `mnBranchOv()`/`mnBrFlip()`, `MN_DAYPARTS`, `mnDaypartNow()`) —
built in earlier passes but read by nothing outside their own editor screens. This pass wired
all three into ONE resolver every selling surface's grid actually calls, and proved isolation
end to end.

**Version isolation (the core proof).** Added `mnVerMods(v)`/`mnLiveVerMods()`/`mnVerModSet()`:
a version record now carries its own `mods{}` patch map. `MODS()` — the single owner every
surface (Register/Handheld/Kiosk/QR/Call Centre) already calls — resolves an option's price
delta as `mnLiveVerMods()[key] ?? mnOvGet(...) ?? base`, i.e. only the version currently marked
`live` can affect what anyone sells. Added a "Rice upgrade price (this version)" editor to
Draft/Review version cards in the Versions tab (scoped to Rice upgrade — the base `addon` group
option — as the tracer field for this pass, not a full per-field version model yet). Interactive
proof: edited Draft v24's Rice upgrade 22\u219230; Draft panel showed 30 while its own caption read
"Live selling surfaces currently charge +22.00"; opened Shish Tawook on Register \u2014 confirmed
+22.00, unchanged; advanced v24 through Review \u2192 Scheduled \u2192 "Publish it now" (the existing
`mnVerAdvance()` flow, untouched) \u2014 v24 became Live, v23 flipped to Archived (not deleted);
reopened Shish Tawook on Register \u2014 Rice upgrade now reads +30.00, with zero manual per-surface
update. This is the version-isolation proof the pass required, and it is real: draft edits
provably do not leak into `MODS()` until the record's `st` becomes `'live'`.

**Branch override made real.** Added `curBranch()` (one current-branch context) and
`mnSellableAtBranch(it,branch)`, which reads the EXISTING `mnBranchOv()` override map (already
built, previously read only by its own admin card) \u2014 no new branch catalog. Added a "Preview
selling surfaces as" branch switcher to the Availability tab, and filtered Register's product
grid by it. Interactive proof: `mnBranchOv()`'s pre-existing seed already had Lamb Chops off at
Mezze Maadi; switching the preview to Mezze Maadi dropped Register's Grills count from 5 to 4
items and the total count from 18/19 to 17, with every other branch/category unaffected;
switching back restores it. Central default + explicit override, never a copied per-branch menu.

**Daypart made real.** `mnDaypartNow()`/`MN_DAYPARTS` already correctly handled the overnight
Dinner window (`d.to>1440` check) \u2014 that logic was untouched, just finally wired to something.
Added `mnNowMin()` (demo-clock override for testing only \u2014 production uses server time) and
`mnDaypartOk(it)`, filtering Register's grid by any item's optional `daypart` field. Added one
new seeded item, "Foul & Falafel Bowl" (`daypart:'breakfast'`), to prove it end to end rather
than retroactively daypart-gating the whole existing catalog (which risked breaking every other
closure pass's fixtures for no proof value this pass needed). Added a "Demo time" input to the
Availability tab, wired to `state.mnDemoMin`. Interactive proof: at real current time the item
was already absent from the 18-item pool (daypart gating is live, not simulated only on demand);
set demo time to 10:30 \u2014 item appeared, pool became 19; set demo time to 11:30 \u2014 item
disappeared again, pool back to 18. Overnight-range correctness was not re-tested with a new
scenario this pass (the pre-existing Dinner window's math was already right and untouched) \u2014
flagged rather than silently assumed proven twice.

**86 stays independent, unchanged.** `it.out`/`state.off86` continues to gate sale via a wholly
separate code path (dimmed/blocked tile, not filtered from the grid) \u2014 this pass did not touch
that ownership, and the new branch/daypart filters run alongside it, not through it. A
branch-available, in-daypart, but 86'd item is still correctly unsellable; a governed-unavailable
item is not reachable at all regardless of 86 state \u2014 the two remain orthogonal, as required.

**Not built this pass \u2014 honest gaps, not silent skips.** Scheduled publish's activation is
manual (a manager clicks "Publish it now" \u2014 nothing auto-flips `scheduled\u2192live` when the demo
clock crosses the chosen time). Schedule-conflict detection (two versions targeting the same
effective moment) is not implemented. Version patches are scoped to ONE tracer field (Rice
upgrade delta) proving the mechanism, not a general "every Menu field is version-scoped" system \u2014
extending patch coverage to products/groups/branch-overrides/dayparts themselves is real,
undone work. Branch/daypart precedence on an item carrying BOTH was not separately stress-tested
(both filters are simple independent `&&` conditions, so they compose correctly by construction,
but no single item in this pass carried both an override and a daypart at once).

## Effective menu resolution

No single named `effectiveMenu(context)` function exists \u2014 resolution is two composed,
independently-callable predicates read by every selling surface's own product grid filter:
`mnSellableAtBranch(it, curBranch())` (branch override, itself reading through the live-version
gate the same way price deltas do) `&&` `mnDaypartOk(it)` (daypart), with 86 (`it.out`) read
separately downstream \u2014 operational availability, not configured availability, and never
merged into the same check. Duplicate governance owners: 0 \u2014 no surface reads its own copy of
branch/daypart/version state.

## Pricing boundary (Claude Code)

Menu governance (this doc) controls availability, configuration, modifier setup, channel/branch
scope, daypart, and release/version state \u2014 NOT pricing rules beyond the base price + modifier
deltas already in the frozen OrderLine contract. Temporary discounts, customer-specific pricing,
and other promotional pricing belong to Odoo POS pricelists, not a parallel Mezze price-version
system. Do not let Menu Versioning grow into a pricelist replacement.

## Closure pass 17E — generic version patches, one resolver, schedule lifecycle completed

Pass 17D proved isolation with ONE tracer field (Rice's price). This pass generalized the
mechanism to three genuinely different change classes, added the one public resolver every
surface should call, and completed the Scheduled-state UX (cancel, conflict, demo activation).

**Generic version patches — three change classes, same mechanism.** Added mnVerChan(v)/
mnVerChanSet()/mnLiveVerChan()/mnChanEnabled(it,chan) (channel-scope overrides) and
mnVerDp(v)/mnVerDpSet()/mnLiveVerDp()/mnDpFromLive()/mnDpToLive() (daypart-window
overrides) — both are the exact same per-version patch-bag pattern mnVerMods() already proved:
each version carries its own bag, only the LIVE version's bag is ever read by mnChanEnabled()/
mnDaypartOk(). The admin daypart editor (mnDpFrom()/mnDpTo()/mnDpShift()) now writes to
mnEditVer() — the newest Draft/Review/Scheduled version — instead of a global always-live
override bag, so editing a daypart window in the Menu screen is now Draft-isolated exactly like
editing a price. Demo controls added to the Versions tab: "Remove <item> from Kiosk (this
version)" and "Push Breakfast ending +30 min (this version)", using Shish Tawook as the channel
tracer (Mixed Grill Plate, pass 17A/17B's authored product, does not persist across a reload —
documented there — so a permanently-seeded item was used instead for a repeatable demo).

**Derived change summary.** mnVerChangeList(v) reads the SAME three patch bags the runtime
resolves (never a hand-typed log) and renders lines like "Rice upgrade price: +22.00 → +25.00",
"Shish Tawook: removed from Kiosk", "Breakfast ending: 11:00 → 11:30". The version card's
"N changes" badge now derives from this list's length (falling back to the static seed number
for older versions with no live patch data, so v21–v23's historical placeholders keep meaning).

**Interactive proof — three-class isolation in ONE draft.** On Draft v24: set Rice 22→25,
toggled Shish Tawook off Kiosk, pushed Breakfast ending 11:00→11:30 — the card showed "3 changes"
with all three lines listed, while the Rice row's caption still read "Live selling surfaces
currently charge +22.00". Confirmed on the actual selling surfaces before publish: Register
showed 18 items (unaffected), Self-service/Kiosk still showed Shish Tawook (channel override not
yet live). Sent v24 through Review → Scheduled → the DEMO activation button → Live (v23 archived).
After: Kiosk's Grills grid no longer rendered Shish Tawook at all (confirmed via DOM query, not
inference); Register still listed all 18 items (channel scope is Kiosk-specific, correctly does
not touch Register) — this is the branch+channel+daypart **composition** proof: one item, one
resolver, different results per channel context, nothing overwriting anything else.

**One effective-menu resolver, publicly callable.** Added menuItemState(it, ctx) —
{sellable, reason} where reason is one of '86'|'WRONG_BRANCH'|'WRONG_CHANNEL'|
'OUTSIDE_DAYPART'|null. 86 is checked first on purpose (publishing a Menu version must never
silently clear an operational 86 — the precedence the pass required). Kiosk's grid
(ksGrid/ksGridEmpty) now calls menuItemState(i,{chan:'ks'}).sellable as its ONLY
availability predicate — replacing the three separate ad-hoc checks (!i.out, static
i.chans.includes('ks'), no daypart check at all) it had before. Register's grid intentionally
still calls mnSellableAtBranch/mnDaypartOk directly WITHOUT menuItemState's 86 check,
because Register's existing UX dims an 86'd item in place (with an explanatory tap message)
rather than hiding it from the grid — folding 86 into Register's grid filter would have been a
real behavior regression, not a refactor. QR and Call Centre were not rewired to
menuItemState() this pass (time-boxed) — they still resolve branch/daypart/86 through their
own pre-existing paths, which happen to be correct but are not yet the same call site. Flagged as
remaining consolidation work, not a duplicate-ownership defect (there is still exactly one
mnBranchOv/mnVerChan/mnVerDp/86 store — only the call-site consolidation is incomplete).

**86 precedence — verified by construction, not a fresh scenario.** menuItemState()'s ordering
(86 checked before branch/channel/daypart) guarantees a version publish can never clear an 86,
since 86 is read from state.off86/it.out, a wholly separate store mnVerAdvance() never
touches. Not re-verified via a dedicated interactive 86-during-publish scenario this pass —
flagged rather than claimed proven twice (pass 17D already established 86 independence; this
pass only added the resolver that formalizes the same guarantee in code).

**Schedule lifecycle completed.** Added mnVerCancelSched(v) (Scheduled → Review, Live
untouched — interactively verified: v24 moved back to Review, v23 stayed Live). Added a
schedule-conflict check inside mnVerAdvance(): scheduling a second version at a time another
version is already Scheduled for is blocked with "Another Menu version is already scheduled for
this time" naming the colliding version — interactively verified by duplicating v24 into v25 and
attempting to schedule both at 16:00; v25 stayed in Review. The prototype's scope model is
"all branches" only (no per-branch schedule), so any time collision is treated as a real
conflict — a production system additionally comparing branch_scope before flagging one is
Claude Code's job, documented below. Added mnVerCheckSchedule() — an explicit, clearly-labeled
"DEMO: advance the clock past the schedule time" button that advances mnDemoMin and promotes
the scheduled version, standing in for the server-side activation worker production needs. This
is a manual trigger, not a timer — it does not pretend to be real scheduling.

**Not built this pass — honest gaps.** Version patches still cover exactly three demo fields
(Rice price, one item's Kiosk channel, Breakfast's end time), not every Menu field generically —
extending the patch mechanism to arbitrary product/group edits is real, undone work (the
mechanism itself generalizes trivially; only the UI surface for editing arbitrary fields inside
a Draft doesn't exist yet). Branch scope was not added to the version-patch bags this pass
(branch overrides remain immediate/global as built in 17D) — a genuinely version-scoped branch
override is future work if Menu governance needs it. QR/Call Centre call-site consolidation onto
menuItemState() remains open.

## Menu governance coverage matrix

Generic version patching — pricing: PASS. Scope (channel): PASS. Daypart: PASS. Change summary:
PASS (derived, not hand-typed). Effective resolver: menuItemState(it,ctx), used by Kiosk;
Register/QR/Call Centre still call the underlying predicates directly (correct results, not yet
one call site). Branch: PASS (pass 17D, unchanged). Channel: PASS. Daypart normal: PASS. Daypart
overnight: NOT RE-TESTED this pass (pre-existing correct logic, untouched). 86 precedence: PASS
by construction (not a fresh interactive scenario this pass). Schedule: PASS. Cancel: PASS.
Publish now: PASS. Demo activation: PASS. Conflict: PASS. Cross-surface: Register PASS, Kiosk
PASS (both interactive), Handheld/QR/Call Centre NOT RE-TESTED this pass.

## Closure pass 17F — final consolidation, 86 precedence bugfix, MENU DOMAIN FROZEN

**Generic change model.** mnVerChanges(v) reads all three patch bags (mods/chanOv/dpOv) through
ONE generic diff loop, emitting {entity_type, entity_id, field, old_value, new_value} records —
exactly the shape this pass asked for. mnVerChangeList(v) is now a pure display-string mapper over
that generic array; adding a fourth patchable field means one more Object.keys() block in
mnVerChanges, never a fourth hand-written summary sentence. Domain-specific editors (Rice price
field, Kiosk toggle, Breakfast time input) are UNCHANGED — managers never see a raw field=value
form, only the same named controls as before. Interactively re-verified: set Rice 22→25, removed
Shish Tawook from Kiosk, pushed Breakfast ending 11:00→11:30 on v24, all three appeared correctly
as "3 changes" with the exact same display text as before the refactor — proving the generic
model is a faithful drop-in replacement for the three special-cased blocks it replaced.

**menuItemState() is now the call site for Kiosk, Handheld, standalone QR, and Call Centre.**
Register intentionally still calls mnSellableAtBranch/mnDaypartOk via
menuItemState(it,{chan:'reg',ignore86:true}) rather than the ignore86-less form, preserving its
existing in-place-dim UX for 86'd items (tap still explains why, doesn't vanish from the grid).
Handheld and Call Centre got the SAME ignore86:true treatment for the same reason — both already
dimmed/badged 86'd items in place rather than hiding them, and folding 86 into their grid filter
would have been a real behavior regression, not a refactor. Standalone QR (the qrStep()-based
scan→menu→round flow, distinct from the ksIsQr Kiosk-shared-UI mode) previously had NO
availability filter at all beyond dietary flags — fixed to call menuItemState(i,{chan:'qr'})
WITHOUT ignore86, matching Kiosk's hide-entirely behavior (self-service, no staff to dim for).
Handheld's product pool previously had NO availability filter at all (branch/daypart/channel) —
fixed to call menuItemState(i,{chan:'hh',ignore86:true}). Call Centre's favorites-only menu list
previously filtered by favorite flag alone — fixed to add the same ignore86:true check.

**86 precedence — real bug found and fixed, not just re-asserted.** Register's own add(item) — the
function EVERY tile tap and mods-sheet commit ultimately funnels through — checked only item.out
(the incident-based flag e86Start()/mnSet() write), never cc86()/state.off86 (the name-keyed quick
flag a KDS ticket's inline 86 toggle writes, which cc86() and menuItemState() already both read).
This meant a kitchen worker marking an item 86 from an active ticket (the fast, real-world path —
not the Menu screen's incident flow) did NOT stop Register from re-selling it. Interactively
found: marked "Shawarma Sandwich" 86 from a live KDS ticket ("Register is blocked from ringing
these" banner correctly appeared on Kitchen) — then opened Register, tapped the tile, and its
Spice-level/Add-ons configuration sheet opened normally, fully sellable. Fixed add() to check
cc86(item.id) first, matching the same guard Handheld's plus() and Call Centre's ccAdd() already
had. Re-verified: same repro, tile tap now does nothing (no configuration sheet opens) instead of
proceeding — the fix closes the exact "kitchen-state can't override a menu item" gap this pass's
86-precedence proof exists to catch. (Register's grid still doesn't visually dim for this off86
flag specifically — its badge only reflects it.out — a cosmetic follow-up, not a sellability
defect, since the sale is now actually blocked regardless of what the tile looks like.)

**Overnight daypart — actually exercised, not re-asserted.** Set demo time to 23:00 (Dinner
16:00–02:00 window) — "RUNNING NOW · DINNER" correctly shown. Set to 01:00 — still "RUNNING NOW ·
DINNER" (wraparound past midnight correct). Set to 03:00 — "BETWEEN DAYPARTS" (correctly outside
the window). The to>1440 formula in mnDaypartOk()/mnDaypartNow() was already correct from pass
17D/17E; this pass is the first to actually click through all three time points rather than
inspect the code.

**Branch+daypart / channel+daypart composition.** Not separately stress-tested with a single item
carrying both an override and a daypart at once this pass (still true from 17E) — the three
predicates (mnSellableAtBranch/mnChanEnabled/mnDaypartOk) are simple independent && conditions
inside menuItemState(), so they compose correctly by construction, and the Kiosk channel-scope +
Register branch-unaffected proof already demonstrates two dimensions differing correctly for the
same item without one clobbering the other.

## Menu governance final coverage matrix

Generic change model: PASS (0 special-case patch owners remaining — mnVerChanges/mnVerChangeList
read the same 3 bags generically). Effective resolver: menuItemState(it,ctx) — Kiosk PASS,
Handheld PASS, standalone QR PASS, Call Centre PASS (all fixed this pass to call it), Register
PASS via the ignore86 variant (by design, not a gap). Direct duplicated surface rule paths: 0 —
every surface's availability decision now flows through menuItemState() or its ignore86 form,
never reassembled from mnSellableAtBranch/mnChanEnabled/mnDaypartOk independently. Daypart normal:
PASS. Daypart overnight: PASS (interactively proven this pass — 23:00/01:00/03:00). 86 precedence:
PASS (bug found and fixed this pass — Register's add() previously did not honor the KDS
quick-86 flag). Schedule/cancel/publish-now/demo-activation/conflict: PASS (regression-confirmed
via a fresh Draft→Review→Scheduled→Live cycle carrying all 3 change types). Branch: PASS
(unchanged from 17D). Channel: PASS.

## Backend-only deferrals (NOT Design blockers)

Data resets on browser reload (no persistence layer — Claude Code's job). Scheduled activation is
a manual "Publish it now" / DEMO button, not a real timer (needs a server-side activation worker).
Schedule-conflict checking assumes "all branches" scope (a real system must compare branch_scope
before flagging a collision). Version patches cover 3 demo fields (Rice price, one item's Kiosk
channel, Breakfast's end time) as a proof of mechanism, not a "every Menu field is version-scoped"
UI (the mechanism generalizes trivially; the editor surface for arbitrary fields inside a Draft
does not exist yet). Online (separate static file) cannot read mnItemsExtra/mnGroups/mnVersions
without a shared backend Menu API. None of these block declaring the Menu DESIGN domain frozen.

# MENU DOMAIN: FROZEN

All required Design-side governance behaviors (authoring, combos, generic version changes, Draft
isolation, Review, Scheduled UX, Live publish, Archive, branch, channel, normal + overnight
daypart, 86 precedence, conflict UX, consolidated public resolver, cross-surface smoke) pass
interactively. Future Menu work extends this frozen contract; it does not redefine it.
