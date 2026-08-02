/** @odoo-module **/
// Centralized communication with the Mezze JSON bridge (type='json2' routes).
// The ONLY place that talks to the backend over HTTP — components never fetch
// directly. No financial calculation happens here; the server is authoritative.
// Errors are normalized into a small, stable shape the UI can act on.

export class MezzeApiError extends Error {
    constructor(kind, message, status) {
        super(message || kind);
        this.kind = kind; // 'auth' | 'network' | 'server' | 'app'
        this.status = status || 0;
    }
}

export class MezzeApi {
    // The bearer token is a true private field: it is never enumerable on the
    // instance, so a debug handle that exposes the api object cannot surface it.
    #token;

    constructor(boot) {
        this.prefix = (boot && boot.api_prefix) || "/mezze/api/v1";
        this.#token = (boot && boot.token) || null;
    }

    /**
     * POST to a bridge endpoint. Returns the parsed JSON body on success.
     * Throws MezzeApiError with a normalized `kind` on any failure so callers
     * can distinguish auth-required from a transport or application error.
     */
    async call(path, params = {}, { signal } = {}) {
        const body = JSON.stringify({ ...params, token: this.#token });
        let res;
        try {
            res = await fetch(this.prefix + path, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body,
                signal,
            });
        } catch (e) {
            if (e && e.name === "AbortError") {
                throw e;
            }
            throw new MezzeApiError("network", "Local Mezze server unavailable", 0);
        }
        if (res.status === 401 || res.status === 403) {
            throw new MezzeApiError("auth", "Authentication required", res.status);
        }
        let data;
        try {
            data = await res.json();
        } catch {
            throw new MezzeApiError("server", "Malformed server response", res.status);
        }
        if (!res.ok || (data && data.ok === false)) {
            const msg = (data && (data.message || data.error)) || "Request failed";
            const kind = (data && data.error === "authentication_required") ? "auth" : "app";
            const err = new MezzeApiError(kind, msg, res.status);
            err.error = data && data.error;
            err.data = data;
            throw err;
        }
        return data;
    }
}
