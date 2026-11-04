import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(({ command, mode, isPreview }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const api = env.VITE_API_BASE_URL ?? "";
  if (api) {
    let url: URL;
    try { url = new URL(api); }
    catch { throw new Error("VITE_API_BASE_URL must be a valid HTTPS backend origin"); }
    if (url.protocol !== "https:" || url.username || url.password || url.pathname !== "/" || url.search || url.hash || ["localhost", "127.0.0.1"].includes(url.hostname)) throw new Error("VITE_API_BASE_URL must be an HTTPS backend origin without credentials or paths");
  }
  if (mode === "pages" && !api) throw new Error("GitHub Pages requires VITE_API_BASE_URL");
  if (env.VITE_AUTH_TRANSPORT && !["bearer", "cookie"].includes(env.VITE_AUTH_TRANSPORT)) throw new Error("Invalid VITE_AUTH_TRANSPORT");
  if (mode === "pages" && env.VITE_AUTH_TRANSPORT === "cookie") throw new Error("Use memory-only bearer sessions for cross-site GitHub Pages");
  return {
  base: command === "build" || isPreview ? "/Maritime-AI/" : "/",
  plugins: [react(), {
    name: "production-security-policy",
    transformIndexHtml() {
      if (command !== "build") return [];
      return [{ tag: "meta", attrs: { "http-equiv": "Content-Security-Policy", content: `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self' ${api}; object-src 'none'; base-uri 'self'; form-action 'none'` }, injectTo: "head-prepend" }];
    },
  }],
  server: {
    host: "127.0.0.1",
    strictPort: true,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
  preview: { host: "127.0.0.1", proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } } },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
    include: ["src/**/*.test.tsx"],
  },
};
});
