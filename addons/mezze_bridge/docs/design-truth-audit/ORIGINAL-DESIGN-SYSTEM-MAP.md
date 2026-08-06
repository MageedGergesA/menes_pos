# ORIGINAL DESIGN SYSTEM MAP + PRINCIPLES (export terminology preserved)

Governing source documents per dimension, and the authored design INTENT (quoted).

| Dimension | Governing export doc(s) |
|---|---|
| Philosophy / tiers / governance | Mezze Design System, Mezze Component Language |
| Color | Mezze Design System (light+dark maps, 10 semantics) |
| Typography | Mezze Typography System |
| Spacing | Mezze Spacing System |
| Motion | Mezze Motion System |
| Density | Mezze Spacing System (compact/standard/comfortable) |
| Touch | Mezze Spacing System + Restaurant UX Patterns |
| Iconography | Mezze Component Language (Material Symbols Rounded) |
| Primitives → Components → Compounds → Workspaces | Primitive / Component / Compound / Workspace Libraries |
| Restaurant patterns | Mezze Restaurant UX Patterns + Cashier/Kitchen/Payment Workspace Specs |
| Accessibility | Component Language 16-state model + per-doc a11y matrix |
| Arabic / RTL | Typography System + Restaurant UX Patterns |
| Dark / density / flags | Foundation Engine (root-attribute engine) |
| Governance | 5 Freeze Packs + Admin Console + Restaurant Configuration |

## Principles (intent, quoted)

**TYPOGRAPHY** — "Typography disappears. The work becomes obvious." 3 faces chosen "for legibility, not beauty." Humanist grotesque = "open apertures + tall x-height … survive glare and low-quality POS panels." Arabic is "a dedicated family tuned independently — never a mirrored Latin font"; looser leading 1.6–1.7, **zero letter-spacing** (tracking breaks cursive joins). "Restaurant software is numeric software" — every value tabular + right-aligned so "a changing total never shifts layout"; Western digits stay LTR/tabular even inside RTL. Hierarchy = **size + weight + color + space together** ("weight-only contrast fails in glare"). Screens touch **semantic roles, never raw sizes** (raw size in a component = review failure). Min 12px; core 13–15px.

**SPACING** — "Whitespace is information." One 8px/4px lattice shared with line-height. 8px default step; 4px optical only; 32–48px section separation. Grouping law: "Related things sit close; unrelated apart. Distance encodes relationship" — read pre-attentively, "exactly what a rushing cashier needs." Off-grid values auto-rejected.

**COLOR** — "Structure first, color last. **97% neutral, 3% accent, zero decoration**." Terracotta = "clay ovens, spice, Mediterranean earth … ~3% of pixels so when it appears it means *act here*" (explicitly rejecting "tech blue"). Status strictly separated from brand ("used only to communicate state"). **Dark is authored, not inverted** ("warm-charcoal night terminal, never OLED black"). "WCAG AA is the floor, not the goal"; **state never carried by color alone.**

**MOTION** — "Motion that communicates — never decorates … If it doesn't earn its place, it isn't shipped." Operational surfaces animate **80–200ms** ("A cashier on a Friday rush must never wait on an effect"); enter-from-origin / exit-toward-destination; one curve family; reduced-motion honored, "no animation is load-bearing." **Spring = the single sanctioned exception (success/payment-complete only).** Prohibited: decorative bounce/spin, >320ms in the order path, list staggering, waiting on an effect to act. Animate transform/opacity only; nothing flashes >3×/sec.

**DENSITY** — compact .8 / standard 1 / comfortable 1.25 via one multiplier, "same layout, different breathing room." Compact = high-volume/drive-thru/expert; Comfortable = training/accessibility/gloved. Density scales tokens, never layout.

**TOUCH** — 44px min every surface; ≥8px dead space between targets ("a fatigued or gloved tap never hits the wrong control"); destructive actions get *extra* separation; ≥16px edge padding (out of bezel/thumb-occlusion); primary actions within thumb arc; in dense grids "shrink visuals, never the tap area."

**ACCESSIBILITY** — WCAG-AA floor both themes; a component is not "Stable" until it passes Auto + Keyboard + Screen-reader + RTL + Hi-contrast. Visible focus (`outline:2px brand, offset 2px`); 16-state model where **every state pairs color with a second signal (icon/border/motion/text)** so it survives glare, low vision, grayscale.

**ARABIC / RTL** — "Arabic is a first-class layout, never a mirrored screenshot." Mirror on logical start/end; "glyphs re-optimized — never a flipped Latin font." Numerals tabular; RTL is a required gate before Stable. Toggle "English / العربية".

**ICONOGRAPHY** — Material Symbols Rounded, 24px, load-bearing (not decoration). Status = icon+text, never color-only (eco/Veg, local_fire_department/Spicy, fiber_new/New, trending_up/Popular, workspace_premium/VIP, block/86).

## Architecture law
5 tiers: **Primitives → Compounds → Containers → Restaurant → Compositions.** "A component may only reach downward — never sideways into a peer, never upward." Components consume semantic/component tokens only (never primitives directly). The whole system is **frozen v1.0**; the 5 Freeze Packs are the "final engineering addendum … After this, Claude Code implements without inventing behavior."
