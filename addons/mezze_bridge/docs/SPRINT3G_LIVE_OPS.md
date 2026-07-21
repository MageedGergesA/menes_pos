# Sprint 3G — Live Operations Audit + Bounded Optimization

Baseline / rollback: **`sprint-1-design-foundation`**. No backend / KPI / alert-logic / polling change.

## Decision classification: **A — KEEP** (dashboard) + **E capability finding reported** (alert severity)

The Live Operations dashboard is enterprise-grade for a read-only monitoring surface: KPI strip with ▲/▼ trend deltas, branch/hourly/variance charts (variance carries real red/green severity + directional arrows), soonest-first burn-rate alerts, LIVE indicator. The one substantive gap — burn-rate alerts are uniformly amber with no critical-vs-mild distinction — cannot be fixed within bounds (distinguishing severity **requires defining thresholds** = prohibited alert-logic/product work). It is reported as an **E capability proposal**, not implemented. No harmful, safely-fixable, in-scope defect → **KEEP**. Documentation-only commit.

## Current-state map

- `#view-ops` → `.ops scroll` → `.ophead` (h1 "Live Operations" + `.live` pill + "Today · updated" sub) → `.tiles` KPI strip → `.grid2` (Sales-by-branch bars `#branchbars` | Today-by-hour `.spark`) → `.grid2` (Food-cost variance `#varbars` | Burn-rate alerts `.alerts`/`#alerts`).
- **KPI tile:** `.tl` label (11px caps) + `.tv` value (**31px/800 `.num`**) + `.td` trend (`▲/▼` %, `.up`=pos / `.dn`=crit). (Live mode replaces `.td` with "live · Odoo" — backend has no comparison delta.)
- **Charts:** `.bar` (branch/top-product horizontal bars + `.bv` tabular value), `.spark` (hourly SVG line), `.var` (food-cost variance: centred track, `.vseg` red-over/green-under, directional arrow, `.vv .over`/`.under`).
- **Alert:** `.alert` = surface-2 card, **3px `--warn` left border**, `.aic` warn icon, `.at` title, `.as` sub, `.aeta` (14px/800 tabular warn ETA).
- **Empty:** 3 hand-rolled inline `<div style="color:--ink-3;font-size:13px;padding:8px 0">` (branchbars / varbars / alerts). **Loading:** none (awaits then swaps). **Error:** `bridgeBadge` toast. **Offline:** demo data (no bridge call).

## Situational-awareness audit

| Question | Finding |
|---|---|
| Business health <5s? | Yes — 4 KPIs (31px + ▲/▼ trend), branch/hourly charts. |
| Critical problems <3s? | Partial — variance over-cost is red (clear); burn-rate alerts are uniform amber (severity not glanceable). |
| Prioritize multiple issues? | Alerts soonest-first (position = priority); variance red vs green. |
| Alert severity distinguished instantly? | **No** — all burn-rate alerts identical amber (E finding). |
| "Healthy" recognizable without reading? | Yes — green ▲ trends, green under-cost variance, "No stock-out risk" empty. |

## Information hierarchy

Target 1 critical alerts · 2 KPIs · 3 trends · 4 queues · 5 tables · 6 filters · 7 secondary actions.
Actual: KPIs 31px + trends (#2/#3 strong) · alerts region present but **flat severity (#1 not tiered)** · charts/variance (#4/#5) · no filters (single live view, #6 n/a) · no in-dashboard actions (#7 n/a — navigation via rail). **Deviation: alert severity not tiered — E capability.**

## Alert audit

| Attribute | Value |
|---|---|
| severity | **single tier** (all warn) |
| colour | `--warn` (amber) border + icon + ETA — uniform |
| icon | warning triangle (same for all) |
| label | item · branch / on-hand · rate |
| action | none (informational) |
| dismissibility | none (auto-refreshed) |
| persistence | until stock replenished / below cutoff (`slice(0,5)`) |

- **Urgency based on more than colour?** Only the ETA *text* + sort position differ — colour/icon are constant. Within-list, urgency is **not** encoded by styling.
- **Warning vs critical distinct?** No — there is no critical tier.
- **Alert fatigue likely?** Moderate risk — a homogeneous amber list where a 38-min and a 6-hour stock-out look equally alarming; the manager must read every ETA.
- **Do healthy states dominate?** The empty alert state ("No stock-out risk") is neutral grey — healthy reads as calm. Good.

## KPI audit

`.tv` 31px/800 `.num` (tabular); `.td` trend `▲/▼` with `.up`(pos)/`.dn`(crit). Scannable left-to-right (4-tile grid). Secondary trend line subordinate (12px) to the 31px value. **No issue** (live mode drops the delta → "live · Odoo", a backend-comparison gap, not a layout issue).

## Queue audit

The dashboard surfaces the **burn-rate alert list** and **variance list** (not the kitchen/payment/reservation queues — those live in their own views). Longest/soonest obvious via sort + ETA; over-cost blocked-ness obvious via red variance. Needless noise: low (uniform amber alerts are the only mild noise, tied to the E finding).

## Action audit

Read-only monitoring — **no in-dashboard actions** (drill-down/refresh/filter/export/resolve). Navigation to affected workflows is via the primary `.railbtn` rail. No dangerous actions to isolate. N/A.

## Business dependency map (all PRESERVED — untouched)

`buildOps`, `bridgeOps`, `buildSpark`/`buildSparkFrom`; endpoint `/ops/summary`; KPI writes (`net_sales/tx/avg_ticket/margin`), `top_products`, `foodcost` (`variance_pct`), `burnrate` (`hours_to_out`/`on_hand`/`rate_per_hr`), `hourly`; render targets `#branchbars/#varbars/#alerts/#spark/.tiles`; thresholds/sort (backend). **None modified.**

## State Matrix (unchanged)

| State | KPI | Alert | Primary | Note |
|---|---|---|---|---|
| Healthy | trends ▲ green | "No stock-out risk" grey | (navigate) | variance green |
| Warning | mixed trends | amber alerts (soonest-first) | (navigate) | — |
| Critical | dn trend red | amber alerts (short ETA) — **not visually escalated** | (navigate) | E finding |
| Offline | demo data | demo alerts | — | no bridge call |
| Loading | prior values | prior | — | no skeleton |
| Empty | zeros | inline "No …" (13px) | — | hand-rolled empties |
| Error | prior | prior | — | `bridgeBadge` toast |

## Visual audit

Mostly **No issue**. Findings: alert-severity flatness (**Capability gap → E**); 3 in-card empties hand-rolled at 13px/left vs `.empty-state` 14px/centre (**Typography/consistency** — *not* value-identical; centering may not suit the in-card slot → debt, not a clean polish); header/grid spacing tokenizable value-identically (**Token cleanup** — hygiene).

## Changes / KEEP rationale

**No code change.** The allowed-polish levers are already at target or unavailable safely:
- KPI/trend hierarchy — already strong (31px + ▲/▼).
- Numeric alignment — already tabular (`.tv`/`.bv`/`.aeta`).
- Queue/variance urgency — variance already red/green + arrows; alert sort already soonest-first.
- **Alert severity tiering** — the real win, but requires severity thresholds → **prohibited** (alert-logic/product) → reported as E.
- Empty-state consistency — the 3 inline empties are **not** a value-identical migration (13→14px, left→centre) and centering is debatable in-card → debt, not a safe polish.
- Spacing tokenization — value-identical hygiene, not a UX change.

Manufacturing any would violate "do not manufacture work."

## Primitive reuse

None changed. KPI `.tile`, `.bar`, `.var`, `.spark`, `.alert` are monitoring-specific and correctly distinct. No `.segment`/`.button` (no filters/actions). The 3 inline empties *could* use `.empty-state` but not value-identically (see debt).

## Verification

- **Computed styles:** N/A (no change).
- **DOM identity:** `pos.html` unchanged (git-confirmed) — 0 delta.
- **Interaction / keyboard:** unchanged (no handlers touched; dashboard is read-only + rail nav).
- **Theme:** unchanged (existing light/dark preserved; `buildSpark` re-renders on theme toggle as before).
- **Business behaviour:** KPI calc, alert generation, thresholds, polling, payloads, sort — untouched.
- **Screenshots:** CDP frozen on heavy `pos.html` (persistent); KEEP = zero visual change → no before/after, no gate. Known-freeze recorded.

## DOM / JS / CSS delta

**0 / 0 / 0** — documentation only.

## Business verification

KPI calculations, alert generation/thresholds, polling, backend payloads, event handlers, navigation, sorting — **unchanged** (no code touched).

## Performance impact

Zero.

## Remaining UX debt

- **Alert severity tiering (E — capability):** classify burn-rate alerts by urgency (e.g. `hours_to_out` bands) into critical(red)/warning(amber) with a non-colour cue (icon/inset), so imminent stock-outs are glanceable. **Requires product-defined thresholds + backend severity or an agreed cutoff** — out of Bounded-Polish scope. Proposal: reuse the KDS `.k-late` idiom (crit border + inset ring) for the critical band.
- 3 in-card empty messages → `.empty-state` (design decision on 13→14px + centering).
- KPI trend deltas in **live** mode (currently "live · Odoo") — needs backend comparison data.
- Header/grid spacing tokenization — value-identical hygiene.
- Accessibility (`aria-live` on the alert region for new critical alerts) → Accessibility Sprint.

## STOP-condition result

The substantive improvement (alert severity) triggers the decision gate's **E (capability)** → **STOP on that item**: reported as a proposal, not implemented (would need alert thresholds/backend). The dashboard itself is **A — KEEP** (no harmful, in-scope, safely-fixable defect). No B/C/D change made; no prohibited edit attempted.
