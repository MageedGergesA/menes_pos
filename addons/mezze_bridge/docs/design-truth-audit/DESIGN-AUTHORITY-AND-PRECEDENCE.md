# DESIGN AUTHORITY & PRECEDENCE

## Precedence model (verified, top wins)
1. **Original export design principles + tokens** (`/home/mageed/Downloads/Mezze POS Visual Redesign/export`) — PRIMARY authority. Frozen v1.0; the 5 Freeze Packs are the explicit hand-off gate.
2. **Explicit later operator-approved corrections** — with evidence only. Two such intentional supersessions are established:
   - **Owl (Odoo framework) as the production implementation layer** instead of the export's "framework-free vanilla JS" production layer. The export's tokens/components are CSS-var based (framework-agnostic), so this is an implementation-tech choice, not a design-compliance breach.
   - **The 12-theme / 5-accent registry** (`mezze-design.css`) that adds alternate accents beyond the single terracotta brand — an operator-approved personalization feature (D1 design platform) layered ON the authoritative default (`--mz-brand:#C0602E` remains the default). Not a conflict.
   - **`Mezze POS v3.dc.html` is authoritative for LAYOUT, NOT for tokens** (operator decision, 2026-09-07). See §"The v3 split ruling" below.
3. **Current canonical shared tokens/components** — `static/design/foundation.css` (tokens), `static/design/components.css` (`.mz-btn`, `.mz-status`, `.mz-badge`), `static/mezze-design.css` (theme registry). Verified near-exact reproduction of #1.
4. **Current production implementation** — the Owl cashier + KDS + static customer surfaces.
5. **Historical prototype** — `static/pos.html` (`/mezze/design/pos`). Reference-only; NEVER scored as production compliance.
6. **Old audit / result / signoff reports** — lowest; several are stale (amber-preserved, 100%-non-compliant, "no HC", "403 tests", "10 surfaces").

## Rule
"Newer code" does NOT automatically override the design source. Where production diverges from the export WITHOUT a documented operator-approved decision (e.g. cashier raw-px spacing, kiosk/onboarding misspelled Arabic font, un-built workspaces), the **export wins** and the divergence is design DEBT — not an approved deviation.

## Authority verdict
The export is **PRIMARY AUTHORITY, fully recoverable, internally coherent, and faithfully reproduced at the token layer.** The repo's own *derived* design docs are CONFLICTED among themselves (stale completion/compliance claims); the `project-truth-audit/` set is the most reliable current layer but its page inventory is now stale (missing the Owl KDS). This audit supersedes the stale derived docs for design truth.

---

## The v3 split ruling (operator decision, 2026-09-07)

The Claude Design bundle imported to `docs/design-handoff/` on 2026-09-07 carries its own
`domain-docs/MEZZE_DESIGN_SYSTEM.md`, which declares itself *"Canonical for `Mezze POS v3.dc.html`
… and every screen built in this project"*. Read literally that outranks everything here, so the
conflict was put to the operator rather than resolved in code.

**Measured conflict** — both files are on disk and were read, not recalled:

| | Export (rank 1) | `Mezze POS v3.dc.html` |
|---|---|---|
| Brand accent | `--mz-brand:#C0602E` | `--color-accent:#B5652E` |
| Radius sm / md / lg | `8 / 11 / 14` (+ pill 999) | `6 / 11 / 13` |
| Dark theme | present — `--mz-brand:#D89A54`, `--mz-brand-soft:#3A2E1F` | *"light theme only; no dark mode exists in this product"* |

**Ruling: the export wins on tokens; v3 wins on everything above them.**

* **v3 IS authoritative for**: information architecture, the rail and its role gating, screen
  inventory, layout, component anatomy, states, interaction and copy. Where a screen exists in v3
  and not here, v3 defines what it contains.
* **v3 is NOT authoritative for**: colour, radius, spacing, elevation, type scale, or the set of
  themes. Those keep coming from `static/design/foundation.css`, `static/design/components.css`
  and `static/mezze-design.css`, which remain the verified reproduction of the export.

**Why.** v3's third row is not a restyle, it is a deletion: High-Contrast is an accessibility
feature, certified in DESIGN-P1 (rc2) and re-certified in `design-final/F11-UIUX-CERTIFICATION-REPORT.md`.
Adopting v3's token layer wholesale would retire dark **and** High-Contrast across nine shipped
surfaces and regress a WCAG conformance we hold evidence for — to move a brand hue by roughly one
JND and two radii by 2px and 1px. The export also carries its own dark ramp, so v3's "no dark mode
exists in this product" is not a statement about the brand; it is a statement about the scope of
one prototype file, which was never built to cover the theme axis.

**Consequence for the clone campaign.** A cloned screen is judged on structure, behaviour and copy
against v3, and on colour/geometry against the export. A reviewer finding `#C0602E` where the
prototype shows `#B5652E` is looking at compliance, not drift. Anything that would delete a theme
axis is out of scope for a clone and needs its own decision.
