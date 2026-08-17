/* Part of the Mezze POS platform. See LICENSE (LGPL-3).
   ===========================================================================
   CANONICAL PRODUCT CONFIGURATION — the rules, in one place
   ===========================================================================
   "No onion, extra cheese, large" is the same question wherever an operator is
   standing, so it gets ONE answer. These are the rules a Mezze surface applies
   when a guest customises a product:

     * which groups a product has                    -> groups(product)
     * what a group starts on                        -> defaultSelection(groups)
     * what a tap does                               -> toggle(group, valueId, sel)
     * what has been chosen                          -> chosen(groups, sel)
     * what it adds to the price                     -> extraPrice(groups, sel)
     * what still has to be answered                 -> missingRequired(groups, sel)
     * which cart line this IS                       -> lineKey(productId, valueIds)

   Deliberately pure: no DOM, no framework, no network, no money formatting. The
   drive-thru renders these with plain DOM and the Register renders them with Owl;
   neither owns the rules. That matters because the rules are where the mistakes
   live — merging a no-onion burger into a plain one is a wrong ORDER, not a wrong
   pixel.

   NOT an authority on price. `extraPrice` drives the live preview only; the server
   re-derives every figure from the chosen values themselves (mezze.cart.pricing and
   _build_lines), and a value that does not belong to the product's own template is
   dropped there rather than trusted.

   Loaded as a plain script so BOTH a static page (<script src>) and an asset bundle
   can consume it. It publishes one frozen global and nothing else.
   =========================================================================== */
(function (global) {
    "use strict";

    /** The configurable groups a product carries, or an empty list.
     *
     *  TWO kinds of question live here and they are deliberately one shape:
     *
     *    * an ATTRIBUTE group — "Size", "Extras" — from the product's POS-time
     *      attribute lines. Accepts either name /bootstrap ships it under:
     *      `modifiers` (the payload's) or `mods` (the drive-thru board's).
     *    * a COMBO group — "Choose your burger" — from Odoo's own
     *      `product.combo` / `product.combo.item`, shipped as `combos`.
     *
     *  A combo group is REQUIRED and single-choice because that is Odoo's rule:
     *  a combo product has exactly one pick per group, enforced server-side by
     *  `_resolve_combo`. Normalising here is what keeps the surfaces honest —
     *  one renderer, one selection model, one line identity — instead of a
     *  second combo algorithm growing beside the first.
     *
     *  Attribute groups keep `key === line_id` so every selection made before
     *  combos existed still reads back unchanged. */
    function groups(product) {
        if (!product) {
            return [];
        }
        var out = [];
        (product.modifiers || product.mods || []).forEach(function (g) {
            var copy = {};
            for (var k in g) {
                if (Object.prototype.hasOwnProperty.call(g, k)) {
                    copy[k] = g[k];
                }
            }
            copy.kind = 'attr';
            copy.key = g.line_id;
            out.push(copy);
        });
        (product.combos || []).forEach(function (c) {
            // Odoo's own cardinality (point_of_sale extends product.combo):
            //   qty_max  — how many items may be taken from this group
            //   qty_free — how many the meal's price already covers
            // Both default to 1, which is the familiar "choose one". A group with
            // qty_max > 1 is multi-select, and anything beyond qty_free costs the
            // group's base price. Treating every group as "exactly one" was right
            // only for the default and wrong for a branch that configured more.
            var qmax = (c.qty_max === undefined || c.qty_max === null) ? 1 : c.qty_max;
            var qfree = (c.qty_free === undefined || c.qty_free === null) ? 1 : c.qty_free;
            out.push({
                kind: 'combo',
                key: 'c' + c.combo_id,
                combo_id: c.combo_id,
                attribute: c.name,          // the renderers read `attribute`
                multi: qmax > 1,
                required: qfree > 0,
                min: qfree,
                max: qmax,
                qty_free: qfree,
                qty_max: qmax,
                base_price: c.base_price || 0,
                values: (c.items || []).map(function (it) {
                    return {
                        id: it.item_id,               // the id the SERVER validates
                        product_id: it.product_id,
                        name: it.name,
                        price_extra: it.extra_price || 0,
                    };
                }),
            });
        });
        return out;
    }

    function keyOf(group) {
        return (group && (group.key !== undefined ? group.key : group.line_id));
    }

    function isConfigurable(product) {
        return groups(product).length > 0;
    }

    function valuesOf(group) {
        return (group && group.values) || [];
    }

    function selected(sel, group) {
        return (sel && sel[keyOf(group)]) || [];
    }

    /** What a group starts on.
     *
     *  A single-choice group pre-selects its first value, so the ordinary order is
     *  one confirm rather than a hunt for the option that was already implied. A
     *  multi group starts empty — "extras" nobody asked for are not a default. */
    function defaultSelection(gs) {
        var sel = {};
        (gs || []).forEach(function (g) {
            // A combo group starts EMPTY on purpose: "which burger" is the question
            // the guest is being asked, and answering it for them with the first row
            // is how a wrong plate gets made. An attribute group still pre-selects
            // its implied value, which is what makes the ordinary order one confirm.
            if (g.kind === 'combo') {
                sel[keyOf(g)] = [];
            } else if (!g.multi && valuesOf(g).length) {
                sel[keyOf(g)] = [valuesOf(g)[0].id];
            }
        });
        return sel;
    }

    /** The selection an EXISTING line carries, so reopening it restores exactly what
     *  the guest asked for instead of starting over. */
    function selectionFrom(gs, valueIds) {
        var have = valueIds || [];
        var sel = {};
        (gs || []).forEach(function (g) {
            sel[keyOf(g)] = valuesOf(g)
                .filter(function (v) { return have.indexOf(v.id) > -1; })
                .map(function (v) { return v.id; });
        });
        return sel;
    }

    /** What a tap does. Multi groups toggle; a single-choice group replaces its value,
     *  and tapping the chosen one again clears it — which is how a required group can
     *  be left unanswered, and therefore how the guard below ever fires. */
    function toggle(group, valueId, sel) {
        var next = {};
        for (var k in sel) {
            if (Object.prototype.hasOwnProperty.call(sel, k)) {
                next[k] = sel[k].slice();
            }
        }
        var cur = (next[keyOf(group)] || []).slice();
        if (group.kind === 'combo' && group.qty_max > 1) {
            // One control, no stepper: a tap takes one more of this item while the
            // group has room, and clears this item once the group is full. Odoo's
            // own popup uses +/- buttons; a lane screen is tapped mid-rush, so the
            // same rule is expressed as a cycle rather than two small targets.
            var total = cur.length;
            if (total < group.qty_max) {
                cur.push(valueId);
            } else {
                cur = cur.filter(function (v) { return v !== valueId; });
            }
        } else if (group.multi) {
            var i = cur.indexOf(valueId);
            if (i > -1) {
                cur.splice(i, 1);
            } else {
                cur.push(valueId);
            }
        } else {
            cur = (cur.length === 1 && cur[0] === valueId) ? [] : [valueId];
        }
        next[keyOf(group)] = cur;
        return next;
    }

    function isOn(sel, group, valueId) {
        return selected(sel, group).indexOf(valueId) > -1;
    }

    /** How many of this option the operator has taken (0, 1, or more where the
     *  group's qty_max allows it). */
    function countOf(sel, group, valueId) {
        return selected(sel, group).filter(function (v) { return v === valueId; }).length;
    }

    /** Items still available in this group, given Odoo's qty_max. */
    function roomLeft(group, sel) {
        var max = (group && group.qty_max) || (group && group.max) || 1;
        return Math.max(0, max - selected(sel, group).length);
    }

    /** The chosen values, in group order: ids for the server, names for the human.
     *  Order is deterministic (group order, then value order) so two identical
     *  configurations always produce the same description and the same line key. */
    function chosen(gs, sel) {
        var ids = [], names = [], combo = [];
        (gs || []).forEach(function (g) {
            valuesOf(g).forEach(function (v) {
                if (!isOn(sel, g, v.id)) {
                    return;
                }
                var units = g.kind === 'combo' ? countOf(sel, g, v.id) : 1;
                names.push(units > 1 ? (v.name + ' x' + units) : v.name);
                if (g.kind === 'combo') {
                    // The server validates and prices combos from product.combo.item,
                    // so the item id is what travels. `ids` stays attribute-only: the
                    // two id spaces are different tables and must never be mixed.
                    combo.push({ item_id: v.id, product_id: v.product_id, qty: units });
                } else {
                    ids.push(v.id);
                }
            });
        });
        return { ids: ids, names: names, combo: combo };
    }

    /** Live preview only — never sent, never trusted, never the figure charged. */
    function extraPrice(gs, sel) {
        var x = 0;
        (gs || []).forEach(function (g) {
            if (g.kind === 'combo') {
                // Odoo's rule, not an invention: everything beyond qty_free costs
                // the group's base price, and every taken item adds its own extra.
                var taken = selected(sel, g).length;
                var beyond = Math.max(0, taken - (g.qty_free === undefined ? 1 : g.qty_free));
                x += beyond * (g.base_price || 0);
                valuesOf(g).forEach(function (v) {
                    x += countOf(sel, g, v.id) * (v.price_extra || 0);
                });
                return;
            }
            valuesOf(g).forEach(function (v) {
                if (isOn(sel, g, v.id)) {
                    x += (v.price_extra || 0);
                }
            });
        });
        return x;
    }

    /** Required groups with nothing chosen. Returned as GROUPS, not as a boolean, so
     *  the surface can name the one that is missing: "Choose a Size" is actionable,
     *  "invalid configuration" is a puzzle. */
    function missingRequired(gs, sel) {
        return (gs || []).filter(function (g) {
            if (g.kind === 'combo') {
                // Odoo's own confirm rule: at least qty_free items from the group.
                var need = (g.qty_free === undefined ? 1 : g.qty_free);
                return need > 0 && selected(sel, g).length < need;
            }
            return g.required && !selected(sel, g).length;
        });
    }

    function isComplete(gs, sel) {
        return missingRequired(gs, sel).length === 0;
    }

    /** The combo picks as a flat list of item ids, one entry PER UNIT taken.
     *
     *  A group with qty_max > 1 can hold the same item twice, and two Cokes is not
     *  the same order as one — so the identity has to count, not just contain.
     *  Accepts either bare ids or the `{item_id, qty}` records `chosen()` emits, so
     *  every caller can hand over what it already has. */
    function comboIds(list) {
        var out = [];
        (list || []).forEach(function (c) {
            if (c === null || c === undefined) {
                return;
            }
            if (typeof c === 'object') {
                var n = Math.max(1, parseInt(c.qty, 10) || 1);
                for (var i = 0; i < n; i++) {
                    out.push(Number(c.item_id));
                }
            } else {
                out.push(Number(c));
            }
        });
        return out;
    }

    /** Which cart line this IS.
     *
     *  Product AND configuration. Merging on product id alone would quietly turn a
     *  plain burger and a no-onion burger into two of the same thing — one ticket,
     *  one plate wrong. Sorted, so the key does not depend on the order the operator
     *  happened to tap the options in.
     *
     *  `note` participates too: free text is part of what makes a line distinct, and
     *  the Register has always treated it that way. So does the COMBO selection: a
     *  Burger Meal with a Coke and one with a Coke Zero are two different meals, and
     *  merging them would send one guest the wrong drink. */
    function lineKey(productId, valueIds, note, comboItemIds) {
        var ids = (valueIds || []).slice().sort(function (a, b) { return a - b; });
        var combo = comboIds(comboItemIds).sort(function (a, b) { return a - b; });
        var key = productId + "@" + ids.join("-") + (combo.length ? "+" + combo.join("-") : "");
        // The separator is NUL written as an ESCAPE: a byte no operator can type, so a
        // note can never be mistaken for part of the key. Written as a raw byte it made
        // this file binary to git - no textual diff, no merge - on a file both surfaces
        // depend on. Same value, same key, readable history.
        return note ? (key + "\u0000" + note) : key;
    }

    /** The selection an existing line's COMBO picks describe, so Edit reopens on
     *  exactly what the guest chose rather than on an empty set of questions. */
    function comboSelectionFrom(gs, comboItemIds) {
        var have = comboIds(comboItemIds);
        var sel = {};
        (gs || []).forEach(function (g) {
            if (g.kind !== 'combo') {
                return;
            }
            var cur = [];
            valuesOf(g).forEach(function (v) {
                // once per unit taken, so reopening a line that holds two Cokes
                // reopens on two Cokes rather than on one
                have.forEach(function (id) {
                    if (id === Number(v.id)) {
                        cur.push(v.id);
                    }
                });
            });
            sel[keyOf(g)] = cur;
        });
        return sel;
    }

    /** One line of human-readable configuration, e.g. "Large · No onion". */
    function describe(gs, sel) {
        return chosen(gs, sel).names.join(" · ");
    }

    global.MezzeProductConfig = Object.freeze({
        groups: groups,
        isConfigurable: isConfigurable,
        defaultSelection: defaultSelection,
        selectionFrom: selectionFrom,
        toggle: toggle,
        isOn: isOn,
        selected: selected,
        countOf: countOf,
        comboIds: comboIds,
        roomLeft: roomLeft,
        chosen: chosen,
        comboSelectionFrom: comboSelectionFrom,
        extraPrice: extraPrice,
        missingRequired: missingRequired,
        isComplete: isComplete,
        lineKey: lineKey,
        describe: describe,
    });
})(typeof window !== "undefined" ? window : this);
