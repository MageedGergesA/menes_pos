# Final Architecture — Mezze Design System

---

## Before

A single-file POS with design values written directly into components.

```
pos.html
├── <style>
│   ├── :root { 86 custom properties }        ← partial, inconsistently used
│   └── ~1,065 component rules
│         .card    { background:#17130C; padding:16px 17px; border-radius:18px;
│                    box-shadow:0 1px 2px rgba(40,32,14,.06); font-size:13px }
│         .prod    { padding:9px; border-radius:11px; transition:.14s }
│         .modal   { border-radius:22px 22px 0 0; padding:20px 24px 28px }
│                        ↑ 1,383 hardcoded design values
├── markup with 104 inline <svg> icon geometries
└── <script> with icon path strings stored in data (tn.ic, r.ic, mk(…))
```

**Consequences**
- A visual change meant editing dozens of rules and hoping none were missed.
- 104 icons were geometry embedded in markup, JS strings, and JS data — three places, no single source.
- Two visual identities were impossible: values had exactly one home.
- No density, no motion scale, no reduced-motion opt-out.
- No `<meta charset>` — all Arabic mojibaked wherever the header was absent.

---

## After

One component layer, two appearances, four orthogonal axes.

```
                    ┌──────────────── APPEARANCE AXIS ────────────────┐
                    │  (absent) = AMBER            data-appearance="mezze"
                    │       literals                  approved system
                    └─────────────────────────────────────────────────┘

  LAYER 1 · PRIMITIVES        (mezze; amber holds literals)
    --mz-brand --mz-canvas --mz-text --mz-ok --mz-danger …        27 colours
    --mz-size-100…900  --mz-weight-*  --mz-leading-*               type
    --mz-radius-sm…pill    --mz-elev-1…3                           surface
    --mz-dur-instant…deliberate   --mz-ease-*                      motion
    --mz-space-000…1200 (12 steps)   --mz-density (.8|1|1.25)      spacing
                              │
                              │  × var(--mz-density) where applicable
                              ▼
  LAYER 2 · SEMANTIC          role-named, appearance-agnostic
    --accent --surface --ink --border --pos --warn --crit --info
    --pad-card --pad-panel --pad-dialog --gap-grid --stack-sm|md|lg
    --font-ui --font-num --touch --touch-lg
                              │
                              ▼
  LAYER 3 · COMPONENT         one per migrated literal (compat layer)
    --sp-4…52   --r-4…99   --fs-8…40   --fw-400…900   --dur-100…1700
    --shadow-sm|md|lg  --ring-*  --ls-*  --lh-*
                              │
                              ▼
  LAYER 4 · COMPONENTS        never contain a literal
    .card { background:var(--surface); padding:var(--sp-17) var(--sp-18);
            border-radius:var(--r-lg); box-shadow:var(--shadow-sm);
            font-size:var(--fs-13) }

  ICONS  (content, not style — needs its own indirection)
    ICONS registry ──► IC('close') ──┬─ amber : byte-identical legacy <svg>
                                     └─ mezze : <span class="mi">close</span>
```

### The four axes

| Axis | Attribute | Values |
|---|---|---|
| Appearance | `data-appearance` | *absent* = amber · `mezze` |
| Theme | `data-theme` | *absent* = OS · `light` · `dark` |
| Density | `data-mz-density` | `compact` · `standard` · `comfortable` |
| Motion | `data-mz-motion` | `off` |

They compose freely: `[data-appearance="mezze"][data-theme="dark"][data-mz-density="compact"]` is defined and verified.

---

## Why it is built this way

**1. The compatibility-token layer exists to protect amber, not to be a second scale.**
The amber literals sat on values (9, 13, 14, 22, 26px…) present on neither the old nor the approved scale. Snapping them straight onto the approved steps would have moved amber by 1–2px — breaking the pixel-identity invariant. So each literal became a token holding its exact amber value, re-pointed to the approved step under mezze. The public API remains the approved scale; `--sp-*`/`--fs-*`/`--r-*` are plumbing.

**2. Icons needed a different mechanism from everything else.**
Colour, type, spacing, radius, shadow and motion are *properties* — the browser inherits them onto untouched markup, so P1/P2/P4/P5 changed zero component rules. An icon is *content*: turning `<path d="…">` into a font ligature requires changing what is inside the element. Hence the registry + `IC()` + boot-swap, and hence P3 is the only phase that touched call sites.

**3. Amber pays nothing.**
No `.mi` elements exist under amber, so the Material Symbols family is never referenced and the font is never fetched. Amber's compat tokens are literals, so density has no effect. The certified build is untouched in behaviour *and* cost.

**4. Specificity is load-bearing.**
`:root[data-appearance="mezze"]` is (0,2,0). Overrides must meet or beat it *and* come later. The export's own selectors are (0,1,0) because its tokens live on a flat `:root` — copying them verbatim shipped a silently broken reduced-motion implementation (fixed in P4B). Density selectors are deliberately (0,3,0).

---

## Before → After at a glance

| | Before | After |
|---|--:|--:|
| Hardcoded design values | 1,383 | **0** |
| Custom properties | 86 | **353** |
| `var()` references | 1,099 | **3,184** |
| Icon sources of truth | 3 (markup, JS strings, JS data) | **1 registry** |
| Visual identities supported | 1 | **2**, switchable at boot |
| Density modes | 0 | **3** |
| Reduced-motion opt-out | none | **token-level + manual** |
| External dependencies | 0 | **0** (preserved) |
| Declared text encoding | **none** | UTF-8 |

## What did not change

Business logic · workflows · navigation · screen layouts · application architecture · markup tag sequence (3,410) · CSS selector sequence (1,065) · JS behaviour · the amber appearance (2,510 declarations proven identical).

## Known architectural limitations

1. **The flag is read once at boot.** CSS re-resolves on runtime attribute changes, but `ICboot()` swaps icons only at startup — appearance changes require a reload.
2. **Compat tokens are a translation layer, not a design scale.** If amber is ever retired, they should collapse into the approved scale.
3. **The bundled Material Symbols face is a static instance** (no `fvar`), so the approved `FILL/wght/GRAD/opsz` axes are inert.
4. **Six documented gaps in the approved spec** (violet, teal, letter-spacing, 5 spacing aliases, 40 ligature names, `FILL`) are carried as explicit exceptions rather than invented values.
