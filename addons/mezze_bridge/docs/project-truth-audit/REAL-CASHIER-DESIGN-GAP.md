# REAL CASHIER (/mezze/pos Owl) — DESIGN GAP (measured, NOT fixed)

V1 phase, 2026-08-05. Source of truth: `static/src/cashier/**`, `views/cashier_templates.xml`,
`controllers/cashier.py`, `static/design/{foundation,components}.css`. Compared to the canonical
foundation + `/home/mageed/Downloads/Mezze POS Visual Redesign/export`. **No fixes made here** (except the
`/bootstrap` readonly boot-blocker, which was a functional harness-blocker, not design).

## What the shipped cashier DOES have (good)
- Loads the canonical foundation: `foundation.css` (`--mz-` tokens + vendored @font-face Hanken/IBM-Plex-
  Arabic/JetBrains-Mono) + `components.css` (canonical `.mz-btn`, `.mz-status`). Bundle
  `mezze_bridge.assets_cashier` (`__manifest__.py:57-58`).
- Uses canonical `.mz-btn` for primary actions; status is "never colour-only" (icon+text).
- Server-authoritative boot (branch/currency/user from `cashier.py`), least-privilege terminal token.

## Gaps

### P0 — operational (blocks function)
| Gap | Evidence | Status |
|---|---|---|
| `/bootstrap` cannot open a session (readonly route) → cashier can't cold-boot a branch with no open session (phase=error) | `controllers/main.py` bootstrap route lacked `readonly=False` while `_ensure_open_session` writes | **FIXED in V1** (added `readonly=False`; the only production change this phase) — surfaced by the first browser test |

### P1 — major consistency / accessibility
| Gap | Evidence |
|---|---|
| **No RTL / Arabic direction** on the cashier — `mz_dir` is never passed by `cashier.py` render, yet `cashier_templates.xml:13` binds `t-att-dir="mz_dir"` → dir unset → Arabic renders **LTR** and the `[dir=rtl]`-gated Arabic font never activates | cashier.py render dict = `{boot_json, mz_lang, mz_debug}` (no `mz_dir`) |
| **No dark mode** — template hardcodes `data-mz-mode="light"` (`cashier_templates.xml:16`); bundle excludes the theme engine (`mezze-design.js/css`); `foundation.css` has no dark tokens | hardcoded; grep: no `prefers-color-scheme`/`data-mz-mode` overrides reach the cashier |
| **No High-Contrast theme** — template hardcodes `data-mz-theme="classic"`; the `[data-mz-theme="highcontrast"]` ramps live in `mezze-design.css`, which the cashier bundle does NOT load | the HC theme exists ONLY for prototype/customer surfaces |
| **2nd `.mz-btn` base drift** — `static/src/cashier/cashier.css:134` redefines `.mz-btn` (`padding:14px 18px; font-size:16px; border:none`, **no `min-height:44px`**), diverging from canonical `components.css:13` (44px touch target) | duplicate class; touch-target a11y regression |
| **Status not on canonical `.mz-status`** — cashier uses its own `.mz-conn`, `.mz-state--error/--warn`, `.mz-terminal-status--*`, `.mz-tile-badge`, `.mz-pay-error` (token-aligned but not the component) | cashier.css / root.xml |

### P2 — polish
| Gap | Evidence |
|---|---|
| Connectivity shows a **single signal** (`local`) though `root.js` state carries `{local, wan}` and the architecture intended 3 (local/WAN/services) | root.xml:14 renders only `.mz-conn[data-state=local]`; root.js:173 `{local, wan}` |
| `.mz-badge` canonical metadata badge essentially unadopted | — |

## Bottom line
The shipped cashier is on the canonical **foundation + buttons** but is **light-only, classic-only, LTR-
only**, with its own status vocabulary and a drifted button base. Dark/HC/RTL that this session "verified"
were on the **prototype**, not here. This is the real P3 remediation scope for the cashier — to be done in
a LATER phase, per V1's mandate (verify + measure now, fix later).
