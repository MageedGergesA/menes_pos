# Font Source & License (DESIGN-P2 Part C)

The three authoritative Mezze typefaces (+ the icon font) are **already vendored** in
`static/fonts/` (added 2026-07-21, before this task) and are all permissively licensed.
**No binary was extracted from the design export or re-downloaded in this task** — the
existing files were verified (`wOF2` magic) and their upstream licenses confirmed while
network was reachable.

| Family | Role | Files (weights) | Upstream project | Version | License | Copyright |
|---|---|---|---|---|---|---|
| **Hanken Grotesk** | interface (`--mz-font-text`) | `Hanken-{400,500,600,700,800}-{latin,latinext}.woff2` | github.com/marcologous/hanken-grotesk | (vendored 2026-07-21) | **SIL OFL 1.1** | © 2021 The Hanken Grotesk Project Authors |
| **IBM Plex Sans Arabic** | Arabic (`--mz-font-ar`) | `IBMPlexArabic-{400,500,600,700}-arabic.woff2` | github.com/IBM/plex | (vendored 2026-07-21) | **SIL OFL 1.1** | © IBM Corp. (IBM Plex Project Authors) |
| **JetBrains Mono** | numerics (`--mz-font-num`) | `JetBrainsMono-{400,500,600,700}-latin.woff2` | github.com/JetBrains/JetBrainsMono | (vendored 2026-07-21) | **SIL OFL 1.1** | © 2020 The JetBrains Mono Project Authors |
| Material Symbols Rounded (subset) | icons | `MaterialSymbolsRounded-subset.woff2` | github.com/google/material-design-icons | subset | **Apache-2.0** | © Google LLC |

- License text: **`static/fonts/OFL.txt`** (SIL Open Font License, Version 1.1 — the
  same text governs all three OFL families; per-family copyright lines above).
- Material Symbols is Apache-2.0 (icon font); attribution above.
- Integrity: all four verified as real WOFF2 (`wOF2` header); sizes recorded in
  `PAGE-LEDGER.md`/build notes.

**Verification status: PASS — packaging permitted.** All families are OFL-1.1 /
Apache-2.0, which allow bundling + web serving with attribution + license inclusion
(now added). No proprietary or unverified font is used. **No substitution** (Inter /
system-ui / Noto / Arial) was made for the design fonts.

**Design fidelity note:** the export's intended families exactly match the vendored
files (Hanken Grotesk, IBM Plex Sans Arabic, JetBrains Mono) — so the shared foundation
`@font-face`s these existing files; it does not introduce or require new binaries.
