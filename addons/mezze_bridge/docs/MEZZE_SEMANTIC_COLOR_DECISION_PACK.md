# Mezze — Final Semantic Color Decision Pack

*Design Director sign-off pack resolving the two release blockers preventing Mezze from becoming the default appearance. Every token has an exact name and hex; every pairing has a measured WCAG ratio. No layout, workflow, or logic change. This finalizes the existing approved identity — no new visual language.*

Contrast measured with the WCAG 2.1 relative-luminance formula. Target: **AA normal text = 4.5:1**; UI/large = 3.0:1.

---

## 0. Root cause (why 2.53:1 happened)

The approved dark danger `#E58A82` is a **light salmon**. It is an *excellent danger **text*** colour (7.17:1 on the dark canvas) but was also being used as a **fill** with white text (`.p86` out-of-stock badge, destructive buttons) — white on light salmon = **2.53:1**. One token cannot be both a light danger-text colour *and* a white-bearing fill in a dark theme. The fix is a danger **system** that separates the **role colour** (text/icon/border) from the **fill colour** (button/badge background).

---

## BLOCKER 1 — DARK DANGER CONTRAST

### The three options

| | Approach | Dark fill | On-fill text | AA (dark fill) | Brand feeling | Verdict |
|---|---|---|---|--:|---|---|
| **Opt 1 ★** | Split **role** vs **fill**; deep-red fill carries white | `#C0453B` | `#FFFFFF` | **5.05** | Same brick-red family | **RECOMMENDED** |
| Opt 2 | Keep approved salmon as the fill; flip on-text to dark ink | `#E58A82` | `#1C1305` | 7.24 | Highest fidelity, but salmon+dark reads soft, not "alarming" | Alt |
| Opt 3 | Full independent danger scale (extra hover/press/border ramp) | `#C0453B`+ramp | `#FFFFFF` | 5.05 | Same, more tokens | Overkill |

**Why Option 1:** it preserves the approved danger **text** colour exactly (`#B0433A`/`#E58A82` for error messages, borders, icons — where the salmon shines), adds one dedicated **fill** token dark enough to carry white, and keeps the universal danger signal (**white-on-red**) that "failed payment / destructive / out-of-stock" states need. Minimal new tokens; nothing about the warm brick-red brand feeling changes.

### RECOMMENDED — Official Mezze Danger System (Option 1)

#### Design Tokens (primitives)

| Token | Light | Dark | Role |
|---|---|---|---|
| `--mz-danger` | `#B0433A` | `#E58A82` | **Foreground** — danger text, icons, default border *(unchanged from approved)* |
| `--mz-danger-fill` | `#B0433A` | `#C0453B` | **Background** — destructive button / badge / filled danger |
| `--mz-danger-fill-hover` | `#9E3A32` | `#B23F36` | Fill hover (darkens) |
| `--mz-danger-fill-press` | `#8F332C` | `#A23A31` | Fill pressed (darkens more) |
| `--mz-on-danger` | `#FFFFFF` | `#FFFFFF` | **Foreground on the fill** |
| `--mz-danger-soft` | `#F7E4E1` | `#3A2420` | **Soft background** — cards, tints *(unchanged from approved)* |
| `--mz-danger-border` | `#B0433A` | `#E58A82` | **Border** — = the role colour, clearly visible |

#### Semantic aliases (what components consume)

```
--crit        → var(--mz-danger)         /* danger text/icon */
--crit-fill   → var(--mz-danger-fill)    /* destructive/badge background */
--crit-hover  → var(--mz-danger-fill-hover)
--crit-press  → var(--mz-danger-fill-press)
--on-crit     → var(--mz-on-danger)      /* text on the fill (replaces --on-color here) */
--crit-soft   → var(--mz-danger-soft)
--crit-border → var(--mz-danger-border)
```

#### WCAG Contrast Table — Danger (Option 1)

| Pairing | Light | Dark | AA normal (4.5) |
|---|--:|--:|:--:|
| on-danger (white) / danger-fill | **5.66** | **5.05** | ✅ / ✅ |
| on-danger (white) / fill-hover | 6.76 | 5.74 | ✅ / ✅ |
| on-danger (white) / fill-press | 7.84 | 6.59 | ✅ / ✅ |
| danger text / canvas | 5.58 | 7.17 | ✅ / ✅ |
| danger text / surface | 5.66 | 6.00 | ✅ / ✅ |
| danger text / danger-soft | 4.62 | 5.70 | ✅ / ✅ |
| danger-border / surface | 5.66 | 6.00 | ✅ (visible) |

**Every danger pairing is AA-compliant for normal text in both themes.** The failing 2.53:1 pairing (white on `#E58A82`) is eliminated — that usage moves to `--crit-fill` (`#C0453B` dark → 5.05:1).

#### Where it applies + Component Examples

| State | Background | Text | Border | Light ratio | Dark ratio |
|---|---|---|---|--:|--:|
| **Destructive button** (Void / Delete) | `--crit-fill` | `--on-crit` (white) | — | 5.66 | 5.05 |
| ↳ hover / press | `--crit-hover` / `--crit-press` | white | — | 6.76 / 7.84 | 5.74 / 6.59 |
| **Error message** (inline) | canvas | `--crit` | — | 5.58 | 7.17 |
| **Warning card** *(this is `--warn`, not danger — unchanged)* | `--warn-soft` | `--warn` | `--warn` | — | — |
| **Reservation no-show** | `--crit-soft` | `--crit` | `--crit-border` | 4.62 | 5.70 |
| **Failed payment** (banner/badge) | `--crit-fill` | `--on-crit` (white) | — | 5.66 | 5.05 |
| **Out-of-stock `.p86`** (the original defect) | `--crit-fill` | `--on-crit` (white) | — | 5.66 | 5.05 |

**Implementation note (single mechanical change):** components that today read `background:var(--crit); color:var(--on-color)` for a *filled* danger (the `.p86` badge, destructive buttons, failed-payment fills) must read `background:var(--crit-fill); color:var(--on-crit)`. Components that use `--crit` as **text/border** are already correct and unchanged.

#### The other two options (for the record — full values)

**Option 2 — dark-ink-on-salmon** (highest approved fidelity):
- `--mz-danger-fill`: `#B0433A` / `#E58A82` · `--mz-on-danger`: `#FFFFFF` / `#1C1305`
- Ratios: 5.66 / **7.24** — AA both. Rejected only because a salmon fill with dark text reads *soft*, weakening the "alarm" of destructive/failed states.

**Option 3 — full independent scale**: identical fills to Opt 1 plus a discrete `--mz-danger-border` ramp (`#E4B3AD`/`#6E3630`). Rejected as unnecessary token bloat; Opt 1's role-colour border (5.66/6.00) is already clearly visible.

---

## BLOCKER 2 — VIOLET DELIVERY CTA

The approved palette defines no violet. The current `--violet` (`#6552CE`/`#8A7BF0`) also **fails AA in dark** with white text (**3.40:1**) and reads as a cool purple that sits awkwardly against the warm terracotta system.

### The three options

| | Approach | Light / Dark | On-text | AA | Palette fit | Verdict |
|---|---|---|---|--:|---|---|
| A | Keep violet, formalise `--mz-delivery` = current violet | `#6552CE` / `#8A7BF0` | white L / **dark-ink D** | 5.75 / 5.39* | Clashes with warm brand; dark needs ink not white | No |
| B | Reuse existing `--mz-info` (teal-blue) | `#2C6E8F` / `#6FB2D0` | white L / dark-ink D | 5.62 / 7.82 | **Conflicts with `info` semantic** | No |
| **C ★** | New harmonised **`--mz-delivery`** indigo | `#4A57B8` / `#8E9BE8` | white L / dark-ink D | **6.28 / 6.99** | Cool logistics accent, distinct from all statuses | **RECOMMENDED** |

*Option A only reaches AA in dark if the on-text is switched to dark ink (`#8A7BF0` + `#1C1305` = 5.39); with white it stays 3.40 = fail.

**Why Option C:** delivery is a *logistics* role, not a *status* — it deserves its own cool accent so it never competes with warn/ok/danger (all warm) or reads as info (teal). A refined **indigo** harmonises with terracotta far better than the current saturated violet, and it follows the Mezze dark convention exactly (light accent + dark-ink text, like `--mz-brand` → `--mz-on-brand`).

### RECOMMENDED — Official Mezze Delivery Token (Option C)

#### Design Tokens

| Token | Light | Dark | Role |
|---|---|---|---|
| `--mz-delivery` | `#4A57B8` | `#8E9BE8` | Delivery accent / CTA fill |
| `--mz-delivery-hover` | `#414EA8` | `#7E8CDF` | Hover |
| `--mz-delivery-press` | `#384594` | `#6E7DD2` | Pressed |
| `--mz-on-delivery` | `#FFFFFF` | `#1C1305` | Text on the delivery fill *(dark ink in dark — Mezze convention)* |
| `--mz-delivery-soft` | `#E7E9F6` | `#23263A` | Soft delivery background / chips |

#### Semantic aliases

```
--delivery       → var(--mz-delivery)
--delivery-hover → var(--mz-delivery-hover)
--delivery-press → var(--mz-delivery-press)
--on-delivery    → var(--mz-on-delivery)
--delivery-soft  → var(--mz-delivery-soft)
/* retire --violet: every --violet consumer → --delivery (delivery role) */
```

#### WCAG Contrast Table — Delivery (Option C)

| Pairing | Light | Dark | AA normal (4.5) |
|---|--:|--:|:--:|
| on-delivery / delivery (CTA) | **6.28** (white) | **6.99** (dark ink) | ✅ / ✅ |
| on-delivery / hover | 7.29 | 5.86 | ✅ / ✅ |
| on-delivery / press | 8.58 | 4.83 | ✅ / ✅ |
| delivery text / delivery-soft | 7.10 | 5.68 | ✅ / ✅ |

#### Meaning, usage limits, harmony

- **Meaning:** delivery / dispatch / off-premise fulfilment only. The single cool "logistics" accent.
- **Usage limits:** Delivery CTA, delivery order-type chip, delivery status pill, delivery zone tags. **Not** for navigation, generic emphasis, or any success/warning/error meaning.
- **Conflict check (all clear):**
  - **warning** (gold `#B5842B`/`#E0B24C`) — warm vs cool indigo: no confusion ✅
  - **success** (green `#2F7D4A`/`#5FB884`) — green vs indigo: distinct ✅
  - **danger** (red `#B0433A`/`#E58A82`) — red vs indigo: distinct ✅
  - **brand terracotta** (`#C0602E`/`#D89A54`) — warm vs cool, complementary but not clashing (refined indigo, not saturated violet) ✅
  - **info** (teal `#2C6E8F`/`#6FB2D0`) — teal-cyan vs blue-indigo: distinct hue family; delivery is more saturated/violet-leaning ✅
  - **kitchen status** (new=teal, cooking=warn, late=crit) — indigo is not used in KDS; no overlap ✅

#### Delivery CTA Examples

| State | Background | Text | Light | Dark |
|---|---|---|--:|--:|
| Delivery CTA (default) | `--delivery` | `--on-delivery` | 6.28 | 6.99 |
| ↳ hover | `--delivery-hover` | `--on-delivery` | 7.29 | 5.86 |
| ↳ pressed | `--delivery-press` | `--on-delivery` | 8.58 | 4.83 |
| Delivery order-type chip (selected) | `--delivery-soft` | `--delivery` | 7.10 | 5.68 |
| Delivery status pill | `--delivery-soft` | `--delivery` | 7.10 | 5.68 |

---

## Light Theme Mapping (all new/changed tokens)

```
--mz-danger:#B0433A; --mz-danger-fill:#B0433A; --mz-danger-fill-hover:#9E3A32;
--mz-danger-fill-press:#8F332C; --mz-on-danger:#FFFFFF; --mz-danger-soft:#F7E4E1;
--mz-danger-border:#B0433A;
--mz-delivery:#4A57B8; --mz-delivery-hover:#414EA8; --mz-delivery-press:#384594;
--mz-on-delivery:#FFFFFF; --mz-delivery-soft:#E7E9F6;
```

## Dark Theme Mapping

```
--mz-danger:#E58A82; --mz-danger-fill:#C0453B; --mz-danger-fill-hover:#B23F36;
--mz-danger-fill-press:#A23A31; --mz-on-danger:#FFFFFF; --mz-danger-soft:#3A2420;
--mz-danger-border:#E58A82;
--mz-delivery:#8E9BE8; --mz-delivery-hover:#7E8CDF; --mz-delivery-press:#6E7DD2;
--mz-on-delivery:#1C1305; --mz-delivery-soft:#23263A;
```

## Before / After Colour Comparison

| Usage | Before (fails) | After (Opt 1 / Opt C) | Before ratio | After ratio |
|---|---|---|--:|--:|
| Out-of-stock badge, **dark** | white on `#E58A82` | white on `--crit-fill` `#C0453B` | **2.53 ❌** | **5.05 ✅** |
| Destructive button, dark | white on `#E58A82` | white on `#C0453B` | 2.53 ❌ | 5.05 ✅ |
| Failed-payment fill, dark | white on `#E58A82` | white on `#C0453B` | 2.53 ❌ | 5.05 ✅ |
| Error **text**, dark | `#E58A82` on canvas | `#E58A82` on canvas *(unchanged)* | 7.17 ✅ | 7.17 ✅ |
| Delivery CTA, **dark** | white on violet `#8A7BF0` | dark-ink on indigo `#8E9BE8` | **3.40 ❌** | **6.99 ✅** |
| Delivery CTA, light | white on violet `#6552CE` | white on indigo `#4A57B8` | 5.75 ✅ | 6.28 ✅ |

---

## FINAL RECOMMENDATION

1. **Danger → adopt Option 1** (split role/fill; white-on-deep-red fill, hover/press darken). Exact tokens above. Only mechanical change: filled-danger consumers switch `--crit`/`--on-color` → `--crit-fill`/`--on-crit`.
2. **Delivery → adopt Option C** (`--mz-delivery` indigo; retire `--violet`). Exact tokens above.

Both are AA-compliant for normal text in light **and** dark, preserve the warm terracotta identity, introduce no new visual language, and require **only colour-token edits** — no layout, workflow, or logic change.

## EXPLICIT DESIGN APPROVAL STATEMENT

> As Design Director for Mezze POS, I approve the following as the **official Mezze semantic colour system**, final and complete:
>
> **Danger (Option 1):** `--mz-danger` #B0433A/#E58A82 · `--mz-danger-fill` #B0433A/#C0453B · `--mz-danger-fill-hover` #9E3A32/#B23F36 · `--mz-danger-fill-press` #8F332C/#A23A31 · `--mz-on-danger` #FFFFFF/#FFFFFF · `--mz-danger-soft` #F7E4E1/#3A2420 · `--mz-danger-border` #B0433A/#E58A82.
>
> **Delivery (Option C):** `--mz-delivery` #4A57B8/#8E9BE8 · `--mz-delivery-hover` #414EA8/#7E8CDF · `--mz-delivery-press` #384594/#6E7DD2 · `--mz-on-delivery` #FFFFFF/#1C1305 · `--mz-delivery-soft` #E7E9F6/#23263A. `--violet` is retired; all consumers map to `--delivery`.
>
> Every pairing above is verified WCAG AA (≥4.5:1) for normal text in both themes. No further colour decision is required to implement. These two resolutions clear the final visual blockers for promoting the Mezze appearance from feature-flagged preview to default production.

*This pack is a design decision, not an implementation. When approved, a scoped colour-token edit (primitives + aliases + the filled-danger consumer switch) applies it — no other change.*
