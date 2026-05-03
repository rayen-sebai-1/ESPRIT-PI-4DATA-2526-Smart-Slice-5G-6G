var _a;
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
var proxyTarget = (_a = process.env.VITE_DEV_PROXY_TARGET) !== null && _a !== void 0 ? _a : "http://localhost:8008";
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
            "/api": {
                target: proxyTarget,
                changeOrigin: true,
            },
        },
    },
});
