# Device platform

Screen **32 Devices** now has two tabs: **Fleet** and **Peripherals**. Peripherals is the old
screen, unchanged — scale, scanner, card reader, drawer, printer, CFD, with a test per device.
Fleet is the new one, and it answers a different question.

A fleet view is not a list of serials. It answers: **can this branch trade tonight?**

Branch: **Cairo Festival City**.

---

## The seven devices

| Device | What it is | Platform |
|---|---|---|
| `POS-01` | Front counter till | Elo I-Series 4 · Windows 11 IoT |
| `POS-02` | Second till, window side | Elo I-Series 4 · Windows 11 IoT |
| `KDS-GRILL` | Grill station screen | ProDVX 21" · Android 13 |
| `KDS-BAR` | Bar and shisha screen | ProDVX 21" · Android 13 |
| `WAITER-04` | Handheld, floor pool | Sunmi V2s Plus · Android 11 |
| `KIOSK-01` | Self-order kiosk, entrance | Elo 22" kiosk · Windows 11 IoT |
| `CFD-01` | Customer display on POS-01 | Elo 10" second screen · firmware |

## States are conditions, not a status field

The eight states the brief names are **not** mutually exclusive, and modelling them as one enum is
what makes most fleet screens useless. `KDS-GRILL` is online *and* has a printer error *and* is low
on storage. So each device carries a list of conditions, and the screen shows the most severe as its
headline state with the rest as chips:

| State | What it actually means |
|---|---|
| **Online** | reachable, nothing outstanding |
| **Offline** | not reachable — anything it took is held on the device |
| **Syncing** | catching up after a drop, sending in the order taken |
| **Update available** | behind the branch baseline (19.0.3) |
| **Printer error** | a station printer is not answering; tickets went to the fallback |
| **License warning** | seat expires inside 30 days; at expiry it trades but cannot re-activate |
| **Low storage** | under 20% free — offline orders and logs fail to write first |
| **Last seen** | derived from the heartbeat, not a field |

`CFD-01` adds a ninth the brief implies: **not activated** — it displays, but the group cannot see
it, so it is not a device.

The strip above the list is the summary that matters: devices, **cannot trade** (offline, unprinted
or unpaired), **behind baseline**, and **orders held on devices** — the last being money not yet in
the branch totals.

## Device detail

Left pane selects; the middle pane is the device:

- **Software version** — current, with `→ 19.0.3` when it is behind
- **IP address** and **MAC**
- **Hardware** and **operating system**
- **Uptime** (`—` when offline)
- **Activation** — date, who activated it, activation code; or "never activated"
- **License** — validity, and which seat of how many
- **Storage** — used/total with the bar going amber at 60% and red at 80%
- **Printers** — every printer this device drives, how it is attached, and whether it answers
- **Sync queue** — count, with what it means: orders the branch has not received are not in
  today's totals until they arrive
- **Logs** — timestamped, severity-coloured, newest first; actions taken here append to it
- **What needs attention** — every outstanding condition with its consequence and the one action
  that resolves it

## Actions that refuse

- **Request restart** — refused on an offline device (it has to happen at the device or on the
  power, and the held orders are named); deferred on a till with an open drawer (it restarts at the
  session close so no sale is mid-flight).
- **Request update** — always deferred to the session close, never mid-service. Already-current
  devices say so instead of pretending to queue.
- **Push the queue** — refused when offline: the queue is on the device, not on the server.
- **Activate** — pairs the device to the branch, after which it appears in the group fleet and
  takes group pushes.
- **Request renewal** — goes to the group licence pool; the device keeps trading until then.

## Odoo mapping

Devices are `pos.config` records with an IoT box, self-order client or kitchen client. Activation is
the database pairing. The licence is the enterprise seat. The sync queue is the local-first order
buffer Odoo POS already keeps — this screen reads it, it does not invent it. Restart and update are
requests **to the device**; neither writes to order data.

## Prepares the Windows Station work

`POS-01`, `POS-02` and `KIOSK-01` are Windows machines, and the fields this screen names are exactly
what a Windows station agent has to report:

- **software version** vs a branch baseline → the update channel
- **activation** (code, date, who) → machine identity and re-pairing
- **licence seat** → per-terminal entitlement, and behaviour at expiry
- **storage** → the local order buffer's headroom
- **uptime and last seen** → the heartbeat interval
- **sync queue depth** → what is unsent if the machine dies

Naming them here rather than assuming them means the later station work has a contract to build
against, not a guess. The three refusals above are the behaviours that agent must honour: no restart
with an open drawer, no update mid-service, no server-side flush of a device-side queue.

## Bilingual

Every string goes through `tr()` / `N()`. Device ids, IPs, MACs and version numbers stay Latin (they
are identifiers, not words) while everything around them translates — the same rule the rest of the
prototype uses for model numbers.

## Note on visual language

Built in the prototype's existing language (warm neutrals, Hanken Grotesk / IBM Plex Sans Arabic
with JetBrains Mono for figures, RTL-aware inline styles) for consistency with the other 47 screens,
not in the newly attached Modernist system — restyling the prototype to Modernist is a separate,
whole-app decision.
