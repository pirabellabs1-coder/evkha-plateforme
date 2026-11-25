/** Ce que la refonte de la page des partenaires (`Partenaires.tsx`) AJOUTE au
 * texte de la cliente.
 *
 * Le texte de la page — ouverture, preuves, principe, cibles, calcul,
 * fondatrice, questions, appel final — reste dans `contenu.ts`, repris de son
 * site et non réécrit. Ce fichier porte deux choses :
 *
 * 1. ce que la nouvelle forme demande en plus : où un titre se coupe pour que
 *    sa fin passe en italique, les surtitres, les intitulés de boutons, les
 *    phrases d'état, la passerelle vers les études à l'unité ;
 * 2. les courtes phrases que l'ANCIENNE page écrivait dans son TSX (le titre
 *    et l'introduction des formules, les lignes d'une carte de formule, le
 *    bouton de souscription) : elles sont ici mot pour mot, pour que le TSX
 *    n'écrive plus aucun texte.
 *
 * Éditorial uniquement : AUCUN PRIX, aucun nombre de crédits. Ils viennent de
 * `/api/public/formules/` ; le test
 * `la-page-partenaires-lit-ses-formules-au-serveur` verrouille qu'aucun
 * montant ne figure ici. Le seul montant que la page affiche sans le tenir du
 * serveur est celui que la cliente écrit dans SA phrase sur les cabinets
 * (`contenu.CALCUL`) : il est LU dans cette phrase, pas recopié — voir
 * `DEMONSTRATION`.
 */
import { CALCUL, FAQ, FONDATRICE, APPEL_FINAL, HERO, POUR_QUI, PRINCIPE } from "./contenu";
import { LIENS } from "./contenuSite";

// ── Les titres, en deux temps ───────────────────────────────────────────────

export type DeuxTemps = { avant: string; fin: string };

/** Un titre de la cliente, coupé en deux pour que sa fin passe en italique
 *  (Fraunces), comme sur l'accueil et la page des études. Le titre n'est PAS
 *  réécrit : on désigne seulement où il se coupe.
 *
 *  Si le titre ne se termine plus par l'accent attendu — parce qu'il a été
 *  retouché dans `contenu.ts` —, le module LÈVE une erreur au chargement :
 *  rendre un titre amputé passerait inaperçu (règle 1). L'erreur, elle, casse
 *  les tests de la page. Même garde que `contenuEtudes.ts`, dont la fonction
 *  n'est pas exportée. */
function enDeuxTemps(titre: string, accent: string): DeuxTemps {
  if (accent === "" || !titre.endsWith(accent) || titre.length === accent.length) {
    throw new Error(
      `contenuPartenaires : le titre « ${titre} » ne se termine pas par « ${accent} »`,
    );
  }
  return { avant: titre.slice(0, -accent.length).trimEnd(), fin: accent };
}

/** Le titre de la section des formules, tel que l'ancienne page l'écrivait. */
const TITRE_DES_FORMULES = "Quatre formules, zéro droit d'entrée";

export const TITRES_PRO = {
  principe: enDeuxTemps(PRINCIPE.titre, "des livrables"),
  formules: enDeuxTemps(TITRE_DES_FORMULES, "zéro droit d'entrée"),
  pourQui: enDeuxTemps(POUR_QUI.titre, "QUI ?"),
  calcul: enDeuxTemps(CALCUL.titre, "est simple"),
  fondatrice: enDeuxTemps(FONDATRICE.titre, "16 ans d'accompagnement"),
  faq: enDeuxTemps(FAQ.titre, "le plus souvent"),
  appel: enDeuxTemps(APPEL_FINAL.titre, "la profondeur d'analyse d'un cabinet."),
};

// ── L'onglet ────────────────────────────────────────────────────────────────

/** Le titre de l'onglet, récrit le 20/11/2026 pour dire ce que la page VEND
 *  dans les mots qu'un porteur de projet tape dans un moteur — le titre
 *  d'avant (« Partenaires PRO et abonnements ») ne nommait aucun des documents. À faire valider par la
 *  cliente (`docs/referencement/etat-et-plan.md`). */
export const TITRE_DE_LA_PAGE_PRO =
  "Études et business plans sous votre marque, pour les pros — EVKHA";
/** La description, pour les moteurs : la phrase de la cliente qui dit ce que
 *  l'abonnement produit, pas une phrase de plus. */
export const DESCRIPTION_DE_LA_PAGE_PRO = HERO.corps[0];

// ── Ouverture ───────────────────────────────────────────────────────────────

/** L'identifiant de la section des formules : le bouton de l'ouverture y
 *  mène, et l'appel final aussi tant qu'aucune formule n'est connue. */
export const ID_DES_FORMULES = "formules";

export const OUVERTURE_PRO = {
  surtitre: "Partenaires PRO · Abonnements",
  /** Les deux gestes de l'ancienne page, mêmes libellés, mêmes adresses. */
  formules: { libelle: "Découvrir les formules", lien: `#${ID_DES_FORMULES}` },
  espace: { libelle: "Créer son espace client", lien: LIENS.espace },
  nomDesPreuves: "EVKHA en chiffres",
  /** `public/partenaires/reunion.jpg`. Les dimensions donnent le RATIO, qui
   *  réserve la place de l'image avant son chargement. */
  image: {
    adresse: "/partenaires/reunion.jpg",
    alt: "Trois personnes en réunion de travail autour d'un ordinateur portable",
    largeur: 1500,
    hauteur: 1001,
  },
};

// ── Le principe ─────────────────────────────────────────────────────────────

/** Le bandeau « 1 crédit = 1 livrable », coupé à son tiret : ce qui précède
 *  est mis en avant, la suite reste telle quelle (tiret compris — la phrase
 *  de la cliente se lit entière dans la page). Sans tiret, le module lève une
 *  erreur plutôt que d'afficher un bandeau sans son accroche (règle 1). */
function coupeAuTiret(phrase: string): { fort: string; suite: string } {
  const tiret = phrase.indexOf(" — ");
  if (tiret <= 0) {
    throw new Error(
      `contenuPartenaires : le bandeau « ${phrase} » n'a plus son tiret`,
    );
  }
  return { fort: phrase.slice(0, tiret), suite: phrase.slice(tiret) };
}

export const BANDEAU_DU_PRINCIPE = coupeAuTiret(PRINCIPE.bandeau);

// ── Les formules ────────────────────────────────────────────────────────────

/** Les mots d'une carte de formule. Les NOMBRES n'y sont pas : la page les
 *  reçoit du serveur et les passe à ces fonctions. Les phrases sont celles de
 *  l'ancienne page. */
export const FORMULES_PRO = {
  surtitre: "Les formules",
  /** L'introduction que l'ancienne page écrivait sous le titre. */
  intro:
    "Abonnement mensuel avec crédits inclus. Prix nets, tout compris\u00a0: TVA non applicable, article 293\u00a0B du CGI. Engagement minimum de 3\u00a0mois, puis sans engagement. Crédits supplémentaires à tarif dégressif.",
  /** Sur la carte que le serveur met en avant (`mise_en_avant`). */
  enAvant: "Formule conseillée",
  parMois: "/ mois",
  quoi: "Ce que vous obtenez :",
  /** « 5 crédits inclus » — accordé sur le nombre reçu. */
  credits: (nombre: number) =>
    `${nombre} crédit${nombre > 1 ? "s" : ""} inclus`,
  chaqueMois: "chaque mois",
  creditSupplementaire: "Crédit supplémentaire\u00a0:",
  /** « Soit 64,50 € par livrable inclus » : le montant vient entre les deux. */
  coutAvant: "Soit",
  coutApres: "par livrable inclus",
  souscrire: (libelle: string) => `Souscrire à ${libelle}`,
  attente: "Chargement des formules…",
  /** Le catalogue a répondu, et il ne porte aucune formule. */
  vide: "Aucune formule n'est proposée pour le moment.",
};

// ── Ruban ───────────────────────────────────────────────────────────────────

/** Bandeau défilant sous les formules. Décoratif (masqué aux lecteurs
 *  d'écran) : il ne répète que ce que la page écrit en toutes lettres — les
 *  quatre étapes du principe, puis la signature de l'ouverture. */
export const RUBAN_PRO = [
  ...PRINCIPE.etapes.map((etape) => etape.titre),
  HERO.signature,
];

// ── Le calcul : la démonstration ────────────────────────────────────────────

/** Ce qu'un cabinet facture, LU dans la phrase de la cliente
 *  (`CALCUL.colonnes[0].corps` : « Un cabinet facture jusqu'à … par
 *  livrable »). Le montant n'est écrit qu'une fois, là-bas ; ici on le
 *  retrouve. `null` si la phrase ne le dit plus : la démonstration n'affiche
 *  alors que le coût de l'abonné, sans rien inventer en face. */
function prixDUnCabinet(phrase: string): { avant: string; montant: string } | null {
  const trouve = phrase.match(/(jusqu'à)\s+(\d[\d\s]*€)/);
  return trouve ? { avant: trouve[1], montant: trouve[2] } : null;
}

export const DEMONSTRATION = {
  /** Sous la fourchette calculée sur les formules reçues. */
  mentionDuCout: "par livrable inclus dans votre formule",
  /** En face : ce que facture un cabinet, selon la phrase de la cliente. */
  cabinet: prixDUnCabinet(CALCUL.colonnes[0].corps),
  etiquetteDuCabinet: "Ce qu'un cabinet facture",
  mentionDuCabinet: "par livrable",
  /** Le nom de la liste des deux autres gains (temps, catalogue). */
  nomDesGains: "Ce que l'abonnement change aussi",
};

// ── La fondatrice ───────────────────────────────────────────────────────────

/** `public/partenaires/evangeline.jpg`. */
export const PORTRAIT_PRO = {
  adresse: "/partenaires/evangeline.jpg",
  alt: "Evangeline Khaili, fondatrice d'Evkha",
  largeur: 798,
  hauteur: 1200,
};

// ── Passerelle : les études à l'unité ───────────────────────────────────────

/** Le renvoi vers les études à l'unité. Le corps est la phrase de la cliente
 *  (`CALCUL.liseré`), entière ; l'ancienne page en faisait deux liens vers
 *  `/etudes`, la nouvelle un seul bouton. */
export const PASSERELLE_PRO = {
  surtitre: "À l'unité",
  titre: { avant: "Un seul dossier,", fin: "sans abonnement." } as DeuxTemps,
  corps: CALCUL.liseré,
  bouton: "Voir les études à l'unité",
  lien: LIENS.etudes,
};

// ── Appel final ─────────────────────────────────────────────────────────────

export const FIN_PRO = {
  /** Le bouton de l'ancienne page disait « CHOISIR LA FORMULE PRO » : le nom
   *  de la formule est désormais celui que le serveur met en avant. */
  choisir: (libelle: string) => `Choisir la formule ${libelle}`,
  /** Tant qu'aucune formule mise en avant n'est connue. */
  voirLesFormules: "Découvrir les formules",
  /** « Écrivez-nous, ou demandez un modèle d'étude » : un courriel prérempli. */
  ecrire: "Nous écrire",
  objetDuCourriel: "Partenaires PRO : une question avant de souscrire",
};
