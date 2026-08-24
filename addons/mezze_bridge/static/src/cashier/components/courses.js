/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/** Courses for a table — what has gone to the kitchen, and what is waiting.
 *
 *  `/courses/board|hold|fire` have worked since they were written. The only surface
 *  that reached them was `static/courses.html`, which no route serves and which reads
 *  the API token out of the URL query string — a token in a URL ends up in browser
 *  history, in the server's access log and in the `Referer` header of anything the
 *  page links to. This screen is inside the Register, so it authenticates the way
 *  every other call does and no token is ever written into a location bar.
 *
 *  The workflow is the reason courses exist at all: starters go now, mains are HELD,
 *  and the waiter fires them when the table is ready for them. A held course is not
 *  an order the kitchen has seen — that distinction is the whole feature, so the
 *  screen states it rather than relying on colour.
 */
export class CoursesScreen extends Component {
    static template = "mezze_bridge.CoursesScreen";
    static props = {
        api: Object,
        tableId: { type: [Number, { value: null }], optional: true },
        cartLines: { type: Array, optional: true },
        onFired: Function,
        onClose: Function,
    };

    setup() {
        this.state = useState({
            loading: true,
            error: "",
            busy: false,
            courses: [],
            tableNumber: null,
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const r = await this.props.api.call("/courses/board", {
                table_id: this.props.tableId,
            });
            if (r && r.ok) {
                this.state.courses = r.courses || [];
                this.state.tableNumber = r.table_number;
            } else {
                this.state.error = (r && r.message) || _t("Could not read the courses.");
            }
        } catch (e) {
            this.state.error = _t("Could not reach the server. Try again in a moment.");
        }
        this.state.loading = false;
    }

    /** The next free course number, so a waiter never has to think about ordering. */
    get nextSeq() {
        const used = this.state.courses.map((c) => c.seq || 0);
        return (used.length ? Math.max(...used) : 0) + 1;
    }

    get canHold() {
        return !!(this.props.cartLines || []).length && !this.state.busy;
    }

    /** Stage what is in the cart as a course, instead of sending it now. */
    async hold() {
        if (!this.canHold) {
            return;
        }
        this.state.busy = true;
        this.state.error = "";
        try {
            const seq = this.nextSeq;
            const r = await this.props.api.call("/courses/hold", {
                table_id: this.props.tableId,
                seq,
                name: _t("Course %s", seq),
                lines: (this.props.cartLines || []).map((l) => ({
                    product_id: l.product.id,
                    qty: l.qty,
                    note: l.note || "",
                })),
            });
            if (r && r.ok) {
                await this.load();
            } else {
                this.state.error = (r && r.message) || _t("That course could not be held.");
            }
        } catch (e) {
            this.state.error = _t("That course could not be held.");
        } finally {
            this.state.busy = false;
        }
    }

    /** Send a held course to the kitchen. */
    async fire(course) {
        if (this.state.busy || !course.held) {
            return;
        }
        this.state.busy = true;
        this.state.error = "";
        try {
            const r = await this.props.api.call("/courses/fire", {
                table_id: this.props.tableId,
                seq: course.seq,
            });
            if (r && r.ok) {
                await this.load();
                this.props.onFired(course);
            } else {
                this.state.error = (r && r.message) || _t("That course could not be fired.");
            }
        } catch (e) {
            this.state.error = _t("That course could not be fired.");
        } finally {
            this.state.busy = false;
        }
    }

    /** Where a course has got to, in words. A colour alone does not tell a waiter
     *  whether the kitchen has even seen it. */
    stateLabel(course) {
        if (course.held) {
            return _t("Waiting — the kitchen has not seen this yet");
        }
        return {
            preparing: _t("Being made"),
            ready: _t("Ready to run"),
            served: _t("Served"),
        }[course.state] || _t("Sent");
    }

    // ---- labels ----
    get title() {
        return this.state.tableNumber
            ? _t("Courses · table %s", this.state.tableNumber)
            : _t("Courses");
    }
    get holdLabel() { return _t("Hold as next course"); }
    get fireLabel() { return _t("Fire"); }
    get closeLabel() { return _t("Done"); }
    get emptyLabel() { return _t("Nothing has been sent or held for this table yet."); }
    get holdHint() {
        return _t("Holding keeps these items off the kitchen's board until you fire them.");
    }
}
