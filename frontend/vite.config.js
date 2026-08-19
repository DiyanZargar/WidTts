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
      "/realtime": { target: "http://localhost:8000", changeOrigin: true },
      "/api/bot": { target: "http://localhost:8000", changeOrigin: true },
      "/rtc": { target: "http://localhost:7880", changeOrigin: true, ws: true },
      "/twirp": { target: "http://localhost:7880", changeOrigin: true },
    },
  },
  worker: {
    format: "es",
  },
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor_react: ["react", "react-dom", "react-router-dom"],
          vendor_livekit: ["livekit-client"],
          vendor_three: ["three", "@react-three/fiber", "@react-three/drei"],
        },
      },
    },
  },
});
