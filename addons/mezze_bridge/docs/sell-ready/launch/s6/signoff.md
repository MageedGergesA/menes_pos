# S6 — Final Commercial Signoff (PART 67)

Commercial launch requires **named** signoff from all four roles. **No single role
may waive a financial Critical defect.**

- **Release certified:** mezze-v1.0-rc1 / ad32f3ea533912e01cacaa92e3427f808ff1a92e
  (or the RC that finally passes — rc2+, if defects required a fix)
- **Editions in scope:** ☐ Cloud Base  ☐ Edge Base
- **Commercial profile(s) certified:** __________________________

| Role | Name | Verdict (GO / NO-GO) | Date | Signature/ref | Notes |
|---|---|---|---|---|---|
| Technical | | | | | RC identity, integrity, security |
| Operations | | | | | shift, hardware, WAN/power, restore |
| Finance / Reconciliation | | | | | **financial difference = 0** |
| Restaurant Manager | | | | | staff usability, real service |

## Gate roll-up (attach the DoD sheets)
- Cloud Base DoD: ☐ all PASS  → `cloud-dod.md`
- Edge Base DoD: ☐ all PASS  → `edge-dod.md`
- Commercial matrix complete: ☐ → `commercial-matrix.md`
- Open Critical defects: ______ (must be 0)
- Open financial Major defects: ______ (must be 0)
- Unexplained financial difference: ______ (must be 0.00)

## Final tag decision (PART 66)
- [ ] Base profiles required for v1 all PASS → **create `mezze-v1.0`** (annotated,
      on the passing RC commit; never move an RC).
- [ ] Not yet — remain on the current RC; record blockers below.

Blockers / conditions: ______________________________________________
