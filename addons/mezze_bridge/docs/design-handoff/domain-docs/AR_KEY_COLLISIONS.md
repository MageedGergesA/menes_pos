# Arabic dictionary — key collisions

The AR dictionary is one object literal, so a key written twice keeps only its **last** value.
No error, no warning: the earlier translation silently stops existing.

A full scan of the file (3,457 translation pairs, 3,170 unique keys) found **229 repeated keys**,
of which **106 carry conflicting values**. The `'Production'` defect — a kitchen production queue
labelled "production environment" (بيئة الإنتاج) because the tax screen's key won — was one
instance of this, now fixed by giving the tax surface its own `'Production environment'` key.

## Resolved so far

| Key | Was | Now | How |
| --- | --- | --- | --- |
| `Production` | الإنتاج / بيئة الإنتاج | الإنتاج | Tax screen took its own `'Production environment'` key |
| `Cooking` | قيد الطهي / درجة الطهي | قيد الطهي | Handheld modifier group renamed to `'Doneness'`, which already had درجة الطهي |
| `Received` | مستلم / تم الاستلام | تم الاستلام | Synonym consolidated |
| `Counted` | المعدود / المجرود | المعدود | Synonym consolidated |

111 conflicting keys remain of the original 113. The `Cooking` case is the cautionary one: the
commissary code added a **new call site** for a key whose winning value meant something else, and
its own corrective entry was dead on arrival — the batch state chip and the KDS ticket status both
read "doneness level" in Arabic. **Run the scan below before adding any `tr()` call for a word that
might already exist in another sense.**

## Fix pattern

Do **not** rename the dictionary entry alone. Disambiguate at the **call site**: pass a distinct
English string from the surface that means something different, then give that string its own
entry. That is what `'Production environment'` did. Renaming only the dict key leaves the caller
asking for a key that no longer exists, which renders English.

## Wrong-meaning conflicts — fix these first

These are not synonym drift; one of the two values is wrong wherever it lands.

| Key | Values | Problem |
| --- | --- | --- |
| `Mezze` | مقبلات / مزّة | Brand name vs "appetisers". The brand must not be translated. |
| `Checks` | الفواتير / الفحوصات | Bills vs medical examinations. |
| `Cooking` | قيد الطهي / درجة الطهي | "Being cooked" vs "doneness level". |
| `All day` | إجمالي الأصناف / اليوم كله | Kitchen all-day totals vs "the whole day". |
| `Off` | سيئة / راحة / خارج الوردية | "Bad" vs "rest day" vs "off shift". |
| `Held` | مثبّت / محتجز | Pinned vs withheld (money). |
| `Fire` | الإرسال / أطلق | Noun vs imperative — both used as a button. |
| `Accept` | استلام / قبول | Receiving goods vs agreeing. |
| `Terminal` | نقطة البيع / الجهاز | POS terminal vs generic device. |
| `Clocked in` | وقت الحضور / مسجّلون / سجّل حضوره | Timestamp label vs count vs event. |
| `Placed` | وقت الطلب / تمت إضافة | Order time vs "was added". |
| `Clear` | خالٍ / مسح / تنظيف | "Empty" vs "erase" vs "clean down". |
| `lines` | سطور / صنف | Document lines vs item count. |
| `EN` / `English` | ع, عربي / عربي, العربية | Language toggle labels crossed over. |

## Synonym drift — lower priority

The remaining ~90 are cases where both values are correct Arabic but inconsistent across screens
(`Cash` → النقد / النقدية / نقدي, `Card` → البطاقة / الكارت / بطاقة, `Settle` → تحصيل / سدّد / سداد,
`Covers` → الأفراد / الضيوف, and so on). These read as sloppiness rather than error. Worth one pass
to pick a house term per concept and delete the rest.

## Also found

123 keys are repeated with **identical** values — harmless at runtime, but they mean two people
translated the same string twice. Safe to dedupe.

## Bigger finding: 301 strings have no Arabic at all

Scanning every literal `tr('…')` / `T('…')` call site (2,106 of them) against the dictionary shows
**301 keys with no Arabic entry**. These render English in AR mode. They are not evenly spread —
they cluster in the session-close and cash-control copy added during the drawer work
(`Start the closing control`, `Count every payment method`, `Close and post the session`,
`Expected in drawer`, `X report`, `Z report`, `Journal entries`, `Session posted`, and most of the
toast bodies on those flows), plus dozens of confirmation toasts elsewhere.

This is a larger EN/AR gap than the collisions above and probably the higher priority of the two:
a missing entry shows English, which a reviewer notices; a colliding entry shows fluent Arabic
that means the wrong thing, which they may not. Both need a pass.

Caveat on the scan: it only sees **literal** call sites. Keys passed as variables
(`this.tr(t)` over an array of tab names, state labels built from config objects) are invisible to
it, so 301 is a floor, not a total. It also means a dict entry with zero literal callers is not
necessarily dead — `'Production'` reports zero callers but is still what the Commissary tab strip
resolves at runtime through `this.tr(t)`. Do not delete entries on the strength of this scan.

## Bigger finding: 266 strings have no Arabic at all

Scanning every literal `tr('…')` / `T('…')` call site (2,327 of them) against the dictionary shows
**266 keys with no Arabic entry**. These render English in AR mode.

**Run check 2 against any region you rewrite, not only the strings you newly authored.** The
house-account round is the cautionary case: entries were added for the new strings (`Invoice raised`,
`Nothing to pay`, `exposure`) but not for the pre-existing keys the rewritten methods *reused*
(`Payment received`, `Charged to the account`, `Over the credit limit`), so the credit-limit refusal
— the safety message the whole limit mechanism exists to deliver — rendered English inside an Arabic
sentence. One scoped script call would have caught all eleven.

There is also a **fourth failure mode the scan cannot see**: a value passed to the template *raw*,
bypassing `tr()` entirely. Guest names were rendering Latin while all 59 names sat in the dictionary,
because the list passed `g.name` instead of `this.tr(g.name)`. No call-site scan finds this — only a
DOM sweep for Latin leaves while the app is in Arabic does. Worth adding as check 4.

## Regression guard — run BEFORE adding a `tr()` call

Three checks, all cheap. The third was added after a case-blind scan declared a screen clean while
it rendered `COOKING` and `UP` in Arabic.

```js
// build the dictionary and every literal call site
const dict = {};                    // 'english' -> 'arabic'
const calls = {};                   // 'english' -> count
// dict:  /'([^'\n]*)'\s*:\s*'([^'\n]*[\u0600-\u06FF][^'\n]*)'/g
// calls: /(?:this\.tr|[^A-Za-z_$]T)\(\s*'((?:[^'\\]|\\.)*)'\s*\)/g

// 1. CONFLICTS — one key, two meanings. The later definition wins silently.
//    Group dict entries by key; report any key with >1 distinct value.

// 2. MISSING — a call site with no entry at all. Renders English.
//    Object.keys(calls).filter(k => !dict[k])

// 3. CASE MISMATCH — a call site whose key exists only in another case.
//    Also renders English, and check 2 alone will not tell you the entry is
//    sitting right there under a different capital.
const lower = {};
Object.keys(dict).forEach(k => (lower[k.toLowerCase()] ||= []).push(k));
Object.keys(calls).filter(k => !dict[k] && lower[k.toLowerCase()]);
```

Check 3 found 13 such call sites — `Float` / `float`, `difference` / `Difference`,
`Commission` / `commission`, `paused` / `Paused`, `Period` / `period`, `Due` / `due`,
`Redeemed` / `redeemed`, `Version` / `version`, `tables` / `Tables`, `Pick one` / `pick one`,
`target` / `Target`, `cancelled` / `Cancelled`, `You` / `you` — all now resolved by adding the
missing case with the same Arabic value.

**82 keys are still defined in more than one case** (`Held`/`held`/`HELD`, `Paid`/`paid`/`PAID`,
`Order`/`order`, …). Those are not bugs today because each case has its own entry, but every one is
a place where adding a call site in a fourth case fails silently. Prefer capitalising a new call
site so it reuses an existing owner rather than adding another case.

Caveat on the scan: it only sees **literal** call sites.
