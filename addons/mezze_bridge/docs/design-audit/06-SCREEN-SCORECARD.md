# 06 — Screen Scorecard

Scored 1–5 on 16 dimensions, per screen **family** (grouping screens that share an
implementation). Design quality is scored independently of software correctness (the
software is 403/0/0; that does **not** lift a design score). Scores are grounded in
the token/a11y/component evidence + observed structure; families that were only
read in source are marked so and scored conservatively.

Dimensions (1=poor … 5=excellent): VH visual-hierarchy · ID info-density · TC
task-clarity · AH action-hierarchy · CO consistency · TU touch · RD readability · ST
status-comms · EP error-prevention · AX accessibility · AR arabic/RTL · DK dark ·
RS responsive · PP perf-perception · EN enterprise-polish · RA restaurant-fit.

| Family | VH | ID | TC | AH | CO | TU | RD | ST | EP | AX | AR | DK | RS | PP | EN | RA | /100 |
|---|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--:|
| Cashier (`pos.html` ref) | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | **80** |
| Cashier (`/mezze/pos` Owl, prod) | 4 | 4 | 4 | 4 | 3 | 4 | 4 | 4 | 4 | 3 | 3 | 3 | 4 | 4 | 4 | 4 | **75** |
| Floor / tables | 4 | 3 | 4 | 3 | 4 | 4 | 4 | 4 | 3 | 3 | 3 | 4 | 3 | 4 | 4 | 4 | **73** |
| KDS | 4 | 4 | 4 | 4 | 4 | 4 | 5 | 4 | 4 | 3 | 3 | 4 | 4 | 4 | 4 | 5 | **80** |
| Delivery dashboard | 3 | 3 | 3 | 3 | 3 | 4 | 4 | 3 | 3 | 3 | 3 | 3 | 3 | 4 | 3 | 3 | **63** |
| Payment family | 4 | 4 | 4 | 4 | 3 | 4 | 4 | 4 | 5 | 4 | 3 | 4 | 4 | 4 | 4 | 4 | **78** |
| Customer `shop.html` | 3 | 3 | 4 | 3 | 2 | 3 | 4 | 3 | 3 | 2 | 3 | 3 | 4 | 3 | 3 | 3 | **60** |
| Table QR `qr.html` | 3 | 3 | 4 | 3 | 2 | 3 | 4 | 3 | 3 | 2 | 3 | 3 | 4 | 3 | 3 | 3 | **60** |
| Kiosk `kiosk.html` | 4 | 3 | 4 | 4 | 3 | 5 | 4 | 3 | 3 | 2 | 4 | 3 | 3 | 4 | 4 | 4 | **69** |
| Onboarding / Go-Live `onboarding.html` | 3 | 3 | 4 | 3 | 2 | 3 | 3 | 4 | 3 | 1 | 3 | 3 | 3 | 3 | 3 | 3 | **56** |
| CFD `cfd.html` | 3 | 3 | 3 | 3 | 2 | 4 | 4 | 3 | 3 | 2 | 3 | 3 | 3 | 3 | 3 | 4 | **59** |
| Feedback `feedback.html` | 3 | 3 | 4 | 3 | 2 | 4 | 4 | 3 | 3 | 2 | 3 | 3 | 4 | 3 | 3 | 3 | **60** |

## Reading

- **Highest:** Cashier reference + KDS (**80**) — the DS is fully applied; KDS is
  distance-readable and restaurant-appropriate.
- **Payment (78)** — strongest error-prevention (signature/confirm discipline).
- **Lowest:** Onboarding/Go-Live (**56**) — the S5 admin console: no focus/ARIA, own
  ad-hoc palette. CFD (59), shop/qr/feedback (60) — customer-facing debt islands with
  weak accessibility and off-DS tokens.
- The spread (56→80) **is** the story: consistency (CO) and accessibility (AX) are the
  columns dragging the non-`pos` families down, not layout or task clarity (TC stays
  3–4 everywhere — the workflows are well thought out).

## Honesty note

Families marked "read in source" (delivery, shop, qr, CFD, feedback) were **not**
visually screenshotted in this pass (tooling instability). Scores are conservative and
should be re-validated on real screenshots before acting on the lowest ones.
