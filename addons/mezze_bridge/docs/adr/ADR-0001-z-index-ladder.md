# ADR-0001 — The z-index token ladder must describe real layering, not numeric coincidence

- **Status:** ✅ **RESOLVED** — Sprint 2 · Phase 2A · Step 2A-2 (2026-07-20)
- **Date:** 2026-07-19
- **Origin:** Sprint 1 · Step 4 (z-index → tokens)

## Resolution (shipped ladder — values preserved exactly)

The aspirational `--z-base/dropdown/sticky/modal` tokens (unused, mislabelled) were **removed** and replaced with a semantic ladder whose names describe real usage. Sprint 1's `--z-toast:120` was itself a mislabel (it was the notification bell); it was **renamed** `--z-notification:120`, and a correct `--z-toast:80` was introduced for the real `.toast`.

| Token | Value | Selector migrated |
|---|--:|---|
| `--z-floor-object` | 1 | `.chair` |
| `--z-tooltip` | 20 | `.railtip` |
| `--z-hintbar` | 30 | `.hintbar` |
| `--z-flash` | 49 | `.paidflash` |
| `--z-overlay` | 50 | `.overlay` (Sprint 1) |
| `--z-sheet` | 52 | `.sheet` (Sprint 1) |
| `--z-overlay-pay` | 55 | `#ov-pay` |
| `--z-overlay-receipt` | 56 | `#ov-receipt` |
| `--z-menu` | 60 | `.branchmenu` |
| `--z-login` | 70 | `.login` |
| `--z-toast` | 80 | `.toast` (real toast) |
| `--z-onboarding` | 90 | `.welcome` |
| `--z-tour-spot` | 95 | `.tour-spot` |
| `--z-tour-pop` | 96 | `.tour-pop` |
| `--z-notification` | 120 | `.waiterbell` (was `--z-toast`) |

All values identical to baseline → **stacking order invariant** (verified: all tokens resolve to exact values + computed z-index unchanged, light + dark).

**Still deferred (later sprint):** JS-created overlay z-indexes (90/92/93/94/95) and JS-inline `z-index:200` debug bar, plus the not-yet-tokenized floor sub-objects (`.tabletop 2`, `.tbadge 3`, `.tqr 4`) and chrome (`.topbar 4`, `.rail 5`) — these require JS edits or were out of the approved 2A-2 selector scope.

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
