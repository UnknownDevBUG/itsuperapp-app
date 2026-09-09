import { config } from "@vue/test-utils";

// Every Agent Flow Studio SFC uses Frappe's translation helper `__()` in
// its template. In the real Desk app it's installed as a Vue global
// property by SetVueGlobals(app) (see agent_flow_studio.bundle.js) --
// Vue's template compiler resolves a bare `__` as an instance property
// access (`_ctx.__`), not a lookup on `globalThis`, so tests need the
// same global-property registration, not just `globalThis.__`.
config.global.config ||= {};
config.global.config.globalProperties ||= {};
config.global.config.globalProperties.__ = (s) => s;

globalThis.__ = (s) => s;
globalThis.frappe = globalThis.frappe || { show_alert: () => {} };
