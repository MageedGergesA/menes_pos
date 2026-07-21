# Changelog — Mezze Visual Redesign Migration (P1–P7)

All work is **flag-gated**. The certified amber build is the default and is unchanged.
Source of truth throughout: the approved Mezze Visual Redesign export.

Format: [Keep a Changelog](https://keepachangelog.com/). Versioning: RC1 (pilot).

---

## [RC1] — Release Candidate 1

### Added
- `<meta charset="utf-8">` — the file declared no charset and was being decoded as `windows-1252` (see Fixed).
- Two orthogonal appearance axes: `data-appearance` (`amber` default | `mezze`) × `data-theme` (`light` | `dark`), plus `data-mz-density` and `data-mz-motion`.
- Complete `--mz-*` design-token layer: 27 colour primitives, 9-step type scale, 5 weights, 4 leading steps, 5 radii, 3 elevations, 5 durations, 4 easing curves, 12-step spacing scale, 3 density modes.
- Self-hosted fonts (19 files, 587 KB): Hanken Grotesk 400–800, JetBrains Mono 400–700, IBM Plex Sans Arabic 400–700, Material Symbols Rounded (subset).
- Single icon abstraction layer (`ICONS` registry + `IC()` + `ICboot()`).
- `[data-mz-motion="off"]` manual reduced-motion opt-out (did not previously exist).

### Changed
- **1,383 → 2 hardcoded design values** (the 2 are regex artifacts, not literals; genuine count is 0). Every component now resolves through tokens.
- Token adoption: `var()` references **1,099 → 3,184**; distinct custom properties **86 → 353**.
- 94 icons now addressed by registry name instead of inline geometry.

### Fixed
- **CSS comment terminated early, silently disabling P5 and P6** under mezze. A literal `*/` inside a documentation comment (`(--pad-*/--stack-*/…)`) closed the comment, malformed the following CSS, and caused the browser to discard the entire mezze spacing/density/typography block. Spacing, density and the type scale never applied. *(P7)*
- **Missing `<meta charset>`** caused every non-ASCII character — and all Arabic — to mojibake in any serving context that does not send a charset header. *(P7)*
- **Amber font-stack regression**: three plain monospace stacks had been mapped to `var(--font-num)`, which resolves to a different stack. Restored via `--ff-mono-a/b/c`. *(P6)*
- **Reduced-motion cascade failure**: the approved `[data-mz-motion="off"]` / `:root` selectors are specificity (0,1,0) and lost to our (0,2,0) appearance block, so reduced motion did nothing under mezze. Both selectors raised. *(P4B)*
- **Amber numeric-font leak**: the self-hosted JetBrains face could reach amber through an aspirational fallback in `--font-num`. Removed. *(P2)*

### Unchanged (by design)
- Business logic, workflows, navigation, screen layouts, application architecture.
- Markup tag sequence, CSS selector sequence, JS behaviour.
- The certified amber appearance — proven pixel-identical across **2,510 declarations** and verified live in-browser.

---

## [P7] Visual Convergence & Release Validation
First live-browser validation. Found and fixed the two critical bugs above. Verified all six phases resolve to approved values in the real stylesheet; produced the workspace compliance matrix, RTL / density / reduced-motion / theme-switching validation, and the GO/NO-GO assessment. Diff: **+27 bytes**.

## [P6] Component Library
20 component families / 442 rules audited; 20 compliant, 3 structural exceptions. Closed the typography gap P2 deferred: font-size 401→0, font-weight 269→0, line-height 32→0, letter-spacing 70→0, font-family 3→0, colour literals 38→0. Amber proven identical across 2,555 declarations.

## [P5] Spacing & Density
Approved 12-step scale (0–72px) + density modes (.8 / 1 / 1.25). Hardcoded spacing **608 → 0** (811 substitutions, including 107 inline `style=` declarations). Positioning offsets deliberately excluded — density-scaling them would relocate absolutely-positioned elements. Amber proven across 612 declarations.

## [P4B] Motion
Approved durations (80/120/180/240/320 ms) and 4 easing curves. Raw timing **64 → 0**. Choreography untouched: 62 transitions, 12 animations, 7 keyframes all preserved. Ambient loops (1.4–1.7 s) retained — no approved equivalent. Amber proven across 74 declarations.

## [P4A] Surface
Approved radius scale (8/11/14/16/999) and 3-level elevation, dual-theme. Hardcoded radius **119 → 0**, shadow **22 → 0**. Introduced the compatibility-token strategy reused by P5/P6. Amber proven across 262 declarations.

## [P3] Icons
Single icon abstraction; 94 of 104 icons migrated to Material Symbols Rounded. Font subset **369,656 → 7,552 bytes (−98.0%)**, all 55 ligatures verified. Amber re-emits byte-identical legacy SVG. Four documented non-migrations: brand wordmark, sparkline, CSS `url()` lock, empty chart node.

## [P2] Typography
Self-hosted Hanken Grotesk / JetBrains Mono / IBM Plex Sans Arabic, extracted from the approved export and subsetted (18 files, 579 KB). No Google Fonts, no CDN, offline preserved. RTL Arabic-first stack + 1.7 leading. Component size migration deferred (completed in P6).

## [P1] Colour
27 approved `--mz-*` primitives (dual-theme) + semantic aliases re-pointing existing role tokens. ~836 consumer sites recoloured with **zero component edits**. Purely additive: **+52 / −0**.
