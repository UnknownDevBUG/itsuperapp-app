import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
	plugins: [vue()],
	test: {
		environment: "jsdom",
		include: ["itsuperapp/public/js/**/__tests__/**/*.spec.js"],
		setupFiles: ["itsuperapp/public/js/agent_flow_studio/__tests__/setup.js"],
	},
});
