/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/** The Settings workspace, built from the REAL settings catalogue.
 *
 *  /settings/effective returns, per key: category, type, options, range, effect,
 *  status and a human `reason`, plus provenance (scope / source / lock). Every group,
 *  label, control and badge below is derived from that payload — the category counts
 *  in the sidebar are the catalogue's own, which is why they line up with the design.
 *
 *  ONE honesty rule shapes this screen: the catalogue marks only 18 of 101 settings
 *  `working`. 76 are `disabled` ("not yet wired") and 7 `hidden`. Hidden keys are not
 *  rendered at all; disabled keys ARE shown — a settings page that quietly omitted
 *  three quarters of itself would be misleading — but read-only, with the catalogue's
 *  own reason, so a till never offers a control that does nothing.
 */
export class SettingsPanel extends Component {
    static template = "mezze_bridge.SettingsPanel";
    static props = {
        api: Object,
        onChange: { type: Function, optional: true },
        // asks for a supervisor when the branch-wide save needs one
        onElevate: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({
            loading: true,
            error: null,
            denied: false,
            catalog: {},
            effective: {},
            provenance: {},
            category: null,
            query: "",
            saving: false,
            savedKey: null,
            // Where a change lands. Device is a personal preference; Branch is the
            // look every screen shares — which is what an operator usually means
            // when they "choose a theme".
            scope: "user",
        });
        onWillStart(() => this.load());
    }

    async load() {
        Object.assign(this.state, { loading: true, error: null, denied: false });
        try {
            const r = await this.props.api.call("/settings/effective", {});
            Object.assign(this.state, {
                loading: false,
                catalog: r.catalog || {},
                effective: r.effective || {},
                provenance: r.provenance || {},
            });
            if (!this.state.category) {
                this.state.category = (this.categories[0] || {}).name || null;
            }
        } catch (e) {
            const code = (e && (e.error || (e.data && e.data.error))) || "";
            Object.assign(this.state, {
                loading: false,
                denied: code === "permission_denied",
                error: code === "permission_denied" ? null : ((e && e.message) || "failed"),
            });
        }
    }

    /** Catalogue entries that should ever be shown. `hidden` means exactly that. */
    get visibleKeys() {
        const c = this.state.catalog;
        return Object.keys(c).filter((k) => (c[k].status || "") !== "hidden");
    }

    get categories() {
        const c = this.state.catalog;
        const counts = {};
        for (const k of this.visibleKeys) {
            const cat = c[k].category || _t("Other");
            counts[cat] = (counts[cat] || 0) + 1;
        }
        return Object.keys(counts).sort().map((name) => ({ name, count: counts[name] }));
    }

    /** Rows for the selected category, filtered by the search box. */
    get rows() {
        const c = this.state.catalog;
        const q = this.state.query.trim().toLowerCase();
        return this.visibleKeys
            .filter((k) => (c[k].category || "") === this.state.category)
            .filter((k) => !q
                || k.toLowerCase().includes(q)
                || String(c[k].reason || "").toLowerCase().includes(q))
            .sort()
            .map((k) => this.row(k));
    }

    row(key) {
        const meta = this.state.catalog[key] || {};
        const prov = this.state.provenance[key] || {};
        const working = (meta.status || "") === "working";
        return {
            key,
            label: this.humanise(key),
            reason: meta.reason || "",
            type: meta.type || "bool",
            options: meta.options || [],
            range: meta.range || null,
            value: this.state.effective[key],
            scope: prov.scope || "",
            locked: (prov.lock || "free") !== "free",
            working,
            live: (meta.effect || "") === "live",
            // read-only when the catalogue says it is not wired, or the org locked it
            readonly: !working || ((prov.lock || "free") !== "free"),
        };
    }

    /** The catalogue ships keys, not labels. The leading segment is the category the
     *  row already sits under (`ac_` Accessibility, `app_` Appearance, `pg_` Product
     *  Grid …), so repeating it in every label just adds noise: `ac_contrast` reads as
     *  "Contrast", `app_dark_theme` as "Dark theme". */
    humanise(key) {
        let s = String(key);
        const cut = s.indexOf("_");
        if (cut > 0 && cut <= 4) {
            s = s.slice(cut + 1);
        }
        s = s.replace(/_/g, " ").trim();
        return s.charAt(0).toUpperCase() + s.slice(1);
    }

    /** QWeb expressions evaluate against the component, not globals — no String(). */
    same(a, b) {
        return String(a) === String(b);
    }

    isOn(row) {
        const v = row.value;
        return v === true || v === "true" || v === 1 || v === "1";
    }

    /** A short enum renders as a segmented control, a long one as a select — the
     *  design uses both, and the boundary is simply how many options there are. */
    segmented(row) {
        return row.type === "enum" && row.options.length > 0 && row.options.length <= 3;
    }

    setScope(scope) {
        this.state.scope = scope;
        this.state.error = null;
    }

    get scopeChoices() {
        return [
            { key: "user", label: _t("This device"), active: this.state.scope === "user" },
            { key: "branch", label: _t("Whole branch"), active: this.state.scope === "branch" },
        ];
    }

    async setValue(row, value) {
        if (row.readonly || this.state.saving) {
            return;
        }
        const previous = this.state.effective[row.key];
        this.state.effective[row.key] = value;   // optimistic, reverted below on reject
        this.state.saving = true;
        try {
            const res = await this.save(row.key, value);
            if (res && res.elevating) {
                return;     // a supervisor is being asked; the gate finishes the job
            }
            const rejected = (res && res.rejected) || {};
            if (Object.prototype.hasOwnProperty.call(rejected, row.key)) {
                this.state.effective[row.key] = previous;
                this.state.error = _t("%s was rejected: %s", row.label,
                                      String(rejected[row.key]));
            } else {
                this.state.savedKey = row.key;
                // `live` settings must take effect on the spot, not on next boot
                if (this.props.onChange) {
                    this.props.onChange({ [row.key]: value });
                }
                this.state.provenance[row.key] = Object.assign(
                    {}, this.state.provenance[row.key] || {}, { scope: this.state.scope });
            }
        } catch (e) {
            this.state.effective[row.key] = previous;
            this.state.error = (e && e.message) || "failed";
        } finally {
            this.state.saving = false;
        }
    }

    /** One save, two destinations. A branch save needs admin.settings, which a till
     *  does not hold, so a refusal is turned into a supervisor prompt rather than an
     *  error the cashier can do nothing about. */
    async save(key, value) {
        const values = { [key]: value };
        if (this.state.scope !== "branch") {
            return this.props.api.call("/settings/save", { values });
        }
        try {
            return await this.props.api.call("/settings/branch", { values });
        } catch (e) {
            const code = (e && (e.error || (e.data && e.data.error))) || "";
            if (code === "permission_denied" && this.props.onElevate) {
                this.props.onElevate({
                    values,
                    label: this.humanise(key),
                    apply: (credential) => this.props.api.call(
                        "/settings/branch", Object.assign({ values }, credential)),
                });
                return { elevating: true };
            }
            throw e;
        }
    }

    onToggle(row) {
        this.setValue(row, !this.isOn(row));
    }

    onPick(row, ev) {
        this.setValue(row, ev.target.value);
    }

    async resetSection() {
        if (this.state.saving) {
            return;
        }
        this.state.saving = true;
        try {
            await this.props.api.call("/settings/reset", { section: this.state.category });
            await this.load();
            if (this.props.onChange) {
                this.props.onChange(this.state.effective);
            }
        } catch (e) {
            this.state.error = (e && e.message) || "failed";
        } finally {
            this.state.saving = false;
        }
    }

    onSearch(ev) {
        this.state.query = ev.target.value;
    }

    pick(category) {
        this.state.category = category;
    }

    get overrideCount() {
        return this.visibleKeys.filter(
            (k) => ((this.state.provenance[k] || {}).scope || "default") !== "default").length;
    }

    // ---- labels ----
    get title() {
        return _t("Settings");
    }

    get applyToLabel() {
        return _t("Apply to");
    }

    get searchLabel() {
        return _t("Search settings");
    }

    get resetLabel() {
        return _t("Reset section");
    }

    get notWiredLabel() {
        return _t("Not yet wired");
    }

    get lockedLabel() {
        return _t("Org");
    }

    get liveLabel() {
        return _t("Live");
    }

    get emptyLabel() {
        return _t("No settings match that search.");
    }

    get loadingLabel() {
        return _t("Loading…");
    }

    get deniedLabel() {
        return _t("This terminal may not read settings.");
    }

    get footNote() {
        return _t("Only settings the product actually applies are editable. The rest are "
                  + "listed with the reason they are not yet wired, so nothing here "
                  + "pretends to work.");
    }
}
