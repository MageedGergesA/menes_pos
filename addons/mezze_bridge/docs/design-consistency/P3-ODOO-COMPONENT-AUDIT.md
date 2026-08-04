# P3 — Odoo Native Component Audit (audit before building)

Two runtime contexts:
- **Static surfaces** (`shop/qr/kiosk/onboarding/courses/drivethru/cfd/feedback/pos.html`
  + `checkout` QWeb): **vanilla HTML/CSS/JS**, no Owl, no `@web/core`. Odoo web-client
  components are **not available** here → use **native HTML + canonical Mezze CSS classes**.
- **Owl cashier** (`/mezze/pos`, `assets_cashier`): loads `@web/core`, so Odoo components
  **are** available and may be reused where they fit.

Classification: **REUSE ODOO** / **WRAP ODOO** / **NATIVE HTML** / **MEZZE CUSTOM**.

| Component | Static surfaces | Owl cashier | Rationale |
|---|---|---|---|
| Button | **NATIVE HTML** `<button>` + `.mz-btn` | **NATIVE HTML** `<button>` + `.mz-btn` | A styled native `<button>` gives correct keyboard/role/focus for free; no Odoo button component earns its weight; visual identity must be Mezze, not web-client. |
| Icon button | NATIVE HTML `<button aria-label>` + `.mz-icon-btn` | same | same |
| Checkbox / Radio / Switch | **NATIVE HTML** inputs + `.mz-*` | **WRAP ODOO** `@web/core` CheckBox where already used, else native | native inputs are accessible + touch-fine; wrap Odoo only where the cashier already uses it. |
| Select | **NATIVE HTML** `<select>` + `.mz-field` | **WRAP ODOO** `SelectMenu`/`Dropdown` if searchable needed | native select is best for simple cases + touch; Odoo SelectMenu only for search/large lists in the cashier. |
| Dialog / Modal | **MEZZE CUSTOM** `.mz-dialog` (role=dialog + JS focus-trap) | **WRAP ODOO** `@web/core` `Dialog` (focus-trap/aria-modal/Esc built-in) | static surfaces can't use Owl Dialog → custom, but must add focus-trap (P1 added role=dialog only); the cashier should reuse Odoo's `Dialog` rather than reimplement modality. |
| Dropdown / menu | NATIVE / MEZZE CUSTOM | **REUSE ODOO** `Dropdown` | Odoo Dropdown is solid; reuse in the cashier. |
| Tabs / Notebook | MEZZE CUSTOM `.mz-tabs` (ARIA) | **REUSE ODOO** `Notebook` where it fits | — |
| Pager | N/A (customer infinite-scroll) | REUSE ODOO `Pager` if a paged list appears | — |
| Status badge / chip | **MEZZE CUSTOM** `.mz-status` (icon+label, never color-only) | same | restaurant status semantics are Mezze-specific; no Odoo equivalent. |
| Quantity stepper | **MEZZE CUSTOM** `.mz-stepper` (≥44px) | same | domain control; not in Odoo core. |
| Toast / notification | MEZZE CUSTOM `.mz-toast` (aria-live) | **REUSE ODOO** notification service where used | — |
| Card / list row | **MEZZE CUSTOM** `.mz-card` / `.mz-list-row` | same | layout primitives; Mezze-owned. |
| Empty / loading / skeleton | **MEZZE CUSTOM** | reuse Odoo spinner where present | — |

## Conclusions
- **Do not** force the Odoo web-client visual language onto customer/kiosk surfaces (breaks
  Mezze identity + those surfaces have no `@web/core`).
- **Do** reuse `@web/core` **`Dialog`**, **`Dropdown`**, **`SelectMenu`**, **`Notebook`**,
  **`Pager`**, and the **notification** service **inside the Owl cashier** where they fit —
  styled to the `--mz-` foundation — rather than reimplementing modality/menus.
- Everywhere else, prefer **native semantic HTML** styled by canonical `.mz-*` classes over
  bespoke widgets (Part 18): native `<button>`, `<input>`, `<select>`, `<label>` give
  accessibility + touch behaviour for free.
- **No component is built to replace a good native/Odoo control merely for abstraction.**
