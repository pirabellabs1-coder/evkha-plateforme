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

/** Posée sur `<html>` tant que la page affichée est celle que le pré-rendu a
 *  écrite. `Site.css` y lit de ne pas rejouer la révélation des blocs. */
const CLASSE_PAGE_ECRITE = "page-ecrite";

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
//
// Un délai borne l'attente : si le morceau ne répond jamais, la page écrite
// resterait à l'écran sans menu ni prix, indéfiniment. Passé ce délai on
// monte, et le routeur prend la suite comme sur une page ordinaire.
if (racine.hasAttribute("data-prerendu")) {
  const ATTENTE_MAX_MS = 5000;
  let monte = false;
  const monter = () => {
    if (monte) return;
    monte = true;
    rendreLEnTeteAuGabarit(document);
    racine.removeAttribute("data-prerendu");
    // Les blocs de la page écrite sont déjà à l'écran. L'application les
    // recrée « à révéler » : sans cette classe, chacun s'effacerait puis
    // reviendrait en fondu sous les yeux du visiteur (`Site.css`). Elle tombe
    // à la première page suivante, qui se révèle comme d'habitude.
    document.documentElement.classList.add(CLASSE_PAGE_ECRITE);
    // L'adresse d'arrivée est comparée ici, et non lue dans `pathChanged` :
    // le premier chargement du routeur s'annonce lui aussi comme un
    // changement d'adresse, et la classe tombait avant d'avoir servi (vu dans
    // le navigateur, sur l'image construite).
    const arrivee = window.location.pathname;
    const finDEcoute = router.subscribe("onBeforeNavigate", (evenement) => {
      if (evenement.toLocation.pathname === arrivee) return;
      document.documentElement.classList.remove(CLASSE_PAGE_ECRITE);
      finDEcoute();
    });
    createRoot(racine).render(application);
  };
  window.setTimeout(monter, ATTENTE_MAX_MS);
  void router.load().finally(monter);
} else {
  // Une fiche de la boutique arrive avec un en-tête écrit par le SERVEUR
  // (`organisations.pages_boutique`), marqué comme celui du pré-rendu, et une
  // racine vide : on le rend au gabarit, puis on monte tout de suite. Sur une
  // page sans marque, cet appel ne change rien.
  rendreLEnTeteAuGabarit(document);
  createRoot(racine).render(application);
}
