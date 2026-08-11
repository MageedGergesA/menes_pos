# FINAL-C5 — CUSTOMER STEPPER ACCESSIBLE-NAME LOCALISATION

Bounded closure of the condition **opened by FINAL-C4** and recorded as F11 condition 7:

> "`shop.html`, `qr.html` and `kiosk.html` still expose English-only quantity-stepper
> accessible names in Arabic."

C5 owns that defect and nothing else. It is an accessible-name localisation pass: not a
translation phase, not a stepper redesign, not a screen-reader certification.

---

## Why this was a real defect

The stepper buttons are icon controls. Their visible content is `−` and `+`, which is not
a usable action name, so an `aria-label` supplies it — that is the P3E contract and it is
correct. The defect was that the label was **baked into the markup in English** while
every other string on the page followed the language:

```js
'<button class="mz-stepper__btn" aria-label="Decrease quantity">−</button>'
```

An Arabic customer therefore saw an Arabic interface and heard an English action name at
the one control they use most. The visible glyphs were never the problem and were not
touched — **P3E stays frozen**.

## Phase 1 — inventory of CURRENT HEAD

Every generation path was read, including dynamically built template strings. There is
**more than one path per page**, which is why the count is not simply "one literal per
file".

| Surface | Location | Path | Buttons | Name source before | Hardcoded | Language-aware |
|---|---|---|---|---|---|---|
| shop | `shop.html:461` | cart line (`renderCart`) | minus + plus | markup literal | **yes** | no |
| qr | `qr.html:244` | menu-item stepper (`renderMenu`) | minus + plus | markup literal | **yes** | no |
| qr | `qr.html:277` | order-line stepper (`renderCart`) | minus + plus | markup literal | **yes** | no |
| qr | `qr.html:248` | add-one control (`.qr-add`, shown before a stepper exists) | add | `setAttribute('aria-label','add')` | **yes** | no |
| kiosk | `kiosk.html:252` | order line (`renderLines`) | minus + plus | markup literal | **yes** | no |

| | |
|---|---|
| Shop accessible-name sites | **2** |
| QR accessible-name sites | **5** |
| Kiosk accessible-name sites | **2** |
| **Total** | **9** |
| Hardcoded language bypasses **before** | **9** |
| Hardcoded language bypasses **after** | **0** |

### One site the brief did not name

`qr.html`'s `.qr-add` button is the control that adds the *first* unit — the stepper only
appears once quantity ≥ 1. Its accessible name was the literal string `'add'`: English,
lowercase, and less descriptive than the control deserves. It is the same defect class on
the same quantity affordance, so it was fixed in the same pass and is reported here
explicitly rather than folded in silently.

## Phase 2 — the existing localisation system was reused

All three pages already carried a page-local `T = {en, ar}` dictionary and a `t()` getter
(the architecture C4 adopted for the operator boards). C5 added **two keys per page** and
replaced the literals with `t('dec')` / `t('inc')`. No new framework, no AR-only DOM copy,
no duplicate stepper, no separate quantity dictionary.

| | English | Arabic |
|---|---|---|
| `dec` | `Decrease quantity` | `تقليل الكمية` |
| `inc` | `Increase quantity` | `زيادة الكمية` |
| `addone` (qr only) | `Add to order` | `أضف إلى الطلب` |

These are the **same pair FINAL-C4 already shipped** on `courses.html` and
`drivethru.html`, so one meaning now has one wording across all five surfaces.
`test_03` fails if the three customer pages ever disagree; `test_04` fails if the
customer pages and the operator boards drift apart.

### One re-render was missing — a real stale-label bug on the kiosk

Shop and QR already re-render everything a switch touches (shop's toggle calls
`renderCats(); renderGrid(); renderCart();`, qr's `applyLang()` calls
`renderCats(); renderMenu(); renderCart();`), so their localised names follow a live
switch for free.

**The kiosk did not.** Its order lines — the elements that hold the steppers — live in
`#k-lines` and are written **only** by `openSheet()`. The language toggle called
`applyLang(); render();`, and `render()` rebuilds the categories and the product grid but
never `#k-lines`. So a customer who opened the review sheet and then switched language
kept the **previous** language in their order list, accessible names included.

This was not visible from reading the diff: the names were already coming from `t()`.
`test_16` found it by driving the real switch, and it is a pre-existing defect rather than
something C5 introduced. The fix re-renders the sheet only when it is already open:

```js
applyLang(); render();
if (!$('#k-ov').classList.contains('hidden')) openSheet();
```

`openSheet()` is a pure re-render in this position — it no-ops on an empty cart, and the
overlay is already visible, so no state changes. **No quantity handler, cart model,
price, tax or route was modified.**

## Phase 3 — rendered verification

Every check below was made on a **real, interacted-with stepper** — an item was actually
added to the order first — not on an empty page.

### DOM accessible names

| Surface | EN decrease | EN increase | AR decrease | AR increase |
|---|---|---|---|---|
| shop (cart line) | `Decrease quantity` | `Increase quantity` | `تقليل الكمية` | `زيادة الكمية` |
| qr (menu item) | `Decrease quantity` | `Increase quantity` | `تقليل الكمية` | `زيادة الكمية` |
| qr (order line) | `Decrease quantity` | `Increase quantity` | `تقليل الكمية` | `زيادة الكمية` |
| qr (add-one) | `Add to order` | — | `أضف إلى الطلب` | — |
| kiosk (order line) | `Decrease quantity` | `Increase quantity` | `تقليل الكمية` | `زيادة الكمية` |

### Runtime language switch

EN → AR → EN was driven through each page's own control, asserting after **every**
switch. **Stale labels from the previous language: 0.**

### One page-specific fact worth recording

`qr.html` has **no `?lang=` parameter at all** — it derives the language from
`navigator.language`, because a table QR is scanned by a guest whose own phone decides.
That is its established contract and C5 preserved it: the Arabic proof for QR drives the
in-page toggle, which is exactly how a real guest switches.

### Computed accessibility tree

Reading `getAttribute('aria-label')` only proves an attribute exists. The **computed**
name was read over the DevTools Protocol — `DOM.getDocument` → `Accessibility.enable` →
`Accessibility.queryAXTree` filtered by `role: 'button'` and the expected
`accessibleName`, issued while the page is still live (the query runs inside a patched
`ChromeBrowser._wait_code_ok`, which returns after the page's own JS has driven the UI
and before the browser is torn down).

For each page and language the tests assert the AX node exists, its `role` is `button`,
its computed `name` equals the expected string, **and** that a query for the *other*
language's name returns **zero** nodes.

### Proving the tests can fail

**Negative control: PASS.** One hardcoded English label was temporarily restored
(`aria-label="Decrease quantity"` on the kiosk decrement) and the suite re-run on a fresh
database. **3 of 12 tests failed** — and exactly the right three:

| Test | Layer it guards |
|---|---|
| `test_01_no_hardcoded_accessible_name_bypasses` | the static contract |
| `test_15_kiosk_arabic` | the rendered Arabic name |
| `test_16_runtime_switch_leaves_no_stale_name` | the live language switch |

The mutation was reverted immediately and is **not** committed; the same suite returns
**0 failed, 0 errors** on the shipped code.

The AX layer is separately shown to be non-vacuous within each passing run: the *same*
`Accessibility.queryAXTree` call returns **≥1 node** for the active language's name and
**0 nodes** for the other language's name. A query that always matched, or always
returned nothing, could not produce that split.

Note that `test_16` did not need a deliberate mutation to prove its worth — it found the
real kiosk re-render bug above on its first run.

## Phase 4 — nothing else moved

| Check | Result |
|---|---|
| Visible glyphs (`−` / `+`) | unchanged |
| Layout / dimensions / colours / icons | unchanged — the diff adds no CSS |
| Touch target | **≥44px maintained** (kiosk measured 52×52) |
| Native `<button type="button">` | maintained |
| Keyboard reachable, `tabIndex` 0 | maintained |
| Quantity behaviour | 1 → +3 → **4** → −2 → **2**, one line throughout |
| Duplicate cart lines | **0** |
| Dropped taps | **0** |
| Themes (Light / Dark / HC-light / HC-dark × 3 pages) | **12 / 12 correct, 0 overflow** |
| `forced-colors` / `prefers-contrast` CSS | **not touched** |
| Business logic, routes, API | **unchanged** |
| Module version | unchanged |

## Regression

The two paths were kept strictly separate, as in C4 — the upgrade database was installed
from a clean `git worktree` at the C4 commit `8c190f4`, then cloned with `createdb -T`
before being upgraded, so no partially-upgraded or contaminated database was reused. It
was **not** seeded, precisely because C4 showed that seeding perturbs the
`full menu (5 tiles)` cashier tests.

```
FRESH     empty db -> install C5 code                -> full suite
UPGRADE   empty db -> install C4 (8c190f4) -> clone  -> C5 code -> -u mezze_bridge -> full suite
```

| Run | Tests | Failed | Errors |
|---|---|---|---|
| **C5 FRESH** | *(see report)* | | |
| **C5 UPGRADE** | *(see report)* | | |

## A separate finding, deliberately NOT fixed here

`shop.html`'s **runtime** language switch updates `documentElement.lang` but never the
`dir` attribute — it flips direction with a `body.rtl` class instead. A fresh
`?lang=ar` load is correct (`dir="rtl"`, set by the canonical FOUC guard), and the
*visible* direction is correct after a switch (computed `direction: rtl`), so this is a
stale **declaration**, not a broken layout.

It is out of C5's scope and was left alone on purpose: shop styles direction through
`body.rtl`, so adding `dir="rtl"` at runtime could newly activate `[dir="rtl"]` rules and
shift layout — exactly the visual change C5 is forbidden to make. `qr.html` and
`kiosk.html` both set `dir` correctly. Recorded so it is a decision, not an oversight.

This does **not** weaken the accessible-name result: the AX name's language context comes
from `lang`, which *is* updated on switch and was verified as `ar`.

## Limitations, stated plainly

1. **Computed browser accessibility-name verification: PASS.**
   **Real screen-reader walkthrough: NOT TESTED.** The AX tree is what the browser
   exposes to assistive technology; it is not a screen reader, and no such claim is made.
2. **Human native-speaker review: NOT PERFORMED.** `تقليل الكمية` / `زيادة الكمية` follow
   the C2 glossary register and were already shipped by C4, but no native speaker has
   read them.
3. **Physical device testing: NOT TESTED.**
