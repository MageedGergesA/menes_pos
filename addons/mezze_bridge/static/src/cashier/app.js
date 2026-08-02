/** @odoo-module **/
// S2C-1 — production cashier entry point. Boots a standalone Owl app (no
// webclient, no demo data). Auth/branch/token come from the server-injected
// boot payload; if it is absent or not ok, the app shows an explicit error
// state — it never fabricates a restaurant.
import { App, whenReady } from "@odoo/owl";
import { makeEnv } from "@web/env";
import { getTemplate } from "@web/core/templates";
import { appTranslateFn } from "@web/core/l10n/translation";
import { localizationService } from "@web/core/l10n/localization_service";
import { MezzeApi } from "./api";
import { OrderStore } from "./order_store";
import { Root } from "./root";
import { installDebugHandle } from "./debug";

function readBoot() {
    const el = document.getElementById("mezze-boot");
    if (!el) {
        return { ok: false, error: "boot_missing" };
    }
    try {
        return JSON.parse(el.textContent || "{}");
    } catch {
        return { ok: false, error: "boot_parse" };
    }
}

whenReady(async () => {
    const boot = readBoot();
    const env = makeEnv();
    // Load the user's language terms via Odoo's OWN localization service (fetches
    // /web/webclient/translations for the <html lang>). Reuses the standard
    // registry — no custom dictionary. A failure must not break the cashier, so
    // we proceed untranslated (source strings) on error.
    try {
        await localizationService.start();
    } catch {
        // translations unavailable — fall back to source (English) strings
    }
    const api = new MezzeApi(boot);
    // The token now lives privately inside MezzeApi; drop it from the boot object
    // so no debug handle (which may reach boot via the root/env) can surface it.
    delete boot.token;
    const order = new OrderStore(boot);
    env.mezze = { boot, api, order };
    const app = new App(Root, {
        env,
        getTemplate,
        dev: false,
        name: "MezzeCashier",
        // Translate literal template text through Odoo's translation registry.
        translateFn: appTranslateFn,
        translatableAttributes: ["data-tooltip", "title", "placeholder", "aria-label"],
    });
    const target = document.getElementById("mezze-cashier-root");
    const root = await app.mount(target);
    // Debug/testability handle — ONLY under Odoo developer mode (mirrors Odoo's
    // own odoo.__WOWL_DEBUG__). In normal production it is explicitly removed, so
    // window.__mezzeCashier does not exist. Exposes only non-secret runtime
    // objects (root component + order store); the bearer token is not reachable
    // through it. It never alters cashier behaviour.
    installDebugHandle(env, { root, order });
});
