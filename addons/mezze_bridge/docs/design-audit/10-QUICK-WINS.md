# 10 — Top 10 Quick Wins

Small effort + large UX/visual impact + low regression risk. Each derives from the
audit evidence. **Not implemented** — proposals only.

| # | Quick win | Why it's quick | Impact | Risk | Screens |
|--|--|--|--|--|--|
| 1 | Add the DS focus ring (`2.5px --accent`, offset 2) to `kiosk.html` + `onboarding.html` | ~1 CSS rule per file | Restores keyboard visibility on the two worst surfaces | very low | kiosk, onboarding |
| 2 | Add `aria-label` to the unnamed icon buttons (~20 in `pos.html`, few in others) | attribute-only edits | Screen-reader + tooltip clarity on the flagship | very low | pos + others |
| 3 | Unify the brand accent to one hex (`#E0982B`/DS) under one name via a shared var | find/replace 3→1 | Consistent brand color across the customer journey | low | qr, kiosk, onboarding, shop |
| 4 | Enforce `min-height:44px` on customer interactive controls in `shop.html`/`qr.html` | 1–2 CSS rules | Fewer mis-taps on customer phones | low | shop, qr |
| 5 | Mark customer/kiosk sheets `role="dialog" aria-modal="true"` + label | attribute edits | Dialog semantics for AT | low | shop, qr, kiosk |
| 6 | Add `prefers-reduced-motion` block to kiosk + onboarding | 1 CSS block | Motion-sensitivity compliance parity | very low | kiosk, onboarding |
| 7 | Link Onboarding/Go-Live from the staff Settings screen | 1 nav entry | New admins actually find setup | very low | pos shell |
| 8 | Gate "Toggle offline demo" / "Replay tour" behind the debug/demo flag | conditional render | Production chrome stops reading as a prototype | low | pos shell |
| 9 | Differentiate Go-Live `NOT TESTED`/`N/A` pills with an icon/shape (not just hue) | pill CSS + icon | "uncertainty ≠ pass/fail" reads instantly | very low | onboarding |
| 10 | Darken the customer muted text tier (`--mut`) to ≥4.5:1 on its card bg | change 1–2 hexes | Readable secondary text on customer/kiosk | low | shop, qr, kiosk, onboarding |

**Sequencing note:** #1, #2, #4, #5, #6, #9, #10 are pure accessibility/contrast and
can ship as one small "a11y parity" patch with high confidence. #3 is the first step
toward the shared token layer (structural item S1 in the roadmap). All require the
usual regression + browser acceptance + Arabic/dark re-check before any RC.
