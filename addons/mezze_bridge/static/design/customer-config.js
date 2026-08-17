/* Mezze CUSTOMER product configurator — Kiosk V2 presentation.
 *
 * The approved design (Claude Design "Mezze Kiosk v2") presents a configurable product
 * as a MEAL SUMMARY — one line per component, each with its chosen value and a way to
 * change that one part — and opens a FOCUSED CHOICE screen for the component being
 * changed. This file renders those two screens. It decides nothing else.
 *
 * Every rule still comes from the canonical MezzeProductConfig
 * (design/product-config.js), the same module the Register and the Drive-Thru consume:
 * which groups a product has, what a tap does, what a configuration costs, what is
 * still missing, and which cart line it is. If you find yourself computing a price or a
 * group's cardinality here, it belongs there.
 *
 * Surface-agnostic on purpose — it takes a product, a money formatter, a translator and
 * a direction — so QR can adopt the same customer configurator. It is NOT wired into QR
 * by this phase.
 */
(function (global) {
    "use strict";

    var PC = global.MezzeProductConfig;

    var TEXT = {
        yourMeal: "Your meal",
        back: "Back",
        change: "Change",
        choose: "Choose",
        notChosen: "Not chosen yet",
        required: "Required",
        optional: "Optional",
        chooseOne: "Choose one",
        chooseUpTo: "Choose up to %s",
        included: "%s included",
        includedOne: "Included",
        eachAfter: "Each extra %(group)s adds %(price)s",
        addToOrder: "Add to order",
        saveChanges: "Save changes",
        continue_: "Continue",
        add: "Add",
        less: "Decrease quantity",
        more: "Increase quantity",
        quantity: "Quantity",
        chooseYour: "Choose your %s"
    };

    function esc(s) {
        return String(s === undefined || s === null ? "" : s).replace(/[&<>"]/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
        });
    }

    function keyOf(g) { return g.key !== undefined ? g.key : g.line_id; }

    var I_CHECK = '<svg viewBox="0 0 24 24" class="k-i"><path d="M20 6 9 17l-5-5"/></svg>';
    /* A component shows what it IS, the way the approved design does — a grill, a cup,
       a bowl — chosen from the name the branch already wrote for that group. It falls
       back to a plate, never to a guess about the food. */
    var GLYPH = [
        [/grill|bbq|kebab|مشو/i, '<path d="M4 4h16l-2 8H6zM8 12l-2 8M16 12l2 8M9 20h6"/>'],
        [/burger|sandwich|برجر/i, '<path d="M4 9a8 8 0 0 1 16 0zM3 13h18M4 17h16a0 0 0 0 1 0 0 3 3 0 0 1-3 3H7a3 3 0 0 1-3-3z"/>'],
        [/side|fries|جانب/i, '<path d="M8 9h8l-1 11H9zM8 9l1-5h6l1 5"/>'],
        [/drink|juice|soda|مشروب/i, '<path d="M6 3h12l-2 8v9H8v-9zM6 7h12"/>'],
        [/dessert|sweet|حلو/i, '<path d="M5 21h14M6 17h12l-1-4H7zM12 13V8M9 8a3 3 0 1 1 6 0"/>'],
        [/sauce|dip|صوص/i, '<path d="M3 11h18a9 9 0 0 1-18 0zM7 7c0-2 2-2 2-4"/>'],
        [/size|حجم/i, '<path d="M4 12h16M4 12l4-4M4 12l4 4M20 12l-4-4M20 12l-4 4"/>'],
        [/extra|topping|إضاف/i, '<path d="M12 5v14M5 12h14"/>']
    ];
    function glyphFor(name) {
        for (var i = 0; i < GLYPH.length; i++) {
            if (GLYPH[i][0].test(String(name || ""))) {
                return '<svg viewBox="0 0 24 24" class="k-i">' + GLYPH[i][1] + "</svg>";
            }
        }
        return '<svg viewBox="0 0 24 24" class="k-i"><path d="M4 8h16v3a7 7 0 0 1-14 0zM4 19h16"/></svg>';
    }
    var I_WARN = '<svg viewBox="0 0 24 24" class="k-i"><path d="M12 8v5m0 4h.01M10.3 3.3 1.8 19a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.3a2 2 0 0 0-3.4 0z"/></svg>';
    var I_DOT = '<svg viewBox="0 0 24 24" class="k-i"><circle cx="12" cy="12" r="8"/></svg>';

    /** Open a configurator over a product. Returns a controller the host screen renders
     *  and forwards clicks to: the host owns the shell, this owns the two screens. */
    function open(opts) {
        var product = opts.product;
        var money = opts.money || function (n) { return String(n); };
        var intf = opts.int || function (n) { return String(n); };
        var t = opts.t || function (k) { return TEXT[k] || k; };
        var groups = PC.groups(product);
        var sel = opts.existing
            ? Object.assign({},
                PC.selectionFrom(groups, opts.existing.attribute_value_ids || []),
                PC.comboSelectionFrom(groups, opts.existing.combo || []))
            : PC.defaultSelection(groups);
        var qty = (opts.existing && opts.existing.qty) || 1;
        var focus = null;      // index of the group being changed, null on the meal
        var tried = false;     // has the customer tried to continue?

        function ruleOf(g) {
            if (g.kind === "combo") {
                if (g.qty_max > 1) {
                    var cap = t("chooseUpTo", g.qty_max);
                    return g.qty_free ? cap + " · " + t("included", g.qty_free) : cap;
                }
                return g.qty_free ? t("chooseOne") : t("optional");
            }
            return g.multi ? t("optional") : t("required");
        }

        /** The extra-item sentence, only where one exists: a group that can take more
         *  than it includes charges the group's own base price for the extra. */
        function extraSentence(g) {
            if (g.kind !== "combo" || g.qty_max <= 1 || !g.base_price) { return ""; }
            return t("eachAfter", { group: shortName(g), price: money(g.base_price) });
        }

        /** "Choose your side" -> "side". The branch writes the group name; this only
         *  trims the instruction off the front so it reads mid-sentence. */
        function shortName(g) {
            var n = String(g.attribute || "");
            // Not anchored: a branch may prefix its group names ("K Choose your side"),
            // and the useful half is whatever follows the instruction.
            var m = n.match(/(?:choose|pick|select)\s+(?:your\s+)?(.+)$/i);
            return (m ? m[1] : n);
        }

        /** Does the group name already tell the customer what to do? Then it IS the
         *  instruction, and "Choose your Choose your burger" is a sentence only a
         *  template writes. */
        function hasInstruction(g) {
            return /(choose|pick|select)/i.test(String(g.attribute || ""));
        }

        function chosenNames(g) {
            var out = [];
            g.values.forEach(function (v) {
                var n = g.kind === "combo" ? PC.countOf(sel, g, v.id)
                                           : (PC.isOn(sel, g, v.id) ? 1 : 0);
                if (n > 0) { out.push(n > 1 ? (v.name + " ×" + intf(n)) : v.name); }
            });
            return out;
        }

        function isAnswered(g) {
            return PC.selected(sel, g).length > 0 && PC.missingRequired([g], sel).length === 0;
        }

        function unitTotal() {
            return (product.list_price || 0) + PC.extraPrice(groups, sel);
        }

        function heroHtml(cls) {
            if (opts.imageUrl) {
                return '<img class="k-shot ' + cls + '" src="' + esc(opts.imageUrl) + '" alt="">';
            }
            return '<span class="k-shot k-shot--none ' + cls + '" aria-hidden="true">' +
                     (opts.glyph || "") +
                     '<span class="k-shot__t">' + esc(product.name) + '</span>' +
                   '</span>';
        }

        /* ---- MEAL SUMMARY -------------------------------------------------- */
        function mealHtml() {
            var comps = groups.map(function (g, gi) {
                var done = isAnswered(g);
                var need = tried && PC.missingRequired([g], sel).length > 0;
                var value = done ? chosenNames(g).join(" · ") : t("notChosen");
                var rule = done ? (extraSentence(g) || ruleOf(g)) : ruleOf(g);
                return '<button type="button" class="k-comp' +
                         (done ? " k-comp--done" : "") + (need ? " k-comp--need" : "") +
                       '" data-open="' + gi + '">' +
                         '<span class="k-comp__ic" aria-hidden="true">' +
                           (need ? I_WARN : glyphFor(g.attribute)) + '</span>' +
                         (done ? '<span class="k-comp__ok" aria-hidden="true">' + I_CHECK + '</span>' : "") +
                         '<span class="k-comp__body">' +
                           '<span class="k-comp__label">' + esc(g.attribute) + '</span>' +
                           '<span class="k-comp__value">' + esc(value) + '</span>' +
                           '<span class="k-comp__rule">' + esc(rule) + '</span>' +
                         '</span>' +
                         '<span class="k-comp__cta">' + esc(done ? t("change") : t("choose")) +
                           '<span class="k-chev" aria-hidden="true">›</span></span>' +
                       '</button>';
            }).join("");

            return '<div class="k-detail">' +
                     heroHtml("k-shot--sq") +
                     '<div class="k-detail__head">' +
                       '<h2 class="k-detail__name">' + esc(product.name) + '</h2>' +
                       (product.description
                         ? '<p class="k-detail__desc">' + esc(product.description) + '</p>' : "") +
                       (groups.length
                         ? '<div class="k-chips">' + groups.map(function (g) {
                             return '<span class="k-chip' + (isAnswered(g) ? " k-chip--ok" : "") +
                                    '">' + I_CHECK + esc(shortName(g)) + '</span>';
                           }).join("") + '</div>'
                         : (product.tags && product.tags.length
                            ? '<div class="k-chips">' + product.tags.map(function (tg) {
                                return '<span class="k-chip">' + esc(tg) + '</span>'; }).join("") +
                              '</div>' : "")) +
                     '</div>' +
                   '</div>' +
                   (groups.length ? '<h3 class="k-sect">' + esc(t("yourMeal")) + '</h3>' +
                                    '<div class="k-comps">' + comps + '</div>' : "") +
                   '<div class="k-qtyrow">' +
                     '<span class="k-qtyrow__l">' + esc(t("quantity")) + '</span>' +
                     '<span class="mz-stepper mz-stepper--lg k-step">' +
                       '<button type="button" class="mz-stepper__btn" data-qty="-1" aria-label="' +
                         esc(t("less")) + '">−</button>' +
                       '<span class="mz-stepper__value" aria-live="polite">' + esc(intf(qty)) + '</span>' +
                       '<button type="button" class="mz-stepper__btn" data-qty="1" aria-label="' +
                         esc(t("more")) + '">+</button>' +
                     '</span>' +
                   '</div>';
        }

        /* ---- FOCUSED CHOICE ------------------------------------------------ */
        function choiceHtml() {
            var g = groups[focus];
            var multi = g.kind === "combo" && g.qty_max > 1;
            var full = multi && PC.roomLeft(g, sel) <= 0;
            var extra = extraSentence(g);
            var rows = g.values.map(function (v) {
                var n = g.kind === "combo" ? PC.countOf(sel, g, v.id)
                                           : (PC.isOn(sel, g, v.id) ? 1 : 0);
                var on = n > 0;
                var price = v.price_extra
                    ? '<span class="k-opt__px" dir="ltr">+' + esc(money(v.price_extra)) + '</span>'
                    : '<span class="k-opt__inc">' + esc(t("includedOne")) + '</span>';
                var trail = "";
                if (multi) {
                    trail = on
                        ? '<span class="mz-stepper mz-stepper--lg k-step">' +
                            '<button type="button" class="mz-stepper__btn" data-dec="' + v.id +
                              '" aria-label="' + esc(t("less")) + '">−</button>' +
                            '<span class="mz-stepper__value" aria-live="polite">' + esc(intf(n)) + '</span>' +
                            '<button type="button" class="mz-stepper__btn" data-inc="' + v.id + '"' +
                              (full ? " disabled" : "") + ' aria-label="' + esc(t("more")) + '">+</button>' +
                          '</span>'
                        : '<span class="k-opt__add' + (full ? " k-opt__add--off" : "") + '">' +
                            esc(t("add")) + '</span>';
                }
                return '<button type="button" class="k-opt' + (on ? " k-opt--on" : "") + '"' +
                       ' role="' + (multi || g.multi ? "checkbox" : "radio") + '"' +
                       ' aria-checked="' + (on ? "true" : "false") + '"' +
                       ' data-pick="' + v.id + '"' + (!on && full ? " disabled" : "") + '>' +
                         '<span class="k-opt__box" aria-hidden="true">' + I_CHECK + '</span>' +
                         '<span class="k-opt__body">' +
                           '<span class="k-opt__n">' + esc(v.name) + '</span>' + price +
                         '</span>' + trail +
                       '</button>';
            }).join("");
            return '<p class="k-rule">' + esc(ruleOf(g)) + '</p>' +
                   (extra ? '<p class="k-note"><span class="k-note__i" aria-hidden="true">i</span>' +
                            esc(extra) + '</p>' : "") +
                   '<div class="k-opts" role="' + (multi || g.multi ? "group" : "radiogroup") +
                   '" aria-label="' + esc(g.attribute) + '">' + rows + '</div>';
        }

        /* ---- the controller the host screen drives -------------------------- */
        return {
            product: product,
            groups: groups,
            isFocused: function () { return focus !== null; },
            focusedGroup: function () { return focus === null ? null : groups[focus]; },
            qty: function () { return qty; },
            title: function () {
                return focus === null ? product.name : groups[focus].attribute;
            },
            backLabel: function () { return focus === null ? t("back") : t("yourMeal"); },
            html: function () { return focus === null ? mealHtml() : choiceHtml(); },
            unit: function () { return unitTotal(); },
            total: function () { return unitTotal() * qty; },
            /** The footer's action is contextual by design: when something is missing it
             *  takes the customer TO the missing question instead of sitting disabled. */
            action: function () {
                if (focus !== null) { return { kind: "continue", label: t("continue_") }; }
                var missing = PC.missingRequired(groups, sel);
                if (missing.length) {
                    var g0 = missing[0];
                    return { kind: "goto", group: groups.indexOf(g0),
                             label: hasInstruction(g0) ? g0.attribute
                                                       : t("chooseYour", shortName(g0)) };
                }
                return { kind: "add",
                         label: (opts.existing ? t("saveChanges") : t("addToOrder")) };
            },
            /** Arrow keys inside a choose-one group — what a radiogroup is expected to
             *  answer, and the only way a keyboard or switch user moves between
             *  alternatives without tabbing through every one of them. Returns the id
             *  to focus after the host re-renders, or null when the key was not ours. */
            arrow: function (target, key) {
                if (["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].indexOf(key) < 0) {
                    return null;
                }
                var here = target && target.closest ? target.closest("[data-pick]") : null;
                if (!here || focus === null) { return null; }
                var g = groups[focus];
                var single = (g.kind === "combo") ? g.qty_max === 1 : !g.multi;
                if (!single) { return null; }
                var pickable = Array.prototype.slice.call(
                    scrim_query("[data-pick]:not([disabled])", target));
                var i = pickable.indexOf(here);
                if (i < 0) { return null; }
                var fwd = (key === "ArrowRight" || key === "ArrowDown");
                var next = pickable[(i + (fwd ? 1 : -1) + pickable.length) % pickable.length];
                var id = +next.dataset.pick;
                sel = PC.toggle(g, id, sel);
                return id;
            },

            /** One handler for both screens; true when the host should re-render. */
            handle: function (target) {
                var el = target && target.closest
                    ? target.closest("[data-open],[data-pick],[data-inc],[data-dec],[data-qty]")
                    : null;
                if (!el) { return false; }
                if (el.dataset.open !== undefined) { focus = +el.dataset.open; return true; }
                if (el.dataset.qty !== undefined) {
                    qty = Math.max(1, Math.min(99, qty + (+el.dataset.qty)));
                    return true;
                }
                var g = groups[focus];
                if (!g) { return false; }
                if (el.dataset.inc !== undefined) {
                    if (PC.roomLeft(g, sel) > 0) { sel = PC.toggle(g, +el.dataset.inc, sel); }
                    return true;
                }
                if (el.dataset.dec !== undefined) {
                    var cur = PC.selected(sel, g).slice();
                    cur.splice(cur.indexOf(+el.dataset.dec), 1);
                    sel = Object.assign({}, sel); sel[keyOf(g)] = cur;
                    return true;
                }
                if (el.dataset.pick !== undefined) {
                    var id = +el.dataset.pick;
                    var multi = g.kind === "combo" && g.qty_max > 1;
                    if (multi && PC.countOf(sel, g, id) > 0) { return false; }
                    var single = (g.kind === "combo") ? g.qty_max === 1 : !g.multi;
                    var required = (g.kind === "combo") ? g.qty_free > 0 : !g.multi;
                    // a customer cannot un-choose a required single choice by tapping it
                    // again; they change it by choosing another one, and answering it
                    // returns them to the meal, which is what the design does
                    if (single && required && PC.isOn(sel, g, id)) { focus = null; return true; }
                    sel = PC.toggle(g, id, sel);
                    if (single && required && PC.isOn(sel, g, id)) { focus = null; }
                    return true;
                }
                return false;
            },
            goto: function (gi) { tried = true; focus = gi; },
            back: function () {
                if (focus === null) { return false; }
                focus = null; return true;
            },
            /** What the host adds to the cart, or null when something is missing. */
            confirm: function () {
                var missing = PC.missingRequired(groups, sel);
                if (missing.length) {
                    tried = true; focus = groups.indexOf(missing[0]); return null;
                }
                var chosen = PC.chosen(groups, sel);
                return {
                    attribute_value_ids: chosen.ids,
                    names: chosen.names,
                    combo: chosen.combo,
                    price_extra: PC.extraPrice(groups, sel),
                    qty: qty,
                    key: PC.lineKey(product.id, chosen.ids, "", chosen.combo)
                };
            }
        };
    }

    /** The option buttons currently on screen, found from the element the customer is
     *  actually on — the host owns the container, so this never assumes one. */
    function scrim_query(sel, from) {
        var root = from && from.closest ? (from.closest("[data-screen]") || document) : document;
        return root.querySelectorAll(sel);
    }

    function isConfigurable(product) { return PC.isConfigurable(product); }

    global.MezzeCustomerConfig = Object.freeze({
        open: open,
        isConfigurable: isConfigurable,
        TEXT: TEXT
    });
})(window);
