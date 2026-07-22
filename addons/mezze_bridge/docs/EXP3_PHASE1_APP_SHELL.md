# Experience 3.0 — Phase 1: Application Shell

*New program (not part of the closed P1–P7 migration). Rebuild the shell layout onto the approved Mezze Application Shell. Presentation layer only — business logic, APIs, workflows, state, shortcuts preserved.*

**STATUS: implemented, verified, local commit — STOPPED for review before Phase 2 (Cashier), per the brief.**

---

## 1. Objective

Adopt the approved cashier shell geometry:

```
68px rail  |  176px vertical category panel  |  flexible product workspace  |  340px order panel
```

replacing the legacy shell (76px rail | horizontal category strip | 400px order).

## 2. What changed (and what did not)

**Changed — presentation only:**

| Change | Before | After |
|---|--:|--:|
| Rail width (`--rail`) | 76px | **68px** |
| Order panel (`--ticket`) | 400px | **340px** |
| Category panel | horizontal strip inside `.catalog` | **176px vertical column**, own region |
| POS view layout | flex row (`catalog | ticket`) | **3-col grid** `176px 1fr 340px` |
| Category chips | horizontal pills | full-width stacked list items |

**Preserved — verified byte-identical / intact:**

- **JavaScript: byte-identical to `git HEAD`.** No business logic, API, state, or workflow touched.
- All DOM hooks: `#cats`, `#grid`, `#search`, `#view-pos`, `.chip`, `data-view` — unchanged.
- View-switching, keyboard shortcuts, category filtering, product rendering, order panel.
- The other 12 workspaces — untouched (the grid rule is scoped to `#view-pos.active`).

## 3. Implementation

Deliberately minimal — **1 markup line relocated + 5 CSS edits**. No JS.

1. **Markup:** moved `<div class="cats" id="cats">` out of `.catalog` to be the first child of `#view-pos` (so it becomes column 1). One line, cut-and-paste.
2. `--rail: 76px → 68px`, `--ticket: 400px → 340px`, added `--catpanel: 176px`.
3. `#view-pos{flex-direction:row}` → `#view-pos.active{display:grid; grid-template-columns:var(--catpanel) 1fr var(--ticket); grid-template-rows:minmax(0,1fr)}` (scoped by ID so only POS is affected; specificity (1,1,0) beats the global `.view.active{display:flex}`).
4. `.cats` → vertical panel: `flex-direction:column`, `overflow-y:auto`, panel surface + `border-inline-end`.
5. `.chip` → `width:100%`, `justify-content:flex-start`, `border-radius:var(--r-md)`.
6. Responsive `@media(max-width:1040px)` ticket override 360→340px for consistency.

`.chip` is used **only** for categories (verified — single JS creation site, no markup/compound uses), so restyling it is safe.

## 4. Validation — measured live (both appearances)

| Region | Approved | Live (mezze) | Live (amber) | ✓ |
|---|--:|--:|--:|:--:|
| Rail width | 68px | **68** | **68** | ✓ |
| Category panel | 176px | **176** | **176** | ✓ |
| Category orientation | vertical | **column** | **column** | ✓ |
| Order panel | 340px | **340** | **340** | ✓ |
| Product workspace | 1fr | **1910 (1fr)** | **1910 (1fr)** | ✓ |
| POS grid columns | `68 176 1fr 340` | `176 1910 340` + rail 68 | same | ✓ |

**Functional (live):**

| Check | Result |
|---|---|
| JS errors across all 13 workspace switches | **0** |
| Products render | 18 ✓ |
| Categories render (vertical, stacked) | 6 ✓ |
| Category filter (click Coffee) | grid re-rendered 18 → 5 ✓ |
| Active category state | `Coffee` `aria-pressed` correct ✓ |
| Other 12 workspaces | all display, unaffected ✓ |
| amber icons unchanged | 71 SVG / 0 `.mi` ✓ |
| mezze icons | 0 SVG-of-note / Material Symbols ✓ |

## 5. Shell geometry compliance: **100%**

All four region widths and the category orientation match the approved shell exactly. The four-region grid `68 | 176 | 1fr | 340` is in place in both appearances.

## 6. Deferred to later phases (NOT done here — correctly out of Phase 1 scope)

These are approved-shell details that belong to **Phase 2 (Cashier Workspace)** — hierarchy, density, composition — not the shell skeleton:

| Item | Approved | Live now | Phase |
|---|--:|--:|---|
| Rail button size | 46×44 | 64×49 | 2 (density) |
| Category "CATEGORIES" caption (`.mzw__caption`) | present | absent | 2 |
| Product grid padding | 20px (`space-300`) | current | 2 (spacing) |
| Product card min-width | 150px | 134px | 2 |
| Order-panel internal hierarchy | approved layout | legacy | 2 / 3 |
| Category item exact chrome | panel rows | md pills | 2 |

## 7. Note on the amber invariant

The closed P1–P7 program held amber **pixel-identical**. This new program explicitly rebuilds layout and instructs "do not preserve the legacy shell" — so the shell geometry now changes in **both** appearances (amber and mezze share the approved layout). Amber still keeps its own colour/type/icon **tokens** (legacy SVG icons, amber palette); only the **layout** converged. This is the intended behaviour of Experience 3.0, and supersedes the P1–P7 amber-layout invariant by explicit instruction.

## 8. Recommendation

**Phase 1 is complete and correct. Recommend approval to proceed to Phase 2 (Cashier Workspace).**

- Shell geometry matches the approved design 100%.
- Zero business-logic change (JS byte-identical), zero regressions in 13 workspaces, zero JS errors.
- Change is minimal and fully revertible (1 markup move + 5 CSS edits).

**Per the brief, STOPPING here. Not proceeding to Cashier until this is reviewed and approved.**

*Committed locally (not pushed) as a reviewable checkpoint.*
