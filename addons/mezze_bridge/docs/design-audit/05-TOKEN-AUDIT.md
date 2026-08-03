# 05 — Token Audit

Measured by grep across the 9 production `static/*.html` files + `cashier.css`.
No refactoring performed — evidence only, ranked by impact.

## Per-file token adoption vs hardcoding

| File | CSS vars defined | hardcoded hex colors | hardcoded `font-size:px` | hardcoded `border-radius:px` | box-shadows | hardcoded spacing px |
|---|---:|---:|---:|---:|---:|---:|
| `pos.html` | **340** | 236¹ | **1** | **0** | 56 | 50 |
| `shop.html` | 19 | 76 | 45 | 20 | 11 | 75 |
| `qr.html` | 9 | 37 | 42 | 17 | 3 | 65 |
| `kiosk.html` | 11 | 26 | 29 | 12 | 1 | 36 |
| `onboarding.html` | 13 | 22 | 15 | 7 | 0 | 29 |
| `courses.html` | 17 | 35 | 22 | 15 | 3 | 35 |
| `drivethru.html` | 17 | 36 | 25 | 14 | 3 | 42 |
| `cfd.html` | 14 | 32 | 15 | 4 | 4 | 17 |
| `feedback.html` | 16 | 33 | 8 | 4 | 2 | 12 |

¹ `pos.html`'s 236 hex includes the multi-theme registry definitions + inline SVG
icon fills; its **font-size and radius are ~fully tokenized** (1 and 0 hardcoded),
which is the disciplined target. Every other file inlines its scale.

**Reading:** the DS is genuinely implemented in `pos.html` only. The other eight
surfaces average **~25 hardcoded font-sizes and ~12 hardcoded radii each** and
define their own 9–19-variable palettes.

## Token vocabulary divergence (same concepts, different names)

| Concept | DS / `pos.html` | `qr.html` | `kiosk.html` + `onboarding.html` |
|---|---|---|---|
| bg | `--canvas` | `--bg` | `--bg` |
| card | `--surface` | `--surface` | `--card` / `--card2` |
| brand accent | `--accent` (`#E0982B`) | `--saffron` (`#EFA23C`) | `--acc` (`#e08a3c`) |
| primary text | `--ink` / `--ink-2` / `--ink-3` | `--ink` / `--ink2` | `--txt` / `--mut` |
| success | `--pos` | `--pos` | `--ok` |
| danger | `--crit` | (n/a) | `--danger` |
| radius base | `--r-sm/md/lg/xl` = 8/12/18/24 | `--r` = 16 | `--r` = 22 / 16 |

The **same amber brand** is expressed under three names (`--accent`, `--saffron`,
`--acc`) at three slightly different hex values, and the radius primitive is a
single ad-hoc value per file (16 / 22) rather than the DS scale.

## Radius drift

Distinct `border-radius` px values in use across all files:
`6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 20, 22, 24, 26, 999` — **16 distinct
values** against the DS's 5-step scale (`8 / 12 / 18 / 24 / pill`). Notably the DS
card radius `18` barely appears; files use 16 / 20 / 22 instead.

## Spacing

- **Authoritative primitive = 4px base** (`--space-1..8` = 4/8/12/16/20/24/32/40),
  per `DESIGN_SYSTEM.md §4`, which explicitly says *"Snap to the scale — avoid
  5/7/9/11/13."*
- Off-scale spacing values appear across the non-`pos` files (65–75 hardcoded
  spacing declarations in `shop`/`qr`; heights include 7, 9, 11, 13, 17, 21, 26px).

## Typography

- One DS scale (10 steps, `--text-4xl`…`--text-xs`) — `pos.html` conforms
  (1 hardcoded font-size: a `42px` hero, above the `31px` scale max).
- Other files inline **8–45 font-sizes each** with no shared scale.
- Fonts: DS uses `system-ui …, "Noto Kufi Arabic"` + tabular monospace for numbers.
  Customer/kiosk files use their own stacks (`Hanken Grotesk` / `IBM Plex Arabic`
  in kiosk/onboarding) — **a different type personality per surface.**

## Elevation / shadow

`pos.html` has 56 box-shadow declarations (DS defines `--shadow-sm/md/lg/accent`);
other files use 0–11 ad-hoc shadows. No shared elevation token outside `pos.html`.

## Token debt — ranked by impact

1. **P1 — No shared token layer across surfaces.** The DS lives in `pos.html`; 8
   surfaces re-declare their own. Highest-leverage fix: extract the DS `:root`
   tokens into one shared stylesheet all `static/*.html` import.
2. **P1 — Brand accent triplicated** (`--accent`/`--saffron`/`--acc`, 3 hexes).
3. **P2 — Radius: 16 values vs 5-step scale.**
4. **P2 — Type scale re-inlined per file (8–45 sizes each).**
5. **P2 — Arabic/Latin font stacks differ by surface** (type personality drift).
6. **P3 — `42px` hero in `pos.html` exceeds the 31px scale max** (single instance).

**No tokens were changed. Do not refactor in this task.**
