# Canonical Mezze Component Contract

Derived from the original source (*Mezze Component Library* T1–T5, *Primitive/Typography/
Spacing/Design* systems). Components consume the `--mz-` foundation only — **no raw hex/px**.
Namespace: **`.mz-*`** classes (static + Owl share one contract). Precedence: original
Component/Primitive source → later original revision → restaurant patterns → `--mz-`
foundation → existing code. This is the target; **migration is staged (Button first)**.

## Global rules
- Every interactive control: native semantics, visible `:focus-visible` ring
  (`2px/2.5px solid var(--mz-focus)`, offset 2), `prefers-reduced-motion` honored.
- Operational touch controls **≥ 44×44 CSS px**; ≥8px gap between adjacent targets.
- Status **never color-alone** — always icon + label (+ shape/sign).
- Light/dark via semantic `--mz-` tokens only (no per-component light/dark hardcodes).
- Tabular numerals (`--mz-font-num`) for money/qty/time.

## Button — `.mz-btn`
- **Anatomy:** native `<button>`; optional leading icon (gap `--mz-space-100`); label
  `--mz-font-text`/`--mz-weight-bold`, `--mz-size-md`.
- **Variants (5):** `--primary` (`--mz-brand`/`--mz-on-brand`) · `--secondary`
  (surface + `--mz-border`) · `--ghost` (transparent + text) · `--danger` (`--mz-danger`) ·
  `--success` (`--mz-success`, for Charge/Pay). Icon-only = `.mz-icon-btn` (requires
  `aria-label`).
- **Sizes:** `--compact` (h 36, admin) · default (h 44) · `--touch` (h 50, primary bars).
  Radius `--mz-radius-md` (11). Padding `0 var(--mz-space-300)`.
- **States:** default · hover · **focus-visible** · pressed (`transform:scale(.97)` @
  `--mz-dur-fast`) · disabled (`opacity var(--mz-disabled-opacity)`) · loading (spinner,
  label hidden, `aria-busy`).
- **Semantics:** action → `<button>`; navigation → `<a>` (don't style links as buttons
  with wrong semantics). Enter/Space activate (native).
- **Action hierarchy:** one dominant primary per screen; secondary quieter; destructive
  separated. (Visual only — no workflow change.)

## Status — `.mz-status`
- **Anatomy:** icon + label; height ~24; padding `var(--mz-space-050) var(--mz-space-100)`;
  radius `--mz-radius-sm` (8); `--mz-size-xs` uppercase weight 800; `-soft` bg + solid fg.
- **UI states:** neutral/active/success/warning/danger/info/offline/paused/**not-tested**.
- **Restaurant states** (color+icon+label, shared across cashier/floor/KDS/delivery/customer):
  available/occupied/waiting/preparing/ready/completed/paid/partial/cancelled/86.
- **Go-Live:** PASS/WARNING/FAIL/**NOT TESTED**/N-A must be unmistakable by **icon+label+
  style**, not hue alone; NOT TESTED reads as *uncertainty*, never a pale pass/fail.

## Dialog — `.mz-dialog` (static) / `@web/core` `Dialog` (Owl)
- **Anatomy:** scrim (`--mz-backdrop`) · container (radius `--mz-radius-xl` 16, shadow) ·
  header/title · optional description · content · error area · footer/actions · close route.
- **Accessibility (must):** `role="dialog"` + `aria-modal="true"` **only when outside is truly
  inert** · accessible title (`aria-labelledby`) · initial focus inside · Tab/Shift+Tab
  contained · Esc closes when the workflow allows · focus restored to the trigger on close.
- **Variants:** standard · confirmation · danger · **financial/approval** (keeps amount/
  method/remaining/reason/manual-vs-confirmed; default focus favors the safer action).

## Input — `.mz-field`
- **Anatomy:** `<label>` (never placeholder-only) · control (native `<input>/<select>/
  <textarea>`, h 44, radius `--mz-radius-md`, `--mz-border`) · helper · **error** (icon +
  text, associated via `aria-describedby`; never red-border-only; never raw backend text).
- **States:** default/focus/error/required/disabled/readonly. Numeric inputs tabular.

## Quantity — `.mz-stepper`
- **Anatomy:** `−` / value / `+`; each button ≥44×44 (`aria-label` less/more); value tabular.
- Disabled at min/max; RTL-mirrored order; server remains the quantity authority (no rule
  change).

## Card / List row — `.mz-card` / `.mz-list-row`
- **Card:** `--mz-surface`, 1px `--mz-border`, radius `--mz-radius-lg` (14), padding
  `--mz-space-200`; elevation only when it communicates layer (not decoration); optional 4px
  inline-start status stripe. **Not every section is a card.**
- **List row:** denser admin/reconciliation/delivery/customer-select; no card chrome.

## Alert — `.mz-alert`
- Variants info/success/warning/danger/offline; icon + message + optional action + dismiss.
- Financial failure stays **persistent/explicit**, never a transient toast.

## Empty / Loading — `.mz-empty` / `.mz-skeleton`
- Empty: short title + one-line explanation + one optional next action (compact).
- Loading: small action → inline spinner; content → skeleton; long op → explanatory status.
  No indefinite unexplained spinner. (No async business-logic change.)

## API discipline
Small semantic API: `variant` / `size` / `state` + composition. No prop soup
(`orange/blue/left/right/rounded/flat`). One canonical base per family; intentional
specialized variants (product tile, order card, KDS ticket) **compose** these primitives
rather than fork them.
