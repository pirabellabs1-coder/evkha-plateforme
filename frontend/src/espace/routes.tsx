/** Routes de l'espace client, greffées sous `/espace`.
 *
 * Elles vivent dans le même déploiement que la console d'administration, mais
 * derrière un jeton NOMINATIF et une coquille distincte : ce ne sont ni les
 * mêmes utilisateurs, ni les mêmes droits, ni la même charte.
 */
import { createRoute, redirect, type AnyRoute } from "@tanstack/react-router";
import { ecranDiffere } from "../chargement";
import { jeton } from "./jeton";

// ── Les écrans, chargés à la demande ─────────────────────────────────────────
//
// Aucun écran n'est importé ici : le visiteur du site ne télécharge pas
// l'espace client. Tous viennent d'UN morceau (`ecrans.ts`), demandé quand une
// route de l'espace est ouverte — donc APRÈS la garde d'accès, qui s'exécute
// avant tout chargement de composant. Les routes plus bas gardent leur forme :
// `component: TableauDeBord`.
const ecrans = () => import("./ecrans");

const Coquille = ecranDiffere(ecrans, "Coquille");
const Abonnement = ecranDiffere(ecrans, "Abonnement");
const Clients = ecranDiffere(ecrans, "Clients");
const CommanderSelonAdresse = ecranDiffere(ecrans, "CommanderSelonAdresse");
const Credits = ecranDiffere(ecrans, "Credits");
const Equipe = ecranDiffere(ecrans, "Equipe");
const FicheClient = ecranDiffere(ecrans, "FicheClient");
const Livrables = ecranDiffere(ecrans, "Livrables");
const MaMarque = ecranDiffere(ecrans, "MaMarque");
const MesAchats = ecranDiffere(ecrans, "MesAchats");
const MonCompte = ecranDiffere(ecrans, "MonCompte");
const Signalements = ecranDiffere(ecrans, "Signalements");
const Souscription = ecranDiffere(ecrans, "Souscription");
const SuiviLivrable = ecranDiffere(ecrans, "SuiviLivrable");
const TableauDeBord = ecranDiffere(ecrans, "TableauDeBord");

// La connexion partage la coquille de l'inscription : deux portes du meme
// endroit doivent se ressembler. Elle vit donc avec les pages publiques, dans
// son propre morceau : se connecter ne demande pas de telecharger l'espace.
const Connexion = ecranDiffere(() => import("../public/Connexion"), "Connexion");

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
    // Travailler par client : la liste, puis la fiche d'un client, depuis
    // laquelle chaque livrable se commande pré-rempli.
    createRoute({
      getParentRoute: () => coquille,
      path: "clients",
      component: Clients,
    }),
    createRoute({
      getParentRoute: () => coquille,
      path: "clients/$clientId",
      component: FicheClient,
    }),
    createRoute({
      getParentRoute: () => coquille,
      path: "commander",
      component: CommanderSelonAdresse,
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
    // Les etudes de boutique. Distinctes des livrables : un fichier achete
    // une fois n'a ni questionnaire, ni progression, ni controle.
    createRoute({
      getParentRoute: () => coquille,
      path: "achats",
      component: MesAchats,
    }),
    createRoute({
      getParentRoute: () => coquille,
      path: "abonnement",
      component: Abonnement,
    }),
    // Activation de l'abonnement. Une page de l'espace, atteignable depuis le
    // bandeau et depuis Abonnement — c'est aussi l'adresse de retour de Stripe.
    createRoute({
      getParentRoute: () => coquille,
      path: "souscription",
      component: Souscription,
    }),
    createRoute({
      getParentRoute: () => coquille,
      path: "equipe",
      component: Equipe,
    }),
    // Signaler un probleme. Aucun droit particulier n'est exige cote serveur :
    // celui qui voit qu'un document ne va pas n'est pas toujours celui qui
    // gere l'abonnement.
    createRoute({
      getParentRoute: () => coquille,
      path: "signalements",
      component: Signalements,
    }),
    // Identité et mot de passe. Enfant de la coquille comme les autres : le
    // changement de mot de passe exige une session, et c'est `beforeLoad` du
    // parent qui la réclame.
    createRoute({
      getParentRoute: () => coquille,
      path: "mon-compte",
      component: MonCompte,
    }),
  ];

  return [connexion, coquille.addChildren(enfants)];
}
