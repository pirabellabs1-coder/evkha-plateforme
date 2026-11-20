/** Le texte de la page d'accueil publique (`Accueil.tsx`).
 *
 * Éditorial uniquement, comme `contenu.ts` : des arguments de vente, pas des
 * données. AUCUN PRIX n'est écrit ici — ni « dès », ni fourchette, ni tarif
 * d'abonnement. Ils sont lus dans l'API par la page et calculés sur ce qu'elle
 * rend (règle 5) ; le test `l-accueil-lit-ses-prix-au-serveur` verrouille
 * qu'aucun montant en euros ne figure dans ce fichier.
 *
 * La structure et l'ordre des sections sont ceux de la maquette validée par la
 * cliente, complétés des sections de son site actuel (`www.evkha.fr`, relevé
 * dans `docs/refonte/inventaire-site-evkha.md`). Les TEXTES et les OFFRES
 * suivent la stratégie commerciale et le catalogue réellement vendu par la
 * plateforme : la maquette portait du contenu d'essai, dont des packs et des
 * formations que la plateforme ne vend pas. Ceux-là sont présentés SANS prix,
 * avec un renvoi vers le site où ils se réservent.
 *
 * Ce qui existe déjà ailleurs n'est pas réécrit ici : le nombre de chapitres
 * vient de `contenu.ETUDES`, l'engagement des abonnements de
 * `espace/engagement.ts`. Deux écritures d'un même fait finissent par ne plus
 * dire la même chose.
 *
 * Pour la même raison, ce que l'accueil PARTAGE avec la page des études — les
 * adresses (`LIENS`), la barre et son menu, le pied, le bouton de pause, les
 * phrases qui remplacent un prix (`TARIFS`) — a quitté ce fichier pour
 * `contenuSite.ts`, que les deux pages lisent.
 */
import { ARRET_EN_UNE_LIGNE } from "../espace/engagement";
import { CONTACT_EMAIL, ETUDES } from "./contenu";
import { LIENS } from "./contenuSite";

/** Les quatre livrables sur mesure, par leur `type` côté serveur
 *  (`LivrablePublic.type`). C'est la clé qui relie un texte d'ici à un prix et
 *  à un slug de commande venus de l'API. */
export type TypeDeLivrable =
  | "market_study"
  | "competitor_study"
  | "business_plan"
  | "business_strategy";

/** Le nombre de chapitres ANNONCÉ d'un livrable, lu dans `contenu.ETUDES`.
 *
 *  Une clé inconnue LÈVE une erreur au chargement du module : rendre zéro ou
 *  une chaîne vide laisserait la page afficher « chapitres » sans nombre, ou
 *  rien du tout, sans que personne le voie (règle 1). L'erreur, elle, casse
 *  les tests de la page à la première exécution. */
function chapitresAnnonces(cle: string): number {
  const chapitres = ETUDES[cle]?.chapitres;
  if (typeof chapitres !== "number" || !(chapitres > 0)) {
    throw new Error(
      `contenuAccueil : aucun nombre de chapitres dans contenu.ETUDES["${cle}"]`,
    );
  }
  return chapitres;
}

/** Le nombre que la page répète (chiffres, mosaïque, questions, études
 *  prêtes) : celui de l'étude de marché, écrit une seule fois dans
 *  `contenu.ts`. */
export const CHAPITRES_ETUDE_DE_MARCHE = chapitresAnnonces("etude-marche");

/** La relecture, dans les mots déjà en ligne sur la page des études
 *  (`contenu.ETUDES_PAGE.comparatif.pied`, première phrase). Citée à
 *  l'identique et non importée : la phrase d'origine se poursuit par une
 *  opposition aux textes « générés à la chaîne », que l'accueil ne reprend
 *  pas. Le test de l'accueil vérifie que les deux écritures restent la même. */
export const RELECTURE =
  "Chaque étude est relue avant envoi par Evangeline elle-même.";

/** Toutes les images de l'accueil, et nulle part ailleurs.
 *
 *  Elles sont servies par la plateforme, depuis `public/accueil/`, comme
 *  `contenu.ts` sert les siennes depuis `public/partenaires/`. Elles venaient
 *  du site de la cliente (systeme.io, adresses relevées dans
 *  `docs/refonte/images-site-evkha.json`) : la page d'accueil dépendait donc
 *  du site qu'elle remplace, et aurait perdu ses douze images à sa fermeture.
 *  Rapatriées le 19/11/2026, converties en WebP (1,1 Mo → 240 Ko au total).
 *
 *  Les dimensions ne sont annoncées que là où elles servent à réserver la
 *  place (logos, visuel des formations) : elles donnent le RATIO, que la
 *  conversion a conservé. Les autres images sont logées dans une boîte dont
 *  la feuille déclare la hauteur — rien ne saute. */
const DOSSIER = "/accueil";

export const IMAGES_ACCUEIL = {
  portrait: `${DOSSIER}/portrait.webp`,
  /** Bandeau de visages, recadré en quatre médaillons par la feuille. */
  visages: `${DOSSIER}/visages.webp`,
  idee: `${DOSSIER}/profil-idee.webp`,
  freelance: `${DOSSIER}/profil-freelance.webp`,
  rebond: `${DOSSIER}/profil-rebond.webp`,
  microEntreprise: `${DOSSIER}/profil-micro-entreprise.webp`,
  partenaire: `${DOSSIER}/profil-partenaire.webp`,
  logoLegalPlace: `${DOSSIER}/logo-legalplace.webp`,
  logoInitiativeFrance: `${DOSSIER}/logo-initiative-france.webp`,
  logoSwapn: `${DOSSIER}/logo-swapn.webp`,
  logoYyyours: `${DOSSIER}/logo-yyyours.webp`,
  formations: `${DOSSIER}/formations.webp`,
};

// ── Ouverture ───────────────────────────────────────────────────────────────

export const OUVERTURE = {
  /** « Plus de 15 ans », et non « 16 ans » : le site de la cliente écrit les
   *  deux selon les pages, et elle n'a pas tranché (point 4 des questions
   *  ouvertes du plan de refonte). La formule basse est vraie dans les deux
   *  cas. */
  surtitre: "Méthode EVKHA · plus de 15 ans de terrain",
  titre: {
    avant: "Transformez votre",
    /** Le mot qui tourne. Le premier est celui que lit un lecteur d'écran. */
    mots: ["idée", "projet", "envie"],
    milieu: "en entreprise",
    fin: "qui tient debout.",
  },
  /** La promesse au porteur de projet (stratégie commerciale). */
  promesse:
    "Le dossier que votre banque ou votre conseiller attend, écrit pour votre projet et votre zone, relu avant envoi, reçu sous 24 heures ouvrées.",
  boutonPrincipal: { libelle: "Commander une étude", lien: LIENS.etudes },
  boutonSecondaire: { libelle: "Réserver un appel gratuit", lien: LIENS.appel },
  /** Le second public, visible dès l'ouverture. */
  professionnels: {
    question: "Vous accompagnez des créateurs ?",
    reponse: "EVKHA produit le dossier sous votre marque.",
    lien: LIENS.partenaires,
  },
  preuve: { valeur: "500+", libelle: "entrepreneurs formés et accompagnés" },
  altPortrait: "Evangeline Khaili, fondatrice d'EVKHA",
  /** Les deux pastilles en orbite : un nom, et le prix lu dans l'API. */
  pastilles: [
    { type: "market_study", libelle: "Étude de marché" },
    { type: "business_plan", libelle: "Business plan" },
  ] as { type: TypeDeLivrable; libelle: string }[],
};

/** Bandeau défilant. Décoratif (masqué aux lecteurs d'écran) : il ne nomme
 *  que ce que la plateforme vend. */
export const RUBAN = [
  "Étude de marché",
  "Étude de la concurrence",
  "Business plan",
  "Stratégie business",
  "Études prêtes à télécharger",
  "Abonnements professionnels",
  "À vos couleurs",
];

// ── Ils me font confiance ───────────────────────────────────────────────────

/** Les quatre structures affichées sur l'accueil du site actuel, sous le même
 *  titre. `largeur` × `hauteur` : les dimensions des fichiers, relevées sur le
 *  site — elles réservent la place de chaque logo avant son chargement. */
export const CONFIANCE = {
  titre: "Ils me font confiance",
  logos: [
    {
      nom: "LegalPlace",
      image: IMAGES_ACCUEIL.logoLegalPlace,
      largeur: 870,
      hauteur: 198,
    },
    {
      nom: "Réseau Initiative France",
      image: IMAGES_ACCUEIL.logoInitiativeFrance,
      largeur: 1388,
      hauteur: 646,
    },
    {
      nom: "Swapn",
      image: IMAGES_ACCUEIL.logoSwapn,
      largeur: 404,
      hauteur: 402,
    },
    {
      nom: "Yyyours",
      image: IMAGES_ACCUEIL.logoYyyours,
      largeur: 208,
      hauteur: 226,
    },
  ],
};

// ── Le parcours : un projet, quatre documents ───────────────────────────────

/** Les quatre livrables d'un même projet, DANS CET ORDRE — celui du projet,
 *  pas celui des prix. Pas de total ni de lot : la plateforme ne vend pas de
 *  pack. */
export type Marche = {
  type: TypeDeLivrable;
  /** La question que se pose le porteur à cette étape. */
  question: string;
  document: string;
  corps: string;
};

export const PARCOURS = {
  surtitre: "Le parcours",
  titre: { avant: "Un projet,", fin: "quatre documents." },
  corps:
    "Chaque marche prépare la suivante : le marché d'abord, la concurrence ensuite, puis le dossier pour la banque et le plan d'action. Vous commandez celle dont vous avez besoin, quand vous en avez besoin.",
  etiquetteQuestion: "Étape",
  etiquetteDocument: "Le document",
  marches: [
    {
      type: "market_study",
      question: "Mon idée tient-elle ?",
      document: "Étude de marché",
      corps:
        "La taille du marché, sa tendance, vos clients et les risques du projet, sur votre secteur et dans votre zone.",
    },
    {
      type: "competitor_study",
      question: "Face à qui ?",
      document: "Étude de la concurrence",
      corps:
        "Vos concurrents directs et indirects analysés un par un : prix, services, points forts, faiblesses.",
    },
    {
      type: "business_plan",
      question: "Convaincre la banque",
      document: "Business plan",
      corps:
        "Votre projet présenté comme un financeur aime le lire : marché, clients, prix, plan d'action, prévisions financières.",
    },
    {
      type: "business_strategy",
      question: "Passer à l'action",
      document: "Stratégie business",
      corps:
        "Vos priorités, votre positionnement et des recommandations que vous pouvez appliquer sans connaissance technique.",
    },
  ] as Marche[],
};

// ── Comment ça marche ───────────────────────────────────────────────────────

/** Trois étapes, numérotées parce qu'elles se suivent : choisir, décrire,
 *  recevoir. Les délais et les formats sont ceux de la page des études. */
export const COMMENT = {
  surtitre: "Comment ça marche",
  titre: { avant: "Trois étapes,", fin: "un dossier." },
  corps:
    "Vous commandez en ligne, vous nous parlez de votre projet, vous recevez votre document. Pas besoin d'être expert.",
  etapes: [
    {
      titre: "Choisissez votre document",
      corps:
        "Étude de marché, étude de la concurrence, business plan ou stratégie business : selon l'étape où en est votre projet.",
    },
    {
      titre: "Répondez au questionnaire",
      corps:
        "15 à 20 minutes pour décrire votre projet, votre zone et votre cible.",
    },
    {
      titre: "Recevez votre dossier",
      corps:
        "Sous 24 heures ouvrées, relu avant envoi, en PDF et en Word modifiable, à vos couleurs.",
    },
  ],
  bouton: { libelle: "Choisir mon document", lien: LIENS.etudes },
};

// ── L'atelier : le document à vos couleurs ──────────────────────────────────

export const ATELIER = {
  surtitre: "Études & livrables",
  titre: { avant: "Votre document,", fin: "à vos couleurs." },
  corps:
    "Vous répondez à un questionnaire de 15 à 20 minutes, vous recevez votre livrable par e-mail sous 24 heures ouvrées, en PDF et en Word. Essayez : choisissez un document et une couleur.",
  groupeDocuments: "Choisir un livrable",
  groupeTeintes: "Couleur du document",
  invitationTeinte: "La couleur de votre marque :",
  bouton: { libelle: "Commander mon étude", lien: LIENS.etudes },
  bulle: { delai: "Livré sous 24 heures ouvrées", formats: "PDF et Word" },
  feuille: { logo: "Votre logo", signature: "Votre entreprise" },
  /** `chapitres` : le nombre ANNONCÉ, lu dans `contenu.ETUDES`. Il n'est pas
   *  le même d'un livrable à l'autre, et l'écrire ici une seconde fois le
   *  ferait diverger de la page des études. */
  documents: [
    {
      type: "market_study",
      chapitres: CHAPITRES_ETUDE_DE_MARCHE,
      titre: "Étude de marché",
      sous: "Votre secteur, chiffres à l'appui",
      barres: [30, 46, 58, 74, 100],
    },
    {
      type: "competitor_study",
      chapitres: chapitresAnnonces("etude-concurrence"),
      titre: "Étude de la concurrence",
      sous: "Qui est déjà en place, et à quel prix",
      barres: [88, 52, 70, 40, 62],
    },
    {
      type: "business_plan",
      chapitres: chapitresAnnonces("business-plan"),
      titre: "Business plan",
      sous: "Le dossier qui convainc une banque",
      barres: [22, 38, 60, 82, 100],
    },
    {
      type: "business_strategy",
      chapitres: chapitresAnnonces("strategie-business"),
      titre: "Stratégie business",
      sous: "Vos priorités et votre plan d'action",
      barres: [60, 84, 48, 92, 70],
    },
  ] as {
    type: TypeDeLivrable;
    chapitres: number;
    titre: string;
    sous: string;
    barres: number[];
  }[],
  /** Les couleurs à essayer. `jeton` est une propriété de `tokens.css` : la
   *  valeur n'est écrite que là-bas. */
  teintes: [
    { nom: "Jaune", jeton: "var(--evkha-or)" },
    { nom: "Corail", jeton: "var(--evkha-corail)" },
    { nom: "Vert", jeton: "var(--evkha-atelier-vert)" },
    { nom: "Bleu", jeton: "var(--evkha-atelier-bleu)" },
    { nom: "Prune", jeton: "var(--evkha-atelier-prune)" },
  ],
};

// ── Chiffres ────────────────────────────────────────────────────────────────

/** REPRIS DU SITE DE LA CLIENTE, NON VÉRIFIÉS. Ces chiffres figurent sur
 *  `evkha.fr` (accueil et page partenaires) et dans le plan de refonte ; aucun
 *  n'a été recompté. S'ils changent, ils changent ici — sauf le nombre de
 *  chapitres, qui vient de `contenu.ETUDES`.
 *
 *  L'ancienneté n'y figure pas en chiffre : « 16 ans » ou « plus de 15 ans »,
 *  la cliente n'a pas tranché — voir `OUVERTURE.surtitre`. */
export type Chiffre = {
  /** La valeur vers laquelle le compteur monte. */
  valeur: number;
  avant?: string;
  apres?: string;
  libelle: string;
};

export const CHIFFRES: Chiffre[] = [
  { valeur: 500, apres: "+", libelle: "entrepreneurs formés et accompagnés" },
  { valeur: 250, apres: "+", libelle: "dossiers livrés" },
  {
    valeur: CHAPITRES_ETUDE_DE_MARCHE,
    libelle: "chapitres dans une étude de marché",
  },
  {
    valeur: 24,
    avant: "sous",
    apres: " h",
    libelle: "ouvrées pour recevoir votre livrable",
  },
];

// ── À qui ça s'adresse ──────────────────────────────────────────────────────

export const POUR_QUI = {
  surtitre: "À qui ça s'adresse",
  titre: { avant: "Cinq profils,", fin: "une même exigence." },
  corps:
    "Choisissez votre profil. La démarche reste la même : des chiffres sourcés, puis des décisions.",
  profils: [
    {
      titre: "Porteurs de projet",
      corps:
        "Vous avez l'idée, pas encore la preuve. On mesure le marché avant que vous ne vous engagiez.",
      bouton: "Valider mon idée",
      lien: LIENS.etudes,
      image: IMAGES_ACCUEIL.idee,
    },
    {
      titre: "Freelances",
      corps:
        "Vous vendez votre savoir-faire. On regarde votre marché, vos clients et les prix pratiqués autour de vous.",
      bouton: "Structurer mon offre",
      lien: LIENS.etudes,
      image: IMAGES_ACCUEIL.freelance,
    },
    {
      // « France Travail », jamais l'ancien nom de l'organisme.
      titre: "Demandeurs d'emploi",
      corps:
        "Vous préparez votre rebond. On sécurise le projet avant le grand saut, avec un dossier à présenter à votre conseiller France Travail.",
      bouton: "Préparer ma création",
      lien: LIENS.etudes,
      image: IMAGES_ACCUEIL.rebond,
    },
    {
      titre: "Micro-entreprises",
      corps:
        "L'activité tourne, la direction manque. La stratégie business fixe vos priorités et votre plan d'action.",
      bouton: "Clarifier ma stratégie",
      lien: LIENS.etudes,
      image: IMAGES_ACCUEIL.microEntreprise,
    },
    {
      /** La promesse au professionnel (stratégie commerciale). */
      titre: "Partenaires PRO",
      corps:
        "Vous restez l'expert de votre client. EVKHA produit le dossier sous votre marque, en moins de vingt minutes de votre temps.",
      bouton: "Voir les abonnements",
      lien: LIENS.partenaires,
      image: IMAGES_ACCUEIL.partenaire,
    },
  ],
};

// ── Les offres réellement vendues ───────────────────────────────────────────

/** D'où vient le prix d'une carte. C'est la page qui le calcule sur l'API ;
 *  ce fichier ne dit que QUEL calcul faire.
 *
 *  - `boutique-plancher` : l'étude prête la moins chère du catalogue ;
 *  - `livrables-fourchette` : du livrable le moins cher au plus cher ;
 *  - `formule-plancher` : l'abonnement professionnel le moins cher ;
 *  - `formule-nommee` : UNE formule, désignée par son `code`. */
export type SourceDePrix =
  | "boutique-plancher"
  | "livrables-fourchette"
  | "formule-plancher"
  | "formule-nommee";

export type Offre = {
  prix: SourceDePrix;
  /** Pour `formule-nommee` : le `code` de la formule côté serveur. Le titre
   *  de la carte devient alors son `libelle`, et ses points ses `avantages`
   *  — rendus par le serveur, pas recopiés ici. */
  codeFormule?: string;
  surtitre: string;
  /** Le titre de la carte. Pour `formule-nommee`, celui affiché tant que la
   *  formule n'est pas chargée, ou si elle n'est plus au catalogue. */
  titre: string;
  corps: string;
  points: string[];
  bouton: string;
  lien: string;
  /** La carte mise en avant, et son étiquette. */
  etiquette?: string;
};

export const OFFRES = {
  surtitre: "Les offres",
  titre: { avant: "Un prix clair,", fin: "un résultat précis." },
  corps:
    "Quatre façons de travailler avec EVKHA, de l'étude prête à télécharger à l'abonnement d'une structure d'accompagnement.",
  cartes: [
    {
      prix: "boutique-plancher",
      surtitre: "Tout de suite",
      titre: "Étude prête",
      corps: "Une étude déjà rédigée sur un secteur, dans la boutique.",
      points: [
        "Téléchargement immédiat",
        "Aucun questionnaire à remplir",
        "Un secteur déjà étudié, prêt à lire",
      ],
      bouton: "Voir la boutique",
      lien: LIENS.boutique,
    },
    {
      prix: "livrables-fourchette",
      surtitre: "Pour votre projet",
      titre: "Livrable sur mesure",
      corps: "Écrit pour votre projet et votre zone.",
      points: [
        "Étude de marché, concurrence, business plan ou stratégie",
        "Relu avant envoi",
        "Reçu sous 24 heures ouvrées",
        "PDF et Word, à vos couleurs et avec votre logo",
      ],
      bouton: "Commander une étude",
      lien: LIENS.etudes,
      etiquette: "Écrit pour vous",
    },
    {
      prix: "formule-plancher",
      surtitre: "Vous accompagnez",
      titre: "Abonnement professionnel",
      corps: "Pour les coachs, les cabinets et les agences.",
      points: [
        "Documents à votre marque",
        // La règle d'engagement, dans les mots de `espace/engagement.ts` :
        // les trois écrans de l'espace la lisent là, l'accueil aussi.
        ARRET_EN_UNE_LIGNE,
        "Un crédit, un livrable au choix",
      ],
      bouton: "Voir les abonnements",
      lien: LIENS.partenaires,
    },
    {
      prix: "formule-nommee",
      codeFormule: "structure",
      surtitre: "Réseaux et incubateurs",
      titre: "Formule pour les structures",
      corps: "Pour accompagner des promotions entières de porteurs.",
      // Vide à dessein : les points de cette carte sont les `avantages` de la
      // formule, tels que le serveur les rend.
      points: [],
      bouton: "Voir cette formule",
      lien: LIENS.partenaires,
    },
  ] as Offre[],
};

// ── Études prêtes : les produits réels de la boutique ───────────────────────

/** Les titres, les prix et les liens viennent du catalogue de la boutique —
 *  le même appel que la carte « Étude prête » des offres. Ici, seulement
 *  l'habillage. Ni « mises à jour tous les 6 mois » ni « des dizaines
 *  d'études » : le site l'écrit, rien ne le vérifie. */
export const ETUDES_PRETES = {
  surtitre: "Études prêtes",
  titre: { avant: "Un secteur,", fin: "déjà étudié." },
  corps: `Téléchargement immédiat. Une étude en ${CHAPITRES_ETUDE_DE_MARCHE} chapitres qui répond aux premières questions : est-ce un secteur rentable ? en croissance ? saturé ?`,
  /** Au plus six cartes : la suite est dans la boutique. */
  maximum: 6,
  carte: "Voir l'étude",
  bouton: { libelle: "Voir toute la boutique", lien: LIENS.boutique },
  attente: "Chargement des études prêtes…",
  panne: "Les études prêtes sont momentanément indisponibles.",
};

// ── La méthode ──────────────────────────────────────────────────────────────

export const METHODE = {
  surtitre: "La méthode",
  titre: { avant: "Trois temps,", fin: "dans le bon ordre." },
  corps:
    "On ne rédige pas un business plan avant de connaître son marché. La méthode EVKHA remet les étapes à leur place.",
  temps: [
    {
      titre: "Comprendre",
      corps:
        "Le marché, les clients, les concurrents. Des données sourcées, pas des intuitions.",
      livrables: "Études de marché et de concurrence",
    },
    {
      titre: "Construire",
      corps:
        "L'offre, les prix, le prévisionnel. Un projet qui tient sur le papier avant de tenir en vrai.",
      livrables: "Business plan et stratégie",
    },
    {
      titre: "Piloter",
      corps:
        "Une organisation, des indicateurs, des rendez-vous réguliers avec vos chiffres.",
      livrables: "Méthode P.O.P et accompagnement",
      // La méthode P.O.P est une formation, vendue sur le site de la
      // cliente : le renvoi y mène, il ne promet rien que la plateforme vende.
      lien: LIENS.formations,
    },
  ] as { titre: string; corps: string; livrables: string; lien?: string }[],
};

// ── Formations et accompagnement ────────────────────────────────────────────

/** Deux offres de la cliente que la plateforme NE VEND PAS. Elles sont
 *  présentées SANS PRIX : leur tarif vit sur `evkha.fr`, et l'écrire ici en
 *  ferait une seconde source que personne ne mettrait à jour. Textes repris de
 *  l'accueil du site actuel, passés au vouvoiement. */
export const AILLEURS = {
  surtitre: "Formations et accompagnement",
  titre: { avant: "Pour aller plus loin,", fin: "avec Evangeline." },
  corps:
    "Vous préférez apprendre à créer votre entreprise vous-même, ou être accompagné pas à pas ? Les formations et les packs d'accompagnement sont là pour cela.",
  mention: "Ces offres se réservent sur evkha.fr.",
  cartes: [
    {
      titre: "Les formations",
      corps:
        "18 heures en ligne et 2 heures d'accompagnement personnalisé pour chacune des deux formations à la création.",
      points: [
        "Créer son entreprise de A à Z",
        "Créer sa micro-entreprise de A à Z",
        "Gérer son entreprise avec la méthode P.O.P : productivité, suivi financier, organisation quotidienne",
      ],
      bouton: "Voir les formations",
      lien: LIENS.formations,
      image: { src: IMAGES_ACCUEIL.formations, largeur: 1080, hauteur: 1080 },
    },
    {
      titre: "L'accompagnement individuel",
      corps:
        "Deux packs, avec des rendez-vous en visio et un suivi, pour parler de votre projet, de vos chiffres et de votre future entreprise.",
      points: [
        "Évaluer la viabilité de votre projet",
        "Identifier vos opportunités",
        "Anticiper les risques",
        "Préparer une demande de financement",
      ],
      bouton: "Voir les packs",
      lien: LIENS.packs,
    },
  ] as {
    titre: string;
    corps: string;
    points: string[];
    bouton: string;
    lien: string;
    image?: { src: string; largeur: number; hauteur: number };
  }[],
};

// ── La fondatrice ───────────────────────────────────────────────────────────

export const FONDATRICE_ACCUEIL = {
  surtitre: "Qui vous accompagne",
  citation: {
    avant:
      "« Créer une entreprise ne se résume pas à remplir des formulaires. Il faut",
    appui: "comprendre le terrain",
    apres: "sur lequel vous allez évoluer. »",
  },
  nom: "Evangeline Khaili, fondatrice d'EVKHA",
  corps:
    "J'ai créé et dirigé des entreprises dans le e-commerce, la restauration et la gestion de projets. Je suis passée par les doutes et les questions ; c'est ce vécu que je mets dans chaque étude et chaque accompagnement.",
  references: ["Formatrice LégalPlace", "Consultante Initiative France"],
  bouton: { libelle: "Discutons de votre projet", lien: "#contact" },
};

// ── Pourquoi EVKHA ──────────────────────────────────────────────────────────

/** Les trois preuves de la stratégie commerciale — des chiffres sourcés, une
 *  méthode, une relecture humaine — puis deux cases : l'habillage et le prix.
 *  `forme` : `large` pour la grande case dorée, `voile` pour la case crème.
 *
 *  La relecture est dite pour ce qu'elle est, sans l'opposer à quoi que ce
 *  soit (décision du 19/11/2026). */
export const POURQUOI = {
  surtitre: "Pourquoi EVKHA",
  titre: { avant: "Ce qui change,", fin: "concrètement." },
  corps:
    "Trois preuves, et deux choses qui comptent quand on se lance avec ses propres moyens.",
  cases: [
    {
      signe: "✦",
      forme: "large",
      titre: "Des chiffres sourcés, sur votre marché et votre zone",
      corps:
        "Chaque donnée de votre étude renvoie à son origine. Votre banquier peut la contrôler, vous aussi.",
    },
    {
      signe: String(CHAPITRES_ETUDE_DE_MARCHE),
      titre: "Une méthode",
      corps: `L'étude de marché suit ${CHAPITRES_ETUDE_DE_MARCHE} chapitres, toujours dans le même ordre. Rien d'important n'est laissé de côté.`,
    },
    {
      signe: "Aa",
      titre: "Une relecture humaine avant envoi",
      corps: RELECTURE,
    },
    {
      signe: "&",
      forme: "voile",
      titre: "À vos couleurs et avec votre logo",
      corps:
        "Le document porte votre identité, en PDF et en Word modifiable.",
    },
    {
      signe: "€",
      titre: "Un prix qu'un créateur peut payer seul",
      corps:
        "Le tarif est affiché, le paiement se fait en ligne : vous savez ce que vous engagez avant de commencer.",
    },
  ] as {
    signe: string;
    forme?: "large" | "voile";
    titre: string;
    corps: string;
  }[],
};

// ── Les avis ────────────────────────────────────────────────────────────────

/** Les neuf avis de clients, MOT POUR MOT — fautes comprises. Ce sont des
 *  citations : en corriger l'orthographe en ferait des textes que personne n'a
 *  écrits. Ne pas « réparer » ce fichier.
 *
 *  Ils datent de 2024 et portent sur des études réalisées sur commande par
 *  Evangeline, AVANT la plateforme : l'introduction le dit, pour qu'aucun ne
 *  se lise comme un avis sur une commande passée ici.
 *
 *  `colonne` : la colonne du mur où l'avis défile. `dore` : la carte jaune. */
export type AvisClient = {
  texte: string;
  auteur: string;
  contexte: string;
  colonne: 1 | 2;
  dore?: boolean;
};

export const AVIS = {
  surtitre: "Ils se sont lancés",
  titre: { avant: "Ce qu'ils en disent,", fin: "mot pour mot." },
  // Les dix derniers avis du profil ComeUp d'Evangeline
  // (comeup.com/fr/@evkha-business), relevés le 19/11/2026 à la demande du
  // client, pour remplacer ceux de 2024. Recopiés mot pour mot, fautes
  // comprises ; seuls les retours à la ligne sont devenus des espaces.
  // Les deux plus longs sont donnés EN EXTRAIT (demande du client, 19/11/2026 :
  // sur téléphone, la file prend la hauteur de la carte la plus haute, et un
  // avis de 700 signes étirait toutes les autres). Un extrait garde les mots
  // du client et marque la coupe par « […] » : on ne réécrit pas un avis. Le
  // nombre d'avis positifs est celui que le profil affichait ce jour-là : il
  // n'est PAS relu en direct, et vieillira avec cette phrase.
  corps:
    "Les dix derniers avis laissés à Evangeline sur ComeUp, où son profil compte 221 avis positifs. Recopiés tels qu'ils ont été écrits, les plus longs en extrait.",
  bouton: { libelle: "Commander une étude", lien: LIENS.etudes },
  groupe: "Avis de clients",
  liste: [
    {
      colonne: 1,
      texte:
        "« Prestation pro concernant des questions précises sur la création d'une entreprise.Merci pour la reactivité. »",
      auteur: "charly_a",
      contexte: "Avis ComeUp · 19 nov. 2026",
    },
    {
      colonne: 1,
      dore: true,
      texte:
        "« Très satisfait du travail d'Evangéline, comme à chaque fois :) »",
      auteur: "DamienBert",
      contexte: "Avis ComeUp · 13 nov. 2026",
    },
    {
      colonne: 1,
      texte:
        "« Merci pour ce excellent travail. Ta disponibilité et ton expertise Hors paire. Je la recommande »",
      auteur: "IreneINOUA",
      contexte: "Avis ComeUp · 1 nov. 2026",
    },
    {
      colonne: 1,
      texte:
        "« Toujours très professionnelle, et réactive, je suis plus que satisfait »",
      auteur: "LionelVargas",
      contexte: "Avis ComeUp · 13 oct. 2026",
    },
    {
      colonne: 1,
      texte:
        "« Toujours satisfait de son travail, très pro, je recommande ! »",
      auteur: "LionelVargas",
      contexte: "Avis ComeUp · 10 oct. 2026",
    },
    {
      colonne: 2,
      dore: true,
      texte:
        "« Une prise en charge ultra-personnalisée et une véritable expertise à l’œil de lynx ! […] Évangeline nous a clairement permis de franchir un cap dans la qualité et la crédibilité de nos dossiers. »",
      auteur: "David_Simone",
      contexte: "Avis ComeUp · 6 oct. 2026",
    },
    {
      colonne: 1,
      texte:
        "« Evangéline a vraiment une belle capacité d'analyse, avec des conseils judicieux, je recommande »",
      auteur: "LionelVargas",
      contexte: "Avis ComeUp · 3 oct. 2026",
    },
    {
      colonne: 2,
      texte:
        "« Merci pour votre travail de qualité, et pour votre réactivité ! »",
      auteur: "Vil",
      contexte: "Avis ComeUp · 28 sept. 2026",
    },
    {
      colonne: 2,
      dore: true,
      texte:
        "« Evangéline est très professionnelle et consciencieuse. Ça a été un vrai plaisir de lui confier la réalisation de notre business plan. Je la recommande vivement ! »",
      auteur: "LionelVargas",
      contexte: "Avis ComeUp · 21 sept. 2026",
    },
    {
      colonne: 2,
      texte:
        "« Je suis très satisfait des services d'Evangéline ! Comme d'habitude, son cabinet allie professionnalisme, réactivité et précision quant à ses analyses. […] »",
      auteur: "DamienBert",
      contexte: "Avis ComeUp · 9 sept. 2026",
    },
  ] as AvisClient[],
};

// ── Boîte à outils ──────────────────────────────────────────────────────────

/** Trois ressources gratuites du site de la cliente. Les deux premières se
 *  demandent depuis sa page « Boîte à outils » (elle les envoie par e-mail),
 *  la troisième est un article. Le site tutoie ; ici on vouvoie. */
export const OUTILS = {
  surtitre: "Boîte à outils",
  titre: { avant: "Trois ressources,", fin: "pour commencer." },
  corps:
    "Des documents gratuits pour préparer votre projet, avant de vous engager.",
  etiquette: "Gratuit",
  ressources: [
    {
      titre: "Checklist : créer sa micro-entreprise en 10 étapes",
      corps:
        "Dix étapes clés, avec des actions concrètes à cocher, pour vous lancer sans rien oublier.",
      bouton: "Voir la checklist",
      lien: LIENS.outils,
    },
    {
      titre: "Le lexique EVKHA de l'entrepreneuriat",
      corps:
        "Des définitions claires et des exemples concrets, pour comprendre les mots de la création d'entreprise avant de signer.",
      bouton: "Voir le lexique",
      lien: LIENS.outils,
    },
    {
      titre: "Ai-je une idée de business viable ? Les 4 questions à se poser",
      corps:
        "Un article pour éprouver votre idée avant de vous projeter dans le logo, le site et les clients.",
      bouton: "Lire l'article",
      lien: LIENS.article,
    },
  ],
};

// ── Questions fréquentes ────────────────────────────────────────────────────

/** Uniquement ce qui est établi ailleurs dans le dépôt (page des études, plan
 *  de refonte). Deux réponses de la maquette ont été retirées parce que rien
 *  ne les fonde : la déduction du prix d'une étude sur un pack, et le
 *  financement des formations. */
export const QUESTIONS = {
  surtitre: "Questions fréquentes",
  titre: { avant: "Avant de", fin: "vous décider." },
  corps: "Une autre question ? Écrivez-nous, nous répondons sous 48 h.",
  liste: [
    {
      q: "Que contient une étude de marché ?",
      r: `${CHAPITRES_ETUDE_DE_MARCHE} chapitres : la taille de votre marché, sa tendance, vos clients types, les risques du projet et la façon de les anticiper. Les chiffres sont sourcés, sur votre secteur et dans votre zone.`,
    },
    {
      q: "En combien de temps vais-je la recevoir ?",
      r: "Sous 24 heures ouvrées après l'envoi de votre questionnaire, qui demande 15 à 20 minutes. Vos fichiers arrivent par e-mail.",
    },
    {
      q: "Sous quelle forme vais-je la recevoir ?",
      r: "Un PDF prêt à imprimer ou à envoyer, et une version Word modifiable. Les deux sont à vos couleurs et portent votre logo.",
    },
    {
      q: "Mon document est-il relu ?",
      r: `Oui. ${RELECTURE}`,
    },
    {
      q: "Quelle différence entre une étude prête et une étude sur mesure ?",
      r: "L'étude prête est déjà rédigée, sur un secteur : vous la téléchargez immédiatement depuis la boutique. L'étude sur mesure est écrite pour votre projet et votre zone, à partir de votre questionnaire ; vous la recevez sous 24 heures ouvrées.",
    },
  ],
};

// ── Fin de page ─────────────────────────────────────────────────────────────

export const FIN = {
  titre: "Alors, lancez-vous.",
  corps:
    "Un premier appel gratuit pour parler de votre projet, de vos chiffres et de la suite.",
  bouton: { libelle: "Réserver un appel gratuit", lien: LIENS.appel },
  /** À la place de la lettre d'information de la maquette : aucun service ne
   *  reçoit d'inscription, et un formulaire qui n'envoie rien est interdit. */
  question: {
    titre: "Une question ?",
    corps: "Écrivez-nous : nous répondons sous 48 h.",
    lien: LIENS.courriel,
    adresse: CONTACT_EMAIL,
  },
  bande: "de l'idée à l'action",
};

/** Le titre de l'onglet, récrit le 20/11/2026 pour dire ce que la page VEND
 *  dans les mots qu'un porteur de projet tape dans un moteur — le titre
 *  d'avant (« EVKHA — De l'idée à l'entreprise ») ne nommait aucun des documents. À faire valider par la
 *  cliente (`docs/referencement/etat-et-plan.md`). */
export const TITRE_DE_LA_PAGE =
  "Étude de marché, business plan, étude de concurrence — EVKHA";
export const DESCRIPTION_DE_LA_PAGE =
  "Étude de marché, étude de la concurrence, business plan et stratégie business : le dossier de votre projet, écrit pour votre zone, relu avant envoi, reçu sous 24 heures ouvrées.";
