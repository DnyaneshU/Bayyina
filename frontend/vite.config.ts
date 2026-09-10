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
    // Every backend route must appear here, or it 404s against the dev server
    // instead of reaching the API. `/evaluate` was missing, which is exactly the
    // failure this list is easy to have: the app works, one button does not.
    // A backend test keeps this in sync with the routes FastAPI actually serves.
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/evaluate": { target: "http://localhost:8000", changeOrigin: true },
      "/healthz": { target: "http://localhost:8000", changeOrigin: true },
      "/comparables": { target: "http://localhost:8000", changeOrigin: true },
      "/areas": { target: "http://localhost:8000", changeOrigin: true },
      "/provenance": { target: "http://localhost:8000", changeOrigin: true },
      "/evidence-pack": { target: "http://localhost:8000", changeOrigin: true },
    },
  },

  build: {
    outDir: "dist",
    sourcemap: true,
    rollupOptions: {
      // Two pages. `specimen.html` is the T2.0 design reference and it imports
      // the product's own index.css, so it cannot drift from what ships — a
      // specimen maintained separately is wrong within a month.
      input: {
        main: "index.html",
        specimen: "specimen.html",
      },
    },
  },

  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
