/** LA SOURCE DES ARTICLES DU BLOG (`Blog.tsx` : `/blog` et `/blog/$slug`).
 *
 * UN ARTICLE S'AJOUTE EN AJOUTANT UNE ENTRÉE À LA LISTE `ARTICLES`, plus bas,
 * en attendant la publication depuis l'administration. Rien d'autre à
 * toucher : la liste du blog, les filtres par thème, la page de l'article, son
 * sommaire, son temps de lecture et ses données structurées se construisent à
 * partir de cette liste. Le jour où l'administration publie les articles,
 * c'est cette liste — et elle seule — qu'une réponse du serveur remplace.
 *
 * Pour ajouter un article :
 *   1. écrire son texte sous la forme `SourceDArticle` (titre, chapô,
 *      sections, conclusion) — dans ce fichier ou dans un fichier de contenu ;
 *   2. l'ajouter à `ARTICLES` par `composer(…)`, avec un `slug` unique (c'est
 *      son adresse : `/blog/<slug>`), un thème de la liste fermée `THEMES`, et
 *      sa date de publication si elle est connue — `null` sinon, jamais une
 *      date supposée.
 * Le temps de lecture ne s'écrit PAS : `composer` le calcule sur le texte.
 *
 * Aujourd'hui, un seul article : « Ai-je une idée de business viable ? »,
 * relevé sur le site de la cliente. Son texte vit dans
 * `contenuRessources.ARTICLE_IDEE_BUSINESS_VIABLE` ; il est RÉUTILISÉ ici, pas
 * recopié (règle 5).
 *
 * Éditorial uniquement : aucun prix, aucun montant. Les passerelles de fin de
 * page mènent à l'étape payante la plus proche sans en écrire le tarif.
 */
import {
  ARTICLE_IDEE_BUSINESS_VIABLE,
  ROUTES_RESSOURCES,
  type ElementDArticle,
  type Passerelle,
  type SectionDArticle,
} from "./contenuRessources";

// ── Adresses ────────────────────────────────────────────────────────────────

export const ROUTE_DU_BLOG = "/blog";

/** L'adresse d'un article. Le slug est encodé : il vient d'une liste écrite
 *  ici aujourd'hui, d'une saisie en administration demain. */
export function adresseDeLArticle(slug: string): string {
  return `${ROUTE_DU_BLOG}/${encodeURIComponent(slug)}`;
}

/** Le paramètre d'adresse qui présélectionne un thème sur la liste
 *  (`/blog?theme=financement`) : le fil d'Ariane d'un article y mène. */
export const PARAMETRE_DU_THEME = "theme";

export function adresseDuTheme(theme: SlugDeTheme): string {
  return `${ROUTE_DU_BLOG}?${PARAMETRE_DU_THEME}=${theme}`;
}

// ── Les thèmes : une liste FERMÉE ───────────────────────────────────────────

/** Les cinq thèmes du blog, dans l'ordre des filtres. Un thème sans article
 *  reste affiché, désactivé : la liste dit de quoi parle le blog. */
export const THEMES = [
  { slug: "creation", libelle: "Création" },
  { slug: "statuts", libelle: "Statuts" },
  { slug: "etude-de-marche", libelle: "Étude de marché" },
  { slug: "financement", libelle: "Financement" },
  { slug: "productivite", libelle: "Productivité" },
] as const;

export type SlugDeTheme = (typeof THEMES)[number]["slug"];

export function estUnTheme(valeur: string | null): valeur is SlugDeTheme {
  return THEMES.some((theme) => theme.slug === valeur);
}

export function libelleDuTheme(slug: SlugDeTheme): string {
  const theme = THEMES.find((t) => t.slug === slug);
  // Inatteignable tant que `SlugDeTheme` est déduit de `THEMES` ; écrit pour
  // qu'un thème retiré ne s'affiche jamais sous un libellé vide (règle 1).
  if (!theme) throw new Error(`contenuBlog : thème inconnu « ${slug} »`);
  return theme.libelle;
}

// ── Le type d'un article ────────────────────────────────────────────────────

/** Ce qu'on ÉCRIT pour un article. */
export type SourceDArticle = {
  /** Son adresse : `/blog/<slug>`. Unique dans `ARTICLES`. */
  slug: string;
  titre: string;
  sousTitre: string;
  theme: SlugDeTheme;
  /** La date de publication, au format `AAAA-MM-JJ`. `null` : inconnue —
   *  elle n'est alors ni affichée ni déclarée aux moteurs. Jamais inventée. */
  publieLe: string | null;
  /** Le titre de l'onglet et la méta-description. */
  entete: { titreOnglet: string; description: string };
  /** Le chapô : son intertitre d'ouverture et ses paragraphes. */
  chapo: { intertitre: string; paragraphes: string[] };
  sections: SectionDArticle[];
  conclusion: {
    intertitre: string;
    elements: ElementDArticle[];
    /** La formule qui précède la signature. */
    salut: string;
    signature: string;
  };
  /** L'appel de fin d'article : ce qu'il propose de gratuit, et où. */
  appel: {
    titre: string;
    document: string;
    corps: string;
    bouton: { libelle: string; lien: string };
  };
  /** LA passerelle vers l'étape payante la plus proche du sujet. */
  passerelle: Passerelle;
};

/** Un article tel que les pages le lisent : la source, plus ce qui se
 *  CALCULE sur son texte. */
export type Article = SourceDArticle & {
  /** Le chapô court des cartes : la première phrase du chapô. */
  accroche: string;
  nombreDeMots: number;
  /** En minutes, calculé — voir `MOTS_PAR_MINUTE`. */
  tempsDeLecture: number;
};

// ── Ce qui se calcule sur le texte ──────────────────────────────────────────

/** Le texte d'un élément du corps, amorce et introduction comprises. */
function texteDeLElement(element: ElementDArticle): string[] {
  switch (element.genre) {
    case "paragraphe":
      return [element.texte];
    case "liste":
      return [element.introduction ?? "", ...element.points];
    case "question":
    case "exemple":
      return [element.amorce, element.texte];
  }
}

/** Tout ce qu'un lecteur lit dans l'article, dans l'ordre. */
export function texteDeLArticle(article: SourceDArticle): string[] {
  return [
    article.titre,
    article.sousTitre,
    article.chapo.intertitre,
    ...article.chapo.paragraphes,
    ...article.sections.flatMap((section) => [
      section.intertitre,
      ...section.elements.flatMap(texteDeLElement),
      ...(section.sousSections ?? []).flatMap((sous) => [
        sous.intertitre,
        ...sous.elements.flatMap(texteDeLElement),
      ]),
    ]),
    article.conclusion.intertitre,
    ...article.conclusion.elements.flatMap(texteDeLElement),
    article.conclusion.salut,
    article.conclusion.signature,
  ].filter((phrase) => phrase !== "");
}

/** Un « mot » porte au moins une lettre ou un chiffre : un tiret ou un point
 *  d'interrogation isolés par la typographie française n'en sont pas. */
export function compterLesMots(phrases: string[]): number {
  return phrases
    .join(" ")
    .split(/\s+/)
    .filter((mot) => /[\p{L}\p{N}]/u.test(mot)).length;
}

/** La vitesse de lecture retenue pour un texte courant, en mots par minute. */
export const MOTS_PAR_MINUTE = 200;

/** Le temps de lecture, en minutes entières, arrondi au-dessus : jamais
 *  « 0 min ». */
export function minutesDeLecture(nombreDeMots: number): number {
  return Math.max(1, Math.ceil(nombreDeMots / MOTS_PAR_MINUTE));
}

/** La première phrase d'un paragraphe — jusqu'au premier point, point
 *  d'interrogation ou d'exclamation suivi d'une espace. Sans fin de phrase
 *  trouvée, le paragraphe entier : mieux vaut une accroche longue qu'une
 *  accroche coupée au milieu d'un mot. */
export function premierePhrase(paragraphe: string): string {
  const fin = paragraphe.search(/[.!?](?=\s)/);
  return fin === -1 ? paragraphe : paragraphe.slice(0, fin + 1);
}

/** Fait d'une source un article : calcule l'accroche, le nombre de mots et le
 *  temps de lecture. Un article sans chapô ou sans texte est une erreur
 *  d'écriture, dite au chargement plutôt qu'affichée vide (règle 1). */
export function composer(source: SourceDArticle): Article {
  const premier = source.chapo.paragraphes[0];
  if (source.slug === "" || source.titre === "" || premier === undefined) {
    throw new Error(
      `contenuBlog : l'article « ${source.slug || source.titre} » n'a pas de slug, de titre ou de chapô`,
    );
  }
  const nombreDeMots = compterLesMots(texteDeLArticle(source));
  return {
    ...source,
    accroche: premierePhrase(premier),
    nombreDeMots,
    tempsDeLecture: minutesDeLecture(nombreDeMots),
  };
}

// ── Les articles ────────────────────────────────────────────────────────────

const VIABLE = ARTICLE_IDEE_BUSINESS_VIABLE;

/** Le slug de l'article relevé sur le site. Nommé : la boîte à outils y mène
 *  (« Lire la suite de l'article ») et ne doit pas l'écrire une seconde fois. */
export const SLUG_IDEE_BUSINESS_VIABLE = "idee-business-viable";

/** LA LISTE. Le plus récent en premier : le premier de la liste est mis en
 *  avant, en grand, sur `/blog`. */
export const ARTICLES: Article[] = [
  composer({
    slug: SLUG_IDEE_BUSINESS_VIABLE,
    titre: VIABLE.titre,
    sousTitre: VIABLE.sousTitre,
    // L'article demande si une idée tient « sur le marché » — un vrai besoin,
    // une cible, des clients prêts à payer — et recommande une étude de
    // marché : c'est son thème, et celui de sa passerelle.
    theme: "etude-de-marche",
    // Le relevé du site ne donne aucune date pour cet article.
    publieLe: null,
    // L'article n'a NI titre d'onglet NI méta-description sur le site actuel :
    // ce sont les suggestions de `contenuRessources`, à valider.
    entete: {
      titreOnglet: VIABLE.entete.propose?.titreOnglet ?? VIABLE.titre,
      description: VIABLE.entete.propose?.description ?? VIABLE.sousTitre,
    },
    chapo: VIABLE.chapo,
    sections: VIABLE.sections,
    conclusion: VIABLE.conclusion,
    // Le texte de l'appel est celui de l'article ; son bouton menait à la
    // boîte à outils de l'ancien site, il mène à celle de la plateforme.
    appel: {
      titre: VIABLE.appel.titre,
      document: VIABLE.appel.document,
      corps: VIABLE.appel.corps,
      bouton: {
        libelle: "Ouvrir la boîte à outils",
        lien: ROUTES_RESSOURCES.boiteAOutils,
      },
    },
    passerelle: {
      titre: { avant: "Votre idée tient debout ?", fin: "Vérifiez-le sur votre marché." },
      corps:
        "Un vrai problème, une cible précise, des clients prêts à payer : l'étude de marché EVKHA cherche ces réponses pour votre projet.",
      bouton: { libelle: "Découvrir l'étude de marché", lien: ROUTES_RESSOURCES.etudes },
    },
  }),
];

/** L'article d'un slug, ou `null` : la page dit alors « article introuvable »
 *  au lieu de rendre une page vide. */
export function articleDuSlug(slug: string): Article | null {
  return ARTICLES.find((article) => article.slug === slug) ?? null;
}

// ── Ce que la page de la liste écrit (`/blog`) ──────────────────────────────

/** Écrit pour la plateforme : le site actuel n'a pas de page de blog. À
 *  valider par la cliente. */
export const BLOG = {
  titreOnglet: "Le blog EVKHA – Conseils pour créer et développer votre entreprise",
  description:
    "Création, statuts, étude de marché, financement, productivité : les articles pratiques d'EVKHA pour avancer dans votre projet d'entreprise.",
  surtitre: "Le blog",
  titre: { avant: "Des conseils concrets pour", fin: "bien entreprendre." },
  presentation:
    "Des articles pratiques pour avancer dans votre projet d'entreprise : des questions concrètes, pas des grandes théories.",
  titreDesArticles: "Les articles",
  filtres: {
    /** Le nom accessible du groupe de boutons. */
    nom: "Filtrer les articles par thème",
    tous: "Tous",
  },
  /** Annoncé à chaque changement de filtre. */
  compte: (nombre: number) => (nombre === 1 ? "1 article" : `${nombre} articles`),
  /** Défensif : un thème sans article est désactivé, ce cas ne s'atteint pas
   *  par les boutons. */
  aucun: "Aucun article dans ce thème.",
  aLaUne: "À la une",
  lire: "Lire l'article",
  /** L'espace insécable tient le nombre et son unité sur la même ligne. */
  lecture: (minutes: number) => `${minutes}\u00a0min de lecture`,
  passerelle: {
    titre: { avant: "De la lecture", fin: "à votre projet." },
    corps:
      "Quand vous voudrez des réponses sur votre propre marché, les études EVKHA sont rédigées sur votre projet.",
    bouton: { libelle: "Voir les études", lien: ROUTES_RESSOURCES.etudes },
  } as Passerelle,
};

// ── Ce que la page d'un article écrit (`/blog/$slug`) ───────────────────────

export const PAGE_ARTICLE = {
  /** Les noms accessibles des deux navigations de la page. */
  filDAriane: "Fil d'Ariane",
  blog: "Blog",
  sommaire: "Dans cet article",
  publieLe: "Publié le",
  /** Le nom de la maison d'édition, pour les données structurées. */
  editeur: "EVKHA Business & Formations",
  introuvable: {
    titreOnglet: "Article introuvable – Le blog EVKHA",
    description: "Cet article n'existe pas ou n'est plus en ligne.",
    surtitre: "Le blog",
    titre: { avant: "Article", fin: "introuvable." },
    corps:
      "L'adresse que vous avez suivie ne correspond à aucun article du blog. Il a peut-être changé d'adresse.",
    bouton: "Retour au blog",
  },
};
