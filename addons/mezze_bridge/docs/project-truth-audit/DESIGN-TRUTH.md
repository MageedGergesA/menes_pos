# DESIGN TRUTH (forensic — from code)

Audit date 2026-08-05. HEAD `5ec05b1`. **This corrects overstated design claims in the P3A/P3B result docs.**

## THE central finding — prototype vs production cashier
- **Production cashier = a standalone Owl app** (`static/src/cashier/**`, manifest bundle
  `mezze_bridge.assets_cashier`) served at **`/mezze/pos`** (`controllers/cashier.py:60`, `auth='user'`).
- **`static/pos.html` (473 KB) is the VISUAL REFERENCE PROTOTYPE**, served at the SEPARATE route
  **`/mezze/design/pos`** (`controllers/main.py:2448-2469`; its own comment: "serves the visual reference
  prototype (static/pos.html)…the production cashier is the standalone Owl app").
- **Consequence:** ALL of this session's P3B design migrations (KDS/floor/delivery/reservations/settings
  status badges) were made on the **prototype**, NOT the shipped cashier. They are real (the prototype IS
  a shipped surface) but they do **not** change the production POS UI.

## Owl cashier design state (the real POS)
- Loads the canonical foundation: `assets_cashier` includes `design/foundation.css` (`--mz-` tokens) +
  `design/components.css` (canonical `.mz-btn`). So tokens + buttons ARE on the canonical base there.
- BUT its **status vocabulary is its own**: `.mz-conn`, `.mz-state--error/--warn`, `.mz-terminal-status--*`,
  `.mz-tile-badge`, `.mz-pay-error` (cashier.css) — it consumes `--mz-` tokens and is "never colour-only",
  but it does **not** use the canonical `.mz-status` component.
- **Button drift:** `static/src/cashier/cashier.css:134` defines a SECOND `.mz-btn` base
  (`padding:14px 18px; font-size:16px; border:none`, **no `min-height:44px`**) — diverges from the
  canonical `components.css:13` (`min-height:44px; border:1px`). Same class, two definitions.

## P3A Buttons — **PARTIAL** (docs claim COMPLETE — overstated)
- Canonical `.mz-btn` source = 1 (`components.css:13`); **but a 2nd drifted base** exists in cashier.css.
- Canonical-only surfaces: pos.html(proto), shop, qr, kiosk, onboarding.
- **3 legacy button palettes remain**: `drivethru.html`, `feedback.html`, `courses.html` each ship own
  gradient `.btn`/`.newbtn`/`.hbtn`/`.ghost` (5 legacy classes), no migration/deferral marker.
- Verdict: **PARTIAL** — canonical owns core+primary-customer, but 3 legacy pages + cashier button drift.

## P3B Status — **PARTIAL** (foundation complete; coverage incomplete)
- Canonical `.mz-status` (9 variants: neutral/info/active/success/warning/paused/danger/offline/not-tested,
  `components.css:89-112`) + `.mz-badge` (`:132`) + compat aliases (ok/warn/accent/violet → success/warning/
  info, `:126-129`). Foundation is COMPLETE and correct.
- Migrated (prototype + onboarding/shop): KDS, delivery, reservation, waitlist, checkout, header-conn badges → canonical `.mz-status`.
- **Admin/Settings governance** `.admin-badge` (in `mezze-design.js` as injected CSS, lines ~455-641) —
  consumes `--mz-` tokens; P3B.5 fixed its semantics (locked≠danger, bounded≠warn). (Note: a source-grep
  scoped to html/css misses it; it IS present in the JS.)
- **Still legacy/incomplete:** `.st-*` card borders (deferred **P3G**, marked); `.mz-badge` near-unadopted
  (only onboarding ×2); **2 unexplained legacy status palettes** (`.mezze-conn` footer in pos.html;
  customer `.conn`/`.dot` in cfd + drivethru); **~3 legacy metadata badge palettes** (catalog `.tag`/`.chip`
  in shop/qr, `.rsvchip`, KDS metadata labels).
- **Production Owl cashier status = NOT on canonical `.mz-status`** (own token-aligned vocabulary).
- Verdict: **PARTIAL.**

## P3C–P3I — **NOT STARTED**
Alerts (P3C), Inputs (P3D), Quantity (P3E), Dialogs (P3F), Cards/ListRows (P3G), Empty/Loading (P3H),
Tabs/Segmented (P3I): **no commit, no code, no result doc** — only forward-deferral references (and P3D
was never even named as a deferral target).

## High-Contrast / A11y (three separate capabilities)
- **Mezze app HC theme = YES** (`mezze-design.css:83/158` `[data-mz-theme="highcontrast"][data-mz-mode=…]`,
  black/white + strong borders + 3px focus; activated by `ac_contrast` setting / `?mztheme=highcontrast`).
  Manual app setting only — NOT OS-derived. Browser-verified this session (~21:1) on the prototype.
- **prefers-contrast = NO.** **forced-colors = NO.** (product-wide a11y foundation gap)
- reduced-motion YES · focus-visible YES · RTL YES · touch ≥44px YES (canonical) · `role="status"` YES (some pages).

## Theme-engine coverage gap
- **kiosk.html + onboarding.html load NEITHER `mezze-design.css` NOR the theme engine** → **no colour
  registry, no dark mode, no HC theme** on those two (they render via components.css hex fallbacks = fixed
  light palette). onboarding is the admin go-live console yet is light-only. This contradicts any implied
  "product-wide dark/HC".

## Page inventory: **9 shipped HTML surfaces** (+ the Owl cashier = the 10th, real, POS)
pos.html(proto, /mezze/design/pos), shop, qr, cfd, kiosk, onboarding, drivethru, feedback, courses.
Design-debt trio = drivethru/feedback/courses (legacy buttons + no mz-status). Not "11 pages".

## Token/foundation truth
Fonts: EN Hanken Grotesk, AR IBM Plex Sans Arabic, num JetBrains Mono (vendored @font-face). Brand light
`#C0602E`, dark `#D89A54`. Spacing 4/8 lattice `--mz-space-*`; radius 8/11/14/16/pill; motion 80–320ms.
**Drift:** pos.html uses its own `--sp-*/--fs-*/--r-*` scale (not `--mz-` primitives); mezze-design.css adds
a semantic-alias bridge (`--accent/--ink/--surface/…`); components.css hard-codes hex fallbacks; legacy
pages define local `--accent` tokens.

## Bottom line
Foundation (fonts/tokens/geometry) + canonical button + 9-variant status LANGUAGE are real and well-authored.
But **P3A = PARTIAL and P3B = PARTIAL**; the production cashier is on a drifted button base + its own status
system; 3 legacy pages + 2 no-theme surfaces remain; 7 design families (P3C–P3I) are not started. Prior
"P3A COMPLETE / coherence 93-95%" claims were measured on the **prototype** and are **overstated** for the
shipped product.
