# Mezze POS — Troubleshooting

Fast decision trees for the most common issues. For each: **symptom → checks →
resolution → when to pull a support bundle**. Pull a redacted support bundle any time
Mezze support is involved: `POST /mezze/api/v1/admin/support_bundle` (no secrets, no
PII leaves the site).

## Can't log in

- **Checks:** Right URL and edition? PIN correct and not deactivated? Is the staff
  record active with a role? For admins, are you using a real account (not a disabled
  shared/default one)?
- **Resolution:** A manager/admin resets the PIN in the Admin Console. Confirm the
  role is assigned. Never re-enable `admin/admin` or a shared token in production.
- **Bundle:** if logins fail site-wide (not one person), pull a bundle.

## Payment declined / stuck

- **Checks:** Which tender? Integrated terminal — is the device online and reachable?
  Online/Paymob — is WAN up and the provider enabled? Manual card — was a reference
  entered?
- **Resolution:** For a stuck integrated terminal, follow the terminal's cancel/retry;
  Mezze reconciles from the terminal's result, not a guess. For online, retry once WAN
  is back. Reconciliation flags online transactions that completed but did not link —
  the manager clears those (see `MANAGER-GUIDE.md`).
- **Bundle:** if a tender is repeatably stuck, pull a bundle before retrying live.

## KDS not firing

- **Checks:** Were items **fired** (not just added to a draft)? Is the channel paused?
  Is the KDS screen connected to the branch (live updates)?
- **Resolution:** Fire the items / resume the channel. Refresh the KDS. Fire-once means
  re-firing will not double-cook, so it is safe to re-fire if in doubt.
- **Bundle:** if fired items never reach a healthy KDS, pull a bundle.

## Printer not printing

- **Checks:** Is it the **network** receipt printer (Bluetooth printers are not
  supported)? Powered, on the LAN, reachable? Correct printer selected in POS?
- **Resolution:** Reconnect/power-cycle the printer; re-select it. Confirm cabling to
  the cash drawer if the drawer also fails to kick.
- **Bundle:** if the printer is reachable but never prints, pull a bundle. See
  `HARDWARE-COMPATIBILITY.md`.

## Order won't sync

- **Checks:** Is WAN down (Cloud needs it; Edge keeps selling on the LAN)? Are there
  dead-letter events in the outbox?
- **Resolution:** On **Edge**, keep selling — orders queue on the LAN and sync when
  WAN returns. On **Cloud**, a WAN outage stops the branch; restore connectivity.
  Dead-letter outbox events are surfaced by the go-live validator for a manager/partner
  to retry.
- **Bundle:** if orders do not sync after WAN is confirmed up, pull a bundle.

## WAN down on Edge (keep selling)

- **This is expected to survive on Edge.** The LAN keeps taking orders, firing the
  kitchen, and printing. Only online-only steps pause: online payment, aggregator
  callbacks, cross-branch reporting.
- **Resolution:** Take cash/manual/terminal payments; online resumes automatically
  when WAN returns. On **Cloud**, WAN is required — there is no LAN-only mode.

## Go-live check failing

- **Checks:** Run `POST /mezze/api/v1/admin/golive` with your profile and read the
  **Fail** lines — each says exactly what is missing (e.g. "you chose Delivery but
  configured no zone", "cash method missing a journal").
- **Resolution:** Fix each Fail in its Admin Console screen and re-run until overall is
  not Fail. **NOT TESTED** items (physical hardware/host facts) are honest and are
  never forced to Pass — they are certified on-site, not in software.
- **Bundle:** attach a bundle when asking Mezze to review a stubborn Fail.
