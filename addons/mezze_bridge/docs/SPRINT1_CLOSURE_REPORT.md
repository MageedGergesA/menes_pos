# Sprint 1 — Design System Foundation · Closure Report

*Frontend: `mezze_bridge/static/pos.html`. Objective: centralize design tokens; normalize radius/z-index/motion/colour — pixel-identical, zero behaviour change. Baseline `59b5605` → head `6050b04`. Not pushed/squashed.*

## 1. Executive summary
Sprint 1 established a **centralized design-token foundation** and migrated **value-identical** radius, z-index, motion and colour literals onto it, with **pixel-identical rendering and zero behaviour change**, proven by a token-resolution oracle + computed-style checks in both themes. **156 value-preserving edits** (97 literal→token migrations + 59 dead-fallback removals); **33 tokens introduced**; **0 HTML/JS/Python/route/handler/business-logic changes** (every diff hunk inside `<style>`, max line 1067 ≤ 1070). One ADR raised, one latent bug discovered (`--ok` undefined), primitive extraction correctly a no-op. No regressions.

## 2. Files modified
| File | Change |
|---|---|
| `static/pos.html` | token foundation + radius/z/motion/colour migrations (259 lines, **all inside `<style>`**) |
| `docs/SPRINT1_FOUNDATION.md` | engineering history + verification methodology (new) |
| `docs/adr/ADR-0001-z-index-ladder.md` | ADR (new) |
| `docs/SPRINT1_CLOSURE_REPORT.md` | this report (new) |
Backend (`*.py`, `security/`, `controllers/`, `__manifest__.py`): **0 files changed.**

## 3. Commit history (local, unpushed — 7 incl. this report)
```
851037e  Step 2  add centralized design-token foundation
7af0663  Step 3  migrate value-identical radii to tokens
1703252  Step 4  migrate value-identical z-index to tokens
3713d32  Step 5  migrate value-identical motion to tokens
8828068  Step 6  remove dead colour fallbacks
6050b04  Step 7  primitive extraction analysis (no-op)
(Step 8) closure report + final verification
```

## 4. Tokens introduced (33, all additive)
- **Radius (2):** `--r-pill 999px`, `--r-circle 50%`
- **Spacing (8):** `--space-1..8` = 4/8/12/16/20/24/32/40px
- **Type (9):** `--text-xs..4xl` = 11/12/13/14/16/18/20/26/31px
- **Motion (5):** `--dur-fast .13s / --dur-base .16s / --dur-slow .22s`, `--ease-standard cubic-bezier(.2,.8,.3,1) / --ease-spring cubic-bezier(.2,1.4,.4,1)`
- **Z-index (7):** `--z-base 1 / --z-dropdown 20 / --z-sticky 30 / --z-overlay 50 / --z-sheet 52 / --z-modal 60 / --z-toast 120`
- **Colour (2):** `--warn-soft` (theme-adaptive `color-mix(--warn 15%)`), `--on-color #fff`
*(Spacing, type, `--z-base/dropdown/sticky/modal`, `--on-color`, `--warn-soft` remain defined-but-unused this sprint — foundation for Sprint 2.)*

## 5. Radius migration statistics
- **Migrated 73** value-identical literals → tokens (+2 pre-existing tokenized): `8px→--r-sm`(14), `12px→--r-md`(26), `24px→--r-xl`(1), `999px→--r-pill`(9), `50%→--r-circle`(23).
- **Left literal (off-scale, ~113):** 4/5/6/7/9/10/11/13/14/15/16/20/22/26/99px — snapping would move pixels (deferred to appearance sprint).
- **Left literal (JS/HTML inline):** `12px`×1, `999px`×1 outside `<style>` (preserve HTML/JS).

## 6. z-index migration statistics
- **Migrated 3** (value + semantics both correct): `.overlay 50→--z-overlay`, `.sheet 52→--z-sheet`, `.waiterbell 120→--z-toast`.
- **Held 4** (value-match, semantic-mismatch → misleading): `.chair 1`, `.railtip 20`, `.hintbar 30`, `.branchmenu 60` — see ADR-0001.
- **Left literal (no token):** 2/3/4/5/49/55/56/70/80/90/95/96/200 + JS overlay values 92–96.

## 7. Motion migration statistics
- **Migrated 21:** `cubic-bezier(.2,.8,.3,1)→--ease-standard`(9), `cubic-bezier(.2,1.4,.4,1)→--ease-spring`(1), `.13s→--dur-fast`(8), `.16s→--dur-base`(3).
- **Not normalized (left literal):** `.14s`(22), `.15s`(16), `.12s`(7), `.2s`(12), `.18/.24/.25/.26/.3/.32/.34s` — no matching token; snapping would change timing. `--dur-slow .22s` has no real usage.

## 8. Colour cleanup statistics
- **Removed 59** provably-dead fallbacks in `<style>`: `var(--tok,#old)→var(--tok)` for `--pos`(28), `--violet`(10), `--pos-soft`(7), `--warn`(4), `--violet-soft`(3), `--crit`(2), `--surface-3`(2), `--muted`(1), `--line`(1), `--shadow-lg`(1).
- **Preserved (load-bearing):** `var(--ok,#2f9e6b)`×3 — `--ok` is undefined.
- **Deferred:** ~10 dead fallbacks inside JS-inline strings (`--crit`×6, `--violet`×3, `--warn`×1) — preserve JS.
- **Off-token hex left untouched:** `#d64545/#c9821f/#2f9e6b` — theme-invariant literals no theme-variant token equals in both themes.

## 9. Primitive extraction outcome
**No-op by design.** 944 rules parsed; 84 byte-identical bodies found — all coincidental value-sharing across unrelated components; merging violates "same cascade" and manufactures coupling. Zero extractions (quality > quantity). 84 duplicates catalogued as Sprint 2 input.

## 10. Verification methodology and results
**Authoritative oracle:** token-resolution proof — each substituted token resolves to the exact old literal, so CSS guarantees identical computed output for every element of that class (data-independent). **Confirmed by** targeted computed-style checks in **light + dark**. Whole-view fingerprints are informational only (proven reload-noisy via git-stash control, Step 3).
**Results:** every introduced token resolves to its exact value (both themes); every migrated radius/z/motion/colour element computes the old value (`.modal` 24px + `cubic-bezier(0.2,0.8,0.3,1)`; `.chip` 999px; `.railbtn` `0.16s,0.16s`; delivery = `--violet` #6552CE/#8A7BF0); every deferred literal unchanged (`.verb` 11px/.14s, `.railbtn` 14px, `.branchmenu` z60, `.railtip` z20); `--ok` UNDEF (load-bearing preserved). **Syntax:** braces 2581=2581; `<style>` parens 1222=1222; `<style>`/`<script>` tags intact. **Scope:** all diff hunks ≤ line 1067; 0 non-CSS added lines; 0 backend files.

## 11. ADRs created
- **ADR-0001** — the z-index token ladder must describe real layering, not numeric coincidence (Accepted, deferred to Sprint 2).

## 12. Deferred work and rationale
| Deferred | Rationale |
|---|---|
| ~113 off-scale radii | snapping to the scale moves pixels (appearance sprint, flag-gated) |
| 4 held z-index values + JS overlay values | ADR-0001 — need a semantic ladder, not numeric coincidence |
| non-matching motion durations | no exact token; snapping changes timing |
| ~10 JS-inline dead fallbacks + 2 inline radii | preserve JS this sprint (CSS-scoped) |
| primitive/component consolidation (7 buttons, badges) | requires *changing* computed output → frozen component library (Sprint 2) |
| type-scale rationalization (32 sizes) | lossy; changes pixels |
| frozen `--mz-*` terracotta/Hanken migration | deliberately appearance-changing (later sprint) |

## 13. Known bugs discovered
- **`--ok` is undefined** → `var(--ok,#2f9e6b)` (×3) renders the fallback `#2f9e6b` instead of a themed success colour (no dark-mode adaptation). Latent since before Sprint 1. **Sprint 2:** define `--ok` or remap to `--pos`.
- **Whole-file paren count −1** (6285 vs 6284) — **pre-existing** (present at `59b5605`), located in JS/text (string/regex/prose), not CSS. Not introduced by Sprint 1; benign.

## 14. Recommended Sprint 2 backlog
1. **Fix `--ok`** (define or remap to `--pos`; migrate the 3 usages).
2. **Redesign the z-index ladder** (ADR-0001): semantic layers, reconcile JS overlay values 92–96, migrate held values.
3. **Component consolidation** onto the frozen library: one `.btn` (7→1), one `.badge`+`.st-*` (uses the 84-duplicate catalogue).
4. **Frozen `--mz-*` design-system migration** (terracotta `#C0602E`, Hanken/IBM Plex/JetBrains) — flag-gated, appearance-changing.
5. **Type-scale + spacing rationalization** onto `--text-*`/`--space-*` (appearance sprint).
6. **JS-inline cleanup**: dead fallbacks, inline radii/styles.
7. **Motion**: accept literals or add exact-value duration tokens.
8. **Cross-file token unification** (customer pages: shop/qr/drivethru/feedback/cfd/courses).
9. **Accessibility (Platform-Polish Pass 2)**: input focus-ring suppression, `aria-live`/`aria-modal`/focus-trap, light-theme contrast.

## 15. Final readiness assessment
Sprint 1 objectives **met**: a real, centralized token layer now exists; radius/z/motion/colour-fallbacks are normalized value-identically; **zero regressions** (both themes, computed-style proven); full reversible audit trail. The frontend is now a sound foundation for Sprint 2's appearance migration and component consolidation. **Readiness: ready to merge.**

## 16. Recommended merge & push strategy
The 6 code+doc commits are atomic, reversible, and individually verified — **recommend preserving them as discrete history** (do not squash away the audit trail) when ready:
1. `git push origin main` (the 7 local commits).
2. Optionally rebuild `review/full` (reset to baseline → `merge --squash main` → force-push) for a single-diff review artifact, per the established flow.
**Not executed** — awaiting approval (Sprint 1 kept local per instruction).
