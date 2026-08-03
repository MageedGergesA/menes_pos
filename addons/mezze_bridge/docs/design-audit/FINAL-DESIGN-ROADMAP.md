# Final Design Improvement Roadmap

Execution planning only — **nothing implemented in this task.** Phases order the work;
they are not a commitment. Every production change later becomes a *targeted design
patch → full regression → browser + Arabic + dark acceptance → new immutable RC if
appropriate*. `mezze-v1.0-rc1` (`ad32f3e`) stays untouched.

Effort: **S** ≤0.5d · **M** ~1–3d · **L** ~1–2wk.

## P0 — Operational / financial UX defects
**None.** No P0 design defects found — the money/operational surfaces are the
strongest design areas. (Do not manufacture P0 work.)

## P1 — System consistency (the backbone; do this first)

| ID | Item | Screens | Components/tokens | Risk | Browser scenarios | AR impact | Dark impact | Effort |
|--|--|--|--|--|--|--|--|--|
| S1 | Extract DS `:root` tokens into ONE shared stylesheet imported by every `static/*.html`; unify accent to one hex/name | all | all `--*` | med (visual regressions) | full smoke each surface | high (re-check EN/AR) | high (re-check all themes) | L |
| S2 | Accessibility parity patch: focus ring on kiosk+onboarding; `aria-label` icon buttons; `role=dialog`/trap on sheets; `aria-live` for cart/pay/KDS; reduced-motion on kiosk+onboarding | all non-pos + pos icons | focus, aria, modal | low | keyboard + SR smoke | med | low | M |
| S3 | Contrast fix: darken customer/kiosk `--mut`; restrict `--ink-3` to ≥14px/bold; differentiate `NOT TESTED`/`N/A` by icon | shop, qr, kiosk, onboarding | color tokens | low | contrast check EN/AR/dark | med | med | S–M |
| S4 | One button + status-badge + qty-stepper + modal component set from shared tokens | all | button/badge/stepper/modal | med | per-surface interaction smoke | med | med | M–L |
| S5 | Radius + type scale snap to DS scale on non-pos surfaces | all non-pos | `--r-*`, `--text-*` | low–med | visual diff | med | low | M |
| S6 | One theming contract (`data-theme` + `prefers-color-scheme`) on all surfaces; complete dark for kiosk+onboarding | kiosk, onboarding, others | theme | med | dark smoke each surface | low | high | M |

## P2 — High-value screen improvements

| ID | Item | Screens | Risk | Effort |
|--|--|--|--|--|
| H1 | Tier + profile-gate the staff nav (Sell/Manage/Configure; format workspaces gated by commercial profile) | pos shell | med | M |
| H2 | Shared customer shell/token layer so pickup↔delivery↔payment is one product | shop, qr, checkout | med–high | M–L |
| H3 | Bring `onboarding.html` fully onto DS tokens + a11y contract; link from Settings | onboarding | low | M |
| H4 | Delivery dashboard: operational board over CRM-table density; clarify new/late/unassigned | delivery | med | M |
| H5 | Enforce 44px min on customer controls; logical-property RTL pass on shop/qr | shop, qr | low–med | M |
| H6 | Remove/guard demo affordances in production shell chrome | pos shell | low | S |

## P3 — Polish (only after structure is correct)

| ID | Item | Effort |
|--|--|--|
| PL1 | Elevation restraint (border+surface over shadow); snap off-scale spacing | S–M |
| PL2 | One icon set + optical-size pass; empty-state consistency | M |
| PL3 | Arabic type tuning (line-height/weight parity, not just taller) | M |
| PL4 | Motion consistency (durations/easing from DS) across surfaces | S–M |

## Recommended FIRST increment

**S2 + S3 (accessibility + contrast parity) as one small patch**, then **S1 (shared
token layer)**. S2/S3 are low-risk, high-integrity wins that also de-risk S1 (you fix
a11y before mass-editing tokens). Do NOT start P2/H-items until the shared token layer
(S1) exists — otherwise you build screen improvements on divergent foundations.

## Guardrails for any later implementation
- One surface at a time; full backend + structural test regression per patch.
- Browser acceptance in EN **and** AR, light **and** dark, on real viewports.
- Never move `mezze-v1.0-rc1`; ship as `mezze-v1.0-rc2+` if a production change lands.
- Preserve all workflows, routes, IDs, classes, handlers (DS implementation note).
