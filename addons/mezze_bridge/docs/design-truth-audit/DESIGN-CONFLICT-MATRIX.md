# DESIGN CONFLICT MATRIX

| Topic | Original export | Current repo docs | Production (HEAD 96a72e1) | Prototype `pos.html` | Truth / required decision |
|---|---|---|---|---|---|
| **Brand color** | terracotta #C0602E / dark #D89A54 | COMPLIANCE_REPORT: "shipped amber #E0982B" | **terracotta #C0602E** (foundation.css; #E0982B=0×) | amber #E0982B ×2 | Production ALREADY terracotta. Compliance/signoff docs STALE. |
| **English font** | Hanken Grotesk | COMPLIANCE_REPORT: "system fonts" | **Hanken** (`--mz-font-text`, browser-verified) | own @font-face Hanken | Production correct. Doc stale. |
| **Arabic font** | IBM Plex Sans Arabic | — | correct on cashier/kds/6 customer; **misspelled `'IBM Plex Arabic'` on kiosk+onboarding** | Hanken/Plex | Fix kiosk/onboarding font name + bridge (design DEBT). |
| **Numeric font** | JetBrains Mono (tabular) | — | **only KDS**; cashier renders amounts in text font | mono in proto | Cashier should adopt `--mz-font-num` for amounts/totals. |
| **Spacing** | 4/8 lattice, semantic stacks | P-docs restate it | KDS on lattice; **cashier 0 primitives / 267 raw px** | mixed | Cashier spacing migration is the biggest token-adoption gap. |
| **Radius** | sm8/md11/lg14/xl16/pill | correct | KDS uses `--mz-radius-*`; **cashier local `--radius:14px`** | mixed | Cashier should consume `--mz-radius-*`. |
| **Component system** | 5 tiers, ~30 families, 16-state | P3A–P3I plan | **only 2 canonical** (`.mz-btn`, `.mz-status`/`.mz-badge`); P3C–P3I bespoke per-surface | proto reuses .mz-btn×59 | Component system is 2 families deep vs a designed ~30. |
| **Status ≠ color-only** | every state = color + 2nd signal | AC1_ACCESSIBILITY | Owl compliant (text+data-state); **drivethru/onboarding color-only dots** | proto ok | Customer legacy status = design DEBT. |
| **Touch ≥44px** | 44 min, +8 gap | — | KDS ≥48; **cashier qty 36px, cat tabs ~38px** | 44 in proto | Cashier qty/cat-tabs violate the 44px law (high-frequency). |
| **Dark mode** | authored `[data-mz-theme="dark"]` | "no HC exists" (DESIGN-P3B4) — FALSE | real registry on 8 surfaces; **kiosk/onboarding self-lavender, no registry** | proto registry | HC/dark exist; 2 surfaces off-registry. |
| **High Contrast** | app HC theme (AA floor) | contradictory | real Mezze HC theme (`?mztheme=highcontrast`); **no `prefers-contrast`/`forced-colors`** | proto | HC app theme real; OS forced-colors is a product-wide gap. |
| **Navigation / IA** | 6 workspaces + shell + role rail | — | **no production nav shell**; 2 isolated Owl apps | 11-dest rail + role gate (proto only) | MAJOR-RESTRUCTURE: real IA lives only in the prototype. |
| **Staff workspaces** | Cashier, Floor, KDS, Reservations, CRM, Reporting | — | **Cashier + KDS only**; Floor/Reservations/Delivery/Ops/Manager = proto+JSON | all as data-views | 4 of 6 designed workspaces are unbuilt as production. |
| **Screen count** | (n/a) | CURRENT-PAGE-INVENTORY "10 (cashier only)" | 2 Owl + rendered checkout + 9 static | 1 (11 views) | Inventory stale (missing KDS). |
| **Test count** | (n/a) | "403/0/0" ×16 docs | 428/0/0 | — | Stale numbers. |
| **Icon system** | Material Symbols Rounded 24px | — | inline SVG (labeled) | inline SVG | Icon-library drift (SVG vs Material Symbols); semantically labeled so low severity. |
| **Impl. tech** | framework-free vanilla JS | — | Owl (Odoo) | vanilla JS | Operator-approved supersession (framework-agnostic tokens); not a breach. |
