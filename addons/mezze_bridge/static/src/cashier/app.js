/** @odoo-module **/
// S2C-1 — production cashier entry point. Boots a standalone Owl app (no
// webclient, no demo data). Auth/branch/token come from the server-injected
// boot payload; if it is absent or not ok, the app shows an explicit error
// state — it never fabricates a restaurant.
import { App, whenReady } from "@odoo/owl";
import { makeEnv } from "@web/env";
import { getTemplate } from "@web/core/templates";
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
        translatableAttributes: ["data-tooltip"],
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
