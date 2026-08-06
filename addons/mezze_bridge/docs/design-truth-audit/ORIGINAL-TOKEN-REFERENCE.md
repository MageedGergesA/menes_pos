# ORIGINAL TOKEN REFERENCE — reconstructed from the Visual Redesign export

Source: `/home/mageed/Downloads/Mezze POS Visual Redesign/export` (PRIMARY authority).
Extracted verbatim from the bundles' embedded CSS custom properties + authored dark map.
Dark ramp trigger in the export: **`[data-mz-theme="dark"]`** (authored, not inverted).
Density trigger: `[data-mz-density="compact|standard|comfortable"]`. Reduced motion collapses all durations to 1ms.

## Fonts (exact stacks)
| Token | Value |
|---|---|
| `--mz-font-text` | `'Hanken Grotesk', system-ui, -apple-system, sans-serif` (English/UI) |
| `--mz-font-ar` | `'IBM Plex Sans Arabic', 'Hanken Grotesk', sans-serif` (Arabic) |
| `--mz-font-num` | `'JetBrains Mono', 'SFMono-Regular', monospace` (numeric, `tabular-nums`) |
| icons | `'Material Symbols Rounded'`, 24px |
| weights | regular 400 · medium 500 · semibold 600 · bold 700 · extrabold 800 |

## Color — LIGHT | DARK (authored, warm-charcoal night — never OLED black)
| Token | Light | Dark |
|---|---|---|
| brand | #C0602E | **#D89A54** |
| brand-hover | #AC5427 | #E2A860 |
| brand-press | #984922 | #C98C48 |
| brand-soft | #F6E9E0 | #3A2E1F |
| on-brand | #FFFFFF | #1C1305 |
| canvas | #FFFDFB | #191510 |
| workspace | #F7F5F1 | #211C15 |
| surface | #FFFFFF | #2A251D |
| surface-2 | #FAF6F0 | #332D23 |
| surface-3 | #EFE7DB | #3E362B |
| text | #2A2420 | #F5F1EB |
| text-2 | #4A4038 | #E4DBCC |
| text-mut | #786A57 | #B6AB9A |
| text-faint | #9A8C79 | #8A7E6E |
| border | #EAE2D6 | #453E33 |
| border-strong | #D6C7B2 | #5A4E3F |
| divider | #F1EBE1 | #332D23 |
| **ok** | #2F7D4A | #5FB884 (soft #E6F1E8 / #1E332A) |
| **warn** | #B5842B | #E0B24C (soft #F6EDD8 / #352C18) |
| **danger** | #B0433A | #E58A82 (soft #F7E4E1 / #3A2420) |
| **info** | #2C6E8F | #6FB2D0 (soft #E2EEF3 / #1C2E38) |
| **vip** (gold/loyalty) | #B08900 | #E5C558 |
| focus / ring | #C0602E | #D89A54 |
| scrim | rgba(38,32,26,.42) | rgba(0,0,0,.62) |
| elev-1 | 0 1px 2px rgba(42,36,32,.06) | none |
| elev-2 | 0 6px 16px -8px rgba(42,36,32,.16) | 0 6px 18px -8px rgba(0,0,0,.5) |
| elev-3 | 0 18px 40px -14px rgba(42,36,32,.24) | 0 22px 48px -16px rgba(0,0,0,.7) |

**Menu semantics** (distinct from status): house/brand=warm brown, veg=botanical green, spicy=red-orange, new=terracotta, popular=amber.
**No `--mz-active` / `--mz-offline` / `--mz-violet` / `--mz-accent` token exists.** The palette is deliberately warm-only (no purple). offline→info/neutral; active/selected→brand; on-danger→on-brand/#FFFFFF.

## Radius / Spacing / Type / Density / Motion (theme-invariant)
- **Radius:** sm 8 · md 11 · lg 14 · xl 16 · pill 999
- **Spacing (4px grid):** 000=0 · 025=2 · 050=4 · 075=6 · 100=8 · 150=12 · 200=16 · 300=20 · 400=24 · 600=32 · 800=48 · 1200=72. Semantic: stack-sm/md/lg, inline-sm/md, gap-grid, pad-card 12 / pad-panel 16 / pad-dialog 20 — all `× --mz-density`.
- **Type scale (~1.2):** 100=11 · 200=12 · 300=13 · 400=15 · 500=18 · 600=22 · 700=26 · 800=32 · 900=40. Leading: tight 1.2 · normal 1.4 · relaxed 1.55 · **ar 1.7**.
- **Touch:** 44 · touch-lg 48 · touch-gap 8.
- **Density:** compact .8 · standard 1 · comfortable 1.25 (single multiplier; never touches layout).
- **Motion:** instant 80 · fast 120 · mod 180 · slow 240 · deliberate 320 (ms). Eases: standard `cubic-bezier(.2,0,0,1)` · decelerate `(0,0,0,1)` · accelerate `(.4,0,1,1)` · spring `(.5,1.4,.5,1)` (spring = success/payment-complete only).

## Known-foundations verification (all CONFIRMED, none corrected)
English=Hanken Grotesk ✅ · Arabic=IBM Plex Sans Arabic ✅ · Numeric=JetBrains Mono ✅ · Brand Light=#C0602E ✅ · Brand Dark=#D89A54 ✅ · Spacing 4/8px ✅ · Radius 8/11/14/16/pill ✅.
