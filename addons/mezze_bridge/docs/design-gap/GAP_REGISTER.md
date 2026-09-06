# Design → Odoo gap register

What the frozen Claude Design prototype (`Mezze POS v3.dc.html`) specifies, against what
`mezze_bridge` actually implements. One row per capability, each with evidence.

**Why this exists.** The design bundle ships its own
`IMPLEMENTATION-STATUS-RECONCILIATION.md`, but that maps only **BE-001–BE-020** — the design's
*backend join* list. The prototype froze whole domains that never appear on it (menu governance,
structured modifiers, combo authoring, loss categories, Call Centre, Handheld, multi-stage
production). Those cannot show up as "already built" because they were never asked about.

**Sources.** `design_handoff_mezze_pos/` in Claude Design project `4b9aa028`:
`CLAUDE_CODE_HANDOFF.md` (master index), `MEZZE_FINAL_FROZEN_AUDIT.md` (current state),
`domain-docs/*.md` (29 contracts).

**Verdicts.**

| Verdict | Meaning |
| --- | --- |
| `BUILT` | present and matches the contract's shape |
| `PARTIAL` | present but narrower than the contract |
| `ADAPT` | present in a different shape; needs reconciling, not rebuilding |
| `ABSENT` | no implementation |
| `N/A-BE` | blocked on credentials/hardware/a partner, not code |
| `UNVERIFIED` | not yet checked against its domain doc |

**Evidence discipline.** A keyword hit is a pointer, not a verdict. Anything marked `BUILT` or
`PARTIAL` on a grep alone is recorded as `UNVERIFIED` until read against its domain doc.

---

## 1. Menu engine — `MENU_ENGINE.md`

Design status: **MENU DOMAIN FROZEN** (closure pass 17F).

| # | Capability | Contract | Repo | Verdict |
| --- | --- | --- | --- | --- |
| M-01 | Modifier group / option model | dedicated model on `product.template`, ONE definition read by Register, Kiosk, QR, Handheld, Call Centre | no `modifier_group`/`mezze.modifier` model | `ABSENT` |
| M-02 | Structured `mods[]` on the order line | `[{g,t,p}]` — never a label string; `note` and `qty` stay independent fields | line notes exist; no structured selection store | `ABSENT` |
| M-03 | Required / min / max picks per group | POS-side rule; the doc states Odoo has **no native min/max** | no `min_pick`/`max_pick` | `ABSENT` |
| M-04 | Combo product + combo slots | slot = same modifier-group model tagged `combo:true`; maps to Odoo Combo product / Combo Choice | 2 keyword hits, unverified | `UNVERIFIED` |
| M-05 | Menu version records + audit history | versioned patches, **atomic** publish | no `menu_version` | `ABSENT` |
| M-06 | Server-side scheduled activation | prototype's activation is a labelled DEMO button; the worker is Claude Code's side | no scheduler | `ABSENT` |
| M-07 | Schedule-conflict enforcement incl. branch scope | prototype compares all-branches only; real system must compare `branch_scope` | — | `ABSENT` |
| M-08 | Stable option/group IDs surviving a label rename | prototype keys patches by `group\|option-label` | — | `ABSENT` |
| M-09 | Dayparts incl. overnight wraparound | `to>1440` proven at 23:00/01:00/03:00; backend likely UTC-normalised | no `daypart`; Odoo POS category Service Hours may cover part — **inspect before building** | `ABSENT` |
| M-10 | Channel availability | not an ad-hoc allowlist | 1 hit, unverified | `UNVERIFIED` |
| M-11 | Branch overrides | must reference Odoo's existing branch identities, not a second branch master | — | `ABSENT` |
| M-12 | ONE menu API serving POS **and** the storefront | two static files cannot share a runtime object | `/shop/menu` exists; not reconciled with the till menu | `PARTIAL` |
| M-13 | Pricing boundary | availability/version/scope = Menu; promotional/customer pricing = Odoo pricelist. Do not fold Menu governance into pricelists | — | `ABSENT` |
| M-14 | Station routing per product | custom field → KDS station | `station_id` present | `UNVERIFIED` |

## 2. Kitchen production — `KITCHEN_PRODUCTION_ENGINE.md`

| # | Capability | Contract | Repo | Verdict |
| --- | --- | --- | --- | --- |
| K-01 | One KDS ticket builder | `fireLinesToKds()` — every surface calls it, second-fire dedup by open ticket + `checkRef` | `kds_ticket.py` exists | `UNVERIFIED` |
| K-02 | `mods` + `note` as two independent ticket fields | never flattened into one string | depends on M-02 | `ABSENT` |
| K-03 | Multi-stage production | Frozen→Thaw→Prep→Cook→Hold→Pass; **forward only**; person + time per stage | no stage model | `ABSENT` |
| K-04 | Thaw/Hold timed stages gating availability | doc: one of two things "Odoo will not do out of the box" | — | `ABSENT` |
| K-05 | Hold expiry → waste | expiry is a waste record, never "still there" | lot expiry hits exist | `UNVERIFIED` |
| K-06 | Availability reads the stage chain | lets 86 be **predicted** rather than discovered | — | `ABSENT` |
| K-07 | Forecast prep board | `expected − prepared − in-production`, floored at 0, **rounded up to batch size**; Required derived never typed; basis stated | no forecast model | `ABSENT` |
| K-08 | Per-station forecast split | open in the prototype too | — | `ABSENT` |
| K-09 | Batch production w/ real yield cost | unit cost = real input ÷ real output; variance posted | `mrp.production`/`mrp.bom` hits | `UNVERIFIED` |
| K-10 | Batch assignment gates start | an unassigned batch is the one nobody starts | — | `UNVERIFIED` |
| K-11 | Combo line → per-component station tickets | one customer line, one price, N ticket entries | depends on M-04 | `ABSENT` |
| K-12 | Fired-line amendment rule | a fired line is historical instruction; a qty increase creates NEW demand | 1 hit, unverified | `UNVERIFIED` |

## 3. Call centre — `CALL_CENTER.md`

Design status: built as screen 33. **The engines it reads already exist here** — the gap is the
agent surface, not the machinery behind it. The doc is explicit that the call centre "decides
nothing on its own"; it is a client of the same guest record, menu, zone map, payment registry and
order board.

| # | Capability | Contract | Repo | Verdict |
| --- | --- | --- | --- | --- |
| C-01 | Zone fee / minimum / free-over / promise | the SAME `ORD_ZONES` the storefront reads | S3 delivery zones | `BUILT` |
| C-02 | Prep buffer, one per channel | phone cannot promise what the web would not | present | `BUILT` |
| C-03 | Caller lookup on `res.partner` | never a second guest database | `_kiosk_partner` searches `phone` | `PARTIAL` — reuse, not a CC lookup |
| C-04 | Saved addresses as child delivery partners, zone-tagged | a free-text address with no zone is the failure | present | `UNVERIFIED` |
| C-05 | Payment methods filtered to the `call` surface | Cash/Card/Wallet/Loyalty/House only | registry exists, no `call` surface | `PARTIAL` |
| C-06 | Branch routing: open **and** serving the zone | "the call is taken by a branch that cannot cook it" | partial | `UNVERIFIED` |
| C-07 | Send → ONE order on the shared board + one KDS ticket per station | real lines, fee as a **line** not prose, VAT-inclusive quote | order board + KDS exist | `UNVERIFIED` |
| C-08 | Repeat last order re-priced at today's menu | never yesterday's prices | — | `ABSENT` |
| C-09 | Agent queue / call log / handle time / abandoned | "an abandoned call is a record" → call-back list | no call model | `ABSENT` |
| C-10 | Every refusal names itself before Send | closed branch, unserved zone, 86, under minimum | — | `ABSENT` |
| C-11 | Minimum shown as a gap ("40 more"), not a rejection | a rejection at the end of a call is a lost order | — | `ABSENT` |
| C-12 | Modifiers on the call | open in the prototype too; needs M-01 | depends on M-01 | `ABSENT` |
| C-13 | CTI / recording / consent / outbound | explicitly "designed here, not built" | — | `N/A-BE` |

**Read:** the Call Centre is a thinner gap than it first looks — C-01, C-02, C-05, C-07 rest on
engines already shipped. What is genuinely missing is the call record (C-09), the refusal surface
(C-10/C-11) and Repeat (C-08).

## 4. Refire costing — `REFIRE_COSTING.md`

Principle: a refire is **two events**. The kitchen issues ingredients a second time and the
original plate is thrown away. "A refire that only reprints a ticket loses the entire cost of the
incident." Nothing is charged to the guest; the only money that moves is stock leaving the branch.

| # | Capability | Contract | Repo | Verdict |
| --- | --- | --- | --- | --- |
| R-01 | `mezze.refire` incident record | original line, dish, reason, owner, station, employee, table, derived cost, timestamp — "the record the reports read" | no model | `ABSENT` |
| R-02 | 8 fixed reasons, each carrying owner **and** waste category | so the two "can never be set inconsistently" | — | `ABSENT` |
| R-03 | Reason pre-selects station; override allowed | default is a suggestion, not a lock | — | `ABSENT` |
| R-04 | `Not attributable` as a first-class answer | forcing a station corrupts station reporting | — | `ABSENT` |
| R-05 | Cost = recipe cost, **per BoM line** | per-ingredient, never a lump sum, or plate cost cannot attribute variance | BoM cost helper exists | `PARTIAL` |
| R-06 | No recipe → "cost cannot be derived" | "zero would read as free" | — | `ABSENT` |
| R-07 | Remake line at **zero price** linked to the original | revenue must not double-count | 1 hit, unverified | `UNVERIFIED` |
| R-08 | Discarded plate → `stock.move` per component to waste location | same ledger as a manual write-off | native `stock.scrap` + reason tags | `ADAPT` |
| R-09 | Refire needs **no** manager PIN | blocking it delays the guest's food; control is after-the-fact reporting | — | `ABSENT` |
| R-10 | Refire cost reported **next to** waste, not inside it | same account, separately reportable — the management action differs | — | `ABSENT` |
| R-11 | KDS prints the remake marked, with its reason | so the line knows why it is cooking again | — | `ABSENT` |

## 5. Loss accounting & plate cost — `INVENTORY_WASTE.md`, `COMP_ACCOUNTING.md`

| # | Capability | Contract | Repo | Verdict |
| --- | --- | --- | --- | --- |
| L-01 | Waste as real stock movement | on-hand drops, loss books through inventory | native `stock.scrap` + `stock.scrap.reason.tag` | `BUILT` |
| L-02 | Loss category as a **stored enum** | 6 values: `COMP`, `REFIRE_REMAKE`, `WASTE_DISCARD`, `SPOILAGE`, `OVERPRODUCTION`, `RECOVERY_SUBSTITUTION`. Handoff: "a real backend should carry this as a stored enum column, **not a string match**" | reason *tags*, no category column | `ADAPT` |
| L-03 | Plate cost aggregating the three ledgers | `lossCatTotals()` over comp/refire/waste and only those | no plate-cost aggregation | `ABSENT` |
| L-04 | Per-ingredient variance attribution | why R-05 must be per-line | — | `ABSENT` |
| L-05 | Comp posts to its own ledger, manager-approved | audited apart from discounts | `order.comp` present | `UNVERIFIED` |
| L-06 | 86 is **not** a financial event | only the chosen comp/refund/waste consequence posts cost; the availability flag alone never does | — | `UNVERIFIED` |
| L-07 | Recovery record **references** the comp/refund/refire it caused | never owns its own copy of the cost | no recovery model | `ABSENT` |
| L-08 | Recovery substitution pricing | frozen MEZZE POLICY: `charge = min(original, replacement)` — not a native POS exchange | — | `ABSENT` |

## 6. Arrival queue — `ARRIVAL_QUEUE.md`

Principle: a booking, a walk-in and a seated party are **the same event at different stages**. One
queue, derived from all three, living inside Floor. "A host who has to switch screens to decide
where a party goes will guess instead."

| # | Capability | Contract | Repo | Verdict |
| --- | --- | --- | --- | --- |
| A-01 | One derived queue over bookings + walk-ins + seated | never a fourth place arrival state lives; every action writes back to its source | reservations and waitlist are separate | `ABSENT` |
| A-02 | Six stages, **derived never stored** | `aqStage()` = source state + clock + floor | states exist per-model | `PARTIAL` |
| A-03 | Ready-to-seat requires a table at `Ready` | not one still `Needs clearing` — "how a party gets walked to a dirty table" | table state exists | `UNVERIFIED` |
| A-04 | Late ≠ No-show; no-show is a **person's** decision after 25 min | releasing a table is a commercial choice | — | `ABSENT` |
| A-05 | Seat now takes the **smallest** clean table that fits | least waste, not first found | 2 hits | `UNVERIFIED` |
| A-06 | Quoted-vs-actual wait on the record | "the number the host is judged on" | 2 hits | `PARTIAL` |
| A-07 | Computed wait quote from turn time + parties ahead | **open in the prototype too**; `flTurnAvg()` exists there, unused | no turn-time average | `ABSENT` |
| A-08 | Ready-to-seat notification (SMS/WhatsApp) | **open in the prototype too**; BE-016 | marketing channel exists, not wired | `ABSENT` |
| A-09 | Walk-in modelled as a booking made at the door | "what lets one queue exist at all" | separate waitlist model | `ADAPT` |
| A-10 | Horizon: further-out bookings counted not listed | "a queue that shows the 21:30 table at 18:00 is a diary" | — | `ABSENT` |

## 7. Domains with substantial existing coverage

Recorded from repo probes plus the design bundle's own
`IMPLEMENTATION-STATUS-RECONCILIATION.md`. **Not yet read against their domain docs** — every row
here is a candidate for `ADAPT` once the contract is checked, in the way BE-010's "already built"
turned out to be the wrong mapping.

| Domain | Repo evidence | Verdict |
| --- | --- | --- |
| Session / EOD (`SESSION_LIFECYCLE.md`) | X/Z reports, denomination count, handover, close gate | `UNVERIFIED` |
| Table lifecycle (`TABLE_LIFECYCLE.md`) | states, merge/transfer (13 files) | `UNVERIFIED` |
| Payments & value (`PAYMENT_VALUE_ENGINE.md`) | S2 L1–L7 complete; deposits (BE-001) unfound | `PARTIAL` |
| House accounts (`HOUSE_ACCOUNTS.md`) | `mezze_customer_credit.py` | `UNVERIFIED` — **credit-limit policy is an open business decision**: prototype hard-blocks, Odoo warns |
| Loyalty (`LOYALTY_ENGINE.md`) | native `loyalty` | `UNVERIFIED` — negative balance must NOT be clamped |
| Delivery (`DELIVERY_ENGINE.md`) | S3 complete: zones, fee, ETA, COD, courier | `PARTIAL` — live GPS is BE-015 |
| Online ordering (`ONLINE_ORDERING.md`) | storefront + `/shop/*` | `PARTIAL` — one menu API (M-12) unresolved |
| Inventory / waste (`INVENTORY_WASTE.md`) | native `stock.scrap` + reason tags | `BUILT` except L-02 |
| Stock variance (`STOCK_COUNT_VARIANCE.md`) | 2 files | `UNVERIFIED` |
| Workforce (`WORKFORCE_WORKFLOWS.md`) | attendance, breaks, onboarding (10 files) | `UNVERIFIED` |
| Group / HQ (`GROUP_GOVERNANCE.md`) | 4 files | `UNVERIFIED` |
| Devices (`DEVICE_PLATFORM.md`) | edge pack, hardware models | `PARTIAL` — 0% physically certified |
| Integrations (`INTEGRATIONS.md`) | aggregator ingest, HMAC, idempotency | `N/A-BE` — needs a partner cert |
| Tax (`TAX_INTEGRATION.md`) | ETA B2B wired | `ABSENT` for B2C e-receipt — a real gap |
| Payroll (`PAYROLL_INTEGRATION.md`) | attendance only | `ABSENT` — export unbuilt; blocked on `hr.employee` (see BE-008) |
| Drive-thru (`DRIVE_THRU_DEPTH.md`) | lane board, vehicle→guest | `PARTIAL` — guest path not unified (open in prototype too) |
| Localization (`AR_KEY_COLLISIONS.md`) | ar.po 542/542 | `UNVERIFIED` |
| Design system (`MEZZE_DESIGN_SYSTEM.md`) | `mezze-design.css` + foundation | `BUILT` |

---

## Summary

| Verdict | Rows |
| --- | --- |
| `ABSENT` | 38 |
| `UNVERIFIED` | 20 |
| `PARTIAL` | 12 |
| `ADAPT` | 4 |
| `BUILT` | 5 |
| `N/A-BE` | 2 |

The absences cluster, they do not scatter. **Menu (11), Refire/loss (14), Kitchen production (9)
and Arrival queue (7) are 41 of the 38+ absent rows** — four domains, not a long tail of small
misses. Everything else is largely built or needs reconciling rather than building.

## Two places the design bundle contradicts itself

Recorded because both were nearly acted on:

1. **BE-010 modifiers.** `IMPLEMENTATION-STATUS-RECONCILIATION.md` says *ALREADY BUILT — modifiers
   = real product attributes*. `CLAUDE_CODE_HANDOFF.md`'s own BE-005/16A addendum says the
   opposite: *"Do not assume Mezze's restaurant modifier groups map 1:1 onto either [variants or
   Combo Choices]… most of Mezze's MODS groups need a dedicated modifier-group/option model."*
   The addendum is later and more specific. **Trust the addendum.**
2. **Tip capture (BE-008).** The Final Integration Audit lists *Register tip → Tip Pool* as an open
   gap; `MEZZE_FINAL_FROZEN_AUDIT.md` marks that claim **stale and closed**. The frozen audit wins
   — and neither is about this repo, where the whole tip ledger was absent until now.

## Proposed build order

Foundational first, because most of Menu sits on top of one missing model.

| # | Work | Why here | Rows |
| --- | --- | --- | --- |
| 1 | **Modifier group / option model** | five surfaces read it; combos are the same model tagged; menu versions patch it | M-01..M-04, C-12, K-02 |
| 2 | **Loss category enum + plate cost** | ledgers already exist; this is a column and an aggregation | L-02..L-04 |
| 3 | **Refire incident record** | completes the cost chain with #2 | R-01..R-11 |
| 4 | **Sellability single source of truth** | every order-entry point checks one resolver; the design found a real bug here | L-06, M-09 |
| 5 | **Menu governance** | versions, dayparts, atomic publish, scheduled activation | M-05..M-13 |
| 6 | **Kitchen multi-stage + forecast** | the two things "Odoo will not do out of the box" | K-03..K-08 |
| 7 | **Arrival queue** | one derived queue + computed quote | A-01..A-10 |
| 8 | **Call centre surface** | thin: engines exist, needs call record + refusals + Repeat | C-08..C-11 |

Deliberately **not** scheduled: BE-013 ETA B2C token, BE-018 partner certification, BE-017 physical
Edge gates. The bundle's own reconciliation says `GO_LIVE.md`'s P0/P1 outranks remaining design
gaps, and those need credentials, a host and a UAT pass — not more backend code.

## Before building any row

1. Read that row's domain doc in full — this register is an index, not a substitute.
2. Re-verify `UNVERIFIED` against the contract; expect some to become `ADAPT`.
3. Check `FEATURE_MATRIX.md` / `PROJECT-STATE.md` — do not re-verify what they already certify.
