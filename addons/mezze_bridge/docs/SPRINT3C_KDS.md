# Sprint 3C — Kitchen Display System (KDS) Audit + Bounded Optimization

Baseline / rollback: **`sprint-1-design-foundation`**. No backend / order-lifecycle / kitchen-state change. Every business rule preserved.

## Decision classification: **B — Bounded Polish** (one value-identical change)

The KDS is genuinely enterprise-grade; the audit found **no** hierarchy, timer, action, or density problem worth changing. The single defensible improvement is a **primitive-reuse gap**: the KDS live empty state was the only view still hand-rolling its empty message inline instead of using the `.empty-state` primitive. Fixed (value-identical). Everything else = **KEEP**.

## Current-state map

- **Board** `.kds` (`#kds`): horizontal-scroll flex row of ticket columns; oldest-first, `padding:20px 22px`, `gap:14px`, `align-items:flex-start`.
- **Ticket** `.kcol` (288px, surface card, `--r-lg`, max-height 100%, column flex):
  - **Header** `.kh`: `.kt` table/takeaway (15.5px/800) + `.ko` server·course (11.5px) + `.kstate st-<state>` badge + **`.ktimer`** (19px/800 pill).
  - **Body** `.kbody`: `.kstation` (station, accent-strong caps + dot) + `.kitem`s (14.5px; `.kq` qty accent-strong; `.kmod` modifier/note warm-amber 12.5px; live path) / `.kcourse` + `.kseat` (demo path).
  - **Actions** `.kacts`: next-action button (`.primary` ink = advance / `.go-ready` pos-green = ready) + `.ghost` recall (↩); **or** `.kbump` (demo). 44px.
- **Empty:** `#kds` empty message (live path) — **was** inline-styled, **now** `.empty-state`.
- Two render paths share `.kcol`: **live** `kdsRenderTickets(k,tickets)` (bridge, `/kds/transition`) and **demo** `buildKds` fallback (`.kbump`, static `tk.timer`).

## Queue analysis

- **Visual priorities:** 3 timer tiers (`.k-new` teal / `.k-cook` amber / `.k-late` crit) + `.k-ready` (pos border). Oldest ticket is **leftmost** (sort by `fired_at` asc) → identifiable in <1s by position **and** the amber/crit timer.
- **Urgent (late) tickets:** unmistakable — crit border + inset ring + crit-soft header tint + **pulsing** timer (a *non-colour* cue, so it survives colour-blindness and glance-distance). Reduced-motion honoured.
- **State legibility without reading:** yes — `st-fired`(teal)/`st-accepted`(amber)/`st-preparing`(violet)/`st-ready`(green)/`st-served`(grey) badges + column border tints (`.k-late`/`.k-ready`) encode state via colour + shape + position.
- **Colour doing too much?** No — colour is layered with position (sort), motion (late pulse), and border/inset, so no single channel is overloaded. Typography (19px timer, 15.5px table, accent-strong qty) reinforces.

## Information hierarchy

Target 1 timer · 2 priority · 3 table/order# · 4 items · 5 allergy/modifier · 6 status · 7 utility.
Actual: timer **19px/800** (#1 ✓) → priority via border/colour/pulse/sort (#2 ✓) → table `.kt` **15.5px/800** (#3 ✓) → items **14.5px** (#4 ✓) → modifier `.kmod` **12.5px amber** emphasised (#5 ✓) → status `.kstate` **9.5px badge** (#6 ✓) → actions (#7). **Matches the target; no harmful deviation.** No change.

## Timer audit

`.ktimer` 19px/800, tabular pill (`padding:4px 10px`, `--r-sm`), right-aligned in header. Aged: teal→amber→crit; late adds pulse + crit border/header. Readable at 10 and 30 tickets (fixed 288px columns, horizontal scroll keeps timer at a constant on-column position). Touch + desktop both fine. **Strong — KEEP** (no manufactured bump).

## Ticket audit

288px column, `.kbody` `padding:10px 14px`, `.kitem` 14.5px / line-height 1.35 / gap 8. Density **well balanced**. Modifiers/notes rendered warm-amber and bolder than body (deliberate — must not be missed). **Long items intentionally NOT truncated** — full item + modifier visibility is safety-critical in a kitchen (truncation could hide an allergy/mod). KEEP.

## Colour audit

| Colour | Meaning | OK? |
|---|---|---|
| teal (`.k-new`, `st-fired`, `.kseat`) | new / just fired / seat | ✓ |
| amber `--warn` (`.k-cook`, `st-accepted`, `.kmod`) | cooking / modifier-note | ✓ |
| violet (`st-preparing`) | preparing | ✓ |
| green `--pos` (`st-ready`, `.k-ready`, `.go-ready`) | ready | ✓ |
| grey (`st-served`) | served/done | ✓ |
| crit `.k-late` | late/urgent (+ pulse + border) | ✓ |
| accent-strong (`.kq`, `.kstation`) | quantity / station emphasis | ✓ |

No colour is ambiguous; none added.

## Action audit

Correct action is a single prominent next-action button (`.primary`/`.go-ready`); recall is a small `.ghost` ↩ (subordinate, hard to hit by accident). Actions disable during async (`btn.disabled=true`) → no double-fire. No destructive delete. **Findable, safe. KEEP.**

## Business dependency map (all PRESERVED — untouched)

- **Render:** `kdsRenderTickets(k,tickets)`, `buildKds()`, `kdsTimer(fired_at)`.
- **Queue algorithm:** filter `state!=='served'&&!=='cancel'`, **sort `fired_at` asc**.
- **Priority/state maps:** `KDS_NEXT`, `KDS_STCLS` (`fired→k-new`, `accepted/preparing→k-cook`, `ready→k-ready`), `KDS_STLBL`.
- **Transitions:** `bridgeCall('/kds/transition',{ticket_id,action})` via `data-act`; bus `mezze_kds_update`/`mezze_waiter_ready` → `buildKds()`.
- **ids/containers:** `#kds`, `#view-kds`, `.railbtn[data-view="kds"] .badge`.
- The changed line is the **empty branch only** (`!k.children.length`) — no ticket/timer/state/sort/handler code touched.

## State Matrix (behaviour unchanged)

| State | Timer | Badge | Controls | Primary action | Transition |
|---|---|---|---|---|---|
| New/Fired | teal | `st-fired` | next | Accept | fired→accepted |
| Cooking (accepted/preparing) | amber | `st-accepted`/`st-preparing` | next + recall | Prepare/Ready | →preparing/ready |
| Ready | (k-ready border) | `st-ready` green | next + recall | Serve | ready→served |
| Served/Cancelled | — | (filtered out) | — | — | removed from board |
| Rush/Delayed (late) | crit + pulse | per state | per state | per state | (aging only, no state change) |
| Allergy | (note in amber `.kmod`) | per state | per state | per state | n/a |
| Empty queue | — | — | — | — | `.empty-state` message |
| Offline/Loading | demo/fallback board or bridge badge | — | — | — | n/a |

## Visual audit

| Element | Measure | Classification |
|---|---|---|
| `.ktimer` | 19px/800 aged pill + late pulse | No issue (strong). |
| `.kt` / items / `.kmod` / `.kstate` | 15.5 / 14.5 / 12.5 / 9.5px | No issue (correct hierarchy). |
| `.kacts button` / `.kbump` | 44px | No issue (touch min met). |
| `.k-late` / `.k-ready` borders | crit / pos inset | No issue (non-colour cue). |
| **KDS empty state** | inline-styled div | **Token/consistency issue** → migrate to `.empty-state`. |
| spacing (20/22/14/10/8) | mixed | Token cleanup available; deferred (value-only). |

## Change made

Line 3072 (live-path empty branch): `<div style="padding:48px;text-align:center;color:var(--ink-3);font-size:14px">` → `<div class="empty-state" style="padding:48px">`. The `.empty-state` primitive = the exact three removed declarations; `padding:48px` retained inline → **value-identical**. Completes the 2B-1 empty-state migration (KDS was the last hold-out; `bds`/`rsv`/waitlist already migrated).

## Primitive reuse

Reused `.empty-state` (approved). No new primitives; none invented. KDS-specific ticket components (`.kcol`/`.ktimer`/`.kstate`/`.kacts`/`.kbump`) correctly remain distinct — not forced into generic cards or the Command Button primitive.

## Screenshots / failure log

Required KDS-state screenshots **not captured** — CDP froze on the heavy `pos.html`: attempt 1 (tab …377) timeout, attempt 2 (tab …389) timeout, attempt 3 (tab …377) timeout → **stopped after 3**. Rendering the queue also needs live bridge tickets. **Manual merge gate** — though the change is a proven value-identical empty-state swap (zero visual change), so the gate is effectively trivial.

## Computed-style verification (light harness, both themes)

OLD inline empty vs NEW `.empty-state`+`padding:48px`: **MATCH** — textAlign `center`, color `--ink-3` (light rgb(139,131,112) / dark rgb(134,125,106)), fontSize `14px`, padding `48px` all identical. No intentional visual difference (this is a consistency refactor, not a visual polish).

## DOM / JS / CSS delta

DOM 0 (same element/insertion) · JS 0 logic (one innerHTML string's class/style tokens) · CSS 0 (reuses existing `.empty-state`). No new elements/animation/library.

## Interaction verification

**No handler/render-flow change** → ticket selection, ready/fire/serve/recall, async disable-guard, expand/collapse (n/a — flat columns), scroll, offline/demo fallback, bus-driven refresh all byte-identical. The empty branch renders only when 0 tickets (non-interactive text).

## Theme verification

Both themes MATCH (harness) — `--ink-3` resolves per theme identically old-vs-new.

## Business verification

Ticket ordering (`fired_at` asc), priority (`KDS_STCLS`/`KDS_NEXT`), timers (`kdsTimer`), status badges, actions, `/kds/transition` payloads, and queue transitions — **all unchanged**. Diff = 1 line; braces 2582=2582; 28 KDS-machinery refs intact.

## Performance impact

Zero — same DOM, no new work; the changed branch runs only on empty queue.

## Remaining UX debt (deferred, non-harmful)

- Dedicated **allergy** flag/emphasis (currently allergies ride the amber `.kmod` note channel) — requires allergy data + render change → out of bounds (business/render).
- Token-only spacing normalization on the board/columns (value-identical; cosmetic).
- Optional across-room timer scale-up (currently strong at 19px) — only if floor feedback demands it; not manufactured here.
- Accessibility (`aria-live` for new/late tickets, `role` on the board) → Accessibility Sprint.

## STOP-condition result

**None tripped** — no priority-logic / ticket-render-substance / queue-layout / DOM-restructure / backend change; classification is **B**, not C/D. The change is confined to the empty-branch string and is value-identical.
