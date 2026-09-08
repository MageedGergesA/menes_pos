# Surface ledger — the frozen prototype against what we ship

Companion to `GAP_REGISTER.md`. That register asks *"does the addon have this capability"*;
this one asks *"is there a screen, and is there an engine behind it"* — for every surface the
prototype defines. Imported from Claude Design project `4b9aa028` on 2026-09-07; the bundle now
lives in the repo at `docs/design-handoff/` so it is versioned rather than sitting in a Downloads
folder.

**Measured, not estimated.** `Lines` is that surface's own markup in
`Mezze POS v3.dc.html`, counted by splitting the file on its top-level `<sc-if value="{{ isX }}">`
blocks. It is a size signal, not a hard estimate — but it is the only honest one available
before each surface is read against its domain doc.

| Surface | Rail | Lines | UI | Backend | Note |
| --- | --- | ---: | --- | --- | --- |
| `handheld` | Handheld | 1317 | `ABSENT` | `ABSENT` | Largest surface in the prototype (1,317 lines). No counterpart. |
| `cfd` | Display | 1259 | `SHIPPED` | `BUILT` | `/mezze/cfd` + `/cfd/push`. Ours is a thin static page; the prototype's is the 2nd-largest surface in the file. |
| `selfserve` | Self-service | 955 | `SHIPPED` | `BUILT` | kiosk.html / kiosk-v3.html / shop.html / qr.html + `/shop/*`, `/kiosk/config`, `/selforder/*`. |
| `eod` | Session | 938 | `PARTIAL` | `BUILT` | `session_close` component + `/sessions/*/close|z_report|cash_move`. Prototype's Session is 938 lines vs our modal. |
| `floor` | Floor | 722 | `SHIPPED` | `PARTIAL` | `/mezze/floor` Owl renders native geometry; the prototype's plan EDITOR (place/move/rotate, 140 part sprites) has no counterpart. |
| `register` | POS | 585 | `SHIPPED` | `BUILT` | `/mezze/pos` Owl. Visual gaps enumerated in GAP_REGISTER §8b. |
| `menu` | Menu | 553 | `ABSENT` | `PARTIAL` | 86 + quick keys + BE-010 modifier groups. No versioning, daypart, atomic publish, channel scope. |
| `kitchen` | Commissary | 484 | `ABSENT` | `BUILT` | `mezze.ck.request` + `/ck/board|request|produce|dispatch|receive`, no screen. |
| `channels` | Channels | 450 | `ABSENT` | `PARTIAL` | Generic HMAC aggregator ingest + payload mapping; no named vendor, no screen. |
| `guests` | Guests | 439 | `PARTIAL` | `BUILT` | Guest panel modal + `/customer/*`; no CRM screen. |
| `kds` | Kitchen | 436 | `SHIPPED` | `BUILT` | `/mezze/kds` Owl on `mezze.kds.ticket`. Prototype adds lanes/grid layout switch, all-day view, sort. |
| `callcenter` | Call centre | 364 | `ABSENT` | `PARTIAL` | GAP §3: zones/buffer/board engines exist; call record, refusals and Repeat do not. |
| `inventory` | Stock | 363 | `ABSENT` | `PARTIAL` | `/waste/*` + native stock; no count/variance screen. |
| `cost` | Plate cost | 362 | `ABSENT` | `ABSENT` | GAP §5 L-03: no aggregation over the comp/refire/waste ledgers. |
| `ops` | Live ops | 346 | `ABSENT` | `BUILT` | `/ops/summary`, `/manager/dashboard`, `/ops/pulse`; no screen. |
| `devices` | Devices | 303 | `PARTIAL` | `BUILT` | Odoo backend views for stations/printers/scales; no operator Devices screen. |
| `resv` | Deposits | 296 | `ABSENT` | `ABSENT` | BE-001 deposit → prepayment/accounting. Not found in repo. |
| `dtperf` | Drive-thru performance | 291 | `ABSENT` | `PARTIAL` | Stage timings are captured on `mezze.drivethru`; no performance screen reads them. |
| `ordering` | Ordering | 289 | `PARTIAL` | `BUILT` | `/shop/config` + channel pause/resume; no admin screen. |
| `mereq` | My requests | 287 | `ABSENT` | `ABSENT` | Workforce. Leave/swap/early requests. |
| `teamrep` | Team reports | 269 | `ABSENT` | `ABSENT` | Workforce. |
| `giftcards` | Gift cards | 251 | `PARTIAL` | `BUILT` | `enter_code` component + `/giftcard/issue|balance`; no gift-card workspace. |
| `hq` | HQ | 251 | `ABSENT` | `PARTIAL` | `/hq/summary` roll-up; no screen. |
| `rider` | Rider | 237 | `ABSENT` | `PARTIAL` | `mezze.courier` + dispatch; no rider app. BE-015 geocoding absent. |
| `onboard` | Onboarding | 235 | `ABSENT` | `ABSENT` | Workforce. (`mezze.onboarding` is DEPLOYMENT onboarding — a different thing.) |
| `staff` | On shift | 230 | `ABSENT` | `ABSENT` | Workforce. |
| `dtboard` | Drive-thru board | 226 | `SHIPPED` | `BUILT` | `/mezze/ocb/<display_token>` order-confirmation board. |
| `tax` | Tax | 222 | `ABSENT` | `PARTIAL` | ETA B2B `mezze.einvoice`. BE-013 B2C e-receipt does not exist. |
| `rota` | Rota | 213 | `ABSENT` | `ABSENT` | Workforce. |
| `drivethru` | Drive-thru | 206 | `SHIPPED` | `BUILT` | `/mezze/drivethru` lane board. |
| `delivery` | Delivery | 198 | `PARTIAL` | `BUILT` | `delivery_form` component + full `/delivery/*` engine. |
| `slots` | Shift slots | 187 | `ABSENT` | `ABSENT` | Workforce. |
| `me` | My shift | 184 | `ABSENT` | `PARTIAL` | `mezze.attendance` clock only. |
| `inbox` | Team admin | 168 | `ABSENT` | `ABSENT` | Workforce approval inbox. |
| `recon` | Reconcile | 160 | `ABSENT` | `BUILT` | `/reconciliation/summary|settlement|finalize`, no screen. |
| `absence` | Absence | 158 | `ABSENT` | `ABSENT` | Workforce. |
| `payroll` | Payroll | 150 | `ABSENT` | `ABSENT` | BE-020 export. Blocked on `hr.employee` adoption. |
| `booking` | Bookings | 148 | `ABSENT` | `BUILT` | `/reservations/*` + `/waitlist/*` FSMs exist with no screen at all. |
| `reports` | Reports | 131 | `ABSENT` | `BUILT` | `/reports/summary`, `/gl/*`, CSV exports; no screen. |
| `marketing` | Marketing | 131 | `ABSENT` | `PARTIAL` | `/marketing/segments|send|campaigns`; no screen. |
| `group` | Group | 129 | `ABSENT` | `PARTIAL` | `/branches`; no governance screen. |
| `exc` | Exceptions | 128 | `ABSENT` | `PARTIAL` | Append-only audit log exists; no exception workspace. |
| `kconf` | Kitchen setup | 121 | `ABSENT` | `PARTIAL` | Station routing is a hardcoded English keyword matcher — blocker for an Arabic menu. |
| `cover` | Shift cover | 121 | `ABSENT` | `ABSENT` | Workforce. |
| `linebust` | Line busting | 118 | `ABSENT` | `ABSENT` | Queue-breaking order taking. No counterpart. |
| `orders` | Orders | 112 | `PARTIAL` | `BUILT` | Orders workspace inside the Register, not its own screen. |
| `breaks` | Breaks | 104 | `ABSENT` | `ABSENT` | Workforce. |
| `myroster` | My roster | 81 | `ABSENT` | `ABSENT` | Workforce. |
| `settings` | Settings | 65 | `SHIPPED` | `BUILT` | Settings component + 101-setting admin console. |

## Totals

51 top-level surface blocks, **15,973 lines of prototype markup** across the 49 that map to a
navigable surface (two blocks — `isCash`, `isState` — are sub-views, excluded).

| | SHIPPED | PARTIAL | ABSENT |
| --- | ---: | ---: | ---: |
| Screen exists | 8 | 7 | 34 |
| Engine behind it | 19 | 14 | 16 |

By weight rather than by count: the 8 surfaces with a shipped screen are
**4,454 of 15,973 lines (27%)** of the prototype's markup.

## What the shape of this table says

**The gap is overwhelmingly UI, not engine.** Count the rows: 20 surfaces have a working
backend and no screen or only a partial one. Bookings, Commissary, Reconcile, Live ops and
Reports each have a complete, tested API and nothing that renders it — which is the same
finding the 2026-08-21 inventory recorded as *"45% of the API surface has no production
front-end caller"*, still true and now enumerated per screen.

So "finish all backend" is the wrong frame for most of this file. The genuinely absent
engines are a short list, and `GAP_REGISTER.md` already names them: Menu governance, Refire
costing, Kitchen multi-stage production, Arrival queue, Loss/plate cost — plus, from this
table, Deposits (BE-001), workforce scheduling, and the Handheld.

**Workforce is 13 of the 49 rows and is absent end to end.** It is also the one block that
should probably not be built here at all before a decision: Odoo has `hr`, `hr_attendance`,
`hr_holidays` and `hr_payroll`, and BE-008/BE-020 both point at `hr.payslip.input`. Building a
second rota/absence/payroll stack inside `mezze_bridge` would be the largest reuse violation
in the project. **Decision needed before any workforce row is scheduled.**

## Suggested order

Not the same order as `GAP_REGISTER.md`'s — that one sequences missing *engines*; this one
sequences *surfaces*, and the two interleave.

| # | Work | Why here |
| --- | --- | --- |
| 0 | Finish the in-flight Register §8b work | It is uncommitted in the tree right now. A half-built tax line is worse than none. |
| 1 | Render what is already built — Bookings, Commissary, Reconcile, Live ops, Reports | Five screens over five tested APIs. Highest value per line in the whole plan, and no new engine. |
| 2 | Menu governance + the modifier foundation | Five surfaces read it; `GAP_REGISTER` rows M-01..M-13, C-12, K-02 all sit on it. |
| 3 | Loss category enum → plate cost → refire | One column, one aggregation, then the incident record that completes the cost chain. |
| 4 | Arrival queue | Folds Bookings + waitlist + Floor into the one derived queue the design specifies. |
| 5 | Call centre | Thin: the engines exist. Needs the call record, the refusal surface and Repeat. |
| 6 | Handheld | Largest single surface; depends on the modifier foundation from #2. |
| 7 | Workforce | Only after the `hr` reuse decision above. |

Deliberately not scheduled: BE-013 ETA B2C, BE-015 geocoding, BE-016 notification BSP,
BE-017 MDM, BE-018 aggregator certification. Each needs credentials, a partner or hardware —
not backend code — and the handoff's own `GO_LIVE.md` outranks them.
