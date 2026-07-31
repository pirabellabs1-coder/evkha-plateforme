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
