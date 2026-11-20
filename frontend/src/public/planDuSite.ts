/** LE PLAN DU SITE : les pages publiques qu'un moteur doit connaître.
 *
 * UNE liste, lue par tout ce qui parle aux robots (règle 5) :
 *   - le pré-rendu (`src/prerendu.ts`, `scripts/prerendre.mjs`) écrit un
 *     fichier HTML complet par page d'ici ;
 *   - `sitemap.xml` et `llms.txt` sont ÉCRITS à partir d'elle, à la
 *     construction — aucun des deux n'est tenu à la main.
 *
 * Une page publique s'y ajoute en ajoutant une ligne. Le test
 * `le-plan-du-site-n-oublie-aucune-page` verrouille que chaque chemin de
 * `contenuSite.CHEMINS` est soit dans le plan, soit dans `HORS_DU_PLAN` avec
 * sa raison : une page ne peut pas être oubliée en silence (règle 1).
 *
 * Ce fichier importe les articles du blog : il ne doit être importé NI par
 * une page NI par `site.ts`, sinon tout le blog partirait dans le premier
 * fichier que le visiteur télécharge. Seuls le pré-rendu et les tests le
 * lisent.
 */
import { ARTICLES } from "./contenuBlog";
import { adresseDeLArticle, CHEMINS } from "./contenuSite";

export type PageDuPlan = {
  /** L'adresse de la page, telle que le routeur la sert. */
  chemin: string;
  /** Le fichier source du morceau que la page charge à la demande, tel que
   *  `router.tsx` l'importe — `null` pour l'accueil, livré avec l'application.
   *  Le pré-rendu y lit la feuille de style à lier dans la page écrite : sans
   *  elle, le texte s'afficherait une fraction de seconde sans sa mise en
   *  forme. */
  module: string | null;
  /** La rubrique sous laquelle `llms.txt` range la page. */
  rubrique: Rubrique;
};

/** Les rubriques de `llms.txt`, dans l'ordre où il les écrit. */
export const RUBRIQUES = [
  "Études et livrables",
  "Accompagnement",
  "Formations",
  "Professionnels",
  "Guides et ressources",
  "Informations légales",
] as const;

export type Rubrique = (typeof RUBRIQUES)[number];

const ETUDES = "src/public/NosEtudes.tsx";
const PACKS = "src/public/Packs.tsx";
const FORMATIONS = "src/public/Formations.tsx";
const RESSOURCES = "src/public/Ressources.tsx";
const BLOG = "src/public/Blog.tsx";
const LEGALES = "src/public/PagesLegales.tsx";

export const PAGES_DU_PLAN: PageDuPlan[] = [
  { chemin: CHEMINS.accueil, module: null, rubrique: "Études et livrables" },
  { chemin: CHEMINS.etudes, module: ETUDES, rubrique: "Études et livrables" },
  { chemin: CHEMINS.boutique, module: "src/public/Boutique.tsx", rubrique: "Études et livrables" },
  { chemin: CHEMINS.packs, module: PACKS, rubrique: "Accompagnement" },
  { chemin: CHEMINS.packEssentiel, module: PACKS, rubrique: "Accompagnement" },
  { chemin: CHEMINS.packPremium, module: PACKS, rubrique: "Accompagnement" },
  { chemin: CHEMINS.formations, module: FORMATIONS, rubrique: "Formations" },
  { chemin: CHEMINS.formationSocietes, module: FORMATIONS, rubrique: "Formations" },
  { chemin: CHEMINS.formationMicro, module: FORMATIONS, rubrique: "Formations" },
  { chemin: CHEMINS.formationPop, module: FORMATIONS, rubrique: "Formations" },
  { chemin: CHEMINS.partenaires, module: "src/public/Partenaires.tsx", rubrique: "Professionnels" },
  { chemin: CHEMINS.swapn, module: RESSOURCES, rubrique: "Professionnels" },
  { chemin: CHEMINS.blog, module: BLOG, rubrique: "Guides et ressources" },
  // Chaque article publié, dans l'ordre du blog : un article ajouté à
  // `contenuBlog.ARTICLES` est dans le plan sans qu'on y pense.
  ...ARTICLES.map((article) => ({
    chemin: adresseDeLArticle(article.slug),
    module: BLOG,
    rubrique: "Guides et ressources" as const,
  })),
  { chemin: CHEMINS.boiteAOutils, module: RESSOURCES, rubrique: "Guides et ressources" },
  { chemin: CHEMINS.contact, module: RESSOURCES, rubrique: "Guides et ressources" },
  { chemin: CHEMINS.mentionsLegales, module: LEGALES, rubrique: "Informations légales" },
  { chemin: CHEMINS.cgv, module: LEGALES, rubrique: "Informations légales" },
  { chemin: CHEMINS.rgpd, module: LEGALES, rubrique: "Informations légales" },
  { chemin: CHEMINS.confidentialite, module: LEGALES, rubrique: "Informations légales" },
];

/** Les chemins de `CHEMINS` qui ne sont PAS des pages à faire connaître, et
 *  pourquoi. Une liste d'exceptions justifiées, pas un oubli. */
export const HORS_DU_PLAN: Record<string, string> = {
  [CHEMINS.espaceClient]: "la porte de l'espace connecté : rien à lire pour un moteur",
  [CHEMINS.article]: "le gabarit de la route d'un article, pas une adresse",
  [CHEMINS.commentCaMarche]: "une section de la page des études, pas une page",
};

/** Ce qu'un robot n'a pas à parcourir : les espaces connectés et les pages de
 *  passage (paiement, mot de passe). `robots.txt` est écrit à partir d'ici.
 *
 *  Chaque préfixe est celui d'une route de `router.tsx` — le test du plan le
 *  vérifie, pour qu'un espace renommé ne reste pas ouvert aux robots sous son
 *  nouveau nom pendant que l'ancien est interdit pour rien. */
export const INTERDIT_AUX_ROBOTS = [
  "/admin",
  "/espace",
  "/login",
  "/inscription",
  "/acheter",
  "/definir-mot-de-passe",
  "/mot-de-passe-oublie",
  "/confirmer-adresse",
  "/boutique/retour",
  "/formations/retour",
  "/api/",
] as const;
