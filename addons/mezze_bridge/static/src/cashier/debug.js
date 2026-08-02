/** @odoo-module **/
// S2C-1A — expose the cashier debug handle ONLY under Odoo's native debug mode.
// Odoo debug state is a string: "" in normal production, non-empty ("1",
// "assets", "tests", …) when developer mode is on. No custom flag is introduced.

/** True when Odoo developer/debug mode is active (any non-empty debug string). */
export function debugEnabled(debug) {
    return Boolean(debug);
}

/**
 * Install (or, in normal mode, explicitly remove) the global debug handle.
 * The explicit delete guarantees no stale global survives a return to normal
 * mode. The handle must contain only non-secret runtime objects.
 */
export function installDebugHandle(env, handle) {
    if (debugEnabled(env && env.debug)) {
        window.__mezzeCashier = handle;
    } else {
        delete window.__mezzeCashier;
    }
}
