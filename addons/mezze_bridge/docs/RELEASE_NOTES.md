# Release Notes — Mezze POS RC1

**Release Candidate 1 · pilot deployment · `mezze_bridge`**

---

## What this release is

The Mezze POS interface has been rebuilt on a complete design-token system, and the approved **Mezze visual redesign** has been implemented behind a feature flag.

**Nothing changes for existing users.** The current amber interface remains the default and has been proven **pixel-identical** — verified both by static analysis across 2,510 style declarations and live in a browser. The new appearance is opt-in.

## What stakeholders should know

**1. Zero-risk default.** The redesign activates only when `data-appearance="mezze"` is explicitly set. Without it, the terminal renders exactly what it renders today — same colours, spacing, fonts, icons, timings, down to the pixel.

**2. The new appearance is complete and faithful.** Colour, typography, icons, surface treatment, motion, spacing, density and the component library all resolve to the approved values, verified in a live browser across every workspace.

**3. Two decisions are needed before the new look can become the default.** Both are design questions, not engineering ones, and both are documented rather than worked around:
- A status badge fails contrast requirements in dark mode.
- One call-to-action uses a colour that does not exist in the approved palette.

**4. A genuine bug affecting Arabic was fixed.** The interface never declared its text encoding. In any hosting setup that does not supply that header, every non-Latin character — including all Arabic — displayed as corrupted symbols. This is now fixed, and it benefits the current amber build too.

**5. Offline operation is preserved.** All fonts are self-hosted; no Google Fonts, CDNs or external runtime dependencies were introduced.

## User-visible changes in this release

| | Amber (default) | Mezze (opt-in) |
|---|---|---|
| Appearance | Unchanged | Terracotta palette, Hanken Grotesk, Material Symbols icons |
| Text encoding | **Fixed** — Arabic and symbols now render correctly | Same fix |
| Everything else | Unchanged | Approved redesign |

**Workflows, navigation, business logic and component behaviour are unchanged in both appearances.** No feature was added or removed.

## Accessibility

- **Improved:** the approved type scale has an 11px floor, removing the smallest text. On the Payment surface the amber build has 8 elements below 11px; the new appearance has **0**.
- **Improved:** a manual "reduce motion" opt-out now exists, and motion tokens neutralise automatically under the OS setting.
- **Improved:** icons are explicitly hidden from screen readers; button labels are unchanged (63 `aria-label`s intact).
- **Outstanding:** one status badge fails contrast in dark mode (see Known Issues).

## Performance

- No new network requests, no JavaScript added, no external dependencies.
- Fonts load lazily and **only** under the new appearance — the amber build fetches **0 bytes** of them.
- The icon font is subsetted from 369,656 to **7,552 bytes** (−98%).
- Interface file grew 404 KB → 464 KB (+14.7%), entirely token definitions and indirection.

## Known Issues (both require a design decision)

1. **Dark-mode danger contrast — 2.53:1.** The out-of-stock badge renders white text on the approved dark danger colour, below the 4.5:1 requirement. It fails in the current amber build too (3.15:1), but the approved colour is lighter, making it worse. Light mode passes in both.
2. **Violet Delivery button.** The delivery call-to-action uses a violet that has no counterpart in the approved palette, so it remains visually inconsistent with the terracotta identity.

Neither has been "fixed" by guessing a replacement — that would mean inventing design decisions.

## Recommendation

**Ship RC1 with amber as the default.** Enable the new appearance for pilot terminals only after the two items above are resolved.

## Rollback

Removing the flag reverts instantly and completely — no data migration, no build step. See `ROLLBACK.md`.
