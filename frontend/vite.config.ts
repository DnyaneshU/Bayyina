// Imported from vitest/config, not vite: the `test` block below is a Vitest
// option and vite's own defineConfig does not accept it.
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],

  server: {
    port: 5173,
    // In development the frontend runs on its own dev server and proxies API
    // calls to the backend, so there is no CORS configuration to maintain.
    // In production the backend serves the built assets from dist/, so the
    // whole product stays a single container.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/healthz": "http://localhost:8000",
    },
  },

  build: {
    outDir: "dist",
    sourcemap: true,
  },

  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
