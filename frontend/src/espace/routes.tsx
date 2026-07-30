/** Routes de l'espace client, greffées sous `/espace`.
 *
 * Elles vivent dans le même déploiement que la console d'administration, mais
 * derrière un jeton NOMINATIF et une coquille distincte : ce ne sont ni les
 * mêmes utilisateurs, ni les mêmes droits, ni la même charte.
 */
import { createRoute, redirect, type AnyRoute } from "@tanstack/react-router";
import { jeton } from "./api";
import { Coquille } from "./Coquille";
import { Abonnement } from "./pages/Abonnement";
import { Commander } from "./pages/Commander";
import { MaMarque } from "./pages/MaMarque";
import { Connexion } from "./pages/Connexion";
import { Credits } from "./pages/Credits";
import { Equipe } from "./pages/Equipe";
import { Livrables } from "./pages/Livrables";
import { SuiviLivrable } from "./pages/SuiviLivrable";
import { TableauDeBord } from "./pages/TableauDeBord";

/** Garde d'accès. Un jeton absent renvoie vers la connexion.
 *
 * Ce n'est PAS une mesure de sécurité — le serveur refuse de toute façon toute
 * requête sans jeton valide. C'est une commodité : afficher un écran vide puis
 * une erreur serait une mauvaise expérience pour une session simplement
 * expirée.
 */
function exigerSession() {
  if (!jeton.present()) {
    throw redirect({ to: "/espace/connexion" });
  }
}

export function routesEspace(racine: AnyRoute) {
  const connexion = createRoute({
    getParentRoute: () => racine,
    path: "/espace/connexion",
    component: Connexion,
  });

  // Le parent porte `/espace`, les enfants des chemins RELATIFS. Un `id`
  // sans `path` produisait des routes doublees (`/espace/espace/...`).
  const coquille = createRoute({
    getParentRoute: () => racine,
    path: "/espace",
    beforeLoad: exigerSession,
    component: Coquille,
  });

  const enfants = [
    createRoute({
      getParentRoute: () => coquille,
      path: "/",
      component: TableauDeBord,
    }),
    createRoute({
      getParentRoute: () => coquille,
      path: "commander",
      component: Commander,
    }),
    createRoute({
      getParentRoute: () => coquille,
      path: "livrables",
      component: Livrables,
    }),
    createRoute({
      getParentRoute: () => coquille,
      path: "livrables/$jobId",
      component: SuiviLivrable,
    }),
    createRoute({
      getParentRoute: () => coquille,
      path: "ma-marque",
      component: MaMarque,
    }),
    createRoute({
      getParentRoute: () => coquille,
      path: "credits",
      component: Credits,
    }),
    createRoute({
      getParentRoute: () => coquille,
      path: "abonnement",
      component: Abonnement,
    }),
    createRoute({
      getParentRoute: () => coquille,
      path: "equipe",
      component: Equipe,
    }),
  ];

  return [connexion, coquille.addChildren(enfants)];
}
