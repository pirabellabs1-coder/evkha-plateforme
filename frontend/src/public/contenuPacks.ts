/** Le texte des trois pages « Packs d'accompagnement » : la page d'ensemble,
 *  le Pack Création Essentiel et le Pack Création Premium.
 *
 * D'OÙ VIENT LE CONTENU. Du site actuel de la cliente (`www.evkha.fr`,
 * Systeme.io), relevé le 25/10/2026 dans
 * `docs/refonte/inventaire-site-evkha.md` :
 *   - section 7  `/packs`                    → `PAGE_PACKS` ;
 *   - section 19 `/paiement-packcrea`        → `PAGE_PACK_ESSENTIEL` ;
 *   - section 20 `/paiement-packcreapremium` → `PAGE_PACK_PREMIUM`.
 * Le texte est REPRIS TEL QUEL, dans l'ordre de chaque page. Rien n'est
 * résumé, rien n'est réécrit, le « je » d'Evangeline est conservé.
 *
 * CE QUI A ÉTÉ RETOUCHÉ, et rien d'autre :
 *   - retirés : le menu de navigation, le pied de page (liens légaux,
 *     « © EVKHA. Tous droits réservés. ») et les boutons « Accueil » /
 *     « Nos packs » de l'en-tête des pages de paiement — communs au site ;
 *   - coquilles : « livraiuson » → « livraison » ; « BONUS EXCEPTIONNEL: »
 *     et « ( VALEUR » → espaces rétablies ; sur `/packs`, la puce
 *     « … après livraison Ce pack sert à : » était collée à l'intertitre
 *     suivant, les deux sont séparés ;
 *   - les montants ne sont plus écrits dans les phrases : chaque phrase qui
 *     cite un prix est construite à partir de `TARIFS_PACKS` ;
 *   - « Pôle Emploi » → « France Travail » : aucune occurrence à changer, les
 *     trois pages écrivent déjà « France Travail ».
 *
 * CE QUI N'A PAS ÉTÉ CORRIGÉ, volontairement (style ou doute, pas coquille
 * de frappe) : « Vous donnez un accompagnement », « Vous faire Gagner »,
 * « qui coûtent chères », « votre famille d'investisseurs », « PRÉMIUM » avec
 * accent, et l'alternance « 15 ans » / « 16 ans » d'expérience — la cliente
 * n'a pas tranché (point 4 des questions ouvertes du plan de refonte).
 *
 * COMPLÉTÉ LE 19/11/2026 par un second relevé fait sur le site : les
 * QUESTIONS des deux FAQ, les douze LIGNES du comparatif Essentiel / Premium,
 * et les vignettes de l'aperçu des documents de l'Essentiel.
 *
 * CE QUE LES RELEVÉS NE CONTIENNENT TOUJOURS PAS (voir le commentaire sur
 * place) : les chiffres des trois cartes « De contenu / D'accompagnement / De
 * bonus offerts » du Premium. Rien n'a été inventé pour combler : le champ
 * est `null`.
 *
 * UNE SOURCE PAR FAIT (règle 5). Le prix et la durée de la Méthode P.O.P,
 * offerte avec le Premium, ne sont PAS écrits ici : ils se lisent dans
 * `contenuFormations` (`TARIFS_FORMATIONS.pop`, `DUREES_POP`), où la formation
 * est vendue. Les adresses des trois pages se lisent dans
 * `contenuSite.CHEMINS`, et les montants s'affichent par `donnees.euros`,
 * comme partout sur le site.
 */
import { DUREES_POP, TARIFS_FORMATIONS } from "./contenuFormations";
import { CHEMINS } from "./contenuSite";
import { euros } from "./donnees";

// ── Tarifs ──────────────────────────────────────────────────────────────────

/** Un montant relevé sur le site. `mentionTaxe` : la mention que le site
 *  accole au prix (« TTC », « HT »), ou `null` quand il n'en donne aucune. */
export type TarifReleve = {
  centimes: number;
  mentionTaxe: string | null;
};

/** LES PRIX DES PACKS — relevés sur evkha.fr le 25/10/2026.
 *
 *  C'est la SEULE source de ces montants dans le dépôt : ces offres ne sont
 *  dans aucune API de la plateforme. À REMPLACER par le catalogue serveur le
 *  jour où elles y entrent ; d'ici là, tout le reste de ce fichier lit cette
 *  constante, et aucun de ces montants n'est écrit une seconde fois.
 *
 *  Le site n'écrit ni « TTC » ni « HT » à côté de ces prix : `mentionTaxe`
 *  vaut donc `null`, et non une supposition. Les deux prix de vente ne
 *  figurent que sur `/packs` ; les pages de paiement ne les redisent pas.
 *
 *  `formationPop` : la valeur de la formation P.O.P offerte avec le Premium,
 *  telle que les pages des packs la citent. Ce n'est pas un prix de vente de
 *  ce lot : le montant est LU dans `contenuFormations.TARIFS_FORMATIONS.pop`,
 *  le prix auquel la formation est vendue. Écrit ici une seconde fois, il
 *  aurait suffi d'un changement de tarif de la formation pour que le Premium
 *  annonce une « valeur » que plus rien ne vend. Les pages des packs ne
 *  l'accompagnent d'aucune mention de taxe : `mentionTaxe` reste `null`. */
export const TARIFS_PACKS = {
  essentiel: { centimes: 49500, mentionTaxe: null },
  premium: { centimes: 99500, mentionTaxe: null },
  formationPop: { centimes: TARIFS_FORMATIONS.pop.centimes, mentionTaxe: null },
} as const satisfies Record<string, TarifReleve>;

/** Le montant en euros entiers, sans symbole (« 495 »). Un montant qui ne
 *  tombe pas sur un euro rond LÈVE une erreur : l'arrondir en silence ferait
 *  afficher un prix que personne n'a relevé. */
function eurosEntiers(tarif: TarifReleve): string {
  const euros = tarif.centimes / 100;
  if (!Number.isInteger(euros) || euros <= 0) {
    throw new Error(
      `contenuPacks : montant non entier ou nul (${tarif.centimes} centimes)`,
    );
  }
  return String(euros);
}

/** Le montant tel que le SITE l'affiche : « 495 € », par la fonction commune
 *  `donnees.euros` — la même que l'accueil, les études et la boutique, avec
 *  ses espaces insécables. `eurosEntiers` passe d'abord : un montant nul ou
 *  qui ne tombe pas sur un euro rond lève une erreur au lieu de s'afficher. */
function enEuros(tarif: TarifReleve): string {
  eurosEntiers(tarif);
  return euros(tarif.centimes);
}

/** La durée de la Méthode P.O.P, telle que les pages des packs l'écrivent :
 *  « 7h ». Le nombre d'heures est lu là où la formation est décrite. */
const HEURES_POP = `${DUREES_POP.heuresEnLigne}h`;

const PRIX_ESSENTIEL = enEuros(TARIFS_PACKS.essentiel);
const PRIX_PREMIUM = enEuros(TARIFS_PACKS.premium);
const VALEUR_POP = enEuros(TARIFS_PACKS.formationPop);

// ── Adresses ────────────────────────────────────────────────────────────────

/** Les destinations des boutons, telles que relevées.
 *
 *  Aucun lien Calendly ne figure sur ces trois pages : il n'y en a donc pas
 *  ici (celui du site est dans `contenuAccueil.LIENS.appel`).
 *
 *  `decouvrirPremium` : sur la page de l'Essentiel, le bouton « Découvrir le
 *  Premium → » pointe vers « # », c'est-à-dire nulle part. Relevé tel quel ;
 *  la destination voulue est à l'évidence celle de `commandePremium`.
 *
 *  Les boutons « Profiter de l'offre » des deux pages de paiement n'ont pas
 *  d'adresse : ils valident le formulaire de commande de Systeme.io. */
export const LIENS_PACKS = {
  pagePacks: "https://www.evkha.fr/packs",
  commandeEssentiel: "https://www.evkha.fr/paiement-packcrea",
  commandePremium: "https://www.evkha.fr/paiement-packcreapremium",
  decouvrirPremium: "#",
} as const;

// ── Images ──────────────────────────────────────────────────────────────────

export type ImageARapatrier = {
  /** La page du site où l'image a été relevée. */
  page: string;
  adresse: string;
  /** Le texte voisin sur la page, pour la reconnaître. */
  contexte: string;
};

/** Les quatre images relevées sur ces pages, toutes sans texte alternatif.
 *  Elles sont encore servies par Systeme.io : à copier dans la plateforme
 *  avant la fermeture de l'ancien site. Rien n'a été téléchargé. */
export const IMAGES_PACKS_A_RAPATRIER: ImageARapatrier[] = [
  {
    page: "https://www.evkha.fr/packs",
    adresse:
      "https://d1yei2z3i6k35z.cloudfront.net/9890127/6844d0a794f08_ChatGPTImage8juin202501_48_06.png",
    contexte:
      "En-tête, avant le menu de navigation (« Accueil », « Etude de marché & Livrables »…) : le logo du site.",
  },
  {
    page: "https://www.evkha.fr/packs",
    adresse:
      "https://d1yei2z3i6k35z.cloudfront.net/9890127/684aa0126cde0_Bienvenue5.png",
    contexte:
      "Juste au-dessus du titre « Lancez votre entreprise avec nos packs sur-mesure ».",
  },
  {
    page: "https://www.evkha.fr/paiement-packcrea",
    adresse:
      "https://d1yei2z3i6k35z.cloudfront.net/9890127/6a31a793c2a3e9.44324754_LOGOEVKHABUSINESSETFORM.png",
    contexte:
      "En-tête, avant les boutons « Accueil » et « Nos packs » et le titre « Pack Création Essentiel » : le logo EVKHA Business & Formations.",
  },
  {
    page: "https://www.evkha.fr/paiement-packcreapremium",
    adresse:
      "https://d1yei2z3i6k35z.cloudfront.net/9890127/6a33fd586856b7.97183294_LOGOEVKHABUSINESSETFORM.png",
    contexte:
      "En-tête, avant les boutons « Accueil » et « Nos packs » et le titre « Pack Création Premium » : le logo EVKHA Business & Formations.",
  },
];

// ── Types communs ───────────────────────────────────────────────────────────

export type BoutonDePack = { libelle: string; lien: string };

/** Un intertitre et son paragraphe. */
export type CarteDePack = { titre: string; corps: string };

/** Une carte de contenu détaillé : un livrable, sa description, ses points. */
export type LivrableDePack = { titre: string; corps: string; points: string[] };

/** Une question de la FAQ. Les réponses viennent de l'inventaire du
 *  25/10/2026 ; les questions (en-têtes d'accordéon, absentes de ce relevé)
 *  ont été relevées sur le site le 19/11/2026 et appariées dans l'ordre de la
 *  page, chaque appariement relu contre le contenu de sa réponse. */
export type QuestionDePack = {
  question: string;
  reponse: string;
};

/** Une ligne du comparatif Essentiel / Premium. « ✓ » : inclus ; « — » : non
 *  inclus ; « ★ » : le bonus mis en avant. Tels qu'affichés sur le site. */
export type LigneDeComparatif = {
  critere: string;
  essentiel: string;
  premium: string;
};

/** Un aperçu de document : la vignette (son titre en capitales et son
 *  volume), l'étiquette « Livrable n », puis le titre et la description. */
export type ApercuDeDocument = {
  vignette: { titre: string; volume: string };
  etiquette: string;
  titre: string;
  corps: string;
};

/** Le formulaire de commande au bas des pages de paiement (Systeme.io). */
export type FormulaireDeCommande = {
  titre: string;
  rubrique: string;
  codeDeReduction: string;
  consentementCgv: string;
  consentementCourriels: string;
  bouton: string;
};

// ── Page d'ensemble : /packs ────────────────────────────────────────────────

/** Une carte de pack sur la page d'ensemble. */
export type CarteDeLaPageDEnsemble = {
  nom: string;
  tarif: string;
  accroche: string;
  contenuTitre: string;
  contenu: string[];
  sertATitre: string;
  sertA: string[];
  duree: string;
  bouton: BoutonDePack;
};

export const PAGE_PACKS = {
  titreDeLOnglet:
    "Packs création d’entreprise complets : étude, prévisionnel, Business Plan – EVKHA",
  metaDescription:
    "Des packs clés en main pour lancer son entreprise : étude de marché, prévisionnel financier et business plan personnalisés, conçus pour convaincre et obtenir un financement.",

  ouverture: {
    titre: "Lancez votre entreprise avec nos packs sur-mesure",
    corps: [
      "Deux packs pour lancer et structurer votre entreprise, selon vos besoins et votre budget.",
      "Des documents concrets, un accompagnement personnalisé, et une expertise de 15 ans à vos côtés !",
    ],
  },

  packEssentiel: {
    nom: "Pack Création ESSENTIEL",
    tarif: `Tarif : ${PRIX_ESSENTIEL}`,
    accroche:
      "L’essentiel pour démarrer avec des bases solides. Idéal si vous avez besoin rapidement des documents clés attendus par les banques et les administrations.",
    contenuTitre: "Contenu du pack :",
    contenu: [
      "Je réalise votre Étude de marché + Étude de la concurrence",
      "Je travaille votre cible client et vos personas",
      "2 appels de 45 minutes",
      "Je réalise votre Prévisionnel financier sur 3 ans",
      "Je rédige votre Business plan personnalisé de 30 pages",
      "Vous profitez de 6 semaines de support mail/WhatsApp après livraison",
    ],
    sertATitre: "Ce pack sert à :",
    sertA: [
      "Lancer votre entreprise avec un dossier prêt à convaincre les banques et investisseurs",
      "Vous donnez un accompagnement sur-mesure pour démarrer sereinement.",
      "Vous faire Gagner du temps et éviter les erreurs : on s’occupe de tout !",
    ],
    duree: "Durée : 1 à 2 semaines (+ suivi de 6 semaines)",
    bouton: {
      libelle: "Je commande le pack ESSENTIEL",
      lien: LIENS_PACKS.commandeEssentiel,
    },
  } satisfies CarteDeLaPageDEnsemble,

  /** Le prévisionnel financier sur 3 ans ne figure PAS dans cette liste, alors
   *  que la page du Premium l'annonce et le détaille. Relevé tel quel. */
  packPremium: {
    nom: "Pack Création PRÉMIUM",
    tarif: `Tarif : ${PRIX_PREMIUM}`,
    accroche:
      "Un accompagnement complet et stratégique pour structurer, comprendre, présenter et piloter son projet, avec un suivi exclusif et des outils concrets.",
    contenuTitre: "Contenu du pack :",
    contenu: [
      "Nous posons les bases de votre projet, votre idée, votre positionnement",
      "Je réalise votre Étude de marché + Étude de la concurrence premium",
      "3 appels d'une heure",
      "Je rédige votre Business Plan stratégique et détaillé de 40 pages pour banque et investisseurs",
      "Je crée une analyse et un plan stratégique pour la première année.",
      "Je crée votre Pitch impactant et animé pour convaincre vos interlocuteurs",
      "Vous bénéficiez de nombreux outils et tableaux de bord",
      `BONUS EXCEPTIONNEL : ACCÈS À LA FORMATION POP (VALEUR ${eurosEntiers(TARIFS_PACKS.formationPop)} EUROS)`,
      "Vous profitez de 6 semaines de support mail/WhatsApp après livraison",
    ],
    sertATitre: "Ce pack sert à :",
    sertA: [
      "Structurer et comprendre votre projet avec un accompagnement complet",
      "Booster vos chances de réussite avec un accompagnement complet, clair et structuré.",
      "Bénéficier d’un suivi unique encore 6 semaines après la livraison",
      "Convaincre vos financeurs grâce à un dossier professionnel et un pitch animé qui font la différence.",
      "Piloter votre projet dès la première année avec une méthode et une formation exclusives.",
      "Économiser des semaines de travail et éviter les erreurs qui coûtent chères.",
    ],
    duree: "Durée : 3 semaines (+ suivi de 6 semaines)",
    bouton: {
      libelle: "Je commande le pack PREMIUM",
      lien: LIENS_PACKS.commandePremium,
    },
  } satisfies CarteDeLaPageDEnsemble,
};

// ── Pack Création Essentiel : /paiement-packcrea ────────────────────────────

export const PAGE_PACK_ESSENTIEL = {
  /** Titre et méta-description TELS QUE RELEVÉS — et tous deux fautifs : le
   *  titre est un nom de travail, identique sur la page du Premium, et la
   *  description parle d'une « inscription à la formation ». À réécrire pour
   *  la nouvelle page ; conservés ici pour mémoire. */
  titreDeLOnglet: "PAGE DE PAIEMENT pack créa",
  metaDescription:
    "Vous êtes à un clic de transformer votre business! Finalisez votre inscription à la formation et commençons le début de votre accompagnement en création d'entreprise.",

  /** Le prix du pack : la page de paiement ne l'écrit nulle part dans son
   *  texte. Il est rappelé ici pour la future page, depuis `TARIFS_PACKS`. */
  tarif: TARIFS_PACKS.essentiel,

  ouverture: {
    titre: "Pack Création Essentiel",
    corps:
      "Idéal si vous avez besoin rapidement des documents clés attendus par les banques et les administrations. Étude de marché, prévisionnel financier, business plan et accompagnement personnalisé : tout est inclus, je m'occupe de tout.",
    points: [
      "Étude de marché + concurrence",
      "Cible client et personas",
      "2 appels de 45 minutes",
      "Prévisionnel financier sur 3 ans",
      "Business plan personnalisé de 30 pages",
      "6 semaines de support mail / WhatsApp",
      "Documents prêts pour banques & administrations",
    ],
  },

  pourQui: {
    titre: "Pour les porteurs de projet qui veulent démarrer vite et bien",
    corps:
      "Un pack pensé pour celles et ceux qui ont besoin de documents professionnels et fiables, sans y passer des mois.",
    profils: [
      {
        titre: "Porteurs de projet pressés",
        corps:
          "Vous voulez vous concentrer sur votre activité, pas passer des semaines à rédiger des documents.",
      },
      {
        titre: "Futurs créateurs",
        corps:
          "Vous lancez votre première entreprise et avez besoin de bases solides validées par une experte.",
      },
      {
        titre: "Demandeurs de financement",
        corps:
          "Vous avez rendez-vous bientôt avec votre banquier ou un organisme et il vous faut un dossier crédible.",
      },
      {
        titre: "Créateurs en reconversion",
        corps:
          "Vous quittez le salariat et voulez sécuriser votre projet avant de vous lancer pour de bon.",
      },
    ] as CarteDePack[],
  },

  /** Les arguments : faire seul / avec le pack, en deux colonnes. */
  seulOuAccompagne: {
    titre: "Construire ces documents seul, c'est long et risqué",
    seul: {
      titre: "Faire vous-même, c'est s'exposer à :",
      points: [
        "Y passer 2 à 3 mois au détriment de votre projet",
        "Présenter un dossier amateur qui ne convainc personne",
        "Vous tromper sur les hypothèses financières clés",
        "Sous-estimer ou surestimer votre marché",
        "Ne pas savoir quoi mettre dans un business plan crédible",
        "Voir votre demande de financement refusée par manque de structure",
      ],
    },
    avecLePack: {
      titre: "Avec le Pack Essentiel, vous obtenez :",
      points: [
        "Vos 3 documents clés livrés en 1 à 2 semaines",
        "Un dossier professionnel qui inspire confiance",
        "Des chiffres réalistes, défendables devant un banquier",
        "Une analyse de marché solide et chiffrée",
        "Un business plan structuré de 30 pages",
        "L'accompagnement d'une experte avec 15 ans de terrain",
      ],
    },
  },

  contenuDuPack: {
    titre: "3 livrables stratégiques + accompagnement personnalisé",
    corps:
      "Chaque document est rédigé sur mesure pour votre projet, validé avec vous lors de nos appels, et livré en version éditable et PDF.",
    livrables: [
      {
        titre: "Étude de marché & étude de la concurrence",
        corps:
          "Une analyse complète du marché sur lequel vous vous lancez, avec dimensionnement, tendances, opportunités et cartographie de vos concurrents directs et indirects.",
        points: [
          "Taille et tendances de votre marché",
          "Définition de votre cible et de vos personas",
          "Analyse des concurrents directs et indirects",
          "Identification de votre avantage concurrentiel",
          "Recommandations stratégiques",
        ],
      },
      {
        titre: "Prévisionnel financier sur 3 ans",
        corps:
          "Un prévisionnel financier complet construit sur des hypothèses réalistes, conçu pour convaincre les banques et les investisseurs et piloter votre activité dès le démarrage.",
        points: [
          "Plan de financement initial",
          "Compte de résultat prévisionnel sur 3 ans",
          "Plan de trésorerie",
          "Calcul du seuil de rentabilité",
          "Hypothèses détaillées et défendables",
        ],
      },
      {
        titre: "Business plan personnalisé de 30 pages",
        corps:
          "Le document que vous présenterez à votre banque, à votre famille d'investisseurs ou à France Travail. Rédigé sur mesure, structuré, professionnel, prêt à convaincre.",
        points: [
          "Résumé exécutif percutant",
          "Présentation du projet et de l'équipe",
          "Synthèse de l'étude de marché",
          "Stratégie commerciale et marketing",
          "Synthèse financière et hypothèses",
        ],
      },
      {
        titre: "2 appels personnalisés de 45 minutes",
        corps:
          "Deux rendez-vous en visio pour cadrer le projet, valider les choix stratégiques et ajuster les livrables. Un coaching humain qui fait toute la différence.",
        points: [
          "Appel de cadrage initial",
          "Validation des livrables et ajustements",
          "Conseils stratégiques sur votre projet",
          "Réponse à toutes vos questions",
        ],
      },
    ] as LivrableDePack[],
  },

  /** Les étapes se suivent : leur rang dans le tableau est leur numéro. */
  processus: {
    titre: "De votre commande à votre dossier finalisé",
    corps:
      "Un processus clair et balisé en 5 étapes. Vous savez à tout moment où vous en êtes et ce qu'il vous reste à faire.",
    etapes: [
      {
        titre: "Vous commandez votre pack",
        corps:
          "Vous validez votre commande en ligne et recevez immédiatement un mail de bienvenue avec un questionnaire de cadrage à remplir et un lien pour réserver votre premier appel.",
      },
      {
        titre: "Appel de cadrage (45 min)",
        corps:
          "On échange en profondeur sur votre projet, votre vision, vos objectifs, vos hypothèses. Je collecte tout ce dont j'ai besoin pour démarrer la rédaction de vos livrables.",
      },
      {
        titre: "Rédaction des livrables",
        corps:
          "Je réalise votre étude de marché, votre prévisionnel financier et votre business plan personnalisé. Vous restez disponible par mail/WhatsApp pour les éventuelles précisions.",
      },
      {
        titre: "Appel de validation (45 min)",
        corps:
          "On parcourt ensemble les livrables, on ajuste ce qui doit l'être, et je vous transmets les versions finales en format éditable et PDF.",
      },
      {
        titre: "Support mail / WhatsApp",
        corps:
          "Pendant 6 semaines après la livraison, vous me sollicitez librement par mail ou WhatsApp pour toute question : ajustement d'un chiffre, préparation d'un rendez-vous bancaire, conseil stratégique…",
      },
    ] as CarteDePack[],
  },

  support: {
    titre: "6 semaines de support après la livraison",
    corps:
      "Le pack ne s'arrête pas à la remise des documents. Vous bénéficiez d'un vrai accompagnement humain pour aller au bout de votre projet.",
    points: [
      "Support mail/WhatsApp pendant 6 semaines",
      "Réponses rapides sous 24 à 48h",
      "Ajustements possibles sur les livrables si besoin",
      "Conseil stratégique pour vos rendez-vous bancaires",
      "Aide pour défendre vos hypothèses devant un financeur",
    ],
  },

  aQuoiSertLePack: {
    titre: "À quoi va vous servir ce pack",
    benefices: [
      {
        titre: "Convaincre votre banquier",
        corps:
          "Un dossier propre, structuré et professionnel qui inspire confiance et qui multiplie vos chances d'obtenir un financement.",
      },
      {
        titre: "Gagner du temps",
        corps:
          "Vous économisez 2 à 3 mois de travail. Vous vous concentrez sur votre activité, je m'occupe des documents.",
      },
      {
        titre: "Éviter les erreurs",
        corps:
          "Bénéficier de 15 ans d'expérience pour ne pas tomber dans les pièges classiques des créateurs débutants.",
      },
    ] as CarteDePack[],
  },

  /** Sur le site, ce bloc présente trois aperçus de documents, dessinés en
   *  CSS (aucune image). L'inventaire n'en portait que le titre et la
   *  description ; la vignette (titre en capitales, volume) et l'étiquette
   *  « Livrable n » ont été relevées sur le site le 19/11/2026.
   *
   *  « ~ 20 PAGES » pour l'étude de marché n'est écrit nulle part ailleurs
   *  sur ces pages. Pour le prévisionnel, la vignette répète « 3 ANS » dans
   *  son titre et dans son volume : relevé tel quel. */
  apercuDesDocuments: {
    titre: "Des documents premium, prêts à l'emploi",
    corps:
      "Chaque livrable est mis en page selon la charte EVKHA : élégant, professionnel, immédiatement utilisable pour vos rendez-vous bancaires et administratifs.",
    documents: [
      {
        vignette: { titre: "ÉTUDE DE MARCHÉ & CONCURRENCE", volume: "~ 20 PAGES" },
        etiquette: "Livrable 1",
        titre: "Étude de marché",
        corps: "Analyse approfondie du marché, concurrence, cible et personas.",
      },
      {
        vignette: { titre: "PRÉVISIONNEL FINANCIER 3 ANS", volume: "3 ANS" },
        etiquette: "Livrable 2",
        titre: "Prévisionnel financier",
        corps:
          "Plan de financement, compte de résultat, trésorerie, seuil de rentabilité.",
      },
      {
        vignette: { titre: "BUSINESS PLAN PERSONNALISÉ", volume: "30 PAGES" },
        etiquette: "Livrable 3",
        titre: "Business plan",
        corps: "30 pages structurées pour convaincre banques et investisseurs.",
      },
    ] as ApercuDeDocument[],
  },

  experte: {
    titre: "Une experte, pas un junior dans une agence",
    corps:
      "Quand vous commandez un pack EVKHA, c'est moi qui m'en occupe, de A à Z. Pas de sous-traitance, pas de junior en télétravail à qui on aurait délégué votre projet. Vous avez en face de vous une experte qui a accompagné plus de 500 créateurs d'entreprise depuis 16 ans, qui connaît les questions que va poser le banquier, et qui sait construire un dossier qui tient la route.",
  },

  /** Huit questions et leurs réponses, dans l'ordre de la page — voir
   *  `QuestionDePack` pour la provenance de chacune des deux moitiés. */
  faq: {
    titre: "Tout ce que vous voulez savoir avant de commander",
    questions: [
      {
        question: "Combien de temps avant de recevoir mes livrables ?",
        reponse:
          "Vos 3 livrables sont rédigés et livrés en 1 à 2 semaines après l'appel de cadrage initial. Le délai dépend essentiellement de votre disponibilité pour me transmettre les informations nécessaires.",
      },
      {
        question: "Et si je ne suis pas satisfait des documents ?",
        reponse:
          "L'appel de validation à mi-parcours et le suivi de 6 semaines après livraison sont précisément faits pour ça : on ajuste, on retravaille, on affine jusqu'à ce que les documents correspondent vraiment à votre projet et à vos besoins.",
      },
      {
        question: "Sous quel format je reçois les documents ?",
        reponse:
          "Chaque livrable vous est remis en format éditable (Word/Excel selon le document) et en PDF mis en page selon la charte EVKHA, prêt à être imprimé ou envoyé tel quel à votre banquier.",
      },
      {
        question: "Quelle est la différence avec le Pack Premium ?",
        reponse: `Le Pack Essentiel couvre les 3 livrables fondamentaux et l'accompagnement de base. Le Pack Premium est plus complet : appels d'1 heure (au lieu de 45 min), business plan de 40 pages, étude de marché premium, pitch animé, plan stratégique année 1, tableaux de bord ET la formation P.O.P incluse (valeur ${VALEUR_POP}). Si vous visez un financement important ou avez un projet ambitieux, le Premium fait sens.`,
      },
      {
        question: "Quels types de projets sont compatibles ?",
        reponse:
          "Le pack convient à tous types de projets : micro-entreprise, EI, EURL, SARL, SASU, SAS, dans tous les secteurs (services, commerce, e-commerce, artisanat…). J'adapte les livrables aux spécificités de votre activité.",
      },
      {
        question: "Le paiement en plusieurs fois est-il possible ?",
        reponse:
          "Oui, vous pouvez régler en plusieurs fois sans frais. Les modalités exactes vous seront présentées sur la page de paiement.",
      },
      {
        question: "Mon projet est encore vague, est-ce que c'est gênant ?",
        reponse:
          "Pas du tout. Une partie du travail consiste justement à clarifier et structurer votre projet. L'appel de cadrage permet de poser toutes les bases et de transformer une idée encore floue en un projet concret et défendable.",
      },
      {
        question: "Comment se passe le suivi de 6 semaines ?",
        reponse:
          "Pendant 6 semaines après la livraison, vous pouvez m'écrire librement par mail ou WhatsApp pour toute question : ajustement d'un chiffre, préparation d'un rendez-vous, validation d'une décision stratégique. Je vous réponds sous 24 à 48h.",
      },
    ] as QuestionDePack[],
  },

  /** Le renvoi vers le Premium : c'est tout ce que la page de l'Essentiel
   *  dit du comparatif (pas de tableau ici). */
  versLePremium: {
    titre: "Le Pack Premium va plus loin",
    corps: `Business plan de 40 pages, pitch animé, plan stratégique année 1, tableaux de bord… et la formation P.O.P incluse (valeur ${VALEUR_POP}). Pour les projets ambitieux qui veulent maximiser leurs chances.`,
    bouton: {
      libelle: "Découvrir le Premium\u00a0→",
      lien: LIENS_PACKS.decouvrirPremium,
    } satisfies BoutonDePack,
  },

  appelFinal: {
    titre: "Lancez votre projet avec des bases solides",
    corps:
      "3 livrables professionnels, 2 appels personnalisés, 6 semaines de support, et l'expertise de 16 ans à votre service. Tout est inclus.",
    mention: "Paiement sécurisé · Démarrage immédiat après commande",
  },

  formulaireDeCommande: {
    titre: "JE COMMANDE MON PACK CRÉA!",
    rubrique: "ADRESSE",
    codeDeReduction: "Ajout d'un code de réduction sur la page suivante",
    consentementCgv:
      "Oui, je certifie accepter les Conditions générales de vente et d'utilisation",
    consentementCourriels:
      "Oui, je consens à recevoir des emails et newsletter d'EVKHA.fr",
    bouton: "Profiter de l'offre",
  } satisfies FormulaireDeCommande,
};

// ── Pack Création Premium : /paiement-packcreapremium ───────────────────────

export const PAGE_PACK_PREMIUM = {
  /** TELS QUE RELEVÉS, et fautifs comme ceux de l'Essentiel (mêmes textes,
   *  mot pour mot). À réécrire pour la nouvelle page. */
  titreDeLOnglet: "PAGE DE PAIEMENT pack créa",
  metaDescription:
    "Vous êtes à un clic de transformer votre business! Finalisez votre inscription à la formation et commençons le début de votre accompagnement en création d'entreprise.",

  /** Le prix du pack : absent du texte de la page de paiement, rappelé ici
   *  depuis `TARIFS_PACKS`. */
  tarif: TARIFS_PACKS.premium,

  ouverture: {
    titre: "Pack Création Premium",
    corps:
      "Pour structurer, comprendre, présenter et piloter votre projet. Un accompagnement complet avec un suivi exclusif, des livrables premium et des outils concrets. Le pack pensé pour les projets ambitieux qui veulent maximiser leurs chances de réussite.",
    points: [
      "Cadrage projet, idée, positionnement",
      "Étude de marché & concurrence PREMIUM",
      "3 appels personnalisés d'1 heure",
      "Prévisionnel financier sur 3 ans",
      "Business plan stratégique de 40 pages",
      "Plan stratégique année 1",
      "Pitch impactant et animé",
      "Outils et tableaux de bord",
      "6 semaines de support mail / WhatsApp",
      `★ BONUS : Formation P.O.P incluse (${VALEUR_POP})`,
    ],
  },

  pourQui: {
    titre: "Pour les projets ambitieux qui veulent toutes les cartes en main",
    corps:
      "Un pack pensé pour celles et ceux qui ne veulent rien laisser au hasard et bénéficier d'un accompagnement complet du cadrage à la première année d'activité.",
    profils: [
      {
        titre: "Porteurs de projet ambitieux",
        corps:
          "Vous visez un financement bancaire important ou des investisseurs et vous voulez maximiser vos chances.",
      },
      {
        titre: "Créateurs stratèges",
        corps:
          "Vous voulez comprendre votre projet en profondeur, pas juste cocher des cases administratives.",
      },
      {
        titre: "Demandeurs de financement",
        corps:
          "Vous avez besoin d'un dossier irréprochable + d'un pitch animé pour convaincre vos interlocuteurs.",
      },
      {
        titre: "Futurs dirigeants",
        corps:
          "Vous voulez démarrer avec une vraie méthode de pilotage pour réussir votre première année.",
      },
    ] as CarteDePack[],
  },

  /** Les arguments : ce que le Premium ajoute à l'Essentiel.
   *
   *  DOUTEUX : les trois titres « De contenu », « D'accompagnement », « De
   *  bonus offerts » sont des fins de phrase. Sur le site, chacun est très
   *  probablement précédé d'un gros chiffre ou d'un « + » que le relevé n'a
   *  pas saisi. `chiffre` reste `null` : à relire sur la page. */
  cePlusDuPremium: {
    titre: "Le pack qui va au bout des choses",
    corps:
      "Là où l'Essentiel fournit les fondamentaux, le Premium ajoute la profondeur stratégique, le pitch animé, le plan d'action première année et l'accès à la formation P.O.P.",
    cartes: [
      {
        chiffre: null,
        titre: "De contenu",
        corps:
          "Business plan de 40 pages au lieu de 30, étude de marché premium, et toute la profondeur d'analyse en plus.",
      },
      {
        chiffre: null,
        titre: "D'accompagnement",
        corps:
          "3 appels d'une heure au lieu de 2 de 45 minutes, pour aller vraiment en profondeur sur votre projet.",
      },
      {
        chiffre: null,
        titre: "De bonus offerts",
        corps:
          "La formation P.O.P incluse pour piloter votre activité avec méthode dès votre première année.",
      },
    ] as { chiffre: string | null; titre: string; corps: string }[],
  },

  contenuDuPack: {
    titre: "9 livrables stratégiques + accompagnement renforcé",
    corps:
      "Un kit complet pour cadrer, présenter, défendre et piloter votre projet. Tous les documents sont sur-mesure, rédigés par mes soins, et livrés en format éditable et PDF.",
    livrables: [
      {
        titre: "Cadrage du projet, idée, positionnement",
        corps:
          "Un temps stratégique pour poser les bases : clarifier votre vision, votre proposition de valeur, votre positionnement unique et votre stratégie globale.",
        points: [
          "Clarification de votre vision",
          "Définition de votre proposition de valeur",
          "Positionnement stratégique",
          "Identification de votre différenciation",
        ],
      },
      {
        titre: "Étude de marché & concurrence PREMIUM",
        corps:
          "Une analyse approfondie de votre marché et de vos concurrents, enrichie de recommandations stratégiques opérationnelles et d'une cartographie détaillée.",
        points: [
          "Analyse approfondie du marché et tendances",
          "Cartographie complète des concurrents",
          "Personas détaillés et parcours client",
          "Opportunités stratégiques identifiées",
          "Recommandations opérationnelles",
        ],
      },
      {
        titre: "3 appels personnalisés d'1 heure",
        corps:
          "Trois rendez-vous en visio en profondeur : cadrage, validation à mi-parcours et stratégie de lancement. Un vrai coaching stratégique.",
        points: [
          "Appel 1 : cadrage et vision stratégique",
          "Appel 2 : validation des livrables intermédiaires",
          "Appel 3 : stratégie de lancement et plan d'action",
        ],
      },
      {
        titre: "Prévisionnel financier sur 3 ans",
        corps:
          "Un prévisionnel financier complet et défendable, construit pour convaincre les banques, les investisseurs et piloter votre rentabilité.",
        points: [
          "Plan de financement initial détaillé",
          "Compte de résultat prévisionnel 3 ans",
          "Plan de trésorerie mensuel",
          "Calcul du seuil de rentabilité et point mort",
        ],
      },
      {
        titre: "Business Plan stratégique de 40 pages",
        corps:
          "Le document de référence de votre projet : 40 pages stratégiques et détaillées, conçues spécifiquement pour convaincre banques et investisseurs.",
        points: [
          "Résumé exécutif impactant",
          "Présentation complète du projet",
          "Étude de marché détaillée intégrée",
          "Stratégie commerciale et marketing",
          "Plan financier et hypothèses défendues",
          "Analyse de risques et mesures",
        ],
      },
      {
        titre: "Plan stratégique année 1",
        corps:
          "Une feuille de route opérationnelle pour votre première année : priorités, jalons, indicateurs de réussite. Pour ne plus avancer à l'aveugle.",
        points: [
          "Roadmap trimestrielle",
          "Jalons clés et objectifs mesurables",
          "Priorités commerciales",
          "Indicateurs de pilotage",
        ],
      },
      {
        titre: "Pitch impactant et animé",
        corps:
          "Un pitch percutant pour convaincre vos interlocuteurs en quelques minutes. Animé, mis en page selon la charte EVKHA, prêt à projeter en rendez-vous.",
        points: [
          "Pitch deck complet sur mesure",
          "Animations et transitions soignées",
          "Argumentaire structuré pour banquiers/investisseurs",
          "Version courte et version longue",
        ],
      },
      {
        titre: "Outils et tableaux de bord",
        corps:
          "Une boîte à outils opérationnelle pour piloter votre activité dès le lancement : tableaux de bord, indicateurs, modèles prêts à l'emploi.",
        points: [
          "Tableau de bord de pilotage",
          "Suivi du chiffre d'affaires et marges",
          "Indicateurs clés (KPI)",
          "Modèles opérationnels (devis, facture, suivi client)",
        ],
      },
      {
        titre: `Formation P.O.P incluse (valeur ${VALEUR_POP})`,
        corps:
          `L'accès complet à la formation Méthode P.O.P d'EVKHA : ${HEURES_POP} de formation pour structurer votre activité, organiser votre temps et gagner en rentabilité dès votre première année.`,
        points: [
          `${HEURES_POP} de formation digitale`,
          "Méthode P.O.P : Planifiez, Organisez, Produisez",
          "Accès à un agent IA dédié",
          "Templates et tableaux de bord",
          "Accès à vie à la plateforme",
        ],
      },
    ] as LivrableDePack[],
  },

  formationOfferte: {
    titre: "La formation P.O.P offerte avec votre pack",
    corps: `D'une valeur de ${VALEUR_POP}, la formation P.O.P est habituellement vendue séparément. Elle est intégralement offerte aux clients du Pack Premium. Parce qu'avoir un bon dossier, c'est bien — mais piloter son activité dans la durée, c'est ce qui fait la différence entre les projets qui durent et ceux qui s'essoufflent.`,
    carte: {
      titre: "Planifiez. Organisez. Produisez.",
      corps:
        "Le système EVKHA pour structurer votre activité, reprendre le contrôle de votre temps et gagner en rentabilité dès votre première année d'activité.",
      points: [
        `${HEURES_POP} de formation digitale à votre rythme`,
        "La méthode P.O.P appliquée à votre activité",
        "Outils, templates et tableaux de bord",
        "Accès à un agent IA dédié à vos objectifs",
        "Accès à vie à la plateforme",
      ],
    } satisfies LivrableDePack,
  },

  /** Le titre annonce « 5 étapes » ; la page en affiche SIX blocs, le sixième
   *  étant le support après livraison. Relevé tel quel, dans l'ordre. */
  processus: {
    titre: "Un parcours en 5 étapes sur 3 semaines",
    corps:
      "Un processus stratégique, balisé, qui vous emmène du cadrage de votre idée jusqu'à la livraison de votre kit complet et de votre formation P.O.P.",
    etapes: [
      {
        titre: "Vous commandez votre pack Premium",
        corps:
          "Validation de la commande, accès immédiat à la formation P.O.P, envoi du questionnaire de cadrage et lien pour réserver votre premier appel.",
      },
      {
        titre: "Appel 1 : cadrage stratégique (1h)",
        corps:
          "Un échange approfondi pour cadrer votre vision, votre positionnement, votre proposition de valeur et toutes les hypothèses fondatrices de votre projet.",
      },
      {
        titre: "Rédaction des livrables stratégiques",
        corps:
          "Je travaille votre étude de marché premium, votre prévisionnel financier détaillé et votre business plan de 40 pages. Échanges réguliers par mail/WhatsApp.",
      },
      {
        titre: "Appel 2 : validation à mi-parcours (1h)",
        corps:
          "On parcourt ensemble les livrables principaux, on ajuste les hypothèses, on affine les recommandations stratégiques pour la suite.",
      },
      {
        titre: "Livraison complète + appel 3 : lancement (1h)",
        corps:
          "Remise des 9 livrables : étude premium, prévisionnel, business plan 40 pages, plan stratégique année 1, pitch animé, tableaux de bord. Appel final dédié à votre stratégie de lancement et à votre plan d'action.",
      },
      {
        titre: "Support mail / WhatsApp exclusif",
        corps:
          "Pendant 6 semaines après la livraison, vous me sollicitez librement pour toute question, ajustement, préparation de rendez-vous bancaire ou décision stratégique. Réponse sous 24-48h.",
      },
    ] as CarteDePack[],
  },

  /** Le titre et l'introduction viennent de l'inventaire ; les douze lignes
   *  du tableau ont été relevées sur le site le 19/11/2026, dans l'ordre. Les
   *  deux prix et la valeur de la formation lisent `TARIFS_PACKS`.
   *
   *  À NOTER : le tableau coche « Prévisionnel financier 3 ans » pour le
   *  Premium, alors que la carte du Premium sur `/packs` ne le liste pas
   *  (voir `PAGE_PACKS.packPremium`). */
  comparatif: {
    titre: "Essentiel vs Premium : ce qui change vraiment",
    corps:
      "Si vous hésitez encore, voici la comparaison rapide entre les deux packs pour faire le bon choix.",
    colonnes: { essentiel: "Essentiel", premium: "Premium" },
    lignes: [
      {
        critere: "Étude de marché & concurrence",
        essentiel: "✓ Standard",
        premium: "✓ Premium",
      },
      { critere: "Prévisionnel financier 3 ans", essentiel: "✓", premium: "✓" },
      { critere: "Business plan", essentiel: "30 pages", premium: "40 pages" },
      {
        critere: "Cadrage projet et positionnement",
        essentiel: "—",
        premium: "✓",
      },
      { critere: "Plan stratégique année 1", essentiel: "—", premium: "✓" },
      { critere: "Pitch impactant animé", essentiel: "—", premium: "✓" },
      { critere: "Outils et tableaux de bord", essentiel: "—", premium: "✓" },
      {
        critere: "Appels d'accompagnement",
        essentiel: "2 × 45 min",
        premium: "3 × 1 heure",
      },
      {
        critere: "Formation P.O.P incluse",
        essentiel: "—",
        premium: `★ Valeur ${VALEUR_POP}`,
      },
      {
        critere: "Support mail / WhatsApp",
        essentiel: "6 semaines",
        premium: "6 semaines",
      },
      {
        critere: "Délai de livraison",
        essentiel: "1 à 2 sem.",
        premium: "3 semaines",
      },
      { critere: "Prix", essentiel: PRIX_ESSENTIEL, premium: PRIX_PREMIUM },
    ] as LigneDeComparatif[],
  },

  experte: {
    titre: "Une experte stratégique, pas un prestataire interchangeable",
    corps:
      "Le Pack Premium, c'est aussi le pack où la dimension humaine compte le plus. 3 heures d'appels en visio, 6 semaines de suivi rapproché, et la garantie qu'à chaque échange, c'est moi qui suis en face de vous. Avec 16 ans d'accompagnement de créateurs d'entreprise et plus de 500 projets à mon actif, je ne fais pas du remplissage de documents : je vous apporte une vraie expertise stratégique pour faire les bons choix.",
  },

  /** Neuf questions et leurs réponses, dans l'ordre de la page — voir
   *  `QuestionDePack` pour la provenance de chacune des deux moitiés. */
  faq: {
    titre: "Tout ce que vous voulez savoir avant de commander",
    questions: [
      {
        question: "Quelle est la vraie différence avec le Pack Essentiel ?",
        reponse: `Le Premium est nettement plus complet : 3 appels d'1h au lieu de 2 de 45 min, business plan de 40 pages au lieu de 30, étude de marché premium, cadrage stratégique en amont, plan stratégique année 1, pitch animé, tableaux de bord, ET la formation P.O.P (valeur ${VALEUR_POP}). Si vous visez un financement important, un pitch devant des investisseurs ou un projet ambitieux, le Premium est fait pour vous.`,
      },
      {
        question:
          "Quand est-ce que je commence à avoir accès à la formation P.O.P ?",
        reponse:
          "Dès la validation de votre commande, vous recevez vos accès à la formation P.O.P. Vous pouvez la commencer immédiatement, en parallèle du travail sur les livrables. La plupart des clients la suivent pendant les 3 semaines de réalisation du pack pour être opérationnel dès la livraison.",
      },
      {
        question: "Le pitch animé, c'est quoi exactement ?",
        reponse:
          "C'est un pitch deck complet (à la manière d'une présentation PowerPoint ou Keynote), mis en page selon la charte EVKHA, avec des animations professionnelles et des transitions soignées. Vous projetez ce pitch lors de vos rendez-vous bancaires ou avec des investisseurs. Vous repartez avec deux versions : une longue (10-12 slides) et une courte (5-6 slides) pour les pitchs de moins de 5 minutes.",
      },
      {
        question:
          "3 semaines, c'est long. Est-ce qu'on peut aller plus vite ?",
        reponse:
          "3 semaines correspond à un délai stratégique pour bien faire les choses : creuser le cadrage, prendre le temps de la réflexion entre les appels, livrer des documents premium. Si vous avez une vraie urgence, on peut en discuter au moment du cadrage : un délai accéléré reste possible dans certains cas.",
      },
      {
        // La question dit « pas viable », la réponse parle de « failles
        // majeures » traitées ensemble : appariement par l'ordre de la page,
        // cohérent, mais la réponse ne dit pas ce qui se passe si le projet
        // n'est réellement pas viable.
        question:
          "Et si après l'appel de cadrage, on se rend compte que mon projet n'est pas viable ?",
        reponse:
          "C'est précisément à ça que sert le cadrage. Si on identifie des failles majeures dans votre projet, on les traite ensemble avant d'avancer. L'objectif n'est pas de remplir des documents pour remplir, mais de vous donner un projet solide. Mieux vaut ajuster maintenant que de le découvrir devant le banquier.",
      },
      {
        question: "Sous quel format je reçois les documents ?",
        reponse:
          "Chaque livrable est remis en format éditable (Word, Excel, PowerPoint selon le document) et en PDF mis en page selon la charte EVKHA. Vous pouvez les modifier, les imprimer, les transmettre tels quels à votre banquier ou à un investisseur.",
      },
      {
        question: "Le paiement en plusieurs fois est-il possible ?",
        reponse:
          "Oui, vous pouvez régler en plusieurs fois sans frais. Les modalités exactes vous seront présentées sur la page de paiement.",
      },
      {
        question: "Comment se passe le suivi de 6 semaines après la livraison ?",
        reponse:
          "Pendant 6 semaines après la livraison complète, vous bénéficiez d'un accès exclusif à un canal mail/WhatsApp pour toute question : ajustement d'un chiffre, préparation d'un rendez-vous bancaire, validation d'une décision stratégique, conseils sur la mise en pratique de la méthode P.O.P. Réponse sous 24 à 48h.",
      },
      {
        // « 30 000 € » : un seuil de financement du projet du client, pas un
        // prix d'offre — il n'a donc pas sa place dans `TARIFS_PACKS`.
        question: "Quels types de projets sont compatibles ?",
        reponse:
          "Le Pack Premium convient particulièrement aux projets qui nécessitent un dossier solide : créations de sociétés (EURL, SARL, SASU, SAS), projets nécessitant un financement bancaire de plus de 30 000\u00a0€, projets innovants, projets avec investisseurs ou associés. Tous les secteurs sont compatibles.",
      },
    ] as QuestionDePack[],
  },

  appelFinal: {
    titre: "Donnez à votre projet toutes ses chances",
    corps:
      "9 livrables stratégiques, 3 appels d'1h, 6 semaines de support, et la formation P.O.P incluse. Le pack complet pour les projets ambitieux qui ne veulent rien laisser au hasard.",
    mention:
      "Paiement sécurisé · Accès immédiat à la formation P.O.P après commande",
  },

  formulaireDeCommande: {
    titre: "Je commande mon PACK PREMIUM !",
    rubrique: "ADRESSE",
    codeDeReduction: "Ajout d'un code de réduction sur la page suivante",
    consentementCgv:
      "Oui, je certifie accepter les Conditions générales de vente et d'utilisation",
    consentementCourriels:
      "Oui, je consens à recevoir des emails et newsletter d'EVKHA.fr",
    bouton: "Profiter de l'offre",
  } satisfies FormulaireDeCommande,
};

// ════════════════════════════════════════════════════════════════════════════
// CE QUE LA PLATEFORME AJOUTE AU TEXTE RELEVÉ (`Packs.tsx`)
//
// Tout ce qui précède est le texte de la cliente. Ce qui suit est écrit pour
// les trois pages de la plateforme : leurs adresses, quel mot d'un titre passe
// en italique, les surtitres, les intitulés de boutons, les phrases de
// liaison — et les trois accords qui empêchent une page d'afficher un nombre
// qu'elle contredit elle-même. À VALIDER par la cliente.
// ════════════════════════════════════════════════════════════════════════════

// ── Adresses et prix affichés ───────────────────────────────────────────────

/** Les trois pages, sur la plateforme. Un ALIAS : chaque chemin est lu dans
 *  `contenuSite.CHEMINS`, la seule source des adresses du site (règle 5) ; le
 *  nom est gardé pour les fichiers qui l'importent. Les boutons d'ACHAT, eux,
 *  mènent encore aux pages de paiement du site (`LIENS_PACKS`) : la plateforme
 *  n'encaisse pas ces offres. */
export const ROUTES_PACKS = {
  ensemble: CHEMINS.packs,
  essentiel: CHEMINS.packEssentiel,
  premium: CHEMINS.packPremium,
} as const;

/** Les deux prix de vente, tels qu'ils s'affichent. Lus dans `TARIFS_PACKS` :
 *  aucun montant n'est écrit ici. */
export const PRIX_DES_PACKS = {
  essentiel: PRIX_ESSENTIEL,
  premium: PRIX_PREMIUM,
} as const;

/** Le portrait de la fondatrice, déjà servi par la plateforme. Les dimensions
 *  sont celles du fichier : elles donnent le ratio, la feuille la taille. */
export const PORTRAIT_DES_PACKS = {
  adresse: "/partenaires/evangeline.jpg",
  alt: "Evangeline Khaili, fondatrice d'EVKHA, dans son bureau",
  largeur: 798,
  hauteur: 1200,
};

// ── Les accords : une page n'affiche pas un nombre qu'elle contredit ────────

/** Les deux mots devant lesquels une page écrit un nombre à accorder. */
export const UNITES_A_ACCORDER = { etapes: "étapes", livrables: "livrables" } as const;

// L'ancienneté (« 15 ans » ici, « 16 ans » là, non tranché — voir l'en-tête)
// s'affiche « plus de 15 ans » par `site.ancienneteSure`, la fonction que les
// formations utilisent aussi : elle n'est plus écrite dans ce fichier.

/** Remplace le nombre écrit devant `unite` par celui qu'on a compté.
 *  « en 5 étapes » devient « en 6 étapes » quand la page en affiche six. Un
 *  texte qui n'annonce aucun nombre est rendu tel quel. */
export function compteRendu(texte: string, unite: string, nombre: number): string {
  return texte.replace(new RegExp(`\\d+(?=\\s${unite}(?![\\wà-ÿ]))`, "g"), String(nombre));
}

/** Retire le nombre écrit devant `unite`, quand la page ne permet pas de le
 *  recompter. « Remise des 9 livrables : » devient « Remise des livrables : » ;
 *  en tête de phrase, la majuscule est rétablie. */
export function sansCompte(texte: string, unite: string): string {
  const sans = texte.replace(
    new RegExp(`\\d+\\s(?=${unite}(?![\\wà-ÿ]))`, "g"),
    "",
  );
  return sans !== texte && sans.startsWith(unite)
    ? sans.charAt(0).toUpperCase() + sans.slice(1)
    : sans;
}

/** Un point de liste, et s'il s'agit du bonus mis en avant. L'étoile que le
 *  site écrit en tête de ligne devient la puce de la ligne. */
export function pointDeListe(point: string): { texte: string; vedette: boolean } {
  return {
    texte: point.replace(/^★\s*/, ""),
    vedette: /^(?:★\s*)?BONUS(?![\wà-ÿ])/.test(point),
  };
}

/** Un libellé de bouton sans sa flèche finale : le bouton de la plateforme
 *  dessine déjà la sienne. */
export function sansFleche(libelle: string): string {
  return libelle.replace(/\s*→\s*$/, "");
}

// ── Les titres, en deux temps ───────────────────────────────────────────────

export type DeuxTemps = { avant: string; fin: string };

/** Un titre relevé, coupé en deux pour que sa fin passe en italique, comme
 *  sur l'accueil et la page des études. Le titre n'est pas réécrit. S'il ne se
 *  termine plus par l'accent attendu, le module LÈVE une erreur : un titre
 *  amputé passerait inaperçu. */
function enDeuxTemps(titre: string, accent: string): DeuxTemps {
  if (accent === "" || !titre.endsWith(accent) || titre.length === accent.length) {
    throw new Error(
      `contenuPacks : le titre « ${titre} » ne se termine pas par « ${accent} »`,
    );
  }
  return { avant: titre.slice(0, -accent.length).trimEnd(), fin: accent };
}

export const TITRES_PACKS = {
  ouverture: enDeuxTemps(PAGE_PACKS.ouverture.titre, "nos packs sur-mesure"),
  comparatif: enDeuxTemps(
    PAGE_PACK_PREMIUM.comparatif.titre,
    "ce qui change vraiment",
  ),
  experte: enDeuxTemps(
    PAGE_PACK_ESSENTIEL.experte.titre,
    "pas un junior dans une agence",
  ),
};

export const TITRES_PACK_ESSENTIEL = {
  ouverture: enDeuxTemps(PAGE_PACK_ESSENTIEL.ouverture.titre, "Essentiel"),
  pourQui: enDeuxTemps(PAGE_PACK_ESSENTIEL.pourQui.titre, "démarrer vite et bien"),
  seulOuAccompagne: enDeuxTemps(
    PAGE_PACK_ESSENTIEL.seulOuAccompagne.titre,
    "c'est long et risqué",
  ),
  contenuDuPack: enDeuxTemps(
    PAGE_PACK_ESSENTIEL.contenuDuPack.titre,
    "accompagnement personnalisé",
  ),
  processus: enDeuxTemps(
    PAGE_PACK_ESSENTIEL.processus.titre,
    "à votre dossier finalisé",
  ),
  support: enDeuxTemps(PAGE_PACK_ESSENTIEL.support.titre, "après la livraison"),
  aQuoiSertLePack: enDeuxTemps(PAGE_PACK_ESSENTIEL.aQuoiSertLePack.titre, "ce pack"),
  apercuDesDocuments: enDeuxTemps(
    PAGE_PACK_ESSENTIEL.apercuDesDocuments.titre,
    "prêts à l'emploi",
  ),
  experte: TITRES_PACKS.experte,
  faq: enDeuxTemps(PAGE_PACK_ESSENTIEL.faq.titre, "avant de commander"),
  versLePremium: enDeuxTemps(PAGE_PACK_ESSENTIEL.versLePremium.titre, "va plus loin"),
  appelFinal: enDeuxTemps(
    PAGE_PACK_ESSENTIEL.appelFinal.titre,
    "avec des bases solides",
  ),
};

export const TITRES_PACK_PREMIUM = {
  ouverture: enDeuxTemps(PAGE_PACK_PREMIUM.ouverture.titre, "Premium"),
  pourQui: enDeuxTemps(PAGE_PACK_PREMIUM.pourQui.titre, "toutes les cartes en main"),
  cePlusDuPremium: enDeuxTemps(
    PAGE_PACK_PREMIUM.cePlusDuPremium.titre,
    "au bout des choses",
  ),
  contenuDuPack: enDeuxTemps(
    PAGE_PACK_PREMIUM.contenuDuPack.titre,
    "accompagnement renforcé",
  ),
  formationOfferte: enDeuxTemps(
    PAGE_PACK_PREMIUM.formationOfferte.titre,
    "offerte avec votre pack",
  ),
  processus: enDeuxTemps(PAGE_PACK_PREMIUM.processus.titre, "sur 3 semaines"),
  comparatif: TITRES_PACKS.comparatif,
  experte: enDeuxTemps(
    PAGE_PACK_PREMIUM.experte.titre,
    "pas un prestataire interchangeable",
  ),
  faq: enDeuxTemps(PAGE_PACK_PREMIUM.faq.titre, "avant de commander"),
  appelFinal: enDeuxTemps(PAGE_PACK_PREMIUM.appelFinal.titre, "toutes ses chances"),
};

// ── Ce que les trois pages ont en commun ────────────────────────────────────

/** La différence entre un pack et une étude de la plateforme, dite en haut de
 *  chaque page (stratégie commerciale) : un pack est réalisé par Evangeline
 *  elle-même. La seconde phrase reprend ce que les pages affirment déjà —
 *  « c'est moi qui m'en occupe, de A à Z. Pas de sous-traitance ». */
export const COMMUN_PACKS = {
  realisePar: "Réalisé par Evangeline Khaili elle-même",
  realiseCorps:
    "Un pack n'est pas produit par la plateforme : Evangeline réalise elle-même votre dossier, de A à Z, sans sous-traitance.",
  appelGratuit: "Réserver un appel gratuit",
  voirLesDeuxPacks: "Voir les deux packs",
  /** Sous le prix, dans l'encart de l'ouverture d'un pack. */
  libelleDuPrix: "Tarif",
  /** Le nom accessible de la liste de l'encart. */
  nomDesPoints: "Ce que le pack comprend",
  surtitreExperte: "Votre interlocutrice",
  surtitreFaq: "Questions fréquentes",
};

/** Le comparatif, rendu en tableau. Les signes du site (« ✓ », « — », « ★ »)
 *  restent affichés ; un lecteur d'écran, lui, entend leur lecture. */
export const COMPARATIF_PACKS = {
  surtitre: "Comparatif",
  legende: "Ce que comprend chaque pack, critère par critère",
  colonneDesCriteres: "Critère",
  signes: [
    { signe: "✓", lecture: "Inclus", ton: "oui" },
    { signe: "—", lecture: "Non inclus", ton: "non" },
    { signe: "★", lecture: "Bonus", ton: "bonus" },
  ],
  /** Sur la page du Premium, sous le tableau : le renvoi vers l'autre pack. */
  versLEssentiel: "Voir le Pack Essentiel",
  versLePremium: "Voir le Pack Premium",
};

/** Avant l'appel final : la passerelle vers les études à l'unité. SANS PRIX —
 *  la page des études lit les siens au serveur. */
export const PASSERELLE_PACKS = {
  surtitre: "Autrement",
  titre: { avant: "Besoin d'un", fin: "seul document ?" } satisfies DeuxTemps,
  corps:
    "Étude de marché, étude de la concurrence, business plan ou stratégie : chaque étude se commande aussi séparément, sur la plateforme.",
  bouton: "Voir les études",
};

// ── Page d'ensemble ─────────────────────────────────────────────────────────

export const ENSEMBLE_PACKS = {
  surtitre: "Packs d'accompagnement",
  comparer: "Comparer les deux packs",
  idDuComparatif: "comparatif",
  idDesPacks: "les-packs",
  /** Le nom accessible de la section des deux cartes. */
  nomDesPacks: "Les deux packs",
  detail: "Voir le détail",
  /** Bandeau défilant, décoratif : il ne répète que ce que la page dit. */
  ruban: [
    "Étude de marché",
    "Étude de la concurrence",
    "Business plan",
    "Appels en visio",
    "6 semaines de support",
    "Format éditable et PDF",
    "Réalisé par Evangeline",
  ],
  fin: {
    titre: { avant: "Un doute sur le pack", fin: "qu'il vous faut ?" } satisfies DeuxTemps,
    corps:
      "Un appel gratuit permet d'en parler de vive voix avant de commander.",
  },
};

// ── Les deux pages de pack ──────────────────────────────────────────────────

/** Ce qu'une page de pack ajoute à son texte relevé. Les deux pages sont
 *  jumelles : même forme, un contenu chacune.
 *
 *  `titreDeLOnglet` : celui du site (« PAGE DE PAIEMENT pack créa ») est un
 *  nom de travail, identique sur les deux pages. Réécrit, court. La
 *  description de la page, elle, est le chapeau de son ouverture — la phrase
 *  de la cliente.
 *
 *  `compteDeLivrablesFiable` : la page de l'Essentiel annonce « 3 livrables »
 *  et en montre trois, partout. Celle du Premium annonce « 9 livrables », en
 *  énumère six à l'étape de livraison, et compte ailleurs les appels et la
 *  formation À PART de ces neuf : le nombre n'y est donc pas affiché. */
export type ArticulationDePack = {
  titreDeLOnglet: string;
  surtitre: string;
  prix: string;
  duree: string;
  commande: BoutonDePack;
  compteDeLivrablesFiable: boolean;
  surtitres: Record<string, string>;
};

const SURTITRES_COMMUNS = {
  pourQui: "Pour qui",
  contenuDuPack: "Contenu du pack",
  processus: "Le déroulé",
};

export const ARTICULATION_PACK_ESSENTIEL = {
  titreDeLOnglet:
    "Pack Création Essentiel : étude de marché, prévisionnel et business plan – EVKHA",
  surtitre: "Pack d'accompagnement",
  prix: PRIX_ESSENTIEL,
  duree: PAGE_PACKS.packEssentiel.duree,
  commande: PAGE_PACKS.packEssentiel.bouton,
  compteDeLivrablesFiable: true,
  surtitres: {
    ...SURTITRES_COMMUNS,
    seulOuAccompagne: "Seul ou accompagné",
    eviter: "Sans le pack",
    obtenir: "Avec le pack",
    support: "Après la livraison",
    aQuoiSertLePack: "À quoi il sert",
    apercuDesDocuments: "Aperçu des documents",
    autrePack: "L'autre pack",
  },
} satisfies ArticulationDePack;

export const ARTICULATION_PACK_PREMIUM = {
  titreDeLOnglet:
    "Pack Création Premium : business plan, pitch animé et formation P.O.P – EVKHA",
  surtitre: "Pack d'accompagnement",
  prix: PRIX_PREMIUM,
  duree: PAGE_PACKS.packPremium.duree,
  commande: PAGE_PACKS.packPremium.bouton,
  compteDeLivrablesFiable: false,
  surtitres: {
    ...SURTITRES_COMMUNS,
    cePlusDuPremium: "Ce que le Premium ajoute",
    formationOfferte: "Bonus",
  },
} satisfies ArticulationDePack;
