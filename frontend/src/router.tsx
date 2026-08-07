import {
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
} from "@tanstack/react-router";
import { GabaritRacine } from "./GabaritRacine";
import { CoquilleAdmin } from "./admin/Coquille";
import { TableauDeBordAdmin } from "./admin/pages/TableauDeBord";
import { OrganisationsAdmin } from "./admin/pages/Organisations";
import { TransactionsAdmin } from "./admin/pages/Transactions";
import { DemandesAdmin } from "./admin/pages/Demandes";
import { Jobs } from "./pages/Jobs";
import { JobDetail } from "./pages/JobDetail";
import { Incidents } from "./pages/Incidents";
import { Clients } from "./pages/Clients";
import { ClientDetail } from "./pages/ClientDetail";
import { Orders } from "./pages/Orders";
import { Login } from "./pages/Login";
import { isAuthenticated } from "./auth";
import { routesEspace } from "./espace/routes";
import { Partenaires } from "./public/Partenaires";
import { Inscription } from "./public/Inscription";
import { DefinirMotDePasse, MotDePasseOublie } from "./public/MotDePasse";
import { ConfirmerAdresse } from "./public/ConfirmerAdresse";

// --- Racine ------------------------------------------------------------------
// Le gabarit vit dans `GabaritRacine.tsx` : il appelle un crochet React, ce
// qu'une fonction anonyme passee a `component` ne permet pas proprement.

const rootRoute = createRootRoute({
  component: GabaritRacine,
});

// --- Garde d'acces -----------------------------------------------------------

function requireAuth() {
  if (!isAuthenticated()) {
    throw redirect({ to: "/login" });
  }
}

// --- Connexion ---------------------------------------------------------------

// --- Page partenaires (PUBLIQUE) ---------------------------------------------
// Aucune garde : elle s'adresse a des visiteurs sans compte. C'est la seule
// route de l'application dans ce cas — le menu du site vitrine pointe dessus.

const partenairesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/partenaires",
  component: Partenaires,
});

// Creation de compte, publique elle aussi : celui qui souscrit n'a pas encore
// de compte, donc pas de jeton a presenter.
const inscriptionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/inscription",
  component: Inscription,
});

// Definir son mot de passe depuis le lien recu par courriel, et le redemander
// quand on l'a perdu. Publiques toutes les deux : la personne n'a par
// definition pas de session — c'est meme le probleme qu'elle vient resoudre.
const definirMotDePasseRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/definir-mot-de-passe",
  component: DefinirMotDePasse,
});

const motDePasseOublieRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/mot-de-passe-oublie",
  component: MotDePasseOublie,
});

// Confirmer sa nouvelle adresse de connexion. PUBLIQUE, et le chemin est fige :
// c'est celui que le serveur ecrit dans le courriel
// (`{EVKHA_APP_URL}/confirmer-adresse?jeton=...`). Le renommer casserait tous
// les liens deja partis, qui restent valables trois jours.
//
// Publique aussi parce qu'on clique depuis sa boite, souvent sur un autre
// appareil que celui ou la session est ouverte — exiger un jeton fermerait la
// porte a ceux qui n'ont plus acces a l'ancienne adresse.
const confirmerAdresseRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/confirmer-adresse",
  component: ConfirmerAdresse,
});

// --- Connexion ---------------------------------------------------------------

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: Login,
});

// --- Espace administrateur ---------------------------------------------------
// La page « Generer » a ete RETIREE : EVKHA ne produit plus les documents a la
// place de ses clients. Cet espace supervise — il ne lance rien. La generation
// manuelle reste accessible en administration Django si un depannage l'exige.

// Prefixe REEL et non un `id` de mise en page : dans cette version de
// TanStack Router, l'identifiant d'une route parente se compose dans les
// chemins des enfants. Les deux espaces sont donc symetriques : `/admin/*` et
// `/espace/*`, chacun avec sa coquille.
const adminRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin",
  beforeLoad: requireAuth,
  component: CoquilleAdmin,
});

const adminIndex = createRoute({
  getParentRoute: () => adminRoute,
  path: "/",
  component: TableauDeBordAdmin,
});

const adminOrganisations = createRoute({
  getParentRoute: () => adminRoute,
  path: "organisations",
  component: OrganisationsAdmin,
});

const adminTransactions = createRoute({
  getParentRoute: () => adminRoute,
  path: "transactions",
  component: TransactionsAdmin,
});

const adminDemandes = createRoute({
  getParentRoute: () => adminRoute,
  path: "demandes",
  component: DemandesAdmin,
});

const adminJobs = createRoute({
  getParentRoute: () => adminRoute,
  path: "jobs",
  component: Jobs,
});

const adminJobDetail = createRoute({
  getParentRoute: () => adminRoute,
  path: "jobs/$jobId",
  component: JobDetail,
});

const adminIncidents = createRoute({
  getParentRoute: () => adminRoute,
  path: "incidents",
  component: Incidents,
});

const adminOrders = createRoute({
  getParentRoute: () => adminRoute,
  path: "orders",
  component: Orders,
});

const adminClients = createRoute({
  getParentRoute: () => adminRoute,
  path: "clients",
  component: Clients,
});

const adminClientDetail = createRoute({
  getParentRoute: () => adminRoute,
  path: "clients/$clientId",
  component: ClientDetail,
});

// --- Page d'accueil ----------------------------------------------------------
//
// La racine EST la page partenaires. Elle renvoyait vers `/admin` : la premiere
// chose qu'un visiteur du tunnel de vente rencontrait etait donc l'ecran de
// connexion de l'administration — au mieux un cul-de-sac, au pire une invitation
// a chercher la porte de service.
//
// Le meme composant sert les deux adresses plutot qu'une redirection : `/`
// pour le menu du site, et `/partenaires` qui reste valide pour tout lien deja
// diffuse. Une redirection aurait fait clignoter l'URL sous les yeux du
// visiteur, et casse le partage d'un lien profond.
//
// L'administration reste a `/admin`, hors de tout chemin public : aucune page
// visible par un visiteur n'y renvoie.
const racine = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: Partenaires,
});

const routeTree = rootRoute.addChildren([
  partenairesRoute,
  inscriptionRoute,
  definirMotDePasseRoute,
  motDePasseOublieRoute,
  confirmerAdresseRoute,
  loginRoute,
  racine,
  adminRoute.addChildren([
    adminIndex,
    adminOrganisations,
    adminTransactions,
    adminDemandes,
    adminJobs,
    adminJobDetail,
    adminIncidents,
    adminOrders,
    adminClients,
    adminClientDetail,
  ]),
  ...routesEspace(rootRoute),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
