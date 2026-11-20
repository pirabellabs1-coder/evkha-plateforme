/** Tous les écrans de l'administration, réunis pour être chargés d'un bloc.
 *
 * `router.tsx` importe ce fichier À LA DEMANDE (`ecranDiffere`,
 * `chargement.ts`) : la coquille et les pages de l'administration forment un
 * morceau à part, que seul un administrateur télécharge — et seulement après
 * que la garde d'accès (`requireAuth`) l'a laissé passer.
 *
 * Un morceau pour tout l'espace plutôt qu'un par page : une fois entré, on
 * passe d'une page à l'autre sans attente, et une mise en ligne survenue
 * entre-temps ne peut échouer qu'à l'entrée, pas à chaque clic.
 *
 * Un écran ajouté à l'administration s'inscrit ici, puis dans `router.tsx`.
 */
export { CoquilleAdmin } from "./Coquille";
export { Annonces } from "./pages/Annonces";
export { BoutiqueAdmin } from "./pages/BoutiqueAdmin";
export { DemandesAdmin } from "./pages/Demandes";
export { FormationsAdmin } from "./pages/Formations";
export { LivrablesAdmin } from "./pages/Livrables";
export { OrganisationsAdmin } from "./pages/Organisations";
export { ProspectionAdmin } from "./pages/Prospection";
export { QualiteAdmin } from "./pages/Qualite";
export { SignalementsAdmin } from "./pages/Signalements";
export { TableauDeBordAdmin } from "./pages/TableauDeBord";
export { TransactionsAdmin } from "./pages/Transactions";
// Les écrans de supervision, plus anciens, vivent dans `src/pages`.
export { ClientDetail } from "../pages/ClientDetail";
export { Clients } from "../pages/Clients";
export { Incidents } from "../pages/Incidents";
export { JobDetail } from "../pages/JobDetail";
export { Jobs } from "../pages/Jobs";
export { Orders } from "../pages/Orders";
