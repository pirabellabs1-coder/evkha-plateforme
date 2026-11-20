import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // Le manifeste dit quel fichier porte chaque morceau : le pre-rendu
    // (`scripts/prerendre.mjs`) y lit la feuille de style a lier dans chaque
    // page ecrite, puis le retire de `dist/`.
    manifest: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // Proxy les appels API vers Django en dev local
      "/api": {
        // `EVKHA_API_PROXY` ne regle QUE la cible du relais : `VITE_API_URL`,
        // lui, est aussi lu par le navigateur (`donnees.BASE`), qui appelle
        // alors le serveur en direct et se fait refuser par CORS.
        target:
          // `||` et non `??` : une variable posee VIDE (`EVKHA_API_PROXY=`)
          // donnerait une cible vide au relais au lieu du repli.
          process.env.EVKHA_API_PROXY ||
          process.env.VITE_API_URL ||
          "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
