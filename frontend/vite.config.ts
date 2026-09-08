import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "path";
import frappeui from "frappe-ui/vite";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    frappeui({
      frontendRoute: "/frontend",
      buildConfig: {
        outDir: "../itsuperapp/public/frontend",
        baseUrl: "/assets/itsuperapp/frontend/",
        indexHtmlPath: "../itsuperapp/www/frontend.html",
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  optimizeDeps: {
    // frappe-ui's barrel export (src/index.ts) pulls in TextEditor, which
    // imports icons through the `~icons/*` virtual module resolved by
    // unplugin-icons. esbuild's dependency-scan pass (used only to build the
    // pre-bundle cache) doesn't understand that virtual module and crashes
    // the dev server outright -- excluding frappe-ui here skips the scan;
    // Vite still serves it correctly at request time via the real plugin.
    exclude: ["frappe-ui"],
    // Some frappe-ui modules import CommonJS packages as default exports.
    // Because frappe-ui itself is excluded above, Vite does not discover and
    // wrap these transitive dependencies automatically in dev mode. Pre-bundle
    // only those CJS boundaries so dev interop matches the working production
    // bundle without scanning the full frappe-ui barrel.
    include: ["feather-icons", "debug"],
  },
});
