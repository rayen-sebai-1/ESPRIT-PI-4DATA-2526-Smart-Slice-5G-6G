import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api/auth": {
        target: "http://localhost:8001",
        changeOrigin: true,
        rewrite: (value) => value.replace(/^\/api\/auth/, ""),
      },
      "/api/session": {
        target: "http://localhost:8002",
        changeOrigin: true,
        rewrite: (value) => value.replace(/^\/api\/session/, ""),
      },
      "/api/prediction": {
        target: "http://localhost:8003",
        changeOrigin: true,
        rewrite: (value) => value.replace(/^\/api\/prediction/, ""),
      },
      "/api/dashboard": {
        target: "http://localhost:8004",
        changeOrigin: true,
        rewrite: (value) => value.replace(/^\/api\/dashboard/, ""),
      },
    },
  },
});
