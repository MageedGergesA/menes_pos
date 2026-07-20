# Sprint 2 · Phase 2A — Foundation Corrections & Component Inventory (engineering record)

Baseline / rollback: **`sprint-1-design-foundation`** (immutable). Discipline: Sprint 1 verification methodology (token-resolution proof + targeted computed-style checks, light+dark; whole-view fingerprints informational only). No redesign; no terracotta/type/spacing migration; preserve all behaviour.

**Approved plan decisions:** (1) `--ok` = theme-invariant `#2f9e6b`, no dark adaptation. (2) Implement the semantic z-index ladder exactly as proposed, preserving all numeric values, resolving ADR-0001. (3) Remove only the CSS `--ok` fallback; leave JS fallbacks. (4) Defer all JS z-index tokenization. (5) Component extraction order: Empty State → Number Stepper → Status Badge. (6) Each extracted component documents Purpose / Variants / States / Accessibility / Token dependencies / Current usage / Migration classification.

---

## Step 2A-1 — Fix `--ok` (REFACTOR / bugfix) ✅

**Investigation:** `--ok` was **undefined** (0 definitions) → its fallback `#2f9e6b` rendered in both themes. Used in 3 places: `.lt.free` ("free/comped" line indicator, CSS) and two success form-messages (`#mkt-msg`, `#clock-msg`, JS — the success partner of `var(--crit,#d64545)`). Semantically a **generic success/positive green, distinct from `--pos`** (`#1C9A60`/`#59C48D`, POS operational states). The Bible's success (`#2F7D4A`) is close but not equal — adopting it would change the current colour (deferred to the appearance sprint).

**Change:** define `--ok:#2f9e6b` in the baseline `:root` (theme-invariant — no dark override, so identical in every theme); remove the now-dead CSS fallback (`.lt.free{color:var(--ok,#2f9e6b)}` → `var(--ok)`). The 2 JS-inline fallbacks left untouched (per decision).

**Pixel-identity proof (both themes):** `--ok` resolves to `#2f9e6b`; `.lt.free` computes `rgb(47,158,107)`; the JS path `var(--ok,#2f9e6b)` computes `rgb(47,158,107)` (now via the defined token). Diff scope: 2 CSS lines (max line 205, inside `<style>`); JS lines 3256/3326 unchanged; braces 2581=2581. **Zero visual change; undefined-token bug closed.**

**Deferred:** dark-theme adaptation of `--ok`; convergence of the two success greens (`--ok` vs `--pos`) with the Bible `#2F7D4A`; removal of the 2 JS-inline `--ok` fallbacks — all to a later sprint.

## Step 2A-2 — Semantic z-index ladder (REFACTOR) ✅ · resolves ADR-0001

CSS-only, value-preserving. Removed the 4 unused/mislabelled aspirational tokens (`--z-base/dropdown/sticky/modal`, 0 refs); renamed `--z-toast(120)`→`--z-notification`; added `--z-toast:80`; introduced semantic tokens and migrated 13 selectors.

| Selector | Old value | Token | Computed (light/dark) |
|---|--:|---|--:|
| `.chair` | 1 | `--z-floor-object` | 1 / 1 |
| `.railtip` | 20 | `--z-tooltip` | 20 / 20 |
| `.hintbar` | 30 | `--z-hintbar` | 30 / 30 |
| `.paidflash` | 49 | `--z-flash` | 49 / 49 |
| `#ov-pay` | 55 | `--z-overlay-pay` | 55 / 55 |
| `#ov-receipt` | 56 | `--z-overlay-receipt` | 56 / 56 |
| `.branchmenu` | 60 | `--z-menu` | 60 / 60 |
| `.login` | 70 | `--z-login` | 70 / 70 |
| `.toast` | 80 | `--z-toast` (new) | 80 / 80 |
| `.welcome` | 90 | `--z-onboarding` | 90 / 90 |
| `.tour-spot` | 95 | `--z-tour-spot` | 95 / 95 |
| `.tour-pop` | 96 | `--z-tour-pop` | 96 / 96 |
| `.waiterbell` | 120 | `--z-notification` (renamed) | 120 / 120 |

**Verification (both themes):** all 15 z-tokens resolve to exact values (`ALL_MATCH`); computed z-index on every present element (`.overlay 50, .sheet 52, .branchmenu 60, .railtip 20, .toast 80, .waiterbell 120, #ov-pay 55, #ov-receipt 56, .paidflash 49`) equals baseline; absent elements covered by token-resolution proof. **Toast/notification mislabel fixed.** 0 residual literals on scoped selectors; 4 old tokens removed; braces 2581=2581; all diff hunks inside `<style>`; no HTML/JS/backend change. **ADR-0001 → Resolved.**

**Deferred (scope-honest):** JS-created overlays (90/92/93/94/95) + JS `z-index:200`; floor sub-objects (`.tabletop 2/.tbadge 3/.tqr 4`) and chrome (`.topbar 4/.rail 5`) — outside the approved 2A-2 selector set / require JS edits.

---

# Phase 2B — Component Extraction

## Step 2B-1 — Empty State primitive `.empty-state` (EXTRACT + REFACTOR) ✅

- **Purpose:** one reusable centered muted status-message primitive (empty / no-data / inline-error). The illustrated icon+text `.empty` stays a separate primitive.
- **Variants:** base `.empty-state{text-align:center;color:var(--ink-3);font-size:14px}`; `.empty-state--grid{grid-column:1/-1}` (for grid-placed empties). Padding stays per-use (contextual) — full padding normalization deferred (appearance).
- **States:** stateless container; caller supplies text/glyph/i18n (unchanged).
- **Accessibility:** none added yet (per decision); `role=status`/`aria-live` recommended for a later a11y pass.
- **Token dependencies:** `--ink-3`.
- **Current usage (migrated, 11 sites):** `bdsempty`×2, `ckempty`×2, `dlvempty`×3 (`+--grid`), `rsvempty`×6 → markup now `class="empty-state <domain>"`; domain rules slimmed to padding/grid delta.
- **Migration classification:** EXTRACT (primitive) + REFACTOR (repoint 4 identical instances).

**Deferred (untouched, verified unchanged):** `favempty` (13.5px + line-height — appearance), `mgrempty` (positive `--pos`/bold "all-clear" — different semantic), illustrated `.empty`.

**Verification (both themes, probe vs Sprint-1/2A baseline, 11 computed props):** all 4 migrated empties compute `center | --ink-3 | 14px | 400 | 19.6px` + original padding/grid — **byte-identical to baseline** (`lightMatchesBaseline: true`); `fav`/`mgr` unchanged (dark `mgr` = `--pos` `rgb(89,196,141)`). **DOM structure invariant** — git diff shows every JS change is only an added class token (surrounding logic/i18n/error paths identical); 0 logic/structural changes. Braces 2583=2583 (+2 new rules). No backend change.

## Step 2B-2 — Number Stepper size variant `.stepper--lg` (REFACTOR) ✅

- **Purpose:** one integer ±1 stepper; the two "steppers" are one component (identical DOM/interaction — plain `onclick` −/+, native-button keyboard/focus, no hold/repeat/pointer/keyboard-value/animation) differing only in *size* (variant) + *min/max/callback* (per-instance config: denom min0, cart remove-at-0, split min2/**max8**).
- **Change:** convert context selector `.equalrow .stepper` / `button` → modifier `.stepper--lg` / `button` (same values 40px/r11/38px/font18), **kept in place after base `.stepper`** so the same-specificity (0,1,0) override still wins by source order. Apply `class="stepper stepper--lg"` to the **split-ways** stepper only. `.equalrow` container rule retained. Denomination + cart-line steppers untouched.
- **Consumers:** denom (open/close shift) + cart-line qty = `.stepper`; split-ways = `.stepper--lg`.
- **Per scope:** no JS factory, no a11y/hit-area/keyboard/hold changes.
- **Migration classification:** REFACTOR (internal restructure, identical external behaviour/rendering).

**Verification (both themes, probe vs baseline):** standard `.stepper` unchanged (`30/9/28/16`); `.stepper stepper--lg` == old `.equalrow .stepper` (`40/11/38/18`) — `lightStdMatch/lightLgMatch/darkStdMatch/darkLgMatch: true`. **DOM/behavior/business invariant** — git diff shows only the added `--lg` class token; `equalWays` handlers (min2/max8) + `renderSplit` logic byte-identical; 0 non-stepper changes. `.equalrow .stepper` selector removed (0 refs). Braces 2583=2583. No backend change.

## Step 2B-3 (Phase 1) — Status Badge primitive `.status-badge` (EXTRACT + REFACTOR) ✅

- **Purpose:** one status pill for an entity's state, tone via modifier.
- **Scope (approved):** migrate ONLY the two **byte-identical** pills `rsvstate` + `ckstate` (proof-of-concept). NOT migrated: `dlvst`, `hqstate`, `dlvkr`; no `.st-*` dedup; no padding/font normalization. Naming: `.status-badge` (the numeric `.badge` overlay is untouched).
- **Created:** `.status-badge` (weight800/uppercase/.04em/`--r-sm`), `.status-badge--sm` (10px/3·9), tone modifiers `--ok/--warn/--accent/--violet/--neutral` (only the 5 tones rsvstate/ckstate need; reuse the exact prior tokens `--pos/--warn/--accent-strong/--violet/--ink-3` + soft/line).
- **State→tone maps (JS, presentational):** RSV `{booked:accent, seated:ok, cancelled/no_show/done:neutral}`; waitlist `notified→ok else accent`; CK `{requested:warn, produced:accent, dispatched:violet, received:ok}`.
- **Consumers:** Reservations, Waitlist, Central Kitchen (3 render sites).
- **Migration classification:** EXTRACT (primitive) + REFACTOR (repoint 2 byte-identical chromes).

**Verification (both themes):** all 5 tones + base chrome (`10px/800/uppercase/.04em/3·9/r-sm`) probe **identical to pre-edit baseline** (`lightMatchesBaseline: true`); every state maps to a resolving tone (`allStatesMapCleanly: true`); dark identical (same tokens). Old `.rsvstate`/`.ckstate` CSS + markup removed (0 refs); 3 new sites; `.badge` untouched; **0 non-status-badge logic changes**; braces 2582=2582.
**DOM note:** unlike 2B-1/2B-2 (added token only), clean tone modifiers require replacing the *state* class with the *tone* class — the state remains visible as the badge text; verified no JS reads the removed state classes.

## Step 2B-3 (Phase 2) — Status Badge size/shape variants (EXTRACT + REFACTOR) ✅

- **Purpose:** extend the proven `.status-badge` primitive with size/shape modifiers so the three remaining status pills (`dlvst`, `hqstate`, `dlvkr`) render pixel-identically.
- **Scope (approved):** migrate ONLY `dlvst` (Delivery), `hqstate` (HQ), `dlvkr` (Kitchen-ready). Untouched: `.badge` overlay, `.st-*` card system, `glflag`, `aggst`, timers, connection indicator, pickup chip, manager alerts, section labels.
- **Public classes:** `.status-badge` · `--sm` · `--md` · `--bordered` · `--label` · tone `--ok/--warn/--accent/--violet/--neutral`. Phase-1 API (`--sm` + tones) unchanged.
- **Created (this phase):**
  - `.status-badge--md{font-size:11px;padding:4px 10px;white-space:nowrap}` — the 11px medium pill (Delivery's full delta over base).
  - `.status-badge--bordered{padding:4px 9px;border:1px solid transparent;white-space:normal}` — HQ's delta **over `--md`**: 1px-narrower inline padding, a 1px transparent border, and a white-space reset (HQ never had nowrap). Applied as `--md --bordered`.
  - `.status-badge--label{font-size:11px;padding:2px 8px;text-transform:none;letter-spacing:normal}` — Kitchen-ready's non-uppercase label chrome (resets base uppercase + `.04em`).
  - HQ-scoped container rules (layout + state-border tint stay out of the component, per architecture rule 2): `.hqhd .status-badge{margin-inline-start:auto}`, `.hqhd .status-badge--ok{border-color:color-mix(in srgb,var(--pos) 30%,transparent)}`, `.hqhd .status-badge--neutral{border-color:var(--border-strong)}`.
- **Tone maps (JS, presentational):** dlvst `{preparing:warn, ready:ok, dispatched:violet, delivered:neutral, failed:neutral}`; hqstate `session_open?ok:neutral`; dlvkr `kitchen_ready?ok:warn`.
- **Migration classification:** EXTRACT (2 size + 1 shape variant) + REFACTOR (repoint 3 chromes).

**Variant matrix (verified against code):**

| Variant | Consumers | Exact purpose |
|---|---|---|
| Base `.status-badge` | Reservations, Waitlist, CK, Delivery, HQ, Kitchen-ready | weight 800 / uppercase / .04em / `--r-sm` |
| `--sm` | Reservations, Waitlist, CK | 10px / 3·9 |
| `--md` | Delivery, HQ | 11px / 4·10 / nowrap |
| `--bordered` | HQ | +1px border, 4·9 padding, white-space reset (delta over `--md`) |
| `--label` | Kitchen-ready | 11px / 2·8 / non-uppercase / no letter-spacing |
| tone `--ok/--warn/--accent/--violet/--neutral` | all migrated consumers | existing state→tone tokens |

**Architecture note (honest deviation):** the brief's ideal ("`--md` shared by Delivery+HQ, `--bordered` = border chrome *only*") is contradicted by the code — Delivery (`4px 10px`, `nowrap`) and HQ (`4px 9px`, no-nowrap, border) genuinely differ by more than a border. Because Delivery (`dlvst`) carries **only** `--md` + tone, all of its delta-over-base is forced into `--md`; HQ then composes `--md --bordered` and `--bordered` patches the three HQ-specific deltas (padding, border, white-space) + a state-border tint scoped to `.hqhd`. This is the minimal pixel-exact encoding of the real 1px differences; `--bordered` remains HQ-exclusive.

**Verification (Component Verification Standard v3, both themes):**
- **Computed-style equivalence:** harness diff of old-vs-new across **17 properties** (font-size/weight, text-transform, letter-spacing, padding ×4, radius, border width/style/color ×2, color, background, white-space, margin-left used-value) for all **9** consumer/state cases → `allMatch:true, 0 mismatches` in **light + dark**. HQ `color-mix` border tints, `--bordered` white-space reset, and `--label` transform/spacing resets all resolve exactly.
- **DOM equivalence:** git diff = only class-token strings change at the 3 render sites; state text (`v.state`, translated open/closed + kready/knot labels) unchanged; same parent/insertion point/shape; no event/handler change.
- **Tone mapping (old→token→new-tone→token):** dlvst preparing `--warn/--accent-soft`→`--warn` ✓, ready `--pos/--pos-soft`→`--ok` ✓, dispatched `--violet/--violet-soft`→`--violet` ✓, delivered/failed `--ink-3/--line`→`--neutral` ✓; hqstate open `--pos/--pos-soft(+pos30% border)`→`--ok`(+`.hqhd` tint) ✓, closed `--ink-3/--line(+border-strong)`→`--neutral`(+`.hqhd` tint) ✓; dlvkr y `--pos/--pos-soft`→`--ok` ✓, n `--warn/--accent-soft`→`--warn` ✓.
- **Business verification:** delivery `preparing|ready→dispatch`, `dispatched→delivered|failed` transitions, `st-<state>` card class, `session_open`/`closed` card class, and the `kitchen_ready` boolean are byte-identical; no state name or stored value changed.
- **Consumer verification:** all 3 render sites emit correct class sets across every reachable state.
- **Syntax/scope:** braces 2578=2578 (whole-file), 978=978 (`<style>`); no backend change; Phase-1 badges, `.badge` overlay, `.st-*` rules untouched.
- **Legacy references:** `dlvst`, `hqstate`, `dlvkr` = **0 live** (3 remaining hits are migration comments).

**Status Badge coverage:**
- **Migrated:** Reservations, Waitlist, CK (Phase 1) + Delivery, HQ, Kitchen-ready (Phase 2) — all 6 status pills now on `.status-badge`.
- **Deferred normalization:** the real 1–4px padding/size differences are *preserved as variants*, not normalized (an appearance-sprint decision).
- **Intentionally separate:** `.badge` numeric overlay, `.st-*` card-border system, `glflag`, `aggst`, timers, connection indicator, pickup chip, manager alerts, section labels — distinct components, not status pills.

---

# Sprint 2B-4 — Command Button primitive `.button` (EXTRACT + REFACTOR) ✅ (Phase 1)

- **Purpose / business meaning:** issue a discrete *command* (confirm, submit, secondary, cancel). `.button` is the **Command Button primitive — NOT a universal clickable-control primitive.** Nav rails, toggles, segments, keypads, selection cards, and JS-coupled workflow buttons are deliberately excluded (see 2B-4 investigation).
- **Scope (approved):** migrate ONLY the former `.btn` family (`.btn`, `.btn.primary`, `.btn.pos`, `.btn.ghost`, `.btn.dark`) and its real consumers. All other button-like controls untouched.
- **Public API:** `.button` (base) · `--primary` · `--positive` · `--secondary` · `--strong` · `--sm` · `--block`. (`--danger` **deferred** — no current `.btn`-family consumer is a clean red-variant; the two `--crit` usages are one-off inline color tweaks on `--positive` buttons.)
- **Variants (exact map, byte-identical declaration blocks — only the selector prefix changed):** `.btn.primary`→`--primary`, `.btn.pos`→`--positive`, `.btn.ghost`→`--secondary`, `.btn.dark`→`--strong`. Primary/positive are **not** merged (distinct accent vs pos chrome).
- **Size/layout modifiers (extracted from inline):** `--sm{height:40px;padding:0 18px;font-size:13.5px}` (the one repeated compact config, 2 consumers) · `--block{width:100%}` (repeated full-width, 6 consumers). Layout ownership (`margin`, `flex:0 0 auto`, `margin-top`) stays inline on the consumer — **not** hidden in the component. Pre-existing `flex:1` inside `--primary/--positive/--strong` is **preserved as-was** (it lived in the original variant); moving it would change flex-grow → deferred to Future evolution.
- **States:** `:hover` / `:active` (primary & positive), `:hover` only (secondary/strong), `:disabled` (primary opacity .5; positive/strong opacity .45; both `not-allowed`). Base `.button` (no variant) has no hover/active/disabled — preserved for `#hw-drawer`, `#rpt-csv`.
- **Token dependencies:** `--accent/--on-accent/--accent-strong`, `--pos`, `--ink/--canvas`, `--surface-2`, `--border/--border-strong`, `--ink-2`.
- **Consumers (27):** 2 base (`hw-drawer` reskinned, `rpt-csv` plain); 17 `--primary`; 6 `--positive`; 1 `--secondary` (`sc-cancel`); 1 `--strong` (`sc-go`). Spanning: shift open/close, waste/marketing/clock forms, reservations + waitlist, central-kitchen request, payment complete + cash 1-tap, receipt "new order", refund confirm + booking, delivery placement, item-hold pin/86, gift-card check/apply, split-gift add, manager approval.
- **Interaction contract:** native `<button>` (Enter/Space/click); global `:focus-visible` ring (shared, untouched). No hold/repeat/pointer-capture/spinner. **Unchanged — zero JS edited.**
- **Disabled contract (preserved exactly):** `disabled` still triple-serves (a) async **busy/re-entry guard** (`btn.disabled=true` before `await`, `=false` on error), (b) **business gate** (`#pay-complete` until paid, `#rf-confirm` until valid), (c) initial unavailable (`pay-complete`/`rf-confirm` ship `disabled`). Double-click guard (`if(btn.disabled)return`) intact.
- **Accessibility:** unchanged this sprint (no ARIA added, no `aria-busy`, no toggle-semantics change) — deferred to the dedicated a11y pass.
- **Non-goals:** not for `.charge`, `.wbtn`, `.tbtn`, `.rptseg`, `.railbtn`, `.iconbtn`, `.mx`, `.verb`, keypads, `.tender`, `.tact`, `.kacts/.kbump/.bqact/.ckact/.hqfocus/.cpay/.mod-add`, `.scanbtn`, `.sendbtn`, `.rgbtn`, `.matag`, chips, selection cards, workflow `data-a` buttons, steppers, text-links. No button factory. No `--danger` (deferred).

**Dependency audit:** `.btn/.primary/.pos/.ghost/.dark` are read by **no** JS (querySelector/classList/closest/matches/getElementsByClassName), test, or behavioral CSS selector (the only `btn`-substring JS hits are `.scanbtn/.rgbtn/.railbtn` — different, excluded classes). `.primary`/`.ghost` tokens ARE reused by excluded components via *their own* compound selectors (`.kacts button.primary/.ghost`, `.wbtn.primary/.ghost`) → the new `--*` modifier tokens are distinct, and those rules/markup were not touched. **Full (non-additive) rename is safe.**

**Inline-style matrix (pre-migration → action):**

| Consumer | Old class | Old inline | Classified | Action |
|---|---|---|---|---|
| hw-drawer | btn | height34/pad0·14/font12.5/border/bg surf2/color ink/margin-auto | one-off reskin + layout | **retain inline**, class→`button` |
| rpt-csv | btn | — | — | class only |
| waste/mkt/clock | btn primary | width100 / justify-center / pad11 | block / redundant / one-off pad | width100→`--block`; **retain** justify+pad11 |
| rsv-new | btn primary | margin-auto / flex:0 0 auto / **40·18·13.5** | layout / layout / size | size→`--sm`; **retain** margin+flex |
| wl-submit | btn primary | **40·18·13.5** | size | size→`--sm`; inline removed |
| ck-add, so-go, rf-confirm, pay-complete | (primary/pos) | — | — | class only |
| pay-cash1tap | btn primary | justify-center / gap8 / margin-top2 | redundant / redundant / layout | **retain** (no modifier match) |
| rc-done | btn primary | margin-top:auto | layout | **retain** |
| rf-book | btn primary | width100 | block | →`--block`; inline removed |
| df-book | btn primary | width100 / bg violet / border violet | block / one-off reskin | width100→`--block`; **retain** violet |
| data-ok | btn primary | flex1 / justify-center | redundant / redundant | **retain** |
| attach-btn | btn primary | width100 / margin-top6 | block / layout | width100→`--block`; **retain** margin |
| gc-apply, sg-add, data-x2, gc-check, apr-go | (primary/pos) | justify-center / **pad12** (+display:none / margin-top4) | redundant / one-off pad / state·layout | **retain** (pad12 not in approved API) |
| cancel (item-hold) | btn pos | flex1 / justify-center / bg surf2 / color ink2 | layout / redundant / reskin | **retain** |
| data-pin | btn pos | justify-flex-start / gap10 | override / one-off | **retain** |
| data-86 | btn pos | justify-flex-start / gap10 / color crit | override / one-off / reskin | **retain** |
| sc-cancel | btn ghost | — | — | class only |
| sc-go | btn dark | — | — | class only |

**Inline styles — before/removed/retained:** 20 consumers carried inline; **removed** only `width:100%` (6×) and the `height:40px;padding:0 18px;font-size:13.5px` triple (2×) — each reproduced exactly by a modifier with ≥2 justified consumers. **Retained** every other inline (reskins, `padding:11px`/`padding:12px`, `justify-content` overrides & redundancies, `gap`, `display:none`, all layout `margin`/`flex`). No inline removed purely for cosmetic zero-out; `padding:12px` (5×) intentionally **not** promoted to a modifier (not in the approved API).

**Variant matrix:**

| Variant | Consumers | Purpose | Old source class | Computed proof | # |
|---|---|---|---|---|--:|
| `.button` (base) | hw-drawer, rpt-csv | shared command-button chrome | `.btn` | MATCH ×2 themes | 2 |
| `--primary` | waste, mkt, clock, rsv-new, wl-submit, ck-add, so-go, pay-cash1tap, rc-done, rf-confirm, rf-book, df-book, data-ok, attach, gc-apply, sg-add, data-x2 | accent confirm | `.btn.primary` | MATCH (default+disabled) | 17 |
| `--positive` | pay-complete, cancel, data-pin, data-86, gc-check, apr-go | pos confirm | `.btn.pos` | MATCH (default+disabled) | 6 |
| `--secondary` | sc-cancel | ghost/neutral | `.btn.ghost` | MATCH | 1 |
| `--strong` | sc-go | ink/dark | `.btn.dark` | MATCH (default+disabled) | 1 |
| `--sm` | rsv-new, wl-submit | 40/18/13.5 compact | (inline) | MATCH | 2 |
| `--block` | waste, mkt, clock, rf-book, df-book, attach | full-width | (inline) | MATCH | 6 |

Every variant has ≥1 live migrated consumer; no speculative modifier.

**Verification results (Component Standard v4):**
1. **Computed style** — harness diff of OLD `.btn`+inline vs NEW `.button`+modifiers+retained-inline, **24 props × 13 equivalence classes × 2 themes, default + disabled** → `allMatch:true, 0 mismatches`. `:hover`/`:active` blocks byte-identical by construction.
2. **DOM** — only class/style tokens changed; all 21 ids present ×1; text/icons/children/`data-*`/`type`/parent/insertion unchanged.
3. **JS dependency** — no removed class queried (audit); ids/handlers/event bindings unchanged; excluded JS-coupled classes (`.rptseg/.railbtn/.scanbtn/.rgbtn/.kacts button/…`) counts unchanged; **zero JS edited.**
4. **Interaction** — click/Enter/Space native; disabled-click suppression + async double-click guard (`if(btn.disabled)return`) intact (handlers untouched).
5. **Focus** — tab order unchanged; global `:focus-visible` untouched.
6. **Theme** — light + dark both MATCH.
7. **Business** — no payload/callback/validation/backend call changed (no JS edits); every form/confirm flow byte-identical.
8. **Scope** — excluded families verified unchanged (`wbtn`×3, `charge`×3, `kacts button`×8, `wbtn.primary/.ghost`×3). Braces 2580=2580; no backend change.

**Coverage:** `.btn`-family — **27/27 consumers migrated = 100%**; 0 deferred, 0 exceptions (all reskins/one-offs carried forward as retained inline, still migrated to `.button`). Whole button-ecosystem — `.button` covers ~**30%** (the command-button layer); the other ~70% (nav/workflow/keypad/selection/toggle/segment/icon/text-link) remain distinct by design — **not** counted toward coverage.

**Legacy references:** `class="btn"` (& `btn primary/pos/ghost/dark`) = **0**; `.btn*` CSS rules = **0**. Generic `.primary/.ghost` (owned by `.wbtn`/`.kacts`) intentionally **retained** — not removed.

**Deferred controls:** all excluded families (Non-goals). Modifiers deferred: `--danger` (no clean consumer). Normalization deferred: `padding:11px`/`padding:12px` compact configs (not a single size → left inline), `flex:1`-in-variant relocation, a11y (`aria-busy`, toggle semantics).

**Future evolution:** (a) relocate `flex:1` out of `--primary/--positive/--strong` into a `--block`/layout responsibility once each consumer's container is audited; (b) reconcile `padding:12px` modal-footer config if a 3rd+ consumer justifies a size; (c) alias `.charge` → `--primary --block` at the hero CTA; (d) fold `.scanbtn`/`.sendbtn`/`.wbtn`/`.tbtn` in as `--secondary` if pixel-identical; (e) a11y pass adds `aria-busy` to the disabled-busy phase.

---

# Sprint 2B-5 — Segment Control primitive `.segment` / `.segment-group` (EXTRACT + REFACTOR) ✅ (Phase 1)

- **Purpose / business meaning:** an exclusive mode/range **toolbar** — pick exactly one option to switch what a management view shows. `.segment` is the pill; `.segment-group` is the container.
- **Scope (approved):** migrate the proven `.rptseg` family only. **Ratified expansion:** the dependency sweep proved `.rptseg` had **6** consumers, not 5 — `#mkt-channel` (marketing-channel picker) shared the visual class but was selected by *element* (`$$('#mkt-channel button')`), so the investigation catalogued it without noting the class. CTO ratified including it (it is the identical control; pixel-identical; JS already element-based). No other toggle/chip/card/nav/workflow control touched.
- **Public API:** `.segment-group` (container) + `.segment` (pill). **No `--selected` modifier** — selection stays the existing runtime `.on` class (unchanged), per approved API.
- **Interaction model:** exclusive/radio. Click → `var = b.dataset.*` → `$$('#group .segment').forEach(x => x.classList.toggle('on', x===b))` → `apply*()`/`build*()`. Native `<button>` Enter/Space; global `:focus-visible`. **Unchanged — no JS behavior edited.**
- **State lifecycle (all 6 identical — verified, no toolbar differs):**

| Group | Segments | Default `.on` | dataset | Storage var | Default value | Update fn | Re-render | Reset |
|---|---|---|---|---|---|---|---|---|
| `#mgr-mode` | 7 (shift/sync/hw/waste/clock/fb/mkt) | shift | `data-mmode` | `mgrMode` | `'shift'` | `applyMgrMode()` | `buildManager()` | none (DOM `.on` persists) |
| `#rpt-mode` | 2 (sales/gl) | sales | `data-mode` | `rptMode` | `'sales'` | `applyRptMode()` | `buildReports()` | none |
| `#rpt-range` | 3 (today/7d/mtd) | today | `data-range` | `rptRange` | `'today'` | — | `buildReports()` | none |
| `#book-mode` | 2 (rsv/wait) | rsv | `data-bmode` | `bookMode` | `'rsv'` | `applyBookMode()` | `buildReservations()` | none |
| `#dlv-mode` | 2 (board/apps) | board | `data-dmode` | `dlvMode` | `'board'` | `applyDlvMode()` | `buildDelivery()` | none |
| `#mkt-channel` | 3 (email/sms/whatsapp) | email | `data-ch` | `mktCh` | `'email'` | — | `buildMarketing()` | none |

  Every var default equals its group's markup `.on` default → exactly one active segment per group at init and after every click.
- **Group responsibility split:** `.segment-group{display:flex;gap:6px}` (the layout duplicated across all 6 containers, extracted from inline). Consumer-specific positioning (`margin-inline-start:auto`, on 4 of 6) **stays inline** — not hidden in the component.
- **Consumers (6):** `#mgr-mode`, `#rpt-mode`, `#rpt-range`, `#book-mode`, `#dlv-mode`, `#mkt-channel` (19 segment buttons total).
- **Variants:** none (single skin). No speculative modifiers.
- **Non-goals:** `.segmented` (order-type + `#sp-modes` — different inset-track skin, `aria-pressed`), `.chip`, `.tipchip`, `.custchip`, `.verb`, `.modopt`, `.railbtn`, `.branchrow`, `.tender`/`.ordcard`/`.reason` cards. No `--selected` class. **No ARIA/roving-tabindex/arrow-nav** (deferred to the Accessibility Sprint).

**Dependency audit:** `.rptseg` (class) queried in JS only via `$$('#{group} .rptseg')` across the 5 mode toolbars (10 selectors) — all migrated **atomically** to `#{group} .segment`. `#mkt-channel` uses an **element** selector (`$$('#mkt-channel button')`), independent of the class name → unaffected by the rename, migrated for visual class only. State string `'on'` (7 `classList.toggle('on')` sites) **left exactly as-is** — no hybrid state, no alias. Excluded `.segmented`/`#sp-modes` are a different class token (`.segment` never matches `.segmented`).

**CSS / API changes:** `.rptseg`→`.segment`, `.rptseg.on`→`.segment.on` (byte-identical declaration blocks); new `.segment-group{display:flex;gap:6px}` absorbing the 6 containers' duplicated inline layout. `rptseg-row` (mkt-channel's dead, rule-less container class) → `segment-group`.

**Verification (Component Standard v6):**
1. **Dependency audit** — above; all class selectors migrated atomically; element selector + `'on'` untouched.
2. **State lifecycle** — 6/6 identical (table); one active segment per group; defaults match; DOM-persisted, no reset path.
3. **Computed style** — harness diff old `.rptseg`/`.rptseg.on`/inline-group vs new `.segment`/`.segment.on`/`.segment-group`, both themes, default + selected → `allMatch:true, 0 mismatches`. (No hover/pressed/disabled rules exist for this control — none added.)
4. **DOM** — only class/style tokens changed; no wrappers/child/icon/text/`data-*`/handler changes; all 6 container ids + all `data-*mode/range/ch` preserved.
5. **Interaction** — exclusive `toggle('on')` per group intact; handlers untouched.
6. **Keyboard / Focus** — native `<button>` + global `:focus-visible` unchanged; tab order unchanged.
7. **Theme** — light + dark MATCH.
8. **Business** — `mgrMode/rptMode/rptRange/bookMode/dlvMode/mktCh` values, `apply*()`/`build*()` calls, and rendered views byte-identical (no JS edited).
9. **Scope** — `.segmented`/`#sp-modes` untouched; braces 2581=2581; no backend change.

**Legacy-reference counts:** live `.rptseg` (class/CSS/JS selectors) = **0** (1 remaining mention = the origin comment). `.rptseg-row` = **0**. `.on` state = **unchanged** (7 toggle sites, 6 markup defaults). New: `.segment` rule ×1 (+`.segment.on`, `.segment-group`), 6 `.segment-group` containers, 19 `.segment` buttons, 10 `#group .segment` JS selectors.

**Coverage:** `.rptseg` family — **6/6 consumers migrated = 100%** (5 approved + 1 ratified). Whole toggle-ecosystem — `.segment` covers the exclusive-toolbar behavior; `aria-pressed` pills, cards, binary/multi toggles, nav remain distinct by design (not counted).

**Deferred (accessibility — own sprint):** `role=tablist`/`radiogroup`, `aria-selected`/`aria-checked`, roving `tabindex` + Arrow/Home/End. Current semantics (plain buttons + `.on` + no group ARIA) preserved exactly.

**Unexpected findings:** (1) `.rptseg` had **6** consumers, not 5 — `#mkt-channel` shared the class but was element-selected in JS (CTO-ratified inclusion). (2) `#mgr-mode` has **7** segments (shift/sync/hw/waste/clock/**fb**/**mkt**), not 5 — the two extra map to `applyMgrMode()`'s `fb`/`mkt` branches; all within the approved toolbar, no scope impact.

**Future evolution:** promote the exclusive-selection *interaction contract* (aria + roving tabindex) across `.segment` in the Accessibility Sprint; consider whether the `aria-pressed` pill family (`.chip`/`.seat`/`.floortab`/`.langtog`/`#sp-modes`/`.segmented`) should converge onto the same interaction engine (behavior-only, skins stay distinct).

---

# Sprint 2B-6 — Input Chrome primitive `.input` / `.textarea` (EXTRACT) ✅ (Phase 1)

> **Architecture rule:** *Input Chrome owns presentation only. Behaviour, validation, parsing, persistence and business state remain consumer-owned.*
> **Hierarchy:** Field Context → Input Chrome → Behaviour → Runtime State → Consumer Layout.

- **Purpose / problem solved:** the exact declaration `border:1px solid var(--border);background:var(--surface-2);color:var(--ink)` was duplicated **16×** across the settings/modal field cluster (11 field inlines + the `FLD` JS constant + others). `.input`/`.textarea` extract **only** that byte-identical chrome; every size/behaviour difference stays where it lives.
- **Public classes:** `.input` (single-line fields) and `.textarea` (multiline) — one grouped rule `{border:1px solid var(--border);background:var(--surface-2);color:var(--ink)}`. **Presentation only.**
- **Chrome Matrix (the `--surface-2` cluster — the migrated system):**

| Field | elem | pad | radius | font | bg | border | color | extra inline (retained) | classify |
|---|---|--:|--:|--:|---|---|---|---|---|
| waste-search | input | 11 | 11 | 14 | surface-2 | 1px border | ink | — | drift |
| waste-qty | input#num | 9 | 9 | (def) | surface-2 | 1px | ink | `width:100px` | drift + layout |
| mkt-subject | input | 11 | 11 | 14 | surface-2 | 1px | ink | — | drift |
| clock-code | input | 11 | 11 | 14 | surface-2 | 1px | ink | `letter-spacing:1px` | drift + behaviour(code) |
| clock-pin | input#pw | 11 | 11 | 15 | surface-2 | 1px | ink | `letter-spacing:4px` | drift + behaviour(PIN) |
| wl-name | input | 10 | 10 | 14 | surface-2 | 1px | ink | `flex:1;min-width:130px` | drift + layout |
| wl-phone | input | 10 | 10 | 14 | surface-2 | 1px | ink | `width:130px` | drift + layout |
| wl-size | input#num | 10 | 10 | (def) | surface-2 | 1px | ink | `width:64px` | drift + layout |
| apr-code | input | 12 | 11 | 15 | surface-2 | 1px | ink | — | drift |
| apr-pin | input#pw | 12 | 11 | 15 | surface-2 | 1px | ink | `letter-spacing:4px` | drift + behaviour(PIN) |
| mkt-body | textarea | 11 | 11 | 14 | surface-2 | 1px | ink | `resize:none;rows=4` | drift + behaviour(multiline) |

  **Shared, extracted:** `border`+`background`+`color` (identical in all 11). **Retained inline (per-consumer):** padding (9/10/11/12), radius (9/10/11), font-size (def/14/15), letter-spacing, width/flex/min-width, resize/rows — all classified **historical drift / consumer layout / behaviour-driven**, none a genuine reusable size.
- **Size-modifier decision:** **NONE added.** The padding/radius/font differences are historical drift (r9/r10/r11 across otherwise-identical fields), not intentional semantic sizes — creating `--sm/--md` would merely preserve drift, which the brief forbids. Retained inline instead. Re-evaluate only if a deliberate scale is designed later.
- **Consumers (migrated, 11):** waste-search, waste-qty, mkt-subject, clock-code, clock-pin, wl-name, wl-phone, wl-size, apr-code, apr-pin (`.input` ×10) + mkt-body (`.textarea` ×1).
- **Behaviour ownership (unchanged, consumer-owned):** validation (`type/step/min/maxlength/inputmode`), parse (`parseFloat/parseInt/.trim`), events, persistence, business payloads, focus, placeholder text — none touched.
- **Token dependencies:** `--border`, `--surface-2`, `--ink`.
- **Accessibility:** unchanged — no focus ring added, no `outline` change, no ARIA/label/`aria-invalid`. The suppressed-focus-ring debt (fields with `outline:none` elsewhere) and placeholder-as-label remain deferred to the Accessibility Sprint. Migrated fields had **no** `outline:none` and keep the global `:focus-visible` — verified identical.
- **Non-goals:** `.rsvform`/`.ckreq`/`.dlvacts` class-forms (`--surface` bg system, already class-based), `.search`/`.custsearch` borderless wrappers, native `<select>`/date/time, virtual keypads (`.numpad`/`.pinpad`), PIN *behaviour*, all validation/parse/events. No `.field`/error/success/prefix/suffix/size classes.

**Dependency audit:** every migrated field is read by JS via **id + `.value`** (never by a styling class); no `<input>` is JS-selected by class. → **additive-safe**; all ids/types/`data-*`/validation attrs preserved verbatim. Migration is markup-only (no JS logic touched).

**Inline-style report — before/removed/retained:** removed **only** the 3-declaration shared chrome (`border:1px solid var(--border);background:var(--surface-2);color:var(--ink)`) from 11 fields (reproduced exactly by `.input`/`.textarea`). **Retained** all padding/radius/font/letter-spacing/width/flex/min-width/resize/display — consumer layout, one-offs, and drift. No cosmetic cleanup.

**Deferred (in-scope but not migrated, with reason):**
- `gc-code`, `gc-amt`, `sg-amt` — chrome comes from the **`FLD` JS constant**; extracting requires editing JS (`var FLD=…`) → outside markup-only scope → **STOP-avoidance defer** (would need CTO sign-off to touch JS).
- `df-address` (textarea) — has **no** `--surface-2` chrome (only `resize:none`, otherwise browser-default); adding `.textarea` would *change* its appearance → not pixel-identical → excluded.
- `ck-qty` and all `.ckreq`/`.rsvform`/`.dlvacts` fields — a **different** visual system (`--surface` bg, class-based, focus rule) → separate future refactor.

**Verification (Standard v8):**
1. **Dependency audit** — additive-safe (id/`.value` coupling; no class selectors on inputs).
2. **Semantic/behaviour** — families remain separate; only chrome extracted.
3. **Validation matrix** — `type/step/min/maxlength/inputmode/value/placeholder` byte-identical on all 11.
4. **Computed style** — harness OLD full-inline vs NEW class+residual, **15 props × 6 equivalence classes × 2 themes, default + focus** → `allMatch:true, 0 mismatches` (incl. border w/s/color, bg, color, padding, radius, font, letter-spacing, **outline-style**, width, box-sizing, textarea resize).
5. **DOM** — only class add + 3-declaration removal; element/id/type/name/placeholder/value/`data-*`/parent/children unchanged.
6. **Focus** — no `outline`/`:focus-visible` change; computed outline identical.
7. **Theme** — light + dark MATCH.
8. **Business** — no JS edited → search/barcode/amount/qty/phone/PIN/reservation/delivery/approval payloads unchanged.
9. **Scope** — braces 2582=2582; no backend/JS-logic change; excluded systems untouched.

**Legacy-reference counts:** shared-chrome inline occurrences on migrated fields = **0** (was 11); `.input` ×10, `.textarea` ×1; `FLD` const = **1** (untouched, 3 deferred consumers).

**Coverage:** input-chrome — **10 migrated** of ~16 `--surface-2`-chromed inputs (gc/sg deferred = FLD; rest are `--surface`/borderless/native) → **~63%** of the surface-2 inline-input cluster. Textarea-chrome — **1 of 2** (df-address deferred, default-styled) = **50%**. Whole input ecosystem (~33 fields) — `.input`/`.textarea` covers **~33%** (chrome of one cluster); search/selects/date-time/class-forms/keypads separate by design.

**Deferred architecture:** focus-ring restoration + `aria-invalid` + label/helper association (Accessibility Sprint); a `.field`/`.field-group` wrapper for label+helper+error composition; `--surface` class-form unification behind variants; search-wrapper structure; money/quantity/date/time behaviour primitives; `FLD`→`.input` reconciliation (needs a JS-const edit).

**STOP-condition result:** the Chrome-Matrix STOP gate was evaluated and **not** triggered — a stable reusable chrome exists (border/bg/color identical ×16), no speculative modifiers were needed (drift retained inline), the rule applies safely to both `<input>` and `<textarea>`, and the migration stayed within one coherent visual system. One in-scope defer (gc/sg/`FLD`) was taken **specifically to avoid the "modify JS" STOP** rather than expand scope. No committed STOP.
