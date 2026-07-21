# RC1 Checklist — Pilot Readiness

Legend: ✅ done & evidenced · ⚠️ open, non-blocking · ⛔ blocking · 👤 requires a human (cannot be automated)

---

## 1. Development

| # | Item | Status | Evidence |
|---|---|---|---|
| 1.1 | All seven phases implemented | ✅ | Commits `1d4a75f` → `446e708` |
| 1.2 | No hardcoded design values in components | ✅ | 1,383 → 0 (2 regex artifacts) |
| 1.3 | Token architecture Primitive→Semantic→Component | ✅ | `FINAL_ARCHITECTURE.md` |
| 1.4 | No business logic / workflow / navigation change | ✅ | JS byte-identical in P6/P7; markup tags identical |
| 1.5 | JS parses | ✅ | `node --check` clean every phase |
| 1.6 | CSS braces balanced | ✅ | 1065/1065 |
| 1.7 | No undefined token references | ✅ | 0 undefined across 353 properties |
| 1.8 | No external runtime dependencies | ✅ | All fonts self-hosted; no CDN, no Google Fonts |
| 1.9 | Program closed — no further implementation | ✅ | This is RC1 |

## 2. QA

| # | Item | Status | Evidence |
|---|---|---|---|
| 2.1 | Amber pixel-identical (static) | ✅ | 2,510 declarations, recursive token resolution vs `git HEAD` |
| 2.2 | Amber verified live in browser | ✅ | 0 `.mi`, 71 `<svg>`, amber tokens, system-ui |
| 2.3 | Mezze resolves to approved values live | ✅ | `ALL_PHASES_LIVE: true` |
| 2.4 | Cashier / Payment / Kitchen / Reports / Live Ops | ✅ | Compliance matrix, P7 §2 |
| 2.5 | Light + dark | ✅ | Both verified per workspace |
| 2.6 | RTL | ✅ | Arabic font stack, `.mi direction:ltr`, rail mirrors, 0 clipping |
| 2.7 | All 3 density modes | ✅ | 9.6 / 12 / 15px; no new overflow or clipping |
| 2.8 | Theme switching | ✅ | Runtime attribute toggle re-resolves tokens |
| 2.9 | Text clipping / truncation | ✅ | 0 clipped across all workspaces |
| 2.10 | Overflow | ⚠️ | 1 pre-existing hidden overlay (`.rsvform`); **worse in amber** (133px vs 103px) |
| 2.11 | Long text / large numbers | 👤 | Needs real order data on a terminal |
| 2.12 | End-to-end order → pay → receipt | 👤 | Logic untouched, but must be exercised on a pilot terminal |

## 3. Accessibility

| # | Item | Status | Evidence |
|---|---|---|---|
| 3.1 | Small-text floor raised | ✅ | Payment: amber 8 elements <11px → mezze **0** |
| 3.2 | Reduced motion (OS) | ✅ | Token-level 1ms + `!important` blanket backstop |
| 3.3 | Reduced motion (manual opt-out) | ✅ | `data-mz-motion="off"` → 0.001s, new capability |
| 3.4 | Focus visibility | ✅ | All 8 `outline` declarations unchanged all program |
| 3.5 | Screen-reader labels | ✅ | `aria-label` 63, `role` 16 unchanged; ligatures `aria-hidden` |
| 3.6 | Keyboard navigation | ✅ | No selector/tabindex/handler modified |
| 3.7 | RTL | ✅ | Verified live |
| 3.8 | **Dark danger contrast 2.53:1** | ⛔ | **BLOCKER 1** — fails AA; amber also fails (3.15) but mezze is worse |
| 3.9 | `warn/warn-soft` 2.86:1 | ⚠️ | Pre-existing since P1; property of approved values |
| 3.10 | Touch targets ≥44px | ⚠️ | 10 elements below; **pre-existing**, no `min-height:44px` anywhere; density does not worsen it |

## 4. Performance

| # | Item | Status | Evidence |
|---|---|---|---|
| 4.1 | No new network requests | ✅ | Token indirection only |
| 4.2 | No JS added to hot paths | ✅ | Only `IC()`/`ICboot()` at boot |
| 4.3 | Icon font subsetted | ✅ | 369,656 → 7,552 B (−98.0%) |
| 4.4 | Amber fetches zero font bytes | ✅ | No `.mi` elements → family never referenced |
| 4.5 | Fonts lazy per weight/subset | ✅ | Arabic faces stay unloaded until Arabic renders |
| 4.6 | No layout-triggering motion introduced | ✅ | Keyframes are opacity/transform only |
| 4.7 | File size | ✅ | 404 KB → 464 KB (+14.7%) |
| 4.8 | Terminal-hardware frame rate | 👤 | Measure on real POS hardware during pilot |

## 5. Security

| # | Item | Status | Evidence |
|---|---|---|---|
| 5.1 | No new external origins | ✅ | Self-hosted fonts only; no CDN |
| 5.2 | No new script execution paths | ✅ | No `eval`, no dynamic script, no `createElementNS` |
| 5.3 | XSS posture unchanged | ✅ | `escapeHtml()` boundaries untouched; `IC()` emits a fixed registry string, never user input |
| 5.4 | No new network/data flows | ✅ | No fetch/XHR added |
| 5.5 | Offline capability preserved | ✅ | All assets local |
| 5.6 | No secrets/PII in new code | ✅ | Tokens and font binaries only |

## 6. Design

| # | Item | Status | Evidence |
|---|---|---|---|
| 6.1 | Values taken verbatim from the export | ✅ | No approximation in any phase |
| 6.2 | Nothing invented where the spec is silent | ✅ | All gaps documented, not filled |
| 6.3 | **Violet Delivery CTA** | ⛔ | **BLOCKER 2** — no approved colour for this role |
| 6.4 | Teal (free tables/seats) | ⚠️ | No approved equivalent; retained |
| 6.5 | Letter-spacing (19 tokens) | ⚠️ | Approved system defines none; holds old-typeface tracking |
| 6.6 | 40 unattested ligature names | ⚠️ | Canonical Material Symbols, not sampled in export |
| 6.7 | 5 derived spacing tokens | ⚠️ | Requested by brief, absent from export |
| 6.8 | Material Symbols `FILL` axis inert | ⚠️ | Bundled face is a static instance (no `fvar`) |
| 6.9 | Dark `elev-1: none` | ⚠️ | Approved as specified; removes dark shadow separation |
| 6.10 | Full visual sign-off | 👤 | Every workspace × theme × density on real hardware |

## 7. Deployment

| # | Item | Status | Notes |
|---|---|---|---|
| 7.1 | No build step | ✅ | Single self-contained file |
| 7.2 | No schema/data migration | ✅ | No model touched |
| 7.3 | Ship with amber default | ✅ | Flag absent = certified build |
| 7.4 | Serve `static/fonts/` | 👤 | 19 files must deploy with the addon |
| 7.5 | Cache headers on `/static/fonts/*` | 👤 | Recommended |
| 7.6 | Verify charset header | 👤 | `<meta charset>` now covers it, but confirm the server too |
| 7.7 | 27 commits pushed | 👤 | Currently local only |

## 8. Rollback

| # | Item | Status | Evidence |
|---|---|---|---|
| 8.1 | Documented procedure | ✅ | `ROLLBACK.md` |
| 8.2 | Flag-off reverts completely | ✅ | Amber is the default state |
| 8.3 | Verification script | ✅ | `ROLLBACK.md` §5 (`miIcons === 0`) |
| 8.4 | Emergency path | ✅ | `?appearance=amber` + reload |
| 8.5 | Per-phase revert commits listed | ✅ | `ROLLBACK.md` §3 |
| 8.6 | Rollback rehearsed on a terminal | 👤 | Do once before pilot |

## 9. Monitoring

| # | Item | Status | Notes |
|---|---|---|---|
| 9.1 | Console-error watch during pilot | 👤 | Especially font 404s |
| 9.2 | Font asset 404 monitoring | 👤 | Missing fonts degrade silently to fallbacks |
| 9.3 | Track appearance in use | 👤 | Log `data-appearance` for attribution |
| 9.4 | Staff friction reports | 👤 | Density/legibility feedback |
| 9.5 | Rollback trigger defined | 👤 | Agree the threshold before pilot |

## 10. Pilot Sign-off

| # | Gate | Owner | Status |
|---|---|---|---|
| 10.1 | Engineering: amber unchanged | Eng | ✅ evidenced |
| 10.2 | Design: mezze matches approved | Design | 👤 pending |
| 10.3 | **Design: resolve BLOCKER 1** (dark danger contrast) | Design | ⛔ |
| 10.4 | **Design: resolve BLOCKER 2** (violet CTA) | Design | ⛔ |
| 10.5 | Accessibility sign-off | A11y | 👤 blocked by 10.3 |
| 10.6 | Operations: terminal rehearsal + rollback drill | Ops | 👤 |
| 10.7 | Go/No-Go for **amber-default ship** | Release | ✅ **GO** |
| 10.8 | Go/No-Go for **mezze-default** | Release | ⛔ **NO-GO** until 10.3–10.4 |

---

### Summary

**Ship RC1 with amber as default — all engineering gates pass and production risk is effectively zero.**
**Do not enable mezze as default** until the two design blockers are resolved. Every remaining ⚠️ is either pre-existing in amber or a documented gap in the approved spec — none is an implementation defect.
