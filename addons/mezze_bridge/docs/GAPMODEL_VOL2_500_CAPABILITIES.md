# Mezze — Complete Gap Model · VOLUME II: Top 500 Missing Capabilities

*Ranked by tier then grouped by domain so distinctness is auditable. Tiers: **[P0]** existential (system cannot operate/scale/be trusted without it) · **[P1]** critical (blocks enterprise/market) · **[P2]** high · **[P3]** medium · **[P4]** completeness. The cross-domain "start order" = all [P0] first (they concentrate in Runtime, Security, Payments, Multi-tenancy, Ops), then [P1]. Each item is a distinct runtime capability, not a restatement.*

## A. Runtime Substrate, Events & Data (1–30)
1. [P0] Append-only immutable event store (per-aggregate ordering).
2. [P0] Event envelope: event-time, observation-time, business-day, actor, tenant, causation, correlation, idempotency key.
3. [P0] Projection engine (deterministic, disposable read-models).
4. [P0] Replay engine (rebuild any projection / any past state).
5. [P0] Event schema registry + versioning + upcasters.
6. [P1] Snapshotting for large aggregates (bounded replay cost).
7. [P1] Event-store compaction/archival with retention tiers.
8. [P1] Deterministic projection checkpointing + crash-resume cursors.
9. [P1] Backfill/genesis projection from current Odoo state.
10. [P1] Dual-write bridge from `mezze.sync.outbox` into the event store.
11. [P1] Data contracts (producer/consumer schema enforcement in CI).
12. [P2] Change-data-capture stream to the warehouse.
13. [P2] Event replay sandbox (rebuild prod-shaped data in CI).
14. [P2] Poison-event quarantine + reprocessing tooling.
15. [P2] Projection lag/freshness SLOs + alarms.
16. [P2] Multi-projection consistency guarantees (read-your-writes on origin).
17. [P2] Temporal ("as-of") query API over history.
18. [P2] Event PII-classification + redaction hooks (feeds erasure).
19. [P3] Bi-temporal modelling (valid-time vs system-time).
20. [P3] Event enrichment pipeline (denormalized projections).
21. [P3] Idempotent projection replay verification harness.
22. [P3] Aggregate versioning + optimistic concurrency tokens.
23. [P3] Event ordering across aggregates (causal barriers where needed).
24. [P3] Cold-storage event retrieval SLA.
25. [P3] Projection rebuild throughput budget (≥1000 ev/s).
26. [P2] Ontology→code conformance test (40 entities ≡ models).
27. [P2] Machine-readable ontology artifact.
28. [P3] Reference-data management (currencies, countries, MCC codes, allergens).
29. [P3] Master-data management + golden-record resolution.
30. [P4] Event-catalog developer docs auto-generated from registry.

## B. Identity & Time (31–45)
31. [P0] Globally-unique, edge-born entity IDs (offline collision-free).
32. [P1] Reversible entity merge with full history preservation.
33. [P1] Un-merge (reverse a wrong merge) with audit.
34. [P1] Conflict-by-rule identity resolution (not last-writer).
35. [P2] Duplicate-detection service (guest/supplier/customer).
36. [P2] Cross-tenant identity NON-linkage guarantee (privacy).
37. [P1] Business-day engine (per-location, non-calendar day).
38. [P1] Event-time vs wall-clock separation enforced.
39. [P1] Timezone + DST correctness across 100 countries.
40. [P2] Kitchen (elapsed) time model.
41. [P2] Accounting-period time recognition.
42. [P2] Monotonic logical clocks for offline ordering.
43. [P3] Leap-second / calendar-edge handling.
44. [P3] Locale-aware calendar (Hijri, fiscal-year variants).
45. [P3] Clock-skew detection + correction on terminals.

## C. Authentication & Authorization (46–70)
46. [P0] Per-principal authentication (device/user/service) — retire shared token.
47. [P0] Short-lived signed tokens + refresh + rotation + revocation.
48. [P0] Route-level auth on every data endpoint (0 `auth='none'`).
49. [P0] Default-deny authorization engine.
50. [P1] Role × permission × scope model (tenant/branch/terminal/workspace/entity/record/field).
51. [P1] SSO — OIDC.
52. [P1] SSO — SAML 2.0.
53. [P1] SCIM user provisioning/deprovisioning.
54. [P1] MFA (TOTP/WebAuthn) + step-up auth.
55. [P1] Elevation (manager approval / PIN / session) with TTL + audit.
56. [P1] Approval workflows (void/refund/override/config change).
57. [P2] ABAC policy engine (conditional/time/location/device/risk).
58. [P2] Field-level authorization enforcement.
59. [P2] Delegated administration (tenant admins manage own roles).
60. [P2] Break-glass emergency access (audited, time-boxed).
61. [P2] Service-to-service authN (mTLS / signed service tokens).
62. [P2] Session management + device trust + concurrent-session limits.
63. [P2] Offline authorization via signed policy snapshot.
64. [P3] Just-in-time access provisioning.
65. [P3] Passwordless / phone-OTP staff login option.
66. [P3] Biometric terminal login (where hardware supports).
67. [P3] Role-mining / least-privilege recommendations.
68. [P3] Consent-based cross-tenant sharing (guest-initiated).
69. [P3] API-key management for partners (scoped, rotatable).
70. [P4] Login anomaly detection (impossible-travel, brute-force).

## D. Secrets & Platform Security (71–95)
71. [P0] Secrets vault (out of `ir.config_parameter`).
72. [P0] Secret rotation + expiry + access audit.
73. [P0] API rate limiting + quotas per principal/tenant.
74. [P0] WAF / API gateway with policy.
75. [P1] Secret-scanning in CI + pre-commit.
76. [P1] SBOM generation + dependency vulnerability scanning.
77. [P1] SAST + DAST in the pipeline.
78. [P1] CSP + security headers on all frontends.
79. [P1] Webhook signature + replay protection + rotation.
80. [P1] Encryption at rest (per-tenant keys) + in transit everywhere.
81. [P1] Key management (KMS/HSM) + envelope encryption.
82. [P2] Threat modeling (STRIDE) per service.
83. [P2] Penetration testing program (recurring).
84. [P2] Bug bounty / responsible disclosure.
85. [P2] Supply-chain security (artifact signing, provenance/SLSA).
86. [P2] DDoS protection + bot management.
87. [P2] Input validation / output encoding framework (injection defense).
88. [P2] CSRF protection review across surfaces.
89. [P2] Security incident response plan + runbooks.
90. [P3] Hardware/terminal attestation.
91. [P3] Certificate lifecycle management + auto-renew.
92. [P3] Data-loss-prevention on exports.
93. [P3] Insider-threat monitoring / privileged-access recording.
94. [P3] Red-team exercises (annual).
95. [P4] Security awareness training + phishing simulation.

## E. Payments (96–140)
96. [P0] PSP-agnostic payment abstraction (authorize/capture/void/refund).
97. [P0] Idempotency keys end-to-end (no double capture).
98. [P0] Tokenization vault (no PAN/CVV in Mezze storage).
99. [P0] PCI-DSS scope definition + attestation path.
100. [P1] 3-D Secure 2 / SCA (PSD2) support.
101. [P1] Multi-PSP routing + health-based failover.
102. [P1] Card-present terminal driver integration (EMV).
103. [P1] Card-not-present / online payment flows.
104. [P1] Digital wallets (Apple Pay, Google Pay, regional wallets).
105. [P1] Regional payment methods (mada, Fawry, Benefit, KNET, UPI, PIX…).
106. [P1] Offline card store-and-forward + risk policy.
107. [P1] Split payment (equal/amount/seat/item) with sum-invariant.
108. [P1] Partial payment + balance-due handling.
109. [P1] Refund (full/partial/line/tender-specific) via reversing entry.
110. [P1] Void (pre-capture) vs refund (post-capture) distinction.
111. [P1] Tips/gratuity (pre/post-auth, pooled, tip-out).
112. [P2] Surcharging / convenience fees (jurisdiction-aware legality).
113. [P2] Chargeback / dispute management + evidence submission.
114. [P2] Pre-authorization + incremental auth (bar tabs).
115. [P2] Currency conversion / DCC at point of sale.
116. [P2] Cash management (float, drops, pay-in/out, drawer recon).
117. [P2] Gift cards / stored value (issue, redeem, liability).
118. [P2] House accounts / on-account billing + terms.
119. [P2] Deposits / prepayments / deferred capture.
120. [P2] Payment reconciliation vs terminal batch.
121. [P2] PAR / network-token lifecycle management.
122. [P2] Retry/decline recovery (soft vs hard declines).
123. [P2] Payment link / QR-pay / pay-at-table.
124. [P2] Recurring / subscription billing (for SaaS + for restaurant memberships).
125. [P3] Buy-now-pay-later integrations.
126. [P3] Crypto acceptance (optional, jurisdiction-gated).
127. [P3] Loyalty-point tender.
128. [P3] Voucher / coupon tender.
129. [P3] Multi-acquirer settlement optimization (least-cost routing).
130. [P3] Fraud scoring at authorization (velocity, device, geo).
131. [P3] AVS / CVV / 3DS result handling policy.
132. [P3] Payment SLA + timeout policy per method.
133. [P3] Refund approval limits by role.
134. [P3] Payout to sub-merchants (marketplace/aggregator model).
135. [P3] Interchange++ / fee transparency reporting.
136. [P3] Payment method availability by tenant/branch config.
137. [P3] PCI network segmentation / P2PE evaluation.
138. [P4] Tap-to-phone (softPOS) support.
139. [P4] Open-banking / account-to-account payments.
140. [P4] Payment orchestration analytics (auth-rate optimization).

## F. Ledger, Settlement & Financial Operations (141–170)
141. [P0] Immutable double-entry ledger projection (balances to zero).
142. [P1] Multi-currency ledger + FX rate capture + revaluation.
143. [P1] Settlement reconciliation vs processor settlement files.
144. [P1] Fee / interchange accounting.
145. [P1] Fiscal-period close controls + lock.
146. [P1] Revenue recognition (accrual, deferred, service dates).
147. [P2] Payout / disbursement engine (marketplace).
148. [P2] Reserve / rolling-reserve accounting.
149. [P2] Journal export to external accounting (QuickBooks/Xero/SAP).
150. [P2] Chart-of-accounts mapping per tenant/jurisdiction.
151. [P2] Intercompany / multi-entity consolidation.
152. [P2] Bank reconciliation (statements → ledger).
153. [P2] Accounts receivable / aging for house accounts.
154. [P2] Accounts payable (supplier invoices).
155. [P2] Cost-of-goods-sold posting from recipe depletion.
156. [P2] Tax liability accounts + remittance tracking.
157. [P2] Loyalty / gift-card liability accounting.
158. [P2] Tip liability + payout accounting.
159. [P3] Cash-flow statement + working-capital views.
160. [P3] Financial-close checklist automation.
161. [P3] Audit-trail export for external auditors.
162. [P3] Multi-GAAP / IFRS support.
163. [P3] Transfer pricing / franchise royalty accounting.
164. [P3] Write-off / bad-debt handling.
165. [P3] Dispute / chargeback financial posting.
166. [P3] Deferred-revenue schedules (prepaid packages).
167. [P4] Real-time P&L per branch.
168. [P4] Budgeting / forecasting integration to ledger.
169. [P4] Grant/subsidy accounting (gov programs).
170. [P4] ESG / carbon-cost accounting hooks.

## G. Tax & Fiscalization (171–200)
171. [P0] Tax determination engine (jurisdiction cascade).
172. [P1] Discount-before-tax ordering enforced.
173. [P1] Inclusive/exclusive + compound tax computation.
174. [P1] Per-jurisdiction rule packs (framework + launch markets).
175. [P1] Fiscalization: KSA ZATCA (Phase 2 e-invoicing).
176. [P1] Fiscalization: EU per-country (Italy SdI, Spain, Hungary, Poland…).
177. [P1] Fiscalization: Egypt ETA (exists — harden + certify).
178. [P1] Fiscalization: LATAM (Brazil NF-e, Mexico CFDI, Chile…).
179. [P2] Tax exemption / B2B / reverse-charge handling.
180. [P2] Effective-dated tax rates (past sales taxed at then-rate).
181. [P2] Tax freeze/reverse (immutable legal figure).
182. [P2] Fiscal device / signature hardware integration (where mandated).
183. [P2] Tax reporting / filing exports per jurisdiction.
184. [P2] Digital-services / marketplace-facilitator tax rules.
185. [P2] Service charge vs tip vs tax interaction rules.
186. [P2] Rounding policy per jurisdiction (per-line vs per-order).
187. [P3] Tax remittance automation + calendar.
188. [P3] Withholding tax (some markets).
189. [P3] Excise / sin taxes (alcohol, sugar, tobacco).
190. [P3] Tourist / VAT-refund handling.
191. [P3] Multi-rate baskets (mixed food/alcohol/service).
192. [P3] Tax audit trail + jurisdiction versioning.
193. [P3] Real-time tax-authority reporting (where mandated).
194. [P3] Tax on delivery fees / packaging.
195. [P3] Nexus determination for online ordering.
196. [P3] Certificate management for exemptions.
197. [P4] Tax-engine parity harness vs `account.tax` (bit-for-bit).
198. [P4] What-if tax simulation for new markets.
199. [P4] Fiscal-pack authoring SDK for new countries.
200. [P4] Cross-border / customs for cloud-kitchen supply.

## H. Multi-Tenancy & Platform (201–225)
201. [P0] Tenant model + hierarchy (Tenant→Org→Brand→Restaurant→Branch→Terminal→User).
202. [P0] Tenant isolation across data/cache/files/jobs/search/events.
203. [P0] Cross-tenant leakage test suite (fuzz, 100% denied).
204. [P0] Provisioning saga (idempotent, compensatable, ≤90s, no partials).
205. [P1] Tenant lifecycle (Trial→Active⇄Suspended→Read-only→Archived→Deleted).
206. [P1] Per-tenant resource quotas + noisy-neighbor controls.
207. [P1] Entitlement / feature-flag resolution per tenant.
208. [P1] Per-tenant billing metering.
209. [P1] Tenant data residency routing (per country).
210. [P2] Tenant export / import (signed, versioned bundles).
211. [P2] Tenant clone (staging from prod).
212. [P2] Tenant merge / split (franchise reorg).
213. [P2] Dedicated-instance option for enterprise tenants.
214. [P2] White-label branding pipeline (domain/palette/logo).
215. [P2] Tenant health scoring + lifecycle automation.
216. [P2] Per-tenant backup + selective restore.
217. [P3] Tenant-level audit partitioning.
218. [P3] Tenant onboarding self-serve wizard (≤2 min).
219. [P3] Tenant offboarding + data-return + purge.
220. [P3] Cell-based tenant placement + rebalancing.
221. [P3] Tenant-aware caching namespaces.
222. [P3] Control-plane API (provision/suspend/restore/delete/clone/export/import/upgrade/downgrade/health).
223. [P3] Tenant configuration inheritance + locks.
224. [P4] Tenant cost attribution + profitability.
225. [P4] Tenant migration between cells/regions (cutover tooling).

## I. Sync, Offline & Consistency (226–250)
226. [P0] Exactly-once event apply (dual-guard: cursor + applied-ledger) — exists, harden.
227. [P0] Dead-letter quarantine + reprocessing — exists, harden.
228. [P1] Realtime transport (websocket/stream) for fan-out.
229. [P1] Conflict engine (per-field + additive line-merge + review queue).
230. [P1] Duplicate-collapse by idempotency key across replays.
231. [P1] Convergence SLA proof (≤5s post-reconnect at scale).
232. [P1] Durable encrypted local store (power-loss safe).
233. [P2] Offline operation matrix (full/limited/cached) enforced.
234. [P2] Priority draining (payments/kitchen first).
235. [P2] Backpressure + flow control on sync.
236. [P2] Out-of-order buffering + gap-timeout resync.
237. [P2] Tenant-scoped sync channels (no cross-tenant events).
238. [P2] Vector-clock / version-gated pull deltas.
239. [P2] Chaos/Jepsen-style consistency test harness.
240. [P3] Multi-terminal same-order concurrent editing.
241. [P3] Multi-branch replication topology (branch hub → cloud).
242. [P3] Sync bandwidth optimization (delta compression).
243. [P3] Offline duration / queue-depth telemetry.
244. [P3] Read-your-writes + monotonic-reads guarantees on origin.
245. [P3] Server-truth reconciliation for inventory (oversell flagged).
246. [P3] Sync cursor persistence + crash-resume.
247. [P3] Clock-based last-writer-wins ONLY for non-critical fields.
248. [P4] Cross-region sync latency SLOs.
249. [P4] Sync replay debugging tooling.
250. [P4] Offline-first PWA packaging for terminals.

## J. Observability, SRE & Ops (251–295)
251. [P0] Metrics pipeline (RED/USE, per service/tenant).
252. [P0] Distributed tracing (trace IDs end-to-end).
253. [P0] Structured logging (PII-scrubbed) + retention.
254. [P1] SLO/SLI definitions + error budgets.
255. [P1] Alerting + on-call rotation + escalation.
256. [P1] Dashboards (golden signals) per service/tenant.
257. [P1] Synthetic monitoring / canary probes.
258. [P1] Incident management (SEV levels, comms, postmortems).
259. [P1] Status page + uptime transparency.
260. [P2] Chaos engineering / fault injection.
261. [P2] Game-day exercises (recurring).
262. [P2] Real-user monitoring (frontend perf).
263. [P2] Log correlation + search at scale.
264. [P2] Anomaly detection on ops metrics.
265. [P2] Runbook automation.
266. [P2] Capacity planning + forecasting.
267. [P2] Cost/FinOps observability + per-tenant unit economics.
268. [P0] Disaster recovery plan + tested multi-region failover.
269. [P0] Per-tenant PITR backup + auto-verified restore drills.
270. [P1] RPO/RTO targets defined + proven (≤5m/≤30m).
271. [P1] Business-continuity plan (payments/kitchen degrade gracefully).
272. [P1] Data-corruption detection + recovery.
273. [P2] Cross-region active-active or active-passive strategy.
274. [P2] Backup encryption + immutability (ransomware-resistant).
275. [P2] Restore-time optimization (large tenants).
276. [P1] CI/CD pipeline (lint→test→scan→build→deploy).
277. [P1] Infrastructure-as-Code (full topology).
278. [P1] Blue-green + canary deploys + auto-rollback.
279. [P2] Progressive delivery + feature-flag governance.
280. [P2] Environment parity (dev/staging/prod) + ephemeral envs.
281. [P2] Database migration framework (zero-downtime, reversible).
282. [P2] Schema/data migration tests + dry-run.
283. [P2] Release train + change management + CAB-lite.
284. [P3] Deployment provenance + artifact signing.
285. [P3] Config drift detection.
286. [P3] Auto-scaling policies + load shedding.
287. [P3] Multi-region traffic management + geo-routing.
288. [P3] Edge caching / CDN per tenant.
289. [P3] Connection pooling + resource governance.
290. [P3] Job queue tenancy tagging + fairness.
291. [P3] Storage lifecycle / tiering / archival.
292. [P3] Certificate/DNS automation.
293. [P4] Green/sustainable compute optimization.
294. [P4] Observability-as-code (dashboards in VCS).
295. [P4] Toil measurement + reduction program.

## K. Scale & Performance (296–320)
296. [P0] Cell-based architecture (bounded blast radius) for 1M restaurants.
297. [P0] Horizontal scaling / sharding strategy (tenant-sharded).
298. [P1] Load testing at 1M-restaurant / peak-rush scale.
299. [P1] Soak / endurance testing (memory leaks, connection exhaustion).
300. [P1] Performance regression gates in CI.
301. [P1] Capacity model (per-tenant resource envelope).
302. [P2] Read/write splitting + replicas.
303. [P2] Query performance budgets + slow-query governance.
304. [P2] Hot-partition / celebrity-tenant mitigation.
305. [P2] Caching strategy (read-through, invalidation ≤1s).
306. [P2] Async / background job scaling.
307. [P2] Rate-limit + admission control under overload.
308. [P2] Backpressure across the stack.
309. [P3] Data archival to keep hot set small.
310. [P3] Index strategy + maintenance automation.
311. [P3] Connection/thread pool tuning per workload.
312. [P3] Payload size / N+1 audits.
313. [P3] Frontend bundle-size + TTI budgets (≤2s).
314. [P3] Virtualization for 10k-SKU grids / 1000-ticket KDS.
315. [P3] Search latency budgets (≤80ms@10k).
316. [P3] Multi-region latency SLOs (≤ target per continent).
317. [P4] Edge compute for offline-first terminals.
318. [P4] Cost-per-transaction optimization.
319. [P4] GPU/inference capacity planning for AI.
320. [P4] Peak-event (holiday/Ramadan) surge playbooks.

## L. Inventory & Supply (321–340)
321. [P1] Recipe → ingredient depletion on sale (true consumption).
322. [P1] Stock = net-of-movements (movements primary, balance derived).
323. [P1] Physical counts as adjustment movements (no silent overwrite).
324. [P1] Waste events → outbound movements + cause.
325. [P2] Multi-location transfers (paired movements).
326. [P2] Par levels + reorder points + auto-PO suggestions.
327. [P2] Purchase orders + goods receipt + 3-way match.
328. [P2] Supplier catalog + price history + lead times.
329. [P2] Yield / prep / sub-recipe management.
330. [P2] Batch / lot / expiry tracking (allergen + recall).
331. [P2] Food-cost % + variance analysis.
332. [P3] Inventory valuation (FIFO/weighted-avg).
333. [P3] Central-kitchen production + dispatch (exists thin — deepen).
334. [P3] Supplier performance / waste attribution.
335. [P3] Demand-based ordering (forecast-driven).
336. [P3] Shrinkage / theft detection.
337. [P3] Unit-of-measure conversions (purchase→recipe→sale).
338. [P4] Cold-chain / temperature compliance logging.
339. [P4] Supplier marketplace / demand aggregation (North Star liquidity).
340. [P4] Sustainability / food-waste reporting.

## M. Kitchen & Restaurant Operations (341–360)
341. [P1] 14-state KDS ticket FSM.
342. [P1] Deterministic station routing (category→station→override→fallback).
343. [P1] Recall contract (served→rejected→corrective).
344. [P2] Bump-bar / KDS hardware integration.
345. [P2] Cook-time SLA prediction + aging alerts.
346. [P2] Course firing / pacing / coursing.
347. [P2] Expo aggregation across stations.
348. [P2] Multi-screen KDS sync.
349. [P2] Allergen / dietary flag propagation to kitchen (safety).
350. [P2] Labor scheduling / rostering.
351. [P2] Time & attendance → payroll integration.
352. [P2] Shift management + cash-session accountability.
353. [P3] Prep lists / production planning.
354. [P3] Table management / floor plan / turn-time.
355. [P3] Waitlist + reservation integration.
356. [P3] Drive-thru / curbside flow.
357. [P3] Delivery dispatch + rider management.
358. [P3] Multi-brand / ghost-kitchen operations.
359. [P4] Voice-ordering / drive-thru AI.
360. [P4] Kitchen equipment IoT integration.

## N. CRM, Loyalty, Reservations, Pricing, Promotions (361–385)
361. [P2] Customer segmentation engine.
362. [P2] Customer journeys / lifecycle campaigns.
363. [P2] Consent + preference management (linked to privacy).
364. [P2] Loyalty tiers + benefits + accrual/redemption.
365. [P2] Cross-brand / coalition loyalty.
366. [P2] Loyalty liability accounting.
367. [P2] Reservation channel integrations (Google, OpenTable-class).
368. [P2] No-show prediction + deposit policy.
369. [P2] Dynamic pricing (day-part, demand, channel).
370. [P2] Channel-specific pricing (delivery vs dine-in).
371. [P2] Price versioning (historical price truth).
372. [P2] Best-price / stacking discount solver.
373. [P2] Coupon / voucher / promo-code lifecycle.
374. [P3] Promotion attribution + retention measurement.
375. [P3] Gift-card program management.
376. [P3] Referral / affiliate programs.
377. [P3] Feedback / review management + sentiment.
378. [P3] Marketing-consent + suppression (CAN-SPAM/GDPR).
379. [P3] Customer 360 profile (across channels).
380. [P3] Birthday / anniversary / win-back automation.
381. [P3] Membership / subscription (restaurant-side).
382. [P4] Personalization / recommendation at ordering.
383. [P4] Waitlist SMS/notifications.
384. [P4] Reservation deposit + prepayment.
385. [P4] Corporate / event catering CRM.

## O. Config, Printing, Notifications, Search (386–410)
386. [P1] Configuration cascade engine (8–9 level, nearest-wins, LOCK).
387. [P1] Config versioning + publish/rollback + scheduled publish.
388. [P1] Config templates (QSR/fine-dining/cafe/cloud-kitchen…).
389. [P2] Config validation engine (dependency/circular/reference checks).
390. [P2] Config deployment (single/multi-branch/canary/staged).
391. [P2] Config change propagation ≤1s + audit.
392. [P1] Durable print queue + DLQ + failover.
393. [P2] Intent-based print routing (Restaurant Config owns map).
394. [P2] Governed reprints (approval + reason + REPRINT stamp).
395. [P2] Printer device registry + health + fallback groups.
396. [P2] Label / QR / barcode document schema.
397. [P1] Notification service (categories/priorities/channels).
398. [P2] Escalation ladder (unacked critical → manager → HQ).
399. [P2] Inbox / history + dedup + grouping + rate-limit.
400. [P2] Notification channels (toast/banner/dialog/badge/email/SMS/push/webhook).
401. [P1] Search service (multi-provider, 6-stage pipeline).
402. [P1] Arabic normalization + English normalization pipeline.
403. [P2] Deterministic ranking contract (weights from config).
404. [P2] Offline search index + atomic swap + rollback.
405. [P2] Permission-filtered + tenant-isolated search results.
406. [P3] Barcode/SKU exact-match + fuzzy + phonetic.
407. [P3] Search telemetry (no-result terms → merchandising).
408. [P3] Voice / AI search hook (no-op until AI ships).
409. [P4] Cross-entity global search (orders/customers/reports).
410. [P4] Search relevance A/B testing.

## P. Analytics, Forecasting, Benchmarking (411–430)
411. [P1] Analytics warehouse fed from event log/CDC.
412. [P1] Semantic metrics layer (governed definitions).
413. [P2] Self-serve BI + scheduled reports.
414. [P2] Executive dashboards (owner/HQ/franchise).
415. [P2] Cohort / retention / RFM analysis.
416. [P2] Menu-mix / item-profitability analysis.
417. [P1] Demand forecasting (sales/covers).
418. [P2] Inventory-depletion forecasting.
419. [P2] Labor forecasting / scheduling optimization.
420. [P2] Forecast accuracy tracking (MAPE) + backtesting.
421. [P1] Cross-restaurant benchmarking engine (privacy-preserving).
422. [P1] Benchmark peer-set / similarity / cohorting.
423. [P2] Re-identification-resistant aggregation (k-anonymity/clean-room).
424. [P2] Financing-qualification scoring (fintech).
425. [P3] Supplier / procurement benchmarking.
426. [P3] Anomaly detection (refund/void/cash abuse).
427. [P3] Data-freshness SLOs + quality checks.
428. [P3] Report export (PDF/CSV/API) governance.
429. [P4] Embedded analytics for partners.
430. [P4] Real-time streaming analytics (live ops).

## Q. AI, Model Governance & Safety (431–460)
431. [P1] Provider-agnostic AI abstraction (cloud + local).
432. [P1] Advisory-only guardrail (AI never mutates truth).
433. [P1] Confidence gating (abstain below threshold).
434. [P1] Explanation / reason on every AI output.
435. [P1] Model registry + versioning + rollback.
436. [P1] Prompt-injection / jailbreak defense.
437. [P1] Hallucination control (grounding + citation + abstain).
438. [P1] AI evaluation harness + golden sets + CI gates.
439. [P2] Model drift monitoring + retraining triggers.
440. [P2] PII redaction before inference (tenant-isolated).
441. [P2] Responsible-AI review (bias, fairness, fraud FP).
442. [P2] Human-in-the-loop for money/stock-affecting outputs.
443. [P2] AI cost governance (cloud vs local per capability).
444. [P2] Copilots (manager/cashier/kitchen/inventory/support) advisory.
445. [P2] OCR (invoice/receipt) → draft, human-confirm.
446. [P2] Translation (AR↔EN + more) with quality gates.
447. [P2] Recommendation / upsell / substitution (advisory).
448. [P3] Forecast/optimization model serving + caching.
449. [P3] Feedback loop (accept/reject) → model improvement.
450. [P3] AI audit log (prompt/response/decision provenance).
451. [P3] Data-clean-room for cross-tenant model training (privacy).
452. [P3] Model cards + documentation.
453. [P3] Adversarial / robustness testing.
454. [P3] Content-safety filters (toxic/unsafe outputs).
455. [P3] Rate limiting / cost caps per tenant on AI.
456. [P3] On-device / edge inference path.
457. [P4] Autonomous agent guardrails (if ever enabled).
458. [P4] Synthetic-data generation for eval.
459. [P4] AI-governance board + approval workflow.
460. [P4] Regulatory AI compliance (EU AI Act classification).

## R. Plugin Platform, Marketplace, Partner, ERP, DX (461–485)
461. [P1] Frontend de-monolith (shell + workspace modules, byte-parity).
462. [P1] Plugin SDK (manifest, lifecycle, 21 extension points).
463. [P1] Plugin sandbox (no core edit, no permission bypass).
464. [P2] `mezze lint` conformance gate (blocks bad plugins).
465. [P2] Marketplace (signed bundles + review + entitlements + billing).
466. [P2] Public versioned partner API (OAuth, rate-limited, documented).
467. [P2] Developer portal + API reference + sandbox.
468. [P2] `mezze` CLI (scaffold/lint/deploy/migrate).
469. [P2] ERP connector framework.
470. [P2] ERP connectors: SAP / Oracle / NetSuite / QuickBooks / Xero.
471. [P2] Accounting/POS data-exchange standards support.
472. [P3] Webhook subscriptions for partners (delivery guarantees).
473. [P3] Delivery-aggregator connectors (UberEats/Deliveroo/regional).
474. [P3] Payment-provider plugin interface.
475. [P3] Printer-driver plugin interface.
476. [P3] Identity-provider plugin interface (BYO-IdP).
477. [P3] Extension-point conformance test kit.
478. [P3] Plugin telemetry + health + kill-switch.
479. [P3] Semver + minSdk gating + deprecation windows.
480. [P3] Local dev environment + hot reload for plugins.
481. [P4] Plugin revenue-share + payout.
482. [P4] Marketplace search / discovery / ratings.
483. [P4] Partner certification program.
484. [P4] GraphQL/gRPC alternative API surface.
485. [P4] Sandbox data seeding + test fixtures for partners.

## S. Compliance, Privacy, Legal, GTM (486–510 → capped at 500)
486. [P0] PCI-DSS attestation (AOC/ROC) for deployment topology.
487. [P1] SOC 2 Type II control implementation + evidence.
488. [P1] ISO 27001 ISMS + certification.
489. [P0] GDPR: consent store + lawful-basis tracking.
490. [P0] GDPR: DSAR (access/portability) end-to-end.
491. [P0] GDPR: right-to-erasure reconciled with immutable audit.
492. [P1] Data-residency enforcement per country.
493. [P1] Data catalog + lineage + classification.
494. [P1] Records retention + legal hold + e-discovery export.
495. [P1] DPA + sub-processor management.
496. [P2] AML / KYC / sanctions screening (fintech/lending).
497. [P2] Consumer-protection / receipt-law per jurisdiction.
498. [P2] Accessibility conformance (WCAG AA) + VPAT.
499. [P2] Localization pipeline (TMS, N languages, pluralization).
500. [P1] Commercial stack: metered billing, SLAs, enterprise procurement kit (security questionnaire/RFP), professional services, customer success, training + certification.

*Volume II ends. 500 distinct capabilities, tier-ranked. Beyond 500 (recorded but not enumerated here): government/FedRAMP posture, insurance/underwriting integrations, franchise-disclosure compliance, union/labor-law scheduling constraints, per-country hardware certification, carbon/ESG reporting, and ~40 further completeness items surfaced in the self-audit (Vol VI). The count is not the ceiling; it is the floor a Fortune-100 board expects covered.*
