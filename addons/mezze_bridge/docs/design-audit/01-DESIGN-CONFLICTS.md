# 01 — Design-System Conflicts

Each conflict lists the competing rules, the **actual current source**, the most
coherent resolution, and the migration consequence. No values changed.

## C1 — Spacing: 4px base vs 8px grid  ⟵ the one the brief asked about

- **Historical export** ("Mezze Spacing System") references an **8px grid**.
- **Current authoritative DS** (`DESIGN_SYSTEM.md §4`, measured from the app) is a
  **4px base**: `--space-1..8 = 4/8/12/16/20/24/32/40`.
- **Actual implementation:** `pos.html` follows the 4px scale; other surfaces use
  many off-scale values (7/9/11/13/17/21/26px seen in heights/margins).
- **Authoritative going forward: 4px base.** It is a superset of the 8px grid (8px
  values still land on it) and matches the shipped app. The 8px export is
  **HISTORICAL**.
- **Migration consequence:** low — 4px base already dominant in `pos.html`; the work
  is snapping the other 8 surfaces onto `--space-*`.

## C2 — Radius scale: 8/12/18/24 vs 16 vs 22

- DS: `--r-sm/md/lg/xl = 8/12/18/24` + pill.
- `qr.html`/`onboarding.html`: single `--r:16`. `kiosk.html`: single `--r:22`.
- 16 distinct radius values exist product-wide.
- **Resolution:** adopt the DS 5-step scale everywhere; card = 18, control = 12.
  Consequence: medium (touches every non-`pos` surface, purely cosmetic/low-risk).

## C3 — Brand accent naming + value: `--accent`(#E0982B) vs `--saffron`(#EFA23C) vs `--acc`(#e08a3c)

- Same amber brand, three token names, three near-but-not-equal hexes.
- **Resolution:** one `--accent` token (+ `--accent-strong`, `--on-accent`) from a
  shared stylesheet. Consequence: low visual change, high consistency gain.

## C4 — Type scale: one 10-step DS scale vs 8–45 inlined sizes per file

- DS collapses "32 ad-hoc sizes to 10 steps" (its own words). `pos.html` conforms;
  other files re-inline. **Resolution:** shared `--text-*` scale. Consequence: medium.

## C5 — Font personality: system-ui/Noto Kufi (DS) vs Hanken Grotesk/IBM Plex Arabic (kiosk/onboarding)

- Two different type identities across staff vs kiosk/admin.
- **Resolution:** pick one family pair (the DS `system-ui + Noto Kufi Arabic`, or a
  deliberate display face) and apply product-wide. Consequence: medium; visible but
  low-risk. This is a *product identity* decision, not just a token.

## C6 — Theming mechanism: full registry vs partial vs none

- `pos.html`: `data-theme` (dark/light) **+** `data-appearance`/`data-mz-mode` +
  the D1 multi-theme registry.
- `shop.html`/`qr.html`: `data-theme` + `data-mz-mode` + `prefers-color-scheme`.
- `kiosk.html`: `data-mz-mode` + `prefers-color-scheme` (no registry).
- `onboarding.html`: `data-mz-mode` **only** — no `prefers-color-scheme`, not on the
  theme registry.
- **Resolution:** one theming contract (`data-theme` + `prefers-color-scheme`
  fallback) shared by all surfaces. Consequence: medium.

## C7 — Status color semantics

- DS defines semantic status (`--pos`/`--warn`/`--crit`/`--info`/`--violet`) **and**
  mandates "status never by color alone" (icon+label+sign). `pos.html` honors it
  (73 aria-labels, textual status). Customer/kiosk surfaces lean more on color +
  short text; need per-screen check that state isn't color-only.
- **Resolution:** adopt the DS state matrix (see `04`/`08`) everywhere.

## C8 — Button component: `.btn`/`.primary` (pos) vs `.addbtn`/`.svcbtn`/`.startbtn`/`.review` (kiosk) vs `.pay*` family (pos payment)

- The primary action is implemented under many class names across files.
- **Resolution:** one button component (variants by color/size). Consequence: medium.

## Non-conflicts (already coherent — keep)

- The **DS accessibility contract** (44px touch, focus ring, RTL logical props,
  reduced-motion, status-not-color-alone) is sound and should become the product-wide
  contract — it is not contradicted anywhere, merely **unenforced** outside `pos.html`.
- Warm amber-on-warm-neutral palette direction is coherent and distinctive — keep.
