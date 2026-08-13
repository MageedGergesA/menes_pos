/** @odoo-module **/

/** THE appearance contract for the Owl staff apps (Register, Floor, Kitchen).
 *
 *  The settings catalogue marks 18 keys `working`, but until now the Owl apps read
 *  none of them at boot: a cashier could set Density or Panel side in Settings, the
 *  server would store it faithfully, and the till would look exactly the same. Only
 *  the static prototype (static/mezze-design.js) ever applied them, so "working" was
 *  true of the storage layer and false of the product.
 *
 *  This module is the missing half. It stamps the SAME attributes on <html> that the
 *  prototype stamps — same names, same values — so one stylesheet (mezze-design.css
 *  plus the per-app rules) serves both surfaces and neither drifts.
 *
 *  It applies only what it is given. Absent keys fall back to the catalogue defaults
 *  below; it never invents a value or persists one.
 */

const DEFAULTS = {
    app_mode: "system",
    app_theme: "classic",
    app_dark_theme: "lounge",
    app_accent: "terracotta",
    app_density: "standard",
    app_scale: "100",
    app_motion: "full",
    ws_nav_labels: "labels",
    ws_panel_side: "right",
    ws_panel_width: "standard",
    gr_cols_mode: "auto",
    gr_cols: "4",
    cd_img: "standard",
    ac_contrast: false,
    ac_focus: true,
    ac_reduce: false,
    ac_dir: "auto",
};

const ACCENTS = ["terracotta", "blue", "teal", "plum", "olive"];

/** The page bootstrap honours ?mzmode= / ?mztheme= / ?mzaccent= ABOVE stored
 *  settings, so support and QA can look at any branch in any palette without
 *  changing that branch's configuration. Re-applying the server values on mount
 *  silently undid that, so the applier has to respect the same precedence:
 *  URL > server-effective > catalogue default. */
function urlOverrides() {
    let p;
    try {
        p = new URLSearchParams(window.location.search);
    } catch (e) {
        return {};
    }
    const out = {};
    const mode = p.get("mzmode");
    const theme = p.get("mztheme");
    const accent = p.get("mzaccent");
    if (mode) {
        out.app_mode = mode;
    }
    if (accent) {
        out.app_accent = accent;
    }
    if (theme === "highcontrast") {
        out.ac_contrast = true;      // the bootstrap treats it as the contrast switch
    } else if (theme) {
        out.app_theme = theme;
        out.app_dark_theme = theme;
    }
    return out;
}

function truthy(v) {
    return v === true || v === "true" || v === 1 || v === "1";
}

function media(q) {
    return typeof window.matchMedia === "function" && window.matchMedia(q).matches;
}

/** system → follow the OS. Anything else is the operator's explicit choice. */
function resolveMode(mode) {
    if (mode === "light" || mode === "dark") {
        return mode;
    }
    return media("(prefers-color-scheme: dark)") ? "dark" : "light";
}

/** High contrast is an accessibility override, so it outranks the chosen theme —
 *  a cashier who needs it must get it whichever palette the branch prefers. */
function resolveTheme(s, mode) {
    if (truthy(s.ac_contrast)) {
        return "highcontrast";
    }
    return mode === "dark" ? s.app_dark_theme : s.app_theme;
}

/** `auto` means "leave it to the language", and the page template has ALREADY set dir
 *  from the user's language server-side. Re-deriving it here from the lang attribute
 *  got it wrong for every Arabic locale that is not the bare code `ar` (ar_001, ar_EG,
 *  ar-001 …) and then overwrote a correct RTL document with ltr. So `auto` returns
 *  null and the attribute is left exactly as rendered; only an explicit operator
 *  choice overrides it. */
function resolveDir(dir) {
    return (dir === "ltr" || dir === "rtl") ? dir : null;
}

/**
 * @param {Object} effective  server-effective settings (subset is fine)
 * @returns {Object} the resolved values actually applied — handy for tests
 */
export function applyAppearance(effective) {
    const s = Object.assign({}, DEFAULTS, effective || {}, urlOverrides());
    const el = document.documentElement;
    const mode = resolveMode(s.app_mode);
    const theme = resolveTheme(s, mode);
    const accent = ACCENTS.includes(s.app_accent) ? s.app_accent : DEFAULTS.app_accent;
    const dir = resolveDir(s.ac_dir);
    // Either switch reduces motion, and so does the OS — the strictest wins, because
    // motion sensitivity is a health constraint, not a preference to average out.
    const reduced = truthy(s.ac_reduce)
        || s.app_motion === "reduced"
        || media("(prefers-reduced-motion: reduce)");
    const cols = s.gr_cols_mode === "fixed" ? String(s.gr_cols || DEFAULTS.gr_cols) : "auto";

    const applied = {
        "data-appearance": "mezze",
        "data-theme": mode,
        "data-mz-mode": mode,
        "data-mz-theme": theme,
        "data-mz-accent": accent,
        "data-mz-density": s.app_density,
        "data-mz-scale": String(s.app_scale),
        "data-mz-motion": reduced ? "reduced" : "full",
        "data-mz-focus": truthy(s.ac_focus) ? "strong" : "default",
        "data-mz-grid-cols": cols,
        "data-mz-card": s.cd_img,
        "data-mz-panel": s.ws_panel_side,
        "data-mz-panel-w": s.ws_panel_width,
        "data-mz-navlabels": s.ws_nav_labels,
    };
    for (const [k, v] of Object.entries(applied)) {
        el.setAttribute(k, v);
    }
    if (dir) {
        el.setAttribute("dir", dir);
    }
    return Object.assign({}, applied, { dir: dir || el.getAttribute("dir") });
}

/** Read the effective settings and apply them. Appearance must never be able to
 *  stop a till from selling, so a failure here is swallowed: the app keeps the
 *  markup defaults rather than refusing to boot. */
export async function loadAppearance(api) {
    try {
        const r = await api.call("/settings/effective", {});
        return applyAppearance((r && r.effective) || {});
    } catch {
        return applyAppearance({});
    }
}
