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

// ── Adresses ────────────────────────────────────────────────────────────────

/** Le chemin de la page d'accueil. */
export const ACCUEIL = "/";

export const LIENS = {
  etudes: "/etudes",
  boutique: "/boutique",
  partenaires: "/partenaires",
  espace: "/espace/connexion",
  appel: "https://calendly.com/contact-evkha",
  courriel: `mailto:${CONTACT_EMAIL}`,
  packs: "/packs",
  formations: "/formations",
  outils: "/boite-a-outils",
  article: "/blog/idee-business-viable",
};

/** Les chemins des pages que le menu et le pied desservent, en plus de ceux de
 *  `LIENS`. Tous INTERNES : le menu ne renvoie plus vers l'ancien site.
 *
 *  `LIENS.packs`, `LIENS.formations`, `LIENS.outils` et `LIENS.article`
 *  visent encore l'ancien site : `contenuAccueil.ts` les lit pour les cartes
 *  de l'accueil. Ils ne sont pas renommés ici (les pages les importent) ; le
 *  jour où l'accueil bascule, c'est vers ces chemins-ci. */
export const CHEMINS = {
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
  mentionsLegales: "/mentions-legales",
  rgpd: "/rgpd",
  cgv: "/cgv",
  confidentialite: "/politique-de-confidentialite",
  /** La section « Comment ça marche » de la page des études
   *  (`NosEtudes.tsx`, `id="comment-ca-marche"`). */
  commentCaMarche: `${LIENS.etudes}#comment-ca-marche`,
} as const;

/** L'adresse de la carte d'une étude, sur la page des études.
 *
 *  `NosEtudes.tsx` pose `id="carte-<slug>"` sur chaque carte (sa fonction
 *  `ancreDe`, qui n'est pas exportée) : le préfixe est donc écrit DEUX fois,
 *  là-bas et ici. Le test de l'en-tête verrouille que les slugs du menu sont
 *  ceux du parcours ; le préfixe, lui, n'est tenu que par cette phrase.
 *
 *  Les cartes ne sont montées qu'une fois le catalogue reçu : un visiteur qui
 *  arrive d'une autre page avant ce moment reste en haut de la page des
 *  études — au bon endroit, pas sur un lien mort. */
export function carteDEtude(slug: string): string {
  return `${LIENS.etudes}#carte-${slug}`;
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
 *    page affichée — `EnTeteSite` le DÉDUIT de l'adresse, comme `MenuSite` :
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
        description: "Mon idée tient-elle ?",
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
        libelle: "Méthode P.O.P",
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
        description: "Une checklist et un lexique à télécharger.",
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
  /** Les réseaux de la cliente, relevés sur l'accueil de son site. */
  reseauxTitre: "Réseaux sociaux",
  reseaux: [
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
  ],
};
