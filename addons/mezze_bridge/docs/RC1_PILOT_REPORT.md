# RC1 Pilot Report — Mezze POS v2.0.0-rc1

> **STATUS: PRE-PILOT.** Phases 1–2 (prepare, push, tag) are **complete and evidenced below**.
> Phases 3–4 (internal pilot, restaurant pilot) **have not been run.** Sections 3–6 are
> instrumentation and empty result tables awaiting real data.
>
> **No pilot observation in this document is invented.** Any section marked
> `⏳ AWAITING PILOT DATA` contains no findings because no pilot has occurred.
> A General Availability decision cannot be made from this document in its current state.

---

## 1. Deployment Summary ✅ COMPLETE

| Item | Value |
|---|---|
| Version | `v2.0.0-rc1` |
| Commit | `1f80710` |
| Remote | `github.com:MageedGergesA/menes_pos.git` |
| Pushed | `258b255..1f80710 main -> main` ✅ |
| Tag pushed | `v2.0.0-rc1` ✅ |
| Commits in release | 28 (0 merge commits, 0 empty messages, `git fsck` clean) |
| Files changed | 50 |
| Default appearance | **amber** (certified build) |
| Mezze activation | opt-in only — `?appearance=mezze` or `localStorage.mzAppearance` |

### Pre-flight verification (Phase 1) — all passed

| Check | Result |
|---|---|
| Working tree clean | ✅ (3 untracked files not part of release — see §7) |
| Commit integrity | ✅ fsck clean, no merges, no empty messages |
| Served build matches working tree | ✅ byte-identical |
| Font assets serve | ✅ HTTP 200 |
| **Smoke: 5 workspaces × 2 themes × LTR/RTL (mezze)** | ✅ 20/20 combinations |
| JS errors during smoke | ✅ **0** |
| Text clipping | ✅ **0** in all 20 combinations |
| Text below 11px (mezze) | ✅ **0** in all 20 combinations |
| Payment overlay | ✅ clean |
| **Rollback verified (with reload)** | ✅ 7/7 checks |
| **Feature flag verified** | ✅ storage persist, URL override, clear-to-default |

### Rollback drill result ✅

Executed against the live build:

| Probe | Expected | Actual |
|---|---|---|
| `appearance` | `amber` | ✅ `amber` |
| `miIcons` | **0** | ✅ `0` |
| `legacySvg` | ~71 | ✅ `71` |
| `--accent` | `#EFA23C` | ✅ `#EFA23C` |
| `--r-lg` | `18px` | ✅ `18px` |
| `bodyFont` | `system-ui…` | ✅ |
| `charset` | `UTF-8` | ✅ |

**Confirmed operationally important:** clearing the flag **without a reload** reverts colour and spacing but leaves **81 Material Symbols icons in place**. `?appearance=amber` correctly overrides a stored `localStorage` flag — the emergency path works. `ROLLBACK.md`'s reload requirement is verified as necessary, not theoretical.

## 2. Pre-Pilot Baseline (measured, not observed in production)

These are real measurements taken from the built artifact — the yardstick the pilot compares against. **They are not pilot results.**

| Metric | Amber | Mezze |
|---|--:|--:|
| Text elements < 11px — Cashier | 37 | **0** |
| — Kitchen | 29 | **0** |
| — Reports | 18 | **0** |
| — Live Ops | 24 | **0** |
| Text clipped (all workspaces) | 0 | **0** |
| Floor-plan overflow (total px) | 489 | **429** (pre-existing, mezze better) |
| JS errors | 0 | **0** |
| Icon font bytes fetched | **0** | 7,552 (once, cached) |
| `.p86` danger contrast — dark | 3.15 | **2.53** ⛔ |
| `.p86` danger contrast — light | 5.21 | **5.66** |

## 3. Issues Found ⏳ AWAITING PILOT DATA

**No internal or restaurant pilot has been run. This table is empty because there is nothing to report, not because nothing was found.**

| # | Date | Phase | Workspace | Severity | Description | Appearance | Repro | Status |
|---|---|---|---|---|---|---|---|---|
| *(none — pilot not yet executed)* | | | | | | | | |

**Severity definitions for triage:**

| Severity | Definition | Action |
|---|---|---|
| **Critical** | Blocks taking an order, payment, or kitchen fulfilment | Roll back immediately (`ROLLBACK.md` §4) |
| **High** | Workaround exists but slows service materially | Roll back that terminal; fix before GA |
| **Medium** | Cosmetic/annoyance, no service impact | Log for post-GA roadmap |
| **Low** | Nit | Log only |

**Collection scope (per the program brief): release blockers only. No feature requests.**

## 4. Rollback Usage ⏳ AWAITING PILOT DATA

| Date | Terminal | Trigger | Method | Time to revert | Verified (`miIcons===0`) | Outcome |
|---|---|---|---|---|---|---|
| *(none — pilot not yet executed)* | | | | | | |

Rollback was **drilled successfully pre-pilot** (§1). No production rollback has occurred because no production pilot has occurred.

## 5. Performance Observations ⏳ AWAITING PILOT DATA

Static/desktop measurements exist (§2), but **the meaningful numbers must come from real POS hardware under service load** — desktop Chrome on a dev machine is not representative.

| Metric | Baseline (desktop) | Pilot (real terminal) |
|---|--:|---|
| First paint | not measured on target HW | ⏳ |
| Font load time (mezze, cold) | 7,552 B icon + lazy text faces | ⏳ |
| Interaction latency (tap → visual) | ⏳ | ⏳ |
| Frame rate during scroll | ⏳ | ⏳ |
| Memory over a full shift | ⏳ | ⏳ |
| Offline behaviour | ⏳ | ⏳ |

**Collect with:** `performance.getEntriesByType('navigation')`, `performance.getEntriesByType('resource').filter(r => r.name.includes('/fonts/'))`.

## 6. Accessibility Observations ⏳ PARTIALLY MEASURED

**Measured pre-pilot (real):**

| Finding | Status |
|---|---|
| Sub-11px text eliminated under mezze (37/29/18/24 → 0) | ✅ improvement |
| Focus rings unchanged (8 `outline` declarations) | ✅ |
| `aria-label` 63 / `role` 16 unchanged | ✅ |
| Icons explicitly `aria-hidden` under mezze | ✅ improvement |
| Reduced motion: token-level + manual opt-out | ✅ verified live |
| RTL: Arabic font stack, `.mi direction:ltr`, rail mirrors | ✅ verified live |
| Charset fix restores all Arabic rendering | ✅ |
| **Dark danger contrast 2.53:1** | ⛔ **BLOCKER 1** |
| `warn/warn-soft` 2.86:1 | ⚠️ pre-existing |
| Touch targets < 44px (10 elements) | ⚠️ pre-existing |

**⏳ Awaiting pilot:** real-operator legibility under service lighting, glare and speed; screen-reader use if applicable; whether the 11px floor genuinely helps or the tighter mezze spacing offsets it; density-mode preference from actual staff.

## 7. Known Release Blockers (unchanged — engineering not authorized to solve)

| # | Blocker | Evidence | Owner |
|---|---|---|---|
| **1** | **Dark danger contrast 2.53:1** — white on approved dark danger `#E58A82`, below AA 4.5:1. Amber also fails (3.15:1) but the approved colour is lighter, so mezze is worse. Light mode passes in both (5.21 → 5.66). | Measured live, P7 | **Design** |
| **2** | **Violet Delivery CTA `#8A7BF0`** — no counterpart in the approved palette; clashes with terracotta. | Measured live, P7 | **Design system** |

**Documented only. No solution invented.**

**Housekeeping (not blockers):** three untracked files exist in the repo — `CLAUDE.md`, `docs/DESIGN_COMPLIANCE_REPORT.md`, `docs/DESIGN_SYSTEM.md`. They are not part of `v2.0.0-rc1`. Decide whether to commit them separately.

## 8. Pilot Execution Guide

### Phase 3 — Internal pilot

**Enable** (internal terminals only):
```
http://<host>/mezze_bridge/static/pos.html?appearance=mezze
```
or persist: `localStorage.setItem('mzAppearance','mezze')` — then **reload**.

**Per-session telemetry** — paste into the console at end of session:
```js
JSON.stringify({
  appearance: document.documentElement.getAttribute('data-appearance'),
  theme:      document.documentElement.getAttribute('data-theme') || '(system)',
  density:    document.documentElement.getAttribute('data-mz-density') || 'standard',
  dir:        document.documentElement.getAttribute('dir') || 'ltr',
  miIcons:    document.querySelectorAll('span.mi').length,
  fontsLoaded:[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family),
  fontErrors: performance.getEntriesByType('resource')
                .filter(r=>r.name.includes('/fonts/') && r.responseStatus>=400).map(r=>r.name),
  nav:        performance.getEntriesByType('navigation')[0]?.duration,
  ua:         navigator.userAgent
})
```

**Exit criteria:** ≥3 internal users × ≥2 full sessions each, all 5 workspaces exercised, **zero Critical/High issues**, no font 404s.

### Phase 4 — Restaurant pilot (one restaurant)

Only after Phase 3 exit criteria are met **and** blockers §7 are resolved.

**Monitor:** ordering · checkout · kitchen (KDS) · **printing** · **offline/reconnect** · tables/floor.
Printing and offline are the highest-risk areas because they were never exercised in any phase of this program — they involve hardware and network paths no static or browser check can reach.

**Exit criteria:** one full service day, zero Critical, zero rollbacks triggered by appearance, operator sign-off.

### Kill criteria — roll back immediately if

- Any order, payment or kitchen ticket cannot be completed.
- Printing fails or produces incorrect output.
- Offline queue/sync misbehaves.
- Staff cannot read a critical figure (total, table number, order number).

## 9. Final Recommendation for General Availability

### ⏸️ GA CANNOT BE RECOMMENDED YET — insufficient evidence, not negative evidence

Nothing found so far argues against GA. But **no pilot has run**, so the evidence required for a GA decision does not exist. Recommending GA now would mean asserting a safety property I have not tested.

**What is already justified:**

| Decision | Recommendation | Basis |
|---|---|---|
| Ship `v2.0.0-rc1` with **amber default** | ✅ **GO** — done | Amber pixel-identical across 2,510 declarations, verified static + live; rollback drilled; 0 JS errors |
| Begin **internal pilot** with mezze | ✅ **GO** | All Phase 1 gates pass |
| Begin **restaurant pilot** with mezze | ⚠️ **CONDITIONAL** | Only after §7 blockers resolved + Phase 3 exit criteria met |
| **Mezze as default / GA** | ⛔ **NO-GO** | 2 unresolved design blockers + no pilot data |

**GA becomes recommendable when all of these hold:**
1. Blockers §7 resolved by Design.
2. Phase 3 exit criteria met.
3. Phase 4: one full service day, zero Critical issues, operator sign-off.
4. Printing and offline verified on real hardware.
5. §3 contains zero open Critical/High items.

**Until then the correct posture is exactly what has shipped: amber default in production, mezze behind a flag, rollback one reload away.**

---

*Update §3–§6 with real data as the pilots run. Do not fill them speculatively.*
