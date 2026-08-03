# 09 — Top 20 Product-Wide Design Issues

Severity: **P0** financial/operational/user-error risk · **P1** materially slows work
or confuses · **P2** visible consistency/polish · **P3** cosmetic. No trivial pixel
nits. "Effort" S/M/L. Nothing implemented.

| # | Sev | Issue | Screens | Principle violated | User/ops impact | Recommended | Token/component | Effort |
|--|--|--|--|--|--|--|--|--|
| 1 | P1 | Design system implemented in `pos.html` only; 8 surfaces have own token vocabularies | all non-pos | Enterprise consistency | Product reads as several apps; drift compounds | Extract DS `:root` into one shared stylesheet imported everywhere | `--*` tokens | L |
| 2 | P1 | Brand accent triplicated (`--accent`/`--saffron`/`--acc`, 3 hexes) | qr, kiosk, onboarding, shop | Consistency, brand | Inconsistent brand color across journey | One `--accent` token | color tokens | S |
| 3 | P1 | No visible focus in `kiosk.html` + `onboarding.html`; onboarding has 0 ARIA | kiosk, onboarding | Accessibility | Keyboard users can't see focus; SR users lost in admin | Add DS focus ring + ARIA | focus, aria | M |
| 4 | P1 | Modals lack `role=dialog`/`aria-modal`/focus-trap outside `pos.html` | shop, qr, kiosk | Accessibility | Dialogs not announced/trapped | Shared modal component w/ dialog semantics | modal | M |
| 5 | P1 | 14 flat co-equal staff top-level destinations; format workspaces always shown | pos shell | Cognitive load, IA | Operator scans long nav for 3–4 daily tools | Tier nav (Sell/Manage/Configure) + gate by commercial profile | shell/nav | M |
| 6 | P1 | Low-contrast muted tier (`--ink-3` 3.76:1, status 3.6–3.87) may be used for small body text on non-pos surfaces | shop, qr, kiosk, onboarding | Accessibility (contrast) | Hard-to-read secondary text | Restrict muted to ≥14px/bold; darken customer `--mut` | color tokens | S–M |
| 7 | P1 | No `aria-live` for cart/payment/KDS async updates outside `pos.html` | shop, qr, kiosk | Accessibility | SR users don't hear state changes | Add live regions to shared toast/status | aria-live | M |
| 8 | P2 | Primary-action button has ≥4 implementations (`.btn/.primary/.addbtn/.svcbtn/.startbtn/.review/.pay*`) | all | Consistency | Inconsistent CTA look/behaviour/press feedback | One button component, variants by color/size | button | M |
| 9 | P2 | Radius drift: 16 distinct values vs DS 5-step (8/12/18/24/pill) | all non-pos | Consistency | Mixed corner language; DS card=18 rarely used | Adopt DS radius scale | `--r-*` | M |
| 10 | P2 | Type scale re-inlined per file (8–45 hardcoded sizes) | all non-pos | Consistency, readability | Numbers/labels don't scan uniformly | Shared `--text-*` scale | typography | M |
| 11 | P2 | Two font identities (system-ui/Noto Kufi vs Hanken/IBM Plex Arabic) | kiosk, onboarding vs rest | Brand consistency | Different type personality per surface | Pick one family pair product-wide | font tokens | M |
| 12 | P2 | Dark mode incomplete: kiosk not on theme registry; onboarding no `prefers-color-scheme` | kiosk, onboarding | Consistency, dark | Inconsistent/absent dark behaviour | Shared theming contract | theme | M |
| 13 | P2 | Sub-44px controls in `shop.html`/`qr.html` (26–40px) | shop, qr | Touch usability | Mis-taps on customer phones | Enforce 44px min on interactive | button/chip | S |
| 14 | P2 | Status/86/availability may be color-adjacent on customer surfaces (verify not color-only) | shop, qr, kiosk | Status-not-color-alone | Colorblind/ambiguous state | Icon+label+sign per DS state matrix | status | S–M |
| 15 | P2 | Unnamed icon-only buttons (~20 in `pos.html`) | pos + others | Accessibility | Icon meaning unclear; SR silent | Add `aria-label` to icon buttons | icon-button | S |
| 16 | P2 | Customer journey crosses separate files/tokens (pickup↔delivery↔payment seam) | shop, qr, checkout | Consistency | Journey feels like different sites | Shared customer shell/tokens | shell | M–L |
| 17 | P2 | Onboarding/Go-Live console not linked from staff Settings; standalone URL | onboarding | IA discoverability | New admin can't find setup | Link from Settings | nav | S |
| 18 | P2 | Demo affordances ("Toggle offline demo", "Replay tour") in production shell chrome | pos shell | Enterprise polish | Reads as prototype, not product | Gate behind debug/demo profile | shell | S |
| 19 | P3 | Physical `left/right`/`margin-left` spacing (won't RTL-mirror) in customer files | shop, qr | RTL correctness | Layout mirrors incorrectly in Arabic | Logical properties (`margin-inline`) | spacing | M |
| 20 | P3 | `42px` hero font in `pos.html` exceeds 31px scale max; misc off-scale spacing | pos + others | Token discipline | Minor scale creep | Snap to scale | tokens | S |

**No P0 design issues found.** The financial/operational risk surfaces (payment,
refund, session, reconciliation) are the *strongest* design areas (explicit hierarchy,
confirmation discipline, error-prevention 4–5). The real problems are **consistency +
accessibility across the non-flagship surfaces**, not operational-risk design defects.
