/** @odoo-module **/
// V2C — production Kitchen Display entry point. Boots a standalone Owl app (no
// webclient, no demo data, no Enterprise Preparation Display). Auth/branch/token
// come from the server-injected boot payload; if it is absent or not ok, the app
// shows an explicit state — it never fabricates kitchen tickets. Reuses the
// cashier's proven transport (MezzeApi) and debug predicate.
import { App, whenReady } from "@odoo/owl";
import { makeEnv } from "@web/env";
import { getTemplate } from "@web/core/templates";
import { appTranslateFn } from "@web/core/l10n/translation";
import { localizationService } from "@web/core/l10n/localization_service";
import { MezzeApi } from "../cashier/api";
import { debugEnabled } from "../cashier/debug";
import { KdsStore } from "./store";
import { KdsRoot } from "./root";

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
    // Load the user's language terms via Odoo's OWN localization service (no custom
    // dictionary). A failure must not break the KDS — proceed in source (English).
    try {
        await localizationService.start();
    } catch {
        // translations unavailable — fall back to source strings
    }
    const api = new MezzeApi(boot);
    // The token now lives privately inside MezzeApi; drop it from boot so no debug
    // handle can surface it.
    delete boot.token;
    const store = new KdsStore();
    env.mezze = { boot, api, store };
    const app = new App(KdsRoot, {
        env,
        getTemplate,
        dev: false,
        name: "MezzeKDS",
        translateFn: appTranslateFn,
        translatableAttributes: ["data-tooltip", "title", "placeholder", "aria-label"],
    });
    const target = document.getElementById("mezze-kds-root");
    const root = await app.mount(target);
    // Debug/testability handle — ONLY under Odoo developer mode (mirrors the cashier).
    // Exposes only non-secret runtime objects; the bearer token is not reachable.
    if (debugEnabled(env && env.debug)) {
        window.__mezzeKds = { root, store };
    } else {
        delete window.__mezzeKds;
    }
});
