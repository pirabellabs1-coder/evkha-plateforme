/** Le texte que les pages publiques refondues ont en commun : la barre, le
 * menu, le pied, le bouton de pause, les phrases qui remplacent un prix.
 *
 * Il vivait dans `contenuAccueil.ts`. Depuis que la page des études porte la
 * même barre et le même pied (`EnTeteSite`, `PiedSite`), il est écrit ICI, une
 * fois, et les pages le lisent (règle 5) : une entrée de menu ajoutée pour
 * l'une apparaît sur les autres sans qu'on y pense.
 *
 * Le menu est un méga-menu : `NAVIGATION` porte ses rubriques, leurs liens et
 * leur carte de mise en avant. La barre, le menu plein écran et le pied le
 * lisent tous les trois.
 *
 * Éditorial uniquement, comme `contenu.ts` : AUCUN PRIX n'est écrit ici. Le
 * test `la-page-des-etudes-lit-ses-prix-au-serveur` verrouille qu'aucun
 * montant en euros ne figure dans ce fichier.
 */
import { CONTACT_EMAIL } from "./contenu";
import { ancreDeLEtude } from "./donnees";

// ── Adresses ────────────────────────────────────────────────────────────────

/** Le slug de l'article relevé sur le site de la cliente. Écrit ICI, une
 *  fois : le blog (`contenuBlog`), la boîte à outils, l'accueil et la
 *  redirection de son ancienne adresse (`router.tsx`) le lisent. */
export const SLUG_IDEE_BUSINESS_VIABLE = "idee-business-viable";

const ETUDES = "/etudes";

/** LES CHEMINS DU SITE PUBLIC — LA SEULE SOURCE (règle 5).
 *
 *  Tout ce qui écrit l'adresse d'une page publique la lit ici : le routeur
 *  (`router.tsx`, `path: CHEMINS.x`), le menu et le pied (`NAVIGATION`,
 *  `PIED`), `LIENS`, et les alias que les fichiers de contenu gardent sous
 *  leurs anciens noms (`ROUTES_PACKS`, `ROUTES_FORMATIONS`,
 *  `ROUTES_RESSOURCES`, `ROUTE_DU_BLOG`, les chemins de `contenuLegal`). Une
 *  page qui change d'adresse change ici, et nulle part ailleurs.
 *
 *  Le test `chaque-lien-du-site-a-sa-route` verrouille que chaque chemin
 *  d'ici a sa route dans le routeur.
 *
 *  `as const` : le routeur a besoin de chemins littéraux pour typer ses
 *  routes. Tous INTERNES. */
export const CHEMINS = {
  accueil: "/",
  etudes: ETUDES,
  boutique: "/boutique",
  partenaires: "/partenaires",
  /** La porte des clients déjà inscrits (`espace/routes.tsx`). */
  espaceClient: "/espace/connexion",
  contact: "/contact",
  packs: "/packs",
  packEssentiel: "/packs/essentiel",
  packPremium: "/packs/premium",
  formations: "/formations",
  formationSocietes: "/formations/creer-son-entreprise",
  formationMicro: "/formations/creer-sa-micro-entreprise",
  formationPop: "/formations/methode-pop",
  swapn: "/swapn",
  boiteAOutils: "/boite-a-outils",
  blog: "/blog",
  /** Le GABARIT de la route d'un article, tel que le routeur l'écrit. Pour
   *  l'adresse d'un article donné : `adresseDeLArticle(slug)`. */
  article: "/blog/$slug",
  mentionsLegales: "/mentions-legales",
  rgpd: "/rgpd",
  cgv: "/cgv",
  confidentialite: "/politique-de-confidentialite",
  /** La section « Comment ça marche » de la page des études
   *  (`NosEtudes.tsx`, `id="comment-ca-marche"`). */
  commentCaMarche: `${ETUDES}#comment-ca-marche`,
} as const;

/** Le chemin de la page d'accueil. */
export const ACCUEIL = CHEMINS.accueil;

/** L'adresse d'un article du blog. Le slug est encodé : il vient d'une liste
 *  écrite dans le dépôt aujourd'hui, d'une saisie en administration demain. */
export function adresseDeLArticle(slug: string): string {
  return `${CHEMINS.blog}/${encodeURIComponent(slug)}`;
}

/** Les adresses que les pages citent par leur usage. Les chemins internes
 *  sont LUS dans `CHEMINS` ; seuls la prise de rendez-vous et le courriel, qui
 *  sortent de la plateforme, sont écrits ici — une fois (`contenuRessources`
 *  lit `LIENS.appel` pour sa page de contact).
 *
 *  Typé large (`string`) : ce sont des adresses à poser dans un `href`, pas
 *  des chemins de route. */
export const LIENS: Record<
  | "etudes"
  | "boutique"
  | "partenaires"
  | "espace"
  | "appel"
  | "courriel"
  | "packs"
  | "formations"
  | "outils"
  | "article",
  string
> = {
  etudes: CHEMINS.etudes,
  boutique: CHEMINS.boutique,
  partenaires: CHEMINS.partenaires,
  espace: CHEMINS.espaceClient,
  appel: "https://calendly.com/contact-evkha",
  courriel: `mailto:${CONTACT_EMAIL}`,
  packs: CHEMINS.packs,
  formations: CHEMINS.formations,
  outils: CHEMINS.boiteAOutils,
  article: adresseDeLArticle(SLUG_IDEE_BUSINESS_VIABLE),
};

/** Les réseaux de la cliente, relevés sur l'accueil de son site. Écrits ICI,
 *  une fois : le pied (`PIED.reseaux`) et la page de contact
 *  (`contenuRessources.COORDONNEES.reseaux`) lisent cette liste. */
export const RESEAUX_SOCIAUX = [
  {
    libelle: "LinkedIn",
    lien: "https://www.linkedin.com/in/evangeline-strobbe-khaili-54a2511b2/",
  },
  {
    libelle: "Instagram",
    lien: "https://www.instagram.com/evkha_business_formations/",
  },
  {
    libelle: "Facebook",
    lien: "https://www.facebook.com/profile.php?id=61577284710257",
  },
] as const;

/** L'adresse de la carte d'une étude, sur la page des études. L'ancre est
 *  `donnees.ancreDeLEtude`, celle que `NosEtudes.tsx` pose sur chaque carte :
 *  écrite une fois.
 *
 *  Les cartes ne sont montées qu'une fois le catalogue reçu : la page des
 *  études défile alors jusqu'à la carte visée (`NosEtudes`, au premier
 *  catalogue reçu). Sans catalogue, le visiteur reste en haut de la page — au
 *  bon endroit, pas sur un lien mort. */
export function carteDEtude(slug: string): string {
  return `${LIENS.etudes}#${ancreDeLEtude(slug)}`;
}

/** L'identifiant du contenu principal, visé par le lien d'évitement. Écrit une
 *  fois : le lien (`EnTeteSite`) et sa cible (`<main>` de chaque page) le
 *  lisent ici, et ne peuvent pas se désaccorder. */
export const ID_DU_CONTENU = "acc-contenu";

export const EVITEMENT = "Aller au contenu";

// ── Navigation ──────────────────────────────────────────────────────────────

/** Une entrée simple de la barre. Deux formes, jamais les deux à la fois :
 *
 *  - `lien` : une page. Elle est « courante » quand son chemin est celui de la
 *    page affichée — `EnTeteSite` le DÉDUIT de l'adresse :
 *    un drapeau écrit ici annoncerait « vous êtes ici » sur la mauvaise page.
 *  - `ancre` : une SECTION DE L'ACCUEIL, par son identifiant. Sur l'accueil,
 *    l'entrée reste une ancre (`#methode`) et la page défile ; ailleurs, elle
 *    mène à l'accueil, à cette section (`/#methode`). Voir `adresseDe`
 *    (`site.ts`). Plus aucune entrée du menu n'a cette forme depuis le
 *    méga-menu ; elle reste pour qui en aurait l'usage. */
export type EntreeDeNavigation = {
  libelle: string;
  /** Cerclée dans la barre : c'est la porte des clients déjà inscrits. */
  compte?: boolean;
} & ({ lien: string; ancre?: undefined } | { ancre: string; lien?: undefined });

/** Un lien d'un panneau : son titre, et UNE ligne qui dit ce qu'on y trouve.
 *  Courte et factuelle. Jamais un prix : ils viennent du serveur ou des
 *  pages. */
export type LienDeRubrique = {
  libelle: string;
  description: string;
  lien: string;
};

/** La carte de mise en avant d'un panneau : un message et un bouton. */
export type MiseEnAvant = {
  titre: string;
  corps: string;
  bouton: string;
  lien: string;
};

/** Une rubrique du méga-menu : un bouton dans la barre, qui ouvre un panneau.
 *
 *  `id` : sert aux identifiants du DOM (`aria-controls`). Minuscules, sans
 *  espace, unique.
 *  `court` : le DÉBUT du libellé, seul affiché quand la barre est étroite
 *  (voir `.acc-rubrique-suite`, `Site.css`). Le libellé doit commencer par
 *  lui — le test de l'en-tête le verrouille. */
export type Rubrique = {
  id: string;
  libelle: string;
  court?: string;
  liens: LienDeRubrique[];
  enAvant: MiseEnAvant;
};

/** Le menu du site, écrit UNE fois. Trois lecteurs, sur toutes les pages qui
 *  portent `EnTeteSite` et `PiedSite` : la barre (un bouton et un panneau par
 *  rubrique), le menu plein écran du téléphone (un accordéon), et le pied
 *  (une colonne par rubrique). Une entrée ajoutée ici apparaît aux trois
 *  endroits (règle 5).
 *
 *  Cinq rubriques : au-delà, la barre ne tient plus sur une ligne à 1001 px.
 *  AUCUN PRIX, et aucun lien vers l'ancien site. */
export const NAVIGATION: Rubrique[] = [
  {
    id: "etudes",
    libelle: "Études & livrables",
    court: "Études",
    liens: [
      {
        libelle: "Étude de marché",
        description: "Mon idée est-elle faisable ?",
        lien: carteDEtude("etude-marche"),
      },
      {
        libelle: "Étude de la concurrence",
        description: "Face à qui ?",
        lien: carteDEtude("etude-concurrence"),
      },
      {
        libelle: "Business plan",
        description: "Convaincre la banque",
        lien: carteDEtude("business-plan"),
      },
      {
        libelle: "Stratégie business",
        description: "Passer à l'action",
        lien: carteDEtude("strategie-business"),
      },
      {
        libelle: "Études prêtes à télécharger",
        description: "Des études déjà rédigées, classées par thème.",
        lien: LIENS.boutique,
      },
      {
        libelle: "Comment ça marche",
        description: "De la commande à la réception du document.",
        lien: CHEMINS.commentCaMarche,
      },
    ],
    enAvant: {
      titre: "Un projet, quatre documents",
      corps: "Du marché à la stratégie : chaque document prépare le suivant.",
      bouton: "Voir les études",
      lien: LIENS.etudes,
    },
  },
  {
    id: "accompagnement",
    libelle: "Accompagnement",
    liens: [
      {
        libelle: "Les packs d'accompagnement",
        description: "Les deux packs, présentés côte à côte.",
        lien: CHEMINS.packs,
      },
      {
        libelle: "Pack Création Essentiel",
        description: "Les documents clés attendus par les banques.",
        lien: CHEMINS.packEssentiel,
      },
      {
        libelle: "Pack Création Premium",
        description: "Les documents, et un suivi pour piloter le projet.",
        lien: CHEMINS.packPremium,
      },
      {
        libelle: "Réserver un appel gratuit",
        description: "Un premier échange, à réserver en ligne.",
        lien: LIENS.appel,
      },
    ],
    enAvant: {
      titre: "Deux packs pour lancer votre entreprise",
      corps: "Des documents concrets et un accompagnement personnalisé.",
      bouton: "Comparer les packs",
      lien: CHEMINS.packs,
    },
  },
  {
    id: "formations",
    libelle: "Formations",
    liens: [
      {
        libelle: "Toutes les formations",
        description: "Le catalogue des trois formations.",
        lien: CHEMINS.formations,
      },
      {
        libelle: "Créer son entreprise de A à Z",
        description: "EI, EURL, SARL, SASU, SAS : tous les statuts hors micro.",
        lien: CHEMINS.formationSocietes,
      },
      {
        libelle: "Créer sa micro-entreprise de A à Z",
        description: "De l'idée à la première facture.",
        lien: CHEMINS.formationMicro,
      },
      {
        libelle: "Méthode P.O.P IA",
        description: "Planifier, organiser, produire.",
        lien: CHEMINS.formationPop,
      },
    ],
    enAvant: {
      titre: "Se former pour créer",
      corps: "Société, micro-entreprise ou organisation : à chacun sa formation.",
      bouton: "Découvrir les formations",
      lien: CHEMINS.formations,
    },
  },
  {
    id: "professionnels",
    libelle: "Professionnels",
    liens: [
      {
        libelle: "Abonnements pour les professionnels",
        description: "Les dossiers de vos clients, produits sous votre marque.",
        lien: LIENS.partenaires,
      },
      {
        libelle: "Notre partenaire Swapn",
        description: "Une mise en relation gratuite pour créer votre entreprise.",
        lien: CHEMINS.swapn,
      },
    ],
    enAvant: {
      titre: "Vous accompagnez des créateurs ?",
      corps: "Un abonnement pour produire leurs dossiers sous votre marque.",
      bouton: "Voir les abonnements",
      lien: LIENS.partenaires,
    },
  },
  {
    id: "ressources",
    libelle: "Ressources",
    liens: [
      {
        libelle: "Boîte à outils",
        description: "Une checklist et un lexique à télécharger gratuitement.",
        lien: CHEMINS.boiteAOutils,
      },
      {
        libelle: "Blog",
        description: "Des articles pour mûrir votre projet.",
        lien: CHEMINS.blog,
      },
      {
        libelle: "Contact",
        description: "Une question ? Écrivez-nous.",
        lien: CHEMINS.contact,
      },
    ],
    enAvant: {
      titre: "Une question sur votre projet ?",
      corps: "Écrivez-nous, ou réservez un appel gratuit.",
      bouton: "Nous écrire",
      lien: CHEMINS.contact,
    },
  },
];

/** La porte des clients déjà inscrits : à droite de la barre, cerclée. */
export const ESPACE_CLIENT: EntreeDeNavigation = {
  libelle: "Espace client",
  lien: LIENS.espace,
  compte: true,
};

/** Le bouton noir de la barre. Le contact est désormais une page. */
export const APPEL_DE_LA_BARRE: EntreeDeNavigation = {
  libelle: "Me contacter",
  lien: CHEMINS.contact,
};

/** Ce qui reste visible en bas du menu plein écran, sous l'accordéon.
 *
 *  « Me contacter » n'y est PAS répété : le bouton de la barre reste affiché
 *  au-dessus du menu ouvert, à toutes les largeurs. Le répéter ici ferait deux
 *  liens du même nom à l'écran — et `l-accueil-lit-ses-prix-au-serveur`
 *  cherche celui de la barre par son nom, menu ouvert. Pour l'ajouter quand
 *  même : inscrire `APPEL_DE_LA_BARRE` dans cette liste, et viser dans ce
 *  test le lien de la barre par son conteneur. */
export const PIED_DU_MENU: EntreeDeNavigation[] = [ESPACE_CLIENT];

export const BARRE = {
  logo: "Evkha",
  /** Le nom accessible du logo : il mène à l'accueil. */
  nomDuLogo: "EVKHA, accueil",
  nomDeLaBarre: "Principale",
  nomDuMenu: "Menu",
  ouvrirLeMenu: "Ouvrir le menu",
  fermerLeMenu: "Fermer le menu",
};

/** Le bouton qui arrête tout ce qui tourne en boucle. Plusieurs exemplaires
 *  possibles sur une page, un seul état. */
export const PAUSE = {
  arreter: "Mettre les animations en pause",
  relancer: "Relancer les animations",
};

// ── Ce qu'une page écrit à la place d'un prix ───────────────────────────────

/** Ce que la page écrit à la place d'un prix qu'elle n'a pas. Trois états,
 *  trois phrases : un chargement, une panne et une absence ne se confondent
 *  pas (règle 1).
 *
 *  `absent` : le catalogue a répondu, et il ne porte pas cette offre. La
 *  carte le dit et son bouton est neutralisé — renvoyer vers une page où
 *  l'offre n'est pas non plus serait promettre un prix qui n'existe pas. */
export const TARIFS = {
  attente: "Tarif en cours de chargement…",
  panne: "Tarif momentanément indisponible",
  absent: "Indisponible pour le moment",
  alerte: "Les tarifs sont momentanément indisponibles.",
  alerteSuite: "Écrivez-nous à",
  /** Dans une section, sous l'alerte unique du haut de page. */
  rappel: "Tarifs momentanément indisponibles : la page les affichera dès leur retour.",
};

// ── Pied de page ────────────────────────────────────────────────────────────

export const PIED = {
  droits: "EVKHA. Tous droits réservés.",
  signature: "EVKHA Business & Formations · Lille",
  /** Le nom de la navigation qui reprend les rubriques du menu, en colonnes.
   *  Ses liens ne sont pas écrits ici : le pied lit `NAVIGATION`. */
  plan: "Plan du site",
  navigation: "Informations légales",
  /** Les pages légales de la plateforme : internes, comme tout le menu. */
  liens: [
    { libelle: "Mentions légales", lien: CHEMINS.mentionsLegales },
    { libelle: "RGPD", lien: CHEMINS.rgpd },
    { libelle: "CGV", lien: CHEMINS.cgv },
    { libelle: "Confidentialité", lien: CHEMINS.confidentialite },
  ],
  /** Les réseaux de la cliente : `RESEAUX_SOCIAUX`, plus haut. */
  reseauxTitre: "Réseaux sociaux",
  reseaux: RESEAUX_SOCIAUX,
};

// ── L'identité déclarée aux moteurs ─────────────────────────────────────────

/** L'ADRESSE PUBLIQUE DU SITE, écrite une fois (règle 5). Les adresses
 *  canoniques, le plan du site, `robots.txt`, `llms.txt` et les données
 *  structurées la lisent ici.
 *
 *  Écrite en dur, et pas lue dans `window.location.origin` : une copie du
 *  site servie à une autre adresse (un déploiement d'essai) doit désigner
 *  CELLE-CI comme l'originale, sinon les moteurs voient deux sites. Le
 *  domaine nu, sans `www` — celui vers lequel `nginx.conf` renvoie. */
export const ORIGINE_DU_SITE = "https://evkha.fr";

/** L'adresse complète d'une page du site, pour un moteur. L'accueil garde sa
 *  barre oblique ; les autres pages n'en portent pas à la fin. */
export function adresseAbsolue(chemin: string): string {
  return `${ORIGINE_DU_SITE}${chemin}`;
}

/** Ce que les données structurées disent de l'entreprise. RIEN n'est inventé :
 *  chaque valeur est celle que les mentions légales du site publient déjà
 *  (`contenuLegal`), et le test `le-referencement-dit-vrai` verrouille que le
 *  siège écrit ici est bien celui qu'elles donnent. Pas de téléphone : le site
 *  n'en publie aucun. */
export const IDENTITE = {
  nom: "EVKHA Business & Formations",
  /** La fondatrice, dans l'écriture du reste du site (`AUTEUR_DU_BLOG`). */
  fondatrice: "Evangeline Khaili",
  siege: {
    rue: "41 rue Jacquemars Giélée",
    codePostal: "59800",
    ville: "Lille",
    pays: "FR",
  },
  /** Le logo carré servi par le site (`frontend/public/icon-512.png`). */
  logo: "/icon-512.png",
  /** L'image de partage par défaut (`frontend/public/og-evkha.png`). */
  imageDePartage: "/og-evkha.png",
} as const;

// ── Le titre de l'onglet ────────────────────────────────────────────────────

/** La marque, telle qu'elle FERME le titre de l'onglet de chaque page :
 *  « Titre de la page — EVKHA ». La mise en forme est dans
 *  `site.titreDOnglet` ; les pages n'écrivent que leur titre. */
export const MARQUE = "EVKHA";

// ── La page introuvable ─────────────────────────────────────────────────────

/** Ce que le site affiche à une adresse qu'il ne connaît pas
 *  (`Introuvable.tsx`, branchée en `defaultNotFoundComponent` du routeur).
 *  Écrit pour la plateforme. Aucun prix : des portes, pas des offres. */
export const PAGE_INTROUVABLE = {
  titreOnglet: "Page introuvable",
  description: "Cette page n'existe pas ou n'est plus en ligne.",
  surtitre: "Erreur 404",
  titre: { avant: "Page", fin: "introuvable." },
  corps:
    "L'adresse que vous avez suivie ne correspond à aucune page du site. Elle a peut-être changé d'adresse.",
  accueil: { libelle: "Retour à l'accueil", lien: CHEMINS.accueil },
  /** Le nom accessible de la liste des trois portes. */
  nomDesPortes: "Pages les plus demandées",
  portes: [
    { libelle: "Voir les études", lien: CHEMINS.etudes },
    { libelle: "Parcourir la boutique", lien: CHEMINS.boutique },
    { libelle: "Nous contacter", lien: CHEMINS.contact },
  ],
};
