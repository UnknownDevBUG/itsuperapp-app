import { defineConfig } from "@playwright/test";

// Reuses the chromium-headless-shell binary already present on this host
// for Frappe's own PDF-generation use (section 5's "check existing
// capability before adding a dependency" -- no new browser binary is
// downloaded; @playwright/test itself is the only new dependency, dev/
// test-only, version-pinned). Targets the frontend container directly by
// its internal Docker network hostname with an explicit Host header
// override for Frappe's site routing -- avoids modifying /etc/hosts.
export default defineConfig({
	testDir: "./e2e",
	timeout: 30_000,
	retries: 0,
	use: {
		baseURL: process.env.AGENT_FLOW_E2E_BASE_URL || "http://frontend:8080",
		extraHTTPHeaders: { Host: process.env.AGENT_FLOW_E2E_HOST || "itsuperapp.local" },
		launchOptions: {
			executablePath:
				process.env.AGENT_FLOW_E2E_CHROMIUM || "/usr/lib/chromium/chromium-headless-shell",
			args: ["--no-sandbox"],
		},
		screenshot: "only-on-failure",
		trace: "retain-on-failure",
	},
	reporter: [["list"]],
});
