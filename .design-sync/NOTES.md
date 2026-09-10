# design-sync notes — Mezze POS

## Shape: style layer only

This repo is an **Odoo 19 addon**, not a JavaScript package. It has no
`package.json`, no Storybook, no `dist/`. The 21 components under
`addons/mezze_bridge/static/src/cashier/components/` are **Owl** and import
`@odoo/owl` and `@web/core/l10n/translation`, which Odoo's own asset bundler
resolves at runtime. They cannot be compiled into the `_ds_bundle.js` the design
agent renders, and hand-writing React equivalents would be the reimplementation
the skill forbids. So the skill's converter (`package-build.mjs`) is not used.

What is synced is the framework-agnostic style layer, assembled by
`.design-sync/build.mjs` from the addon's own stylesheets. Re-run it with
`node .design-sync/build.mjs` from the repo root.

## Decisions

* **`tokens/root-default.css` is generated, not hand-written.** Every token in
  the product is scoped to `:root[data-appearance="mezze"]`, stamped on `<html>`
  by an inline pre-paint resolver. A rendered design starts with a bare root, so
  without this block the whole system falls back to browser defaults. The build
  extracts the default (classic, light) values out of `tokens/palette.css` at
  build time so `static/gen_design.py` stays their only source. Verified: all
  four theme states still switch correctly when the attributes are set, and the
  high-contrast brand holds at `#9A3D18` under a terracotta accent.
* **Font URLs are rewritten.** The addon serves them from
  `/mezze_bridge/static/fonts/`, which does not exist here; the build rewrites
  them to `../fonts/` and asserts no addon path survives.
* **Excluded on purpose.** `static/design/kiosk-v2.css` and `kiosk-v3*.css` are a
  separate customer surface. `static/src/cashier/cashier.css` is Register-screen
  furniture rather than reusable vocabulary. Neither is design-system material.
* **No `_ds_sync.json`.** Its hash recipe describes the package/storybook shapes;
  there are no components or stories to key it on. Omitted deliberately, so the
  next sync re-verifies from scratch rather than trusting an anchor that vouches
  for nothing.

## Verification done

Rendered `styles.css` against plain markup in Chrome on a bare `<html>`: tokens
resolve, 6 font faces load from the relative path, and the class vocabulary
applies (`.mz-catside` 201px basis, `.mz-catside__item` 12.5px, `.mz-btn--charge`
terracotta, `.mz-stepper` radius 8px). Every token, class, theme and accent named
in `conventions.md` was checked against the built artifacts; one miss was found
and corrected — there is no bare `.mz-dialog` rule, the root is
`.mz-dialog__panel`.
