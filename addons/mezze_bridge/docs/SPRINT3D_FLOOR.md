# Sprint 3D — Floor Plan Audit + Bounded Optimization

Baseline / rollback: **`sprint-1-design-foundation`**. No backend / seating / table-state change. Every business workflow preserved.

## Decision classification: **A — KEEP** (no code change)

The floor plan is enterprise-grade: table-number-first hierarchy, occupancy/reservation legible via layered non-colour cues (fill, border-style, motion), size-encoded capacity, fixed coordinates for spatial memory, ≥52px touch targets, accurate legend. **No harmful hierarchy deviation, no hand-rolled empty state, no primitive-reuse gap.** Per governance ("the investigation may legitimately conclude KEEP; do not manufacture changes"), the correct outcome is **KEEP**. Documentation-only commit for the record.

## Current-state map

- `.floorwrap` → `.floortop` (`#floortabs` room selector + `#floorstats`) → `.legend` (4 states) → `.floorcanvas` (`#floorcanvas`).
- **Room selector:** `.floortabs`/`.floortab` — `aria-pressed` pill group (the pill family intentionally kept distinct from `.segment` per 2B-5). Click → `activeFloor=k; buildFloor()`.
- **Stats:** `.floorstats`/`.fstat` — occ, covers, dwell, turns (18px numbers).
- **Legend:** `.leg av/oc/bl/rs` swatches mirroring table treatments (teal border / accent fill / warn fill / violet dashed).
- **Canvas:** `.floorcanvas` — 40px grid background, `.floorzone` dashed labels, absolute-positioned `.table` buttons at `x%/y%`.
- **Table object** `.table.<st>` (button): `.tabletop` (shape-sized via `SHP`: round2/round4/sq4/booth6) with `.tn` (number, 18px/800 mono) + `.tmeta` (status meta, 10.5px) + optional `.tbadge` (EGP total, oc/bl) + optional `.tqr` (QR shortcut for av/rs). `.chair` objects positioned around.
- **Toolbar/filters/zoom:** floor tabs are the toolbar; canvas is `overflow:scroll` (no discrete zoom control — adequate for terminal).
- **Wait timers / server / footer:** dwell shown in `.tmeta` ("N′") for occupied; **no per-table server label**; no footer.

## Spatial analysis

| Question | Finding |
|---|---|
| Locate a table <1s? | Yes — `.tn` 18px/800 centred on ≥52px face; fixed layout aids recall. |
| Occupied obvious? | Yes — **solid amber fill** vs white/teal-border free. |
| Reserved obvious? | Yes — **violet dashed** border + violet-soft bg + violet text. |
| Server finds own tables? | **No per-table server cue** (deviation — see hierarchy). |
| Colour overloaded? | No — layered with fill vs border, solid vs dashed, and motion (bill pulse). |
| Shape contributes? | Yes — real table shapes; free=outline vs occupied=filled. |
| Size contributes? | Yes — size ∝ capacity (round2 60 → booth6 154). |
| Typography contributes? | Yes — 18px/800 mono number dominates the face. |
| Spatial memory? | Yes — absolute `x%/y%` = fixed real layout. |

## Information hierarchy

Target 1 table# · 2 occupancy · 3 reservation · 4 wait · 5 server · 6 capacity · 7 utility.
Actual: table# 18px/800 (#1 ✓) · occupancy fill (#2 ✓) · reservation dashed-violet (#3 ✓) · wait `.tmeta` "N′" 10.5px (#4, present/secondary) · **server absent (#5 deviation)** · capacity via size+chairs (#6 ✓) · tabs/legend (#7). **One deviation (server), non-harmful** — servers work known sections; surfacing per-table server requires a data + render change (prohibited). No change.

## Table object audit

| Measure | Value | Verdict |
|---|---|---|
| Table size | 60–154px (shape/capacity) | No issue (touch ≥52px). |
| Label `.tn` | 18px/800 mono | No issue (#1, dominant). |
| Badge `.tbadge` | 11px EGP pill (oc/bl) | No issue. |
| Meta `.tmeta` | 10.5px | No issue (secondary). |
| Selected state | none persistent (click = immediate seat/actions) | N/A — no selection to improve. |
| Hover | scale 1.05 + shadow-md | No issue. |
| Occupied / Reserved / Bill | fill / dashed / warn-pulse | No issue (strong, distinct). |
| Merge indication | no distinct merged visual | Debt (needs render/data). |
| Capacity | size + chair count | No issue. |

## Color audit

| Colour | State | Layered cue | OK? |
|---|---|---|---|
| teal | free/available | border-only (no fill) | ✓ |
| accent/amber | occupied | solid fill | ✓ |
| warn | bill requested | fill + **pulse** | ✓ |
| violet | reserved | **dashed** border + soft bg | ✓ |

No "selected"/"waiting" colour on the floor (no persistent selection; waiting parties live in Reservations/Waitlist). No colour ambiguous; none to add.

## Navigation audit

Room switch (`.floortab`→`buildFloor`); selection = single click → av/rs `seatTable` or oc/bl `openTableActions` (bottom sheet); `.tqr` `stopPropagation` so the QR glyph doesn't seat the table. No drag (coordinates are fixed data), no discrete zoom (canvas scrolls). **Accidental selection risk low** — a table tap opens a seating flow / actions sheet (not an irreversible commit); destructive "Request bill" lives inside the actions sheet.

## Business dependency map (all PRESERVED — untouched)

`SHP` (shape w/h/r/seats), `chairPos`, per-table `x%/y%` coordinates, `tb.st` states (`av/oc/bl/rs`), `buildFloor`, `bridgeFloors`, `FLOORS`, `seatTable`, `openTableActions`, `openTablePicker` (transfer/merge), `showTableQr`, `.tbadge`/`.tqr` logic, `#floorcanvas`/`#floortabs`/`#floorstats` render targets. **None modified.**

## State Matrix (unchanged)

| State | Label | Badge/meta | Primary action | Transition |
|---|---|---|---|---|
| Free (`av`) | `.tn` + "open" | teal border | seatTable | av→(seated) |
| Occupied (`oc`) | `.tn` + "Ng · N′" | amber fill + `.tbadge` EGP | openTableActions | oc→bl/paid |
| Bill (`bl`) | `.tn` + meta | warn fill + pulse + `.tbadge` | openTableActions | bl→free (paid) |
| Reserved (`rs`) | `.tn` + name/time | violet dashed | seatTable | rs→occupied |
| Merged | (occupied face) | — | actions | via openTablePicker |
| Selected | (no persistent state) | hover only | — | — |
| Offline/Loading | demo FLOORS fallback | — | — | — |
| Error | catch → keeps FLOORS | — | — | — |

## Visual audit

Every element classified **No issue** except: merge indicator & per-table server (Structural — need render/data, out of bounds); reservation-name long-label (potential overflow on small tables — Typography debt, but truncation risks hiding the guest name); floor-chrome spacing (`.floortop`/`.legend`/`.floorstats`/`.floorcanvas`) tokenizable value-identically (Token cleanup — pure hygiene, no UX value).

## Changes / KEEP rationale

**No code change.** The three "allowed polish" levers are either already at target (table-number/occupancy/reservation hierarchy are strong) or unavailable safely:
- Table-number hierarchy — already dominant (18px/800 on the face); bumping risks over-tuning a value tuned across 60–154px shapes.
- Reservation/occupancy visibility — already unmistakable (dashed-violet / solid-fill / pulse).
- Spacing tokenization — value-identical hygiene only; bundling maintainability churn into a UX sprint would be scope-adjacent, not UX optimization → deferred to an appearance/hygiene pass.
- Long-label truncation — would hide reservation names (info-loss risk) and needs visual sign-off → deferred.
- Server/merge/dwell emphasis — require prohibited render/data changes.

Manufacturing any of these would violate "do not manufacture changes."

## Primitive reuse

None required — no hand-rolled chrome maps to an approved primitive here. `.floortab` (aria-pressed pill, kept per 2B-5) and `.tact` (kept per 2B-4) are correctly distinct; the floor has no empty/list surface needing `.empty-state` (canvas always renders tables).

## Screenshots / failure log

CDP has frozen on the heavy `pos.html` across every 3.x sprint (script-injection timeout); the freeze persists this sprint. Because the classification is **KEEP (zero visual change)**, there is **no before/after to compare** — no visual gate is required. The known-freeze is recorded; further attempts would be futile round-trips.

## Computed-style verification

N/A — no style changed. (For unchanged controls, equivalence is trivially the identity.)

## DOM / JS / CSS delta

**0 / 0 / 0.** No code file modified (documentation only).

## Interaction verification

N/A — no handler/render/DOM change. Table selection, room switching, scroll, reservation/occupied open, and payment transition are byte-identical (untouched).

## Theme verification

N/A — no style changed; existing light/dark behaviour preserved.

## Business verification

Table selection, reservation state, occupancy, backend payloads, and room transitions **unchanged** — no code touched.

## Performance impact

Zero — no code change.

## Remaining UX debt (deferred, non-harmful)

- Per-table **server assignment** cue (#5 hierarchy gap) — needs data + render.
- **Merged-table** visual indicator — needs render/data.
- **Dwell-time** emphasis for turnover (occupied `.tmeta` minutes) — needs render split.
- Reservation-name **long-label** handling on small tables — needs visual sign-off (truncation vs info-loss).
- Floor-chrome **spacing tokenization** — value-identical hygiene (appearance/hygiene pass).
- Discrete **zoom** control for very large rooms — structural.
- Accessibility (canvas `role`, `aria-live` on state changes) → Accessibility Sprint.

## STOP-condition result

**None tripped** — no coordinate/canvas/selection/DOM/backend change needed. Classification **A — KEEP**; no C/D redesign proposal required.
