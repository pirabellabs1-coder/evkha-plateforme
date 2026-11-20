import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
    // 15 s au lieu des 5 s par défaut : le premier test d'un fichier paie le
    // chargement de la page (jusqu'à 1,5 s seul, bien plus quand tous les
    // fichiers tournent ensemble), et certaines attentes internes valent 8 s.
    testTimeout: 15_000,
  },
});
