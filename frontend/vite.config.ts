import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  preview: { host: "127.0.0.1", proxy: { "/api": "http://127.0.0.1:8000" } },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
    include: ["src/**/*.test.tsx"],
  },
});
