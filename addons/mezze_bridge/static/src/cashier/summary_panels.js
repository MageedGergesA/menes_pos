/** @odoo-module **/

/** Turn a summary payload into something a manager can read.
 *
 *  `ops`, `manager`, `reports` and `hq` each call a rich endpoint — food-cost
 *  variance, per-server takings, burn rate, per-branch KPIs — and each declared
 *  `rows: null` with no entry in the Workspace component's `stats`. The template
 *  fell through every branch and rendered NOTHING: a workspace that went blank on a
 *  SUCCESSFUL call, which reads to a manager as a broken screen rather than as the
 *  figures they asked for.
 *
 *  Deriving the layout from the SHAPE of the payload, rather than hand-writing four,
 *  is deliberate: these are summaries — scalars and lists of records — and a
 *  shape-driven renderer cannot go blank while there is something to show, whereas
 *  four bespoke templates go stale the moment an endpoint gains a field.
 *
 *  Pure on purpose. The component holds no logic worth testing through a browser,
 *  and this way the derivation is unit-tested directly.
 */

/** Keys that are protocol, not information. */
export const PLUMBING = new Set(["ok", "error", "message", "denied", "as_of"]);

/** Keys whose values are money rather than counts. */
export const MONEY_KEY = /(sales|revenue|total|amount|cost|value|net|gross|takings|burn|spend)/i;

/** A machine key as a person would say it. */
export function humanise(key) {
    const s = String(key).replace(/_/g, " ").trim();
    return s.charAt(0).toUpperCase() + s.slice(1);
}

export function formatValue(key, v, fmt) {
    if (typeof v === "number") {
        // Whole numbers are counts even when the key sounds monetary ("branches",
        // "total_tables"); a fractional one under a money-ish key is money.
        return MONEY_KEY.test(key) && !Number.isInteger(v) ? fmt(v) : String(v);
    }
    return v === null || v === undefined ? "—" : String(v);
}

/** One record of an unknown shape, described without guessing its schema. */
export function describeRow(row, index, fmt) {
    if (!row || typeof row !== "object") {
        return { title: String(row), meta: "" };
    }
    const title = row.name || row.display_name || row.label
        || row.branch || row.product || `#${index + 1}`;
    const meta = Object.entries(row)
        .filter(([k, v]) => !PLUMBING.has(k) && k !== "name" && k !== "display_name"
            && k !== "id" && (typeof v === "number" || typeof v === "string"))
        .slice(0, 4)
        .map(([k, v]) => `${humanise(k)} ${formatValue(k, v, fmt)}`)
        .join(" · ");
    return { title: String(title), meta };
}

/** `[{title, stats:[{k,v}], rows:[{title,meta}], count}]` for any summary payload. */
export function summaryPanels(data, fmt) {
    if (!data || typeof data !== "object") {
        return [];
    }
    const out = [];
    const top = [];
    for (const [key, v] of Object.entries(data)) {
        if (PLUMBING.has(key)) {
            continue;
        }
        if (Array.isArray(v)) {
            out.push({
                title: humanise(key),
                stats: [],
                rows: v.slice(0, 50).map((row, i) => describeRow(row, i, fmt)),
                count: v.length,
            });
        } else if (v && typeof v === "object") {
            out.push({
                title: humanise(key),
                stats: Object.entries(v)
                    .filter(([k2]) => !PLUMBING.has(k2))
                    .map(([k2, v2]) => ({ k: humanise(k2), v: formatValue(k2, v2, fmt) })),
                rows: [],
            });
        } else {
            top.push({ k: humanise(key), v: formatValue(key, v, fmt) });
        }
    }
    if (top.length) {
        out.unshift({ title: "", stats: top, rows: [] });
    }
    return out;
}

/** True when there is actually something on screen to read. */
export function hasSomethingToShow(panels) {
    return (panels || []).some((p) => p.stats.length || p.rows.length);
}
