/** Le texte de la page partenaires.
 *
 * Repris de `evkha.fr/partenairespro` (systeme.io) au 31/07/2026. Il vit ici
 * et non en base : ce sont des arguments de vente, pas des données. Les
 * CHIFFRES, eux, viennent tous de l'API — un prix recopié dans ce fichier
 * finirait par contredire la base (règle 5).
 */

export const HERO = {
  /** Trois lignes, coupées comme sur la maquette. Laisser le navigateur
   *  décider produirait un retour à la ligne différent à chaque largeur, et
   *  le titre perdrait son équilibre. */
  titre: [
    "Vous avez besoin d'Études,",
    "de Benchmarking et de",
    "Stratégies Business ?",
  ],
  accroche: "EVKHA LES PRODUIT POUR VOUS.",
  corps: [
    "Études de marché, analyses concurrentielles, business plans et stratégies de haut niveau, générés par la méthode Evkha, livrés en un temps record avec VOTRE LOGO et VOS COULEURS.",
    "Vous restez l'interlocuteur de votre client. Vous générez ce dont vous avez besoin, quand vous en avez besoin.",
  ],
  signature: "Le système EVKHA travaille pour vous.",
};

export const PREUVES = [
  { valeur: "250+", libelle: "dossiers livrés" },
  { valeur: "100 %", libelle: "de notes 5 étoiles" },
  { valeur: "0 €", libelle: "de droit d'entrée" },
];

export const PRINCIPE = {
  surtitre: "LE PRINCIPE",
  titre: "Un abonnement, des crédits, des livrables",
  etapes: [
    {
      titre: "Choisissez votre formule",
      corps: "Quatre niveaux d'abonnement mensuel selon votre volume, de 2 à 10 crédits inclus par mois.",
    },
    {
      titre: "Cadrez la commande",
      corps: "Pour chaque dossier, un formulaire de cadrage rapide — le projet de votre client, sa zone, sa cible.",
    },
    {
      titre: "Evkha produit",
      corps: "La méthode génère le livrable selon la méthode 22 chapitres. Chaque dossier est contrôlé avant envoi.",
    },
    {
      titre: "Vous livrez à votre client",
      corps: "Réception rapide sous 24 h : PDF final + version éditable. Vous restez l'expert aux yeux de votre client.",
    },
  ],
  bandeau:
    "1 crédit = 1 livrable au choix — Étude de marché, étude de la concurrence, business plan ou stratégie business, et chaque nouveau livrable ajouté au catalogue.",
};

export const FORMULES_SOUS_TITRES: Record<string, string> = {
  solo: "COACH · FREELANCE",
  pro: "AGENCE · CABINET",
  "pro-plus": "AGENCE AVEC VOLUME",
  structure: "INCUBATEUR · ASSO · RÉSEAU",
};

export const POUR_QUI = {
  titre: "Pour QUI ?",
  cibles: [
    {
      titre: "Coachs & accompagnants indépendants",
      corps: "Vous devez produire des études d'entreprise mais la production d'études vous coûte des journées entières — ou vous oblige à refuser des missions.",
      avec: "Avec Evkha : vous livrez des études complètes sous votre accompagnement, sans y passer vos soirées.",
    },
    {
      titre: "Agences, cabinets & experts-comptables",
      corps: "Vos clients ont besoin d'études de marché et de business plans que vous ne produisez pas en interne. Chaque mission ponctuelle vous fait perdre un client qui repart.",
      avec: "Avec Evkha : un service homogène à proposer, une connaissance fine de chaque client dès la première réunion.",
    },
    {
      titre: "Structures d'accompagnement",
      corps: "CCI, BGE, incubateurs, pépinières, organismes de formation : des cohortes entières de porteurs qui ont tous besoin de fondations solides et financières.",
      avec: "Avec Evkha : un volume garanti de dossiers professionnels, à coût maîtrisé, pour chaque promotion.",
    },
  ],
};

export const CALCUL = {
  surtitre: "CE QUE ÇA CHANGE",
  titre: "Le calcul est simple",
  colonnes: [
    {
      /** Rempli à l'exécution depuis les formules : le minimum et le maximum
       *  du coût par livrable. Écrit en dur, ce couple deviendrait faux au
       *  premier changement de tarif. */
      valeur: null,
      titre: "Votre coût par livrable",
      corps: "Un cabinet facture jusqu'à 800 € par livrable, en vendant votre journée de travail. Le même travail, sous votre marque, à ce coût-là.",
    },
    {
      valeur: "< 20 min",
      titre: "De votre temps par dossier",
      corps: "Le cadrage prend moins de vingt minutes. Le reste est produit, contrôlé, et vous revient prêt à livrer.",
    },
    {
      valeur: "+4 livrables",
      titre: "Un catalogue qui s'élargit",
      corps: "Modèle représentatif, prévisionnel financier et étude stratégique : le catalogue s'enrichit sans changement de formule. Chaque ajout augmente la valeur de votre abonnement.",
    },
  ],
  liseré:
    "Vous êtes un particulier, un porteur de projet ? Découvrez nos ÉTUDES et autres livrables À L'UNITÉ.",
};

export const FONDATRICE = {
  surtitre: "LA MÉTHODE, LA FONDATRICE",
  titre: "Une méthode née de 15 ans d'accompagnement",
  corps: "Je suis Evangeline Khaili, fondatrice d'Evkha. La méthode en 22 chapitres condense quinze années d'accompagnement de créateurs d'entreprise et plus de 250 dossiers livrés. Chaque livrable produit pour vos clients est contrôlé avant envoi : vous vous appuyez sur une méthode déposée et une exigence de qualité constante — pas sur une IA générique.",
};

export const FAQ = {
  surtitre: "VOS QUESTIONS",
  titre: "Ce qu'on nous demande le plus souvent",
  questions: [
    {
      q: "Comment fonctionnent les crédits ?",
      r: "Chaque mois, votre abonnement vous donne un nombre de crédits. 1 crédit = 1 livrable au choix dans le catalogue. Au-delà, les crédits supplémentaires sont facturés au tarif dégressif de votre formule.",
    },
    {
      q: "Qui signe les livrables ?",
      r: "Les livrables sont produits par Evkha mais s'y apposera votre logo et charte graphique. Votre client voit un document de cabinet, jamais la mécanique. Vous restez son interlocuteur et l'expert qui pilote son accompagnement.",
    },
    {
      q: "Quel est l'engagement ?",
      r: "3 mois minimum, sans droit d'entrée. Au-delà, l'abonnement est résiliable à tout moment, effectif à la fin du mois en cours. Les crédits ne sont pas cumulables.",
    },
    {
      q: "Puis-je changer de formule ?",
      r: "Oui, à la hausse comme à la baisse, à chaque échéance mensuelle. La plupart des partenaires démarrent en Solo ou Pro puis montent en volume.",
    },
    {
      q: "Sous quelle forme je reçois mon étude ?",
      r: "Un PDF propre, prêt à imprimer ou à envoyer par email à votre conseiller, avec vos couleurs et votre logo. Et vous recevez aussi une version éditable au cas où vous voudriez la personnaliser un peu (Word).",
    },
    {
      q: "Mes données et celles de mes clients sont-elles protégées ?",
      r: "Oui. Les informations transmises servent uniquement à produire le dossier, sont traitées de façon confidentielle puis purgées de nos systèmes. La méthode est hébergée et opérée exclusivement par Evkha.",
    },
    {
      q: "Et si après lecture j'ai des questions ?",
      r: "Vous pouvez nous écrire à contact@evkha.fr. On répond à toutes les questions de compréhension sur votre étude, pour que vous puissiez la défendre devant qui vous voulez.",
    },
    {
      q: "Comment se passe une commande concrètement ?",
      r: "Vous remplissez un formulaire de cadrage sur votre projet ou le projet de votre client (15 minutes maxi, ou directement avec lui). Le livrable est généré, contrôlé, puis vous est envoyé par email — réception rapide sous 24 h : PDF final + version éditable.",
    },
  ],
};

export const APPEL_FINAL = {
  surtitre: "LA MÉTHODE EVKHA AU SERVICE DE VOS CLIENTS",
  titre: "Offrez à chacun de vos clients la profondeur d'analyse d'un cabinet.",
  corps: [
    "Une méthode déposée, des sources vérifiées, une analyse contrôlée dossier par dossier.",
    "Des questions avant de souscrire ? Écrivez-nous, ou demandez un modèle d'étude pour juger sur pièce.",
  ],
};

export const CONTACT_EMAIL = "contact@evkha.fr";

/** Le menu du site vitrine, reproduit sur nos pages publiques.
 *
 * Cette page a remplacé `evkha.fr/partenairespro` dans le tunnel de vente. Le
 * visiteur qui cliquait arrivait chez nous — et le menu disparaissait, puisque
 * c'est un autre site. Constaté par la cliente le 07/08/2026 : « on ne voit
 * plus le menu du tunnel de vente ».
 *
 * **C'est une duplication, et elle est assumée.** Elle contredit la règle 5 —
 * une seule source par vérité — mais l'alternative était de laisser le visiteur
 * sans issue au milieu d'un parcours d'achat. On paie donc un entretien : si
 * une entrée change sur Systeme.io, elle doit changer ICI, et nulle part
 * ailleurs. C'est le seul endroit du dépôt où ce menu est écrit.
 *
 * Relevé sur `https://www.evkha.fr/` le 07/08/2026, structure et ordre compris.
 *
 * Une différence assumée avec l'original : le site écrit « Boite à outils »
 * sans accent circonflexe. On écrit « Boîte » — recopier une faute pour
 * ressembler à la source la ferait exister à deux endroits au lieu d'un.
 */
export type EntreeMenu = {
  libelle: string;
  lien: string;
  /** Plus de drapeau `courant` écrit à la main : deux pages publiques
   *  partagent ce menu, et un drapeau figé annoncerait « vous êtes ici » sur
   *  la mauvaise. `MenuSite` le DÉDUIT de l'adresse courante. */
  /** Bouton d'appel, à droite et détaché du reste. */
  appel?: boolean;
  /** Sous-entrées d'un menu déroulant. */
  enfants?: { libelle: string; lien: string }[];
};

export const MENU_SITE: EntreeMenu[] = [
  { libelle: "Accueil", lien: "https://www.evkha.fr/" },
  {
    libelle: "Etude de marché & Livrables",
    lien: "/etudes",
    enfants: [
      // Cette page-ci a remplacé `evkha.fr/etudedemarche` dans le tunnel : le
      // lien est donc interne, comme celui des partenaires. Les études prêtes
      // à télécharger restent sur le site vitrine, elles ne passent pas par
      // la plateforme.
      { libelle: "Générer votre étude ou livrable", lien: "/etudes" },
      {
        libelle: "Études en téléchargement immédiat",
        lien: "https://www.evkha.fr/etude-achat-immediat",
      },
    ],
  },
  { libelle: "Nos packs accompagnement", lien: "https://www.evkha.fr/packs" },
  { libelle: "Partenariats PRO et abonnements", lien: "/partenaires" },
  { libelle: "Nos Formations", lien: "https://www.evkha.fr/formation" },
  { libelle: "Boîte à outils", lien: "https://www.evkha.fr/boite-a-outil" },
  {
    libelle: "Me contacter",
    lien: "https://www.evkha.fr/contacts",
    appel: true,
  },
];

export const LOGO_SITE = "/partenaires/logo-evkha.png";

// ── Nos études : la page des livrables à l'unité ────────────────────────────

/** Argumentaire de chaque étude vendue seule, repris de `evkha.fr/etudedemarche`.
 *
 *  **Éditorial uniquement.** Le libellé, le PRIX et le NOMBRE DE CHAPITRES
 *  viennent du serveur (`/api/public/livrables/`) : les recopier ici ferait de
 *  cette page une seconde vérité, qui contredirait le paiement le jour d'un
 *  changement de tarif ou d'un chapitre ajouté au plan (règle 5). C'est
 *  exactement le partage retenu pour la page partenaires.
 *
 *  La clé est le SLUG de l'offre en base — le même que dans l'adresse
 *  (`/inscription?livrable=etude-marche`). Une offre sans entrée ici s'affiche
 *  quand même, avec son prix : mieux vaut une carte sobre qu'une offre
 *  invisible parce qu'un texte manque.
 */
export type ArgumentaireEtude = {
  /** Le bénéfice, en capitales au-dessus du titre. */
  surtitre: string;
  /** Nombre de chapitres ANNONCÉ, tel qu'il figure sur `evkha.fr`.
   *
   *  Ce n'est PAS le nombre d'entrées du plan de production, et l'écart est
   *  voulu : le plan porte 23 entrées pour l'étude de marché quand la page en
   *  annonce 22, parce que la fiche projet d'ouverture et l'annexe ne sont pas
   *  vendues comme des chapitres. Deux vérités distinctes — ce qu'on produit,
   *  ce qu'on annonce — et lire la première ici réécrirait l'argumentaire
   *  commercial sans que personne l'ait décidé. */
  chapitres: number;
  /** Première puce, en gras : ce que contient le livrable. */
  chapeau: string;
  /** Les puces secondaires, en retrait. */
  details: string[];
  /** Paragraphe de clôture, sous les puces. */
  pied: string;
  /** Libellé du bouton. « Commander mon business plan » n'est pas
   *  « Commander mon étude » — le mot compte sur un bouton d'achat. */
  bouton: string;
};

export const ETUDES: Record<string, ArgumentaireEtude> = {
  "etude-marche": {
    chapitres: 22,
    surtitre: "POUR VALIDER VOTRE IDÉE",
    chapeau: "chapitres clairs et structurés comprenant :",
    details: [
      "Votre marché est-il vraiment porteur ? On vous le dit, chiffres en main.",
      "La taille de votre marché, en euros et en clients potentiels",
      "S'il est en croissance, stable ou en déclin (avec les chiffres)",
      "Vos clients types : qui ils sont, ce qu'ils veulent, combien ils dépensent",
      "Les risques de votre projet et comment les anticiper",
      "Une étude prête à présenter à la banque, la BGE, Pôle Emploi",
    ],
    pied: "Vous répondrez enfin aux questions : est-ce un marché saturé ? Viable ? Rentable ? Prometteur ?",
    bouton: "Commander mon étude",
  },
  "etude-concurrence": {
    chapitres: 9,
    surtitre: "POUR CONNAÎTRE VOS CONCURRENTS",
    chapeau: "chapitres clairs et structurés comprenant :",
    details: [
      "Qui sont-ils, ce qu'ils font, comment vous différencier d'eux",
      "8 concurrents directs + 3 concurrents indirects analysés un par un",
      "Leurs prix, leurs services, leurs points forts et leurs faiblesses",
      "Une carte claire pour vous positionner sur le marché",
      "Vos angles de différenciation pour vous rendre incontournable",
    ],
    pied: "Chaque projet est unique, votre étude aussi. Après votre commande, vous répondez à un questionnaire rapide et la production démarre.",
    bouton: "Commander mon étude",
  },
  "business-plan": {
    chapitres: 21,
    surtitre: "POUR CONVAINCRE VOTRE BANQUE",
    chapeau: "chapitres, présentés comme une banque aime les lire :",
    details: [
      "Votre projet expliqué simplement, du début à la fin",
      "Construit selon les attentes des banques et des financeurs, avec graphiques et matrices",
      "Marché, clients, prix, plan d'action, prévisions financières",
      "Rédigé dans un français clair — comme si vous l'aviez écrit vous-même",
    ],
    pied: "Le dossier que vous posez sur la table, sans avoir à l'expliquer avant qu'on le lise.",
    bouton: "Commander mon business plan",
  },
  "strategie-business": {
    chapitres: 20,
    surtitre: "POUR PASSER À L'ACTION",
    chapeau: "chapitres pour structurer votre business :",
    details: [
      "Un rapport stratégique complet en 4 piliers, personnalisé et orienté résultats",
      "Adapté à vos contraintes et à votre vision",
      "Sortir de la confusion, clarifier votre direction, affirmer ce qui vous rend unique",
      "Un plan pour structurer votre visibilité et parler à votre cible, sans vous éparpiller",
      "Des recommandations concrètes, activables sans connaissance technique",
    ],
    pied: "Stop au flou : une stratégie claire et rentable, que vous pouvez appliquer dès la semaine suivante.",
    bouton: "Commander ma stratégie",
  },
};

export const ETUDES_PAGE = {
  surtitre: "NOS ÉTUDES",
  titre: "EVKHA répond aux questions de TOUT porteur de projet",
  chapeau:
    "Des livrables complets, produits sur votre projet et livrés en Word et en PDF. Payés une fois, sans abonnement.",
  /** Sous les cartes : ce qui se passe après le paiement.
   *  Une séquence réelle — payer, entrer, décrire, recevoir —, d'où la
   *  numérotation : l'ordre porte l'information. */
  etapes: [
    "Vous choisissez votre étude et vous la payez.",
    "Votre espace s'ouvre : vous y répondez au questionnaire de votre projet.",
    "La production démarre et vous la suivez étape par étape.",
    "Vous téléchargez votre document, en Word et en PDF.",
  ],
  appel: {
    titre: "Vous accompagnez plusieurs porteurs de projet ?",
    corps: "Les formules partenaires donnent des crédits chaque mois, sous votre marque, à un coût par livrable bien inférieur.",
    lien: "Voir les formules partenaires",
  },
};
