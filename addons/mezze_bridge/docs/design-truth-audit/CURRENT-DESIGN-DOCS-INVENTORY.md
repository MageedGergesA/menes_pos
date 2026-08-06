# CURRENT DESIGN-DOC INVENTORY

Clusters: `docs/design-audit/` (15), `docs/design-consistency/` (24), `docs/project-truth-audit/` (15), `docs/sell-ready/`, ~12 top-level P1–P7 / DESIGN_* docs, `docs/kds/`.

## The two competing authority chains (core conflict)
| Doc | Claim | Class |
|---|---|---|
| `design-consistency/AUTHORITATIVE-DESIGN-SYSTEM.md` | self-declared "PRIMARY authority" from the export; "97% neutral, 3% accent" | CURRENT-AUTHORITY (derived restatement of the export) |
| `DESIGN_SYSTEM.md` | explicitly "NOT the primary visual authority"; export wins on conflict | DERIVED (correct posture) |
| `DESIGN_COMPLIANCE_REPORT.md` | shipped build is "amber #E0982B, system fonts … 100% of surfaces render differently" | **STALE / CONFLICTS** — see verification below |
| `FINAL_DESIGN_SIGNOFF.md` | "Amber Preserved ✅", WCAG "measured live", "Regression ✅" | **STALE / CONFLICTS** (celebrates the amber the compliance report condemns) |
| `P7_VISUAL_CONVERGENCE_RELEASE.md` | "Cashier … ✅ converged" | CONFLICTS (convergence vs "100% divergent") |

**Verification of the amber claim (this audit, direct grep):** `#E0982B` occurs **0×** in cashier, kds, foundation.css, components.css, mezze-design.css, and all 8 customer static files — **only 2× in the excluded prototype pos.html**. Current production is terracotta `--mz-brand:#C0602E` (matches export) with real Hanken/IBM-Plex/JetBrains fonts (browser-executed in the cashier/KDS tests). **Therefore `DESIGN_COMPLIANCE_REPORT.md` and `FINAL_DESIGN_SIGNOFF.md` are HISTORICAL/STALE — they describe a pre-restoration state, not HEAD 96a72e1.**

## project-truth-audit/ (newest, most reliable — 2026-08-05/06)
| Doc | Class |
|---|---|
| `DESIGN-TRUTH.md` | CURRENT-AUTHORITY (corrects P3A/P3B overstatement; prototype-vs-production) |
| `REAL-CASHIER-DESIGN-GAP.md` | CURRENT-AUTHORITY / PARTIAL (measurement only) |
| `STALE-DOCS-AND-CONFLICTS.md` | CURRENT-AUTHORITY (meta: catalogs "403 vs 405", HC contradiction) |
| `KDS-REUSE-DECISION.md` | CURRENT-AUTHORITY (newest) |
| `PROJECT-STATE.md` | CURRENT-AUTHORITY (+ V1/V2A addenda) |
| `CURRENT-PAGE-INVENTORY.md` | **NOW STALE** — "9 static + 1 Owl cashier = 10" predates the Owl KDS (`/mezze/kds`) and the rendered checkout hub |

## P1–P7 / DESIGN_* spec chain
`P1_MEZZE_COLOR_SYSTEM … P7_VISUAL_CONVERGENCE_RELEASE`, `MEZZE_SEMANTIC_COLOR_DECISION_PACK`, `AC1_ACCESSIBILITY`, `DESIGN-P3A/B*-RESULT` — describe the terracotta `--mz-*` target. Classify as **CURRENT-AUTHORITY-as-spec** for tokens/principles, but any "✅ complete/converged" completion phrasing is CORRECT-BUT-INCOMPLETE (design migration done for tokens + P3A/B only) or CONFLICTS (amber-preserved framing).

## kds/
`docs/kds/STATE-MACHINE.md`, `PRODUCTION-UI.md`, `KNOWN-LIMITATIONS.md` — CURRENT-AUTHORITY (this session's V2C).

## Contradictions to resolve (against the export)
1. Amber-preserved/converged (SIGNOFF, P7) vs 100%-non-compliant (COMPLIANCE_REPORT) — **resolved here: both stale; production is terracotta.**
2. Screen count: `CURRENT-PAGE-INVENTORY` (10) vs actual (2 Owl + rendered checkout + 9 static) — stale.
3. "No HC mode exists" (`DESIGN-P3B4-…RESULT.md:104`) vs real HC theme exercised by both browser test files — **false**; HC theme exists.
4. Test count "403" (16+ docs) vs truth 405/now 428 — stale.
