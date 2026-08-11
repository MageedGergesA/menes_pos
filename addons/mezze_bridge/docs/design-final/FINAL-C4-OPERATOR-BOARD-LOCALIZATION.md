# FINAL-C4 — COURSES + DRIVE-THRU LOCALISATION CLOSURE

Bounded closure of one certification condition from `F11-UIUX-CERTIFICATION-REPORT.md`:

> "`courses.html` + `drivethru.html` ship English-only (0 Arabic literals)."

---

## Phase 0 — what these pages actually are

The brief called this the "customer Arabic localisation gap". **Repository truth
disagrees, and the repository wins**, so it is recorded here before anything else:

| Page | Header comment | Endpoints | Audience |
|---|---|---|---|
| `courses.html` | *Coursing board (waiter — hold & fire courses)* | `/courses/board`, `/courses/hold`, `/courses/fire` (keyed by `table_id`) | **waiter / operator** |
| `drivethru.html` | *Drive-thru lane board (operator screen)* | `/drivethru/board` | **operator** |

"Courses" here means **meal courses** — starters, mains, dessert — held and fired to the
kitchen for a table. It is **not** educational, and neither page is customer-facing. The
F1 surface inventory already classified both as staff; the C2 closure repeated it.

That determines the **register**: both pages use the operational vocabulary from
`ARABIC-TERMINOLOGY-GLOSSARY.md`, not consumer marketing language — the same Arabic a
cashier already sees in the Owl apps.

## Phase 1 — the architecture question, settled before writing strings

The product already had **five** localisation mechanisms. C4 was explicitly not allowed
to add a sixth, so the existing ones were enumerated and one was chosen:

| Mechanism | Used by | Fit for a static operator board |
|---|---|---|
| Odoo `.po` + JS catalogue (`_t()`) | Owl staff apps | **No** — these pages are plain static HTML with no Owl runtime and no `/web/webclient/translations` fetch |
| QWeb server-side translation | `/checkout/s/<token>` | **No** — not a QWeb template |
| `res.lang` on the user record | backend | **No** — the boards are opened by shared devices, not per-user sessions |
| Page-local `T = {en, ar}` + `data-t` hooks | **`onboarding.html`** | **Yes** |
| Page-local ad-hoc string swaps | — | rejected: that *is* a sixth mechanism |

**`onboarding.html`'s contract was adopted verbatim.** It already shipped 12 paired keys,
a working toggle and 43 Arabic literals, and C2 classified it as "Class A — mechanism
exists and is complete". C4 reuses that exact shape:

* a `var T = {en:{…}, ar:{…}}` dictionary,
* `data-t` (text) / `data-tph` (placeholder) / `data-tal` (aria-label) markup hooks,
* a `t(key)` getter for strings built in JS,
* `applyI18n()` stamping `lang` + `dir` and re-drawing dynamic content,
* the **shared** `mezze_shop_lang` preference key — no new storage key.

`test_09` and `test_10` fail the build if any of that is replaced by something new.

## Phase 2 — both pages stay bilingual

The requirement was localisation, **not** translation-in-place. English was not removed
from either page:

| | `courses.html` | `drivethru.html` |
|---|---|---|
| English keys | **25** | **26** |
| Arabic keys | **25** | **26** |
| Keys missing a translation | **0** | **0** |
| Markup hooks (`data-t`/`data-tph`/`data-tal`) | 9 | 7 |
| `t()` call sites | 18 | 20 |
| Orphan keys (translated, never used) | **0** | **0** |
| Undefined references (used, never translated) | **0** | **0** |

**51 translatable strings total.** The inventory comes from `tests/_c4_localization.py`,
which the tests import, so this table and the suite cannot drift apart (the same
discipline `_i18n_inventory.py` established in C2).

`test_03` asserts the English block is still populated and contains no Arabic;
`test_04` asserts every Arabic value actually contains Arabic script.

### Terminology decisions

Shared concepts follow the C2 glossary; page-specific wording is new but built from the
same register.

| Concept | Arabic | Note |
|---|---|---|
| Coursing (the board) | تتابع الأطباق | the sequence of courses, not "دورات" (training courses) |
| Course | طبق | a dish/course in the sequence |
| **Hold** | **تأجيل / مؤجل** | glossary-pinned — must stay distinct from Park (تعليق) |
| **Fire** | **إرسال** | glossary-pinned — send to the kitchen, not combustion |
| **Table** | **طاولة** | glossary-pinned |
| Drive-thru (the board) | خدمة السيارات | the established MENA term |
| Lane | مسار | |
| Call forward | استدعاء | |
| Take payment | تحصيل | |
| Collected | تم التسليم | |

`test_08` pins the glossary-shared terms so a future edit cannot reintroduce the
Park/Hold collision C2 fixed.

## Phase 3 — defects found while doing it

Two were found by measurement, and both are **pre-existing**, not introduced by C4:

1. **Sub-44px touch targets on the drive-thru lane card.** Measured on the bare `.act`
   family: `act 39×40`, `act p 39×40`, `act o 41×42` and — worst — the dismiss control
   `act x` at **`27×40`** (in a live lane the text-bearing ones stretch wider, `107×42`
   and `195×40`, but never taller). This is the
   operator's primary interaction on a lane board, and it was the easiest control to
   miss under pressure. The page-local `.act` vocabulary is exactly the class C3 flagged
   as *"gets forced-colors treatment from the UA … but not the canonical treatment"*;
   the touch audit in F7 had the same blind spot. Raised to ≥44px on both axes.
2. **The `courses.html` header control was 41×41** — introduced by C4's own language
   toggle sharing the existing `.hbtn` padding. Raised the same way.

A third defect was **found and deliberately left alone**, because it is outside C4's
scope and fixing it would be unreviewed scope creep:

3. **`shop.html`, `qr.html` and `kiosk.html` hardcode the English stepper accessible
   name.** All three ship a literal `aria-label="Decrease quantity"` /
   `"Increase quantity"` that never changes with the language, so an Arabic customer
   using a screen reader on the **customer** surfaces hears English there. C4's two
   boards now build that name from the dictionary (`aria-label="'+esc(t('dec'))+'"`), so
   the pattern to copy already exists. Surfaced here as a **new, separate condition** —
   it is a customer-facing a11y/localisation gap, not an operator-board one.

One deliberate, documented **divergence** was introduced:

4. **`?lang=` is authoritative on these two pages.** `shop.html` / `qr.html` honour only
   `?lang=ar` (an opt-in), with `localStorage` otherwise winning. On a shared board that
   is opened from a pinned link and handed over mid-shift, a one-way parameter means a
   link cannot express "English". Both values are now authoritative here, with the
   stored preference as the fallback. Persistence, the storage key and the toggle are
   unchanged. Aligning the other pages is a trivial follow-up and was **not** done,
   because it is outside C4's scope.

## Phase 4 — rendered verification

### Responsive sweep — 24 cases

`courses` / `drivethru` × `en` / `ar` × **360 · 390 · 430 · 768 · 1024 · 1280**, in the
same-origin iframe harness (every case asserts `iframe.contentWindow.innerWidth` equals
the intended width, so these are real CSS viewports and real media-query evaluations).

| Check | Result |
|---|---|
| Cases run | **24 / 24** |
| Viewport width matched intent | **24 / 24** |
| Horizontal overflow | **0 px in 24 / 24** |
| `lang` / `dir` correct for the requested language | **24 / 24** |
| Arabic face (`IBM Plex Sans Arabic`) applied in AR | **12 / 12** |
| Controls under 44 px | **0** (was 4 before the Phase-3 fixes) |
| Contract tests added | **20**, all green |
| Untranslated UI copy in Arabic | **0** |

The only Latin text remaining on the Arabic boards is **record data**, listed in full:
`Main Hall`, `Sky Lounge` (floor names) and `Breakfast Combo`, `Cappuccino`, `Cold Brew`
(product names). These are server-stored business values, not UI copy — the same policy
C2 applied and documented.

### Full operator journeys, in Arabic

Both boards were driven end-to-end, not merely loaded.

* **Coursing:** `طاولة 1 · تتابع الأطباق تغيير الطاولة EN 1 مقبلات مؤجل 2× Avocado Toast
  🔥 إرسال الطبق 1 حذف + إضافة طبق`; stepper aria-labels read
  `["تقليل الكمية","زيادة الكمية"]`.
* **Drive-thru** (created a real order): `مسار 1 1 سيارة 0د 1 كورولا حمراء #358 قيد
  التحضير مستحق الدفع 1× Avocado Toast USD 114.91 استدعاء تحصيل · USD 114.91 ✕`.

Latin digits, currency codes and order references are preserved, as required.

### Themes — 16 cases

Both boards were already on the canonical registry from C1 (`mezze-design.css` +
`data-appearance="mezze"` + the shared FOUC guard), so **no per-page theme CSS was
written**. Verified `courses`/`drivethru` × `en`/`ar` × Light / Dark / HC-light /
HC-dark:

| Mode | Canvas / text |
|---|---|
| Light (`classic`) | `rgb(255,253,251)` / `rgb(42,36,32)` |
| Dark (`lounge`) | `rgb(25,21,16)` / `rgb(245,241,235)` |
| HC light | `rgb(255,255,255)` / `rgb(0,0,0)` |
| HC dark | `rgb(0,0,0)` / `rgb(255,255,255)` |

**16 / 16 correct, 0 overflow, direction correct in all 16.**

One observation worth recording so it is not re-investigated: requesting
`?mztheme=classic&mzmode=dark` resolves to **`lounge`**, not `classic`. That is correct —
the registry keeps separate light and dark theme name lists, and `lounge` is the
canonical dark counterpart. The initial sweep expectation was wrong, not the page.

### Proving the tests have teeth — and one that did not

The `.act` fix was temporarily reverted and the suite re-run. **`test_16` stayed green.**

That is a real gap in the test, not a pass: the boards are loaded *unprovisioned*, so no
lane card is in the DOM and the "no sub-44px control" scan silently covered only the
header. A test that cannot fail is not evidence.

`test_18` was added to close it — it appends probe `<button>`s carrying the real product
classes (`act`, `act p`, `act o`, `act x`, `hbtn`, `hbtn ghost`) and measures them, the
same technique C3 used for the customer chips. With the fix reverted `test_18` fails with
`sub-44px lane/header controls: act 39x40, act p 39x40, act o 41x42, act x 27x40`; with
the fix in place it passes.

This is recorded rather than quietly fixed, because "the suite was green" was briefly
true and would have been misleading.

### Contrast preferences

`courses.html` and `drivethru.html` were **added to C3's `test_12`** rather than given
rules of their own, proving the canonical `components.css` forced-colors block reaches
them: forced palette active, no overflow, text never the same colour as the page.

## Phase 5 — upgrade path, kept distinct from the fresh path

The two paths were never allowed to share a database:

```
FRESH     empty db -> install C4 code            -> full suite
UPGRADE   empty db -> install C3 code (7f3e2fa)  -> seed records -> switch to C4 -> -u -> full suite
CONTROL   the same C3 db, upgraded with C3 code  -> full suite     (today's baseline)
```

The pre-C4 database was built from a **clean `git worktree` at `7f3e2fa`**, installed
`--without-demo=all`, and verified to install with **exit 0 and 0 ERROR/CRITICAL lines**
before anything else touched it. It was then cloned three ways with `createdb -T`, so the
upgrade-only run, the upgrade+suite run and the control all start from **byte-identical
state**. No database that a failed run had touched was reused.

### Upgrade mechanics (clone A — upgrade only, no tests)

| Check | Result |
|---|---|
| `-u mezze_bridge` exit code | **0** |
| `ERROR` / `CRITICAL` lines | **0** |
| XML / view / template parse errors | **0** |
| Asset errors | **0** |
| Translation / i18n loading errors | **0** |
| Module genuinely re-upgraded | **yes** — *"module mezze_bridge: creating or updating database tables"*, loaded in 0.65 s |

### Records and configuration across the upgrade

Representative records were seeded into the C3 database **before** the upgrade (POS
category, 3 POS products, pricelist, partner), then 59 counters were captured before and
after: every `mezze_*` table, the POS/restaurant/product/partner tables, `ir_model_data`
for the module, `ir_model_fields` for `mezze*` models, active languages, install state
and module version.

**Differences: NONE — all 59 counters identical.** No record loss, no configuration
change, no unexpected data migration, and the module version stayed `19.0.2.7.0`
(44 `mezze_*` tables, 1164 xmlids, 693 model fields, unchanged).

### The seeded pair is evidence, not the headline

Seeding has a cost that must be stated rather than buried: the 3 extra POS products make
`TestCashierBrowser.test_11_r1b_keyboard_productivity` and
`test_13_r1b_back_from_payment_clears_search` time out on
`full menu (5 tiles)` — they assert an exact tile count. **Those two failures appear at
C3 code, in the control run, before C4 exists**, so they are seed artifacts, not
regressions. Because control and treatment ran on byte-identical seeded clones, the
C3→C4 delta is still measured like-for-like.

To avoid reporting a contaminated headline, the upgrade suite was **also** run on an
**unseeded** C3 database. That unseeded run is the number quoted in Results; the seeded
pair stands only as the record-and-configuration-intactness proof above.

## Results

| Certification check | Result |
|---|---|
| Both pages bilingual (EN retained) | **PASS** |
| Arabic coverage of UI copy | **51 / 51 keys, 100 %** |
| New localisation mechanisms introduced | **0** |
| New storage keys introduced | **0** |
| Business / route / API changes | **0** (`test_12` locks the endpoints) |
| Module version bumped | **NO** |
| Horizontal overflow, 24 responsive cases | **0** |
| Sub-44px controls | **4 found → 0** |
| Theme cases correct | **16 / 16** |
| C2 staff Arabic regressed | **NO** |
| C3 media preferences regressed | **NO** (coverage extended to these 2 pages) |

### Regression — both paths, on the final code

| Run | Tests | Failed | Errors |
|---|---|---|---|
| **C4 FRESH** (empty db → install C4 → suite) | **563** | **1** | **0** |
| **C4 UPGRADE** (clean C3 db → C4 code → `-u` → suite) | **563** | **1** | **0** |

| | |
|---|---|
| Known `TestRateLimit.test_atomic_under_real_concurrency` | **REPRODUCED** — the sole failure in both runs, untouched by C4 |
| Fresh-only new failures | **0** |
| Upgrade-only new failures | **0** |
| New product regressions | **0** |

+20 tests over C3's 543. Contaminated-baseline runs (`543/3/0` control and `563/4/0`
upgrade, both on the seeded database) are reported in Phase 5 and are **not** these
numbers.

### What the upgrade suite proves about C4 specifically

These all ran **on the upgraded database**, not only on a fresh install:

| Checked after upgrade | Test |
|---|---|
| Courses EN → AR switch, and back | `test_17` |
| Drive-thru EN → AR switch, and back | `test_17` |
| Preference persists both directions | `test_17` |
| `lang` / `dir` change correctly at runtime | `test_11`, `test_13`–`test_16` |
| No English fallback in AR mode | `test_14`, `test_16` |
| Dynamic JS-built strings translate at runtime | `test_19` (`تعذّر الاتصال.` / `غير متصل`) |
| Accessible names localised, never hardcoded | `test_20` |
| Touch targets on lane + header controls | `test_18` |
| C2 staff Arabic catalogue intact | `test_63`, `test_68`–`test_71` |
| C3 forced-colors / prefers-contrast | `test_01`–`test_16` of `TestMediaPreferences` |
| P3A–P3I canonical components | the `p3*` suites, incl. the two updated here |
| Existing cart / order journeys | the cashier, delivery and omnichannel suites |

## Limitations, stated plainly

1. **Human native-speaker review: NOT PERFORMED.** As with C2, no native Arabic speaker
   reviewed this wording and **no native certification is claimed**. The glossary exists
   so that review is a read-through rather than a re-translation.
2. **Fixture record data stays English** (floor and product names above). Translating
   stored business data is out of scope and would change records, not UI.
3. **No physical device or screen-reader testing** — those remain the existing separate
   conditions.
4. The `?lang=` divergence (Phase 3, item 4) is deliberate and is **not** propagated to
   the other customer pages.
5. **A new condition was opened, not closed:** the hardcoded English stepper
   `aria-label` on `shop.html` / `qr.html` / `kiosk.html` (Phase 3, item 3).
