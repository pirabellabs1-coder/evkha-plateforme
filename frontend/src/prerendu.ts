/** L'entrée du PRÉ-RENDU : l'application, montée hors d'un navigateur pour
 * écrire le HTML complet de chaque page publique à la construction.
 *
 * ## Pourquoi
 *
 * Mesuré le 20/11/2026 sur la production, sans exécuter de JavaScript :
 * `/`, `/etudes`, `/formations`, `/blog`, `/robots.txt`, `/sitemap.xml` et
 * une adresse inventée rendaient tous le MÊME fichier de 3 659 octets — titre
 * « EVKHA — Espace client », un `<div id="root">` vide. Un robot qui n'exécute
 * pas de scripts (ceux des moteurs de réponse, la plupart des aperçus de
 * partage) ne lisait donc rien du site ; Google, lui, devait attendre son
 * second passage pour le voir.
 *
 * ## Comment
 *
 * `scripts/prerendre.mjs` ouvre le `index.html` construit dans jsdom, charge
 * ce fichier-ci (construit par `vite.prerendu.config.ts`), et appelle `monter`
 * pour chaque page de `planDuSite.PAGES_DU_PLAN`. C'est le VRAI routeur et les
 * VRAIES pages (`creerRouteur`) : ce que le robot reçoit est ce que le
 * visiteur voit, pas une seconde version à tenir d'accord (règle 5).
 *
 * Le serveur n'est PAS interrogé : les prix restent lus à l'affichage. Une
 * page pré-rendue porte, à leur place, la phrase d'attente du socle
 * (`contenuSite.TARIFS.attente`) — jamais un montant figé à la construction.
 *
 * Ce fichier n'est importé par aucune page : il n'entre pas dans ce que le
 * navigateur télécharge.
 */
import { createElement, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";

import { creerRouteur } from "./router";

export { ORIGINE_DU_SITE } from "./public/contenuSite";
export {
  INTERDIT_AUX_ROBOTS,
  PAGES_DU_PLAN,
  RUBRIQUES,
} from "./public/planDuSite";

/** Monte l'application à l'adresse COURANTE du document, dans `conteneur`, et
 *  rend de quoi la démonter. L'appelant pose l'adresse avant, attend que la
 *  page soit là, relit le document, puis démonte.
 *
 *  Le même arbre que `main.tsx`, écrit sans JSX : ce fichier n'exporte aucun
 *  composant, et n'a pas à en porter l'extension. */
export function monter(conteneur: HTMLElement): () => void {
  const racine = createRoot(conteneur);
  racine.render(
    createElement(
      StrictMode,
      null,
      createElement(
        QueryClientProvider,
        { client: new QueryClient() },
        createElement(RouterProvider, { router: creerRouteur() }),
      ),
    ),
  );
  return () => racine.unmount();
}
