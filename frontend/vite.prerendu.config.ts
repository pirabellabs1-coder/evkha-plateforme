import { defineConfig, mergeConfig } from "vite";

import base from "./vite.config";

// La construction de l'entree du PRE-RENDU (`src/prerendu.ts`), lue par
// `scripts/prerendre.mjs`. Voir l'en-tete de ces deux fichiers.
//
// L'application y tourne dans jsdom, c'est-a-dire comme dans un navigateur.
// Deux reglages en decoulent, et sans eux le routeur ne rend rien :
//
// - `noExternal: true` : les dependances sont EMBARQUEES dans le fichier
//   construit au lieu d'etre chargees par Node a l'execution ;
// - les conditions `browser` : TanStack Router publie une variante « serveur »
//   que Node choisit de lui-meme, et qui n'a pas d'etat reactif — mesure le
//   20/11/2026, `MatchesInner` y lisait `undefined`. Embarquees avec la
//   condition `browser`, les dependances sont celles que le visiteur recoit.
export default mergeConfig(
  base,
  defineConfig({
    build: {
      ssr: "src/prerendu.ts",
      outDir: "dist-prerendu",
      emptyOutDir: true,
      manifest: false,
    },
    ssr: {
      noExternal: true,
      resolve: {
        conditions: ["browser", "module", "import", "default"],
      },
    },
    define: {
      "process.env.NODE_ENV": JSON.stringify("production"),
    },
  }),
);
