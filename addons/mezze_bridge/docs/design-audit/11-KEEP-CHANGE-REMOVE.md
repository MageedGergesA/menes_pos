# 11 — Keep / Refine / Replace / Remove

For each major current pattern, with evidence. Classifications: **KEEP** (working,
don't touch) · **REFINE** (good, needs consistency/polish) · **REPLACE** (rework the
approach) · **REMOVE** (drop).

| Pattern | Verdict | Evidence / rationale |
|---|---|---|
| Warm amber-on-warm-neutral palette | **KEEP** | Distinctive, restaurant-warm, not cold-SaaS; matches brand/voice. Just unify the token. |
| `DESIGN_SYSTEM.md` as source of truth | **KEEP** | Coherent, measured, accessibility-aware. Make it enforced, not just documented. |
| `pos.html` design language (cards, KPI, status stripe, tabular numbers) | **KEEP** | Scores 80; the target for every other surface. |
| Payment family hierarchy + confirmation discipline | **KEEP** | Strongest error-prevention (78, EP 4–5). |
| KDS ticket design | **KEEP** | Distance-readable, restaurant-appropriate (80, RD 5). |
| Per-file token vocabularies (`--saffron`/`--acc`/`--bg`…) | **REPLACE** | 3 vocabularies; extract one shared token layer. Root cause of most drift. |
| Button implementations (`.btn/.primary/.addbtn/.svcbtn/.startbtn/.review/.pay*`) | **REPLACE** | ≥4 implementations → one component. |
| Modal/sheet semantics (only `pos.html` sets `role=dialog`) | **REPLACE** | One accessible modal component. |
| Radius usage (16 values) | **REFINE** | Snap to DS 5-step scale; keep the rounded-but-restrained feel. |
| Type scale (re-inlined per file) | **REFINE** | Adopt shared `--text-*`; keep the DS 10-step scale. |
| Font identity (two families) | **REFINE** | Pick one Latin+Arabic pair product-wide. |
| Theme system (12 themes / 5 accents, D1) | **KEEP ALL for now** (structure = **RESTRUCTURE later**) | Do not remove themes this task. But the token divergence means themes only fully work on `pos.html`; once the shared token layer lands, re-evaluate whether all 12 earn their keep (see below). |
| Dark mode | **REFINE** | Complete it on kiosk + onboarding; audit for muddy near-identical dark surfaces. |
| Elevation/shadow (ad-hoc outside pos) | **REFINE** | Adopt `--shadow-sm/md/lg`; prefer border+surface over shadow (POS should feel stable, not floaty). |
| Iconography (line icons, but unnamed icon buttons) | **REFINE** | Keep the family; label icon-only buttons; confirm one icon set. |
| Staff nav (14 flat destinations) | **REFINE/RESTRUCTURE** | Tier + profile-gate; don't remove capability, reduce always-visible surface. |
| Demo affordances in production chrome | **REMOVE** (gate behind demo/debug) | "Toggle offline demo", "Replay tour" shouldn't ship in production chrome. |
| Customer channels as separate token islands | **RESTRUCTURE** | Shared customer shell/token layer so the journey is one product. |
| `onboarding.html` ad-hoc palette + zero a11y | **REFINE** (adopt DS) | Bring the S5 admin console onto the shared tokens + a11y contract. |

## Theme count recommendation (report only — do NOT change themes now)

**Direction: RESTRUCTURE, not remove.** The 12-theme / 5-accent registry is a
strength *for pos.html* but is not honored by the other 8 surfaces, so its product
value is currently partial. Recommended sequence: (1) land the shared token layer so
themes apply everywhere; (2) then decide `KEEP ALL` vs `REDUCE` based on real usage —
likely keep **Classic + High-Contrast (light) + Midnight + High-Contrast (dark)** as
first-class and demote the rest to "extra" until they're validated across all surfaces
for contrast/state integrity. No themes are removed in this audit.

## Navigation recommendation

**REFINE (tier + gate), do not rebuild.** Keep every capability; change only
prominence: Sell (primary) / Manage (secondary) / Configure (tertiary), with
format-specific workspaces gated by the S5 commercial profile.

## Component strategy

**Consolidate to a shared component + token layer** imported by all `static/*.html`
(button, badge/status, card, input, sheet/modal, qty stepper). This is the backbone
of P1 in the roadmap and removes most duplication + a11y gaps at once.
