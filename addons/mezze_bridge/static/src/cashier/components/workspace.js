/** @odoo-module **/
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney } from "../order_store";
import { summaryPanels, hasSomethingToShow } from "../summary_panels";

/** A workspace opened from the rail, rendered inside the modal host.
 *
 *  Each kind reads ONE real endpoint. Nothing is drawn from a fixture: an empty
 *  queue renders as an empty queue, and an endpoint the terminal is not allowed to
 *  read renders as exactly that — naming the capability it needs — rather than as a
 *  dashboard of invented numbers.
 *
 *  Ops, Manager, Reports and HQ all require REPORTS_READ, which a till terminal
 *  deliberately does not hold (a cashier must not read manager dashboards or
 *  financial roll-ups). That is a correct authorisation boundary, not a gap, so the
 *  panel explains it and points at the back office instead of faking a screen.
 */
export class Workspace extends Component {
    static template = "mezze_bridge.Workspace";
    static props = {
        kind: String,
        api: Object,
        currency: { type: Object, optional: true },
    };

    // kind -> { path, key } — `key` is the payload field holding the rows.
    static SOURCES = {
        queue: { path: "/bds/queue", rows: "queue" },
        ck: { path: "/ck/board", rows: "requests" },
        delivery: { path: "/delivery/list", rows: "deliveries" },
        settings: { path: "/settings/effective", rows: null },
        ops: { path: "/ops/summary", rows: null },
        manager: { path: "/manager/dashboard", rows: null },
        reports: { path: "/reports/summary", rows: null, base: "/mezze/w1" },
        hq: { path: "/hq/summary", rows: null },
    };

    setup() {
        this.state = useState({ loading: true, error: null, denied: false, data: null });
        onWillStart(() => this.load());
        onWillUpdateProps((next) => {
            if (next.kind !== this.props.kind) {
                this.load(next.kind);
            }
        });
    }

    async load(kind) {
        const k = kind || this.props.kind;
        const src = Workspace.SOURCES[k];
        Object.assign(this.state, { loading: true, error: null, denied: false, data: null });
        if (!src) {
            Object.assign(this.state, { loading: false });
            return;
        }
        try {
            const opts = src.base ? { base: src.base } : undefined;
            const res = await this.props.api.call(src.path, {}, opts);
            if (res && res.ok === false) {
                // The gate answers with a reason; permission_denied is a legitimate
                // outcome for this principal, not a failure to report as an error.
                if (res.error === "permission_denied") {
                    Object.assign(this.state, { loading: false, denied: true });
                    return;
                }
                Object.assign(this.state, { loading: false, error: res.error || "failed" });
                return;
            }
            Object.assign(this.state, { loading: false, data: res || {} });
        } catch (e) {
            const code = (e && (e.error || (e.data && e.data.error))) || "";
            if (code === "permission_denied") {
                Object.assign(this.state, { loading: false, denied: true });
                return;
            }
            Object.assign(this.state, { loading: false, error: (e && e.message) || "failed" });
        }
    }

    fmt(amount) {
        return formatMoney(amount || 0, this.props.currency || { symbol: "", position: "after", decimals: 2 });
    }

    get rowsKey() {
        const src = Workspace.SOURCES[this.props.kind];
        return src && src.rows;
    }

    /** The real rows for a list-shaped workspace ([] when the endpoint says so). */
    get rows() {
        const k = this.rowsKey;
        const d = this.state.data;
        return (k && d && Array.isArray(d[k])) ? d[k] : [];
    }

    /** A readable panel for ANY summary payload — see `summary_panels`, where the
     *  derivation lives so it can be unit-tested without a browser. */
    get panels() {
        if (this.rowsKey || this.props.kind === "settings") {
            return [];
        }
        return summaryPanels(this.state.data, (v) => this.fmt(v));
    }

    get hasPanels() {
        return hasSomethingToShow(this.panels);
    }

    /** Headline counters, each read straight off the payload. */
    get stats() {
        const d = this.state.data || {};
        const k = this.props.kind;
        if (k === "queue") {
            return [
                { k: _t("In queue"), v: (d.queue || []).length },
                { k: _t("Ready for pickup"), v: (d.pickup || []).length },
            ];
        }
        if (k === "ck") {
            return [
                { k: _t("Branches"), v: (d.branches || []).length },
                { k: _t("Catalog"), v: (d.products || []).length },
                { k: _t("Requests"), v: (d.requests || []).length },
            ];
        }
        if (k === "delivery") {
            const rows = d.deliveries || [];
            return [
                { k: _t("Deliveries"), v: rows.length },
                { k: _t("Active"), v: rows.filter((r) => r.active !== false).length },
            ];
        }
        if (k === "settings") {
            const eff = d.effective || {};
            return [
                { k: _t("Settings"), v: Object.keys(eff).length },
                { k: _t("Overrides"), v: Object.keys(d.overrides || {}).length },
                { k: _t("Locked"), v: Object.keys(d.locks || {}).length },
            ];
        }
        return [];
    }

    /** Settings is a key/value surface rather than a list of records. */
    get settingRows() {
        const d = this.state.data || {};
        const eff = d.effective || {};
        const prov = d.provenance || {};
        return Object.keys(eff).sort().map((key) => ({
            key,
            value: String(eff[key]),
            scope: (prov[key] && prov[key].scope) || "",
        }));
    }

    rowTitle(row) {
        return row.name || row.code || row.tracking || row.reference
            || (row.table && String(row.table)) || ("#" + (row.id || row.order_id || ""));
    }

    rowMeta(row) {
        const bits = [];
        if (row.state) {
            bits.push(row.state);
        }
        if (row.branch) {
            bits.push(row.branch);
        }
        if (row.qty !== undefined) {
            bits.push(String(row.qty));
        }
        if (row.courier) {
            bits.push(row.courier);
        }
        return bits.join(" · ");
    }

    get deniedTitle() {
        return _t("Not available on this terminal");
    }

    /** Naming the capability is the whole point: it tells the operator WHY, and that
     *  the screen exists for someone who holds it. */
    get deniedBody() {
        return _t(
            "This workspace reads reporting data, which needs the REPORTS_READ "
            + "capability. A Register terminal is not granted it, so the figures are "
            + "not shown here rather than shown wrongly. Open it from the back office "
            + "with a manager account.");
    }

    get emptyLabel() {
        return _t("Nothing here yet.");
    }

    get loadingLabel() {
        return _t("Loading…");
    }

    get errorLabel() {
        return _t("Couldn’t load this workspace.");
    }

    get retryLabel() {
        return _t("Try again");
    }
}
