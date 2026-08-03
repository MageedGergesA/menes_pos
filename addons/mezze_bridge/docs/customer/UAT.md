# Mezze POS — Owner Acceptance (UAT)

For the **restaurant owner** to sign off before go-live. Work through each task on
your own site with real staff. Tick each box only when it behaves as described. Plain
language — no technical steps required beyond using the app.

Site: ____________________  Edition: ☐ Cloud ☐ Edge  Date: __________  Owner: __________

## A. Setup & configuration

- [ ] **1.** Onboard a branch: company, currency, timezone, and one POS point exist.
- [ ] **2.** Taxes and a cash journal are configured.
- [ ] **3.** Payment methods are set up (at least cash), and cash has a journal.
- [ ] **4.** The menu shows real products with categories and prices.
- [ ] **5.** Staff exist with personal PINs and correct roles (cashier/manager).
- [ ] **6.** (If dine-in) Tables/floor plan are configured.
- [ ] **7.** (If delivery) At least one delivery zone with a fee and COD is configured.

## B. Selling

- [ ] **8.** **Counter cash sale:** ring up items, take cash, give correct change, print/offer a receipt.
- [ ] **9.** The receipt totals and taxes are correct.
- [ ] **10.** **Dine-in flow:** open a table, add items, fire to the kitchen, add a later course, present the bill, pay.
- [ ] **11.** Firing twice does **not** double-send items to the kitchen.
- [ ] **12.** **Table-QR order:** scan a table's QR, add an item, it appears on the same table and fires to the kitchen exactly once.
- [ ] **13.** **Pickup order:** place a pickup order, pay at the counter, it reaches the kitchen and shows a status.
- [ ] **14.** **Kiosk (if used):** place an order, confirm it is created **unpaid** and paid at the counter (not faked as paid).

## C. Delivery

- [ ] **15.** **Delivery COD:** place a COD order — it is **unpaid** until collected.
- [ ] **16.** Assign a courier and mark it dispatched.
- [ ] **17.** **Collection:** record COD collection; the cash reconciles into the cash method.

## D. Money controls

- [ ] **18.** **Refund with manager PIN:** refund a paid order — it requires a manager PIN and is recorded in the audit log.
- [ ] **19.** A void/comp likewise requires a manager PIN.
- [ ] **20.** **Session close:** count the drawer; expected vs counted variance is reported.
- [ ] **21.** **Split payment:** split a bill by amount/line and pay with two tenders.

## E. Operations & assurance

- [ ] **22.** **Go-live check:** run the go-live validator for your business profile — overall is **not Fail** (all real blockers resolved).
- [ ] **23.** Any remaining **NOT TESTED** items are only physical hardware/host facts to certify on-site (nothing faked to pass).
- [ ] **24.** **Support bundle:** pull a support bundle and confirm it downloads (used if you ever need Mezze support).
- [ ] **25.** **By-channel report:** the manager report shows the orders you just placed, split by channel.
- [ ] **26.** **Arabic check:** switch a customer surface (QR menu / kiosk) to Arabic — it displays right-to-left and reads correctly.
- [ ] **27.** **Backup:** (Cloud) confirm with Mezze the last backup timestamp / (Edge) confirm a backup ran and a test restore succeeded.

## Sign-off

- [ ] All required tasks pass. Remaining items are on-site hardware certification only.

Owner signature: ____________________   Date: __________
