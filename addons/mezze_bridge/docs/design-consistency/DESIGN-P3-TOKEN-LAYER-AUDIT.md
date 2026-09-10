# DESIGN-P3 — Token layer audit and semantic-layer promotion

Measured across `addons/mezze_bridge` (16 CSS files + `pos.html`, `kiosk.html`,
`onboarding.html`). Scope: the **token architecture** only — which layers exist, which are
reachable, and which token references resolve. No component was restyled.

## 1. Root cause: the semantic layer existed, but only inside `pos.html`

`AUTHORITATIVE-DESIGN-SYSTEM.md` §2 requires three tiers and states *"primitives … are never
referenced by UI"*. `foundation.css` — the file every bundle loads — shipped **primitives
only**. The semantic tier (`--mz-pad-card`, `--mz-stack-md`, `--mz-gap-grid`, `--mz-touch`, the
`--sp-*` bridge) was declared inside `pos.html`, one 5,000-line surface.

So every other surface was told to consume a layer it could not see. What they did instead:

| Symptom | Count | Where |
|---|---:|---|
| raw `px` literals in consumer CSS | **1,545** | 15 files |
| — of which map exactly onto an existing `--mz-` primitive | 609 | mechanical swap |
| — of which are off the attested scale (10/14/15/18/19/2.5 px…) | 929 | needs a ruling |
| bare hex colors bypassing the 12-theme registry | 93 | `cashier.css` 70, `kiosk-v2.css` 7 |
| invented `--mz-space-125 / 175 / 187 / 225 / 250 / 112` | 6 names, 12 sites | never defined anywhere |

The invented spacing names are the tell: they follow the real convention exactly
(`125` → 10px, `175` → 14px), they were never declared, and every call site passed a `, 10px`
fallback — so they *worked*, and the drift stayed invisible for the life of the campaign.
The attested scale (§5) is **0/2/4/6/8/12/16/20/24/32/48/72**; 10, 14, 15 and 18 are not on it.

## 2. Fixed — token references that resolved to nothing

A `var()` on an undefined property with no fallback makes the whole declaration
invalid-at-computed-value-time: the property silently drops to its initial value. Three shipped:

| Site | Reference | What actually rendered | Fix |
|---|---|---|---|
| `pos.html` `.tp-card` / `.tp-rule` / `.tp-btn` (tip pool) | `var(--surface-1)` — never defined; the file's own `.card` uses `--surface` | `background: transparent` — three bordered-but-unfilled cards and a transparent button on the workspace ground | → `var(--surface)` |
| `cashier.css:1061` `.mz-refund__order` | `padding:var(--mz-space-125) var(--mz-space-150)` | **whole `padding` dropped** → refund-list rows flush to the row edge | → `var(--mz-pad-order-item)` (12px, the attested *order.item* value) |
| `components.css:35` `.mz-btn--primary:hover` | `var(--mz-brand-hover, var(--mz-interactive-hover))` | inner fallback is fiction; only reachable off-theme | → `var(--mz-brand)` |

Addon-wide hard-undefined references: **3 → 0**.

## 3. Done — semantic + component tier promoted into `foundation.css`

Added at bare `:root`. `pos.html` declares the same names on `[data-appearance="mezze"]`,
which is more specific and keeps winning — so this is **pixel-neutral for `pos.html`** and
purely additive for every other bundle.

- **stack / inline** `--mz-stack-sm|md|lg` (8/16/24), `--mz-inline-sm|md|lg` (4/8/12)
- **container padding** `--mz-pad-card` 12 · `-panel` 16 · `-dialog` 20 · `-button` 20 · `-input` 12
- **collection gaps** `--mz-gap-grid` 12 · `--mz-pad-order-item` 12 · `--mz-gap-ticket-group` 16 · `--mz-section` 32 · `--mz-page` 72
- **control geometry** `--mz-touch` 44 / `--mz-touch-lg` 48 · `--mz-control-h-compact|·|-touch` 36/44/50
- **state** `--mz-focus-width` 2.5px · `--mz-focus-offset` 2px · `--mz-disabled-opacity` .45

All pads/gaps are `calc(token * --mz-density)` per §5. Touch targets deliberately are **not** —
a compact density must never take a 44px target below the accessibility floor.

`--mz-disabled-opacity` was named by `CANONICAL-COMPONENT-CONTRACT.md`, consumed by
`components.css`, and defined **only in `onboarding.html`** — every other surface ran on the
`.45` fallback. Same value, now actually declared.

## 4. Open — needs a ruling, not a patch

1. **`--mz-reserved` is a status color outside the registry.** Defined as a bare
   `#8b78d6` in `floor.css:19`, and re-hardcoded as a fallback in `cashier.css:767`
   (the cashier bundle does not load `floor.css`, so the fallback is what renders).
   It is the same violet in all 12 themes including dark and High-Contrast.
   *Reserved* is a restaurant state; it belongs beside `vip/chef/veg/spicy/new/popular`
   in **`gen_design.py:117-118`**, per theme, WCAG-validated — not in a consumer file.
   Editing `mezze-design.css` directly is wrong; it is generated.
2. **929 off-scale px.** `10px` ×22, `14px` ×21, `18px` ×13, `19px` ×14, `12.5px` ×11,
   `2.5px` ×47 (the focus ring — now tokenized as `--mz-focus-width`). Each needs a
   decision: round onto the attested rung, or ratify a new one. Do **not** add
   `--mz-space-125` etc. to legitimize the drift.
3. **Contract names four tokens that do not exist**: `--mz-size-md`, `--mz-size-xs`,
   `--mz-success`, `--mz-backdrop`. The components were built correctly
   (`--mz-size-400`, `--mz-ok`, `--mz-scrim`) — it is `CANONICAL-COMPONENT-CONTRACT.md`
   that is stale. Doc fix, no code change.
4. **`pos.html` re-declares the spacing primitives** already in `foundation.css`, and its
   unratified `--inline-sm` (6px) / `--section` (24px) contradict the attested
   4px / 32px. Retiring the local copies is the P3 follow-up.
5. **`cashier.css:9` mirrors classic-light** on `[data-appearance="mezze"]` without the
   `:not([data-mz-theme])` guard its dark sibling got. Harmless today — the registry's
   `[data-mz-theme=…]` ramps outrank it — but it is the same shape as the bug that guard
   was added to fix, and it omits `--mz-focus`, `--mz-text-faint`, `--mz-danger-border`.

## 5. Verification

- foundation.css parses (braces balanced), addon-wide hard-undefined references 0.
- The shipped `test_split_bill_v2` "tokens used but never defined" assertion passes
  against the whole of `cashier.css`, not just its end-of-day section.
- Per-bundle check (`foundation` + `components` + `mezze-design`) for
  `components.css` / `kds.css` / `rail.css`: clean. `floor.css` surfaces only
  `--mz-reserved`, item 4.1.
- **The Odoo suite was not run in this session** (no DB credentials available).
  Run before committing: the changes are additive CSS custom properties plus three
  single-token substitutions, but `pos.html` and `cashier.css` are browser-verified surfaces.
