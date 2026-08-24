/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/** Type a quantity, a price, or a discount onto the selected line.
 *
 *  Mezze had +/− steppers and nothing else, so "make that twelve" meant pressing +
 *  eleven times, and a price could not be entered at all — which left
 *  `restrict_price_control` guarding a door with no handle on it.
 *
 *  Three deliberate choices:
 *
 *  * the pad edits ONE line, the selected one, and says which. A pad that silently
 *    acts on "the last thing added" is one that eventually reprices the wrong dish;
 *  * digits ACCUMULATE into a pending value and are only committed on confirm, so a
 *    half-typed "1" on the way to "12" never briefly becomes a real quantity that
 *    syncs, fires, or prices;
 *  * Price is offered only when the branch allows this till to set one. A control
 *    that is present and then refused by the server teaches a cashier to distrust
 *    the screen.
 */
export class Numpad extends Component {
    static template = "mezze_bridge.Numpad";
    static props = {
        line: { type: [Object, { value: null }], optional: true },
        currency: { type: Object, optional: true },
        allowPrice: { type: Boolean, optional: true },
        // Ask the branch's scale. Passed only where the branch HAS one.
        onWeigh: { type: Function, optional: true },
        onQty: Function,
        onPrice: Function,
        onDiscount: Function,
        onClose: Function,
    };

    setup() {
        this.state = useState({ mode: "qty", buffer: "", weighing: false, weighError: "" });
    }

    /** Is this line a MEASUREMENT rather than a count?
     *
     *  The product decides, not the pad. A decimal is a typo on a burger and the
     *  whole point on cheese, and there is no way to tell those apart from the
     *  keystroke — only from what is being sold.
     */
    get weighed() {
        const l = this.props.line;
        return !!(l && l.product && l.product.to_weight);
    }

    /** The scale is offered only where there is one, and only on a line where a
     *  weight means something. A button that reports "no scale" the first time it is
     *  pressed has taught the cashier not to press it again. */
    get canWeigh() {
        return this.weighed && !!this.props.onWeigh;
    }

    /** Ask the scale, and put the answer in the BUFFER rather than on the line.
     *
     *  The scale proposes; the cashier commits. It is the same confirm as a typed
     *  weight, so there is one path onto the line and the number is read back before
     *  anything is charged for it — which matters most on the reading a cashier
     *  would never have questioned. */
    async weigh() {
        if (!this.canWeigh || this.state.weighing) {
            return;
        }
        this.state.weighing = true;
        this.state.weighError = "";
        try {
            const w = await this.props.onWeigh(this.props.line);
            if (typeof w === "number" && w > 0) {
                this.state.mode = "qty";
                this.state.buffer = String(w);
            }
        } catch (err) {
            this.state.weighError = (err && err.message) || _t("The scale did not answer.");
        } finally {
            this.state.weighing = false;
        }
    }

    get weighLabel() { return _t("Weigh"); }
    get weighingLabel() { return _t("Weighing…"); }

    get uomName() {
        const l = this.props.line;
        return (l && l.product && l.product.uom_name) || "";
    }

    get modes() {
        const out = [
            { key: "qty",
              // Named for what it is on this line. "Qty: 0.4" reads as a mistake;
              // "Weight: 0.4 kg" reads as a scale.
              label: this.weighed
                  ? (this.uomName ? _t("Weight (%s)", this.uomName) : _t("Weight"))
                  : _t("Qty") },
            { key: "disc", label: _t("Disc %") },
        ];
        if (this.props.allowPrice) {
            out.splice(1, 0, { key: "price", label: _t("Price") });
        }
        return out;
    }

    setMode(mode) {
        this.state.mode = mode;
        this.state.buffer = "";
    }

    press(key) {
        if (key === ".") {
            // A count has no decimal point — there on a burger it is a typo, not an
            // intention. On a product sold BY WEIGHT the decimal is the whole point:
            // blocking it meant 0.4 kg of cheese could not be rung up at all, which
            // is why weighed products survived the round trip and still could not be
            // sold from this till.
            const countOnly = this.state.mode === "qty" && !this.weighed;
            if (countOnly || this.state.buffer.includes(".")) {
                return;
            }
        }
        this.state.buffer += key;
    }

    backspace() {
        this.state.buffer = this.state.buffer.slice(0, -1);
    }

    clear() {
        this.state.buffer = "";
    }

    get pending() {
        return this.state.buffer === "" ? null : Number(this.state.buffer);
    }

    get canConfirm() {
        const v = this.pending;
        if (v === null || !Number.isFinite(v) || !this.props.line) {
            return false;
        }
        if (this.state.mode === "disc") {
            return v >= 0 && v <= 100;
        }
        if (this.state.mode === "qty" && !this.weighed && !Number.isInteger(v)) {
            // Belt and braces: the pad refuses the keystroke, and refuses the value
            // too, so a pasted or scripted "1.5 burgers" cannot get through either.
            return false;
        }
        return v >= 0;
    }

    confirm() {
        if (!this.canConfirm) {
            return;
        }
        const v = this.pending;
        if (this.state.mode === "qty") {
            this.props.onQty(v);
        } else if (this.state.mode === "price") {
            this.props.onPrice(v);
        } else {
            this.props.onDiscount(v);
        }
        this.state.buffer = "";
    }

    /** What the line reads NOW, so the pad shows what it is about to replace. */
    get currentLabel() {
        const l = this.props.line;
        if (!l) {
            return "";
        }
        if (this.state.mode === "qty") {
            return this.weighed && this.uomName
                ? `${l.qty} ${this.uomName}`
                : String(l.qty);
        }
        if (this.state.mode === "price") {
            return String(l.price_unit ?? "");
        }
        return String(l.discount || 0);
    }

    get title() {
        const l = this.props.line;
        return l ? l.product.name : _t("Pick a line first");
    }

    get keys() {
        return ["7", "8", "9", "4", "5", "6", "1", "2", "3", "0", "."];
    }

    // ---- labels ----
    get confirmLabel() { return _t("Apply"); }
    get closeLabel() { return _t("Done"); }
    get clearLabel() { return _t("Clear"); }
    get backspaceLabel() { return _t("Backspace"); }
    get nowLabel() { return _t("Now"); }
}
