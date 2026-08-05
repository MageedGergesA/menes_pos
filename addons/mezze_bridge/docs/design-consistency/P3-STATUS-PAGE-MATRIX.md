# P3-STATUS-PAGE-MATRIX (DESIGN-P3B)

Status = operational state · Badge = quiet metadata · excluded = chips/filters/tabs/card-modifiers.
Canonical = `.mz-status` / `.mz-badge` (components.css).

| Page | Statuses present | Badges | Excluded (family) | Canonical? | Colour-independent? | EN | AR | Light | Dark | Console | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| onboarding (Go-Live) | PASS/WARN/FAIL/NOT-TESTED/NA + setup-complete | "optional" | — | **yes** | yes (text + dashed shape) | ✓ | (RTL font wired) | ✓ | ✓ | 0 | **PASS** |
| checkout (Payment) | ready/confirming/pending/paid/failed/canceled | — | — | **yes** (`.pay-msg` semantic) | yes (icon+text) | (native i18n) | (RTL) | ✓ | ✓ | 0 | **PASS** |
| shop | store open/closed | product COMBO tag (card) | chips/filters (P3I) | **yes** (open/closed) | yes (dot+text) | ✓ | ✓ | ✓ | ✓ | 0 | **PASS** |
| pos (prototype) | status-badge→**mz-status** (reservation/delivery/waitlist/session); conn→**mz-status**; kstate **pending** | admin-badge→consumes --mz- (collision resolved) | st-* card modifiers (P3G), chips (P3I) | **mostly** (kstate pending) | yes (text + dot) | — | — | ✓ (dark) | ✓ | 0 | **ADVANCED** (kstate + live-panel verify remain) |
| cashier (Owl) | connectivity / payment status | — | method chips (P3I) | **pending** (auth render) | — | — | — | — | — | — | **PENDING** |
| qr | order status | etabadge | tip/mod chips (P3I) | **pending** | — | — | — | — | — | 0 | **PENDING** |
| kiosk | availability / order confirmation | — | — | **pending** | — | — | — | — | — | 0 | **PENDING** |
| cfd / drivethru / feedback | order/eta display | etabadge | — | **pending** | — | — | — | — | — | 0 | **PENDING** |

## Component-level (canonical `.mz-status`, all 9 variants) — browser-verified
EN ✓ · dark ✓ · light ✓ · RTL font wired · contrast AA both modes (light 4.88–5.88 / dark 6.02–9.09)
· not-tested dashed-distinct · console 0. High-contrast/theme/accent smoke: pending full sweep.

## Duplication audit (interim)
- Canonical operational Status styling systems = **1** (`.mz-status`) on the migrated surfaces.
- Canonical metadata Badge systems = **1** (`.mz-badge`).
- Legacy status systems remaining (pos `.status-badge`/`.kstate`/`.conn`, cashier `.conn`, etc.) =
  **inventoried, pending migration** — NOT yet 0. → P3B remains PARTIAL.
