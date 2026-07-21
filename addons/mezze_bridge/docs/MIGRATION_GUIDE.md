# Migration Guide — Amber ⇄ Mezze

Technical reference for `mezze_bridge/static/pos.html`. Read this before touching any style in the file.

---

## 1. The core idea

There is **one component layer** and **two sets of token values**. Components never know which appearance is active — they read role tokens, and the appearance decides what those tokens resolve to.

```
components  →  role tokens  →  appearance decides the value
.card { background: var(--surface); padding: var(--sp-16); border-radius: var(--r-lg) }
                    ↓                        ↓                          ↓
   amber:        #17130C                   16px                       18px
   mezze:     var(--mz-surface)   calc(--mz-space-200 × density)   var(--mz-radius-xl)
```

**Consequence:** to change how something looks, change a token — never a component rule. A hardcoded value in a component is a bug, because it can only ever be right for one appearance.

## 2. Amber architecture (the certified default)

- All amber values live in the base `:root { … }` block as **literals**.
- Amber has **no density concept** — its spacing tokens are fixed px.
- Amber renders **legacy inline SVG icons**; no icon font is fetched.
- Amber is the default: with no `data-appearance` attribute, everything above applies.

**Amber is a release-blocking invariant.** It is proven pixel-identical across 2,510 declarations. Any change that alters an amber computed value is a regression, regardless of how good it looks.

## 3. Mezze architecture (the approved redesign)

Everything lives under `:root[data-appearance="mezze"]`, layered:

```
PRIMITIVE   --mz-space-*, --mz-size-*, --mz-radius-*, --mz-elev-*, --mz-dur-*, --mz-brand …
    ↓                          (× --mz-density where applicable)
SEMANTIC    --pad-card, --pad-dialog, --stack-md, --gap-grid, --accent, --surface, --ink …
    ↓
COMPONENT   --sp-16, --r-lg, --fs-14, --fw-700, --dur-fast, --shadow-sm …
    ↓
COMPONENTS  .card, .modal, .prod, .kcol …
```

**Compatibility tokens** (`--sp-N`, `--r-N`, `--fs-N`, `--dur-N`) exist for one reason: the amber literals sit on values that are on neither scale, so snapping them directly would have shifted amber. Each holds the exact amber literal and re-points to the approved step under mezze. **They are not a second design scale.** The public API is the approved scale.

## 4. Theme system — two orthogonal axes

| Attribute | Values | Controls |
|---|---|---|
| `data-appearance` | *(absent)* = amber · `mezze` | Which design system |
| `data-theme` | *(absent)* = OS · `light` · `dark` | Light/dark mode |
| `data-mz-density` | `compact` · `standard` · `comfortable` | Spacing scale (mezze only) |
| `data-mz-motion` | `off` | Manual reduced-motion |

They compose: `[data-appearance="mezze"][data-theme="dark"]` is a valid, defined state.

### ⚠️ Specificity is a real hazard here

`:root[data-appearance="mezze"]` is **(0,2,0)**. Any override intended to beat it must be at least (0,2,0) *and* later in source order. This has bitten the project twice:

- Reduced motion shipped broken because the approved `[data-mz-motion="off"]` selector is (0,1,0) — it silently lost.
- Density selectors were therefore written as `:root[data-appearance="mezze"][data-mz-density="…"]` **(0,3,0)** deliberately.

**Rule: never copy a selector from the export verbatim.** The export defines tokens on a flat `:root`; this file does not.

## 5. Feature flag

Read once at boot, before first paint:

```js
var _mzAp = new URLSearchParams(location.search).get('appearance')
         || localStorage.getItem('mzAppearance');
if (_mzAp) document.documentElement.setAttribute('data-appearance', _mzAp);
```

Enable by URL (`?appearance=mezze`), by `localStorage.mzAppearance = 'mezze'`, or by setting the attribute server-side.

**The flag is read at boot, not observed.** CSS-driven properties re-resolve if you toggle the attribute at runtime, but **icons do not** — `ICboot()` swaps the DOM once at startup. Always reload after changing appearance.

## 6. Icon system

```js
IC('close')  →  amber : '<svg viewBox="0 0 24 24" …>…</svg>'   (byte-identical original)
             →  mezze : '<span class="mi" aria-hidden="true">close</span>'
```

- JS-rendered icons call `IC('name')`.
- Static markup carries `<svg data-ic="name">`; under mezze `ICboot()` replaces it with the ligature.
- **Never inline new icon geometry.** Add a registry entry and reference it by name.
- Four items intentionally stay SVG: brand wordmark, sparkline, CSS `url()` lock, empty chart node.

## 7. Adding or changing a style — the rules

1. **Never hardcode** a colour, size, radius, shadow, duration or spacing value in a component. Use a token.
2. **Never change an amber token value.** That breaks the pixel-identity invariant.
3. To add a new value: add the amber literal to `:root`, add the mezze mapping to the appearance block, then reference it.
4. **Never write `*/` inside a CSS comment** — including inside token globs like `--pad-*/`. This silently destroyed two entire phases (see CHANGELOG).
5. Validate against the **live stylesheet**, not a reconstruction of it. Simulated CSS cannot detect that real CSS failed to parse.

## 8. Verifying a change

```bash
# structural
python3 -c "s=open('static/pos.html').read(); print(s.count('{'), s.count('}'))"   # must match
node --check <(python3 -c "import re;print(re.search(r'<script>(.*)</script>',open('static/pos.html').read(),re.S).group(1))")
```

In the browser (serve over HTTP, then compare `?appearance=amber` vs `?appearance=mezze`):

```js
// amber must be unchanged
getComputedStyle(document.documentElement).getPropertyValue('--accent')  // #EFA23C / #E0982B
document.querySelectorAll('span.mi').length                              // 0 under amber
// mezze must resolve to approved values
```

Then re-run the amber identity proof (recursive token resolution vs `git HEAD`) — the definitive gate.

## 9. Rollback

See `ROLLBACK.md`. Summary: stop setting the flag. There is no build step, no data migration, and no persisted state beyond one `localStorage` key.
