/** Le texte de quatre pages reprises du site actuel de la cliente
 *  (`www.evkha.fr`, Systeme.io) : la boîte à outils, l'article « Ai-je une idée
 *  de business viable ? » (premier article du futur blog), la page de contact
 *  et la page du partenaire SWAPN.
 *
 *  D'OÙ VIENT LE CONTENU. Du relevé `docs/refonte/inventaire-site-evkha.md`,
 *  sections 8 (`/boite-a-outil`), 38 (`/boite-a-outils/idee-business-viable`),
 *  9 (`/contacts`) et 39 (`/swapn`). Éditorial uniquement, comme
 *  `contenuAccueil.ts` : aucun code d'envoi, aucun prix. Le texte est REPRIS
 *  TEL QUEL, dans l'ordre de la page ; rien n'est résumé ni ajouté.
 *
 *  CE QUI A ÉTÉ RETOUCHÉ, et rien d'autre :
 *  - retirés : le menu, le pied de page (liens légaux, « © EVKHA. Tous droits
 *    réservés. ») et le logo répété en tête de chaque page ;
 *  - coquilles évidentes : « ontact page » → « Contact page » (titre de la
 *    page de contact) ; « premières semaines.. » → un seul point ;
 *    « Demandez-vous : : » → un seul deux-points ; « partagée » → « partagé »
 *    (mention de la lettre d'information, « votre email ») ;
 *  - espaces parasites avant une virgule, un point ou une parenthèse (« clés ,
 *    avec », « ( modèle freemium ) ») : ce sont les traces des mots en gras à
 *    l'extraction, elles sont resserrées ;
 *  - la phrase « Une idée viable… coche 3 cases : - … - … - … » est rendue en
 *    une phrase d'introduction et une liste de trois points, mots inchangés ;
 *  - le titre de l'article, relevé sur trois lignes, est rendu en un titre et
 *    un sous-titre.
 *  Aucune mention de « Pôle Emploi » ne figure sur ces quatre pages : il n'y
 *  avait rien à passer en « France Travail ».
 *
 *  LE TON. La boîte à outils tutoie, le reste de la plateforme vouvoie. Chaque
 *  bloc porte le texte d'origine dans `texte` ; quand il tutoie, il porte en
 *  plus `texteAuVous`, identique mot pour mot hormis le passage au vous. La
 *  page choisit. Un bloc sans `texteAuVous` ne tutoie pas.
 *
 *  CE QUE LE RELEVÉ NE CONTIENT PAS n'est pas inventé ici : c'est écrit `null`
 *  ou `[]`, avec un commentaire. Les seules suggestions du fichier sont dans
 *  des champs nommés `propose`, jamais mêlées au texte relevé.
 */
import { CONTACT_EMAIL } from "./contenu";
import { CHEMINS, LIENS, RESEAUX_SOCIAUX } from "./contenuSite";

// ── Types ───────────────────────────────────────────────────────────────────

/** Un texte de la page. `texteAuVous` n'existe que si `texte` tutoie. */
export type Texte = {
  texte: string;
  texteAuVous?: string;
};

/** Titre de l'onglet et méta-description. `null` : absent du site actuel.
 *  `propose` : une suggestion, à valider — jamais un texte relevé. */
export type Entete = {
  titreOnglet: Texte | null;
  description: Texte | null;
  propose?: { titreOnglet: string; description: string };
};

export type PageSource =
  | "boite-a-outils"
  | "article-idee-business-viable"
  | "contact"
  | "swapn"
  /** L'accueil : seule la lettre d'information en vient (voir FORMULAIRES). */
  | "accueil";

// ── Adresses ────────────────────────────────────────────────────────────────

const SITE = "https://www.evkha.fr";

/** L'adresse de destination de chaque bouton de ces pages, telle que relevée.
 *  Ce sont les adresses du site ACTUEL : la refonte les remplacera par ses
 *  propres routes (et prévoira une redirection 301 depuis chacune). */
export const LIENS_RESSOURCES = {
  /** Les quatre pages d'origine. */
  pages: {
    boiteAOutils: `${SITE}/boite-a-outil`,
    article: `${SITE}/boite-a-outils/idee-business-viable`,
    contact: `${SITE}/contacts`,
    swapn: `${SITE}/swapn`,
  },
  boiteAOutils: {
    /** « Lire la suite de l'article ». Le relevé ne donne pas la destination
     *  de ce bouton ; c'est l'adresse de l'article, DÉDUITE. */
    lireLaSuite: `${SITE}/boite-a-outils/idee-business-viable`,
    /** « Je la veux » et « Je veux mon lexique » envoient un formulaire : pas
     *  d'adresse de destination relevée. */
    jeLaVeux: null,
    jeVeuxMonLexique: null,
  },
  article: {
    /** Fin de l'article : la checklist « Ai-je une idée de business
     *  viable ? » renvoie vers la boîte à outils. */
    bonus: `${SITE}/boite-a-outil`,
  },
  contact: {
    /** « Envoyer » envoie le formulaire : pas d'adresse relevée. */
    envoyer: null,
    courriel: `mailto:${CONTACT_EMAIL}`,
  },
  swapn: {
    /** « Envoyer » envoie le formulaire : pas d'adresse relevée. */
    envoyer: null,
  },
} as const;

// ── Images ──────────────────────────────────────────────────────────────────

export type ImageARapatrier = {
  page: PageSource;
  adresse: string;
  contexte: string;
};

const CDN = "https://d1yei2z3i6k35z.cloudfront.net";

/** Toutes les lignes `[IMAGE]` des quatre pages. Aucune n'a de texte
 *  alternatif sur le site actuel. Rien n'est téléchargé ici : la liste sert à
 *  les rapatrier, comme `IMAGES_ACCUEIL` l'a été. Le contenu des images n'a
 *  pas été regardé, sauf celui des deux visuels SWAPN (relevé du 19/11/2026) ;
 *  pour les autres, le contexte ne dit que leur place dans la page. */
export const IMAGES_RESSOURCES_A_RAPATRIER: ImageARapatrier[] = [
  {
    page: "boite-a-outils",
    adresse: `${CDN}/9890127/6844d0a794f08_ChatGPTImage8juin202501_48_06.png`,
    contexte: "Logo du menu (élément répété sur le site, déjà hors page).",
  },
  {
    page: "boite-a-outils",
    adresse: `${CDN}/9890127/6846defd62022_PinkandBlackPlayfulProfessionalTrainingVirtualInvitation6.png`,
    contexte:
      "Visuel d'ouverture, juste au-dessus de « Bienvenue dans votre espace ressources 100 % gratuit ».",
  },
  {
    page: "article-idee-business-viable",
    adresse: `${CDN}/9453866/670d706f007bf_LOGOEVKHABUSINESSETFORM.png`,
    contexte:
      "Logo du menu de l'article (ancien logo, autre menu que le reste du site).",
  },
  {
    page: "article-idee-business-viable",
    adresse: `${CDN}/9890127/689443222271c_FEEDINSTAGRAMEVKHA-5.png`,
    contexte:
      "Illustration de tête de l'article, au-dessus du titre « Ai-je une idée de business viable ? ».",
  },
  {
    page: "contact",
    adresse: `${CDN}/9890127/6844d0a794f08_ChatGPTImage8juin202501_48_06.png`,
    contexte: "Logo du menu (élément répété sur le site, déjà hors page).",
  },
  {
    page: "contact",
    adresse: `${CDN}/9890127/684acd132a11e_Bienvenue7.png`,
    contexte:
      "Visuel d'ouverture, juste au-dessus de « Posez-nous toutes vos questions ! ».",
  },
  {
    page: "contact",
    adresse: `${CDN}/9890127/6846e23bdd33a_PinkandBlackPlayfulProfessionalTrainingVirtualInvitation7.png`,
    contexte:
      "Visuel placé entre l'accroche et le formulaire (« Un besoin d'informations? »).",
  },
  {
    page: "swapn",
    adresse: `${CDN}/9890127/6844d0a794f08_ChatGPTImage8juin202501_48_06.png`,
    contexte: "Logo du menu (élément répété sur le site, déjà hors page).",
  },
  {
    page: "swapn",
    adresse: `${CDN}/9890127/68f604cfebdd7_SWPAN2.png`,
    contexte:
      "Premier visuel SWAPN (1500×739), sous le titre « MISE EN RELATION GRATUITE AVEC MON PARTENAIRE SWAPN ! ». L'offre de SWAPN est écrite DANS cette image : son texte, relevé le 19/11/2026, est dans SWAPN.texteLuDansLeVisuel.",
  },
  {
    page: "swapn",
    adresse: `${CDN}/9890127/68f603ab0d9dd_SWAPN.png`,
    contexte:
      "Second visuel SWAPN (290×120), juste au-dessus du bouton « Envoyer » : le logo Swapn. Pas de texte à transcrire.",
  },
];

// ── Coordonnées ─────────────────────────────────────────────────────────────

/** Ce que le site dit pour joindre EVKHA, exactement comme relevé.
 *
 *  Les quatre pages de ce lot ne donnent NI horaires, NI téléphone, NI adresse
 *  postale, NI réseaux sociaux : la page de contact ne porte qu'un formulaire
 *  et un délai de réponse. Ces champs sont donc `null` — les remplir serait
 *  inventer. Les réseaux sont ceux relevés sur l'ACCUEIL du site (ligne
 *  « Liens externes » de la section 1 de l'inventaire), donnés ici parce
 *  qu'une page de contact les attend ; leur provenance est dite. */
export const COORDONNEES = {
  /** Relevé sur le menu de l'article (« Contacts → contact@evkha.fr »). La
   *  valeur est lue dans `contenu.ts` : une seule écriture de l'adresse. */
  courriel: CONTACT_EMAIL,
  delaiDeReponse: {
    /** Sur la page de contact, au-dessus du formulaire. */
    surLaPage: "Nous vous répondons sous 48 heures maximum.",
    /** Dans la méta-description de la page de contact. */
    dansLaDescription: "Réponse garantie sous 48h.",
  },
  /** Non relevés sur le site. */
  horaires: null,
  /** Non relevé sur le site. */
  telephone: null,
  /** Non relevée sur ces pages (elle figure dans les mentions légales, hors
   *  de ce lot). */
  adressePostale: null,
  /** Prise de rendez-vous, relevée sur l'accueil. L'adresse est LUE dans
   *  `contenuSite.LIENS.appel` : le menu, le pied et cette page mènent au même
   *  agenda, écrit une fois (règle 5). */
  rendezVous: LIENS.appel,
  /** Relevés sur l'accueil, pas sur ces pages. Le plan de refonte cite aussi
   *  TikTok, sans adresse relevée : il n'est pas listé. La liste est LUE dans
   *  `contenuSite.RESEAUX_SOCIAUX`, que le pied affiche aussi. */
  reseaux: RESEAUX_SOCIAUX,
} as const;

// ── Formulaires ─────────────────────────────────────────────────────────────

/** Un champ de formulaire. `libelle` et `type` sont relevés (ou suggérés, dans
 *  `propose`) ; `nom` est un identifiant choisi ICI pour le futur code, jamais
 *  un texte du site. `obligatoire` vaut `null` quand le relevé ne dit pas si
 *  le champ est marqué obligatoire. */
export type ChampDeFormulaire = {
  nom: string;
  libelle: string;
  type: "text" | "email" | "textarea";
  obligatoire: boolean | null;
};

export type Formulaire = {
  page: PageSource;
  /** Le titre affiché au-dessus du formulaire, sur une ou deux lignes. */
  titre: Texte[];
  /** Les champs RELEVÉS sur le site. Vide : aucun libellé de champ n'a été
   *  relevé pour ce formulaire. Ceux du contact et de SWAPN l'ont été le
   *  19/11/2026. */
  champs: ChampDeFormulaire[];
  /** La case à cocher, mot pour mot. `null` : aucune case relevée. */
  consentement: Texte | null;
  bouton: string;
  /** La mention sous le bouton. `null` : aucune mention relevée. */
  mention: string | null;
  /** Ce que le formulaire est censé déclencher côté serveur. Une description,
   *  pas un contrat : rien n'est branché. */
  declenche: string;
  /** Les champs à prévoir, SUGGÉRÉS — à valider, jamais relevés. Vide quand
   *  les vrais champs sont dans `champs` : il n'y a alors rien à suggérer. */
  propose: { champs: ChampDeFormulaire[]; remarque: string };
};

const CHAMP_COURRIEL: ChampDeFormulaire = {
  nom: "email",
  libelle: "Adresse e-mail",
  type: "email",
  obligatoire: true,
};

/** Les cinq formulaires liés à ces pages. Aucun code d'envoi n'est écrit :
 *  un formulaire affiché sans service derrière est interdit sur la plateforme
 *  (voir `contenuAccueil.FIN`), la page ne les rendra donc qu'une fois le
 *  point d'entrée serveur en place. */
export const FORMULAIRES: Record<
  "checklist" | "lexique" | "contact" | "swapn" | "lettreDInformation",
  Formulaire
> = {
  /** Boîte à outils, premier formulaire. */
  checklist: {
    page: "boite-a-outils",
    titre: [
      { texte: "Ma checklist PDF" },
      { texte: "“Créer sa micro-entreprise en 10 étapes”" },
    ],
    champs: [],
    consentement: {
      texte: "Oui, je souhaite recevoir les nouveautés et informations EVKHA",
    },
    bouton: "Je la veux",
    mention: "Votre email ne sera jamais partagé",
    declenche:
      "Envoyer par e-mail, à l'adresse saisie, la checklist PDF « Créer sa micro-entreprise en 10 étapes ». Si la case est cochée, inscrire l'adresse aux nouveautés et informations EVKHA. Le fichier PDF lui-même n'est pas dans le relevé : il est à récupérer auprès de la cliente.",
    propose: {
      champs: [CHAMP_COURRIEL],
      remarque:
        "La page annonce un envoi contre une adresse e-mail : un seul champ suffit. La case doit rester décochée par défaut et ne pas conditionner l'envoi du document.",
    },
  },
  /** Boîte à outils, second formulaire. */
  lexique: {
    page: "boite-a-outils",
    titre: [
      {
        texte: "Télécharge ton lexique des termes entrepreneuriaux",
        texteAuVous: "Téléchargez votre lexique des termes entrepreneuriaux",
      },
    ],
    champs: [],
    consentement: {
      texte: "Oui, j'accepte d'être informé(e) sur les nouveautés EVKHA",
    },
    bouton: "Je veux mon lexique",
    mention: "Votre email ne sera jamais partagé",
    declenche:
      "Envoyer par e-mail, à l'adresse saisie, le lexique EVKHA des termes de l'entrepreneuriat (PDF). Si la case est cochée, inscrire l'adresse aux nouveautés EVKHA. Le fichier PDF n'est pas dans le relevé : il est à récupérer auprès de la cliente.",
    propose: {
      champs: [CHAMP_COURRIEL],
      remarque:
        "Même forme que la checklist. Les deux cases de consentement n'ont pas le même libellé sur le site : elles sont gardées telles quelles, à harmoniser si la cliente le souhaite.",
    },
  },
  /** Page de contact. */
  contact: {
    page: "contact",
    titre: [
      { texte: "Un besoin d'informations?" },
      { texte: "Nous vous répondons sous 48 heures maximum." },
    ],
    /** Relevés sur `/contacts` le 19/11/2026, dans l'ordre. Aucun n'est
     *  marqué obligatoire sur le site. */
    champs: [
      { nom: "nom", libelle: "Nom", type: "text", obligatoire: false },
      { nom: "email", libelle: "Adresse email", type: "email", obligatoire: false },
      { nom: "sujet", libelle: "Sujet", type: "text", obligatoire: false },
      { nom: "message", libelle: "Message", type: "textarea", obligatoire: false },
    ],
    consentement: null,
    bouton: "Envoyer",
    mention: null,
    declenche:
      "Transmettre le message à EVKHA (boîte de contact), avec de quoi répondre à l'expéditeur. La page promet une réponse sous 48 heures maximum.",
    propose: {
      champs: [],
      remarque:
        "Les quatre champs sont ceux du site. Aucun n'y est marqué obligatoire : or, sans adresse e-mail ni message, la promesse de réponse sous 48 heures ne peut pas être tenue. À décider avec la cliente : rendre au moins ces deux champs obligatoires, et le vérifier côté serveur.",
    },
  },
  /** Page SWAPN. */
  swapn: {
    page: "swapn",
    titre: [
      { texte: "MISE EN RELATION GRATUITE" },
      { texte: "AVEC MON PARTENAIRE SWAPN !" },
    ],
    /** Relevés sur `/swapn` le 19/11/2026, dans l'ordre. Le relevé ne dit pas
     *  si ces champs sont marqués obligatoires : `null`.
     *
     *  Les deux derniers sont « pré-libellés » : leur libellé est une PHRASE
     *  en capitales, pas un nom de champ. La seconde lit comme une
     *  information donnée au visiteur plus que comme une invitation à
     *  écrire ; le relevé ne dit pas si ce texte est un libellé, un texte
     *  indicatif ou une valeur déjà saisie. Mot pour mot, « RECEPTION » sans
     *  accent et « GRATUITEMENT! » sans espace compris. */
    champs: [
      { nom: "nom", libelle: "Nom", type: "text", obligatoire: null },
      { nom: "email", libelle: "Adresse email", type: "email", obligatoire: null },
      {
        nom: "demande",
        libelle: "JE SOUHAITE CONTACTER VOTRE CONSEILLER SWAPN",
        type: "text",
        obligatoire: null,
      },
      {
        nom: "message",
        libelle:
          "SWAPN VOUS CONTACTERA DÈS RECEPTION DE VOTRE NOM ET MAIL, SANS ENGAGEMENT ET GRATUITEMENT!",
        type: "textarea",
        obligatoire: null,
      },
    ],
    consentement: null,
    bouton: "Envoyer",
    mention: null,
    declenche:
      "Enregistrer une demande de mise en relation gratuite avec le partenaire SWAPN, et la porter à la connaissance d'EVKHA. Le relevé ne dit pas si la demande part chez EVKHA, chez SWAPN ou chez les deux : à faire préciser.",
    propose: {
      champs: [],
      remarque:
        "Les quatre champs sont ceux du site. Le formulaire annonce que SWAPN contactera le visiteur dès qu'il aura reçu son nom et son adresse : transmettre des coordonnées à un tiers demande une mention d'information et un accord explicites, que le site ne porte pas (aucune case relevée).",
    },
  },
  /** Lettre d'information « Business Tips ». Elle n'apparaît sur AUCUNE des
   *  quatre pages de ce lot : elle est relevée en bas de l'accueil (section 1
   *  de l'inventaire). Décrite ici parce que la boîte à outils et le blog sont
   *  ses emplacements naturels. */
  lettreDInformation: {
    page: "accueil",
    titre: [
      {
        texte:
          "INSCRIVEZ-VOUS GRATUITEMENT À LA NEWSLETTER \"BUSINESS TIPS\"",
      },
    ],
    champs: [],
    consentement: null,
    bouton: "JE M'ABONNE",
    mention: "Je HAIS le spam. Votre email ne sera jamais partagé",
    declenche:
      "Inscrire l'adresse saisie à la lettre d'information « Business Tips ». Aucun service ne reçoit d'inscription sur la plateforme aujourd'hui.",
    propose: {
      champs: [CHAMP_COURRIEL],
      remarque:
        "Prévoir une confirmation de l'inscription par e-mail et un lien de désinscription dans chaque envoi.",
    },
  },
};

// ── 1. La boîte à outils (`/boite-a-outil`) ─────────────────────────────────

export type Ressource = {
  /** Ce que la ressource est : deux documents envoyés par e-mail, un article. */
  nature: "document" | "article";
  /** Sur-titre de la carte, quand la page en porte un. */
  surtitre?: Texte;
  titre: Texte;
  paragraphes: Texte[];
  /** Le formulaire qui délivre le document (clé de `FORMULAIRES`). */
  formulaire?: "checklist" | "lexique";
  /** Le bouton de la carte, pour l'article. */
  bouton?: { libelle: string; lien: string };
};

export const BOITE_A_OUTILS = {
  entete: {
    titreOnglet: {
      texte:
        "Boîte à outils pour entrepreneurs : modèles, ressources, templates – EVKHA",
    },
    description: {
      texte:
        "Des outils concrets pour booster ton business : modèles de documents, tableaux Excel, templates prêts à l’emploi pour entrepreneurs pressés et motivés.",
      texteAuVous:
        "Des outils concrets pour booster votre business : modèles de documents, tableaux Excel, templates prêts à l’emploi pour entrepreneurs pressés et motivés.",
    },
  } as Entete,

  /** Bloc 1 — l'ouverture. Elle vouvoie déjà. */
  ouverture: {
    titre: "Bienvenue dans votre espace ressources 100 % gratuit",
    corps:
      "Dédié à la création et au développement d’entreprise. Vous y trouverez des documents à télécharger, des articles pratiques et une sélection de liens utiles pour vous accompagner à chaque étape de votre projet.",
  },

  /** Bloc 2 — ce que la page contient. */
  decouvrir: {
    titre: "Ce que vous allez découvrir :",
    points: [
      "Documents pratiques : modèles, guides PDF, fiches à imprimer",
      "Articles & conseils : infos concrètes pour bien entreprendre",
      "Ressources utiles : outils en ligne, partenaires, services officiels",
    ],
    suite:
      "Cette page évoluera régulièrement, alors revenez souvent découvrir les nouvelles ressources ajoutées !",
  },

  /** Bloc 3 — le titre de la liste des ressources. */
  titreDesRessources: "Vos Ressources & Vos Outils",

  /** Blocs 4 à 6 — les trois ressources, dans l'ordre de la page. Sur le
   *  site, les deux formulaires viennent APRÈS les trois cartes ; ils sont
   *  rattachés ici à leur document par `formulaire`. */
  ressources: [
    {
      nature: "document",
      titre: {
        texte:
          "Checklist gratuite : les 10 étapes essentielles pour créer sa micro-entreprise",
      },
      paragraphes: [
        {
          texte:
            "Télécharge gratuitement la checklist EVKHA pour créer ta micro-entreprise pas à pas. 10 étapes simples, claires et motivantes pour te lancer sereinement.",
          texteAuVous:
            "Téléchargez gratuitement la checklist EVKHA pour créer votre micro-entreprise pas à pas. 10 étapes simples, claires et motivantes pour vous lancer sereinement.",
        },
        {
          texte:
            "Tu veux créer ta micro-entreprise mais tu ne sais pas par où commencer ? Cette checklist te guide en 10 étapes clés, avec des actions concrètes à cocher pour passer à l’action sans stress.",
          texteAuVous:
            "Vous voulez créer votre micro-entreprise mais vous ne savez pas par où commencer ? Cette checklist vous guide en 10 étapes clés, avec des actions concrètes à cocher pour passer à l’action sans stress.",
        },
        {
          texte:
            "Elle est issue de mon expérience auprès de centaines d’entrepreneur(e)s accompagné(e)s.",
        },
        {
          texte:
            "Tu y trouveras des conseils simples, des liens utiles, et même une étape zéro pour te reconnecter à ton “pourquoi”.",
          texteAuVous:
            "Vous y trouverez des conseils simples, des liens utiles, et même une étape zéro pour vous reconnecter à votre “pourquoi”.",
        },
        {
          texte:
            "Que tu sois en pleine reconversion ou que tu aies juste une idée en tête, cette ressource va t’aider à structurer ton lancement.",
          texteAuVous:
            "Que vous soyez en pleine reconversion ou que vous ayez juste une idée en tête, cette ressource va vous aider à structurer votre lancement.",
        },
        {
          texte: "Télécharge ta checklist gratuitement en PDF ci-dessous.",
          texteAuVous:
            "Téléchargez votre checklist gratuitement en PDF ci-dessous.",
        },
      ],
      formulaire: "checklist",
    },
    {
      nature: "document",
      titre: {
        texte:
          "Le lexique EVKHA pour enfin comprendre les mots de l’entrepreneuriat",
      },
      paragraphes: [
        {
          texte:
            "Découvre gratuitement le lexique EVKHA, un outil clair et accessible pour comprendre enfin tous les mots techniques qu’on utilise quand on parle de création d’entreprise.",
          texteAuVous:
            "Découvrez gratuitement le lexique EVKHA, un outil clair et accessible pour comprendre enfin tous les mots techniques qu’on utilise quand on parle de création d’entreprise.",
        },
        {
          texte:
            "Parce qu’on ne peut pas construire un projet solide quand on ne comprend pas ce qu’on signe.",
        },
        {
          // PASSAGE DOUTEUX : la phrase s'arrête sur une virgule dans le
          // relevé (« sans jargon , »). Elle est gardée telle quelle ; la fin
          // manque sur le site ou a été perdue à l'extraction.
          texte:
            "Ce lexique est là pour t’aider à comprendre facilement, sans jargon,",
          texteAuVous:
            "Ce lexique est là pour vous aider à comprendre facilement, sans jargon,",
        },
        {
          texte:
            "Tu y trouveras des définitions claires, des exemples concrets, et des conseils issus de mon expérience auprès de centaines d’entrepreneur(e)s accompagnés.",
          texteAuVous:
            "Vous y trouverez des définitions claires, des exemples concrets, et des conseils issus de mon expérience auprès de centaines d’entrepreneur(e)s accompagnés.",
        },
        {
          texte: "Télécharge ton lexique gratuitement en PDF ci-dessous.",
          texteAuVous:
            "Téléchargez votre lexique gratuitement en PDF ci-dessous.",
        },
      ],
      formulaire: "lexique",
    },
    {
      nature: "article",
      surtitre: {
        texte: "4 questions à se poser pour ne pas foncer dans le mur:",
      },
      titre: { texte: "Ai-je une idée de business viable ?" },
      paragraphes: [
        { texte: "Créer oui… mais pas n’importe quoi" },
        {
          texte:
            "Quand on a une idée de business, l’envie de foncer est souvent plus forte que la raison.",
        },
        { texte: "On se projette, on imagine le logo, le site, les clients…" },
        { texte: "Mais une question fondamentale reste souvent en suspens :" },
        { texte: "Est-ce que mon idée est vraiment viable ?" },
      ],
      bouton: {
        libelle: "Lire la suite de l'article",
        lien: LIENS_RESSOURCES.boiteAOutils.lireLaSuite,
      },
    },
  ] as Ressource[],
};

// ── 2. L'article (`/boite-a-outils/idee-business-viable`) ───────────────────

/** Un élément du corps d'une section, dans l'ordre de lecture.
 *
 *  - `paragraphe` : du texte courant ;
 *  - `liste` : des points, avec leur phrase d'introduction s'il y en a une ;
 *  - `question` : l'encadré « Demandez-vous : » et la ou les questions ;
 *  - `exemple` : l'encadré « Exemple : », un cas concret ;
 *  - `citation` : des paroles rapportées, avec le nom de qui les a dites —
 *    absent quand la source ne le dit pas : un auteur ne se suppose pas. Le
 *    texte s'écrit SANS guillemets : la page les pose (portraits du blog,
 *    20/11/2026) ;
 *  - `lien` : un lien qui SORT du site (le site de la personne présentée). Son
 *    libellé dit où il mène : il s'ouvre dans un nouvel onglet. */
export type ElementDArticle =
  | { genre: "paragraphe"; texte: string }
  | { genre: "liste"; introduction?: string; points: string[] }
  | { genre: "question"; amorce: string; texte: string }
  | { genre: "exemple"; amorce: string; texte: string }
  | { genre: "citation"; texte: string; auteur?: string }
  | { genre: "lien"; libelle: string; lien: string };

export type SousSection = {
  intertitre: string;
  elements: ElementDArticle[];
};

export type SectionDArticle = {
  intertitre: string;
  elements: ElementDArticle[];
  /** Les sous-parties numérotées (les quatre questions de la partie 2). */
  sousSections?: SousSection[];
};

/** L'article vouvoie déjà son lecteur : aucun `texteAuVous`. Les questions à
 *  la première personne (« est-ce que mon idée… », « Pourquoi moi ? ») sont
 *  celles que le lecteur se pose, pas un tutoiement. */
export const ARTICLE_IDEE_BUSINESS_VIABLE = {
  /** L'article n'a NI titre d'onglet NI méta-description sur le site actuel
   *  (relevé : titre vide, « (aucune) »). `propose` est une suggestion faite
   *  des mots de l'article, à valider. */
  entete: {
    titreOnglet: null,
    description: null,
    propose: {
      titreOnglet:
        "Ai-je une idée de business viable ? Les 4 questions à se poser – EVKHA",
      description:
        "Avant de vous lancer, 4 questions concrètes pour savoir si votre idée de business est viable dans la vraie vie : un vrai problème, une cible précise, des clients prêts à payer, ce qui vous rend différent.",
    },
  } as Entete,

  titre: "Ai-je une idée de business viable ?",
  sousTitre: "Les 4 Questions à se poser pour ne pas foncer dans le mur",

  /** Le chapô : l'intertitre d'ouverture et ses quatre paragraphes. */
  chapo: {
    intertitre: "Créer oui… mais pas n’importe quoi",
    paragraphes: [
      "Quand on a une idée de business, l’envie de foncer est souvent plus forte que la raison. On se projette, on imagine le logo, le site, les clients… Mais une question fondamentale reste souvent en suspens : est-ce que mon idée est vraiment viable ? Pas viable dans ma tête, mais viable dans la vraie vie, avec des clients, des revenus et une chance réelle de durer.",
      "Chez EVKHA, je vois chaque mois des créateurs motivés… mais mal orientés. Ils ont une bonne idée, mais pas encore le bon cadre.",
      "Voici 4 questions essentielles à vous poser avant de vous lancer.",
      "Des questions concrètes, pas des grandes théories. Pour construire un projet solide, sans vous planter dès les premières semaines.",
    ],
  },

  sections: [
    {
      intertitre:
        "Partie 1 – Pourquoi c’est important de valider son idée avant de créer ?",
      elements: [
        {
          genre: "paragraphe",
          texte:
            "Parce qu’un statut, ça se réfléchit en quelques heures. Mais une entreprise qui marche, ça se construit.",
        },
        {
          genre: "paragraphe",
          texte: "Trop d’entrepreneurs créent sans valider les fondations.",
        },
        {
          genre: "liste",
          introduction: "Résultat :",
          points: [
            "Pas de clients",
            "Des offres floues",
            "Des mois sans chiffre d’affaires",
            "De la démotivation… et parfois l’abandon",
          ],
        },
        {
          genre: "paragraphe",
          texte:
            "Valider son idée, ce n’est pas tout remettre en question. C’est juste s’assurer qu’elle peut tenir debout sur le marché.",
        },
      ],
    },
    {
      intertitre: "Partie 2 – Les 4 questions qui font la différence",
      elements: [],
      sousSections: [
        {
          intertitre: "1. Mon idée répond-elle à un vrai problème ?",
          elements: [
            {
              genre: "paragraphe",
              texte:
                "Une idée de business, ce n’est pas juste “j’aime faire ça” ou “je trouve ça cool”. C’est une solution à un besoin réel.",
            },
            {
              genre: "question",
              amorce: "Demandez-vous :",
              texte:
                "Quelle frustration, difficulté ou envie forte j’aide à résoudre ?",
            },
            {
              genre: "exemple",
              amorce: "Exemple :",
              texte:
                "Maya adore faire des cosmétiques maison. Mais son projet devient viable quand elle se positionne comme une solution pour les femmes qui veulent des soins efficaces sans perturbateurs endocriniens.",
            },
          ],
        },
        {
          intertitre:
            "2. Pour qui est-ce que je crée ? (et est-ce que cette personne existe vraiment)",
          elements: [
            {
              genre: "paragraphe",
              texte:
                "On ne vend jamais “à tout le monde”. Il faut un client cible précis.",
            },
            {
              genre: "question",
              amorce: "Demandez-vous :",
              texte:
                "Qui est la personne la plus susceptible d’acheter mon offre ? Quel âge a-t-elle ? Que vit-elle au quotidien ? Quelle est sa priorité ?",
            },
            {
              genre: "exemple",
              amorce: "Exemple :",
              texte:
                "Martin veut vendre des objets déco. Mais en analysant son marché, il découvre que sa vraie cible, ce sont les trentenaires en location qui veulent personnaliser leur intérieur sans faire de gros travaux.",
            },
          ],
        },
        {
          intertitre:
            "3. Est-ce que cette personne a déjà payé pour ce type de solution ?",
          elements: [
            {
              genre: "paragraphe",
              texte:
                "C’est la grande différence entre une bonne idée et une idée rentable. Un besoin non solvable n’est pas une opportunité de business.",
            },
            {
              genre: "question",
              amorce: "Demandez-vous :",
              texte:
                "Est-ce que ma cible est prête à payer pour ce problème ? Existe-t-il déjà des offres similaires sur le marché ?",
            },
            {
              genre: "exemple",
              amorce: "Exemple :",
              texte:
                "Léa voulait créer une appli gratuite pour suivre son cycle menstruel. Après recherche, elle réalise que les concurrentes payantes cartonnent… mais qu’il faut un modèle économique clair et une vraie valeur ajoutée pour percer. (modèle freemium)",
            },
          ],
        },
        {
          intertitre:
            "4. Qu’est-ce qui me rend différent(e), concret(e) ou crédible ?",
          elements: [
            {
              genre: "paragraphe",
              texte:
                "Vous n’avez pas besoin d’inventer la prochaine licorne. Mais vous avez besoin d’un élément différenciateur, même simple.",
            },
            {
              genre: "question",
              amorce: "Demandez-vous :",
              texte:
                "Pourquoi moi ? Qu’est-ce que j’apporte de plus clair, pratique, humain ou innovant ?",
            },
            {
              genre: "exemple",
              amorce: "Exemple :",
              texte:
                "Julie vend les mêmes bijoux que beaucoup d’autres… mais elle choisit de se démarquer avec une livraison 100 % recyclable, un packaging personnalisé à chaque commande et une mini carte écrite à la main. Résultat : des clientes fidèles.",
            },
          ],
        },
      ],
    },
    {
      intertitre: "Partie 3 – Comment faire si je doute ?",
      elements: [
        {
          genre: "paragraphe",
          texte:
            "Pas besoin d’avoir toutes les réponses tout de suite. Mais il est essentiel de ne pas se lancer à l’aveugle.",
        },
        {
          genre: "liste",
          introduction: "Ce que je vous recommande :",
          points: [
            "Faites une mini étude de marché ciblée",
            "Validez votre client idéal avec des échanges réels (questionnaires, appels, DMs…)",
            "Identifiez vos concurrents et analysez leurs points forts/faibles",
            "Demandez un regard extérieur (c’est ce que je propose dans mes accompagnements ou via ma formation P.O.P IA)",
          ],
        },
        {
          genre: "paragraphe",
          texte:
            "Et surtout… osez ajuster votre idée. Ce n’est pas un échec, c’est une preuve de maturité entrepreneuriale.",
        },
      ],
    },
  ] as SectionDArticle[],

  conclusion: {
    intertitre:
      "Conclusion – Une idée seule ne suffit pas. Une idée testée et structurée, oui.",
    elements: [
      {
        genre: "paragraphe",
        texte:
          "Créer son entreprise, c’est excitant. Mais c’est aussi stratégique.",
      },
      {
        genre: "liste",
        introduction: "Une idée viable, c’est une idée qui coche 3 cases :",
        points: [
          "Elle résout un vrai problème",
          "Pour une cible bien définie",
          "Qui est prête à payer pour ça",
        ],
      },
      {
        genre: "paragraphe",
        texte:
          "Prenez le temps de tester, d’observer le marché, et de vous positionner avec clarté. C’est ce qui fera la différence entre une envie… et un business durable.",
      },
    ] as ElementDArticle[],
    salut: "Bonne chance à vous!",
    /** Écrit « Evangéline », avec un accent, sur l'article ; le reste du site
     *  écrit « Evangeline ». Gardé tel que signé. */
    signature: "Evangéline",
  },

  /** L'appel de fin d'article.
   *
   *  PASSAGE DOUTEUX : il annonce une checklist « Ai-je une idée de business
   *  viable ? » en PDF et renvoie vers la boîte à outils — or la boîte à
   *  outils ne propose que la checklist « micro-entreprise en 10 étapes » et
   *  le lexique. Le document promis n'y est pas. */
  appel: {
    titre: "Bonus EVKHA à télécharger",
    document: "La checklist \"Ai-je une idée de business viable ?\" (PDF)",
    corps: "À imprimer et remplir avant de vous lancer",
    lien: LIENS_RESSOURCES.article.bonus,
  },
};

// ── 3. La page de contact (`/contacts`) ─────────────────────────────────────

export const CONTACT = {
  entete: {
    /** « ontact page » sur le site : la première lettre manque. Corrigé. Le
     *  titre tutoie (« ton projet »), la description vouvoie déjà. */
    titreOnglet: {
      texte: "Contact page EVKHA – Parlons de ton projet d’entreprise",
      texteAuVous: "Contact page EVKHA – Parlons de votre projet d’entreprise",
    },
    description: {
      texte:
        "Une question ? Un projet ? Écrivez-moi via ce formulaire et je vous aiderai à passer de l’idée à l’action. Réponse garantie sous 48h.",
    },
    propose: {
      titreOnglet: "Contact – Parlons de votre projet d’entreprise | EVKHA",
      description:
        "Une question ? Un projet ? Écrivez-moi via ce formulaire et je vous aiderai à passer de l’idée à l’action. Réponse garantie sous 48h.",
    },
  } as Entete,

  /** Bloc 1 — l'accroche, sous le visuel d'ouverture. */
  accroche: {
    titre: "Posez-nous toutes vos questions !",
    corps: "Une demande d'étude de marché, une question sur nos formations ?",
  },

  /** Bloc 2 — le formulaire, sous le second visuel. Son titre, son délai et
   *  son bouton sont dans `FORMULAIRES.contact` : une seule écriture. */
  formulaire: "contact",
} as const;

// ── 4. Le partenaire SWAPN (`/swapn`) ───────────────────────────────────────

/** La page ne porte, en texte, QUE son titre, un formulaire et un bouton.
 *  L'offre elle-même est écrite dans une image (le second visuel n'est que le
 *  logo Swapn) : son texte, relevé le 19/11/2026, est dans
 *  `texteLuDansLeVisuel`. Rien d'autre n'est dit ici sur SWAPN : ce serait
 *  inventer. La page ne tutoie pas. */
export const SWAPN = {
  entete: {
    /** En capitales et sans accent sur le site (« CREER ») : gardés tels que
     *  relevés. `propose` en donne une écriture courante, mêmes mots. */
    titreOnglet: { texte: "SWAPN PARTENAIRE EVKHA BUSINESS ET FORMATIONS" },
    description: {
      texte:
        "MISE EN RELATION GRATUITE AVEC MON PARTENAIRE SWAPN ! CREER VOTRE ENTREPRISE GRATUITEMENT",
    },
    propose: {
      titreOnglet: "SWAPN, partenaire d’EVKHA Business & Formations",
      description:
        "Mise en relation gratuite avec mon partenaire SWAPN ! Créez votre entreprise gratuitement.",
    },
  } as Entete,

  /** Bloc 1 — le titre, sur deux lignes. */
  titre: ["MISE EN RELATION GRATUITE", "AVEC MON PARTENAIRE SWAPN !"],

  /** Bloc 2 — les deux visuels, dans l'ordre : le visuel de l'offre, puis le
   *  logo Swapn. */
  visuels: [
    `${CDN}/9890127/68f604cfebdd7_SWPAN2.png`,
    `${CDN}/9890127/68f603ab0d9dd_SWAPN.png`,
  ],

  /** CE TEXTE VIENT D'UNE IMAGE (`68f604cfebdd7_SWPAN2.png`, le premier
   *  visuel), pas du texte de la page : ce sont les mots de SWAPN, sur son
   *  propre visuel, relevés le 19/11/2026. À écrire en vrai texte sur la
   *  nouvelle page (une offre lisible seulement dans une image est invisible
   *  pour un lecteur d'écran et pour un moteur de recherche).
   *
   *  Le relevé donne six fragments séparés ; leur regroupement ci-dessous
   *  (accroche, mention, offre, trois arguments) suit leur ordre et leur
   *  ponctuation, pas une lecture de la mise en page de l'image.
   *
   *  NON REPRIS, volontairement : les notes d'avis affichées dans l'image.
   *  Elles appartiennent à SWAPN et datent.
   *
   *  À FAIRE VALIDER AVANT AFFICHAGE : « le mieux noté de France », « 0 € »
   *  et « en 24h » sont des promesses de SWAPN, pas d'EVKHA. « 0 € » n'est
   *  pas un prix d'une offre EVKHA : il n'a sa place dans aucune constante
   *  de tarifs. */
  texteLuDansLeVisuel: {
    accroche:
      "La création d'entreprise simple et rapide, le conseil en plus",
    mention: "Le service de création le mieux noté de France",
    offre: ["Créer une entreprise", "0\u00a0€", "Sans engagement"],
    arguments: [
      {
        titre: "Simplicité",
        corps: "Swapn s'occupe de vos démarches administratives",
      },
      {
        titre: "Service express",
        corps: "recevez vos statuts en 24h",
      },
      {
        titre: "Accompagnement",
        corps:
          "votre expert dédié vous conseille sur la forme juridique la mieux adaptée à votre projet",
      },
    ],
  },

  /** Bloc 3 — le formulaire de mise en relation (`FORMULAIRES.swapn`). */
  formulaire: "swapn",
} as const;

// ── 5. Ce que la refonte AJOUTE (`Ressources.tsx`) ──────────────────────────
//
// Tout ce qui précède est RELEVÉ sur le site de la cliente. Tout ce qui suit
// est ÉCRIT pour la nouvelle forme des pages : surtitres, intitulés de
// boutons, objets des courriels, phrases de liaison, passerelles. Aucun fait,
// aucun chiffre, aucun prix. À valider par la cliente, comme les champs
// `propose`.

/** Le texte d'un bloc au vouvoiement : `texteAuVous` quand le relevé tutoie,
 *  le texte d'origine sinon. La plateforme vouvoie partout. */
export function auVous(bloc: Texte): string {
  return bloc.texteAuVous ?? bloc.texte;
}

/** Un titre RELEVÉ, coupé en deux pour que sa fin passe en italique, comme
 *  les titres de l'accueil et de la page des études. Le titre n'est pas
 *  réécrit : on désigne seulement où il se coupe. S'il ne se termine plus par
 *  l'accent attendu, le module LÈVE une erreur au chargement — un titre
 *  amputé passerait inaperçu (règle 1). Même garde que `contenuEtudes`, dont
 *  la fonction n'est pas exportée. */
function enDeuxTemps(titre: string, accent: string): { avant: string; fin: string } {
  if (accent === "" || !titre.endsWith(accent) || titre.length === accent.length) {
    throw new Error(
      `contenuRessources : le titre « ${titre} » ne se termine pas par « ${accent} »`,
    );
  }
  return { avant: titre.slice(0, -accent.length).trimEnd(), fin: accent };
}

/** Les routes de la plateforme que ces pages citent. Un ALIAS : chaque chemin
 *  est lu dans `contenuSite.CHEMINS`, la seule source des adresses du site
 *  (règle 5). Le nom est gardé pour les fichiers qui l'importent. */
export const ROUTES_RESSOURCES = {
  boiteAOutils: CHEMINS.boiteAOutils,
  contact: CHEMINS.contact,
  swapn: CHEMINS.swapn,
  etudes: CHEMINS.etudes,
  packs: CHEMINS.packs,
  formations: CHEMINS.formations,
  partenaires: CHEMINS.partenaires,
} as const;

/** RETOUCHE D'AFFICHAGE : un document ne se télécharge pas sur la plateforme.
 *
 *  Le site de la cliente délivrait la checklist et le lexique par un
 *  formulaire ; la plateforme n'a ni formulaire ni fichier à servir, et le
 *  visiteur les DEMANDE par courriel (`courrielAvecObjet`). Une page qui
 *  écrit « Téléchargez… » au-dessus d'un bouton qui ouvre un courriel promet
 *  ce qu'elle ne fait pas.
 *
 *  À l'affichage, donc : « à télécharger » devient « à recevoir par e-mail »
 *  et « Téléchargez » « Recevez par e-mail ». Le texte RELEVÉ, plus haut,
 *  n'est pas touché — le jour où les fichiers sont servis, il suffit de ne
 *  plus passer par cette fonction. Elle vise la CLASSE (règle 4) : tout texte
 *  qui passe par elle, pas trois phrases désignées ; le test du lot verrouille
 *  qu'aucun « télécharg… » ne reste affiché sur la boîte à outils ni dans
 *  l'encart de fin d'article. */
export function sansTelechargement(texte: string): string {
  return texte
    .replace(/à télécharger/g, "à recevoir par e-mail")
    .replace(/Téléchargez\b/g, "Recevez par e-mail")
    .replace(/téléchargez\b/g, "recevez par e-mail");
}

/** Un lien `mailto:` vers l'adresse de contact, objet prérempli. C'est le
 *  moyen qui remplace chaque formulaire du site : la plateforme n'a pas de
 *  service pour recevoir un message ni envoyer un document. */
export function courrielAvecObjet(objet: string): string {
  return `mailto:${COORDONNEES.courriel}?subject=${encodeURIComponent(objet)}`;
}

/** Une passerelle de fin de page : UNE porte vers l'étape payante la plus
 *  proche, sans prix. */
export type Passerelle = {
  titre: { avant: string; fin: string };
  corps: string;
  bouton: { libelle: string; lien: string };
};

export const PAGE_BOITE_A_OUTILS = {
  surtitre: "Boîte à outils",
  titre: enDeuxTemps(BOITE_A_OUTILS.ouverture.titre, "100 % gratuit"),
  surtitreDesRessources: "En libre accès",
  titreDesRessources: enDeuxTemps(BOITE_A_OUTILS.titreDesRessources, "& Vos Outils"),
  /** L'étiquette de chaque carte, selon `Ressource.nature`. */
  natures: { document: "Document à recevoir par e-mail", article: "Article du blog" },
  /** Le bouton des deux documents : un courriel à EVKHA, qui répond avec le
   *  fichier. */
  recevoir: "Recevoir par e-mail",
  /** L'objet prérempli du courriel, qui nomme la ressource demandée. */
  objets: {
    checklist:
      "Je souhaite recevoir la checklist « Créer sa micro-entreprise en 10 étapes »",
    lexique: "Je souhaite recevoir le lexique EVKHA des termes entrepreneuriaux",
  },
  passerelle: {
    titre: { avant: "Des outils pour démarrer,", fin: "une formation pour avancer." },
    corps:
      "Les formations EVKHA vous accompagnent dans la création de votre entreprise ou de votre micro-entreprise.",
    bouton: { libelle: "Découvrir les formations", lien: ROUTES_RESSOURCES.formations },
  } as Passerelle,
};

/** La méta-description relevée dit « Écrivez-moi via ce formulaire » : la page
 *  n'a plus de formulaire. Les mêmes mots, sans ces trois-là — et une erreur
 *  au chargement si la phrase relevée a changé (règle 1). */
function sansLaMentionDuFormulaire(description: string): string {
  const mention = " via ce formulaire";
  if (!description.includes(mention)) {
    throw new Error(
      `contenuRessources : la description du contact ne dit plus «${mention} »`,
    );
  }
  return description.replace(mention, "");
}

export const PAGE_CONTACT = {
  titreOnglet: "Contact – Parlons de votre projet d’entreprise | EVKHA",
  description: sansLaMentionDuFormulaire(CONTACT.entete.description?.texte ?? ""),
  surtitre: "Contact",
  titre: enDeuxTemps(CONTACT.accroche.titre, "vos questions !"),
  surtitreDesMoyens: "Nous joindre",
  moyens: {
    ecrire: {
      surtitre: "Par e-mail",
      titre: "Écrivez-nous",
      bouton: "Écrire à EVKHA",
      objet: "Question pour EVKHA",
    },
    rendezVous: {
      surtitre: "De vive voix",
      titre: "Prenez rendez-vous",
      corps: "Réservez un créneau dans l'agenda en ligne d'EVKHA.",
      bouton: "Choisir un créneau",
    },
    reseaux: {
      surtitre: "Sur les réseaux",
      titre: "Suivez EVKHA",
      corps: "Les actualités d'EVKHA, là où vous êtes déjà.",
    },
  },
  aide: {
    surtitre: "Avant d'écrire",
    titre: { avant: "Pour quoi", fin: "nous écrire ?" },
    corps: "La réponse à votre question est peut-être déjà sur l'une de ces pages.",
    orientations: [
      {
        titre: "Une étude pour votre projet",
        corps:
          "Étude de marché, étude de la concurrence, business plan, stratégie : la page des études les présente une à une.",
        lien: ROUTES_RESSOURCES.etudes,
      },
      {
        titre: "Un pack d'accompagnement",
        corps: "Ce que contient chaque pack est détaillé sur la page des packs.",
        lien: ROUTES_RESSOURCES.packs,
      },
      {
        titre: "Une formation",
        corps: "Le programme de chaque formation est sur la page des formations.",
        lien: ROUTES_RESSOURCES.formations,
      },
      {
        titre: "Vous accompagnez des porteurs de projet",
        corps:
          "Les formules pour les professionnels sont sur la page des partenaires.",
        lien: ROUTES_RESSOURCES.partenaires,
      },
    ],
  },
  passerelle: {
    titre: { avant: "Votre question porte sur", fin: "votre marché ?" },
    corps: "C'est le sujet des études EVKHA, rédigées sur votre projet.",
    bouton: { libelle: "Voir les études", lien: ROUTES_RESSOURCES.etudes },
  } as Passerelle,
};

/** Le titre de la page SWAPN est relevé EN CAPITALES. Il est affiché en
 *  écriture courante, mêmes mots : la garde ci-dessous compare les deux, et
 *  lève une erreur au chargement s'ils divergent (règle 5 : le relevé reste
 *  la source). */
function enEcritureCourante(
  releve: readonly string[],
  courant: { avant: string; fin: string },
): { avant: string; fin: string } {
  const attendu = releve.join(" ").toLocaleUpperCase("fr");
  const ecrit = `${courant.avant} ${courant.fin}`.toLocaleUpperCase("fr");
  if (attendu !== ecrit) {
    throw new Error(
      `contenuRessources : le titre « ${ecrit} » n'est plus celui du relevé « ${attendu} »`,
    );
  }
  return courant;
}

export const PAGE_SWAPN = {
  surtitre: "Partenaire",
  titre: enEcritureCourante(SWAPN.titre, {
    avant: "Mise en relation gratuite",
    fin: "avec mon partenaire Swapn !",
  }),
  /** Le logo rapatrié (`public/accueil/logo-swapn.webp`), à ses dimensions. */
  logo: { src: "/accueil/logo-swapn.webp", alt: "Swapn", largeur: 404, hauteur: 402 },
  /** L'offre est celle DU PARTENAIRE : chaque bloc qui la cite le dit. */
  offre: {
    surtitre: "Selon Swapn",
    titre: { avant: "Ce que propose", fin: "Swapn." },
    attribution: "Selon Swapn :",
    source:
      "Offre présentée par Swapn. Ses conditions, ses tarifs et ses délais sont ceux de Swapn, et non un engagement d'EVKHA.",
  },
  relation: {
    surtitre: "Mise en relation",
    titre: { avant: "Un message,", fin: "et Swapn vous contacte." },
    corps:
      "Écrivez-nous en indiquant votre nom. En envoyant ce message, vous demandez à EVKHA de transmettre votre nom et votre adresse e-mail à Swapn, qui vous recontactera.",
    bouton: "Demander la mise en relation",
    objet: "Mise en relation avec Swapn",
  },
  passerelle: {
    titre: { avant: "Avant les statuts,", fin: "votre marché." },
    corps:
      "Avant de créer votre entreprise, vérifiez que votre projet a un marché : c'est l'objet des études EVKHA.",
    bouton: { libelle: "Voir les études", lien: ROUTES_RESSOURCES.etudes },
  } as Passerelle,
};
