# DESIGN AUTHORITY & PRECEDENCE

## Precedence model (verified, top wins)
1. **Original export design principles + tokens** (`/home/mageed/Downloads/Mezze POS Visual Redesign/export`) — PRIMARY authority. Frozen v1.0; the 5 Freeze Packs are the explicit hand-off gate.
2. **Explicit later operator-approved corrections** — with evidence only. Two such intentional supersessions are established:
   - **Owl (Odoo framework) as the production implementation layer** instead of the export's "framework-free vanilla JS" production layer. The export's tokens/components are CSS-var based (framework-agnostic), so this is an implementation-tech choice, not a design-compliance breach.
   - **The 12-theme / 5-accent registry** (`mezze-design.css`) that adds alternate accents beyond the single terracotta brand — an operator-approved personalization feature (D1 design platform) layered ON the authoritative default (`--mz-brand:#C0602E` remains the default). Not a conflict.
3. **Current canonical shared tokens/components** — `static/design/foundation.css` (tokens), `static/design/components.css` (`.mz-btn`, `.mz-status`, `.mz-badge`), `static/mezze-design.css` (theme registry). Verified near-exact reproduction of #1.
4. **Current production implementation** — the Owl cashier + KDS + static customer surfaces.
5. **Historical prototype** — `static/pos.html` (`/mezze/design/pos`). Reference-only; NEVER scored as production compliance.
6. **Old audit / result / signoff reports** — lowest; several are stale (amber-preserved, 100%-non-compliant, "no HC", "403 tests", "10 surfaces").

## Rule
"Newer code" does NOT automatically override the design source. Where production diverges from the export WITHOUT a documented operator-approved decision (e.g. cashier raw-px spacing, kiosk/onboarding misspelled Arabic font, un-built workspaces), the **export wins** and the divergence is design DEBT — not an approved deviation.

## Authority verdict
The export is **PRIMARY AUTHORITY, fully recoverable, internally coherent, and faithfully reproduced at the token layer.** The repo's own *derived* design docs are CONFLICTED among themselves (stale completion/compliance claims); the `project-truth-audit/` set is the most reliable current layer but its page inventory is now stale (missing the Owl KDS). This audit supersedes the stale derived docs for design truth.
