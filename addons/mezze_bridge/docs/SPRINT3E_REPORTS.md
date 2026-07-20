# Sprint 3E — Reports & Analytics Audit + Bounded Optimization

Baseline / rollback: **`sprint-1-design-foundation`**. No backend / reporting / KPI-calculation change. Every calculation preserved.

## Decision classification: **A — KEEP** (no code change)

The Reports dashboard is enterprise-grade: dominant tabular KPI values, active-filter segments (already the migrated `.segment` primitive), tabular right-aligned numeric columns, deliberate positive all-clear empties. The genuine hierarchy gaps (trend direction, comparisons) are **backend-gated** — the summary endpoint returns no period-over-period data, so surfacing trends requires prohibited calculation/query changes. Per governance ("may legitimately conclude KEEP; do not manufacture changes"), the outcome is **KEEP**. Documentation-only commit.

## Current-state map

- `#view-reports` → `.mgr scroll` → `.ophead` header → `#rpt-panel-sales` | `#rpt-panel-gl` (hidden).
- **Header `.ophead`:** `#rpt-h1` (23px/800) + `#rpt-asof` sub + **`#rpt-mode`** segment (Sales / Books·GL) + **`#rpt-range`** segment (Today / 7 days / Month) + **`#rpt-csv`** `.button` export.
- **Sales panel:** `.tiles`/`#rpt-tiles` (5 KPI `.tile`s: gross, net, avg-ticket, refunds, reversals) + `.mgrgrid` two `.mgrcard`s — "Refunds by reason" (`.rrow` list + `#rpt-refpill`) and "Cashier leaderboard" (`.srow` list).
- **GL panel:** `.tiles`/`#gl-tiles` (4 KPI tiles) + wide `.mgrcard`s — Trial balance (`.glrow`) + Session-close check.
- **KPI tile:** `.tl` label (11px caps) + `.tv` value (**31px/800 `.num`**) + optional `.td` secondary count.
- **Charts:** none in Reports (sparkline/`.card` charts live in the OPS dashboard, out of this view).
- **Loading:** none (awaits then swaps innerHTML; prior content shown meanwhile). **Empty:** `.mgrempty` (positive green). **Error:** `bridgeBadge` toast. **Offline:** `if(!BRIDGE.connected)return` (no panel message).

## Information hierarchy

Target 1 primary KPIs · 2 trend · 3 comparisons · 4 charts · 5 tables · 6 filters · 7 export.
Actual: KPIs `.tv` 31px (#1 ✓) · **trend absent (#2)** · **comparisons absent (#3)** · charts n/a here (#4) · tables `.rrow`/`.srow`/`.glrow` (#5 ✓) · filters `.segment` groups, active highlighted (#6 ✓) · `#rpt-csv` (#7 ✓). **Deviation: no trend/comparison — backend-gated (endpoint returns only current-period), prohibited to add.** No change.

## KPI audit

| Measure | Value | Verdict |
|---|---|---|
| Number `.tv` | 31px/800 + `.num` (tabular) | No issue (#1, dominant). |
| Label `.tl` | 11px caps, `--ink-3` | No issue. |
| Delta `.td` | 12px count (no arrow in Sales) | No issue (`.td.up/.dn` classes exist but unused — needs comparison data). |
| Colour | neutral; up=pos/dn=crit reserved | No issue. |
| Spacing / alignment | 16/17px padding; `.num` tabular | No issue. |

**Business state in <3s?** Yes for *current* figures (gross/net/avg dominate at 31px). Trend-vs-prior-period would help but is backend-gated.

## Chart audit

No charts in the Reports view (they are in the OPS dashboard — separate surface). N/A here; no chart-library change (prohibited anyway).

## Filter audit

| Filter | Control | Active visible? |
|---|---|---|
| Mode (Sales / GL) | `#rpt-mode` `.segment` | ✓ `.segment.on` accent |
| Date range (Today/7d/Month) | `#rpt-range` `.segment` | ✓ `.segment.on` accent |
| Branch / staff / category | n/a (single-branch view; HQ handles branch) | — |
| Reset | n/a (a segment is always active) | — |

**Active filters immediately identifiable? Yes** — accent-highlighted segments. No issue.

## Table audit

`.rrow` (label + `.rcount` + `.ramt`, tabular `text-end`, min-width columns) and `.srow` (rank badge + name + `.ssales` + `.sord`) and `.glrow`. Header hierarchy via `.mgrhd h2` (14px/800) + `.mgrpill` summary. Rows pre-sorted amount-desc in JS. Numeric/currency **right-aligned + tabular-nums** with fixed min-widths → clean columns. No interactive column-sort or sticky header (lists are short, pre-sorted). Empty → `.mgrempty`. No issue.

## Business dependency map (all PRESERVED — untouched)

`buildReports`, `buildGl`, `applyRptMode`, `wireReports`, `rptDates`/`rptRangeLabel`; endpoints `w1Call('/reports/summary')`, `/gl/summary`, `/gl/sessions`; KPI derivations (`net = round((sales.total+refunds.total)*100)/100`, `avg_ticket`), sort (`by_reason`/`by_cashier` amount-desc), `RF_LABEL`, CSV export (`#rpt-csv`); render targets `#rpt-tiles/#rpt-reasons/#rpt-cashiers/#gl-*`; filter state `rptMode`/`rptRange`. **None modified.**

## State Matrix (unchanged)

| State | KPIs | Lists | Actions | Note |
|---|---|---|---|---|
| Loading | prior tiles shown | prior | segments active | no skeleton |
| Loaded | 5 sales / 4 GL tiles | reasons + leaderboard | export enabled | — |
| Filtered | recomputed per range/mode | re-rendered | — | active segment highlighted |
| Empty (no refunds/cashiers/accounts) | tiles (zeros) | `.mgrempty` positive | — | — |
| Exporting | — | — | `#rpt-csv` | CSV download |
| Offline | prior content | prior | — | `buildReports` returns early |
| Error | prior content | prior | — | `bridgeBadge` toast |

## Visual audit

Every element **No issue** except: 5-sales-tiles in a 4-column `.tiles` grid → one orphan tile on row 2 (**Hierarchy/Structural** — but a column-count change alters tile widths and breaks the 4-tile GL panel; unverifiable-safely → debt); trend/comparison absence (**Structural** — backend-gated); `.mgrempty` positive green reused for neutral no-data empties (cashier/gl-accounts) (**Typography/semantic** — debatable, 2B-1 kept `.mgrempty` distinct → debt); header/tiles spacing tokenizable value-identically (**Token cleanup** — hygiene only, no UX value).

## Changes / KEEP rationale

**No code change.** The allowed-polish levers are already at target or unavailable safely:
- KPI hierarchy — already dominant (31px/800 tabular).
- Numeric alignment — already tabular + right-aligned + fixed columns.
- Active-filter clarity — already the accent-highlighted `.segment` primitive.
- Empty-state consistency — `.mgrempty` is a deliberate positive semantic (2B-1); reclassifying neutral empties needs a design judgment + risks misreading intent.
- Trend/comparison — **prohibited** (needs backend calculation/query).
- Tile-grid orphan — grid change is unverifiable-without-rendering and would break the GL panel.
- Spacing tokenization — value-identical hygiene, not a UX change; manufacturing it into a UX sprint is inappropriate.

## Primitive reuse

Already applied — `.segment`/`.segment-group` (filters, 2B-5), `.button` (export, 2B-4), `.tile`/`.mgrcard` (dashboard-specific, correctly distinct). No hand-rolled chrome maps to an unused approved primitive; `.mgrempty` is the deliberate positive empty (not `.empty-state`). No new primitive invented.

## Screenshots / failure log

CDP has frozen on the heavy `pos.html` across every 3.x sprint (script-injection timeout); the freeze persists. Classification is **KEEP (zero visual change)** → no before/after to compare, no visual gate required. Known-freeze recorded; further attempts would be futile round-trips.

## Computed-style verification

N/A — no style changed (identity).

## DOM / JS / CSS delta

**0 / 0 / 0** — no code file modified (documentation only).

## Interaction verification

N/A — no handler/render/DOM change. Filtering (segments), sorting (pre-sorted), date-range selection, CSV export, mode switch byte-identical (untouched).

## Theme verification

N/A — no style changed; existing light/dark preserved.

## Business verification

KPIs, calculations (net/avg derivations), filters, exports, sorting, aggregation, and backend payloads **unchanged** — no code touched.

## Performance impact

Zero — no code change.

## Remaining UX debt (deferred)

- **Trend/comparison** deltas on KPI tiles (period-over-period) — needs backend/calculation.
- **5-tile grid balance** for the Sales panel — needs a panel-scoped grid + visual sign-off (avoid narrowing tiles / GL breakage).
- **Empty-state semantics** — neutral no-data empties (cashier/gl-accounts) currently render in positive green `.mgrempty`; consider neutral `.empty-state` (design decision).
- **Loading/offline** report states (skeleton / "connect to view") — needs render additions.
- **Interactive column sort / sticky headers** for large tables — structural.
- Header/tiles **spacing tokenization** — value-identical hygiene pass.
- CSV button label is static "Export refunds CSV" (verify intent in GL mode) — content/behaviour, out of bounds.
- Accessibility (`aria-live` on KPI refresh, table semantics) → Accessibility Sprint.

## STOP-condition result

**None tripped** — no report-calculation / chart-rendering / dashboard-recomposition / backend change needed. Classification **A — KEEP**; no C/D proposal required.
