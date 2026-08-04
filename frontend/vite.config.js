import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      "/ws": { target: "ws://localhost:8000", changeOrigin: true, ws: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
      "/admin/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  worker: {
    format: "es",
  },
});
