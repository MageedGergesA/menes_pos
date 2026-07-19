# ADR-0001 — The z-index token ladder must describe real layering, not numeric coincidence

- **Status:** Accepted · deferred to **Sprint 2**
- **Date:** 2026-07-19
- **Origin:** Sprint 1 · Step 4 (z-index → tokens)

## Context

Sprint 1 Step 2 introduced an aspirational z-index token ladder:
`--z-base 1, --z-dropdown 20, --z-sticky 30, --z-overlay 50, --z-sheet 52, --z-modal 60, --z-toast 120`.

Step 4 measured the **actual** layering in `pos.html`:

| Element | z-index | Nature |
|---|--:|---|
| `.chair` | 1 | local floor-plan stacking (not a global "base" layer) |
| `.railtip` | 20 | tooltip |
| `.hintbar` | 30 | fixed bottom hint bar |
| `.overlay` | 50 | modal backdrop / overlay root |
| `.sheet` | 52 | side drawer |
| `.branchmenu` | 60 | dropdown menu |
| `.waiterbell` | 120 | notification |

The token **values** coincide with some literals, but the token **names do not describe the elements**: there is **no dedicated modal layer** (modals render *inside* `.overlay` at 50); `--z-modal 60` actually sits under a *menu*; `--z-base 1` would label a *chair*; `--z-dropdown 20` a *tooltip*; `--z-sticky 30` a *hint bar*. Dynamically-created overlays in JS also use ad-hoc values (92–96).

Migrating by numeric coincidence would produce a **misleading token system** where the name lies about the usage.

## Decision

Only the three tokens whose **name and value both describe the element** were migrated in Step 4 (`--z-overlay`, `--z-sheet`, `--z-toast`). The remaining z-indexes were left as literals.

In **Sprint 2**, the z-index ladder will be **redesigned to describe the real layering architecture** — a small, ordered set of *semantic* layers (e.g. `base / floor-object / popover(tooltip+menu) / fixed-chrome / overlay / drawer / modal-content / notification`), reconciled with the ad-hoc JS overlay values (92–96), then all z-indexes migrated onto it. This is an appearance-neutral REFACTOR (stacking order preserved) but is out of Sprint 1's pixel-identical/token-centralization scope because it involves renaming/redefining tokens and touching JS-inline z-indexes.

## Consequences

- Sprint 1 leaves `.chair 1`, `.railtip 20`, `.hintbar 30`, `.branchmenu 60` as literals (no misleading mapping).
- Sprint 2 owns: define the semantic layer ladder, reconcile JS overlay values, migrate all z-indexes, document the final ordering.
- The aspirational `--z-base/--z-dropdown/--z-sticky/--z-modal` tokens remain defined but **unused** until Sprint 2 reconciles them (may be renamed).
