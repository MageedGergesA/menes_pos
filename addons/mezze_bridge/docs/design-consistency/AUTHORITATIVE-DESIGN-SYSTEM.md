# Mezze — Authoritative Design System (extracted from the original export)

**Source of truth:** `/home/mageed/Downloads/Mezze POS Visual Redesign/export` (the
original Mezze Visual Redesign — **PRIMARY design authority**). This document
faithfully extracts and normalizes that system into an implementable contract. It does
**not** invent a new system. Where the current repo `docs/DESIGN_SYSTEM.md` or the
production code disagrees, **this document (the original source) wins** and the code is
the migration target.

Token values below were read directly from the rendered source harnesses
(`Primitive Library`, `Component Library`) via `getComputedStyle(:root)` — they are the
exact `--mz-` tokens the source ships. Namespace is **`--mz-`**.

Traceability format: **RULE — SOURCE DOCUMENT / SECTION**.

## 1. Philosophy — *Mezze Design System §philosophy*, *Spacing §01-02*, *Typography §01-02*
- **Structure first, color last. 97% neutral, 3% accent, zero decoration.** Food
  photography is the color. — *Design System*
- **Typography/space disappear; the work stays.** Every token carries meaning; nothing
  exists because it "looks nice." — *Typography, Spacing*
- **Speed of scanning + freedom from fatigue** for 9–12h shifts. — *Typography*
- **Status is never color alone** (size + weight + color + space + icon + label). — *all*
- **Two scripts as equals** — Arabic is first-class, optimized not mirrored. — *Typography §08*
- **Built to be correct through 2035.** No gradients, no decorative shadow.

## 2. Token architecture — *Design System §03-05*, *Typography §governance*, *Spacing §04-12*
**Three tiers: primitive → semantic → component.** Primitives hold raw values and are
never referenced by UI. Semantic tokens carry meaning and are the only layer components
consume. Component tokens alias semantics. **Reskinning touches primitives only.**

## 3. Color — *Mezze Design System §primary/§06-08*
Primitives: `clay.500 #C0602E` (brand), `sand.50 #FFFDFB`, `sand.100 #F7F5F1`,
`sand.300 #EAE2D6`, `espresso.900 #2A2420`, `charcoal.night #191510`.

**Brand = Terracotta `#C0602E` (light) / `#D89A54` (dark)** — "earned warmth, not tech
blue"; used on **~3% of pixels** meaning *act here*. **NOT amber/gold.**

| Semantic | Light | Dark |
|---|---|---|
| canvas | `#FFFDFB` | `#191510` |
| workspace | `#F7F5F1` | `#211C15` |
| surface | `#FFFFFF` | `#2A251D` |
| border | `#EAE2D6` | `#3E362E` |
| text.primary | `#2A2420` | `#F5F1EB` |
| text.muted | `#847868` | `#B6AB9A` |
| brand | `#C0602E` | `#D89A54` |

Dark is **authored, not inverted** — warm charcoal, never OLED black.

**10 semantic colors:** Success `#2F7D4A` · Warning `#B5842B` · Danger `#B0433A` ·
Info `#2C6E8F` · VIP `#B08900` · Chef `#7A5C3A` · Vegetarian `#4C8A3F` · Spicy
`#C0392B` · New `#C0602E` (brand) · Popular `#B5842B`. Each justified by restaurant
psychology; status colors only for state.

## 4. Typography — *Mezze Typography System*
**Families:**
- `--mz-font-text: 'Hanken Grotesk', system-ui, -apple-system, sans-serif` (interface)
- `--mz-font-ar: 'IBM Plex Sans Arabic', 'Hanken Grotesk', sans-serif` (Arabic — tuned independently)
- `--mz-font-num: 'JetBrains Mono', 'SFMono-Regular', monospace` (tabular numerics)

**Sizes** `--mz-size-100..900`: 11 / 12 / 13 / 15 / 18 / 22 / 26 / 32 / 40 (~1.2 ratio).
**Weights** `--mz-weight-*`: 400 / 500 / 600 / 700 / 800 (no light weights).

**Semantic roles** (size/lh · weight): display.hero 40/1.05·800 · page.title 32/1.1·800
· section.title 22/1.2·700 · panel.title 18/1.25·700 · card.title/product.name
15/1.25·600 (clamp-2) · order.item 14/1.3·600 · order.modifier 13/1.4·400 ·
navigation.item 14/1.2·500 · navigation.section 11/1.2·700 · button.label 14/1·700 ·
input.label 12/1.3·600 · input.value 15/1.3·500 · dialog.title 19/1.2·700 · dialog.body
13/1.5·400 · badge.label 10/1·700 · caption 12/1.4·400.

**Numeric:** JetBrains Mono, **tabular, right-aligned, fixed 2-decimals** — the decimal
column never moves. order.total/product.price/kds.timer/order.number/analytics.metric.

**Arabic/RTL:** line-height 1.6–1.7, **zero letter-spacing**, Western digits stay LTR
tabular inside RTL, layout mirrors start/end but glyphs re-optimized (never flipped Latin).

## 5. Spacing — *Mezze Spacing System*
**A 4px micro-lattice on an 8px base (the 2× grid).** Base step = 8px; micro = 4px
(optical fixes only); macro = 32–48px. Shares the 4px lattice with type line-height.

**Primitives** `--mz-space-000..1200`: 0 / 2 / 4 / 6 / 8 / 12 / 16 / 20 / 24 / 32 / 48 / 72.
`--mz-touch-gap: 8px`.
**Semantic:** stack.small 8 / medium 16 / large 24; inline.small 4 / medium 8 / large 12;
card.padding 12; product.grid gap 12; panel.padding 16; dialog.padding 20; button.padding
20; input.padding 12; order.item 12; ticket.group 16; section 32; page 72.
Component pads use `calc(token * --mz-density)`.

## 6. Radius — *Primitive/Component Library tokens*
`--mz-radius-sm 8` · `-md 11` · `-lg 14` · `-xl 16` · `-pill 999`. **Max non-pill radius
is 16** (restrained; not the 18/24 in the repo doc).

## 7. Elevation — *Mezze Design System §02*
Five levels **E0 Canvas · E1 Surface · E2 Raised · E3 Floating · E4 Overlay**. Hierarchy
through **luminance, not shadow**: light adds a whisper of shadow + hairline border; dark
brightens the surface. **No decorative shadow, no gradients.**

## 8. Motion — *Mezze Motion System* (tokens)
Durations `--mz-dur-*`: instant 80 · fast 120 · mod 180 · slow 240 · deliberate 320ms.
Eases: standard `cubic-bezier(.2,0,0,1)` · decelerate `(0,0,0,1)` · accelerate
`(.4,0,1,1)` · spring `(.5,1.4,.5,1)`. Honor `prefers-reduced-motion`. Never slow the
cashier/KDS/payment; no marketing animation.

## 9. Density — *Spacing §06*
`--mz-density`: Compact ×0.75 · Standard ×1.0 · Comfortable ×1.25 — one multiplier scales
every semantic token; **layout never changes**, only breathing room. Per-surface defaults:
POS Standard / KDS Comfortable / Tablet Standard / Mobile Compact / Customer & TV Comfortable.

## 10. Iconography & components — *Component Library (T1–T5)*
Line/rounded Material-style icons, **icon + text on every status badge (never
color-only)**. Canonical components: **T1 Primitives** (Button: primary/secondary/ghost/
destructive/loading/disabled/small; IconButton 44px; Input+focus-ring+error; Select/
Checkbox/Radio/Switch; StatusBadge; Tooltip/Progress/Skeleton/Divider) · **T2 Compounds**
(Product Card 6 modes; Category Chip; Quantity Stepper; Payment Tile; Tabs) · **T3
Containers** (Card/Panel/Alert/Toast; Dropdown/Dialog/Toolbar; Data Table/Empty State) ·
**T4 Restaurant** (Order Line; Order Ticket; Course Group; Modifier Group; KDS Ticket;
Kitchen Timer; Status Row; Receipt Preview) · **T5 Compositions** (Cashier Workspace).
Vanilla HTML/CSS/JS — **no React, no Tailwind**.

## 11. Restaurant patterns — *Mezze Restaurant UX Patterns* (to fully extract)
Operational state (table/order/course/KDS/86/payment/delivery) must render the **same
meaning everywhere** (color+icon+label+shape+priority). *[Full pattern set pending a
dedicated read of `Mezze Restaurant UX Patterns.html`; state semantics summarized from
Design System §08 + Component Library T4.]*

## 12. Accessibility — *Design System §09*, *Typography §09*, *Spacing §09*
WCAG **AA is the floor**: text ≥4.5:1 (both themes), non-text ≥3:1, min type 12px,
**44px** min touch (48px primary/mobile), **8px** min gap between targets, 16px safe edge,
**always-visible 2px focus ring**, tabular numerics, hierarchy never weight-alone, full RTL
with logical properties.

## 13. Personal workspace / governance — *Workspace Library, Spacing §11-12, Typography §11-12*
Themes + density + nav + landing + panel side/width + scale are user/workspace settings.
Governance: **components consume semantic tokens only** — a raw px/hex/primitive inside a
component **fails review**; new primitives require justification ("looks better" is not a
reason); deprecations alias for one major version; all spacing stays on the 4px grid.

---

### Canonical `--mz-` token block (for the shared foundation)
```
--mz-font-text:'Hanken Grotesk',system-ui,-apple-system,sans-serif;
--mz-font-ar:'IBM Plex Sans Arabic','Hanken Grotesk',sans-serif;
--mz-font-num:'JetBrains Mono','SFMono-Regular',monospace;
--mz-size-100:11px … --mz-size-900:40px;  --mz-weight-regular:400 … -extrabold:800;
--mz-space-000:0 … --mz-space-1200:72px;  --mz-touch-gap:8px;  --mz-density:1;
--mz-radius-sm:8px;-md:11px;-lg:14px;-xl:16px;-pill:999px;
--mz-dur-instant:80ms;-fast:120ms;-mod:180ms;-slow:240ms;-deliberate:320ms;
--mz-ease-standard:cubic-bezier(.2,0,0,1); … -spring:cubic-bezier(.5,1.4,.5,1);
brand #C0602E/#D89A54; canvas/surface/border/text per §3 light+dark.
```
