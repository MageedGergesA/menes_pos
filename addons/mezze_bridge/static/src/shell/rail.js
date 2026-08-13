/** @odoo-module **/
import { Component, markup } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

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
    };

    get cfg() {
        return this.props.configId ? `?config_id=${this.props.configId}` : "";
    }

    get icons() {
        const g = (d) => markup('<svg viewBox="0 0 24 24" width="20" height="20" fill="none" '
            + 'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
            + 'stroke-linejoin="round">' + d + "</svg>");
        return {
            register: g('<rect x="3" y="8" width="18" height="12" rx="2"/><path d="M7 8V5h10v3M7 13h4"/>'),
            floor: g('<rect x="3" y="4" width="18" height="8" rx="2"/><path d="M7 12v8M17 12v8"/>'),
            ops: g('<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'),
            kds: g('<path d="M5 21V9m0 0a3 3 0 0 1 3-3V3m-3 6a3 3 0 0 0-3-3V3"/><path d="M15 21V3c3 0 5 3 5 7s-2 5-5 5"/>'),
            queue: g('<path d="M4 8h12v6a6 6 0 0 1-12 0z"/><path d="M16 9h2a2 2 0 0 1 0 4h-2M3 21h14"/>'),
            manager: g('<path d="M3 17l5-5 4 3 5-7"/><circle cx="18" cy="7" r="2"/>'),
            reports: g('<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h4"/>'),
            book: g('<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 11h18"/>'),
            delivery: g('<path d="M3 7h11v9H3zM14 10h4l3 3v3h-7z"/><circle cx="7" cy="18" r="1.6"/><circle cx="17" cy="18" r="1.6"/>'),
            hq: g('<path d="M4 21V8l8-5 8 5v13"/><path d="M9 21v-6h6v6"/>'),
            ck: g('<path d="M4 13h16a8 8 0 0 1-16 0z"/><path d="M12 5v3M3 21h18"/>'),
            drivethru: g('<path d="M3 17h18M5 17l1.5-5A2 2 0 0 1 8.4 10.6h7.2a2 2 0 0 1 1.9 1.4L19 17"/><circle cx="7.5" cy="19.5" r="1.5"/><circle cx="16.5" cy="19.5" r="1.5"/>'),
            settings: g('<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1"/>'),
        };
    }

    /** key, label, title, icon — plus EITHER href (a page) OR workspace (in-Register). */
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
            { key: "book", label: _t("Book"), title: _t("Reservations"), icon: i.book,
              workspace: "book" },
            { key: "delivery", label: _t("Delivery"), title: _t("Delivery"), icon: i.delivery,
              workspace: "delivery" },
            // a real page now (/mezze/drivethru), so it is a link like Floor and Kitchen
            { key: "drivethru", label: _t("Drive-thru"), title: _t("Drive-thru"),
              icon: i.drivethru, href: "/mezze/drivethru" + this.cfg },
            { key: "hq", label: _t("HQ"), title: _t("HQ"), icon: i.hq, workspace: "hq" },
            { key: "ck", label: _t("Kitchen"), title: _t("Central Kitchen"), icon: i.ck,
              workspace: "ck" },
            { key: "orders", label: _t("Orders"), title: _t("Orders"), icon: i.reports,
              workspace: "orders" },
        ].map((it) => this.resolve(it));
    }

    get footItems() {
        return [{ key: "settings", label: _t("Settings"), title: _t("Settings"),
                  icon: this.icons.settings, workspace: "settings" }].map((it) => this.resolve(it));
    }

    /** A workspace destination is a link when this surface cannot switch in place. */
    resolve(item) {
        const out = Object.assign({ active: item.key === this.props.active }, item);
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
        if (this.props.onSelect) {
            this.props.onSelect(item.workspace);
        }
    }

    get initials() {
        return String(this.props.userName || "")
            .split(/\s+/).slice(0, 2).map((w) => w.charAt(0)).join("").toUpperCase() || "?";
    }
}
