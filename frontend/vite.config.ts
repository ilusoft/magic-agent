/// <reference types="vitest" />
/// <reference types="vite/client" />

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const srcDir = fileURLToPath(new URL("./src", import.meta.url));

export default defineConfig({
  plugins: [react() as []],
  resolve: {
    alias: {
      "@": srcDir,
    },
  },
  server: {
    // Proxy ``/api/*`` to the .NET backend so the frontend works
    // out of the box against the launchSettings.json port even if
    // ``VITE_API_BASE_URL`` points somewhere else (e.g. a
    // reverse proxy or a different host). The proxy target
    // defaults to the same host the Vite dev server is running
    // on (``process.env.HOST`` or ``localhost``) and the
    // ``5134`` port the .NET backend uses by default.
    proxy: {
      "/api": {
        target: "http://localhost:5134",
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./vitest.setup.ts",
    coverage: {
      provider: "istanbul",
    },
  },
});
