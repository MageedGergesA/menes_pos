# P3-BUSINESS-STATE-MAP (DESIGN-P3B)

Business states → canonical semantic variant. Same meaning → same semantics everywhere (item 8);
size/scale may differ (KDS large, admin compact). Derived from source + business meaning.

## Go-Live (onboarding) ✅ migrated
| State | Semantic |
|---|---|
| PASS | success |
| WARNING | warning |
| FAIL | danger |
| NOT TESTED | **not-tested** (dashed — never resembles pass/fail) |
| N/A | neutral |

## Payment (checkout / cashier) — ✅ checkout migrated (`.pay-msg`)
| State | Semantic | Trust note (item 17) |
|---|---|---|
| Ready to pay | info | — |
| Confirming | info/active | — |
| Pending / processing | warning | not yet settled |
| Paid / successful | success | provider-confirmed |
| Failed | danger | not charged |
| Canceled | warning | not charged |
| Partially paid | warning | distinct from paid |
| Manual confirmation | warning | must NOT look identical to provider-confirmed (paid=success) |
| Refunded | neutral/info | — |
| Refund pending/manual | warning | — |

## Store / Customer (shop/qr/cfd) — ✅ store open/closed migrated
| State | Semantic |
|---|---|
| Open | success | 
| Closed | danger |
| Preparing your order | active |
| Ready for pickup | success |
| On the way / out for delivery | active |
| Completed | success |
| Cancelled | danger |

## Order / KDS (pending migration — pos prototype + cashier)
| State | Semantic |
|---|---|
| Draft / New | neutral |
| Sent / Fired | info |
| Accepted | warning→info |
| Preparing | active |
| Ready | success |
| Served / Completed | neutral (done) or success |
| Late / Urgent | warning (escalates to danger) |
| Cancelled | danger |

## Table / Floor (DESIGN-P3B.4) — ✅ migrated (spatial widget: fill/border colour, NOT badges)
The floor is a spatial canvas; "status" is the table's fill/border colour, not a `.mz-status` pill
(pills would be badge-soup — items 5–6). Table **identity (number) stays dominant** over status.
State colours resolve through the `[data-appearance="mezze"]` alias layer to the canonical `--mz-`
foundation (except `--teal`, a documented retained exception — pos.html:126).

| State (`.table.*`) | Fill / treatment | Canonical token | Non-colour signal | Contrast (dark) |
|---|---|---|---|---|
| Available (`av`) | teal border, surface fill | `--teal` (retained exception) | label "open"/"متاحة" | 13.5 / 6.7 ✅ |
| Occupied (`oc`) | **soft info fill + info border + dark info text** (P3B.4A) | `--info`→`--mz-info` | guests·minutes meta | **8.0 / 8.6** ✅ |
| Bill requested (`bl`) | solid amber fill, pulse, **dark** text | `--warn`→`--mz-warn` | **label "BILL"/"الحساب"** (P3B.4) + pulse | 9.3 / 5.0 ✅ (was white-on-amber **1.97 FAIL**) |
| Reserved (`rs`) | dashed indigo border, soft fill, **text mixed→ink** (P3B.4A) | `--violet`→`--mz-delivery` | name + time | **6.2** ✅ (was **4.24 <4.5**) |

**Occupied-brand RESOLVED (P3B.4A):** the full source (gzip-embedded assets decompressed) treats
"occupied" only as a UX flow ("Table already occupied → Transfer / Add-to-existing") and gives **no
colour/tone spec** for it — no evidence for brand-as-status. Per the closure decision tree (no source
evidence → replace), Occupied was migrated off `--accent`/brand to canonical **info** (also calms the
hierarchy so the amber bill-attention state reads loudest). **Unexplained brand-as-status = 0.**
Hierarchy now: available (quiet teal outline) < occupied (calm info fill) < reserved (dashed indigo) <
bill (loud amber + label). Table **number stays dominant** throughout.

## Reservation / Waitlist — OUT OF SCOPE for P3B.4 (pending → P3B.5)
Floor **reservation indicator** (`rs` table state) IS in scope above; the Reservation/Waitlist
**management UI** is not migrated. Booked→info · Arrived→active · Waiting→warning · Seated→success ·
Cancelled→danger · No-show→danger/neutral (proposed, pending).

## Delivery (DESIGN-P3B.4) — ✅ migrated (badge already `.mz-status--md`; mapping corrected)
Stage badge maps state→canonical variant (pos.html `buildDelivery`). Channel (`dlvMode` apps/manual)
and driver (`.drider` text) are **metadata, not status** (items 22, 25) — left as-is.

| Stage | Canonical variant (P3B.4) | Was | Note |
|---|---|---|---|
| accepted | info | accent (=info) | canonical name |
| preparing | info | **warn (amber)** | now KDS-consistent (KDS preparing=accent→info); amber "caution" was wrong for a normal in-progress state (item 24, 40) |
| ready | success | ok (=success) | matches KDS ready (item 39/40) |
| assigned | info | accent (=info) | canonical name |
| out_for_delivery | active | violet (=info) | live/en-route; distinct from ready & delivered (item 26) |
| delivered | neutral | neutral | **deliberately neutral, NOT success** — keeps it distinct from ready=success (item 28) |
| cancelled | **danger** | neutral | terminal-negative (item 29) |
| rejected | **danger** | neutral | terminal-negative (item 29) |
| failed | **danger** | (unmapped→neutral) | added; terminal-negative (item 29) |

Card left-border accents (`.dlvcard.st-*`) are Card-family chrome → **P3G**; `st-preparing` token
realigned warn→info here only to avoid contradicting the migrated badge.

## Connectivity (pending — preserve 3-signal architecture, item 22)
Local Online→success · Local Unavailable→danger · Internet Online→success · Internet Offline→danger ·
Internet Unknown→not-tested/neutral · External Online→success · External Degraded→warning ·
External Paused→paused · External N/A→neutral. **Do NOT collapse the three signals into one "Offline".**

## Admin / Settings (pending — item 40)
Working→success · Disabled→neutral · Hidden→neutral · Inherited→info · Locked→warning ·
Published→success · Archived→neutral. Disabled / Locked / Unavailable must not look identical.

> No FSM / business behaviour changes — this is state PRESENTATION mapping only.
