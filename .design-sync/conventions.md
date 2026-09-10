# Mezze POS — how to build with this system

Mezze is a restaurant point-of-sale for MENA. Everything here is real CSS lifted
from the shipping Odoo addon. **There are no JavaScript components in this
project**: the product's components are Owl (Odoo's framework) and cannot be
rendered here, so this system gives you the *look* — tokens, fonts and a class
vocabulary — and you write plain markup against it.

## Setup: nothing to wrap

`styles.css` already applies the default theme (Classic, light) to a bare
`:root`, so markup is styled with no provider and no wrapper.

To use any other theme, stamp the attributes the product itself stamps on
`<html>` before first paint. They win over the default:

```html
<html data-appearance="mezze" data-mz-theme="lounge" data-mz-mode="dark">
```

`data-mz-theme` takes `classic` `corporate` `coastal` `forest` `coffeehouse`
`highcontrast` (light) and `lounge` `midnight` `graphite` `slate` `forestnight`
`highcontrast` (dark). `data-mz-mode` is `light` or `dark`. `data-mz-accent`
takes `terracotta` `blue` `teal` `plum` `olive` `signature` `crimson` `ember`
`charcoal` and overrides the brand family only — except under `highcontrast`,
which keeps its own accessible brand on purpose.

## The idiom: semantic classes plus tokens

Style with the `.mz-*` classes below. For your own layout glue, use the tokens
directly — never invent a colour, radius or spacing value.

**Colour** `--mz-canvas` `--mz-workspace` `--mz-surface` `--mz-surface-2`
`--mz-surface-3` `--mz-border` `--mz-border-strong` `--mz-divider` · text
`--mz-text` `--mz-text-2` `--mz-text-mut` `--mz-text-faint` · brand
`--mz-brand` `--mz-brand-hover` `--mz-brand-press` `--mz-brand-soft`
`--mz-on-brand` · status `--mz-ok` `--mz-warn` `--mz-danger` `--mz-info` each
with a `-soft` companion.

**Geometry** `--mz-space-025` through `--mz-space-1200` (2px, 4px, 6px, 8px,
12px, 16px, 20px, 24px, 32px, 48px, 72px) · `--mz-radius-sm` `--mz-radius-md`
`--mz-radius-lg` `--mz-radius-xl` `--mz-radius-pill`.

**Type** `--mz-font-text` (Hanken Grotesk) · `--mz-font-ar` (IBM Plex Sans
Arabic) · `--mz-font-num` (JetBrains Mono). **Every number a cashier reads —
prices, totals, quantities, counts — is set in `--mz-font-num` with
`font-variant-numeric: tabular-nums`.** Sizes are `--mz-size-100` to
`--mz-size-800`.

**Classes**, 338 of them across 130 families. The ones you will reach for:

| Family | Modifiers |
|---|---|
| `.mz-btn` | `--primary` `--secondary` `--tertiary` `--ghost` `--danger` `--success` `--charge` `--confirm` `--on` `--sm` `--compact` `--touch` |
| `.mz-card` | `--interactive` `--selected` `--attention` `--compact` |
| `.mz-status` | `--ok` `--warn` `--danger` `--info` `--neutral` `--accent` `--offline` `--paused` `--pill` `--sm` `--md` `--lg` |
| `.mz-alert` | `--info` `--success` `--warning` `--danger` `--inline` `--toast` |
| `.mz-field` | `--row` `--compact`; pairs with `.mz-input`, `.mz-field-label` |
| `.mz-dialog__panel` | `--sm` `--lg`; with `.mz-dialog__backdrop`, `.mz-dialog__header`, `.mz-dialog__body`, `.mz-dialog__actions`, `.mz-modal`, `.mz-modal-scrim` |
| `.mz-state` | `--empty` `--error` `--warn` |
| `.mz-stepper` | `.mz-stepper__btn`, `.mz-stepper__value` |
| `.mz-flag` | `--best` `--combo` `--portion` `--low` |

Screen vocabularies follow the same `family__element--modifier` shape:
`.mz-tile` (product card), `.mz-catside` (category column), `.mz-rail`
(workspace rail), `.mz-cfg` (product configurator), `.mz-ochecks` (open checks),
`.mz-mhealth` (menu health).

## Two rules that are not cosmetic

**Touch floor.** Anything a cashier taps is at least 44×44. The classes enforce
it; do not override a height below it.

**Bidirectional.** The till runs in Arabic. Use `margin-inline-start`,
`padding-inline-end`, `inset-inline-start` — never the `left`/`right` forms.
Every stylesheet here is RTL-clean.

## Where the truth is

`styles.css` imports, in order: `tokens/foundation.css` (fonts, spacing,
radius), `tokens/palette.css` (12 themes × 9 accents, generated and
contrast-gated), `tokens/root-default.css` (the bare-root default), and
`_ds_bundle.css` (the class vocabulary). Read those files rather than trusting
this summary. `tokens/MEZZE_DESIGN_TOKENS.json` carries the same design values
in data form.

## A worked example

```html
<section class="mz-card mz-card--interactive" style="padding:var(--mz-space-150)">
  <h3 style="font-size:var(--mz-size-400);color:var(--mz-text)">Mixed Grill</h3>
  <p style="color:var(--mz-text-mut);margin:var(--mz-space-050) 0 0">
    Lamb, kofta, shish tawook
  </p>
  <div style="display:flex;align-items:center;justify-content:space-between;
              margin-top:var(--mz-space-150)">
    <span style="font-family:var(--mz-font-num);font-variant-numeric:tabular-nums;
                 font-weight:700">320.00 <span style="color:var(--mz-text-mut)">LE</span></span>
    <span class="mz-stepper">
      <button class="mz-stepper__btn">-</button>
      <span class="mz-stepper__value">1</span>
      <button class="mz-stepper__btn">+</button>
    </span>
  </div>
</section>
```
