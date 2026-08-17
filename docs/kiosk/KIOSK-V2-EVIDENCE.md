# Kiosk V2 — production evidence

The approved Claude Design *Mezze Kiosk v2* implemented in the real Odoo kiosk, driven
in Chrome against a live branch. Every number below was read from the running system.

## Design source

| | |
|---|---|
| Artifact | `claude.ai/design/p/bf4e67c1-3d23-43a3-b268-b27b0ecd09df` — **opened and driven in Chrome** |
| Screens navigated | Welcome, Service, Menu, Product detail, Meal summary, Focused choice (single-choice **and** `qty_max=2`), Cart (empty and populated), Review, Payment, Payment failure, plus the harness (locales, currency, tax rate, orientation, upsell) |
| Design status | the artifact declares itself **FROZEN — READY FOR PRODUCTION HANDOFF** |
| Photography in the artifact | 0 / 26 — content debt, carried into production as the approved fallback |

## What the prototype decides, and what Odoo decides

| Prototype control | Production value | Read from |
|---|---|---|
| `currency: SAR` | **USD** on this branch | `pos.config.currency_id` |
| `taxRate: 15%` | **no tax row at all** — these products carry no tax | `account.tax` through the fiscal position |
| `marketLocale` | formatting only — language + the company's **country** (`ar-SA`/`ar-EG` render Arabic-Indic digits, `ar-AE` Latin) | `?lang=` / `self_ordering_default_language_id` / `res.company.country_id` |
| Card / Phone or watch / Pay at the counter | **Pay at the counter only** | Mezze creates an unpaid order; no terminal is certified |
| Dine In | **Eat in / Takeaway** as this branch configures them | `pos.preset` when used, else the branch's service modes |
| "Mixed Grill Meal" etc. | the branch's real menu | `/shop/menu?channel=kiosk` |
| `PAY-4412` | `797`, `798` | `pos.order.tracking_number` |
| "or browse files" drop target | the approved no-photo fallback | — |

## Geometry measured in production

| | Design | Production (measured) |
|---|---|---|
| Top bar | ~109 px | **109 px** |
| Category rail (landscape) | ~237 px | **237 px** |
| Product grid — portrait | 3 columns | **3** |
| Product grid — landscape | 5 columns | **5** (4 below 1400 px) |
| Product card — landscape | ~311 × 384 | **306 × 374** |
| Card media share | ~63 % | **61 %** |
| Order bar | ~173 px portrait | **173 px** (150 landscape) |

## The journey, end to end

Welcome → service → menu → meal → three focused choices → add → menu → order → review →
payment → success:

| Stage | Value |
|---|---|
| Meal builder running total | 150.00 USD |
| Order bar after Add | 150.00 USD |
| Cart / review total (server-priced, `/shop/quote`) | 150.00 USD |
| `/shop/order` response | 150.00 USD |
| `pos.order` 797 `amount_total` | **150.00** |
| Child lines | Double Burger 80 + Coke Zero 20 + Fries 25 + Fries 25 |
| State | `draft`, `amount_paid = 0` — unpaid until the counter takes it |
| Channel / service | `kiosk` / `takeaway` |

A second run (order 798) placed a simple product for 20.00 and showed the branch's own
instruction — "Please pay at the counter…" — which is derived from
`self_ordering_service_mode`, not hardcoded.

## Fidelity, side by side

Captured in Chrome with the approved artifact and the production kiosk at the same
viewport:

| Comparison | Verdict |
|---|---|
| `prototype-vs-production-menu.jpg` | same shell — brand + service chip + language/Start over, vertical icon rail with an active state, section heading with a count, 3-up image-first cards with big price + small unit and a configure affordance |
| `prototype-vs-production-configurator.jpg` | same meal model — thumbnail + name + completion chips, YOUR MEAL, one component row per group with icon tile, uppercase label, chosen value, rule line and CHANGE |
| `prototype-vs-production-cart.jpg` | same order screen — Add more, line cards with thumbnail/configuration/quantity/Edit/Remove, one priced recommendation with an equally weighted decline, totals block |
| `prototype-vs-production-arabic.jpg` | same mirroring — rail and chrome flip, the layout is RTL rather than a translated LTR page |

The remaining differences are **data**: the branch's own name, categories, products,
prices and currency, and the prototype's leaked placeholder image. That is the intended
result — the design is the design; the values are Odoo's.

## Screens

| Shot | What it shows |
|---|---|
| `prod-welcome-en.jpg` | the branch's own name, no fake restaurant, no stock photography |
| `prod-service-mode.jpg` | the branch's real service options |
| `prod-menu-portrait.jpg` | vertical rail, 3 premium image-first cards, heading + count, order bar |
| `prod-menu-landscape.jpg` | 5 columns, 237 px rail, same order bar — not a stretched portrait |
| `prod-meal-summary.jpg` | YOUR MEAL, one row per component, green checks, CHANGE, quantity, sticky footer |
| `prod-choice-qtymax2.jpg` | "Choose up to 2 · 1 included", "Each extra … adds 25.00 USD", ADD rows |
| `prod-cart.jpg` | thumbnails, configuration in words, stepper, Edit/Remove, one priced recommendation, totals |
| `prod-review.jpg` | service row, 1× lines with configuration, total |
| `prod-payment.jpg` | one real method with the amount on screen |
| `prod-success.jpg` | the real order number and the branch's instruction |
| `prod-meal-summary-ar.jpg` | the same meal in Arabic/RTL, fully mirrored |

## Defects found while implementing, and fixed

| | |
|---|---|
| Cards showed `[CONS_0001] Whiteboard Pen` — `display_name` carries the internal reference | the kiosk channel now sends `product.name`; a reference is staff data |
| The CTA read "Choose your K Choose your burger" | the instruction is added only when the group's own name does not already carry one |
| Pressing **Start order** before the branch's configuration arrived showed an empty menu and no service options | the way in stays closed until boot completes |
| The payment method's name and hint rendered on one line | the method body is a column |
| Landscape cards were 479 px tall against the approved 384 | landscape media aspect + body min-height, now 374 px at 61 % media |
| `/kiosk/config` and `/shop/quote` were unclassified routes | added to the public-route registry, which the endpoint-coverage test enforces |
| The rewrite dropped three product-wide contracts the repo already enforces: the canonical theme registry (`mezze-design.css` + the appearance bootstrap), the canonical `.mz-stepper` component with its per-language accessible names, and the `--mz-font-ar` RTL rule | all three restored **inside** the approved design — the kiosk now consumes `--mz-*` tokens rather than defining them, so Light, Dark and Mezze High Contrast reach it, and quantity is the canonical component at kiosk scale |
| Four existing C5 stepper tests drove the V1 DOM | their **assertions** were kept and their **probes** re-pointed at the V2 screens; nothing was weakened |

## Performance, measured in the browser

| | |
|---|---|
| Boot — page load until the kiosk will accept a tap (includes `/kiosk/config` + `/shop/menu`) | **1224 ms** |
| Menu render after **Start order** | **188 ms** |
| Open a meal (3 groups) | **3 ms** |
| Open a focused choice | **1 ms** |
| A selection | **0.7 ms** |
| RPCs while rendering the menu | **0** — the payload arrives once at boot |
| RPCs while configuring | **0** — no per-option request, no N+1 |
| RPCs on a cart change | 1 (`/shop/quote`) — deliberate: the server owns the price |
| RPCs on submit | 1 (`/shop/order`) |

Images are Odoo's existing bounded `image_512` derivative through `/shop/image`, cached
for an hour, `loading="lazy"` per card — no new image infrastructure, no original-size
downloads. No public CDN is contacted: all four font families are already vendored, and
every icon on the screen is inline SVG.

## Customer effort

| Task | Taps |
|---|---|
| simple item | 2 — card, Add to order |
| one-choice item, accepting the implied answer | 2 |
| one-choice item, changing it | 4 — card, Change, option, Add |
| 3-group meal (nothing pre-chosen) | 8 — card, then 2 per component, then Add |
| change one component afterwards | 3 — Change, option, Save |

The approved model costs two taps per component (open the component, answer it) where
V1's single scrolling panel cost one. That is the design's trade for a meal a customer
can read back and correct part by part. The prototype hides the difference by
pre-filling components; Mezze deliberately does not — an unanswered combo group is a
question, and answering it for the guest is how a wrong plate is made.

## Negative controls

Each sabotage applied, `mezze_kiosk` run on a fresh database, then restored and verified
**byte-identical (sha256)**.

| # | Sabotage | Tests that failed |
|---|---|---|
| 1 | self-order authorization removed | `test_22` |
| 2 | `qty_max` enforcement removed | `test_33` |
| 3 | `qty_free` pricing removed | `test_14`, `test_16` |
| 4 | the browser's total trusted | `test_30` |
| 5 | different configurations merged | `test_106` |
| 6 | configuration omitted from KDS | `test_18` |
| 7 | privacy reset leaves the cart | `test_105` |
| 8 | currency inferred from the locale | `test_07`, `test_110` |
| 9 | an unavailable payment method offered | `test_103` |
| 10 | a rejected order leaves an orphan | `test_22`, `test_31`, `test_36` |

Every restore was byte-identical. Control 5 was **toothless on its first run** — the V2
suite had no test pinning configuration-aware identity, because that assertion lived in
a V1 browser test the redesign replaced. `test_106` (one side vs two sides) and
`test_107` (the same configuration merges) were written to close the gap, and the
control was re-run against them: it now fails `test_106`. A control that does not bite
is a hole in the suite, not a pass.

## Tests

| | |
|---|---|
| Baseline before implementation (`80110f5`) | 986 / 0 / 0 |
| Kiosk V2 targeted (`mezze_kiosk`) | 57 / 0 / 0 |
| Full addon suite after implementation | **972 / 0 / 0** |

The count fell from 986 to 972 because the V1 kiosk browser suite (which drove a
DOM the redesign replaced) was rewritten rather than duplicated: 71 V1 tests gave
way to 57 V2 ones covering the same properties on the approved screens, and four
existing C5 stepper tests kept their assertions with re-pointed probes.
