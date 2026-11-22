import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api and /ws are proxied to the backend so the browser never hits CORS.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const target = env.VITE_API_TARGET || "http://localhost:8000";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": { target, changeOrigin: true },
        "/ws": { target, ws: true, changeOrigin: true },
      },
    },
  };
});
