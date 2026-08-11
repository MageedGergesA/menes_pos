# FINAL-C5.1 — DOCUMENT SEMANTICS + REDUCED-MOTION EVIDENCE

Certification cleanup, not a new design phase. C5 closed its own condition but left two
statements behind that were themselves software-verifiable and had not been verified:

> 1. "`shop.html`'s runtime language switch updates `lang` but not the `dir` attribute."
> 2. "`prefers-reduced-motion` runtime toggle — the environment reports `no-preference`
>    and offers no emulation."

C5.1 closes both. Nothing else was touched.

---

## PART A — storefront document semantics

### The mechanism, which is narrower than C5 recorded

C5 reported "the runtime switch does not set `dir`". True, but the interesting half was
missing: **`shop.html` never sets `dir` at all.** A fresh `?lang=ar` load was nonetheless
correct, and it is worth recording exactly why, because the reason is what makes the fix
safe:

| Step | What runs | `lang` | `dir` |
|---|---|---|---|
| 1 | inline FOUC guard in `<head>` — derives direction from the **static** `<html lang="en">` | `en` | `ltr` |
| 2 | shop's own boot → `applyI18n()` sets the language | **`ar`** | `ltr` |
| 3 | **deferred `mezze-customer.js`** re-derives direction from the *now updated* `lang` | `ar` | **`rtl`** |

Step 3 only ever happens once, at load. A live language switch re-runs step 2 and nothing
else, so the document kept `dir="ltr"` while visibly flipping through `body.rtl`.

So the defect was a **stale declaration on the switch path**, and the fix is convergence:
make the switched state identical to the fresh state that was already certified.

### The change

`applyI18n()` now declares direction alongside language, using the same derivation and the
same `?dir=` precedence `mezze-customer.js` uses:

```js
document.documentElement.lang = lang;
var dirPref = Q.get('dir') || '';
document.documentElement.setAttribute('dir',
  (dirPref === 'rtl' || dirPref === 'ltr') ? dirPref : (lang === 'ar' ? 'rtl' : 'ltr'));
```

`body.rtl` was **kept** — existing shop CSS still keys off it, and removing it would have
been a redesign. `lang` declares the human language, `dir` declares the base writing
direction; both now change together, which is the point.

**This is the change C5 declined to make.** C5's stated reason was that adding `dir` at
runtime could newly activate `[dir="rtl"]` rules and shift layout. That reasoning was
sound but the premise was incomplete: because a fresh Arabic load *already* renders with
`dir="rtl"`, the post-switch state now simply matches a state the product has been
shipping and testing all along. There is no new rendering configuration to certify.

### Measured

Live `EN → AR → EN → AR`, driven through the page's own control, asserting after every
switch:

| State | `lang` | `dir` | computed `direction` | `body.rtl` | overflow |
|---|---|---|---|---|---|
| initial | `en` | `ltr` | `ltr` | no | 0 |
| after 1st switch | `ar` | `rtl` | `rtl` | yes | 0 |
| after 2nd switch | `en` | `ltr` | `ltr` | no | 0 |
| after 3rd switch | `ar` | `rtl` | `rtl` | yes | 0 |

**Declared and painted direction agreed in 4/4 states. Stale states: 0.**

Content across the same sequence:

| Check | Result |
|---|---|
| Stepper accessible names (C5) | follow the language — `Decrease/Increase quantity` ↔ `تقليل الكمية`/`زيادة الكمية` |
| Cart quantity | preserved across every switch |
| Price strings | **byte-identical** in EN and AR — no bidi reordering |
| Categories / menu tiles | still rendered, counts unchanged |
| Horizontal overflow | **0** |

Responsive: the same EN↔AR cycle at **360 · 390 · 430 · 768**, in the established
same-origin iframe harness, with each case asserting `iframe.contentWindow.innerWidth`
equals the intended width before measuring. **0 overflow, direction agreed at every
width, menu and category controls present throughout.**

---

## PART B — `prefers-reduced-motion`, actually emulated

### The previous claim was wrong

F11 condition 3 said the runtime toggle could not be exercised. It can: the CDP path C3
established for `forced-colors` takes `prefers-reduced-motion` just as well —
`Emulation.setEmulatedMedia` with `{'name': 'prefers-reduced-motion', 'value': 'reduce' |
'no-preference'}`, issued on the browser `browser_js` builds.

Every assertion below is preceded by a `matchMedia` check, so nothing is inferred from the
stylesheet:

| Emulated | `matchMedia('(prefers-reduced-motion: reduce)').matches` |
|---|---|
| `reduce` | **true** |
| `no-preference` | **false** |
| *(no emulation)* | **false** — proved separately, so no override leaks between tests |

### Motion inventory

Production continuous (`infinite`) animation, excluding the non-production `/mezze/design/pos`
prototype:

| Animation | Where | Class | Reduced-motion rule |
|---|---|---|---|
| `mz-spin` | canonical spinner | CONTINUOUS, non-essential | `components.css` |
| `mzKdsSpin` | KDS spinner | CONTINUOUS, non-essential | `kds.css` |
| `mzKdsLate` | KDS late timer | CONTINUOUS, **attention** | `kds.css` |
| `mz-status-pulse` | live/active status dot | CONTINUOUS, **attention** | `components.css` |

Finite motion: dialog `mz-dialog-pop` / `mz-dialog-fade` (0.14 s) and the transition
families (toast 0.2 s; stepper, filter chip and nav item 0.1 s) — all measured in normal
mode first, so the reduced-mode readings mean something.

**Every one of them already had a `reduce` rule. No CSS was written in Part B** — the
brief's instruction was to add tests and documentation if runtime proves the behaviour
already correct, and it does.

### Measured under `reduce`

| Element | Normal | Under `reduce` |
|---|---|---|
| `.mz-spinner` | `mz-spin 0.8s infinite` | `animation: none`, box and ring retained, top border still differs from the track — a **static arc**, never removed |
| `.mz-kds-spinner` | `mzKdsSpin 900ms infinite` | `animation: none`, ring retained |
| `.mz-kds-card--late .mz-kds-timer` | `mzKdsLate 1.4s infinite` | `animation: none`; the card keeps a painted border, and the LATE text chip was never motion-dependent |
| `.mz-status--active .mz-status__dot` | `mz-status-pulse infinite` | `animation: none` |
| toast / stepper / chip / nav | 0.2 s / 0.1 s transitions | ≤ 0.05 s |
| `.mz-dialog__panel`, `.mz-dialog__backdrop` | `mz-dialog-pop 0.14s` | `animation: none` |

**Continuous animation surviving `reduce`: 0**, verified not by listing known classes but
by sweeping **every element** in the rendered document on the storefront, the kiosk and
the KDS and failing on any computed `animation-iteration-count: infinite` with a non-zero
duration.

**The loading cue is never removed.** Under `reduce` the spinner keeps its box, its ring
and a contrasting arc, and every loading state also carries its own text plus
`aria-busy` — so "loading" stays legible with no motion at all.

**KDS attention survives without motion.** The pulse stops; the card border and the LATE
text chip remain. Motion was an extra cue, never the only one (P3B/P3G).

### One measurement that is easy to misread

`.mz-kds-spinner` computes `animation: none` **on the storefront** — not because reduced
motion did anything, but because `kds.css` is an Odoo asset bundle that the static
customer pages do not load. Stylesheet scope, not a motion result. The KDS assertions
therefore run against `/mezze/kds`.

### Negative control

The spinner's reduced-motion rule was temporarily removed and the suite re-run on a fresh
database. `test_12` **fails**; with the rule in place it passes. The sabotage was reverted
and is **not** committed.

**The failure mode is worth keeping.** With the canonical rule gone the spinner did not
report "still spinning" — it reported:

```
spinner must STOP under reduce, got mz-spin (1e-06s, 1)
```

That is `shop.html`'s own blanket page-level guard
(`*{animation-duration:.001ms!important; animation-iteration-count:1!important}`) catching
the fall. A weaker test — one asserting only "duration is tiny" or "not infinite" — would
have passed on a page that had **lost its component-level contract entirely**, and would
have gone on passing for surfaces that carry no blanket guard.

The assertion is `animationName === 'none'`, which is the stricter contract F8 deliberately
established when it rejected P3H's "slow the spin to 2400 ms" treatment. That strictness is
exactly what gave the test teeth here.

---

## Results

| Certification check | Result |
|---|---|
| Shop EN declares `en` / `ltr` | **PASS** |
| Shop AR declares `ar` / `rtl` | **PASS** |
| EN→AR, AR→EN, repeated cycling | **PASS**, 0 stale states |
| Declared vs painted direction | agreed **4/4** |
| Bidi content (prices) across switch | **identical**, no reordering |
| C5 accessible names after switch | **PASS** |
| Responsive 360/390/430/768 | **PASS**, 0 overflow |
| CDP reduced-motion emulation | **PASS**, both states + reset |
| Continuous motion under `reduce` | **0** |
| Loading cue preserved | **PASS** |
| KDS attention without motion | **PASS** |
| Finite motion under `reduce` | **PASS** |
| Negative control | **PASS** |
| CSS written for Part B | **none** |
| Business behaviour changed | **NO** — the only functional change is the document's declared direction |

## Regression

Both paths kept separate, the upgrade database built from a clean `git worktree` at the C5
commit `db99c13`, installed `--without-demo=all`, then cloned with `createdb -T` — no
seeding (C4 established that seeding perturbs the `full menu (5 tiles)` cashier tests) and
no reuse of a partially-upgraded database.

| Run | Tests | Failed | Errors |
|---|---|---|---|
| **C5.1 FRESH** | **590** | **1** | **0** |
| **C5.1 UPGRADE** (clean C5 `db99c13` → `-u mezze_bridge`) | **590** | **1** | **0** |

| | |
|---|---|
| Known `TestRateLimit.test_atomic_under_real_concurrency` | **REPRODUCED** — the sole failure in both runs, untouched |
| New failures | **0** |
| Upgrade exit / ERROR / CRITICAL | **0** ERROR lines on the clean C5 install; upgrade parse / view / asset / i18n errors **0** |

+15 tests over C5's 575.

## Limitations

1. One reduced-motion **preference** was exercised, not one per operating system; the
   product responds to the standard media feature, which is what the preference maps to.
2. This proves the CSS contract and the computed styles, **not** a subjective judgement
   that the remaining motion is comfortable.
3. Physical device and real screen-reader validation remain untested, as before.
