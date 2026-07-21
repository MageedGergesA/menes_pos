# P4B — Approved Mezze Motion System (Flag-Gated)

*Duration + easing only. Source of truth: `~/Downloads/Mezze POS Visual Redesign/export`. Amber remains the untouched default and is **timing-identical**. No colour, typography, icon, radius, elevation, shadow, border, layout, spacing, density or business-logic change. No choreography change.*

## 1. Motion Implementation Summary

- **All timing comes from tokens.** Declarations still holding a raw duration or easing keyword: **64 → 0**. 73 hardcoded durations and 3 bare `ease` keywords were replaced with semantic tokens.
- **Choreography is untouched.** `transition` declarations **62 → 62**, `animation` declarations **12 → 12**, all **7 `@keyframes` byte-identical**. Property lists, ordering, delays and iteration counts are unchanged — only the timing *values behind the tokens* differ. What faded still fades; what slides still slides.
- **Amber preserved by construction.** Each migrated declaration reads a token whose *amber* value is the literal it had before. Proven mechanically: **62/62 transitions and 12/12 animations** resolve to their `git HEAD` values (§9).
- **Approved system implemented exactly** under `[data-appearance="mezze"]`: 5 durations, 4 easing curves, verbatim from the export.
- **Reduced motion is now token-level** (the approved pattern), *plus* the pre-existing global blanket retained as a backstop — a strict improvement (§5).
- **Structure:** braces 2761=2761, `node --check` OK, 0 undefined tokens.

## 2. Duration Token Mapping

Approved scale: `instant 80ms · fast 120ms · mod 180ms · slow 240ms · deliberate 320ms`.

**Semantic roles** (pre-existing, 15 uses):

| Token | Amber | → Mezze |
|---|--:|--:|
| `--dur-fast` | .13s | **120ms** (`fast`) |
| `--dur-base` | .16s | **180ms** (`mod`) |
| `--dur-slow` | .22s | **240ms** (`slow`) |

**Amber-compat tokens.** The 73 hardcoded durations sat on values that exist on neither scale; snapping them directly would have retimed amber. Each literal became a token holding its exact amber value, re-pointed onto the approved step under mezze:

| Token | Amber | → Mezze step |
|---|--:|---|
| `--dur-100` | .1s | `instant` 80ms |
| `--dur-120` | .12s | `fast` 120ms (exact) |
| `--dur-140` | .14s | `fast` 120ms |
| `--dur-150` | .15s | `fast` 120ms |
| `--dur-180` | .18s | `mod` 180ms (exact) |
| `--dur-200` | .2s | `mod` 180ms |
| `--dur-240` | .24s | `slow` 240ms (exact) |
| `--dur-250` | .25s | `slow` 240ms |
| `--dur-260` | .26s | `slow` 240ms |
| `--dur-300` | .3s | `deliberate` 320ms |
| `--dur-320` | .32s | `deliberate` 320ms (exact) |
| `--dur-340` | .34s | `deliberate` 320ms |
| `--dur-400` | .4s | `deliberate` 320ms |
| `--dur-800` | .8s | **retained** (§10) |
| `--dur-1400` | 1.4s | **retained** |
| `--dur-1600` | 1.6s | **retained** |
| `--dur-1700` | 1.7s | **retained** |

*As in P4A, the numeric tokens are a compatibility layer, not a second scale: they exist only to keep amber timing-identical while routing mezze onto the approved five steps. The public API is `instant/fast/mod/slow/deliberate`.*

## 3. Easing Token Mapping

| Token | Amber | → Mezze (approved, exact) |
|---|---|---|
| `--ease-standard` | `cubic-bezier(.2,.8,.3,1)` | `cubic-bezier(.2,0,0,1)` |
| `--ease-spring` | `cubic-bezier(.2,1.4,.4,1)` | `cubic-bezier(.5,1.4,.5,1)` |
| `--ease-default` | `ease` (the 3 bare keywords) | `cubic-bezier(.2,0,0,1)` |
| `--ease-decelerate` | — | `cubic-bezier(0,0,0,1)` |
| `--ease-accelerate` | — | `cubic-bezier(.4,0,1,1)` |

No curve was approximated; all four are the export's literal values. `--ease-decelerate` / `--ease-accelerate` are defined for the enter/exit vocabulary but currently have **no consumer** — assigning them to existing rules would be a choreography change, so they are declared and left unused (§10).

## 4. Transition Mapping

Every transition kept its property list; only timing was tokenized.

| Interaction | Rules | Amber | → Mezze |
|---|--:|--:|--:|
| **Hover** (background/colour/border, product & button hovers) | 37 bare-duration `transition:` (all-property) | .14s / .15s | 120ms |
| **Pressed** (`transform` on `:active`) | 8 `transform` transitions | .1s / .12s | 80–120ms |
| **Focus** | `outline` is not transitioned (instant ring — unchanged) | — | — |
| **Enter** | `lineIn` .2s/.26s/.4s, `wbin` .25s/.3s, `pop` .4s, `grow` .8s | as listed | 180–320ms (`grow` retained) |
| **Exit** | overlay/opacity fades .15s–.3s | as listed | 120–320ms |
| **Ambient loops** | `pulse` 1.4s, `pulse` 1.6s, `blpulse` 1.7s, `latepulse` 1.4s | unchanged | **retained** |

## 5. prefers-reduced-motion Validation

Implemented the approved pattern — durations neutralised to `1ms` **at the token layer** — plus a manual `[data-mz-motion="off"]` opt-out:

```css
:root[data-mz-motion="off"], :root[data-mz-motion="off"] *{ --mz-dur-*:1ms; }
@media (prefers-reduced-motion:reduce){ :root,:root[data-appearance="mezze"]{ --mz-dur-*:1ms; --dur-*:1ms; } }
```

**A real bug was found and fixed during validation.** The export's own selectors are `[data-mz-motion="off"]` (0,1,0) and `:root` (0,1,0), which work in the export because its tokens live on plain `:root`. In *our* file the appearance block is `:root[data-appearance="mezze"]` — specificity **(0,2,0)** — so both reduced-motion overrides **lost the cascade and did nothing under mezze**. Verified failing in a live browser, then fixed by raising both selectors to `:root[…]` / `:root,:root[data-appearance="mezze"]` (0,2,0, later in source order). Re-verified: **all 5 checks pass**, including `motion_off_beats_appearance` and `reduced_motion_beats_appearance`.

- **All 20 duration tokens** neutralise to `1ms`, including the retained ambient-loop tokens (`--dur-800/1400/1600/1700`) — so pulses stop, not just transitions.
- **The pre-existing global blanket is kept** (`*{animation-duration:.001ms!important;transition-duration:.001ms!important}`) as a backstop, so behaviour is guaranteed even if a rule ever escapes the token layer.
- **Net: preserved and improved** — same guarantee as before, now also honest at the token layer, plus a manual opt-out that did not previously exist.

## 6. Performance Assessment

- **Nothing new is animated.** No transition, animation, keyframe or property list was added.
- **Keyframes are compositor-friendly:** `pulse`, `latepulse` (opacity); `lineIn`, `wbin` (opacity + transform); `grow`, `pop` (transform). `blpulse` animates `box-shadow` — paint, not layout.
- **Two pre-existing layout-triggering transitions** (`left`, `top`) remain. Converting them to `transform` would be exactly the choreography/interaction redesign this phase forbids, so they are **reported, not changed** (§10).
- **37 bare-duration `transition:` declarations animate *all* properties** — a pre-existing pattern that can transition layout properties incidentally. Also reported, not changed.
- **Cost:** CSS custom-property indirection only. No JS, no new assets, no new requests. `pos.html` **426,774 → 430,545 bytes (+3,771)**. Under mezze, durations get *shorter* (e.g. 140→120ms), so total animating time is marginally reduced.

## 7. Accessibility Assessment

- **Focus is instant and unchanged** — `outline` is not transitioned in either appearance, so the ring appears immediately; no `outline` declaration was touched.
- **Motion reduction strengthened** (§5): token-level neutralisation + retained blanket + new manual opt-out.
- **No vestibular-risk motion introduced** — no parallax, spin, or large-displacement movement added; transforms are the same small translations as before.
- **Durations shorten under mezze** (120–320ms vs amber's 130–340ms), which slightly reduces motion exposure.
- **`--dur-1400`-class ambient pulses** remain the only continuously-looping motion; they are fully stopped under reduced motion.

## 8. Before/After Videos or GIFs

**Not captured** — the CDP bridge freezes on the heavy `pos.html` (persistent across every phase), which blocks screen recording as well as screenshots. Timing behaviour was instead verified numerically in a live browser: amber, mezze, `data-mz-motion="off"` and a reduced-motion stand-in were each resolved and asserted (§9).
**Manual gate:** `…/pos.html?token=<t>&appearance=mezze` — exercise **hover, press, focus, dialogs, menus, tooltips, notifications, loading states** across **Cashier / Payment / Kitchen / Reports / Live Ops** in **light + dark + RTL**; then OS-level "reduce motion" to confirm motion stops; then `?appearance=amber` to confirm the certified build is unchanged.

## 9. Regression Assessment

- **Amber timing-identity — proven, not asserted.** Both token tables resolved recursively and compared declaration-by-declaration: **62/62 `transition`** and **12/12 `animation`** resolve to their original values.
- **Choreography preserved:** declaration counts unchanged (62/12), all 7 `@keyframes` identical, property lists/delays/iteration counts identical. The only structural delta is 3 bare `ease` keywords becoming `var(--ease-default)`.
- **Mezze cascade verified in-browser:** durations `80/120/180/240/320` exact; roles map correctly; easing curves exact; ambient loops retained; motion-off and reduced-motion both neutralise to `1ms`.
- **Untouched:** no markup, no JS, no selector, no keyframe body. This phase changed only the right-hand side of `transition`/`animation` declarations and added token definitions.
- **RTL:** no directional motion values (no hardcoded `translateX` sign) were altered; RTL behaviour is exactly as before.

## 10. Recommendation for Sign-Off

**RECOMMEND SIGN-OFF for P4B**, conditional on the **manual gate** (§8) — in particular confirming that the shorter mezze durations still feel right on a real POS terminal, which no static check can answer.

**Items for the design owner:**

1. **Ambient loops retained.** `pulse` 1.4s/1.6s, `blpulse` 1.7s, `grow` .8s have **no approved equivalent** — the approved scale tops out at 320ms, and forcing a 1.4s pulse to 320ms would make it frantic, i.e. a choreography change. Retained verbatim and flagged rather than invented.
2. **`--ease-decelerate` / `--ease-accelerate` are unused.** The approved enter/exit vocabulary is implemented but has no consumer, because assigning curves to existing enter/exit rules would be a choreography change. Approve a follow-up if you want enter/exit rebound to decelerate/accelerate.
3. **Two pre-existing layout-triggering transitions** (`left`, `top`) and **37 all-property transitions** are reported in §6. Fixing them is a performance improvement but an interaction change — out of scope here, worth its own phase.

*Not in production behaviour — active only when `data-appearance="mezze"` is set. P5 not started.*
