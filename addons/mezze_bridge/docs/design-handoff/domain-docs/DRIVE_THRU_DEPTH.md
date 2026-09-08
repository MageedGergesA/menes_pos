# Drive-thru depth — stage timing, analytics, menu board

Two surfaces added behind the Drive-thru tab strip (`Lane` · `Lane performance` · `Menu board`),
screens 42 and 43. The lane board itself is unchanged apart from the tabs.

## 1. Stage timing (the thing everything else reads)

The lane board shows **three windows** because that is the building. Timing is finer than the
building, so every car carries a `stg` map of stamps in seconds:

| Stamp | Measures | Written when | Target |
|---|---|---|---|
| `speaker` | wait at the speaker before anyone greets the car | the order screen is opened | 22s |
| `order` | taking the order | the order is confirmed | 45s |
| `pay` | at the payment window | payment is taken | 38s |
| `bag` | dwell at the pickup window before bag check | the bag-check screen is opened | 35s |
| `hand` | the handover itself | handed out | 18s |
| `pf` | time in the pull-forward bay | the car comes back to the window | — |

`dtStamp(car, key, tick)` writes the stamp and restarts the stage clock, so the "at window"
timer on the lane board now reads *time at this stage*, not time since the last window change.

A car that is handed out becomes a record via `dtRecord()` and joins `state.dtDone`. Unstamped
remainder (a car seeded mid-lane, or one moved by a path with no stamp) is attributed to
`speaker` — lane wait, never service.

**Why it matters:** the speaker wait is not the time it takes to say the order, and the pickup
dwell is not the handover. Reporting one number for "window time" hides which of the two is
broken, and they have different fixes (staffing vs. kitchen pacing).

## 2. Lane performance (screen 42)

Range: Today / Last 7 days / Last 28 days. Lane filter: both / 1 / 2.

- **Historical rows.** `dtDay(d)` generates one seeded row per car per day — deterministic, so
  a stage average, a daypart row and one car's progression bar can never disagree. Day 0 is
  partial (fills as the branch clock advances) and carries the session's real handed-out cars.
- **Where the service time goes.** Stacked bar of the five stage averages plus the pull-forward
  average, then a table with avg / p90 / worst / target / Δ per stage.
- **Daypart performance.** Breakfast, Lunch, Afternoon, Dinner, Late night — cars, service,
  the five stage averages, within-target %, pull-forward %, all read against each stage's own
  target so the slow stage is named per daypart, not per day.
- **Trend.** Average service by hour (today) or by day (7/28), bars over target in accent.
- **Vehicle progression.** Newest cars off the lane as segmented bars — one segment per stage,
  pull-forward in accent, target marked. Live cars show stamped stages, the current stage
  running, and stages not yet reached.
- **Pull-forward.** Rate, average bay time, lane time freed, and why cars were pulled. Stated
  with its cost: it needs a runner, and the car leaves the bag check's line of sight.
- **Line-busting handoff.** Share taken by the walker, their service time against
  speaker-ordered cars, and handoffs that did not land (walker took the order, the car reached
  the window with nothing on screen, order taker retook it).

## 3. Menu board (screen 43)

Three boards as **devices**, not as a layout: `DT-BOARD-01` pre-sell (lane entry),
`DT-BOARD-02` main (order point, 3 panels), `DT-BOARD-03` order confirmation.

Each carries its own state — online / maintenance (holding last layout) / firmware behind
(publishes queue) — plus heartbeat, revision, firmware and brightness. A board can lag the
branch; the screen says so instead of pretending one truth.

- **Daypart schedule.** Breakfast / All-day / Late-night, or forced (the override is listed as
  a draft change so it cannot be forgotten). Next flip and countdown in the header.
- **Preview.** The board as it renders right now — same prices, same availability, same
  daypart. The confirmation board previews the live car at the speaker.
- **Slots.** Panels resolve against the live menu. An 86'd item either hides and pulls the
  nearest-price substitute into the slot (auto-hide on) or stays on the board (auto-hide off) —
  and then publishing is **blocked**, naming the consequence: cars order it at the speaker and
  the order taker has to say no.
- **Publish.** Draft changes diff (price behind the menu, hidden/sold-out slots, forced layout,
  calories off), publish now or schedule for the next flip. Boards that are offline or behind
  on firmware are reported as queued. Every publish is a revision in the session log.

## Odoo mapping

- Rows read `pos.order` and its session; stage stamps extend the model with one timestamp per
  window (not a new order concept).
- Dayparts are reporting windows over the same session data.
- Board slots read `product.template` through the branch pricelist; 86 reads **availability**,
  never deletion.
- A board is a device: it carries its own revision and can lag — the same local-first,
  sync-on-reconnect behaviour as the POS itself.
- Line-busting handoff is an extension of Odoo POS order taking on a handheld, attributed to
  the walker.

## Bilingual

All new strings go through `tr()` / `N()`, so both screens read in Arabic with Arabic-Indic
numerals and mirror in RTL. Stage names are short in both languages so the daypart table
columns hold.

## Pass 18A — vehicle is not the guest

`car.cust` used to carry a copied `{name,phone,visits}` snapshot from a car-only seed
(`DT_KNOWN`) that duplicated four people already in the one Guest book — exactly the
`driveGuests` anti-pattern the guest-identity pass forbids. It now stores a guest **id**,
resolved live via `dtGuest(id)` against `state.guests`, the same record Register, the handheld
and the call centre read. `DT_VEHICLES` keeps only what is actually a vehicle fact — plate,
colour, body — mapped to one or more guest ids, so `Order → Guest` and `Vehicle → Guest` stay
two different relationships. A plate matching more than one guest (a shared car) surfaces as a
**choice**, never an auto-pick — the employee confirms who is actually at the window.
