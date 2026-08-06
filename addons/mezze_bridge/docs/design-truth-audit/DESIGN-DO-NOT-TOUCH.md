# DESIGN DO-NOT-TOUCH (already aligned with the export + production needs)

Change only on a real defect. These are the strongest, evidence-verified parts — re-engineering them is churn.

1. **`static/design/foundation.css` token values** — near-exact reproduction of the export's authoritative tokens (fonts Hanken/IBM-Plex/JetBrains; spacing 4/8 lattice; radius 8/11/14/16/pill; type 11→40; touch 44/48; motion 80–320 + 4 eases; Arabic leading 1.7). Do not re-value.
2. **Brand identity** — `--mz-brand:#C0602E` light / `#D89A54` dark. Confirmed authoritative. Do not shift to amber/blue.
3. **The theme registry** (`static/mezze-design.css`) — classic/dark/highcontrast ramps + accents, gated on `[data-appearance=mezze][data-mz-theme][data-mz-mode]`. Real runtime dark + HC. Keep.
4. **Canonical `.mz-btn` / `.mz-status` / `.mz-badge`** (`components.css`) — the single correct sources for their families. Extend adoption, don't redefine.
5. **The entire `/mezze/kds` surface** — reference-grade compliance: 0 raw hex, full spacing/radius/numeric-font adoption, ≥48px touch, logical RTL, real dark/HC, restaurant-aging/allergen/cancel semantics. Do not re-style.
6. **Cashier payment hierarchy** — totals-as-read-only-mirror, mixed tender, idempotent tender-key, manager approval, receipt. Matches the export's payment law + is browser+backend certified. Do not re-architect.
7. **KDS restaurant semantics** — held-course-hidden, fired-course-once, addition ADDED-once, void→CANCELLED-shown, late-as-condition (not state), forward-only row-locked FSM. Matches Kitchen Freeze Pack. Do not change.
8. **Cashier color + theme + RTL layer** — token-based UI color (no raw-hex leaks beyond legitimate palette-def + QR-plate), logical properties, `unicode-bidi:isolate` on amounts, real dark/HC. Keep (fix spacing/touch/mono separately without disturbing this).
9. **Early-paint theme contract** — `?mzmode/?mztheme > localStorage > prefers-color-scheme`, flash-free, shared by cashier + KDS + 6 customer surfaces. Keep.
10. **Status-carries-text everywhere in Owl** — connectivity/KDS state chips carry `data-state` + translated label (never color-only). Matches the 2-signal law. Keep.

**Do NOT:** re-value tokens, re-theme the KDS, re-architect payments, change brand color, replace the theme registry, or "finish all components" ahead of the highest-frequency cashier gaps.
