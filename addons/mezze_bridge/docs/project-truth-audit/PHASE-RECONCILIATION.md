# PHASE RECONCILIATION (from git commits + docs)

Audit 2026-08-05. Classification from commit messages + doc verdicts (docs = leads, cross-checked).

| Phase | Commit / tag | Classification |
|---|---|---|
| P1 (pilot RC1) | 634d17e (mezze-pilot-rc1) | CERTIFIED (pilot) |
| P1.1 (RC1 freeze) | 634d17e | SOFTWARE_COMPLETE |
| D-2 / RC2 (hermetic suite) | 13276b9 (mezze-pilot-rc2) | SOFTWARE_COMPLETE |
| R-1 (settings-catalog bootstrap) | 8ad8ed9 (mezze-pilot-rc3) | SOFTWARE_COMPLETE |
| O1 / on-site acceptance | 8219906 | OPERATIONAL_ACCEPTANCE_PENDING (scaffold, NOT EXECUTED) |
| S1 / S1.1 / S1.1B (Edge) | 1580da2…9f20f5b | PARTIAL — S1.1B clean-host gates NOT EXECUTED |
| S2 + S2C-1..7 (payments) | a36558f…2c17005 | SOFTWARE_COMPLETE; external payment cert PENDING |
| S3 (delivery) | d2549b9 | SOFTWARE_COMPLETE |
| S4 (self-service) | ffdb855 | SOFTWARE_COMPLETE |
| S5 (productization) | ad32f3e (mezze-v1.0-rc1) | SOFTWARE_COMPLETE (Software GO; Cloud/Edge CONDITIONAL) |
| S6 (physical pilot) | 72b4a11 | NOT_STARTED / scaffold (empty evidence dirs) |
| DESIGN-P1 (a11y) | 7fee641 (mezze-v1.0-rc2) | DESIGN_COMPLETE |
| DESIGN-P2 (shared foundation) | fb59c79 (mezze-v1.0-rc3) | DESIGN_COMPLETE — **latest certified RC** |
| DESIGN-P3 grounding | 553b21b | inventory/contract docs only |
| DESIGN-P3A (buttons) +A1/A2/A3 | cd49743…1b64d05 | **PARTIAL** (docs say COMPLETE — overstated; 3 legacy pages + cashier button drift) |
| DESIGN-P3B (status) B.1–B.5 | b442cea…5ec05b1 (HEAD) | **PARTIAL** (prototype-scoped; production cashier + legacy palettes remain) |
| P3C Alerts, P3D Inputs, P3E Quantity, P3F Dialogs, P3G Cards, P3H Empty/Loading, P3I Tabs | none | **NOT_STARTED** (deferral references only; P3D never even scheduled) |

Net: functional workstreams (P1→S5) SOFTWARE_COMPLETE and server-tested; operational/physical acceptance
(O1, S1.1B, S6) NOT EXECUTED; design stops mid-P3B with P3A also partial.
