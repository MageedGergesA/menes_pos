# P2 — Approved Mezze Typography System (Flag-Gated)

*Typography migration, flag-gated under `[data-appearance="mezze"]`; amber untouched. Fonts self-hosted, **extracted from the approved export** (no Google Fonts, no external runtime). Colour/icons/layout/motion/spacing/density/radius/business-logic unchanged.*

## 1. Typography Implementation Summary

- **Self-hosted the 3 approved fonts** — extracted the `.woff2` bytes from the export's `window.__resourceBlobs`, subsetted to **Latin + Arabic** (dropped Cyrillic/Greek/Vietnamese), wrote **18 files → `static/fonts/` (596 KB)**: Hanken Grotesk 400–800 (latin + latin-ext), JetBrains Mono 400–700 (latin), IBM Plex Sans Arabic 400–700 (arabic). All verified valid woff2 (`file`), mapped from the export's own `@font-face` src→UUID (authoritative).
- **18 `@font-face`** declarations with the exact approved `unicode-range`s + `font-display:swap`, `src:url("fonts/…woff2")`. **Lazy** — the browser only fetches a face when an element actually uses that family+weight+subset; amber never references these families, so **amber loads zero brand fonts**.
- **Complete typography token system** built (`[data-appearance="mezze"]`): `--mz-font-text/num/ar`, the **9-step scale** `--mz-size-100..900` (11/12/13/15/18/22/26/32/40), `--mz-weight-regular..extrabold` (400/500/600/700/800), `--mz-leading-tight/normal/relaxed/ar` (1.2/1.4/1.55/1.7). *(The approved system defines **no letter-spacing tokens** — noted.)*
- **Font-family applied via role tokens** (no component edits): under mezze, `--font-ui`→Hanken (+ IBM Plex Arabic fallback), `--font-num`→JetBrains Mono. **RTL:** `--font-ui`→IBM Plex Sans Arabic-first + Arabic leading `1.7` on body.
- **Verification:** 8/8 architecture checks pass (amber stacks unchanged; mezze → Hanken/JetBrains/IBM-Plex; RTL Arabic-first; 9-step/leading tokens present). Braces 2633=2633; `node --check` OK.

## 2. Complete Typography Token Mapping

| Role token | Amber (default) | → Mezze | Consumers |
|---|---|---|---|
| `--font-ui` (body → cascades) | system-ui / Segoe / Roboto / Noto Kufi | `'Hanken Grotesk','IBM Plex Sans Arabic',system-ui,…` | 1 (body; cascades app-wide) |
| `--font-ui` (RTL) | (same) | `'IBM Plex Sans Arabic','Hanken Grotesk',…` | RTL scope |
| `--font-num` (`.num`) | ui-monospace / SF Mono / Roboto Mono / Menlo | `'JetBrains Mono','SFMono-Regular',ui-monospace,monospace` | 18 |
| **Built (available) — not yet consumed by components:** | | | |
| `--mz-size-100..900` | — | 11/12/13/15/18/22/26/32/40 | 0 (see §8) |
| `--mz-weight-regular..extrabold` | — | 400/500/600/700/800 | 0 (see §8) |
| `--mz-leading-tight/normal/relaxed` | — | 1.2/1.4/1.55 | 0 (`--mz-leading-ar` 1.7 applied to RTL body) |

Fonts were **already token-driven** (`var(--font-ui)` ×1 cascading + `var(--font-num)` ×18) — **no component declared `font-family`**, so the family swap needed **zero component edits**.

## 3. Font Loading Strategy

- **Self-hosted**, files under `mezze_bridge/static/fonts/` served by the addon (same origin as `pos.html`); `src:url("fonts/…woff2")` (relative). **No Google Fonts / CDN / external runtime dependency** — offline capability preserved.
- **Subsetted** to Latin + Arabic (the export's per-subset splits), dropping Cyrillic/Greek/Vietnamese → 596 KB across 18 files.
- **`font-display:swap`** — text paints immediately in the fallback, swaps to the brand font on load (no FOIT/blank text).
- **Lazy + gated:** faces load only when referenced; only the mezze appearance references them, so **amber incurs zero font cost**.
- **Defensive amber fix:** removed the aspirational `"JetBrains Mono"` fallback from the **amber** `--font-num` stack, so the now-self-hosted face can't leak into the amber build on browsers lacking `ui-monospace`/`SF Mono`. Amber renders system-mono exactly as before.

## 4. Performance Impact

- **+596 KB of woff2** (self-hosted), but **loaded on demand per weight/subset and only under mezze** — a first-paint amber terminal loads **0 bytes** of it. Under mezze, only the weights/subsets actually used are fetched, then browser-cached.
- No render-blocking (`swap`), no new JS, no CDN round-trips. The certified **amber build's ~102 KB / 0-dependency footprint is unchanged.**
- Recommend HTTP caching headers on `/static/fonts/*` at deploy.

## 5. Accessibility Report

- **Readability:** Hanken Grotesk is a high-legibility humanist grotesque; JetBrains Mono improves digit disambiguation (tabular). Both improve on the generic system stack.
- **Arabic:** IBM Plex Sans Arabic applied for Arabic glyphs (RTL-first stack) with **1.7 line-height** (approved `--mz-leading-ar`) on RTL body — correct Arabic vertical rhythm; mixed AR/EN resolves per-glyph (Latin→Hanken, Arabic→IBM Plex).
- **No clipping/overflow/truncation change:** because component **font-sizes are unchanged** (size-scale built but not applied — §8), no reflow/clipping is introduced; zoom behaviour unchanged (px sizes scale with zoom as before).
- **`font-display:swap`** avoids invisible-text (WCAG-friendly). No contrast change (colour is P1).
- **Verify at the visual gate:** headings, tables, receipts, order panel, KDS, reports in Arabic under mezze (font-render is the manual gate — CDP-blocked).

## 6. Before/After Screenshots

**Not captured** — CDP freezes on the heavy `pos.html` (persistent all program). Fonts validated as valid woff2 (`file`) + authoritative extraction + 8/8 token-resolution checks. **Manual visual gate:** open `…/pos.html?token=…&appearance=mezze` and confirm Hanken (UI), JetBrains (numbers), IBM Plex + 1.7 leading (Arabic RTL) on Cashier / Payment / Kitchen / Reports / Live Ops in light + dark; then `?appearance=amber` to confirm the amber build is byte-identical.

## 7. Regression Assessment

- **Amber:** `+34 / −1` diff; the single deletion is the **defensive** `--font-num` edit that *preserves* amber's numeric rendering. Harness confirms amber `--font-ui`/`--font-num` resolve to the exact original stacks. Global `@font-face` is lazy + unreferenced by amber → **zero amber font load / zero visual change.**
- **Mezze:** token resolution verified (Hanken/JetBrains/IBM-Plex LTR+RTL, 9-step + leading tokens). Fonts are valid woff2. `node --check` OK; braces balanced.
- **Behaviour/RTL:** no JS/layout/component change; the `dir=rtl` swap uses the existing lang toggle. Business logic untouched.

## 8. Sign-Off Recommendation & Scope Note

**RECOMMEND SIGN-OFF for the P2 *font* migration** (families + self-hosting + token system + Arabic), conditional on the **manual visual gate** (font rendering on the 5 workspaces × light/dark × RTL × amber/mezze).

**Explicit scope decision needed — the 9-step SIZE scale:** the brief asks to "implement the complete 9-step type scale / no component may declare font-size," **and also** "do NOT modify layout / components." These conflict: the approved scale differs from the current sizes (15≠14, 18≠16, 22≠20, 40≠31), so **applying it to components would change font-sizes → reflow layout**, which the brief forbids in the same breath. I therefore **built the size/weight/leading tokens (complete, available) but did NOT rewrite component `font-size`/`font-weight`** (that is a layout-affecting change). The mezze appearance currently uses the **approved fonts at the current sizes**.
→ **Decision for the CTO:** approve a follow-up (P2b) to migrate component `font-size`/`font-weight` onto `--mz-size-*`/`--mz-weight-*` **accepting the resulting layout reflow**, or keep the current sizes. This is the only faithful way to resolve the brief's internal contradiction. Nothing was approximated or invented.

*Not committed to production behaviour — active only when `data-appearance="mezze"` is set. P3 (icons) not started.*
