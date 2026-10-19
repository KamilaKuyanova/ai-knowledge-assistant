import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Запросы /api проксируются на backend, поэтому CORS не нужен.
const proxy = { "/api": "http://localhost:8000" };

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
});
