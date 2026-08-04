# Token Migration Map (DESIGN-P2)

How pre-existing local tokens map onto the authoritative `--mz-` contract. The mapping
is implemented via **compatibility aliases in `static/mezze-customer.css`** (customer
bridge, gated on `[data-appearance="mezze"]`) — no permanent hidden dual system; local
names are aliased to `--mz-*`, not re-valued independently.

## Token ownership (no ambiguous dual ownership)

| Token category | Authoritative file |
|---|---|
| color primitives | `mezze-design.css` |
| semantic colors | `mezze-design.css` |
| theme mappings | `mezze-design.css` |
| accent mappings (terracotta/blue/teal/plum/olive) | `mezze-design.css` |
| font families (`@font-face`, `--mz-font-*`) | `design/foundation.css` |
| type primitives (`--mz-size-*`, `--mz-weight-*`) | `design/foundation.css` |
| spacing (`--mz-space-*`, `--mz-touch-gap`) | `design/foundation.css` |
| radius (`--mz-radius-*`) | `design/foundation.css` |
| motion (`--mz-dur-*`, `--mz-ease-*`) | `design/foundation.css` |
| density (`--mz-density`) | `design/foundation.css` |

## Customer-surface compatibility aliases (`mezze-customer.css`, `[data-appearance="mezze"]`)

| Old local token | → `--mz-` | Temporary alias? | Consumers | Removal phase |
|---|---|---|---|---|
| `--bg` | `var(--mz-canvas)` | yes (bridge) | shop/qr/cfd/feedback/courses/drivethru | P3/P4 (when local names retired) |
| `--surface` / `--card` / `--panel` | `var(--mz-surface)` | yes | customer surfaces | P3/P4 |
| `--card2` / `--panel2` | `var(--mz-surface-2)` | yes | customer surfaces | P3/P4 |
| `--ink` / `--ink2` / `--ink3` | `var(--mz-text/-2/-mut)` | yes | customer surfaces | P3/P4 |
| `--line` | `var(--mz-border)` | yes | customer surfaces | P3/P4 |
| **`--accent` / `--saffron`** | **`var(--mz-brand)`** | yes | customer CTAs | P3/P4 |
| `--accent-d` / `--saffron-d` | `var(--mz-brand-press)` | yes | customer surfaces | P3/P4 |
| `--ok` / `--pos` / `--crit` / `--warn` | `var(--mz-ok/-danger/-warn)` | yes | customer surfaces | P3/P4 |
| body `font-family` (was `system-ui`) | `var(--mz-font-text)` | override rule | customer body | consumed now (P2) |
| RTL body `font-family` | `var(--mz-font-ar)` | override rule | customer RTL body | consumed now (P2) |

## Duplicate FOUNDATION definitions removed / mapped (Part 14)
- **Removed** the duplicate `@font-face` block from `mezze-customer.css` → `foundation.css`
  is now the single `@font-face` source.
- **Mapped** `mezze-customer.css` hardcoded `font-family:'Hanken Grotesk'` /
  `'IBM Plex Sans Arabic'` → `var(--mz-font-text)` / `var(--mz-font-ar)`.
- Color tokens: **not** duplicated into `foundation.css`. Type/geometry: **not** duplicated
  into `mezze-design.css`.

## kiosk / onboarding (not on the customer bridge)
Brand corrected directly in their local `:root`: `--acc:#e08a3c→#D89A54` (dark) /
`#c56a24→#C0602E` (light); `--acc2:#c56a24→#C98C48`. Fonts render Hanken via
`foundation.css`. Full local→`--mz-` alias migration for these two = later phase.

## Remaining local raw values (P3/P4)
Per Part Y, P2 does **not** eliminate every local component value. The customer local names
(`--bg`, `--accent`, …) remain as **aliases** to `--mz-*`; retiring the alias names entirely
is component-consolidation work (DESIGN-P3+).
