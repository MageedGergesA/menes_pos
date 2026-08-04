# Original Design Source Map

**Directory:** `/home/mageed/Downloads/Mezze POS Visual Redesign/export` — **PRIMARY
design authority**. **Exact file count: 40** (all `.html`, self-contained JS-rendered
"Bundled Page" harnesses; content unpacks client-side + embeds the real woff2 fonts).

Read method: rendered over a local static server and read via browser `get_page_text` +
`getComputedStyle(:root)` (the tokens are CSS custom properties, not prose).

**Source-reading status (truthful, do not overstate):**
- **40** export files inventoried.
- **5** foundation/system documents read **completely** (Design System, Typography,
  Spacing, Component Library, Primitive Library) + Motion/weights/density tokens
  extracted from `:root`.
- **Remaining screen/pattern/engine files:** inspected at the token/source-structure
  level only; **full page-specific specification mapping is still pending** and belongs
  to the page-by-page implementation phases. This is **NOT** "40/40 read completely".

## Foundation / design-system documents (Priority 1 — the design language)

| File | Domain | Type | Read | Key rules |
|---|---|---|---|---|
| Mezze Design System.html | color, elevation, philosophy, token architecture | foundation | ✅ | terracotta `#C0602E`; primitive→semantic→component; E0–E4; 97/3; AA |
| Mezze Typography System.html | typography | foundation | ✅ | Hanken Grotesk / IBM Plex Sans Arabic / JetBrains Mono; size 11–40; roles; tabular; RTL |
| Mezze Spacing System.html | spacing | foundation | ✅ | 4px lattice / 8px base; space.000–1200 (0–72); density ×.75/1/1.25; 44px touch |
| Mezze Motion System.html | motion | foundation | ◻ (tokens read) | dur 80–320ms; eases standard/decel/accel/spring |
| Mezze Component Library.html | components (T1–T5) | foundation | ✅ | full component canon; vanilla; icon+text badges |
| Mezze Component Language.html | component semantics | foundation | ◻ | component naming/state language |
| Mezze Restaurant UX Patterns.html | restaurant state patterns | foundation | ◻ | table/order/course/KDS/86/payment/delivery state |
| Foundation Engine.html | Sprint 1 — token harness | foundation-build | ◻ | earliest build layer |
| Primitive Library.html | Sprint 2 — primitives | foundation-build | ✅ | `--mz-` primitives (space/radius/font/motion/weight) |
| Compound Library.html | Sprint 3 — compounds | foundation-build | ◻ | compound components |
| Workspace Library.html | Sprint 4 — workspaces/personalization | foundation-build | ◻ | themes/density/nav/landing |
| Application Shell.html | Sprint 5 — app shell | foundation-build | ◻ | shell/nav structure |
| Mezze Platform SDK.html | platform SDK | reference | ◻ | integration surface |
| Mezze POS Implementation Playbook.html | implementation guidance | governance | ◻ | how to ship the system |
| Mezze Design System.html … (above) | — | — | — | — |

**Sprint build order (precedence within the build):** Foundation Engine (1) →
Primitive Library (2) → Compound Library (3) → Workspace Library (4) → Application
Shell (5). Later sprints assemble earlier primitives; they do not override foundation
rules unless they explicitly say "revised/supersedes".

## Screen / workspace specifications (Priority 3 — how the system manifests)

| File | Screen domain |
|---|---|
| Cashier Order Screen.html | **the live production reference** ("the live implementation ships in Cashier Order Screen") |
| Cashier Workspace Pro.html / Cashier Workspace Specification.html / Cashier Freeze Pack.html | cashier workspace |
| Kitchen Workspace Specification.html / Kitchen Freeze Pack.html | KDS |
| Payment Workspace Specification.html | payment workspace |
| Admin Console.html / Settings.html | admin + settings |
| Restaurant Configuration Specification.html / …Freeze Pack.html | restaurant config |
| Application Shell.html | shell (also foundation-build) |

## Engine / service specifications (business logic — NOT visual authority)

Non-visual (transaction/logic/architecture); use for behavior context, not design:
AI Service, Discount Engine, Order Engine, Offline Engine, Notification Service,
Permission Service, Printing Service, Search Service (+ Freeze Pack), Synchronization
Engine, Tax Engine, Payment Engine, Multi-Tenant SaaS Platform (+ Freeze Pack), Mezze
Enterprise Product Specification.

## Supersession
No document read so far declares itself a "v2 / revised / supersedes" replacement of a
foundation rule — every foundation doc is stamped **v1.0 · single source of truth ·
frozen**. So **Priority 1 (foundation) governs**; the repo `docs/DESIGN_SYSTEM.md` and
production code are downstream and have **drifted** (see `PRECEDENCE-AND-CORRECTIONS.md`).

## Production relevance
The original system is designed to be consumed by "nine products / 500 screens" via one
token layer. Production currently re-declares tokens per file (8+ independent
vocabularies) — the restoration target is a single shared `--mz-` foundation.
