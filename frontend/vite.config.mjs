import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiOrigin = process.env.PROOFLINE_API_ORIGIN || "http://127.0.0.1:8000";

export default defineConfig({
  build: {
    outDir: "dist/client",
  },
  optimizeDeps: {
    include: ["react", "react-dom/client"],
  },
  server: {
    host: "0.0.0.0",
    allowedHosts: ["terminal.local"],
    proxy: {
      "/api": { target: apiOrigin, changeOrigin: true },
      "/health": { target: apiOrigin, changeOrigin: true },
    },
    warmup: {
      clientFiles: ["./src/main.jsx"],
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{js,jsx}"],
    setupFiles: "./src/test-setup.js",
  },
  plugins: [react()],
});
