import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  build: {
    sourcemap: false,
    manifest: true,
    rollupOptions: {
      input: {
        main: "index.html",
        visitor: "visitor.html",
      },
    },
  },
  test: {
    environment: "node",
  },
});
