import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// VITE_API_BASE points the page at the FastAPI service; see src/api.js.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: { outDir: "dist" },
});
