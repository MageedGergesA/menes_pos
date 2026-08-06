# Mezze production Kitchen Display (`/mezze/kds`) — V2C Phase 1

The first production Mezze KDS front-end. A standalone **Owl** app on the shipped
cashier foundation, consuming the authoritative `mezze.kds.ticket` domain. **No Odoo
Enterprise Preparation Display dependency** (see `../project-truth-audit/KDS-REUSE-DECISION.md`).

## Route & authentication
- **`GET /mezze/kds`** — `auth='user'` (Odoo session). Unauthenticated → `/web/login`
  (real auth-required state, never demo). Controller: `controllers/kds.py`.
- The page mints a **least-privilege kitchen token**: a `mezze.terminal` with
  `role='kitchen'` → capabilities `kitchen.read` + `kitchen.update` (+ `orders.read`)
  ONLY. A KDS screen can view the board and bump a ticket; it can **never** pay,
  refund, void, comp, discount, or reach admin settings (authz `_KITCHEN`).
- `?config_id=` selects the branch (else `default_branch_id`). `?station=` pins a
  station. `?mzmode=` / `?mztheme=` / `?mzaccent=` drive the shared theme contract.

## Owl architecture (`static/src/kds/`)
| File | Role |
|---|---|
| `app.js` | entry: reads server boot, starts Odoo localization, mounts `KdsRoot`, installs the `?debug=1` handle (`window.__mezzeKds`). Reuses the cashier's `MezzeApi` transport + `debugEnabled`. |
| `store.js` | **pure** logic (HOOT-tested, no DOM): state→semantic, next-action, timer/late, channel/course/addition markers, RTL helper, and the **`KdsStore`** snapshot/bus reconcile. |
| `root.js` | `KdsRoot` — phase machine (booting/auth_required/error/board), snapshot→poll-reconcile→transition, connectivity heartbeat, 1s board clock. |
| `root.xml` | board layout: topbar (branch/stations/live-count/connectivity), responsive card grid, empty/auth/error states. |
| `components/ticket_card.{js,xml}` | one ticket card with the kitchen information hierarchy. |
| `kds.css` | styles built ONLY on the shared `--mz-` tokens + canonical `.mz-btn`/`.mz-status`/`.mz-badge`. |

Bundle: **`mezze_bridge.assets_kds`** (own bundle; reuses the shared design
foundation + the cashier's `api.js`/`debug.js` transport — NOT cashier business code).
Line/timer/action sub-blocks live inside `ticket_card.xml` rather than as separate
micro-components — a deliberate choice per the "avoid premature frameworks" rule; all
translated text is in XML/`_t` so l10n works.

## Realtime (LAN-first, server-authoritative)
`initial snapshot (/kds/state) → bus advisory poll (/bus/poll on the REAL Odoo bus) →
refresh/reconcile → on reconnect, full snapshot re-seed`. The **server snapshot is
always authoritative**: `KdsStore.seedSnapshot` REPLACES the board, so a reconnect
drops stale tickets, never duplicates, and never resurrects an aged-out cancellation.
Bus updates **upsert by ticket id**, so the same event delivered twice yields one card
(idempotent). No second realtime framework was introduced (reuses outbox + bus + poll).

## Information hierarchy (per ticket)
timer/urgency → identity (table for dine-in, order/tracking ref otherwise) → course →
items → modifiers/notes → state → **single** next action. Channel is secondary
(`.mz-badge`). State uses canonical `.mz-status` variants (fired=info, accepted=warn,
preparing=accent, ready=ok, served=neutral, **cancel=danger**) — no per-state colours.

## Hard-gate behaviours
- **Held courses stay hidden**: a held course has no ticket; the board shows only fired
  courses. Firing a held course makes it appear exactly once (course N).
- **Additions are obvious**: a later fire (course > 1) carries an explicit **`ADDED`**
  text marker, not colour-only, and appears exactly once (idempotent by id).
- **Cancellations are shown, never removed**: a voided order's tickets render with an
  explicit **`CANCELLED — do not make`** banner + danger treatment; they age out via the
  snapshot's `done_minutes`, never vanish silently.
- **Terminal safety**: served/cancel expose no next action; the backend re-validates
  every transition (a stale screen that loses a race reconciles from the snapshot).
- **Late is a condition, not a state**: `elapsed ≥ kds_late_minutes` (config, default 15)
  adds a `LATE` chip + border/pulse on top of the unchanged business state.

## Design compliance
English **Hanken Grotesk** (`--mz-font-text`), Arabic **IBM Plex Sans Arabic**
(`--mz-font-ar`), timers **tabular numeric** (`--mz-font-num`, kept LTR under RTL).
Terracotta brand is the accent, never a workflow status. Light/dark/High-Contrast come
from the SAME `mezze-design.css` registry as the cashier (no KDS-only theme). All
frequent actions are `.mz-btn--touch` (≥44px). Responsive `auto-fill minmax(260px,1fr)`
grid for tablet → kitchen monitor → large display; no horizontal page scroll.

## Tests
- HOOT: `static/tests/kds_logic.test.js` — pure logic + reconcile (state→semantic,
  next-action, timer, late, channel, addition marker, RTL, idempotent upsert, reconnect,
  liveCount).
- Browser: `tests/test_kds_browser.py` (`mezze_browser`) — authenticated `browser_js`
  on the REAL `/mezze/kds`: mount, held-course-hidden→fired, addition-once,
  cancellation-once, transition, concurrent-one-logical-effect, reconnect-no-duplicate,
  Arabic/RTL, dark, High-Contrast, real cashier + real KDS. Scenario fires/voids are
  driven server-side over HTTP (authoritative waiter/manager principals); in-board
  transitions use the page's own kitchen token.
