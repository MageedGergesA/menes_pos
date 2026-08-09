# R1B — Cashier Speed UX — Result

**Scope:** speed-of-service UX on the REAL production cashier `/mezze/pos`
(standalone Owl app `static/src/cashier/**`). **No new business features** — no new
financial semantics, no new order/tender/refund behaviour. Deterministic only (no
AI/ML). Every meaningful change was developed and shown LIVE in the real cashier.

**Hard safety invariant (held throughout):** nothing added here confirms a payment,
refund, void, or manager override. Undo is cart-only. Keyboard shortcuts navigate and
add lines and *open* the payment screen — they never submit a tender.

---

## Checkpoints

### 1. Favorites (device-local, per branch+user)
A pinned pseudo-category of the cashier's most-used products for 1-tap repeat.
- Frequency is tracked in `localStorage` under
  `mezze:favorites:v1:<config_id>:<user_id>` — scoped to the **authenticated user AND
  branch** (real bootstrap ids, no names/emails). Cashier A and Cashier B on the same
  terminal never share favorites; the same cashier keeps theirs across reloads.
- **DEVICE-LOCAL ONLY.** No server model, no roaming between terminals in R1B.
- Files: `order_store.js` (`favKey`, `_favMap`, `_bumpFavorite`, `favoriteIds`),
  `root.js` (`favoriteProducts`, `hasFavorites`), `root.xml` (★ chip).

### 2. Predictive Defaults
On initial load only: if the cashier already has favorites, the app opens on the
Favorites view (their usuals one tap away). A fresh cashier opens on All. Fully
reversible — tapping any chip overrides instantly. Never auto-confirms anything.
- Files: `root.js` `_applyPredictiveDefaults()` (called once in `bootstrap`).

### 3. Undo (non-financial cart action)
Removing a cart line shows a brief, non-blocking, screen-reader-announced toast
(`role="status"`) offering **Undo**. Undo restores the EXACT removed line.
- **Exact-line identity:** every cart line carries a stable client `key` (`_uuid`).
  The same product may be several distinct lines (modifiers / notes / courses /
  context); removal + Undo operate on the **line key**, never on product id. `remove`
  resolves by key; `undoRemove` restores key + qty + note at the original position and
  is idempotent (a second undo is a no-op). `toSyncLines()` aggregates distinct
  same-product lines by product id so the payment path is unchanged.
- Cart edits only — payment/refund/void are never undone here (server-authoritative).
- Files: `order_store.js` (`_uuid`, `_findLine`, `remove`, `_setUndo`, `undoRemove`,
  `clearUndo`, `toSyncLines`), `root.js` (`undoMsg`, `onUndo`, `dismissUndo`),
  `root.xml` (toast), `cart.xml` (**t-key fixed to `line.key`** — the old
  `line.product.id` key collided for distinct same-product lines).

### 4. Keyboard Productivity
A single global `keydown` listener drives navigation/search/add only.
- **`/`** focuses the product search (discoverable via the placeholder
  "Search menu — press /" and the on-screen hint line).
- **Type** to filter the whole catalog (case-insensitive substring; deterministic,
  source-order preserved). The single best match is keyboard-highlighted.
- **↑ / ↓** move the highlight (clamped, no wrap). **Enter** adds the highlighted
  line and keeps the search open for rapid multi-add.
- **Ctrl+Enter** or **F2** OPEN the payment screen (safe navigation only).
- **Esc** clears the search (menu) or goes back from payment to the menu — and only
  when no payment sub-modal is open (a modal owns its own Cancel; a global Esc never
  silently dismisses an approval/tender flow).
- **No dangerous op has a shortcut.** No key submits a tender, refund, void, or
  manager override.
- Files: `order_store.js` (pure `filterProducts`, `clampIndex`), `root.js`
  (`filteredProducts`, `highlightId`, `handleKey`, `_noPaymentModal`, search state +
  ref + listener lifecycle), `root.xml` (search bar + hint), `product_grid.*`
  (`highlightId` → `.mz-tile--kbd`), `cart.xml` (Charge tooltip "Ctrl+Enter or F2"),
  `cashier.css` (search bar, highlight ring, hint, 44px touch targets).

---

## Verification

### Automated (real Chrome / headless — the authoritative acceptance)
- **HOOT unit suite:** 40 tests / 146 assertions — *suite succeeded*.
  Includes R1B favorites per-(branch,user) isolation (5), exact-line remove/undo (9),
  keyboard product-search filter (4) and highlight-index clamp (3).
- **Cashier browser suite (`TestCashierBrowser`):** all pass, incl.
  - `test_09_r1a_design_compliance` (44px touch, mono money, focus-visible),
  - `test_10_r1b_undo_restores_removed_line` (remove → toast → Undo → exact line
    restored → **0 `pos.order`**),
  - `test_11_r1b_keyboard_productivity` (`/` focus → filter 5→1 → highlight → Enter
    adds → Esc clears → **F2 opens payment** → Esc back → **0 `pos.payment`**).
- **Combined run:** `0 failed, 0 error(s) of 12 tests` on a clean `--without-demo=all`
  DB.

### Live (claude-in-chrome, real `/mezze/pos`, foreground)
- Favorites view + Predictive default (opens on ★ Favorites). ✅
- Exact-line remove: removed the middle of a 3-line cart; the sibling lines stayed
  untouched. ✅
- Undo toast rendered ("Removed <item> · Undo · ✕"). ✅
- Keyboard: `/` focus → typed "cof" narrows to Arabic Coffee (highlighted) → Enter
  adds it → F2 opens Payment (Paid $0.00, "No tenders yet") → Esc back to menu. ✅
- Console: 0 errors throughout. ✅

**Known live-capture limitation:** the Undo *restore click* could not be reliably
captured inside claude-in-chrome — the toast lives 6 s while the background tab freezes
rAF (screenshots intermittently returned "renderer may be frozen"), so the click
repeatedly landed after auto-dismiss. This is an environment timing race, not a code
defect; the restore is proven deterministically by `test_10` in real headless Chrome.
