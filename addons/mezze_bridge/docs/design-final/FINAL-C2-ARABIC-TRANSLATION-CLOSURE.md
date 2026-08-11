# FINAL-C2 — ARABIC STAFF LOCALISATION CLOSURE

Bounded closure of one certification condition from `F11-UIUX-CERTIFICATION-REPORT.md`:

> "Owl staff-app UI copy is 26 % translated (52/201). An Arabic cashier sees a mixed
> Arabic/English interface." — the sole blocker for an **Arabic-market** RC.

This is a localisation-content pass. The RTL/font/theme system was already certified and
was not redesigned.

---

## Phase 1 — the denominator was re-derived from HEAD, not assumed

The previous figure (201) came from scanning Owl **templates only**. Re-auditing current
HEAD showed the real translatable surface is larger, because Odoo also translates:

* every **text node** in an Owl template,
* the attributes Owl treats as translatable — `alt`, `aria-label`, `aria-placeholder`,
  `aria-roledescription`, `aria-valuetext`, `label`, `placeholder`, `title`
  (verified in `owl.js` `TRANSLATABLE_ATTRS`) plus `data-tooltip` (added by Odoo's
  `web/static/src/env.js`),
* every `_t("…")` literal in JS — **including adjacent string concatenation**, which the
  runtime receives as ONE msgid (the first audit had split those into fragments).

Extractor: `tests/_i18n_inventory.py` (the tests import the same module, so the number in
this report and the number the suite enforces can never drift apart).

| | Before C2 | After C2 |
|---|---|---|
| Total staff translatable strings | **367** | **367** |
| Arabic present | **108** | **364** |
| Missing | **259** | **0** |
| Blank | 0 | 0 |
| Wrong / ambiguous | **1** (`Register`) + 2 collisions | **0** |
| Untranslated **by design** | — | **3** |
| **Coverage** | **29.4 %** | **100 %** of translatable strings |

**Untranslated by design (3):** `Mezze` (brand), `QR` (universal acronym), `VIP`
(international marker already shipped on reservation cards). Enforced as an explicit
allowlist in `test_68`, so nothing can be quietly added to it.

Prototype-only strings (`/mezze/design/pos`, `static/pos.html`) are **excluded** from the
production inventory, as required.

---

## Phase 2 — glossary

`ARABIC-TERMINOLOGY-GLOSSARY.md` is now the tie-breaker: one approved Arabic term per
concept, Modern Standard Arabic, operational register, targeted at Egypt / KSA / UAE /
Kuwait. ~150 terms across navigation, orders, tables, reservations, kitchen, payment,
service modes and system state, plus the grammar rules applied (action vs state, button
brevity, placeholder preservation, Latin digits, never translate identifiers).

### The decisions that mattered

| Concept | Approved | Rejected — and why |
|---|---|---|
| **Register** (selling workspace) | **نقطة البيع** | ~~تسجيل~~ = *registration/sign-up* — the live defect. ~~الكاشير~~ = the **person**, which created a second collision. |
| **Cashier** (person/role) | **الكاشير** | now names exactly one thing |
| **Park** (order) | **تعليق** / معلّق | must stay distinct from Hold |
| **Hold** (course) | **تأجيل** / مؤجل | distinct from Park |
| **Change** (cash back) | **الباقي** | never ~~تغيير~~ (modification) |
| **Fire** (KDS) | **إرسال** / مُرسل | not combustion; kept short for the kitchen |
| **Seat** (verb) | **إجلاس** / تم الإجلاس | a verb, not "a seat" |
| **Table** | **طاولة** | ~~ترابيزة~~ (Egyptian colloquial), ~~منضدة~~ (stilted) |
| **Accept** (KDS) | **قبول** | was استلام — collided with **Pickup** |
| **Pickup** (service mode) | **استلام** | now unambiguous |
| **Day** (selector label) | **اختيار اليوم** | was اليوم — collided with its own **Today** option |

---

## Phase 3 — implementation

* **256 new entries** added to the existing `i18n/ar.po`. No parallel translation system
  was introduced.
* **`Register`** corrected `الكاشير` → **`نقطة البيع`**.
* **One superseded entry removed** (`← Back to order`): the arrow moved out of the string
  when `.mz-dirglyph` was introduced, so the msgid no longer existed in source.
* **Source references added to 256 blocks.** Odoo only exports a term to the JS catalogue
  when its `.po` block carries a `#: code:addons/…` reference. Without it the entries
  existed but were invisible to the browser — the served catalogue went **107 → 363 terms**
  once the references were added. (Caught by browser verification, not by grep.)

### Five split sentences consolidated

A sentence broken across a `t-esc` cannot be translated grammatically — Arabic word order
differs — so these were rebuilt as one `_t()` string with one placeholder, using the
pattern already present in the codebase:

| Was (fragments) | Now |
|---|---|
| `Move this order and its kitchen tickets to` + `T<name>.` | `Move this order and its kitchen tickets to T%s.` |
| `Your current order will be parked…, then` + `<label>` + `will open.` | `Your current order will be parked so nothing is lost, then %s will open.` |
| `<name>` + `would exceed their credit limit with this sale.` | `%s would exceed their credit limit with this sale.` |
| `<name>` + `is over their credit limit — a manager must authorize this sale.` | `%s is over their credit limit — a manager must authorize this sale.` |
| `Move ` + `<table>` + ` to…` | `Move %s to…` |

---

## Phase 4 — consistency audit

Every Arabic value reused across different English msgids was reviewed:

| Arabic | English concepts | Verdict |
|---|---|---|
| الضيوف / ضيوف | Covers, Guests | **same concept** — documented |
| عدد الضيوف | Guest count, Party size | **same concept** |
| الطلب | Order, the order | same concept (noun + in-sentence fallback) |
| المتبقي | Remaining, Left | same concept (amount still outstanding) |
| في الانتظار / متأخر | Waiting/waiting, LATE/Late | case variants of one string |
| تم إلغاء الدفع | Payment cancelled, Payment canceled | two English spellings, one concept |
| ~~استلام~~ | ~~Accept, Pickup~~ | **CONFLICT → fixed** (Accept → قبول) |
| ~~اليوم~~ | ~~Day, Today~~ | **CONFLICT → fixed** (Day → اختيار اليوم) |

**Unexplained terminology conflicts: 2 → 0.** The allowlist is enforced by `test_70`, so a
new accidental collision fails the suite.

---

## Phase 5 — browser verification (rendered, not dictionaries)

Every Arabic-supported staff surface loaded in AR with the real catalogue:

| Surface | Arabic loaded | Unexplained English | Font | RTL | Overflow |
|---|---|---|---|---|---|
| Register `/mezze/pos` | YES | **0** | IBM Plex Sans Arabic | rtl | 0 |
| Orders | YES | **0** | IBM Plex Sans Arabic | rtl | 0 |
| Reservations / Waitlist | YES | **0** | IBM Plex Sans Arabic | rtl | 0 |
| Payment + cash tender | YES | **0** | IBM Plex Sans Arabic | rtl | 0 |
| Assign-table dialog | YES | **0** | IBM Plex Sans Arabic | rtl | 0 |
| Floor `/mezze/floor` | YES | **0** | IBM Plex Sans Arabic | rtl | 0 |
| KDS `/mezze/kds` | YES | **0** | IBM Plex Sans Arabic | rtl | 0 |

Remaining English on screen is **brand or record DATA only**, and is listed explicitly:
`Mezze` (brand) · branch name (`Mezze Test`) · user name (`Administrator`) · POS category
names (Bakery/Coffee/Cold/Food/Pizza/QR Menu) · product names · payment-method record names
(Cash, Card, InstaPay, Adyen Card, …) · KDS station names · floor name (`Main Hall`) ·
order references · `Online order` / `LiveEats order` / `QR self-order`, which are
**server-stored values** written onto the ticket record (`mezze_online_payment.py`), not UI
copy — translating them would change stored business data and is out of scope.

### A real defect the browser test caught

`views/cashier_templates.xml` renders `<body class="mezze-floor-body">`, but `floor.css`
styled **`.mz-floor-body`** — a class that appears nowhere in the markup. The Floor
therefore had **no Mezze body font at all** and fell back to the browser default (measured
`"Times New Roman"` in Arabic). Its two sibling apps both had the rule
(`.mezze-cashier-body`, `.mezze-kds-body`). Corrected to the real class **and** given the
RTL rule its siblings already had. This was invisible to every previous audit because the
Latin fallback looked plausible.

### Viewport re-test with Arabic copy

19 cases — Register / Orders / Reservations / Floor at 768, 1024, 1280, 1440 and KDS at
1024, 1280, 1440, all in Arabic:

**Horizontal overflow defects: 0. Direction: rtl in 19/19.** Arabic text expansion produced
no clipping, collision or inaccessible control.

### Theme re-check (C1 must not regress)

kiosk and onboarding, in Arabic, across Light / Dark / HC-light / HC-dark:
canvas `rgb(255,253,251)` / `rgb(25,21,16)` / `rgb(255,255,255)` / `rgb(0,0,0)`, 0 overflow.
**High Contrast remains 11/11.**

---

## Customer / operator surfaces outside the Owl apps — classification

| Surface | Localisation architecture | Class | Action |
|---|---|---|---|
| `onboarding.html` | own `T={en,ar}` dict, **12 EN / 12 AR keys paired**, working toggle, 43 Arabic literals | **A** — mechanism exists and is complete | none needed |
| `courses.html` | **none** — no dict, no lang variable, no toggle, **0 Arabic literals** | **B** | left; separate condition |
| `drivethru.html` | **none** — same | **B** | left; separate condition |

Per the brief, Class B is **not** rebuilt during C2: adding a localisation mechanism to two
operator boards is a customer/operator-product task, not a translation pass. Both remain a
distinct, honestly-reported condition. Note these are **operator boards**, not customer
surfaces — the F1 inventory classifies them as staff.

---

## Quality gates

| Gate | Result |
|---|---|
| Missing Arabic values | **0** |
| Blank Arabic values | **0** |
| Placeholder mismatches (EN vs AR) | **0** |
| Arabic values containing no Arabic script | **0** |
| Duplicate msgids | **0** |
| Unexplained terminology conflicts | **0** |
| Translated identifiers | **0** (UUIDs, POS refs, table ids, provider names, URLs, phone/email untouched) |
| Latin digits preserved | YES — order numbers, table numbers, prices, timers unchanged |
| bidi-safe fields preserved | YES — `dir="ltr"` on reference/PIN/amount inputs and `unicode-bidi:isolate` on phone cells untouched |

**Automated / semantic translation review: PASS.**
**Human native-speaker review: NOT PERFORMED.** Nothing in this pass was reviewed by a
native Arabic speaker, and no claim of native certification is made. Wording remains the
operator's to confirm; the glossary exists precisely so that review is a read-through, not
a re-translation.

---

## Regression

| Run | Result |
|---|---|
| C2 targeted (`mezze_floor`, fresh install) | **89 tests · 0 failed · 0 errors** (was 85) |
| Full module, fresh install | *(see F11 addendum)* |

Tests added (+4): `test_68` coverage, `test_69` placeholders/quality, `test_70` glossary
contract + collision allowlist, `test_71` rendered-Arabic browser proof on five surfaces.

Two existing tests were **updated, not weakened**:
* `test_63` asserted the provisional `Register → الكاشير` from F5; it now asserts the C2
  glossary decision `نقطة البيع`, with `test_70` owning the rule.
* `test_71` had to activate `ar_001` and set the language on the user `browser_js` actually
  logs in as — a fresh install activates only `en_US`.

**Business behaviour changed: NO.** No state key, enum, selection value, route, RPC payload
key, payment-method identifier, tax, order, reservation or KDS state was touched. The only
non-`.po` code changes are: five template sentences consolidated into `_t()` getters
(presentation only) and the Floor body-class correction.
