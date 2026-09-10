/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { icon } from "../../shell/icons";

/** Manager approval for an order action (comp, void, refund, exchange).
 *
 *  The PIN is verified SERVER-side at /w1/approve, which checks the code, the PIN
 *  and the role rank and then mints a short-lived signed token for exactly one
 *  action. Nothing here decides whether the approval is valid — the component only
 *  collects the credential and hands back the token the server minted. A cashier
 *  cannot self-approve, because the server compares the approver's role, not this
 *  form's opinion of it.
 *
 *  It deliberately does NOT reuse the payment screen's manager prompt: that path is
 *  certified money-handling code, and threading a second caller through it to save
 *  a small form would put tender approval at risk for no user-visible gain.
 */
export class ManagerGate extends Component {
    static template = "mezze_bridge.ManagerGate";
    static props = {
        action: String,                              // 'comp' | 'void' | 'refund' | 'exchange'
        heading: String,
        detail: { type: String, optional: true },    // what is being approved, in words
        reasonRequired: { type: Boolean, optional: true },
        api: Object,
        configId: { type: [Number, { value: null }], optional: true },
        onApproved: Function,                        // ({ token, reason }) => …
        onCancel: Function,
    };

    setup() {
        this.state = useState({ code: "", pin: "", reason: "", busy: false, error: "" });
    }

    /** SCREEN01_DIFF row 171 — the mark on the one dialog that asks for a credential. */
    /* ── SCREEN01_DIFF row 175 — the on-screen keypad ───────────────────────
     *  The design gives the approval prompt its own 3x4 pad. This is a TOUCH till:
     *  a manager walking over to approve a comp may have no keyboard in front of
     *  them at all, and the alternative is the OS soft keyboard covering the dialog
     *  they are being asked to read before approving.
     *
     *  Purely additive — the PIN field is unchanged and still takes typing, so
     *  nothing about how the credential is collected or verified moves. The pad
     *  only appends to the same state the field writes. Verification stays where it
     *  was, server-side at /w1/approve. */
    get padKeys() {
        return ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "\u232B"];
    }

    padPress(key) {
        if (!key) {
            return;
        }
        if (key === "\u232B") {
            this.set("pin", this.state.pin.slice(0, -1));
            return;
        }
        // A PIN has no sane maximum here — the server decides what is valid — but an
        // unbounded field on a pad is a way to fat-finger 40 digits into a password
        // box and not see it. 12 is well past any real PIN.
        if (this.state.pin.length < 12) {
            this.set("pin", this.state.pin + key);
        }
    }

    padKeyLabel(key) {
        return key === "\u232B" ? _t("Delete last digit") : key;
    }

    get shieldGlyph() {
        return icon("shield_person");
    }

    get canSubmit() {
        return !!this.state.code.trim() && !!this.state.pin.trim() && !this.state.busy
            && (!this.props.reasonRequired || !!this.state.reason.trim());
    }

    set(field, value) {
        this.state[field] = value;
        this.state.error = "";
    }

    /** The credential goes STRAIGHT to the action, which verifies it server-side.
     *
     *  It used to mint a token at /w1/approve first, which looked tidier and could
     *  never work: that route requires ADMIN_SETTINGS and a till principal does not
     *  hold it, so every approval came back 403 regardless of how correct the PIN
     *  was. Nothing is verified here — the code and PIN are handed to the endpoint
     *  that performs the action, exactly as the payment path does.
     */
    async submit() {
        if (!this.canSubmit) {
            return;
        }
        this.state.busy = true;
        this.state.error = "";
        try {
            await this.props.onApproved({
                managerCode: this.state.code.trim(),
                managerPin: this.state.pin.trim(),
                reason: this.state.reason.trim(),
            });
        } catch (e) {
            this.state.error = this.explain(e);
        } finally {
            this.state.busy = false;
        }
    }

    /** Say which thing went wrong. Reporting a capability refusal as a bad PIN
     *  sends a manager off to re-type a PIN that was never the problem. */
    explain(e) {
        const code = (e && (e.error || (e.data && e.data.error))) || "";
        if (code === "insufficient_role") {
            return _t("That role is not allowed to approve this.");
        }
        if (code === "manager_required") {
            return _t("A supervisor or manager must approve this.");
        }
        if (code === "permission_denied") {
            return _t("This terminal is not allowed to perform that action.");
        }
        if (code === "bad_credentials" || code === "approval_required") {
            return this.badCredentialsLabel;
        }
        return (e && e.message) || _t("That action did not go through.");
    }

    onKey(ev) {
        if (ev.key === "Enter") {
            this.submit();
        } else if (ev.key === "Escape") {
            this.props.onCancel();
        }
    }

    // ---- labels ----
    get codeLabel() {
        return _t("Manager code");
    }

    get pinLabel() {
        return _t("PIN");
    }

    get reasonLabel() {
        return this.props.reasonRequired ? _t("Reason (required)") : _t("Reason");
    }

    get approveLabel() {
        return _t("Approve");
    }

    get cancelLabel() {
        return _t("Cancel");
    }

    get badCredentialsLabel() {
        return _t("That code and PIN were not accepted.");
    }
}
