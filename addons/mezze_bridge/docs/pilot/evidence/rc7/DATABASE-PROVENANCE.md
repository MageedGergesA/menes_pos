# RC7 — Pilot database provenance

No lineage was fabricated. The RC7 pilot database descends from the database the
**live RC6 canonical pilot was actually serving**, via a single verified artefact.

```
live RC6 pilot runtime (:8090, product_version 1.0.0-rc.6)
        │  serving
        ▼
   mezze_pilot_rc6  (65 MB, filestore 447 files)
        │  odoo-bin db dump  (DB + filestore)
        ▼
   pre-rc7_mezze_pilot_rc6_20260812-173401.zip
   sha256 3f96a20e8f71547033a37557d1e717f8233d62cdc1c2e5074b15c1406a66f81e
        ├──► restore proof  → mezze_prerc7_restoretest  (verified, then removed)
        └──► mezze_pilot_rc7  ← the RC7 pilot database
```

| Field | Value |
|---|---|
| Source release | RC6 (`mezze-v1.0-rc6`, `e85be35…`) |
| Source DB | `mezze_pilot_rc6` |
| Source filestore | `~/.local/share/Odoo/filestore/mezze_pilot_rc6` (447 files, 19 MB) |
| RC7 DB | `mezze_pilot_rc7` (63 MB) |
| RC7 filestore | `~/.local/share/Odoo/filestore/mezze_pilot_rc7` (447 files) |
| Creation method | `odoo-bin db load` of the verified pre-RC7 backup |
| Pre-existing RC7 DB | none — confirmed absent before creation, nothing was dropped or forced |

**Provenance: PASS.** The RC6 source database, its filestore and the RC5 rollback
database were all left untouched.
