# P7 — Visual Convergence & Release Validation (Final Phase)

*Workspace-by-workspace convergence review of the live implementation against the approved export. Two defects found and fixed; no token migration, no redesign.*

---

## 0. The headline: this phase found two real bugs that every prior phase missed

For the first time in the program the app **loaded in a real browser** (served over HTTP at `127.0.0.1:8790`), and CDP responded. That immediately exposed two defects that six phases of static verification had not:

### Bug 1 — CSS comment terminated early, silently killing P5 **and** P6 (CRITICAL)

My own P5 documentation comment contained a literal `*/`:

```
PRIMITIVE (--mz-space-*)  ->  SEMANTIC (--pad-*/--stack-*/--gap-*)  ->  COMPONENT
                                             ↑ closes the CSS comment here
```

The parser closed the comment at `(--pad-*/`, turned the remainder into malformed CSS, and **discarded the entire `:root[data-appearance="mezze"]` block for P5 — which had P6's typography block nested inside it.**

**Impact:** spacing, density and the entire type scale **never applied under mezze**. Live evidence before the fix: `--fs-9` had exactly one definition (`:root{--fs-9:9px}`), `--mz-space-150` resolved to empty, and the real `.rllbl` element rendered at **9px instead of 11px**.

**Why earlier validation missed it:** in P5 and P6 I validated by *reconstructing* the token CSS inside a clean harness page and asserting on that. Those assertions were true — of the simulation. They were never true of the shipped stylesheet. **A simulation of your own code cannot detect that your code failed to parse.** Fixed by rewording the comment; re-verified against the real stylesheet (§7).

### Bug 2 — no `<meta charset>`, entire UI mojibaked (HIGH)

`document.characterSet` was **`windows-1252`**. The file contains **20,518 valid-UTF-8 non-ASCII bytes** and declared no charset anywhere, so every `·`, `…`, `—`, `⌘`, `↵`, `⚠` rendered as mojibake — **and all Arabic would have too**, in a bilingual AR/EN POS. Odoo's static handler likely sends `charset=utf-8` and masks this in production, but any other serving path breaks the entire UI. Fixed with a one-line `<meta charset="utf-8">` at byte 0; verified `UTF-8`, `mojibake_present: false`.

---

## 1. Final Visual Convergence Report

With both fixes in place, **all six phases were verified live in the real stylesheet** (`ALL_PHASES_LIVE: true`):

| Phase | Token | Amber (live) | Mezze (live) | ✓ |
|---|---|--:|--:|:--:|
| P1 Colour | `--accent` | `#EFA23C` | `#D89A54` | ✓ |
| P2 Typography | `--mz-size-100/400` | system stack | `11px / 15px`, Hanken | ✓ |
| P3 Icons | `.mi` / `<svg>` | **0 / 71** + 66 `data-ic` | **67–81 / 4** | ✓ |
| P4A Surface | `--r-lg` / `--r-md` | `18px / 12px` | `14px / 11px` | ✓ |
| P4B Motion | `--dur-fast` / ease | `.13s` / `(.2,.8,.3,1)` | `120ms` / `(.2,0,0,1)` | ✓ |
| P5 Spacing | `--sp-9`, `--pad-dialog` | `9px`, `20px` | `8px`, `20px` | ✓ |
| P6 Type scale | `--fs-9` / `--fs-14` | `9px / 14px` | `11px / 15px` | ✓ |

## 2. Workspace-by-Workspace Compliance Matrix

Measured, not eyeballed — computed styles across every visible element (mezze / dark):

| Workspace | Elements | Icons (mi/svg) | Overflow | Clipped | Text < 11px | Contrast fails | Verdict |
|---|--:|--:|--:|--:|--:|--:|---|
| **Cashier** | 636 | 67 / 4 | 2* | 0 | **0** | 10† | ✅ converged |
| **Payment** | 636 | 81 / 4 | 2* | 0 | **0** | 10† | ✅ converged |
| **Kitchen (KDS)** | 526 | 72 / 4 | 2* | 0 | **0** | 10† | ✅ converged |
| **Reports** | — | ✓ | 2* | 0 | **0** | 10† | ✅ converged |
| **Live Ops** | — | ✓ | 2* | 0 | **0** | 10† | ✅ converged |

\* the same two elements on every workspace — a hidden `.rsvform`/`.rsvrow` inside an overlay. **Pre-existing in amber and worse there** (amber overflows by 133px, mezze by 103px). Not a regression; mezze improves it.
† all ten are the same `.p86` out-of-stock badge repeated across product cards (§4).

**Cross-cutting verification:**

| Dimension | Result |
|---|---|
| Amber / Mezze | Both load correctly; icon swap only under mezze (0 vs 67 `.mi`) |
| Light / Dark | Verified both; token sets resolve per theme |
| RTL | Body font → `IBM Plex Sans Arabic`; `.mi` keeps `direction:ltr` (ligatures shape correctly); rail mirrors (left 6 → 2425); 0 clipping |
| Density (all 3) | `--pad-card` = 9.6 / 12 / 15px; **overflow, clipping and tiny-text all unchanged** — comfortable density introduces no new overflow |
| Reduced motion | `data-mz-motion="off"` → `0.001s` vs `0.12s` live |
| Theme switching | Runtime attribute toggle re-resolves all CSS tokens correctly |

**Small-text readability improved:** on the Payment surface amber has **8** elements under 11px; mezze has **0**.

## 3. Remaining Visual Differences

| # | Expected | Current | Reason | Severity | Fix |
|---|---|---|---|---|---|
| 1 | A brand-coherent Delivery CTA | Violet `#8A7BF0` CTA inside a terracotta palette | `--violet` has **no equivalent in the approved palette** (flagged since P1 §4) | **HIGH** | Needs an approved colour. Cannot be invented — source decision. |
| 2 | Approved teal usage | `--teal #2FB2A8` retained (free tables / seats) | Same: no approved equivalent | MEDIUM | Source decision |
| 3 | Approved letter-spacing | 19 tokens hold amber values | Approved system defines **no** letter-spacing tokens; several are negative tracking tuned for the *old* typeface | MEDIUM | Ratify or supply values |
| 4 | Approved `FILL` state axis | Inert | Bundled Material Symbols face is a **static instance (no `fvar`)** | LOW | Supply the variable font |

## 4. Remaining Accessibility Issues

| Issue | Measured | Severity | Notes |
|---|---|---|---|
| `.p86` out-of-stock badge — white on `--crit` | **2.53** (dark) vs 4.5 required | **HIGH** | Fails AA in dark in *both* appearances, but **mezze is worse** (amber 3.15) because the approved dark danger `#E58A82` is lighter than amber's `#EA6A4C`. Light mode passes in both (5.21 → 5.66, mezze better). Root cause is P1's deliberate choice to keep `--on-color` white on coloured fills. **Fix requires a source decision** (dark ink on light danger fills in dark mode). |
| `warn / warn-soft` | 2.86 | HIGH | Unchanged since P1; property of approved values |
| Touch targets < 44px | 10 per workspace (`.wlink` 226×17, `.rolechip` 95×30, `.conn` 77×30) | MEDIUM | **Pre-existing**; no `min-height:44px` exists anywhere. Density does not worsen it (heights are explicit). |
| Keyboard / focus | No regression — `outline` declarations unchanged all program | ✅ | |
| Screen-reader labels | `aria-label` 63, `role` 16, unchanged; ligatures `aria-hidden` | ✅ | |
| RTL | Verified live | ✅ | |

## 5. Remaining Design Ambiguities

1. **No approved violet / teal** — two live UI roles have no colour in the approved palette (§3).
2. **No approved letter-spacing scale** — 19 tokens unresolved.
3. **Five semantic spacing tokens** (`--inline-sm/-md`, `--section`, `--pad-toolbar`, `--gap-form`) requested by the P5 brief but absent from the export; currently derived.
4. **40 of 55 icon ligatures** are canonical Material Symbols names not attested in the export sample.
5. **`--r-circle` (50%) and `--scrim-spotlight`** have no approved equivalents.
6. **Dark `elev-1: none`** — approved, but removes shadow separation from the most-used elevation in dark.

*None were invented around; all are documented and awaiting source decisions.*

## 6. Before / After Screenshots

Screenshot capture is intermittent on this page (`Page.captureScreenshot` times out while JS stays responsive), but three captures succeeded:

1. **Before** — mezze, pre-fix: visible mojibake (`barcodeâ€¦`, `Cairo Â· Terminal 02`, `âš Bridge offline â€"`) and P5/P6 not applied (9px labels).
2. **After — amber**: mojibake gone, legacy SVG icons, amber palette/radius/type.
3. **After — mezze**: Material Symbols icons, Hanken Grotesk UI, JetBrains Mono figures, terracotta accents, tighter radii/spacing.

Both post-fix captures render cleanly and coherently. Full-fidelity visual sign-off across every workspace × theme × density remains a human gate.

## 7. Final Regression Report

- **Amber pixel-identity across 2,510 declarations: PROVEN** (recursive token resolution, declaration-by-declaration vs `git HEAD`).
- **Markup tag sequence identical. JS byte-identical.** P7's entire diff is **+27 bytes**: one `<meta charset>` line and one reworded comment.
- **Amber verified live in-browser** for the first time: `#EFA23C`, radius `18/12px`, motion `.13s` + amber curve, spacing `9/12px`, type `9/14px`, **0 `.mi` / 71 `<svg>`**, system-ui stack, UTF-8.
- **No business logic, workflow, navigation or component behaviour changed** in any phase.

## 8. Release Readiness Assessment

| Criterion | Status |
|---|---|
| Amber is pixel-identical | ✅ **PROVEN** (static, 2,510 declarations + live browser) |
| Mezze faithfully matches the approved design | ✅ all 6 phases resolve to approved values live |
| No critical regressions | ✅ P7's two bugs found and fixed; nothing outstanding |
| No critical accessibility issues | ⚠️ `.p86` 2.53 fails AA in dark (worse than amber) |
| No unresolved high-severity visual differences | ⚠️ violet CTA has no approved colour |

## 9. GO / NO-GO

**Split recommendation, because the two builds carry very different risk:**

### ✅ GO — ship the code with amber as default

Amber is proven pixel-identical statically *and* live, the diff is token indirection plus a genuine charset bug-fix, and mezze is inert unless `data-appearance="mezze"` is set. **Production risk is effectively zero, and the charset fix is a real robustness win for Arabic.**

### ⛔ NO-GO — do not enable mezze as the default yet

Two blockers, both requiring a **design-source decision** I must not invent around:

| Priority | Item | Action needed |
|---|---|---|
| **1** | `.p86` white-on-danger **2.53** in dark mode (AA fail, worse than amber) | Approve a dark on-colour for light danger fills in dark mode |
| **2** | Violet `#8A7BF0` Delivery CTA in a terracotta palette | Supply an approved colour for the delivery/violet role (and teal) |
| 3 | 19 letter-spacing tokens holding old-typeface tracking | Ratify or supply values |
| 4 | 40 unattested ligature choices; 5 derived spacing tokens | Ratify |

Resolve 1–2 and mezze is releasable.

---

## Final Program Summary — P1 → P7

| Phase | Delivered | Amber proof |
|---|---|---|
| **P1** Colour | 27 `--mz-*` primitives dual-theme + semantic aliases; ~836 consumer sites recoloured, 0 component edits | +52/−0 additive |
| **P2** Typography | 3 fonts self-hosted from the export (18 woff2, 596 KB), full token system, RTL Arabic stack | +34/−1 |
| **P3** Icons | Single icon abstraction; 94/104 icons migrated; Material Symbols subset **369,656 → 7,552 B (−98%)** | Byte-identical SVG re-emission, proven in Node |
| **P4A** Surface | Approved radius + 3-level elevation; hardcoded radius 119→0, shadow 22→0 | 202/202 + 60/60 |
| **P4B** Motion | Approved durations/easings; raw timing 64→0; reduced-motion **cascade bug fixed** | 62/62 + 12/12 |
| **P5** Spacing | 12-step scale + 3-mode density; hardcoded spacing **608→0** (811 substitutions) | 612/612 |
| **P6** Components | 20 families / 442 rules; typography 401+269+32+70→0; **amber font-stack regression caught & fixed** | 2,555 declarations |
| **P7** Convergence | Live validation; **2 critical bugs found & fixed**; full workspace matrix | 2,510 declarations + live |

**Cumulative:** `pos.html` 408,036 → 453,176 bytes (+11%). Zero business-logic, workflow, navigation or component-behaviour changes across all seven phases.

### Overall production readiness

**Ship it with amber as default — that is genuinely low-risk and I would sign off on it today.**

The mezze appearance is **functionally complete and faithful**, and needs two source decisions (contrast, violet) before it can become the default. I'd also record one process lesson honestly: **six phases of static verification passed while a CSS comment silently disabled two entire phases in the shipped file.** Only loading the real page caught it. Any future phase should validate against the live stylesheet, not a reconstruction of it — and I'd treat the visual gate as mandatory rather than advisory for the same reason.
