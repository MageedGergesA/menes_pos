/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { icon } from "./icons";

/** THE workspace rail — one implementation for every staff surface.
 *
 *  It used to live inside the Register, which meant walking to Floor or Kitchen threw
 *  the navigation away and stranded the operator on a page with no way back except the
 *  browser. The rail is the shell, so it belongs to the shell: Register, Floor and
 *  Kitchen all mount this same component.
 *
 *  Destinations come in two kinds. A page (Register / Floor / Kitchen) is always a real
 *  link, so a dedicated device can run just that screen. An in-Register workspace (Ops,
 *  Queue, Manager, …) calls `onSelect` when the Register is already mounted, and
 *  otherwise links to `/mezze/pos?ws=<key>` so it still works from Floor or Kitchen —
 *  the destination is reachable from everywhere, never a dead icon.
 */
export class WorkspaceRail extends Component {
    static template = "mezze_bridge.WorkspaceRail";
    static props = {
        active: { type: String, optional: true },      // register | floor | kds | <workspace key>
        configId: { type: [Number, { value: null }], optional: true },
        mark: { type: String, optional: true },         // branch initial for the logo tile
        userName: { type: String, optional: true },
        onSelect: { type: Function, optional: true },   // in-app switch (Register only)
        // Design v3 `tillBarred`: a branch can keep its Servers off the till.
        // A STAFFING policy, not a capability — the destinations still exist and
        // a cashier or manager reaches them normally.
        serversOffTill: { type: Boolean, optional: true },
        role: { type: String, optional: true },         // the signed-in person's role
        onBarred: { type: Function, optional: true },   // how the shell says no
        // Design v3: live counts beside the destinations that have a backlog, so
        // the rail reports the branch rather than just listing rooms in it.
        counts: { type: Object, optional: true },
    };

    /** Destinations a barred Server may not open. The design's own list: the
     *  till and everything that reads the day's money. Their own shift, the
     *  floor and the handheld stay open, which is the point of the policy. */
    static TILL_ONLY = ['register', 'orders', 'drivethru', 'close', 'ops',
                        'reports', 'hq', 'ck', 'delivery'];

    /* ── SCREEN01_DIFF row 6 — the rail collapses ────────────────────────────
     *  The design puts a toggle at the foot of the rail and drives its width from
     *  it. Ours had one width and no control.
     *
     *  Default is COLLAPSED, and that is deliberate rather than a preference: the
     *  four-column geometry this screen was converged onto is rail 48 + categories
     *  222 + catalogue 1214 + panel 436 = 1920 exactly (GAP_REGISTER §8b). An
     *  expanded rail is wider than 48, so defaulting to it would spend the
     *  catalogue's width and undo that measurement on first paint. Expanding is
     *  the operator asking for labels, and it costs the grid a column while it is
     *  open — which is the trade the design's own toggle makes.
     *
     *  Remembered per device in localStorage, like the cashier's favourites: it is
     *  a view preference for this screen, and nothing on the server has an opinion. */
    static RAIL_WIDE_KEY = "mzRailWide.v1";

    setup() {
        this.state = useState({ wide: WorkspaceRail.readWide() });
    }

    static readWide() {
        try {
            return localStorage.getItem(WorkspaceRail.RAIL_WIDE_KEY) === "1";
        } catch {
            // A till in a private window, or with site data blocked, still opens.
            return false;
        }
    }

    toggleWide() {
        this.state.wide = !this.state.wide;
        try {
            localStorage.setItem(WorkspaceRail.RAIL_WIDE_KEY, this.state.wide ? "1" : "0");
        } catch {
            // Not being able to REMEMBER the choice must never stop us honouring it.
        }
    }

    get wideToggleLabel() {
        return this.state.wide ? _t("Collapse") : _t("Expand");
    }

    get wideToggleGlyph() {
        return icon(this.state.wide ? "chevron_left" : "chevron_right");
    }

    /* ── SCREEN01_DIFF row 7 — the rail says what it is not showing ───────────
     *  The design's foot carries "N of M role-filtered". Ours filtered nothing
     *  visibly and said nothing, so a Server who could not open the till had no way
     *  to tell a branch POLICY from a broken button until they tapped it.
     *
     *  Drawn only when something is actually barred. With nothing filtered the line
     *  would be a permanent "13 of 13", which is the rail-of-noughts problem the
     *  count badges already avoid. */
    get roleFilteredNote() {
        const all = this.items.concat(this.footItems);
        const open = all.filter((i) => !i.barred).length;
        if (open === all.length) {
            return null;
        }
        return _t("%(open)s of %(all)s · role-filtered", { open, all: all.length });
    }

    /** Whether this destination is closed to the person at the rail. */
    barred(key) {
        return !!this.props.serversOffTill
            && WorkspaceRail.TILL_ONLY.indexOf(key) >= 0
            && String(this.props.role || '').toLowerCase() === 'server';
    }

    /** The count for a destination, or null when there is nothing to say.
     *  A zero is not drawn: a rail of noughts trains the eye to skip the badges,
     *  and then the one that matters is skipped too. */
    countFor(key) {
        const n = (this.props.counts || {})[key];
        return (typeof n === "number" && n > 0) ? n : null;
    }

    get cfg() {
        return this.props.configId ? `?config_id=${this.props.configId}` : "";
    }

    /* ── SCREEN01_DIFF row 3 — Material Symbols, not hand-drawn SVG ──────────
     *  `domain-docs/MEZZE_DESIGN_SYSTEM.md` rules this out by name: "Icons —
     *  Material Symbols only, never emoji, never custom SVG icon sets". The rail
     *  shipped fifteen bespoke 24px line drawings, which is a second icon language
     *  living beside the one the design specifies.
     *
     *  Addressed by CODEPOINT, never by ligature: the subsetter strips GSUB, so
     *  `<span class="ms">skillet</span>` renders the literal word "skillet" on the
     *  control. `icon()` returns the codepoint and `test_icon_subset` fails the
     *  build if any name here is missing from the shipped .woff2. */
    get icons() {
        return {
            register: icon("point_of_sale"),
            floor: icon("table_restaurant"),
            ops: icon("insights"),
            kds: icon("skillet"),
            queue: icon("liquor"),
            manager: icon("manage_accounts"),
            reports: icon("summarize"),
            tips: icon("payments"),
            book: icon("calendar_month"),
            delivery: icon("delivery_dining"),
            drivethru: icon("directions_car"),
            hq: icon("apartment"),
            ck: icon("soup_kitchen"),
            orders: icon("receipt_long"),
            close: icon("nights_stay"),
            settings: icon("settings"),
            lock: icon("lock"),
        };
    }

    /** key, label, title, icon — plus EITHER href (a page) OR workspace (in-Register). */
    /** RAIL-01 — the accessible name must CONTAIN the visible one (WCAG 2.5.3).
     *
     *  The rail has always carried both a short `label` and a longer `title`, and
     *  the template put the title on `aria-label` — which REPLACED the visible word
     *  rather than describing it. While the labels were hidden that was invisible;
     *  now that they are on screen it means a cashier reads "Book" and voice
     *  control hears "Reservations", and the two never meet.
     *
     *  Nothing is renamed here. Where the two already agree the name is just the
     *  label; where they differ the visible word leads and the fuller name follows.
     */
    accessibleName(item) {
        const label = (item.label || "").trim();
        const title = (item.title || "").trim();
        if (!title || title === label) {
            return label || title;
        }
        return `${label} — ${title}`;
    }

    get items() {
        const i = this.icons;
        return [
            // `?ws=register` is explicit, so a branch whose landing workspace is Floor or
            // Kitchen can still get to the till from the rail instead of bouncing back.
            { key: "register", label: _t("POS"), title: _t("Point of Sale"), icon: i.register,
              href: "/mezze/pos?ws=register" },
            { key: "floor", label: _t("Floor"), title: _t("Floor"), icon: i.floor,
              href: "/mezze/floor" + this.cfg },
            { key: "ops", label: _t("Ops"), title: _t("Live Ops"), icon: i.ops, workspace: "ops" },
            { key: "kds", label: _t("Kitchen"), title: _t("Kitchen"), icon: i.kds,
              href: "/mezze/kds" + this.cfg },
            { key: "queue", label: _t("Queue"), title: _t("Beverage Queue"), icon: i.queue,
              workspace: "queue" },
            { key: "manager", label: _t("Manager"), title: _t("Manager"), icon: i.manager,
              workspace: "manager" },
            { key: "reports", label: _t("Reports"), title: _t("Reports"), icon: i.reports,
              workspace: "reports" },
            // Tips sit in the selling rail, not with End of day: a shift lead reads
            // the pool during service, and the payout is a shift decision.
            { key: "tips", label: _t("Tips"), title: _t("Tip pool"), icon: i.tips,
              workspace: "tips" },
            { key: "book", label: _t("Book"), title: _t("Reservations"), icon: i.book,
              workspace: "book" },
            { key: "delivery", label: _t("Delivery"), title: _t("Delivery"), icon: i.delivery,
              workspace: "delivery" },
            // a real page now (/mezze/drivethru), so it is a link like Floor and Kitchen
            { key: "drivethru", label: _t("Drive-thru"), title: _t("Drive-thru"),
              icon: i.drivethru, href: "/mezze/drivethru" + this.cfg },
            { key: "hq", label: _t("HQ"), title: _t("HQ"), icon: i.hq, workspace: "hq" },
            // NAV-01 — "Commissary", not "Kitchen". While the rail was icon-only this
            // destination and the KDS both carried the label "Kitchen" and nobody could
            // see the clash; with captions on screen two identical words sat six rows
            // apart. Commissary is the frozen design's own term for it
            // (`Mezze POS v3.dc.html:34354`). The route, key, model and location name
            // are untouched — this is the label only.
            { key: "ck", label: _t("Commissary"), title: _t("Commissary"), icon: i.ck,
              workspace: "ck" },
            { key: "orders", label: _t("Orders"), title: _t("Orders"), icon: i.orders,
              workspace: "orders" },
        ].map((it) => this.resolve(it));
    }

    get footItems() {
        // End of day sits DOWN HERE with Settings, not up in the selling rail: it is
        // reached once a shift, and a control that posts the day's journal entry has
        // no business next to the buttons a cashier presses hundreds of times.
        return [
            { key: "close", label: _t("End of day"), title: _t("Close the session"),
              icon: this.icons.close, workspace: "close" },
            { key: "settings", label: _t("Settings"), title: _t("Settings"),
              icon: this.icons.settings, workspace: "settings" },
        ].map((it) => this.resolve(it));
    }

    /** A workspace destination is a link when this surface cannot switch in place. */
    resolve(item) {
        const out = Object.assign({ active: item.key === this.props.active }, item);
        out.barred = this.barred(item.key);
        if (out.barred) {
            // Shown, locked, and not navigable. Hiding it would leave a person
            // wondering where the till went; the lock says the branch decided.
            out.icon = this.icons.lock;
            out.href = false;
            out.title = _t("Not on your role");
            return out;
        }
        if (item.workspace && !this.props.onSelect) {
            out.href = "/mezze/pos?ws=" + encodeURIComponent(item.workspace);
        }
        return out;
    }

    onPick(ev, item) {
        if (item.href) {
            return;   // a real link — let the browser navigate
        }
        ev.preventDefault();
        if (item.barred) {
            // Refuse rather than navigate: the design toasts by name so the
            // person knows it is a branch policy, not a broken button.
            ev.preventDefault();
            if (this.props.onBarred) {
                this.props.onBarred(
                    _t("Not on your role"),
                    _t("This branch keeps servers off the till. "
                       + "Ask a cashier or a manager."));
            }
            return;
        }
        if (this.props.onSelect) {
            this.props.onSelect(item.workspace);
        }
    }

}
