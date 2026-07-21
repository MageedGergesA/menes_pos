# Phase 4A — RC2 Security Hardening (XSS Remediation)

*Frontend: `mezze_bridge/static/pos.html`. Mission: eliminate every exploitable stored/reflected XSS while preserving 100% behaviour. Backend: recommendations only. One local commit.*

## Executive Summary

RC1 identified a **High-severity stored XSS**: user/customer-controlled strings were interpolated into `innerHTML` **without escaping** (no escape helper existed), the sharpest vector being the customer-submitted **feedback comment** rendered in the manager's browser.

RC2 remediates this by introducing **one centralized `escapeHtml()`** helper and applying it at **every `innerHTML` interpolation of user- or backend-controlled text** (~45 render sites, 106 escaped interpolations). `innerHTML` is retained where genuine HTML structure is built (converting all to Node APIs would be a large, behaviour-risking rewrite); escaping at the interpolation boundary is the industry-standard, behaviour-preserving fix.

**Result: the H1 XSS surface is eliminated.** Legitimate text (names, notes, Arabic, emoji, `&`) renders **byte-identically** (verified); every tested payload (`<img onerror>`, `<script>`, `<svg onload>`, attribute-break, nested) is neutralised to inert text. No business logic, sorting, search, filtering, exports, or payloads changed. `node --check` confirms the script parses.

## Phase 1 — HTML-Sink Inventory

| Sink | Count | Notes |
|---|--:|---|
| `.innerHTML =` | 187 | The only structural HTML sink. |
| `insertAdjacentHTML` | 0 | — |
| `.outerHTML =` | 0 | — |
| `Range.createContextualFragment` | 0 | — |
| `DOMParser` | 0 | — |
| `document.write` / `eval` / `new Function` / `javascript:` | 0 | No code-execution sinks (confirmed RC1). |
| `.insertAdjacentElement` | 1 | Node API (safe). |
| `.textContent =` (e.g. `toast()`, line 3269, `#pay-entry`, …) | many | **Auto-escaping** — not XSS sinks. |

## Phase 2 — Sink Classification

- **A — Safe static HTML** (majority of the 187): `innerHTML` built only from static structure + SVG icons + i18n `t()`/lang literals + numeric `INT()/EGP()` outputs + class/id/`data-*`. **No escaping needed** (numbers/i18n can't carry markup; icons are trusted config).
- **B — Trusted generated** (Odoo-admin/config data): product/branch/staff/tender/station/foodcost/burn-rate/reward/campaign names, GL session names, hardware config. **Escaped** (defence-in-depth via the same helper).
- **C — Unsafe user-controlled**: customer name/phone; reservation who/note/phone/table; waitlist who/note/phone; delivery who/phone/address/rider/tracking + items; **feedback who/comment/order** (customer-submitted); gift-card codes; waste product/reason; CK request product/branch/note. **Escaped (mandatory).**
- **D — Potentially unsafe**: receipt branch/employee/item names, manager alert labels, bottom-sheet option labels, order-picker tracking/phone, split-check labels. **Escaped.**

## Phase 3/4 — The Fix

**One helper (Phase 4):**
```
function escapeHtml(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
```
Escapes the five HTML-significant characters (`& < > " '`). `String(s==null?'':s)` handles null/undefined/numbers gracefully. **Centralized — no duplicate escaping logic.** For legitimate content the browser decodes the entities on display, so **rendering is identical**.

**`innerHTML` retained (Phase 3 rationale):** every C/D sink genuinely builds HTML structure interleaved with data; a Node-API rewrite of ~45 large templates would be high-risk to behaviour/rendering. The sanctioned minimal fix is boundary-escaping. (No sink was found where `innerHTML` was used for pure text — those already use `textContent`.)

## Exact Fixes (render sites escaped)

- **Feedback** (the confirmed exploit): `f.who`, `f.order`, `f.comment`.
- **Reservations / Waitlist**: `r.who/phone/note/table`, `w.who/phone/note`.
- **Delivery**: `v.who/phone/address/rider/tracking`, item `i.name` (+ rider `value="…"` attribute).
- **Customer / Loyalty**: `c.name/phone`, `initials(c.name)`, reward `rw.name`, `loyaltyReward.label` (list, profile, attach-chip).
- **Menu / Cart / Modifiers**: `pr.n[lang]`, tile `letter`, `v.name`/`it.name`/`o.name`, group `g.name`, cart `it.name[lang]/mod[lang]/compNote/seat`, upsell `pr.n[lang]`+`upsellReason()`, refund `it.n[lang]`, split-check `it.name[lang]`, `ck.label`.
- **Payment / Receipt**: tender `tn.n[lang]`/`tr.n[lang]` (SVG `.ic` left intact), receipt `branchName`/`EMPS_current.n`/`lastRef` + item/mod names, gift-card `c.code`.
- **KDS / Beverage**: `head`(table)/`sub`(server)/`t.station`/`it.name`/`it.note`; bev `it.name/note`/`tk.station/table`; pickup `p.table/tracking`.
- **Manager / Reports / HQ / Ops / CK**: marketing `c.name/segment`; clock `s.name/role`; stations `s.station`; servers/cashiers `s.name`/`c.name`; GL `r.name/config`; team `tm.name/branch`; alerts `a.label`; waste `p.name/uom`, `it.product/reason/uom`; aggregators `c.name`; hardware `p.name/host/port/station`; branch menu / HQ card / burn-rate / top-product / foodcost `b.name`/`t.name`/`f.name`; CK `p.name/code`, `r.product/branch/note`, `b.branch`; refund reasons `RF_LABEL`, `r[lang]`.

**Deliberately NOT escaped (correct):** SVG icon strings (`tn.ic`, `r.ic`, `nx.cls`) — trusted config markup; numeric `INT()/EGP()`/`.qty`/`.points` — can't carry HTML; i18n `t()`/lang literals — developer-controlled; `.textContent`/`toast()` — auto-escaping; the half/half `label` **data** at construction (escaped later at render — avoids double-encoding); `location.host` in the WebSocket URL (not an HTML sink).

## Regression Verification

- **Rendering identity (both scripts):** `escapeHtml('Ahmed Hassan')`, `'Café & Co'`, `'محمد عبد الرحمن'`, `'Table 12 🍽️'`, `'Ahmed <VIP> عميل'` all render **identically** to the raw string on display. ✅
- **Payload neutralisation:** `<img src=x onerror=…>`, `<script>`, `<svg onload=…>`, `" onmouseover="…`, nested — **0 executable nodes** created. ✅
- **Attribute context:** rider `value="…"` with a quote-break payload creates **no** injected handler. ✅
- **Graceful:** `null`/`undefined`→`''`; numbers→string. ✅
- **Business / sort / search / filter / exports:** unchanged — escaping is applied **only at the innerHTML boundary**; comparisons (`pr.n.en.toLowerCase().indexOf`), sorts (`b.amount-a.amount`), and payloads (form `.value`, `dataset`) read the **raw** data. ✅
- **Syntax:** braces 2586=2586; **`node --check` on the 238k-char script → OK**; 0 double-escaping; 0 numbers/SVG escaped. ✅

## Remaining Sinks (and why they are safe)

- ~140 `innerHTML` sites are **Class A** (static structure + SVG + i18n + numbers) — no user text to escape.
- All `textContent`/`toast()` writes — auto-escaping DOM API.
- SVG icon interpolations — trusted static config; escaping would break the icons.
- `location.host` (WebSocket URL) — browser-provided, not HTML.
- No `outerHTML`/`insertAdjacentHTML`/`DOMParser`/`eval` exist.

**No exploitable HTML-injection sink remains.**

## Backend Recommendations (advisory — no backend change made)

Defence-in-depth: sanitize/normalize free-text on write and/or output-encode on read at the API layer, so a poisoned record can't reach any consumer (POS, reports, exports, other clients):
- **`/feedback`** — customer-submitted comment/name (highest priority; public QR/CFD input).
- **`/reservations`, `/waitlist`** — guest name/note/phone.
- **`/delivery`** — customer name/address/note/rider.
- **`/loyalty`** (partner) — customer name/phone.
Recommended: strip/encode HTML control characters server-side; enforce max-length; store raw + serve encoded. Frontend `escapeHtml` + backend sanitization together give full coverage.

## Performance Impact

`escapeHtml` is one `String().replace(/[&<>"']/g,…)` per field — no-op fast path for strings without special chars. ~106 call-sites, invoked only during renders that already build DOM; cost is microseconds per render. **DOM delta 0, dependency delta 0, no measurable performance change.**

## RC2 Recommendation

**PASS — RC2 Security Certification (frontend XSS).** The RC1 High-severity stored-XSS blocker is remediated: every user/backend-text `innerHTML` interpolation is escaped through one centralized helper, verified to preserve rendering and neutralize payloads, with no behaviour/business change and a clean parse.

**Conditions carried forward (unchanged from RC1, not this phase's scope):** the backend sanitization recommendation (defence-in-depth) and the accessibility baseline (Phase 4 a11y) remain open. With the XSS fixed, a controlled production pilot is unblocked on the security axis.
