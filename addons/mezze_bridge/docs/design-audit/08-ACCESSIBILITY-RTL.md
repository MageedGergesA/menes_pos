# 08 — Accessibility & RTL Baseline

WCAG 2.2 used as a **baseline reference only** — no formal certification claimed.
Evidence = grep + `read_page` + `DESIGN_SYSTEM.md`.

## A11y instrumentation per surface

| Surface | `aria-label` | `role=dialog`/`aria-modal` | `aria-live` | `:focus` rules | `outline:none` | reduced-motion |
|---|--:|--:|--:|--:|--:|--:|
| `pos.html` | 73 | 3 | 2 | 12 | 6 (with replacements) | 3 |
| `shop.html` | 8 | 0 | 0 | 8 | 0 | 1 |
| `qr.html` | 3 | 0 | 0 | 5 | 0 | 1 |
| `kiosk.html` | 2 | 0 | 0 | **0** | 0 | 0 |
| `onboarding.html` | **0** | 0 | 0 | **0** | 0 | 0 |

**Finding (P1):** the DS accessibility contract is genuinely met in `pos.html` and
essentially **unmet everywhere else**. Concrete gaps:
- **No visible focus styling** in `kiosk.html` and `onboarding.html` (keyboard users
  can't see focus). `onboarding.html` (S5 admin console) has **no ARIA at all**.
- **Modals not marked `role=dialog`/`aria-modal`** outside `pos.html` (shop/qr/kiosk
  sheets) — no programmatic dialog semantics / focus-trap evidence.
- **No `aria-live`** for cart updates, payment status, or KDS changes outside
  `pos.html` — screen-reader users don't hear async state changes.
- **Numerous unnamed icon-only buttons** in `pos.html` (`read_page` showed ~20 buttons
  with no accessible name) — even the best surface has icon-button labelling gaps.

## Contrast (from `DESIGN_SYSTEM.md §2`, self-documented)

| Token | Ratio on surface | Verdict |
|---|---|---|
| `--ink-3` (muted, light) | **3.76:1** | Below AA 4.5 for small text — DS restricts it to ≥14px/bold labels (mitigation documented, but enforcement outside `pos.html` unverified). |
| `--warn` (light) | 3.87:1 | Fills/large-bold only. |
| `--pos` (light) | 3.60:1 | Fills/large-bold only. |
| `--ink` / `--ink-2` | pass | Body text OK. |

**Finding (P1/P2):** the palette has a **known low-contrast muted tier**. It's
mitigated by rule in the DS, but the non-`pos` surfaces don't share the DS and may use
their `--mut`/`--ink2`/`--ink-3` equivalents for small body text (e.g. kiosk `--mut
#b7a9c2` on `--card #211a26`, onboarding likewise) — needs a contrast pass on the
customer/kiosk/admin muted text specifically.

## Color-only signals (P2)

- Go-Live console renders PASS/WARNING/FAIL/NOT TESTED as colored pills — the text
  label **is** present (good, not color-only), but `NOT TESTED` and `N/A` are visually
  close and rely on a blue/grey distinction; ensure shape/icon differentiation so
  "not tested" reads as *uncertainty*, not a pale pass/fail.
- Table/KDS/payment status: DS mandates icon+label+sign; `pos.html` honors it.
  Customer surfaces need a check that availability/86 and order status aren't
  color-only.

## Touch targets (CSS px)

| Surface | Smallest observed interactive height | Verdict |
|---|---|---|
| `kiosk.html` | 48 / 52 (primary), 150 (tiles) | ✅ comfortably ≥44 |
| `pos.html` cashier | primary bars 44–52; some dense secondary rows 30–40 | mostly ✅; dense secondary controls need per-element check |
| `qr.html` | some controls 30 / 40 | ⚠ some <44 |
| `shop.html` | some controls 26 / 27 / 40 | ⚠ some <44 |

**Finding:** kiosk is exemplary; primary cashier/KDS/kiosk actions appear to meet
44×44; **`shop.html` and `qr.html` have sub-44 controls** (chips/secondary buttons)
that warrant review. (Heights from static CSS include non-interactive elements — treat
sub-44 as *candidates* pending a browser per-element check.)

## RTL

- DS mandates **logical properties** (`inset-inline`, `margin-inline`) + `dir=rtl` +
  Noto Kufi. `pos.html`/`qr.html` set `[dir=rtl]`; kiosk/onboarding set `dir="rtl"`.
- **Risk:** the non-`pos` files use physical `left/right`/`margin-left` in places
  (65–75 hardcoded positional spacing decls in shop/qr) — those **won't mirror**
  correctly under RTL. Needs a logical-property pass.
- **Must-not-mirror** items (numeric references, QR codes, brand logo, progress
  chevrons): not verified per-element in this pass — flag for the browser RTL gate.

## Arabic typography

- Two type identities: DS `Noto Kufi Arabic`; kiosk/onboarding `IBM Plex Arabic`.
- Risk that Arabic "just makes components taller" rather than being tuned
  (line-height/weight parity) — needs a side-by-side EN/AR visual check (not done this
  pass).

## Reduced motion

- Honored in `pos.html`/`shop.html`/`qr.html` (1–3 rules). **Absent in kiosk +
  onboarding.**

## Baseline verdict

**ACCESSIBILITY BASELINE: partial.** Strong in `pos.html`; **below baseline** in
kiosk, onboarding, and (to a lesser degree) shop/qr — primarily focus visibility,
dialog semantics, live regions, and the low-contrast muted tier. No formal WCAG
certification is claimed.
