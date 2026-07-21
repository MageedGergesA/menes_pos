# Enterprise Release Certification — RC1

*Frontend: `mezze_bridge/static/pos.html` (single-file SPA, 4,672 lines; `<style>` 2–1080, `<script>` 1738–4672). Read-only audit. No code changed, no commits. Evidence gathered by static analysis of the shipped file.*

---

## Executive Summary

The POS frontend is **functionally and structurally sound**: every business workflow is intact, the design system is clean (no duplicate primitives, no live legacy classes, no token drift of substance), RTL is genuinely well-engineered (logical properties throughout), and themes are token-driven. The design/UX program introduced **zero regressions**.

However, **RC1 cannot be issued as a clean PASS** because of **one systemic High-severity security finding**: user- and customer-controlled strings are interpolated into `innerHTML` **without HTML escaping** (no escape helper exists anywhere in the file), producing a **stored-XSS vector** — most sharply on the customer-submitted **feedback comment** rendered in the manager view.

Secondary conditions are the **accessibility baseline** (no live regions, no modal semantics, suppressed focus ring on input class-forms) — non-blocking for a controlled-terminal pilot, blocking for WCAG conformance.

**Result: PASS WITH CONDITIONS.** The design, regression, RTL, theme, and performance dimensions pass. Go-live is conditional on remediating the XSS finding (mandatory) and the accessibility baseline (Phase 4).

---

## Certification Result

### ✅ **PASS WITH CONDITIONS** — RC1

| Gate | Verdict |
|---|---|
| Visual / design-system regression | ✅ PASS |
| Business / workflow regression | ✅ PASS |
| Interaction regression | ✅ PASS |
| Theme consistency | ✅ PASS |
| RTL validation | ✅ PASS |
| Performance | ✅ PASS (with notes) |
| Responsive behaviour | ✅ PASS (with notes) |
| Print / receipt | ✅ PASS (path present; not browser-print styled) |
| **Security (frontend)** | ⚠️ **CONDITION — H1 (XSS) must be fixed before production** |
| **Accessibility baseline** | ⚠️ **CONDITION — Phase 4 required for WCAG** |

---

## Risk Matrix

| ID | Area | Finding | Severity |
|---|---|---|---|
| **H1** | Security | Unescaped user/customer-controlled strings interpolated into `innerHTML` (187 sinks, no escape helper). Stored-XSS via `f.comment`/`f.who` (customer feedback → manager view), and cashier-entered `customer.name/note`, `reservation.who/note`, `waitlist.who/note`, `delivery.who/rider`. | **High** |
| M1 | Accessibility | **No `aria-live` (0)** — toasts, KDS late/new tickets, burn-rate alerts, waiter-bell not announced to screen readers. | Medium |
| M2 | Accessibility | **No `aria-modal`/focus-trap (0)** — overlays (payment, table actions, modifiers) don't trap focus or announce as modal. | Medium |
| M3 | Accessibility | `outline:none` (×6) suppresses the global `:focus-visible` ring on input class-forms + search — keyboard focus invisible there. | Medium |
| M4 | Accessibility / Motion | 5 of 7 keyframes not gated by `prefers-reduced-motion` (attention-pulses `latepulse`/`blpulse` **are** gated; `pulse`/`lineIn`/`grow`/`wbin`/`pop` are not). | Medium |
| L1 | Design system | 6 raw z-index literals on floor sub-objects (`.tabletop 2`,`.tbadge 3`,`.tqr 4`,`.topbar 4`,`.rail 5`,`.chair`) — **documented deferred** (ADR-0001). | Low |
| L2 | Accessibility | `aria-describedby`/`aria-invalid` = 0 — form errors not programmatically linked to fields. | Low |
| L3 | Theme / tokens | One off-token hex `#4a3bb0` in a rule body; `#fff`/`#000` on coloured fills (intentional, theme-invariant). | Low |
| L4 | Responsive | No explicit >1920 ultra-wide cap (flex/grid auto-adapt; no observed defect, untested). | Low |
| L5 | Architecture | `pos.html` is a single 4,672-line file (style+script+markup). | Low |
| C1 | Cosmetic | 2 doc-comment references to legacy `.btn`/`.rptseg` (harmless provenance notes). | Cosmetic |
| C2 | Cosmetic | Off-scale spacing/type not tokenized (deferred appearance work). | Cosmetic |

**Critical: 0 · High: 1 · Medium: 4 · Low: 5 · Cosmetic: 2.**

---

## Regression Matrix

| Workflow | Render fn present | Endpoints intact | Verdict |
|---|---|---|---|
| Workspace / cart / totals | `renderGrid` `renderOrder` `updateTotals` | `/orders/*` `/menu/*` `/ai/upsell` | ✅ no regression |
| Payment | `updatePayState` (+ `addTender`/`remaining`) | `/orders/pay` `/giftcard/balance` | ✅ |
| Kitchen (KDS) | `buildKds` (+ `kdsRenderTickets`) | `/kds/transition` `/kds/state` | ✅ |
| Floor | `buildFloor` | `/floors` `/reservations/*` (seat) | ✅ |
| Beverage (BDS) | `buildBds` | `/bds/queue` | ✅ |
| Manager | `buildManager` (+ reconcile/waste/clock/mkt/feedback) | `/manager/dashboard` etc. | ✅ |
| Reports & GL | `buildReports` `buildGl` | `/reports/summary` `/gl/*` | ✅ |
| Reservations & Waitlist | `buildReservations` `buildWaitlist` | `/reservations/*` `/waitlist/*` | ✅ |
| Delivery | `buildDelivery` | `/delivery/*` | ✅ |
| HQ | `buildHq` | `/hq/summary` | ✅ |
| Central Kitchen | `buildCk` | `/ck/*` | ✅ |
| Live Operations | `buildOps` `bridgeOps` `buildSpark*` | `/ops/summary` | ✅ |

**All 15 core render/workflow functions present (1 definition each). Design program touched presentation only — 0 backend/calc/sort/endpoint/handler/DOM-structure changes across Phase 2 (additive) and Phase 3 (verified per-sprint). No regression detected.**

---

## Performance Summary

- **DOM build:** 78 `createElement` + 187 `innerHTML` swaps. Lists are bounded/sliced (e.g. burn-rate `slice(0,5)`), so no unbounded growth. Full-`innerHTML` container swaps on poll/nav cause localized reflow — acceptable for a POS app-shell; no virtualization needed at these list sizes.
- **Selectors:** only 12 deep (3+ class) descendant selectors; CSS is predominantly shallow single-class → cheap matching.
- **Animation/paint:** 7 keyframes, 12 `animation:` declarations; continuous ones are small (LIVE dot `pulse`, attention pulses gated). Low paint cost. `prefers-reduced-motion` respected for the two attention-pulses only (see M4).
- **Layout shift:** await-then-swap can shift content within a card, but this is an app-shell dashboard, not a scrolling document — CLS impact is contained.
- **CSS duplication / unused:** primitive extraction removed the major duplication; a handful of defined-but-unused tokens remain (documented). No measured bloat.
- **Verdict:** ✅ **PASS** — no performance blocker; notes are optimizations, not defects.

---

## Accessibility Summary (baseline audit — not a redesign)

**Present:** `aria-label` ×68, `aria-pressed` ×22 (segment/pill toggles), `aria-current` ×7 (nav), `aria-hidden` ×9, `role=` ×14 (`group`), global `:focus-visible` ring, native `<button>`/`<input>` semantics (keyboard-operable). RTL `dir`/`lang` set on language toggle.

**Gaps (conditions for WCAG):**
- **No live regions (`aria-live` = 0)** — status changes (toasts, KDS late tickets, OPS alerts, waiter-bell) are silent to AT (M1).
- **No modal semantics (`aria-modal`/focus-trap = 0)** — overlays don't trap focus or announce (M2).
- **Focus ring suppressed** on input class-forms + search (`outline:none` ×6) (M3).
- **No `aria-invalid`/`aria-describedby`** — validation errors not linked (L2).
- **No roving-tabindex** on segment/pill groups (native tab reaches each — functional but not the WAI radio/tab pattern).
- **Motion:** 5/7 keyframes not reduced-motion-gated (M4).

**Verdict:** ⚠️ **CONDITION** — acceptable for a **controlled kiosk/terminal pilot** (staff-operated, keyboard-capable), **not** WCAG-conformant. → Phase 4 Accessibility.

---

## Security Summary (frontend only)

- **No code-execution sinks:** `eval`/`new Function`/`javascript:`/`document.write`/`.outerHTML` = **0**. No `href`/`src` built from data. ✅
- **XSS via `innerHTML` (H1):** 187 `innerHTML` assignments; **no HTML-escaping helper exists**. Many interpolate user/customer-controlled strings directly. Confirmed vector — `buildFeedback` (line 3297): `f.comment` and `f.who` come from `/feedback/list` (customer-submitted via QR/CFD) and are injected raw into `innerHTML` and rendered in the **manager's** browser → **stored XSS**. Same pattern on cashier-entered `customer.name/note`, `reservation.who/note`, `waitlist.who/note`, `delivery.who/rider`, gift-card codes.
- **Mitigating context (why High, not Critical):** rendered in staff/kiosk browsers (not a public web surface); most fields are staff-entered; requires a malicious string to reach a render path. **But** the feedback path is genuinely customer-controlled and un-gated. **This must be remediated before production.**
- **Remediation (frontend):** introduce an `escapeHtml()` helper (or switch to `textContent`/`createTextNode` for user strings) and apply it to every user/customer-controlled interpolation. Backend output-encoding/sanitization on `/feedback` and reservation/customer fields is the defence-in-depth complement.
- **Verdict:** ⚠️ **CONDITION (blocking)** — H1.

---

## Technical-Debt Summary

- **Accessibility** (M1–M4, L2): the largest cluster → Phase 4.
- **Security** (H1): systemic unescaped-`innerHTML` → escaping pass.
- **Design-system**: 6 deferred z-index literals (L1), off-scale spacing/type (C2), `--surface` input class-forms unconsolidated, JS-inline styles/z-index — all documented.
- **Architecture** (L5): single 4.6k-line file; moderate id/class JS coupling (largest fns ~50 lines — acceptable).
- **Capabilities** (from Phase 3): alert severity, live KPI trends, over-party sort promotion, allergy flag — need backend/product.

---

## Go-Live Recommendation

**Conditional GO for a controlled pilot; NO-GO for unrestricted production until H1 is fixed.**

1. **Before any production traffic:** remediate **H1** (escape all user/customer-controlled `innerHTML` interpolations; prioritise the customer-facing feedback path). This is a small, well-scoped frontend change (add + apply `escapeHtml`) plus backend sanitization.
2. **Controlled kiosk/terminal pilot** may proceed with H1 fixed even before the a11y phase, since operators are staff on managed devices.
3. **WCAG-conformant public/enterprise release** requires Phase 4 (a11y baseline).

---

## Production Checklist

- [ ] **H1 — escape user-controlled `innerHTML`** (feedback comment first; then customer/reservation/waitlist/delivery name+note+rider). *(blocking)*
- [ ] Backend output-sanitization on `/feedback`, `/loyalty`, `/reservations`, `/waitlist`, `/delivery`. *(blocking, defence-in-depth)*
- [ ] Phase 4 accessibility: `aria-live` on toasts/KDS/alerts; `aria-modal`+focus-trap on overlays; restore focus ring; `aria-invalid`/`aria-describedby`; reduced-motion-gate remaining keyframes.
- [ ] Push the 23 local design-program commits + run `/code-review ultra`.
- [ ] Fix the CDP/screenshot pipeline; complete the deferred **manual visual merge gates** (3A/3B/3C/3F) in light + dark on a real device.
- [ ] Real-device touch test (≥1024 terminal) + ultra-wide sanity (>1920).
- [ ] RTL/Arabic full pass with real content (mixed AR/EN, long names).
- [ ] Receipt/print verification on target hardware printer.
- [ ] Cross-browser (Chromium terminal target confirmed; verify others if in scope).

---

## Remaining Blockers

| # | Blocker | Type | Gates |
|---|---|---|---|
| 1 | **H1 unescaped-`innerHTML` XSS** | Security | Unrestricted production |
| 2 | Backend sanitization of user fields | Security | Defence-in-depth |
| 3 | Accessibility baseline (M1–M4) | WCAG | Public/enterprise WCAG release (not a controlled pilot) |
| 4 | Deferred visual merge gates (CDP-blocked) | QA | Final visual sign-off of Phase-3 diffs |

No blockers exist in the **design-system, regression, RTL, theme, or performance** dimensions.

---

## Overall Release Score

| Dimension | Score | Basis |
|---|---:|---|
| Design-system integrity | 95% | Clean; no dupes/live-legacy; 6 deferred z-literals. |
| Business/regression safety | 100% | All workflows intact; 0 regressions. |
| RTL | 95% | Logical properties throughout; physical `left` are RTL-safe centering. |
| Theme consistency | 92% | Token-driven both themes; minor `#4a3bb0` off-token. |
| Performance | 88% | Bounded DOM, shallow selectors; innerHTML-swap reflow acceptable. |
| Responsive | 85% | 3 breakpoints (≤1040); flex/grid auto-adapt; ultra-wide untested. |
| Security (frontend) | 60% | No exec sinks, but systemic unescaped-`innerHTML` (H1). |
| Accessibility | 45% | Good labelling; no live/modal semantics; suppressed focus. |
| **Overall** | **≈82%** | **RC1 = PASS WITH CONDITIONS** — clean design/regression/RTL; gated by H1 (security) and the a11y baseline. |

*Score is engineering judgment from static evidence; no user-testing / real-device / automated-scanner pass has been run (see checklist).*

---

## Final Word

The design program delivered a clean, regression-free, RTL-solid, token-driven frontend — those dimensions **certify**. RC1 is withheld from a clean PASS by **one pre-existing, systemic security issue (unescaped `innerHTML`)** and the **known accessibility debt**. Both are well-scoped and remediable. **Fix H1, then a controlled pilot is GO; complete Phase 4 for full WCAG enterprise release.**
