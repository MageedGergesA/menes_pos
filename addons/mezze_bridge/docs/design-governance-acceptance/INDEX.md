# D3 — Design, User-Settings & Admin-Governance Coverage — Evidence Index

| Field | Value |
|---|---|
| Date | 2026-07-24 |
| Commit | `ce8dc74` (+ D3 working changes) |
| Addon version | 19.0.1.6.0 |
| Environment | live Odoo 19 + PostgreSQL, DB `mezze_test` |
| Export source | `/home/mageed/Downloads/Mezze POS Visual Redesign/export` (40 files) |

## Contents
- `coverage-40-files.md` — all 40 export files inventoried + classified (freeze packs honoured).
- `settings-101-matrix.md` — all 101 stable setting IDs: type, default, **status** (18 working / 76 disabled / 7 hidden), runtime consumer or disabled/hidden reason, migration source.
- `controller-inventory.md` — 101 controller routes across the controller files (read/write mode).
- `settings-101-appearance-working-and-disabled.jpg` — live Settings UI: working settings interactive with provenance; disabled settings read-only + "Not available yet" + accurate reason; 13 sections; stable IDs shown.
- `settings-13-sections.jpg` — the 13-section Settings workspace.
- `admin-console-templates.jpg` — Admin Console (templates), authenticated human admin.
- `rtl-example.jpg` — Arabic RTL rendering.

## Conflicts and chosen interpretations
1. **Setting IDs**: pre-D3 engine used ad-hoc keys (mode, lightTheme…); `Settings.html` is authoritative with 101 stable IDs → adopted the 101 IDs + a documented migration map (domain/settings_catalog.MIGRATION_MAP) preserving user overrides. *(Newer authoritative source wins.)*
2. **catStyle / lineDetail / showProvenance / searchScope…**: pre-D3 extras not in the 101 → removed from the catalog; provenance is now always shown (not a toggle). *(Source-of-truth wins over prototype extras.)*
3. **Display vs. financial**: `or_tax_break`, `or_pay_default`, `or_print`, `qa_discount` are DISPLAY/permission-governed only and marked so — they never change tax, tender config, printer policy, or discount authority. *(Financial invariant wins over visual convenience.)*
4. **Freeze packs** (Cashier/Kitchen/Config/SaaS/Search) preserved as invariants; the amber certified build stays byte-identical under the mezze layer.

## Live verification (this session)
- Backend catalog seeded to **exactly 101** rows (pruned the 24 legacy defs).
- Settings UI rendered **13 sections, 101 settings, 18 working / 76 disabled / 7 hidden** (state.catalog).
- Disabled settings are read-only with reason; `save_user` rejects any non-working key (API-layer honesty).
- Bounded int (`gr_cols` 2..8) validated server-side (99 and 1 rejected).
- **202/202 tests green.**
