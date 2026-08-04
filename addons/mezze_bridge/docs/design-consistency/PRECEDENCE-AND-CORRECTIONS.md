# Precedence & Corrections to the Previous Audit

## Authority precedence (as directed)
1. **Original foundation documents** (`/Downloads/Mezze POS Visual Redesign/export`) — PRIMARY.
2. Explicit later revision **inside the same source** ("v2/revised/supersedes") — none found; all foundation docs are stamped v1.0/frozen.
3. Export **screen/pattern** documents — how the system manifests.
4. Repo `docs/DESIGN_SYSTEM.md` — a *downstream translation*, **not** superior to 1–3.
5. Current production code — tells us *what exists*, not what it *should be*; it is the **migration target**.

## The previous audit was WRONG on precedence — corrected here
My earlier `docs/design-audit/` treated `docs/DESIGN_SYSTEM.md` + `pos.html` as
authoritative. **Reversed.** The original export is authoritative; `DESIGN_SYSTEM.md`
and `pos.html` have measurable drift from it. Specific corrections, all from the source:

| Aspect | Original source (authority) | Repo `DESIGN_SYSTEM.md` (drift) | Verdict |
|---|---|---|---|
| **Brand color** | **Terracotta `#C0602E`** (light) / `#D89A54` (dark) | amber `#E0982B` / `#EFA23C` | `DESIGN_SYSTEM.md` + all production accents (`--accent`/`--saffron`/`--acc`) **drifted off-brand** |
| **Interface font** | **Hanken Grotesk** | `system-ui, -apple-system, Segoe UI, Roboto` | drift; `kiosk.html`/`onboarding.html` (Hanken Grotesk) are **closer to source** than `pos.html` |
| **Arabic font** | **IBM Plex Sans Arabic** | Noto Kufi Arabic | drift; kiosk/onboarding (IBM Plex Arabic) **closer to source** |
| **Numeric font** | JetBrains Mono | `ui-monospace, SF Mono, JetBrains Mono` | ~ok |
| **Spacing scale** | 0/2/4/6/8/12/16/20/24/32/**48/72** | 4/8/12/16/20/24/32/**40** | `DESIGN_SYSTEM.md` invents `40`, omits `2/6/48/72` |
| **Spacing primitive** | **4px lattice on 8px base** (both, precisely) | "4px base" | source is richer/precise |
| **Radius scale** | 8 / **11 / 14 / 16** / pill (max 16) | 8 / **12 / 18 / 24** / pill | drift; source radii are tighter; qr/onboarding `16` matches `--mz-radius-xl` |
| **Token namespace** | **`--mz-`** (primitive→semantic→component) | ad-hoc `--accent/--canvas/…` | adopt `--mz-` |
| **Elevation** | E0–E4 luminance-first, no decorative shadow | `--shadow-sm/md/lg/accent` | reconcile to E0–E4 |
| **Motion** | dur 80/120/180/240/320; 4 named eases | dur 130/160/220; 2 eases | adopt source motion |

**Net:** production did NOT override the original because it was "newer/better" — it
simply **drifted** (independent per-file token vocabularies). `pos.html` is a *good but
non-authoritative* implementation that itself drifted on brand color and fonts. The
authority is the original export, extracted in `AUTHORITATIVE-DESIGN-SYSTEM.md`.

## Design-source conflicts
None substantive **within** the source: all foundation docs are internally consistent
and cross-reference each other ("integrates with the frozen Design/Motion/Typography
systems"). The only conflicts are **source ↔ production**, catalogued above — resolved
in favor of the source.

## Implication for prior increments
- **DESIGN-P1 (rc2)** shipped *accessibility* fixes (focus/dialog/aria/reduced-motion)
  that are **fully consistent** with the source's AA contract — they stand, unaffected
  by these corrections. No brand/token values were changed in DESIGN-P1, so nothing
  needs reverting.
- The prior audit's *structural* recommendation (one shared token layer, consolidate
  components) is **correct and reinforced** — but the token *values* must come from the
  original source (terracotta, Hanken/IBM Plex/JetBrains, 4px/8px, 8/11/14/16), **not**
  from `DESIGN_SYSTEM.md`.
