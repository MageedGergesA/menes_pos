# STALE DOCS & CONFLICTS (audit-only — DO NOT correct in this pass)

Audit 2026-08-05. HEAD `5ec05b1`. Truth precedence: git > code > tests > runtime > design source > docs.

| # | File(s) | Stale/conflicting statement | Current truth |
|---|---|---|---|
| A | 16+ docs (sell-ready/FINAL-READINESS.md:41,59; DESIGN-P2-RESULT:61…; DESIGN-P3B-STATUS-RESULT:50; DESIGN-P3B3:46; DESIGN-P3B4:71; design-audit/DESIGN-AUDIT-REPORT:6) | test suite = **403/0/0** | **405/0/0** at HEAD (re-verified this audit). 403 was true at rc1/rc3; P3B.4A + P3B.5 added 2 tests. No doc says 405. |
| B | DESIGN-P3B4-FLOOR-DELIVERY-RESULT.md:104 (+P3B.4/4A prose) | "**No HC mode exists** anywhere in the product" | **FALSE** — a real runtime Mezze HC app theme exists (mezze-design.js + mezze-design.css). Corrected in DESIGN-P3B-STATUS-RESULT:99-105 & P3B.5, but the P3B.4 doc still ships the wrong claim → contradictory pair. |
| C | sell-ready/edge/engineering/edge-validator-output.txt:2; go-live/P1-FINAL-REPORT.md:4; release-manifest.md:14 | certified OS = **Ubuntu 22.04** | Current code certifies **24.04** (common.sh hard gate, golive.py:418, installer). 22.04 refs are stale evidence. |
| D | sell-ready/launch/s6/README.md:37-38; FIELD-RUNBOOK.md:18,117 | deploy pin `mezze-v1.0-rc1` (ad32f3e); "HEAD == ad32f3e" | Latest certified RC = **rc3 (fb59c79)**; **HEAD = 5ec05b1, 12 commits past rc3**. S6 pins the oldest RC. |
| E | DESIGN-P3B* docs ("browser-verified", "Live-measured #000/#FFF", "LIVE (dark)") | imply reproducible browser verification | **No browser/frontend test exists** (TEST-TRUTH). All such numbers are manual one-offs on the **pos.html PROTOTYPE**, not the production cashier, not reproducible from the suite. Sibling doc DESIGN-P3B3:26 itself says "NOT live-verified / cannot browser-verify". |
| F | P3A result docs ("DESIGN-P3A COMPLETE") | P3A buttons complete | **PARTIAL** — 3 legacy button pages (drivethru/feedback/courses) + a 2nd drifted `.mz-btn` base in the production cashier (cashier.css:134, no min-height:44px). (DESIGN-TRUTH) |
| G | P3B.5 result ("Coherence 95%, Readiness 91%"); P3B "advancing" narrative | design nearly done | Measured on the **prototype**. Product-wide: P3A & P3B both PARTIAL; P3C–P3I NOT STARTED; production cashier status not on canonical `.mz-status`; kiosk+onboarding have no theme engine. Scores are optimistic vs shipped surfaces. |
| H | Version strings | manifest **19.0.2.0.0** vs edge pack **19.0.1.9.0** (mezze-pilot-rc3) vs product version **1.0.0-rc.1** (productization.py:16) | three different version identifiers coexist; deploy pack/cert report reference an older module rev than the current manifest. |
| I | sell-ready docs framing | (mostly honest) | FINAL-READINESS correctly hedges Cloud/Edge as CONDITIONAL with external/hardware cert PENDING. Only stale element is the embedded 403 count. No unqualified "100% complete" claim found (the one "100%" hit argues AGAINST claiming completeness). |

Recommended (LATER, not now): single-source the test count + version + certified-OS; retract the P3B.4
"no HC" paragraph; re-pin S6 to rc3/HEAD-policy; relabel P3A/P3B result docs "prototype-scoped, PARTIAL".
