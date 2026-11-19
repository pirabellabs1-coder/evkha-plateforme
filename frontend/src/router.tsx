import {
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
  type RouterHistory,
} from "@tanstack/react-router";
import { GabaritRacine } from "./GabaritRacine";
import { PageEnAttente, PageEnEchec } from "./EtatsDuRouteur";
import { isAuthenticated } from "./auth";
import { ecranDiffere } from "./chargement";
import { routesEspace } from "./espace/routes";
import { Accueil } from "./public/Accueil";
import {
  adresseDeLArticle,
  CHEMINS,
  SLUG_IDEE_BUSINESS_VIABLE,
} from "./public/contenuSite";

// --- Les ecrans, charges a la demande ------------------------------------------
//
// Seule la page d'accueil est importee ici : c'est elle que le visiteur
// demande d'abord, et elle ne doit attendre aucun second fichier. Tout le
// reste est importe quand sa route est ouverte (`ecranDiffere`,
// `chargement.ts`) — jusqu'au 19/11/2026, ce fichier importait tout, et le
// visiteur de l'accueil telechargeait l'administration et l'espace client.
//
// Chaque ecran garde ici le NOM de son composant : les routes plus bas n'ont
// pas change de forme (`component: Packs`), et se lisent comme avant.
//
// Les morceaux :
//   - l'administration, d'un bloc (`admin/ecrans.ts`) — et sa page de
//     connexion a part, qu'on voit AVANT d'avoir le droit d'entrer ;
//   - l'espace client, d'un bloc (`espace/ecrans.ts`, voir `espace/routes.tsx`) ;
//   - les pages publiques, un morceau par fichier : les pages d'un meme
//     fichier (les trois packs, les quatre textes legaux) viennent ensemble.
//     Ce qu'elles partagent (la barre, le pied, les textes communs) est deja
//     la, charge avec l'accueil.
//
// Les gardes d'acces (`beforeLoad`) s'executent AVANT tout chargement de
// composant : personne ne telecharge un espace ou il n'entrera pas.

const admin = () => import("./admin/ecrans");
const CoquilleAdmin = ecranDiffere(admin, "CoquilleAdmin");
const TableauDeBordAdmin = ecranDiffere(admin, "TableauDeBordAdmin");
const OrganisationsAdmin = ecranDiffere(admin, "OrganisationsAdmin");
const LivrablesAdmin = ecranDiffere(admin, "LivrablesAdmin");
const QualiteAdmin = ecranDiffere(admin, "QualiteAdmin");
const BoutiqueAdmin = ecranDiffere(admin, "BoutiqueAdmin");
const Annonces = ecranDiffere(admin, "Annonces");
const ProspectionAdmin = ecranDiffere(admin, "ProspectionAdmin");
const TransactionsAdmin = ecranDiffere(admin, "TransactionsAdmin");
const DemandesAdmin = ecranDiffere(admin, "DemandesAdmin");
const SignalementsAdmin = ecranDiffere(admin, "SignalementsAdmin");
const Jobs = ecranDiffere(admin, "Jobs");
const JobDetail = ecranDiffere(admin, "JobDetail");
const Incidents = ecranDiffere(admin, "Incidents");
const Clients = ecranDiffere(admin, "Clients");
const ClientDetail = ecranDiffere(admin, "ClientDetail");
const Orders = ecranDiffere(admin, "Orders");
const Login = ecranDiffere(() => import("./pages/Login"), "Login");

const Partenaires = ecranDiffere(() => import("./public/Partenaires"), "Partenaires");
const NosEtudes = ecranDiffere(() => import("./public/NosEtudes"), "NosEtudes");

const packs = () => import("./public/Packs");
const Packs = ecranDiffere(packs, "Packs");
const PackEssentiel = ecranDiffere(packs, "PackEssentiel");
const PackPremium = ecranDiffere(packs, "PackPremium");

const formations = () => import("./public/Formations");
const Formations = ecranDiffere(formations, "Formations");
const FormationSocietes = ecranDiffere(formations, "FormationSocietes");
const FormationMicro = ecranDiffere(formations, "FormationMicro");
const FormationPop = ecranDiffere(formations, "FormationPop");

const ressources = () => import("./public/Ressources");
const BoiteAOutils = ecranDiffere(ressources, "BoiteAOutils");
const Contact = ecranDiffere(ressources, "Contact");
const Swapn = ecranDiffere(ressources, "Swapn");

const blog = () => import("./public/Blog");
const Blog = ecranDiffere(blog, "Blog");
const ArticleDeBlog = ecranDiffere(blog, "ArticleDeBlog");

const textesLegaux = () => import("./public/PagesLegales");
const MentionsLegales = ecranDiffere(textesLegaux, "MentionsLegales");
const Rgpd = ecranDiffere(textesLegaux, "Rgpd");
const Cgv = ecranDiffere(textesLegaux, "Cgv");
const PolitiqueDeConfidentialite = ecranDiffere(textesLegaux, "PolitiqueDeConfidentialite");

const Introuvable = ecranDiffere(() => import("./public/Introuvable"), "Introuvable");
const Boutique = ecranDiffere(() => import("./public/Boutique"), "Boutique");
const FicheProduit = ecranDiffere(() => import("./public/FicheProduit"), "FicheProduit");
const RetourBoutique = ecranDiffere(() => import("./public/RetourBoutique"), "RetourBoutique");
const Inscription = ecranDiffere(() => import("./public/Inscription"), "Inscription");

const motDePasse = () => import("./public/MotDePasse");
const DefinirMotDePasse = ecranDiffere(motDePasse, "DefinirMotDePasse");
const MotDePasseOublie = ecranDiffere(motDePasse, "MotDePasseOublie");

const ConfirmerAdresse = ecranDiffere(() => import("./public/ConfirmerAdresse"), "ConfirmerAdresse");
const Acheter = ecranDiffere(() => import("./public/Acheter"), "Acheter");
const RetourPaiement = ecranDiffere(() => import("./public/RetourPaiement"), "RetourPaiement");

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
  path: CHEMINS.partenaires,
  component: Partenaires,
});

// Les etudes vendues a l'unite : la page de vente principale, ou mene le
// bouton « Commander une etude » de l'accueil. Refaite le 19/11/2026 dans le
// langage de l'accueil, dont elle partage la barre, le pied et la feuille de
// base (`public/EnTeteSite`, `PiedSite`, `Site.css`). Elle remplace
// `evkha.fr/etudedemarche`, dont le menu du site pointe desormais ici.
const etudesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.etudes,
  component: NosEtudes,
});

// La boutique : les etudes DEJA REDIGEES, vendues telles quelles. Distincte de
// `/etudes`, qui vend des etudes a produire sur le projet du client — le
// paiement n'y declenche aucune production, il ouvre un acces a un fichier.
//
// Aucune garde : le visiteur n'a par definition pas de compte, et n'en a pas
// besoin pour acheter. Le sien est ouvert par l'encaissement.
const boutiqueRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.boutique,
  component: Boutique,
});

// Le retour de paiement AVANT la fiche : sans cela, `/boutique/retour` serait
// lu comme la fiche d'un produit dont le slug serait « retour ».
const retourBoutiqueRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/boutique/retour",
  component: RetourBoutique,
});

const ficheProduitRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/boutique/$slug",
  component: FicheProduit,
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

// --- Achat d'une etude a l'unite (PUBLIQUE) ----------------------------------
// Achat DIRECT, sans creation de compte prealable : la personne paie, et son
// espace s'ouvre au retour de Stripe.
//
// Ce n'est PAS le chemin des cartes de `/etudes`, qui passent par
// `/inscription?livrable=…` — meme porte que la page partenaires. Celui-ci
// sert le client qui REVIENT : il a deja un compte, l'inscription le
// refuserait (« deja membre »), et `livrer_l_achat` credite l'espace qu'il
// possede au lieu d'en ouvrir un second.
//
// Aucun lien de l'application n'y mene aujourd'hui : le rachat depuis l'espace
// reste a poser. La route existe pour qu'il n'y ait pas deux mecaniques de
// paiement le jour ou on le posera.
//
// Le segment est le SLUG de l'offre en base, pas un identifiant invente ici :
// c'est lui que le serveur retrouve pour appliquer le bon tarif.
const acheterRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/acheter/$livrable",
  component: Acheter,
});

// Adresse de retour de Stripe, figée : elle est écrite dans la `success_url`
// de chaque session de paiement (`paiement/stripe_api.py`). La renommer
// laisserait sur le carreau tous les paiements déjà ouverts.
const retourPaiementRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/acheter/retour",
  component: RetourPaiement,
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

const adminQualite = createRoute({
  getParentRoute: () => adminRoute,
  path: "qualite",
  component: QualiteAdmin,
});

const adminLivrables = createRoute({
  getParentRoute: () => adminRoute,
  path: "livrables",
  component: LivrablesAdmin,
});

// La boutique : le catalogue des etudes deja redigees. Le seul chemin pour
// ajouter, modifier ou retirer un produit — il ne repasse ni par un
// developpeur ni par une mise en ligne.
const adminBoutique = createRoute({
  getParentRoute: () => adminRoute,
  path: "boutique",
  component: BoutiqueAdmin,
});

// Les annonces : le seul chemin pour prevenir tous les clients d'un coup, par
// courriel ET dans leur espace. Il ne repasse pas par un developpeur.
const adminAnnonces = createRoute({
  getParentRoute: () => adminRoute,
  path: "annonces",
  component: Annonces,
});

const adminProspection = createRoute({
  getParentRoute: () => adminRoute,
  path: "prospection",
  component: ProspectionAdmin,
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

// Les signalements venus des espaces clients, et l'assistance qui va avec.
const adminSignalements = createRoute({
  getParentRoute: () => adminRoute,
  path: "signalements",
  component: SignalementsAdmin,
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

// --- Le site public repris de evkha.fr (19/11/2026) ---------------------------
//
// Regle de la refonte : aucune page de l'ancien site (systeme.io) ne manque.
// Chaque ligne de `docs/refonte/catalogue-et-plan-du-site.md` a ici sa page :
// packs, formations, boite a outils, blog, contact, Swapn, et les quatre textes
// legaux, gardes a leur adresse d'origine pour ne pas perdre leur referencement.
// Aucune garde : ce sont des pages de visiteur.
//
// Les chemins se LISENT dans `contenuSite.CHEMINS`, la seule source des
// adresses du site public (regle 5) : le menu, le pied et les pages y lisent
// les memes. `CHEMINS` est `as const` : le routeur recoit des litteraux.
const packsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.packs,
  component: Packs,
});
const packEssentielRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.packEssentiel,
  component: PackEssentiel,
});
const packPremiumRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.packPremium,
  component: PackPremium,
});
const formationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.formations,
  component: Formations,
});
const formationSocietesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.formationSocietes,
  component: FormationSocietes,
});
const formationMicroRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.formationMicro,
  component: FormationMicro,
});
const formationPopRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.formationPop,
  component: FormationPop,
});
const boiteAOutilsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.boiteAOutils,
  component: BoiteAOutils,
});
const blogRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.blog,
  component: Blog,
});
const articleDeBlogRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.article,
  component: ArticleDeBlog,
});
const contactRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.contact,
  component: Contact,
});
const swapnRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.swapn,
  component: Swapn,
});
const mentionsLegalesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.mentionsLegales,
  component: MentionsLegales,
});
const rgpdRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.rgpd,
  component: Rgpd,
});
const cgvRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.cgv,
  component: Cgv,
});
const confidentialiteRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.confidentialite,
  component: PolitiqueDeConfidentialite,
});

// Les anciennes adresses du site, encore dans les moteurs, les courriels et les
// favoris. Elles renvoient a la page qui les remplace. C'est une redirection
// faite par le navigateur : la vraie 301, lue par les robots, se pose au
// serveur (nginx) le jour ou le domaine bascule.
//
// L'ancien article garde son adresse complete, plus bas : `/boite-a-outils/...`.
// Les pages de paiement (`/paiement-*`) ne sont PAS ici : tant que la
// plateforme n'encaisse ni les packs ni les formations, ce sont elles qui
// vendent, et les rediriger couperait la vente.
//
// `search: true` et `hash: true` : la redirection GARDE les parametres et
// l'ancre de l'adresse suivie. Sans eux, `/formation?utm_source=lettre`
// arrivait sur `/formations` tout court, et la campagne qui avait amene le
// visiteur n'etait plus mesuree.
//
// Chaque ancienne adresse s'inscrit dans `ANCIENNES_ADRESSES` au moment ou sa
// route est creee : le test `chaque-lien-du-site-a-sa-route` les rejoue toutes
// depuis cette liste, sans en recopier une seule.
export const ANCIENNES_ADRESSES: { de: string; vers: string }[] = [];

function ancienneAdresse(de: string, vers: Parameters<typeof redirect>[0]["to"]) {
  ANCIENNES_ADRESSES.push({ de, vers: String(vers) });
  return createRoute({
    getParentRoute: () => rootRoute,
    path: de,
    beforeLoad: () => {
      throw redirect({ to: vers, search: true, hash: true });
    },
  });
}

// L'ancienne adresse de l'article, sous la boite a outils. Son slug est lu la
// ou le blog le lit : il n'est pas ecrit une seconde fois ici.
const ANCIENNE_ADRESSE_DE_L_ARTICLE = "/boite-a-outils/idee-business-viable";
ANCIENNES_ADRESSES.push({
  de: ANCIENNE_ADRESSE_DE_L_ARTICLE,
  vers: adresseDeLArticle(SLUG_IDEE_BUSINESS_VIABLE),
});

const anciennesAdresses = [
  ancienneAdresse("/formation", CHEMINS.formations),
  ancienneAdresse("/achat-formationsociete", CHEMINS.formationSocietes),
  ancienneAdresse("/achat-formationmicro", CHEMINS.formationMicro),
  ancienneAdresse("/achat-formationpop", CHEMINS.formationPop),
  ancienneAdresse("/etude", CHEMINS.etudes),
  ancienneAdresse("/etudedemarche", CHEMINS.etudes),
  ancienneAdresse("/etude-achat-immediat", CHEMINS.boutique),
  ancienneAdresse("/partenairespro", CHEMINS.partenaires),
  ancienneAdresse("/boite-a-outil", CHEMINS.boiteAOutils),
  ancienneAdresse("/contacts", CHEMINS.contact),
  ancienneAdresse("/contacte", CHEMINS.contact),
  createRoute({
    getParentRoute: () => rootRoute,
    path: ANCIENNE_ADRESSE_DE_L_ARTICLE,
    beforeLoad: () => {
      throw redirect({
        to: CHEMINS.article,
        params: { slug: SLUG_IDEE_BUSINESS_VIABLE },
        search: true,
        hash: true,
      });
    },
  }),
];

// --- Page d'accueil ----------------------------------------------------------
//
// La racine est la page d'accueil publique (`public/Accueil.tsx`) : la
// maquette validee par la cliente, qui s'adresse d'abord au porteur de projet
// et renvoie le professionnel vers `/partenaires` des son ouverture.
//
// Elle a ete, dans l'ordre : une redirection vers `/admin` (le visiteur du
// tunnel de vente tombait sur l'ecran de connexion de l'administration), puis
// la page partenaires elle-meme, servie aux deux adresses. Ce n'est plus le
// cas : `/` et `/partenaires` rendent desormais deux pages DIFFERENTES.
// `/partenaires` n'a pas change et reste valide pour tout lien deja diffuse.
//
// L'administration reste a `/admin`, hors de tout chemin public : aucune page
// visible par un visiteur n'y renvoie.
const racine = createRoute({
  getParentRoute: () => rootRoute,
  path: CHEMINS.accueil,
  component: Accueil,
});

// Exporte : le test `chaque-lien-du-site-a-sa-route` monte l'arbre REEL sur
// un historique en memoire.
export const routeTree = rootRoute.addChildren([
  partenairesRoute,
  etudesRoute,
  boutiqueRoute,
  retourBoutiqueRoute,
  ficheProduitRoute,
  inscriptionRoute,
  definirMotDePasseRoute,
  motDePasseOublieRoute,
  confirmerAdresseRoute,
  retourPaiementRoute,
  acheterRoute,
  loginRoute,
  racine,
  packsRoute,
  packEssentielRoute,
  packPremiumRoute,
  formationsRoute,
  formationSocietesRoute,
  formationMicroRoute,
  formationPopRoute,
  boiteAOutilsRoute,
  blogRoute,
  articleDeBlogRoute,
  contactRoute,
  swapnRoute,
  mentionsLegalesRoute,
  rgpdRoute,
  cgvRoute,
  confidentialiteRoute,
  ...anciennesAdresses,
  adminRoute.addChildren([
    adminIndex,
    adminOrganisations,
    adminBoutique,
    adminAnnonces,
    adminProspection,
    adminTransactions,
    adminLivrables,
    adminQualite,
    adminDemandes,
    adminSignalements,
    adminJobs,
    adminJobDetail,
    adminIncidents,
    adminOrders,
    adminClients,
    adminClientDetail,
  ]),
  ...routesEspace(rootRoute),
]);

// Une adresse inconnue rend la page « Page introuvable » du site
// (`public/Introuvable.tsx`), avec sa barre, son pied et ses portes de sortie
// — et non le « Not Found » nu de TanStack Router.
//
// Une fabrique, pour que l'application et les tests montent le MEME routeur :
// meme arbre, meme page introuvable. Seul l'historique change (celui du
// navigateur par defaut, un historique en memoire dans les tests).
//
// Deux ecrans pour ce qui se passe ENTRE deux pages, maintenant que les ecrans
// se chargent a la demande (`EtatsDuRouteur.tsx`) : une page vide dans la
// charte tant qu'un morceau n'est pas arrive — le routeur ne la montre qu'au
// bout d'une seconde, un chargement ordinaire ne clignote donc pas — et un
// message en francais, avec « Recharger la page », s'il n'arrive pas. Sans
// eux, le routeur n'affichait rien dans le premier cas et son texte anglais
// dans le second.
export function creerRouteur(history?: RouterHistory) {
  return createRouter({
    routeTree,
    history,
    defaultNotFoundComponent: Introuvable,
    defaultPendingComponent: PageEnAttente,
    defaultErrorComponent: PageEnEchec,
  });
}

export const router = creerRouteur();

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
