import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { rendreLEnTeteAuGabarit } from "./enTetePrerendu";
import { router } from "./router";
import "./theme/tokens.css";
import "./theme/espace.css";
import "./viz/viz.css";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: 1,
    },
  },
});

const racine = document.getElementById("root")!;

const application = (
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* Plus d'enveloppe `<Theme>` Radix : chaque écran porte la charte
          (`theme/tokens.css`, `theme/espace.css`), et ce que l'enveloppe
          donnait en héritage — police, encre, interligne, taille de base,
          fond — est posé sur `body` par `index.css`. */}
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>
);

// Une page PRÉ-RENDUE (`scripts/prerendre.mjs`) arrive avec son contenu déjà
// écrit dans la racine, signalé par `data-prerendu`. React le remplace au
// premier rendu : s'il montait tout de suite, il l'effacerait le temps que le
// morceau de la page soit téléchargé, et le visiteur verrait la page
// apparaître, disparaître, puis revenir. On laisse donc le routeur charger la
// route — son morceau compris — AVANT de monter. Si ce chargement échoue, on
// monte quand même : l'écran d'échec du routeur l'explique.
//
// Partout ailleurs (espace client, administration, fiches de la boutique), la
// racine est vide et rien ne change.
//
// Juste avant de monter, l'en-tête écrit par le pré-rendu est rendu à l'état
// du gabarit (`enTetePrerendu.ts`) : la page y repose aussitôt les siens, et
// rien n'y figure deux fois.
if (racine.hasAttribute("data-prerendu")) {
  void router.load().finally(() => {
    rendreLEnTeteAuGabarit(document);
    createRoot(racine).render(application);
  });
} else {
  createRoot(racine).render(application);
}
