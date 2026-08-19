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

/** Toute la page `/etudes`, section par section, dans l'ordre de la maquette.
 *
 *  Reprise de `evkha.fr/etudedemarche`. Éditorial uniquement : aucun prix ici,
 *  ils viennent de la table `Offer` par `/api/public/livrables/`.
 */
export const ETUDES_PAGE = {
  hero: {
    titre: "Votre marché est-il rentable et viable ?",
    accroche: "Vous avez une idée d'entreprise.",
    corps: "Avant de vous lancer, de présenter votre dossier à la BGE, à Pôle Emploi ou à votre banque, obtenez une étude claire qui répond aux questions que vous vous posez vraiment :",
    questions: [
      "Marché saturé ou en croissance ?",
      "Y a-t-il assez de clients ?",
      "Quels risques ?",
      "Comment vous démarquer ?",
    ],
    image: "/partenaires/reunion.jpg",
    alt: "",
  },

  /** Bandeau noir. La fourchette de prix vaut `null` : elle est remplie À
   *  L'EXÉCUTION depuis le catalogue. Écrire « 89–195 € » ici serait faux dès
   *  le premier changement de tarif — sur la ligne même qui annonce les prix. */
  preuves: [
    { valeur: "500+", libelle: "porteurs accompagnés" },
    { valeur: "100 %", libelle: "de notes 5 étoiles" },
    { valeur: null, libelle: "par étude" },
  ],

  methode: {
    surtitre: "LES ÉTUDES EVKHA",
    titre: "Comment ça marche ?",
    sous: "SIMPLE ET RAPIDE",
    corps: [
      "Créer son entreprise, c'est parier sur un projet — mais un bon pari se prépare. Notre étude répond à toutes les questions, chiffres à l'appui, sur votre secteur et dans votre zone.",
      "Pas besoin d'être expert. Vous commandez en ligne, vous nous parlez de votre projet, vous recevez votre étude. À vos couleurs et avec votre logo. C'est tout.",
    ],
  },

  /** Quatre étapes numérotées. La numérotation encode une vraie séquence —
   *  choisir, payer, décrire, recevoir — et non une décoration. */
  etapes: [
    {
      titre: "Choisissez votre étude",
      corps: "Étude de marché, étude des concurrents, business plan ou stratégie — selon où vous en êtes de votre projet.",
    },
    {
      titre: "Réglez en ligne",
      corps: "Paiement sécurisé par carte. Vous recevez tout de suite la confirmation et la suite des opérations.",
    },
    {
      titre: "Parlez-nous de vous",
      corps: "Un questionnaire de 15 à 20 minutes : votre idée, votre zone, vos objectifs. Pas de jargon, pas de questions pièges.",
    },
    {
      titre: "Recevez votre étude",
      corps: "Votre étude complète arrive par e-mail, en PDF clair, prête à présenter — et facile à lire pour vous d'abord.",
    },
  ],

  choix: {
    surtitre: "QUATRE ÉTUDES AU CHOIX",
    titre: "Choisissez l'étude qui correspond à votre besoin",
    corps: "Chaque étude est rédigée pour vous. Avec des chiffres réels de votre marché, dans un français clair, accepté par les banques, la BGE, Pôle Emploi et tout organisme qui vous demande un dossier.",
  },

  cartes: { titre: "NOS ÉTUDES" },

  /** Les questions que se pose un porteur de projet, en deux colonnes. */
  interrogations: {
    titre: "EVKHA répond aux questions de TOUT porteur de projet",
    liste: [
      "Mon marché est-il saturé ou y a-t-il encore de la place pour moi ?",
      "Combien de clients potentiels dans ma zone géographique ?",
      "Mon marché est-il en croissance, stable ou en déclin ?",
      "Combien pèse mon marché en euros ? Combien puis-je espérer gagner ?",
      "Qui sont mes vrais concurrents et comment me démarquer d'eux ?",
      "Quels prix pratiquer pour rester compétitif et rentable ?",
      "Quels risques je prends en me lançant — et comment les éviter ?",
      "Mon dossier sera-t-il convaincant pour la banque ou la BGE ?",
    ],
    pied: "Une étude Evkha, c'est exactement ça : des réponses claires, vérifiées, écrites dans un français clair — pas du jargon de cabinet.",
  },

  liseret: {
    avant: "Vous êtes coach, consultant, agence ou BGE, et accompagnez plusieurs porteurs ?",
    lien: "Découvrez nos formules pro",
    apres: "avec abonnement mensuel.",
  },

  /** Section sombre : ce que l'étude n'est pas. */
  comparatif: {
    surtitre: "CE N'EST PAS UNE ÉTUDE GÉNÉRIQUE",
    titre: "L'étude trouvée sur Google ne sera pas la vôtre.",
    corps: "Une étude générique ou bidouillée avec ChatGPT, ça se voit. Et ça ne passe pas devant une banque ou la BGE. Voici la différence.",
    generique: {
      titre: "Étude générique ou faite à l'IA",
      points: [
        "Du texte joli mais aucun chiffre vérifié sur votre marché",
        "Du jargon que vous ne comprenez pas vous-même",
        "Aucun risque, aucun client type, aucune analyse réelle",
        "Rejetée par les banques et les organismes d'accompagnement",
        "Vous restez avec autant de doutes qu'avant",
      ],
    },
    evkha: {
      titre: "Une étude Evkha",
      points: [
        "De vrais chiffres sur votre marché, dans votre zone",
        "Un français clair, sans jargon : vous comprenez tout",
        "Risques, clients, concurrents, opportunités — tout y est",
        "Acceptée par les banques, la BGE, Pôle Emploi",
        "Vous repartez avec des réponses, pas des questions",
      ],
    },
    pied: "Chaque étude est relue avant envoi par Evangeline elle-même. Vous lisez une étude claire, faite pour vous — jamais un texte généré à la chaîne.",
  },

  faq: {
    surtitre: "VOS QUESTIONS",
    titre: "Ce qu'on nous demande le plus souvent",
    questions: [
      {
        q: "Je n'ai jamais fait d'étude de marché, est-ce que c'est fait pour moi ?",
        r: "Oui, c'est même fait pour ça. Vous n'avez pas besoin d'y connaître quoi que ce soit : vous répondez à un questionnaire sur votre projet, en français simple, et nous faisons le travail. Vous recevez l'étude, claire, à lire comme vous lisez un article.",
      },
      {
        q: "Quand est-ce que je vais recevoir mon étude ?",
        r: "Sous 24 heures ouvrées après l'envoi de votre questionnaire de cadrage. Pas de mauvaise surprise, pas de délai qui s'étire.",
      },
      {
        q: "Mon étude sera-t-elle acceptée par la BGE, Pôle Emploi ou ma banque ?",
        r: "Oui. Plus de 500 porteurs sont passés par nous et ont monté leur dossier avec nos études — auprès de la BGE, des CCI, des banques, de Pôle Emploi pour l'ARCE, de chambres des métiers. Tout y est : taille du marché, chiffres vérifiés, risques, clients, concurrents, prévisions. C'est exactement ce qu'on vous demande.",
      },
      {
        q: "Et si mon idée est très spécifique, ou que je suis dans un petit village ?",
        r: "Aucun souci. Nous travaillons sur tous les secteurs — artisanat, services, commerce, restauration, tech — et sur toutes les zones, des grandes villes jusqu'aux villages. L'étude est faite pour vous, pas reprise d'un modèle.",
      },
      {
        q: "Sous quelle forme je reçois mon étude ?",
        r: "Un PDF propre, prêt à imprimer ou à envoyer à votre conseiller, avec vos couleurs et votre logo. Et une version Word éditable, au cas où vous voudriez la personnaliser.",
      },
      {
        q: "Mes informations restent-elles confidentielles ?",
        r: "Totalement. Ce que vous nous dites sur votre projet ne sert qu'à produire votre étude. Aucune diffusion, aucun partage. Votre étude porte d'ailleurs une mention de confidentialité.",
      },
      {
        q: "Et si après lecture j'ai des questions ?",
        r: "Écrivez-nous à contact@evkha.fr. Nous répondons à toutes les questions de compréhension sur votre étude, pour que vous puissiez la défendre devant qui vous voulez.",
      },
      {
        q: "Puis-je commander plusieurs études ?",
        r: "Bien sûr. Beaucoup de porteurs commencent par l'étude de marché, puis ajoutent le business plan quand ils vont voir leur banquier. Certains finissent par la stratégie business, pour passer à l'action et se développer.",
      },
    ],
  },

  appel: {
    titre: "Votre projet mérite des réponses claires.",
    sous: "Lancez-vous dès maintenant !",
    bouton: "Commander mon étude",
  },
};
