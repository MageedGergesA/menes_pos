/* Mezze CUSTOMER product configurator — the renderer, not the rules.
 *
 * Every decision about what a product asks, what a tap does, what a configuration
 * costs, what is still missing and which cart line it is comes from the canonical
 * MezzeProductConfig (design/product-config.js), the same module the Register and the
 * Drive-Thru consume. This file owns markup, layout and touch behaviour only. If you
 * find yourself computing a price or a group's cardinality here, it belongs there.
 *
 * Built for a kiosk today and deliberately surface-agnostic: it takes a host element,
 * a product, a money formatter and a translator, so QR can adopt it without a second
 * implementation. It is NOT wired into QR by this phase.
 *
 * Usage:
 *   MezzeCustomerConfig.open({
 *     product, existing, money, t, dir,
 *     onConfirm: function (chosen) { ... }, onCancel: function () { ... }
 *   });
 */
(function (global) {
    "use strict";

    var PC = global.MezzeProductConfig;

    /** Fallback English. A surface passes its own `t` so the kiosk's Arabic (or any
     *  future language) wins; these exist so the module is never wordless. */
    var TEXT = {
        back: "Back",
        required: "Required",
        chooseOne: "Choose 1",
        optional: "Optional",
        chooseUpTo: "Choose up to %s",
        included: "%s included",
        step: "%(n)s of %(total)s",
        change: "Change",
        addAnother: "Add another %s",
        itemTotal: "Item total",
        add: "Add to order",
        save: "Save changes",
        missing: "Choose %s",
        missingMore: "%(group)s — choose %(n)s more"
    };

    function esc(s) {
        return String(s === undefined || s === null ? "" : s).replace(/[&<>"]/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
        });
    }

    function fmt(tpl, vals) {
        if (typeof vals !== "object" || vals === null) {
            return String(tpl).replace("%s", vals);
        }
        return String(tpl).replace(/%\((\w+)\)s/g, function (_m, k) { return vals[k]; });
    }

    function open(opts) {
        var product = opts.product;
        var money = opts.money || function (n) { return (Math.round(n * 100) / 100).toFixed(2); };
        var t = opts.t || function (k, v) { return fmt(TEXT[k] || k, v); };
        var groups = PC.groups(product);
        var sel = PC.defaultSelection(groups);
        if (opts.existing) {
            // Reopening a line: restore exactly what the guest chose, attribute values
            // AND combo picks (including a repeated item's second unit).
            sel = Object.assign({},
                PC.selectionFrom(groups, opts.existing.attribute_value_ids || []),
                PC.comboSelectionFrom(groups, opts.existing.combo || []));
        }
        // The customer has not tried to continue yet, so nothing is "wrong" yet: no
        // red before the first interaction, which is the difference between a form
        // that helps and a form that scolds.
        var tried = false;
        // Which groups the CUSTOMER has answered — not which ones carry an implied
        // value. A meal collapses an answered component to a summary line so the whole
        // meal stays readable (McDonald's shows a meal as its parts); a group the
        // customer has not touched keeps its options in front of them, because a
        // pre-selected size that hides the other sizes is a choice made for them.
        var answered = {};
        if (opts.existing) {
            groups.forEach(function (g) {
                if (PC.selected(sel, g).length) { answered[keyOf(g)] = true; }
            });
        }
        function keyOf(g) { return g.key !== undefined ? g.key : g.line_id; }

        /** Is this component finished, i.e. can it take nothing more?
         *
         *  A choose-one group is finished the moment it is answered. A group that
         *  allows two is NOT finished at one — that is exactly where "add another"
         *  lives, and collapsing it there would hide the second helping. An optional
         *  multi-select group is never finished; there is always another extra. */
        function isSettled(g) {
            if (groups.length < 2) { return false; }        // a single question is the panel
            if (!answered[keyOf(g)]) { return false; }
            if (g.kind === "combo") {
                return g.qty_max > 1 ? PC.roomLeft(g, sel) <= 0 : PC.selected(sel, g).length > 0;
            }
            return !g.multi && PC.selected(sel, g).length > 0;
        }

        var scrim = document.createElement("div");
        scrim.className = "mzc-scrim";
        scrim.innerHTML =
            '<section class="mzc-cfg" role="dialog" aria-modal="true" aria-labelledby="mzc-title">' +
              '<div class="mzc-cfg__hd">' +
                '<button type="button" class="mzc-back" data-mzc="back"></button>' +
                '<h2 class="mzc-cfg__title" id="mzc-title"></h2>' +
              '</div>' +
              '<div class="mzc-cfg__body" data-mzc="body"></div>' +
              '<div class="mzc-cfg__foot">' +
                '<p class="mzc-warn" data-mzc="warn" role="status" aria-live="polite" hidden></p>' +
                '<div class="mzc-total">' +
                  '<span class="mzc-total__k" data-mzc="totk"></span>' +
                  '<span class="mzc-total__v" data-mzc="totv"></span>' +
                '</div>' +
                '<button type="button" class="mz-btn mz-btn--primary mzc-cta" data-mzc="cta"></button>' +
              '</div>' +
            '</section>';

        function q(name) { return scrim.querySelector('[data-mzc="' + name + '"]'); }

        q("back").setAttribute("aria-label", t("back"));
        q("back").textContent = (opts.dir === "rtl") ? "→" : "←";
        scrim.querySelector(".mzc-cfg__title").textContent = product.name || "";
        q("totk").textContent = t("itemTotal");

        /** The group's rule, said the way a customer would say it. `qty_max` and
         *  `qty_free` never reach the screen; "Choose up to 2 · 1 included" does. */
        function ruleOf(g) {
            if (g.kind === "combo") {
                if (g.qty_max > 1) {
                    var cap = t("chooseUpTo", g.qty_max);
                    return g.qty_free ? cap + " · " + t("included", g.qty_free) : cap;
                }
                return g.qty_free ? t("chooseOne") : t("optional");
            }
            if (g.multi) { return t("optional"); }
            return t("required");
        }

        /** "Double Burger", or "Fries ×2", or "Cheese · Bacon" — the component in the
         *  customer's words, from what they actually chose. */
        function chosenLabel(g) {
            var out = [];
            g.values.forEach(function (v) {
                var n = g.kind === "combo" ? PC.countOf(sel, g, v.id) : (PC.isOn(sel, g, v.id) ? 1 : 0);
                if (n > 0) { out.push(n > 1 ? (v.name + " ×" + n) : v.name); }
            });
            return out.join(" · ");
        }

        /** What this component adds to the price, so the summary is not a name with a
         *  hidden cost attached to it. */
        function chosenExtra(g) {
            return PC.extraPrice([g], sel);
        }

        function priceLabel(v) {
            // never "+0.00": an included option should read as included
            return v.price_extra ? ("+" + money(v.price_extra)) : "";
        }

        function bodyHtml() {
            var missing = tried ? PC.missingRequired(groups, sel) : [];
            return groups.map(function (g, gi) {
                var need = missing.indexOf(g) > -1;
                // "Full" only means anything where a group can hold MORE THAN ONE.
                // A choose-one group is never full: tapping another option replaces the
                // first, which is what a customer expects and what stops them having to
                // deselect before they can change their mind.
                var full = g.kind === "combo" && g.qty_max > 1 && PC.roomLeft(g, sel) <= 0;
                var opts_ = g.values.map(function (v) {
                    var n = g.kind === "combo" ? PC.countOf(sel, g, v.id) : (PC.isOn(sel, g, v.id) ? 1 : 0);
                    var on = n > 0;
                    var px = priceLabel(v);
                    // A multi-select group is a set of checkboxes; a choose-one group is
                    // a radio set. Saying so is what a screen reader needs to explain
                    // "selecting this one replaces that one".
                    var role = (g.multi || (g.kind === "combo" && g.qty_max > 1)) ? "checkbox" : "radio";
                    var button = '<button type="button" class="mzc-opt' + (on ? " mzc-opt--on" : "") +
                             (!on && full ? " mzc-opt--full" : "") + '"' +
                           ' role="' + role + '" aria-checked="' + (on ? "true" : "false") + '"' +
                           ' data-pick="' + v.id + '" data-g="' + gi + '"' +
                           (!on && full ? " disabled" : "") + '>' +
                             '<span class="mzc-opt__mark" aria-hidden="true">✓</span>' +
                             '<span class="mzc-opt__n">' + esc(v.name) + '</span>' +
                             // dir=ltr: "+USD 5.00" must keep its sign on the left even
                             // in an RTL page, where bidi reordering otherwise renders it
                             // as "USD 5.00+"
                             (px ? '<span class="mzc-opt__px" dir="ltr">' + esc(px) + "</span>" : "") +
                           "</button>";
                    // The stepper lives BESIDE the option, never inside it: a <button>
                    // nested in a <button> is invalid HTML and the parser silently drops
                    // the inner ones, which is exactly how the +/- controls vanished.
                    var stepper = (g.kind === "combo" && g.qty_max > 1 && on)
                        ? '<span class="mzc-qty">' +
                            '<button type="button" class="mzc-qty__btn" data-dec="' + v.id + '" data-g="' + gi + '" aria-label="' + esc(t("less") || "-") + '">−</button>' +
                            '<span class="mzc-qty__n" aria-live="polite">' + n + '</span>' +
                            '<button type="button" class="mzc-qty__btn" data-inc="' + v.id + '" data-g="' + gi + '"' +
                              (full ? " disabled" : "") + ' aria-label="' + esc(t("more") || "+") + '">+</button>' +
                          '</span>'
                        : "";
                    return '<div class="mzc-optwrap' + (stepper ? " mzc-optwrap--qty" : "") + '">' +
                           button + stepper + "</div>";
                }).join("");
                // A set of radios belongs in a radiogroup: that is what tells assistive
                // technology "these are alternatives", which is the whole point of a
                // choose-one question.
                var single = (g.kind === "combo") ? g.qty_max === 1 : !g.multi;
                // On a long configuration the customer loses track of how much is left.
                // Four questions is where a list stops being glanceable.
                var step = groups.length >= 4
                    ? '<span class="mzc-group__n">' +
                        esc(t("step", { n: gi + 1, total: groups.length })) + "</span>"
                    : "";
                var settled = isSettled(g);
                // The component, once chosen: what it is, what was picked, what it
                // added, and one way to change THAT part without rebuilding the meal.
                var summary = settled
                    ? '<div class="mzc-chosen">' +
                        '<span class="mzc-chosen__n">' + esc(chosenLabel(g)) + "</span>" +
                        (chosenExtra(g) ? '<span class="mzc-chosen__px" dir="ltr">+' +
                           esc(money(chosenExtra(g))) + "</span>" : "") +
                        '<button type="button" class="mzc-change" data-change="' + gi + '">' +
                          esc(t("change")) + "</button>" +
                      "</div>"
                    : "";
                return '<div class="mzc-group' + (need ? " mzc-group--need" : "") +
                         (settled ? " mzc-group--done" : "") + '" data-group="' + gi + '"' +
                       ' role="' + (single ? "radiogroup" : "group") + '" aria-labelledby="mzc-g' + gi + '">' +
                         '<div class="mzc-group__hd">' +
                           '<h3 class="mzc-group__q" id="mzc-g' + gi + '">' + esc(g.attribute) + "</h3>" +
                           (settled ? "" : '<span class="mzc-group__rule">' + esc(ruleOf(g)) + "</span>") +
                           step +
                         "</div>" +
                         (settled ? summary :
                           '<div class="mzc-opts' +
                             ((g.kind === "combo" && g.qty_max > 1) ? " mzc-opts--qty" : "") +
                           '">' + opts_ + "</div>") +
                       "</div>";
            }).join("");
        }

        function heroHtml() {
            if (opts.imageUrl) {
                return '<img class="mzc-hero" src="' + esc(opts.imageUrl) + '" alt="">';
            }
            return '<div class="mzc-hero mzc-hero--none" aria-hidden="true">' +
                   esc(opts.emoji || "🍽️") + "</div>";
        }

        function total() {
            return (product.list_price || 0) + PC.extraPrice(groups, sel);
        }

        function render(keepScroll) {
            var body = q("body");
            var top = keepScroll ? body.scrollTop : 0;
            body.innerHTML = heroHtml() +
                (opts.description ? '<p class="mzc-desc">' + esc(opts.description) + "</p>" : "") +
                bodyHtml();
            body.scrollTop = top;
            q("totv").textContent = money(total());
            q("cta").textContent = (opts.existing ? t("save") : t("add")) + " · " + money(total());
            var missing = PC.missingRequired(groups, sel);
            if (tried && missing.length) {
                q("warn").hidden = false;
                q("warn").textContent = warnFor(missing[0]);
            } else {
                q("warn").hidden = true;
            }
        }

        function warnFor(g) {
            if (g.kind === "combo") {
                var short = g.qty_free - PC.selected(sel, g).length;
                if (short > 1) {
                    return t("missingMore", { group: g.attribute, n: short });
                }
                // A combo group is usually already phrased as the question ("Choose
                // your burger"), and "Choose Choose your burger" is a sentence only a
                // template writes. But a group called "Sides" is a noun and needs the
                // verb, so the instruction is added only when it is missing.
                var verb = t("missing", "").trim();
                var name = String(g.attribute || "");
                if (verb && name.toLowerCase().indexOf(verb.toLowerCase()) > -1) {
                    return name;     // it already tells the customer what to do
                }
                return t("missing", name);
            }
            return t("missing", g.attribute);
        }

        // A radiogroup is expected to answer arrow keys, and a kiosk with a keyboard
        // (or an assistive switch) is the case where that matters most.
        q("body").addEventListener("keydown", function (ev) {
            if (["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].indexOf(ev.key) < 0) {
                return;
            }
            var here = ev.target.closest && ev.target.closest("[data-pick]");
            if (!here) { return; }
            var groupEl = here.closest("[data-group]");
            if (!groupEl || groupEl.getAttribute("role") !== "radiogroup") { return; }
            var pickable = Array.prototype.slice.call(
                groupEl.querySelectorAll("[data-pick]:not([disabled])"));
            var i = pickable.indexOf(here);
            if (i < 0) { return; }
            ev.preventDefault();
            var fwd = (ev.key === "ArrowRight" || ev.key === "ArrowDown");
            var next = pickable[(i + (fwd ? 1 : -1) + pickable.length) % pickable.length];
            var g = groups[+next.dataset.g];
            sel = PC.toggle(g, +next.dataset.pick, sel);
            answered[keyOf(g)] = PC.selected(sel, g).length > 0;
            render(true);
            // the DOM was rebuilt: find the same option again and keep the focus on it
            var target = scrim.querySelector('[data-pick="' + next.dataset.pick +
                                             '"][data-g="' + next.dataset.g + '"]');
            if (target) { target.focus(); }
        });

        q("body").addEventListener("click", function (ev) {
            var inc = ev.target.closest("[data-inc]");
            var dec = ev.target.closest("[data-dec]");
            var pick = ev.target.closest("[data-pick]");
            var g, id;
            if (inc) {
                g = groups[+inc.dataset.g]; id = +inc.dataset.inc;
                if (PC.roomLeft(g, sel) > 0) { sel = PC.toggle(g, id, sel); }
                answered[keyOf(g)] = true;
                return render(true);
            }
            if (dec) {
                g = groups[+dec.dataset.g]; id = +dec.dataset.dec;
                var cur = PC.selected(sel, g).slice();
                cur.splice(cur.indexOf(id), 1);            // one unit off, not the lot
                sel = Object.assign({}, sel); sel[keyOf(g)] = cur;
                answered[keyOf(g)] = cur.length > 0;
                return render(true);
            }
            var change = ev.target.closest("[data-change]");
            if (change) {
                // "Change" reopens ONE component. Nothing else in the meal moves.
                g = groups[+change.dataset.change];
                answered[keyOf(g)] = false;
                render(true);
                var reopened = scrim.querySelector('[data-group="' + change.dataset.change + '"] .mzc-opt');
                if (reopened) { reopened.focus({ preventScroll: true }); }
                return;
            }
            if (pick) {
                g = groups[+pick.dataset.g]; id = +pick.dataset.pick;
                // In a multi-quantity group a tap on an already-taken option must not
                // silently add a second one — that is what the stepper is for.
                if (g.kind === "combo" && g.qty_max > 1 && PC.countOf(sel, g, id) > 0) {
                    return;
                }
                // A customer cannot UN-choose a required single choice by tapping it
                // again: the shared toggle allows it (a cashier sometimes needs to
                // empty a group), but here it silently leaves the question unanswered
                // and the next Add is refused for a reason the customer did not cause.
                // You change a required choice by choosing another one.
                var single = (g.kind === "combo") ? g.qty_max === 1 : !g.multi;
                var required = (g.kind === "combo") ? g.qty_free > 0 : !g.multi;
                if (single && required && PC.isOn(sel, g, id)) {
                    return;
                }
                sel = PC.toggle(g, id, sel);
                answered[keyOf(g)] = PC.selected(sel, g).length > 0;
                return render(true);
            }
        });

        function close() {
            document.removeEventListener("keydown", onKey, true);
            if (scrim.parentNode) { scrim.parentNode.removeChild(scrim); }
        }

        function onKey(ev) {
            if (ev.key === "Escape") { ev.preventDefault(); cancel(); return; }
            if (ev.key !== "Tab") { return; }
            // Keep keyboard focus inside the question while it is being asked: a kiosk
            // has no browser chrome to tab away to, so escaping the dialog strands the
            // caret somewhere invisible behind the scrim.
            var focusables = scrim.querySelectorAll("button:not([disabled])");
            if (!focusables.length) { return; }
            var first = focusables[0], last = focusables[focusables.length - 1];
            if (!ev.shiftKey && document.activeElement === last) {
                ev.preventDefault(); first.focus();
            } else if (ev.shiftKey && document.activeElement === first) {
                ev.preventDefault(); last.focus();
            }
        }

        function cancel() {
            close();
            if (opts.onCancel) { opts.onCancel(); }
        }

        q("back").onclick = cancel;
        scrim.addEventListener("click", function (ev) {
            if (ev.target === scrim) { cancel(); }
        });

        q("cta").onclick = function () {
            var missing = PC.missingRequired(groups, sel);
            if (missing.length) {
                // Take the customer TO the question rather than telling them a question
                // exists somewhere above.
                tried = true;
                answered[keyOf(missing[0])] = false;   // show the question, not a summary
                render(true);
                var gi = groups.indexOf(missing[0]);
                var el = scrim.querySelector('[data-group="' + gi + '"]');
                if (el) { el.scrollIntoView({ block: "start", behavior: "smooth" }); }
                var first = el && el.querySelector(".mzc-opt:not([disabled])");
                if (first) { first.focus(); }
                return;
            }
            var chosen = PC.chosen(groups, sel);
            close();
            opts.onConfirm({
                attribute_value_ids: chosen.ids,
                names: chosen.names,
                combo: chosen.combo,
                price_extra: PC.extraPrice(groups, sel),
                key: PC.lineKey(product.id, chosen.ids, "", chosen.combo)
            });
        };

        document.addEventListener("keydown", onKey, true);
        (opts.host || document.body).appendChild(scrim);
        render(false);
        // Focus the PANEL, not the first option: a focus ring sitting on "Classic
        // Burger" reads as a choice already made, and the customer either accepts it
        // by accident or has to work out that they haven't chosen anything yet.
        var panel = scrim.querySelector(".mzc-cfg");
        panel.setAttribute("tabindex", "-1");
        panel.focus({ preventScroll: true });
        return { close: close, el: scrim };
    }

    /** Does this product ask the customer anything at all? A product that asks nothing
     *  must stay ONE TAP — opening a panel to press Add is a tax on every simple item. */
    function isConfigurable(product) {
        return PC.isConfigurable(product);
    }

    global.MezzeCustomerConfig = Object.freeze({
        open: open,
        isConfigurable: isConfigurable,
        TEXT: TEXT
    });
})(window);
