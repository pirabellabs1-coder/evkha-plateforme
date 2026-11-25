/** Ce que la refonte de la page des études (`NosEtudes.tsx`) AJOUTE au texte de
 * la cliente.
 *
 * Le texte de la page — accroche, étapes, argumentaires, questions, comparatif
 * — reste dans `contenu.ts` (`ETUDES`, `ETUDES_PAGE`), repris de son site et
 * non réécrit. Ce fichier ne porte que ce que la nouvelle forme demande en
 * plus : quel mot d'un titre passe en italique, les libellés courts de la
 * barre d'ancres, la ligne qui nomme le document suivant du parcours, la
 * passerelle vers la boutique et les abonnements, les phrases d'état.
 *
 * Éditorial uniquement : AUCUN PRIX, aucun nombre de crédits, aucune durée
 * d'engagement. Les tarifs viennent de `/api/public/livrables/` ; le test
 * `la-page-des-etudes-lit-ses-prix-au-serveur` verrouille qu'aucun montant ne
 * figure ici. Ni remise ni lot : la plateforme ne vend pas de pack, et la
 * ligne « ensuite dans le parcours » ne promet rien de tel.
 */
import { ETUDES, ETUDES_PAGE } from "./contenu";
import { LIENS } from "./contenuSite";

// ── Les titres, en deux temps ───────────────────────────────────────────────

/** Un titre de la cliente, coupé en deux pour que sa fin passe en italique
 *  (Fraunces), comme les titres de l'accueil. Le titre n'est PAS réécrit : on
 *  désigne seulement où il se coupe.
 *
 *  Si le titre ne se termine plus par l'accent attendu — parce qu'il a été
 *  retouché dans `contenu.ts` —, le module LÈVE une erreur au chargement :
 *  rendre un titre amputé, ou sans son italique, passerait inaperçu
 *  (règle 1). L'erreur, elle, casse les tests de la page. */
function enDeuxTemps(titre: string, accent: string): { avant: string; fin: string } {
  if (accent === "" || !titre.endsWith(accent) || titre.length === accent.length) {
    throw new Error(
      `contenuEtudes : le titre « ${titre} » ne se termine pas par « ${accent} »`,
    );
  }
  return { avant: titre.slice(0, -accent.length).trimEnd(), fin: accent };
}

export const TITRES = {
  ouverture: enDeuxTemps(ETUDES_PAGE.hero.titre, "rentable et viable ?"),
  methode: enDeuxTemps(ETUDES_PAGE.methode.titre, "ça marche ?"),
  choix: enDeuxTemps(ETUDES_PAGE.choix.titre, "à votre besoin"),
  interrogations: enDeuxTemps(
    ETUDES_PAGE.interrogations.titre,
    "de TOUT porteur de projet",
  ),
  comparatif: enDeuxTemps(ETUDES_PAGE.comparatif.titre, "ne sera pas la vôtre."),
  faq: enDeuxTemps(ETUDES_PAGE.faq.titre, "le plus souvent"),
  appel: enDeuxTemps(ETUDES_PAGE.appel.titre, "des réponses claires."),
};

// ── L'onglet ────────────────────────────────────────────────────────────────

/** Le titre de l'onglet, récrit le 20/11/2026 pour dire ce que la page VEND
 *  dans les mots qu'un porteur de projet tape dans un moteur — le titre
 *  d'avant (« Nos études et livrables ») ne nommait aucun des documents. À faire valider par la
 *  cliente (`docs/referencement/etat-et-plan.md`). */
export const TITRE_DE_LA_PAGE =
  "Faire faire son étude de marché ou son business plan — EVKHA";
/** La description de la page, pour les moteurs : la phrase de la cliente qui
 *  dit ce que sont les quatre études, pas une phrase de plus. */
export const DESCRIPTION_DE_LA_PAGE = ETUDES_PAGE.choix.corps;

// ── Ouverture ───────────────────────────────────────────────────────────────

/** Les dimensions du fichier `public/partenaires/reunion.jpg` : elles donnent
 *  le RATIO, qui réserve la place de l'image avant son chargement. La taille,
 *  c'est la feuille qui la fixe. */
export const IMAGE_D_OUVERTURE = { largeur: 1500, hauteur: 1001 };

/** L'identifiant de la section des cartes : le bouton de l'ouverture y mène,
 *  et l'appel final aussi tant qu'aucune étude n'est chargée. */
export const ID_DES_CARTES = "nos-etudes";

/** Sous un prix : ce qu'il comprend. Écrit une fois pour la fourchette de
 *  l'ouverture et pour chaque carte. */
export const MENTION_DU_PRIX = "TTC · paiement unique";

export const OUVERTURE_ETUDES = {
  /** Mène aux cartes, plus bas dans la page. */
  bouton: { libelle: "Choisir mon étude", lien: `#${ID_DES_CARTES}` },
  nomDesPreuves: "EVKHA en chiffres",
};

// ── Le parcours : quatre documents, dans l'ordre ────────────────────────────

/** L'ordre du parcours : celui de `contenu.ETUDES`, écrit là-bas une seule
 *  fois. Marché, concurrence, business plan, stratégie. */
export const PARCOURS_DES_ETUDES = Object.keys(ETUDES);

/** Le libellé court de chaque étude dans la barre d'ancres. Une étude du
 *  catalogue qui n'en a pas y figure sous son libellé complet. */
export const LIBELLES_COURTS: Record<string, string> = {
  "etude-marche": "Marché",
  "etude-concurrence": "Concurrence",
  "business-plan": "Business plan",
  "strategie-business": "Stratégie",
};

/** Après chaque carte, la ligne qui nomme le document SUIVANT du parcours et
 *  ce qu'il apporte — stratégie commerciale de la cliente : chaque livraison
 *  ouvre la vente suivante. La clé est le slug de la carte ; `vers`, celui du
 *  document suivant, dont le NOM est lu dans le catalogue (jamais écrit ici).
 *  La dernière étape du parcours n'a pas de suite.
 *
 *  Aucune remise, aucun lot : la ligne dit seulement ce qui vient après. Si
 *  le document suivant n'est pas au catalogue, la ligne ne s'affiche pas —
 *  elle mènerait à une carte qui n'existe pas. */
export const SUITE_DU_PARCOURS: Record<string, { vers: string; benefice: string }> = {
  "etude-marche": {
    vers: "etude-concurrence",
    benefice: "pour savoir qui est déjà en place, et comment vous en différencier.",
  },
  "etude-concurrence": {
    vers: "business-plan",
    benefice: "pour présenter votre projet à votre banque, chiffres à l'appui.",
  },
  "business-plan": {
    vers: "strategie-business",
    benefice: "pour passer du dossier à l'action, avec des priorités claires.",
  },
};

export const CARTES = {
  /** Devant la ligne qui nomme le document suivant. */
  etiquetteDuParcours: "Ensuite dans le parcours",
  quoi: "Ce que vous obtenez :",
  /** Une offre du catalogue sans argumentaire dans `contenu.ETUDES` s'affiche
   *  quand même, sobrement : mieux vaut une carte courte qu'une étude
   *  invisible parce qu'un texte manque. */
  chapeauSobre: "Un document complet, en Word et en PDF",
  commanderSobre: (libelle: string) => `Commander ${libelle.toLowerCase()}`,
  /** Dite au-dessus des cartes, déjà affichées par leur argumentaire. */
  attente: "Les tarifs arrivent dans un instant.",
  /** Dite dans la région d'alerte du haut de page, suivie de l'adresse. */
  panne: "Le catalogue est momentanément indisponible.",
  panneSuite: "Écrivez-nous à",
  /** Dans la section des cartes, sous l'alerte : la panne n'est pas un vide. */
  rappel:
    "Le catalogue est momentanément indisponible : la page affichera les études et leurs tarifs dès son retour.",
  /** Le catalogue a répondu, et il ne porte aucune étude. */
  vide: "Aucune étude n'est en vente pour le moment.",
};

// ── Ruban ───────────────────────────────────────────────────────────────────

/** Bandeau défilant sous les cartes. Décoratif (masqué aux lecteurs d'écran) :
 *  il ne répète que ce que la page dit déjà en toutes lettres — dans la
 *  méthode, le comparatif et les questions. */
export const RUBAN_DES_ETUDES = [
  "Des chiffres sur votre marché",
  "Dans votre zone",
  "Un français clair, sans jargon",
  "PDF et Word",
  "À vos couleurs et avec votre logo",
  "Sous 24 heures ouvrées",
  "Relue avant envoi",
];

// ── Comparatif ──────────────────────────────────────────────────────────────

export const COMPARATIF = {
  evite: "Ce que vous évitez",
  recu: "Ce que vous recevez",
};

// ── Passerelle : les deux autres portes ─────────────────────────────────────

/** Avant l'appel final : la boutique d'études prêtes et les abonnements
 *  professionnels. SANS PRIX — chacune de ces pages lit les siens au serveur.
 *
 *  La carte des professionnels reprend, mot pour mot, la phrase que la page
 *  portait sous ses questions (`ETUDES_PAGE.liseret`). */
export const PASSERELLE = {
  surtitre: "Autrement",
  titre: { avant: "Un autre besoin,", fin: "une autre porte." },
  corps:
    "Une étude sur mesure n'est pas la seule façon de travailler avec EVKHA.",
  portes: [
    {
      surtitre: "Immédiat",
      titre: "Une étude prête à télécharger",
      corps:
        "Une étude déjà rédigée, sur un secteur : vous la téléchargez immédiatement depuis la boutique, sans questionnaire à remplir.",
      bouton: "Voir la boutique",
      lien: LIENS.boutique,
    },
    {
      surtitre: "Vous accompagnez",
      titre: "Les formules pour les professionnels",
      corps: `${ETUDES_PAGE.liseret.avant} ${ETUDES_PAGE.liseret.lien} ${ETUDES_PAGE.liseret.apres}`,
      bouton: "Voir les abonnements",
      lien: LIENS.partenaires,
    },
  ],
};
