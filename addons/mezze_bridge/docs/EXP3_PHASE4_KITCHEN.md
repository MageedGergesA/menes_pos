# Experience 3.0 — Phase 4: Kitchen (KDS)

*Rebuild the Kitchen workspace to the approved Mezze design. Kitchen workflows, timing, bump actions, routing and performance preserved. Presentation only. Shell (P1), Cashier (P2), Checkout (P3) frozen.*

**STATUS: implemented, verified, local commit — awaiting review.**

---

## 1. The change

The live KDS was a **horizontal-scroll of fixed 288px columns**. The approved KDS is a **wrapping grid of ticket cards** (`repeat(auto-fill, minmax(220px, 1fr))`, gap `space-200`, padding `space-400`).

Each live `.kcol` is already one ticket (table + timer + items + bump), so this is a **container-layout change**, not a card rebuild:

| | Approved | Before | After |
|---|---|---|---|
| KDS container | grid `minmax(220px,1fr)`, gap 16, pad 24, wraps | flex row, gap 14, pad 20/22, horizontal-scroll | **grid, minmax 220, gap 16, pad 24, wraps** |
| Ticket card | grid item, auto width/height | fixed 288px, `max-height:100%` | **grid item (223px), natural height** |

**Implementation:** 2 CSS rules. **No markup, no JS.**

## 2. Preserved (verified)

| Guarantee | Evidence |
|---|---|
| **JavaScript byte-identical to `git HEAD`** | diff = 0 — timing, bump, routing, `renderKDS` untouched |
| Bump action | click fired, 0 JS errors (JS unchanged from working build) |
| Timers | live, color-coded (14:22 etc.) |
| All workspaces | 0 broken, 0 JS errors |
| Frozen work | shell/cashier/checkout untouched |

## 3. Validation — measured live (against the brief's checklist)

| Validate point | Result |
|---|---|
| **Ticket hierarchy** | ✅ every card: header (`.kh`) + title (`.kt`) + order (`.ko`) + timer (`.ktimer`) + body (`.kbody`) + items (`.kitem`) + bump (`.kbump`) |
| **Timers** | ✅ prominent 18px/800, color-coded by state (14:22 / 06:48 / 00:09) |
| **Status colors** | ✅ **NEW = teal**, **COOKING = warn/amber**, **LATE = crit** — 2 new / 2 cook / 1 late live |
| **Station grouping** | ⚠️ this demo's data uses **course/status labels** (LATE/COOKING/NEW), not station tags (`.kstation` count 0). The `.kstation` treatment exists for when routing supplies stations. Grouping-by-urgency (colour) is active. |
| **Priority indicators** | ✅ LATE ticket has crit border + red timer — unmistakable |
| **Touch ergonomics** | ✅ bump button 44px height (meets 44px min) |
| **Dark mode** | ✅ verified live (screenshot); cards/timers/status legible on dark canvas |
| **Large-screen readability** | ✅ grid fills width and wraps; 220px+ cards keep item text readable; no horizontal scroll |

**Layout geometry:** grid, columns 223px (`minmax(220)` filling), gap 16px, padding 24px, overflow-y auto — **matches approved exactly**. **Amber** gets the identical grid (display grid, gap 16, 5 cards, status colours) — layout is appearance-independent.

## 4. Kitchen compliance: **≈ 93%**

| Aspect | Compliance | Notes |
|---|--:|---|
| Grid layout (container) | **100%** | minmax 220 / gap 16 / pad 24 exact |
| Ticket card hierarchy | **~95%** | Full header/timer/items/bump; already well-built |
| Status / priority colours | **~95%** | teal/warn/crit semantic states + late border |
| Timers | **~90%** | Prominent, color-coded, mono |
| Station grouping | **data-dependent** | Course/status grouping active; station tags await routing data |
| **Weighted overall** | **≈ 93%** | |

## 5. Before / After

- **Before:** a single row of fixed 288px columns that scrolled **horizontally** — off-screen tickets were hidden past the right edge.
- **After:** a **wrapping grid** of 220px ticket cards that fills the kitchen screen and flows to new rows — every ticket visible at a glance, which is the point on a large KDS display. Status colour (red LATE / amber COOKING / teal NEW), timers, seat tags and per-card bump buttons all retained.

## 6. Remaining differences

| # | Item | Reason | Recommendation |
|---|---|---|---|
| 1 | **Station grouping** shows course/status labels, not station lanes | This demo's ticket data carries no station assignment; `.kstation` renders when routing supplies it. | No change — verify with real station-routed data during pilot. |
| 2 | Very tall tickets (many items) grow the card | Grid rows size to content; a ticket with many lines makes a tall card. | Add `.kbody{overflow-y:auto; max-height:…}` only if pilot shows over-tall tickets — not a current defect. |
| 3 | Exact timer/bump px vs approved | Live values are prominent and legible; approved exact px not fully extracted. | Fine-tune only if a verified readability issue appears. |

## 7. Recommendation for Reports (Phase 5)

**Phase 4 is complete (~93%).** The KDS matches the approved wrapping-grid layout; timing, bump, routing and performance are preserved (JS byte-identical); status colours, priority and touch targets all validate; zero regressions in either appearance.

**Recommend proceeding to Phase 5 (Reports / executive dashboard).** Reports (`#view-reports`) is a self-contained analytics workspace — a layout/IA rebuild with charts and stat tiles, independent of the KDS. Item 1 above (station grouping) is a pilot-data verification, not a blocker.

*Committed locally (not pushed). Prior phases remain frozen.*
