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

// La racine renvoie vers l'administration : `/` n'appartient a aucun des deux
// espaces, et laisser une page blanche a cette adresse serait un cul-de-sac.
const racineRedirige = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: () => {
    throw redirect({ to: "/admin" });
  },
});

const routeTree = rootRoute.addChildren([
  partenairesRoute,
  inscriptionRoute,
  loginRoute,
  racineRedirige,
  adminRoute.addChildren([
    adminIndex,
    adminOrganisations,
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
