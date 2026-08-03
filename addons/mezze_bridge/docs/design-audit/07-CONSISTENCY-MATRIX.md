# 07 — Screen Consistency Matrix

Per screen family × design dimension. `CONSISTENT` (matches DS / other screens) ·
`MINOR` drift · `MAJOR` drift · `N/A` · `NOT OBS` (not visually observed).

| Family | Shell | Header | Nav | Spacing | Type | 1° action | 2° action | Status | Empty | Error | Loading | Modal | Touch | RTL | Dark | Responsive |
|---|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|
| Cashier `pos.html` | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | MINOR | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT |
| Cashier Owl `/mezze/pos` | MINOR | MINOR | CONSISTENT | MINOR | MINOR | CONSISTENT | MINOR | CONSISTENT | MINOR | CONSISTENT | CONSISTENT | MINOR | CONSISTENT | MINOR | MINOR | CONSISTENT |
| Floor / tables | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | MINOR | MINOR | CONSISTENT | MINOR | MINOR | MINOR | CONSISTENT | CONSISTENT | MINOR | CONSISTENT | MINOR |
| KDS | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | MINOR | MINOR | MINOR | CONSISTENT | CONSISTENT | MINOR | CONSISTENT | CONSISTENT |
| Delivery | MINOR | MINOR | CONSISTENT | MINOR | MINOR | MINOR | MINOR | MINOR | MAJOR | MINOR | MINOR | MINOR | CONSISTENT | MINOR | MINOR | MINOR |
| Payment | CONSISTENT | CONSISTENT | N/A | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | N/A | CONSISTENT | CONSISTENT | CONSISTENT | CONSISTENT | MINOR | CONSISTENT | CONSISTENT |
| Customer `shop.html` | MAJOR | MAJOR | MAJOR | MAJOR | MAJOR | MAJOR | MAJOR | MINOR | MINOR | MINOR | MINOR | MAJOR | MINOR | MINOR | MINOR | CONSISTENT |
| Table QR `qr.html` | MAJOR | MAJOR | MAJOR | MAJOR | MAJOR | MAJOR | MINOR | MINOR | MINOR | MINOR | MINOR | MAJOR | MINOR | MINOR | MINOR | CONSISTENT |
| Kiosk `kiosk.html` | MAJOR | MINOR | MINOR | MAJOR | MAJOR | MAJOR | MINOR | MINOR | MINOR | MINOR | MINOR | MAJOR | CONSISTENT | MINOR | MAJOR | MINOR |
| Onboarding/Go-Live | MAJOR | MINOR | MINOR | MAJOR | MAJOR | MINOR | MINOR | CONSISTENT | MINOR | MINOR | MAJOR | MAJOR | MINOR | MINOR | MAJOR | MINOR |
| CFD / Feedback | MAJOR | MINOR | N/A | MAJOR | MAJOR | MINOR | MINOR | MINOR | MINOR | MINOR | MINOR | MINOR | MINOR | MINOR | MINOR | MINOR |

## Where the drift concentrates

- **Shell / header / token columns (Spacing, Type, Modal):** every non-`pos` surface
  is `MAJOR` — they don't share the DS shell, tokens, or modal semantics. This is the
  dominant pattern and confirms the token audit.
- **Status column is mostly CONSISTENT/MINOR** — the semantic status *idea* travels
  even when tokens don't, because color meaning is intuitive. But see `08` for
  color-only risks.
- **Touch is CONSISTENT** for cashier/KDS/kiosk (44px+ honored); MINOR for
  shop/qr (some <44 controls).
- **Dark mode MAJOR** for kiosk + onboarding (kiosk not on the theme registry;
  onboarding has only `data-mz-mode`, no `prefers-color-scheme`).

## Most-consistent → least-consistent

`pos.html` (near-fully consistent) → Payment → KDS → Floor → Owl cashier → Delivery →
Kiosk → CFD/Feedback → `qr.html` → `shop.html` → **Onboarding/Go-Live (least
consistent + weakest a11y)**.
