# Sprint 3F — Reservations & Waitlist Audit + Bounded Optimization

Baseline / rollback: **`sprint-1-design-foundation`**. No backend / booking-policy / table-assignment / notification change. Every reservation & seating rule preserved.

## Decision classification: **B — Bounded Polish** (one CTO-ratified fix)

The view is already primitive-aligned and enterprise-grade (empty-state 2B-1, status-badge 2B-3, segment 2B-5 all applied; sound hierarchy; 44px targets). The audit surfaced **one harmful hierarchy inversion**: over-quote waitlist parties were dimmed like no-shows. CTO ratified the fix. Everything else = KEEP.

## Current-state map

- `#view-reservations` → `.mgr` → header (`#book-h1` + **`#book-mode`** `.segment`: Reservations / Waitlist) → `#book-panel-rsv` (date row + `#rsv-list`) | `#book-panel-wait` (`#wl-tiles` KPI tiles + add-party `.rsvform` + `#wl-list`).
- **Reservation card** `.rsvcard.st-<state>`: `.rsvtime` (time `utcHM` 22px + guests) · `.rsvwho` (name 14.5 + phone/note + `.rsvchip.tbl` table) · `.status-badge--sm` · `.rsvacts` (Seat[`.go`]/No-show/Cancel, 44px).
- **Waitlist card** `.rsvcard.st-<mapped>`: `.rsvtime` (**waited-min 22px** + `~quoted-wait` sub) · `.rsvwho` (name·size + phone/note) · `.status-badge--sm` · `.rsvacts` (Notify/Seat/No-show/Cancel).
- **Empty:** `.empty-state rsvempty` (primitive). **Error:** `.empty-state rsvempty` with `⚠ message`. **Offline:** `.empty-state rsvempty` with `rsv.empty`. **Loading:** none (awaits then swaps).

## Host workflow analysis

| Question | Finding |
|---|---|
| Next arriving reservation <1s? | Yes — time `.rsvtime b` 22px bold mono, backend time-ordered. |
| Longest-waiting party <1s? | Yes — waited-min 22px dominant. |
| Checked-in vs not-arrived? | booked (accent) → seated (green badge + green border). Clear. |
| Ready-to-seat waitlist? | `notified` → ok/green badge + green border. Clear. |
| Reservation vs walk-in? | Distinct panels (segment). Clear. |
| Table assignment without opening? | Reservation shows `.rsvchip.tbl` table chip. Yes. |
| Which action is next? | Primary Seat (`.go` dark) dominant; others outline. Yes. |
| Accidental destructive action? | No/Cancel are outline buttons (not one-tap-destructive); state-change is reversible-ish. Low risk. |

## Information hierarchy

**Reservations:** name(14.5) · time(22px, actually #1-sized) · status(badge) · size(in time sub) · table(chip) · note(in sub) · actions. Time is the largest — appropriate for a time-ordered host list (matches "identify next arrival"). No harmful deviation.
**Waitlist:** **waited-duration 22px (#1 ✓)** · name(14.5) · quoted-wait(11px sub, distinguishable) · size(in name) · status(badge) · actions. Matches target. **The one harmful deviation was the over-state de-emphasis (fixed below).**

## Time audit

Reservation time `utcHM` (HH:MM). Waitlist **waited** (22px, primary) vs **quoted** (`~Nm`, 11px sub) — clearly distinguishable by size + label. Formats consistent (`m`/`د`). **Late/over parties** now rely on **more than colour** — warn border + inset ring + warn badge + the "over"/"متأخر" text label + the 22px waited number (all non-colour-redundant cues).

## Party row/card audit

Name 14.5/700, time/wait 22px/800 mono, size visible, status badge sm, note in sub-line, table chip (reservation), actions right-aligned 44px. Row ≈72px (padding 14·16 + gap 15). **Well balanced.** Long names/notes wrap (`.rsvwho{min-width:0}`) — no truncation (host needs full name; acceptable). No issue.

## Status audit

| Status | Label | Styling | Next action |
|---|---|---|---|
| booked (rsv) / waiting (wl) | accent badge | normal card | Seat/No-show/Cancel |
| seated (rsv) / notified=ready (wl) | ok/green badge | green border | (seated) / Seat |
| cancelled / no_show (rsv) | neutral badge | opacity .55 (dimmed — correct) | — |
| **over (wl)** | **warn badge "over"** | **warn border + inset, NOT dimmed** | Notify/Seat/No-show/Cancel |

Each has a clear label, semantic styling, and next action. **No status added** (`st-over` is a presentation class for the existing `w.over` data, not a new business state).

## Action audit

Primary **Seat** (`.go` ink/dark) dominant; Notify/No-show/Cancel subordinate outline; labels describe transitions clearly; placement consistent (card end). Destructive (No-show/Cancel) are not red — acceptable (routine host actions, reversible state changes), flagged as minor debt. No change (not harmful).

## Filter/search audit

rsv/wait switch = `#book-mode` `.segment` (active accent-highlighted → dataset immediately clear). Reservation scope fixed 'today'. No free-text search (short host lists). No issue.

## Sorting audit

Order is **backend-determined** (`/reservations/list` scope:'today'; `/waitlist/list`) — not sorted in JS. Not changed (prohibited). Not observed harmful. Note: promoting over-parties to the top would be a **capability** change (E) — deferred, out of scope.

## Business dependency map (all PRESERVED — untouched)

`buildReservations`, `buildWaitlist`, `wireBook`, `applyBookMode`; endpoints `/reservations/list`, `/reservations/state`, `/waitlist/list`, `/waitlist/state`; `seatTable`, `seatWaitParty`, `waitAction`; data `w.over`, `w.waited`, `w.quoted_wait`, `w.state`, `r.state`; state→tone maps; `data-a` action dispatch (notify/seat/no_show/cancel); render targets `#rsv-list`/`#wl-list`/`#wl-tiles`/`#rsv-badge`; `bookMode` filter. **None modified** — the change is purely which presentation className/badge-tone the *over* branch selects.

## State Matrix (only the over row changes visually)

| State | time/wait | status badge | table | primary | note |
|---|---|---|---|---|---|
| Rsv upcoming (booked) | time | accent | chip | Seat | — |
| Rsv seated | time | ok/green | chip | — | green border |
| Rsv no-show/cancelled | time | neutral | chip | — | dimmed .55 (unchanged) |
| WL newly added / waiting | waited | accent | — | Seat | — |
| WL ready (notified) | waited | ok/green | — | Seat | green border |
| **WL over (past quote)** | waited | **warn "over"** | — | Seat | **warn border+inset, un-dimmed (was .55)** |
| Empty rsv/wl | — | — | — | — | `.empty-state` |
| Loading | prior | — | — | — | no skeleton |
| Offline / Error | `.empty-state` msg | — | — | — | — |

## Visual audit

All elements **No issue** except the over-state **Hierarchy issue** (fixed). Minor debt: destructive-action emphasis (Typography), long-note truncation (Typography), spacing tokenization (Token cleanup) — all deferred.

## Exact changes

1. **CSS** (+1 rule): `.rsvcard.st-over{border-color:var(--warn);box-shadow:0 0 0 1px var(--warn) inset,var(--shadow-sm)}` — warn border + inset ring, no dim (mirrors the local `.st-seated` border idiom + the KDS `.k-late` inset urgency idiom).
2. **Waitlist card class** (render): `w.over?'no_show'` → `w.over?'over'` — over parties no longer inherit the `.55` dim.
3. **Waitlist badge tone** (render): `(w.state==='notified'?'ok':'accent')` → `(w.over?'warn':(w.state==='notified'?'ok':'accent'))` — over parties get the `--warn` (urgency) status-badge; badge **text unchanged** ("over"/"متأخر").

**Non-over paths are byte-identical** — each ternary changed only its `w.over` branch. Reservation `st-no_show` (real no-shows) stays dimmed. No calc/sort/transition/endpoint/action/DOM-order/id/event-target change.

## Primitive reuse

Reused `.status-badge--warn` (2B-3 tone) for the over badge. No new primitive; `.st-over` is a card-state presentation class consistent with the existing `.st-seated`/`.st-no_show` family (not a generic card). Segment/empty-state/status-badge/rsvform already applied in prior sprints.

## Screenshots / failure log

CDP froze on the heavy `pos.html`: attempt 1 (tab …377) timeout, attempt 2 (tab …389) timeout, attempt 3 (tab …377) timeout → **stopped after 3**. Reproducing an over-party also needs a live waitlist past quote. **Manual merge gate (code changed):** please open Waitlist with an over-quote party in light + dark and confirm it reads as *urgent* (warn border/badge, full opacity), not faded. No visual proof claimed here.

## Computed-style verification (light harness, both themes)

Over card: **opacity .55 → un-dimmed** (equal to a normal waiting card; in-app 1.0) · **border-color = `--warn`** (light rgb(196,106,22) / dark rgb(233,165,77)) · **inset ring present**. Over badge: **accent → warn** (light rgb(180,117,15)→rgb(196,106,22); dark rgb(246,182,91)→rgb(233,165,77)). Non-over cards/badges unchanged (identity — only the `w.over` branch differs).

## DOM / JS / CSS delta

DOM 0 (same structure/ids/order) · JS: 2 render-string ternary branches (presentation only, no logic/handler change) · CSS: +1 rule. No new elements/animation/library.

## Interaction verification

**No handler/target change** → rsv/wait switch, check-in/seat, add walk-in, edit, mark-ready (notify), assign-table (seat→`seatTable`/`seatWaitParty`), no-show, cancel, keyboard activation (native buttons), async guards, failure recovery all byte-identical (`data-a` dispatch untouched).

## Keyboard & focus verification

Native `<button>` actions unchanged; global `:focus-visible`; tab order unchanged (no DOM/id change).

## Theme verification

Light + dark both confirmed (harness): warn border/badge resolve per theme; over card un-dimmed in both.

## Business verification

Reservation/waitlist ordering (backend), wait times, quoted waits, arrival/over states (`w.over` data), table assignment, status transitions, notifications, backend payloads, seating result — **all unchanged**. Braces 2583=2583; 17 coupling refs intact.

## Performance impact

Negligible — one extra CSS rule; no new DOM/work; the over branch runs only for over-quote parties.

## Remaining UX debt (deferred)

- Promote over-parties in **sort order** (top of waitlist) — **capability/business (E)**, needs backend/sort change.
- Destructive-action (No-show/Cancel) visual distinction — optional emphasis (judgment).
- Long-note truncation on cards — needs visual sign-off.
- Reservation **lateness** cue (a booked reservation past its time isn't specially marked) — needs a lateness calc (backend/derived).
- Spacing tokenization (`.rsvcard`/header) — value-identical hygiene.
- Accessibility (`aria-live` on over/ready transitions) → Accessibility Sprint.

## STOP-condition result

**None tripped** — no sorting / wait-estimation / table-assignment / transition change; the over semantic was confirmed with the CTO (active urgent party, not gone); the fix is presentation-only (no business logic). Classification **B**, not C/D/E.
