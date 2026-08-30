import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/dashboard": "http://127.0.0.1:8000",
      "/datasets": "http://127.0.0.1:8000",
      "/decisions": "http://127.0.0.1:8000",
      "/experiments": "http://127.0.0.1:8000",
      "/research": "http://127.0.0.1:8000"
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    exclude: ["tests/e2e/**", "node_modules/**", "dist/**"]
  }
});
