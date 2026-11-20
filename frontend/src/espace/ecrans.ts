/** Tous les écrans de l'espace client, réunis pour être chargés d'un bloc.
 *
 * `routes.tsx` importe ce fichier À LA DEMANDE (`ecranDiffere`,
 * `chargement.ts`) : la coquille et les pages de l'espace forment un morceau à
 * part, que seul un client connecté télécharge — et seulement après que la
 * garde d'accès (`exigerSession`) l'a laissé passer.
 *
 * Un morceau pour tout l'espace plutôt qu'un par page : une fois entré, on
 * passe d'une page à l'autre sans attente, et une mise en ligne survenue
 * entre-temps ne peut échouer qu'à l'entrée, pas à chaque clic.
 *
 * La connexion n'est PAS ici : elle vit avec les pages publiques
 * (`public/Connexion.tsx`), et celui qui se connecte n'a pas à télécharger
 * l'espace pour voir son formulaire.
 *
 * Un écran ajouté à l'espace s'inscrit ici, puis dans `routes.tsx`.
 */
export { Coquille } from "./Coquille";
export { Abonnement } from "./pages/Abonnement";
export { Clients } from "./pages/Clients";
export { CommanderSelonAdresse } from "./pages/Commander";
export { Credits } from "./pages/Credits";
export { Equipe } from "./pages/Equipe";
export { FicheClient } from "./pages/FicheClient";
export { Livrables } from "./pages/Livrables";
export { MaMarque } from "./pages/MaMarque";
export { MesAchats } from "./pages/MesAchats";
export { FormationSuivie, MesFormations } from "./pages/MesFormations";
export { MonCompte } from "./pages/MonCompte";
export { Signalements } from "./pages/Signalements";
export { Souscription } from "./pages/Souscription";
export { SuiviLivrable } from "./pages/SuiviLivrable";
export { TableauDeBord } from "./pages/TableauDeBord";
