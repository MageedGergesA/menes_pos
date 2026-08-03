# Mezze POS — Product-Wide Design Audit Report

**Audit only. No production code, CSS, component, template, route, manifest, test, or
release tag was modified.** Release under audit: `mezze-v1.0-rc1` (`ad32f3e`) — frozen
and unchanged. Design scores here are **separate** from and do not alter the
software/commercial readiness scores (software = 403/0/0; RC certified).

## Executive verdict

Mezze contains a genuinely strong, coherent, accessibility-aware design system
(`docs/DESIGN_SYSTEM.md`) that is **fully realized in exactly one surface**
(`pos.html`, the design reference). The production cashier Owl app and the customer,
kiosk, admin, and secondary surfaces each carry **independent token vocabularies,
type scales, radius values, and (mostly absent) accessibility instrumentation**. The
product's design problem is not taste or layout — the workflows and hierarchy are well
designed — it is **propagation and consistency**: one excellent system + eight
design-debt islands. There are **no P0 (financial/operational) design defects**; the
money surfaces are the strongest. The highest-leverage work is a shared token +
component + accessibility layer, then screen-level improvements on that foundation.

## Design readiness scores (design only)

| Dimension | Score |
|---|---:|
| Design System Coherence (system quality × application breadth) | **62%** |
| Staff UX | 74% |
| Customer UX | 60% |
| Cashier Speed UX | 78% |
| Restaurant Operations UX | 74% |
| KDS UX | 80% |
| Delivery UX | 63% |
| Kiosk UX | 69% |
| Admin UX | 60% |
| Accessibility Baseline | 58% |
| Arabic / RTL | 65% |
| Responsive | 72% |
| Visual Polish | 70% |
| Enterprise Quality | 70% |
| **MEZZE DESIGN READINESS (weighted)** | **≈68%** |

**Target after roadmap: ≈90%** (P1 system consistency + accessibility parity alone
lifts the floor from 56–60 to ~75+ on the debt surfaces).

## The five highest-impact changes

1. **Shared token layer** — extract the DS `:root` into one stylesheet imported by
   every `static/*.html`; unify the triplicated accent. (Roadmap S1)
2. **Accessibility + contrast parity patch** — focus rings, icon-button labels, dialog
   semantics, live regions, reduced-motion, muted-tier contrast. (S2+S3)
3. **One button / status-badge / modal / qty-stepper component set.** (S4)
4. **Tier + profile-gate the 14-item staff nav.** (H1)
5. **Shared customer shell** so pickup↔delivery↔payment is one product. (H2)

## Highest-risk & highest-opportunity screens

- **Highest-risk (design):** the **Onboarding / Go-Live console** (`onboarding.html`)
  — lowest score (56), zero focus/ARIA, off-DS palette; it's the first screen a new
  operator meets and it's the weakest.
- **Highest-opportunity:** the **production cashier `/mezze/pos`** (Owl) — highest-use
  staff screen, currently drifting from the `pos.html` reference (75 vs 80); closing
  that gap has the biggest operational ROI. Product-wide, the shared token layer is the
  single biggest opportunity.

## Recommended design direction (one sentence)

> Make Mezze **operationally calm, warm-but-restrained, touch-first, financially
> explicit, restaurant-native, Arabic-equal, and enterprise-consistent** — by
> propagating the existing `pos.html` design system to every surface through one shared
> token + component + accessibility layer, before any screen-level restyling.

## Recommended first implementation increment

Ship **S2 + S3 (accessibility + contrast parity)** as one small, low-risk patch
(focus rings, ARIA, dialog semantics, reduced-motion, muted-contrast) across kiosk /
onboarding / shop / qr; then **S1 (shared token layer)**. Do not start screen-level
(P2) work until S1 lands. Any production change ships as `mezze-v1.0-rc2+` after full
regression + EN/AR + light/dark browser acceptance — never by moving `rc1`.

## Method & honesty notes

- Evidence = source reading + grep quantification + browser `read_page` on the running
  app. **Screenshots were intermittently blocked by tooling instability**, and the four
  parallel evidence subagents stalled on the same backend issue; findings were gathered
  first-hand instead. ~10 of ~50 screens were browser-structure-observed; the rest are
  `SOURCE` or `NOT OBSERVED` — **no visual PASS was inferred** for unobserved screens.
- Design scores are deliberately conservative for source-only families and should be
  re-validated on real screenshots before acting on the lowest ones.

## Output files
`00-DESIGN-SOURCES` · `01-DESIGN-CONFLICTS` · `02-INFORMATION-ARCHITECTURE` ·
`03-SCREEN-INVENTORY` · `04-COMPONENT-INVENTORY` · `05-TOKEN-AUDIT` ·
`06-SCREEN-SCORECARD` · `07-CONSISTENCY-MATRIX` · `08-ACCESSIBILITY-RTL` ·
`09-TOP-20-ISSUES` · `10-QUICK-WINS` · `11-KEEP-CHANGE-REMOVE` ·
`FINAL-DESIGN-ROADMAP` · this report.
