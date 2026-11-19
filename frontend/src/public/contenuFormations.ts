/** Le texte des pages de l'Académie EVKHA : le catalogue des formations et
 *  les trois pages de formation (sociétés, micro-entreprise, Méthode P.O.P).
 *
 *  D'OÙ VIENT LE CONTENU. Du site actuel de la cliente (`www.evkha.fr`,
 *  Systeme.io), relevé le 25/10/2026 dans
 *  `docs/refonte/inventaire-site-evkha.md` :
 *    - section 2  `/formation`                 → le catalogue ;
 *    - section 35 `/achat-formationpop`        → la page Méthode P.O.P ;
 *    - section 36 `/achat-formationsociete`    → la page « sociétés » ;
 *    - section 37 `/achat-formationmicro`      → la page « micro-entreprise » ;
 *    - sections 10, 11, 12 `/paiement-formation*` → ce que les tunnels de
 *      paiement disent de chaque formation, et les cases de la commande ;
 *    - sections 30 à 33 (pages légales) → le numéro de déclaration d'activité,
 *      qui ne figure sur AUCUNE page de formation.
 *
 *  CE QUI A ÉTÉ RETOUCHÉ, et rien d'autre. Le texte est repris tel quel : ni
 *  résumé, ni réécriture, ni passage du « je » au « nous ».
 *    - Retirés : le menu, le pied de page, les liens légaux, le logo d'en-tête,
 *      la fenêtre surgissante périmée « CETTE FORMATION SERA DISPONIBLE DÈS
 *      SEPTEMBRE 2025 ! » et son bouton d'inscription, le bouton resté à l'état
 *      de gabarit (« Cliquez ici / Sous-titre ici »), l'étiquette de formulaire
 *      « ADRESSE ».
 *    - Espaces parasites du relevé (« D e l'idée », « solide , ») resserrées.
 *    - Coquilles évidentes corrigées : « accompagné » → « accompagner »,
 *      « qui couvrent » → « qui couvre », « maîtrisez » → « maîtriser »,
 *      « etude » → « étude », « adminsitratifs » → « administratifs »,
 *      « previsionnel » → « prévisionnel », « kPi » → « KPI », « assitant ia »
 *      → « assistant IA », « entierement » → « entièrement », « Laissez le »
 *      → « Laissez-le », « porteurs de projet; entrepreneurs » → virgule,
 *      « Produisez.! » → « Produisez ! », « au quotidien. ! » → « au quotidien ! ».
 *    - Une parenthèse jamais ouverte (« …prévisionnel financier..) ») a été
 *      remplacée par des points de suspension.
 *    - Les « ... » qui terminent les trois listes « Ce que vous allez
 *      maîtriser » ne sont pas repris : la liste s'arrête à son dernier point.
 *    - « Pôle Emploi » n'apparaît sur aucune de ces pages : elles écrivent
 *      déjà « France Travail ».
 *
 *  LES CAPTURES D'ÉCRAN. Les pages `/achat-formationsociete`,
 *  `/achat-formationmicro` et `/achat-formationpop` sont faites presque
 *  entièrement de CAPTURES D'ÉCRAN. Les seize captures de ces trois pages ont
 *  été LUES ET RETRANSCRITES mot pour mot le 19/11/2026 : ouverture,
 *  argumentaire « pourquoi cette formation », formes juridiques, « ce qui est
 *  inclus », coaching, objectifs pédagogiques, public, cœur de la méthode
 *  P.O.P. Elles portent `retranscrite: true` dans
 *  `IMAGES_FORMATIONS_A_RAPATRIER` : leur texte est ici, elles n'ont plus à
 *  être affichées.
 *
 *  CE QUI MANQUE ENCORE. AUCUNE des seize captures ne porte les INTITULÉS DES
 *  MODULES : les tableaux `programme.modules` restent VIDES, pas inventés. Les
 *  captures des tunnels de paiement qui n'ont pas été lues (entrées sans
 *  `retranscrite`) sont le seul endroit où ils peuvent encore se trouver.
 *
 *  CE QUE LES CAPTURES CONTREDISENT (rien n'a été tranché ici) :
 *    - la capture d'ouverture « sociétés » écrit « 9 modules », le tunnel de
 *      paiement « Les 10 modules du parcours » (`NOMBRE_DE_MODULES.societes`) ;
 *    - la capture des formes juridiques écrit « tableau CMA », le texte du
 *      tunnel « tableau comparatif » ;
 *    - le titre annonce « 5 formes juridiques », la capture en montre QUATRE
 *      cartes (SASU et SAS partagent la même) ;
 *    - les trois pages annoncent une « Attestation Qualiopi » : aucun texte
 *      relevé du site ne mentionne de certification Qualiopi (les pages
 *      légales ne donnent qu'un numéro de déclaration d'activité). À FAIRE
 *      CONFIRMER par la cliente avant d'afficher ce mot.
 *
 *  Une seule écriture par fait : les prix dans `TARIFS_FORMATIONS`, les durées
 *  dans `DUREES_*`, le nombre de modules dans `NOMBRE_DE_MODULES`, les adresses
 *  dans `LIENS_FORMATIONS`. Le reste du fichier les lit.
 */

// ── Prix ────────────────────────────────────────────────────────────────────

/** Les prix des trois formations, en CENTIMES, toutes taxes comprises.
 *
 *  RELEVÉS SUR evkha.fr LE 25/10/2026 (page `/formation`). C'est la SEULE
 *  source de ces montants dans le dépôt : aucune API de la plateforme ne les
 *  rend aujourd'hui. À REMPLACER par le catalogue du serveur le jour où ces
 *  offres y entrent — ce jour-là, cette constante disparaît et les pages
 *  lisent l'API, comme l'accueil lit ses prix.
 *
 *  Les formations en présentiel n'ont pas de prix affiché sur le site. */
export const TARIFS_FORMATIONS = {
  societes: { centimes: 149000, ttc: true },
  micro: { centimes: 149000, ttc: true },
  pop: { centimes: 85000, ttc: true },
} as const;

export type CleDeFormation = keyof typeof TARIFS_FORMATIONS;

/** Le prix tel que le site l'écrit : « 1490 € TTC », « 850 € TTC ». */
export function prixAffiche(cle: CleDeFormation): string {
  const tarif = TARIFS_FORMATIONS[cle];
  return `${tarif.centimes / 100}\u00a0€${tarif.ttc ? " TTC" : ""}`;
}

// ── Durées ──────────────────────────────────────────────────────────────────

/** « Créer son entreprise de A à Z » : 18 h en ligne, 2 h de coaching en
 *  visio réparties en 2 séances d'1 heure (pages `/formation` et
 *  `/paiement-formationsociete`). */
export const DUREES_SOCIETES = {
  heuresEnLigne: 18,
  heuresDeCoaching: 2,
  seancesDeCoaching: 2,
  heuresParSeance: 1,
} as const;

/** « Créer sa micro-entreprise de A à Z ». Les 2 h de coaching viennent de
 *  `/paiement-formationmicro`. Les 18 h ne sont écrites en TEXTE sur aucune
 *  des pages de cette formation, mais deux captures de `/achat-formationmicro`
 *  les portent (lues le 19/11/2026) : « 18h de formation » dans l'ouverture,
 *  « 18h de formation digitale » dans « ce qui est inclus ». Elles confirment
 *  aussi les 2 h en 2 séances d'1 h. */
export const DUREES_MICRO = {
  heuresEnLigne: 18,
  heuresDeCoaching: 2,
  seancesDeCoaching: 2,
  heuresParSeance: 1,
} as const;

/** Méthode P.O.P : 7 h, sans coaching individuel. */
export const DUREES_POP = {
  heuresEnLigne: 7,
} as const;

/** Le nombre de modules annoncé par les tunnels de paiement. Les INTITULÉS
 *  des modules ne sont écrits nulle part : ni en texte, ni dans les seize
 *  captures des pages d'achat lues le 19/11/2026.
 *
 *  CONTRADICTION NON TRANCHÉE : la capture d'ouverture de
 *  `/achat-formationsociete` écrit « 9 modules », pas 10 (voir
 *  `PAGE_SOCIETES.ouvertureEnImage.pastilleContredite`). Celle de la
 *  micro-entreprise écrit « 9 modules », conforme. */
export const NOMBRE_DE_MODULES = {
  societes: 10,
  micro: 9,
} as const;

/** Le plan d'action remis à l'issue du coaching « micro » : 30 jours. */
const JOURS_DU_PLAN_D_ACTION_MICRO = 30;

// ── Organisme de formation et financement ───────────────────────────────────

/** Le numéro de déclaration d'activité (NDA) et les mentions de financement,
 *  mot pour mot.
 *
 *  Le NDA est relevé dans les pages légales (`/mentions-legales`, `/rgpd`,
 *  `/cgv`, `/politique-de-confidentialite`), où la ligne est écrite à
 *  l'identique quatre fois. Il ne figure sur aucune page de formation. */
const NDA = "32591302259";

export const ORGANISME_DE_FORMATION = {
  nda: NDA,
  /** La ligne telle que relevée, espace avant la virgule comprise. */
  mentionRelevee: `Numero NDA , organisme de formation: ${NDA}`,
  financement: {
    /** Bloc « Nos formations en présentiel » de `/formation`. */
    presentiel: "Possibilité de prise en charge OPCO / France Travail",
    /** Question fréquente de `/formation`. */
    question: "Les formations sont-elles éligibles à un financement ?",
    reponse:
      "Les formations peuvent être éligibles à un financement OPCO ou France Travail selon votre situation. Contactez-nous par mail pour étudier ensemble vos possibilités.",
  },
} as const;

// ── Adresses ────────────────────────────────────────────────────────────────

/** La destination de chaque bouton, telle que relevée. Ce sont les adresses
 *  de l'ANCIEN site : à remplacer par les routes de la plateforme au
 *  basculement (et à couvrir par une redirection 301).
 *
 *  `sessionsEnPresentiel` vaut `null` : le bouton n'a pas d'adresse, il ouvre
 *  une fenêtre d'inscription par e-mail. */
export const LIENS_FORMATIONS = {
  catalogue: "https://www.evkha.fr/formation",
  decouvrirSocietes: "https://www.evkha.fr/achat-formationsociete",
  decouvrirMicro: "https://www.evkha.fr/achat-formationmicro",
  decouvrirPop: "https://www.evkha.fr/achat-formationpop",
  paiementSocietes: "https://www.evkha.fr/paiement-formationsociete",
  paiementMicro: "https://www.evkha.fr/paiement-formationmicro",
  paiementPop: "https://www.evkha.fr/paiement-formationpopok",
  sessionsEnPresentiel: null,
  contact: "https://www.evkha.fr/contacts",
} as const;

// ── Images ──────────────────────────────────────────────────────────────────

export type ImageARapatrier = {
  /** Le chemin de la page du site actuel où l'image a été relevée. */
  page: string;
  adresse: string;
  contexte: string;
  /** `true` : la capture a été LUE et tout son texte est dans ce fichier ;
   *  elle n'a plus à être affichée ni rapatriée pour son contenu. Absent :
   *  l'image n'a pas été regardée, ou n'est pas une capture de texte. */
  retranscrite?: true;
};

const CDN = "https://d1yei2z3i6k35z.cloudfront.net/9890127";

/** Toutes les images relevées sur les pages de formation, dans l'ordre de
 *  chaque page. RIEN N'EST TÉLÉCHARGÉ : c'est la liste de ce qu'il faudra
 *  rapatrier (et, pour les captures d'écran, RETRANSCRIRE en texte) avant la
 *  fermeture de l'ancien site.
 *
 *  Aucune image du site n'a de texte alternatif. Pour les entrées marquées
 *  `retranscrite`, le contexte dit ce que la capture MONTRE (lue le
 *  19/11/2026) et où son texte est rangé. Pour les autres, il dit seulement où
 *  l'image se trouve dans la page — personne ne l'a regardée.
 *
 *  L'appariement entre une capture lue et son entrée suit L'ORDRE DE LA PAGE
 *  (1re capture lue = 1re capture relevée, etc.), pas une comparaison des
 *  fichiers. Deux entrées de pages différentes ne sont dites « même fichier »
 *  que si leur adresse est identique à l'octet près.
 *
 *  Les noms de fichiers portent des accents (« Capturedécran…à… ») : pour une
 *  adresse exacte à l'octet près, lire `docs/refonte/images-site-evkha.json`. */
export const IMAGES_FORMATIONS_A_RAPATRIER: ImageARapatrier[] = [
  // /formation
  {
    page: "/formation",
    adresse: `${CDN}/6a33fd586856b7.97183294_LOGOEVKHABUSINESSETFORM.png`,
    contexte: "Logo de l'en-tête (commun à tout le site).",
  },
  {
    page: "/formation",
    adresse: `${CDN}/6844d0a794f08_ChatGPTImage8juin202501_48_06.png`,
    contexte: "Logo du second en-tête (menu du téléphone).",
  },
  {
    page: "/formation",
    adresse: `${CDN}/6845f5a471b32_Bienvenue2.png`,
    contexte: "Ouverture, sous le texte d'introduction.",
  },
  {
    page: "/formation",
    adresse: `${CDN}/684a946e44f4f_assets_task_01jxhmwza8e34sr6g7f9cn76ry_1749717900_img_0.jpg`,
    contexte:
      "Entre la preuve « Plus de 500 entrepreneurs… » et « Pourquoi choisir nos formations ? ».",
  },
  {
    page: "/formation",
    adresse: `${CDN}/684a96d7cdc25_17026.jpg`,
    contexte: "Bloc « Pourquoi choisir nos formations ? », avant « NOS FORMATIONS ONT : ».",
  },
  {
    page: "/formation",
    adresse: `${CDN}/6a37970d09ce70.05716078_Page_de_couverture_entreprise.png`,
    contexte: "Carte « Créer son entreprise de A à Z » : page de couverture.",
  },
  {
    page: "/formation",
    adresse: `${CDN}/684fe7e487d66_Pagedecouverturemicroentreprise.png`,
    contexte: "Carte « Créer sa micro-entreprise de A à Z » : page de couverture.",
  },
  {
    page: "/formation",
    adresse: `${CDN}/684fe80bebc4c_PAGEDECOUVERTUREMETHODEPOP.png`,
    contexte: "Carte « Formation P.O.P » : page de couverture.",
  },
  {
    page: "/formation",
    adresse: `${CDN}/6846238d0a4b6_undraw_web-shopping_m3o2.png`,
    contexte: "« À qui ça s'adresse ? » : illustration placée avant « Porteurs de projet ».",
  },
  {
    page: "/formation",
    adresse: `${CDN}/6846239d11344_undraw_got-an-idea_1z3i.png`,
    contexte: "« À qui ça s'adresse ? » : illustration placée avant « En reconversion PRO ».",
  },
  {
    page: "/formation",
    adresse: `${CDN}/684623acce1fa_undraw_building-a-website_1wrp.png`,
    contexte: "« À qui ça s'adresse ? » : illustration placée avant « Freelances ».",
  },
  {
    page: "/formation",
    adresse: `${CDN}/6846238e90e0c_undraw_email-consent_j36b.png`,
    contexte:
      "« À qui ça s'adresse ? » : illustration placée avant « Demandeurs d'emploi ». Le cinquième profil, « Entrepreneurs », n'a pas d'image.",
  },
  {
    page: "/formation",
    adresse: `${CDN}/671ef2ea1600b_avis09.png`,
    contexte: "« Nos avis clients » : avis en image (1er affiché).",
  },
  {
    page: "/formation",
    adresse: `${CDN}/671ef2d1686c2_avis06.png`,
    contexte: "« Nos avis clients » : avis en image (2e affiché).",
  },
  {
    page: "/formation",
    adresse: `${CDN}/671ef2e0d6a24_avis08.png`,
    contexte: "« Nos avis clients » : avis en image (3e affiché).",
  },
  {
    page: "/formation",
    adresse: `${CDN}/671ef2d97eba3_avis07.png`,
    contexte: "« Nos avis clients » : avis en image (4e affiché).",
  },
  {
    page: "/formation",
    adresse: `${CDN}/671ef2c8ac715_avis05.png`,
    contexte: "« Nos avis clients » : avis en image (5e affiché).",
  },
  {
    page: "/formation",
    adresse: `${CDN}/671ef2b926073_avis04.png`,
    contexte: "« Nos avis clients » : avis en image (6e affiché).",
  },
  {
    page: "/formation",
    adresse: `${CDN}/671ef2a64a17e_avis03.png`,
    contexte: "« Nos avis clients » : avis en image (7e affiché).",
  },
  {
    page: "/formation",
    adresse: `${CDN}/671ef2944afa3_avis02.png`,
    contexte: "« Nos avis clients » : avis en image (8e affiché).",
  },
  {
    page: "/formation",
    adresse: `${CDN}/671ef27647d2b_avis01.png`,
    contexte: "« Nos avis clients » : avis en image (9e affiché).",
  },

  // /achat-formationsociete
  {
    page: "/achat-formationsociete",
    adresse: `${CDN}/6a33fd586856b7.97183294_LOGOEVKHABUSINESSETFORM.png`,
    contexte: "Logo de l'en-tête (commun à tout le site).",
  },
  {
    page: "/achat-formationsociete",
    adresse: `${CDN}/6844d0a794f08_ChatGPTImage8juin202501_48_06.png`,
    contexte: "Logo du second en-tête (menu du téléphone).",
  },
  {
    page: "/achat-formationsociete",
    adresse: `${CDN}/6a38faba927060.05496497_Capturedécran2026-06-22à11.02.49.png`,
    contexte:
      "CAPTURE D'ÉCRAN, première image de la page. Montre l'ouverture sur fond noir : étiquette « PARCOURS PREMIUM », titre, accroche, présentation, cinq pastilles de statuts et quatre pastilles (18h, + 2h, « 9 modules », outils financiers). Rangée dans PAGE_SOCIETES.ouvertureEnImage.",
    retranscrite: true,
  },
  {
    page: "/achat-formationsociete",
    adresse: `${CDN}/684a95bdf2e49_2147650929.jpg`,
    contexte: "Photographie, sous la capture d'ouverture.",
  },
  {
    page: "/achat-formationsociete",
    adresse: `${CDN}/6a38fb0eee2276.32106831_Capturedécran2026-06-22à10.51.17.png`,
    contexte:
      "CAPTURE D'ÉCRAN sous « Si vous vous reconnaissez là-dedans, vous êtes au bon endroit ». Montre « Créer une vraie société, ça ne s'improvise pas » : deux colonnes, six difficultés du hors micro et six bénéfices de la formation. Rangée dans PAGE_SOCIETES.pourQui (situations et argumentaire).",
    retranscrite: true,
  },
  {
    page: "/achat-formationsociete",
    adresse: `${CDN}/6a38fb2fb1bfb1.62556950_Capturedécran2026-06-22à11.03.08.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 1re après le bouton « JE REJOINS LA FORMATION ! ». Montre « 5 formes juridiques, expliquées et comparées » : quatre cartes (EI, EURL, SARL, SASU / SAS) de quatre points chacune. Rangée dans PAGE_SOCIETES.statuts (formes, phraseDeLaCapture).",
    retranscrite: true,
  },
  {
    page: "/achat-formationsociete",
    adresse: `${CDN}/6a38fb5f0ea271.21915178_Capturedécran2026-06-22à11.03.36.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 2e après le bouton. Montre « CE QUI EST INCLUS — Tout ce qu'il faut pour créer et piloter votre société » : six cartes. Rangée dans PAGE_SOCIETES.inclus.",
    retranscrite: true,
  },
  {
    page: "/achat-formationsociete",
    adresse: `${CDN}/6a38fbea668463.76312984_Capturedécran2026-06-22à11.03.20.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 3e après le bouton. Montre « ACCOMPAGNEMENT INDIVIDUEL PREMIUM — Un coaching humain, sur votre projet réel » : le grand « 2H » et cinq points. Rangée dans PAGE_SOCIETES.modalites.coaching (captureDAchat, points).",
    retranscrite: true,
  },
  {
    page: "/achat-formationsociete",
    adresse: `${CDN}/6a38f7b6287a97.09647742_Capturedécran2026-06-22à10.51.28.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 4e après le bouton. Montre « OBJECTIFS PÉDAGOGIQUES — Ce que vous saurez faire à la fin de la formation » : huit objectifs numérotés 01 à 08. Ce ne sont PAS les modules. Rangée dans PAGE_SOCIETES.objectifs. Même fichier (adresse identique) sur /paiement-formationsociete.",
    retranscrite: true,
  },
  {
    page: "/achat-formationsociete",
    adresse:
      "https://d1yei2z3i6k35z.cloudfront.net/9453866/670d706f007bf_LOGOEVKHABUSINESSETFORM.png",
    contexte: "Logo du pied de page.",
  },

  // /paiement-formationsociete
  {
    page: "/paiement-formationsociete",
    adresse: `${CDN}/6a33fd586856b7.97183294_LOGOEVKHABUSINESSETFORM.png`,
    contexte: "Logo de l'en-tête.",
  },
  {
    page: "/paiement-formationsociete",
    adresse: `${CDN}/6a38f7a604c3d7.97354491_Capturedécran2026-06-22à10.50.52.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 1re sous « Plus qu'une étape avant de vous former… ». Texte à retranscrire.",
  },
  {
    page: "/paiement-formationsociete",
    adresse: `${CDN}/6a38f7b6287a97.09647742_Capturedécran2026-06-22à10.51.28.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 2e sous le titre, juste avant « Formez-vous avec / Les 10 modules du parcours ». Même fichier (adresse identique) que la 4e capture de /achat-formationsociete : ce sont les huit OBJECTIFS PÉDAGOGIQUES, pas la liste des modules. Rangée dans PAGE_SOCIETES.objectifs.",
    retranscrite: true,
  },
  {
    page: "/paiement-formationsociete",
    adresse: `${CDN}/6a38f7c941d311.91779448_Capturedécran2026-06-22à10.51.17.png`,
    contexte:
      "CAPTURE D'ÉCRAN sous le bouton de commande. Texte à retranscrire. Même nom de capture (10.51.17) que le « pourquoi cette formation » de /achat-formationsociete, mais adresse différente : NON VÉRIFIÉ que ce soit la même image.",
  },

  // /achat-formationmicro
  {
    page: "/achat-formationmicro",
    adresse: `${CDN}/6a33fd586856b7.97183294_LOGOEVKHABUSINESSETFORM.png`,
    contexte: "Logo de l'en-tête (commun à tout le site).",
  },
  {
    page: "/achat-formationmicro",
    adresse: `${CDN}/6844d0a794f08_ChatGPTImage8juin202501_48_06.png`,
    contexte: "Logo du second en-tête (menu du téléphone).",
  },
  {
    page: "/achat-formationmicro",
    adresse: `${CDN}/6a394118b209d2.32246115_Capturedécran2026-06-22à11.25.38.png`,
    contexte:
      "CAPTURE D'ÉCRAN, première image de la page. Montre l'ouverture sur fond noir : étiquette « PARCOURS COMPLET », titre, accroche, présentation et cinq pastilles (18h, + 2h en visio, 9 modules, Agent IA inclus, Accès à vie). Rangée dans PAGE_MICRO.ouvertureEnImage.",
    retranscrite: true,
  },
  {
    page: "/achat-formationmicro",
    adresse: `${CDN}/689443222271c_FEEDINSTAGRAMEVKHA-5.png`,
    contexte: "Visuel (format publication Instagram), sous la capture d'ouverture.",
  },
  {
    page: "/achat-formationmicro",
    adresse: `${CDN}/6a38c2f871c369.01464842_Capturedécran2026-06-22à07.06.49.png`,
    contexte:
      "CAPTURE D'ÉCRAN sous « Si vous vous reconnaissez là-dedans, vous êtes au bon endroit ». Montre « Créer sa micro, ce n'est pas juste cliquer sur \"Je m'immatricule\" » : deux colonnes, six pièges classiques de la micro et six bénéfices de la formation. Rangée dans PAGE_MICRO.pourQui (situations et argumentaire). Même fichier (adresse identique) sur /paiement-formationmicro.",
    retranscrite: true,
  },
  {
    page: "/achat-formationmicro",
    adresse: `${CDN}/6a3941bfa04cd4.35985685_Capturedécran2026-06-22à07.00.13.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 1re après le bouton « JE REJOINS LA FORMATION ! ». Montre « À QUI S'ADRESSE CETTE FORMATION — Pour celles et ceux qui veulent démarrer en micro » : quatre cartes de profils. Rangée dans PAGE_MICRO.pourQui.aQui.",
    retranscrite: true,
  },
  {
    page: "/achat-formationmicro",
    adresse: `${CDN}/6a3941d906ee86.15265632_Capturedécran2026-06-22à11.26.14.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 2e après le bouton. Montre « CE QUI EST INCLUS — Une formation pensée pour vous mener jusqu'au lancement » : six cartes. Rangée dans PAGE_MICRO.inclus.",
    retranscrite: true,
  },
  {
    page: "/achat-formationmicro",
    adresse: `${CDN}/6a3941e5955484.58902847_Capturedécran2026-06-22à11.26.00.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 3e après le bouton. Montre « LE + DE CETTE FORMATION — Un accompagnement individuel premium inclus » : le grand « 2H » et cinq points. Mot pour mot le texte déjà relevé sur le tunnel de paiement : rien à ajouter, voir PAGE_MICRO.modalites.coaching.",
    retranscrite: true,
  },
  {
    page: "/achat-formationmicro",
    adresse: `${CDN}/6a3942364bd739.72544747_Capturedécran2026-06-22à16.09.43.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 4e après le bouton. Montre « OBJECTIFS PÉDAGOGIQUES — Ce que vous saurez faire à la fin de la formation » : huit objectifs numérotés 01 à 08, propres à la micro-entreprise (même gabarit que la capture « sociétés », texte différent). Ce ne sont PAS les modules. Rangée dans PAGE_MICRO.objectifs.",
    retranscrite: true,
  },
  {
    page: "/achat-formationmicro",
    adresse:
      "https://d1yei2z3i6k35z.cloudfront.net/9453866/670d706f007bf_LOGOEVKHABUSINESSETFORM.png",
    contexte: "Logo du pied de page.",
  },

  // /paiement-formationmicro
  {
    page: "/paiement-formationmicro",
    adresse: `${CDN}/6a33fd586856b7.97183294_LOGOEVKHABUSINESSETFORM.png`,
    contexte: "Logo de l'en-tête.",
  },
  {
    page: "/paiement-formationmicro",
    adresse: `${CDN}/6a38c19429e730.30741360_Capturedécran2026-06-22à07.00.13.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 1re sous « Plus qu'une étape avant de vous former… ». Texte à retranscrire. Même nom de capture (07.00.13) que le « à qui s'adresse cette formation » de /achat-formationmicro, mais adresse différente : NON VÉRIFIÉ que ce soit la même image.",
  },
  {
    page: "/paiement-formationmicro",
    adresse: `${CDN}/6a38c1a1a9f384.47026769_Capturedécran2026-06-22à07.00.33.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 2e sous le titre, juste avant « Formez-vous avec / Les 9 modules du parcours ». NON LUE. Texte à retranscrire (sur le tunnel « sociétés », la capture à cette place montre les objectifs pédagogiques, pas les modules).",
  },
  {
    page: "/paiement-formationmicro",
    adresse: `${CDN}/6a38c2f871c369.01464842_Capturedécran2026-06-22à07.06.49.png`,
    contexte:
      "CAPTURE D'ÉCRAN sous le bouton de commande. Même fichier (adresse identique) que le « pourquoi cette formation » de /achat-formationmicro : six pièges, six bénéfices. Rangée dans PAGE_MICRO.pourQui.",
    retranscrite: true,
  },

  // /achat-formationpop
  {
    page: "/achat-formationpop",
    adresse: `${CDN}/6844d0a794f08_ChatGPTImage8juin202501_48_06.png`,
    contexte: "Logo de l'en-tête.",
  },
  {
    page: "/achat-formationpop",
    adresse: `${CDN}/685018da16064_PinkandBlackPlayfulProfessionalTrainingVirtualInvitation.png`,
    contexte: "Visuel d'ouverture, au-dessus de « Vous avez l'impression que vos journées vous échappent… ».",
  },
  {
    page: "/achat-formationpop",
    adresse: `${CDN}/6a38503b457875.86933255_Capturedécran2026-06-21à22.54.40.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 1re sous « Si vous vous reconnaissez là-dedans, vous êtes au bon endroit ». Montre deux colonnes sans titre d'ensemble : « Aujourd'hui, vous vivez peut-être ça » (six constats) et « Avec la Méthode P.O.P, vous allez : » (six bénéfices). Rangée dans PAGE_POP.pourQui (situations et argumentaire).",
    retranscrite: true,
  },
  {
    page: "/achat-formationpop",
    adresse: `${CDN}/6a38506ed0b4f7.13064600_Capturedécran2026-06-21à22.55.07.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 2e sous « POURQUOI CETTE FORMATION ? ». Montre « OBJECTIFS PÉDAGOGIQUES — Ce que vous saurez faire à la fin de la formation » : six objectifs numérotés 01 à 06. Rangée dans PAGE_POP.objectifs.",
    retranscrite: true,
  },
  {
    page: "/achat-formationpop",
    adresse: `${CDN}/6a385090047742.84577237_Capturedécran2026-06-21à22.55.18.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 3e sous « POURQUOI CETTE FORMATION ? ». Montre « LE CŒUR DE LA MÉTHODE — P.O.P : trois lettres, un système complet » : trois cartes Planifiez, Organisez, Produisez. Rangée dans PAGE_POP.methode.",
    retranscrite: true,
  },
  {
    page: "/achat-formationpop",
    adresse: `${CDN}/6a3850addbdb57.16350597_Capturedécran2026-06-21à22.56.15.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 4e, juste avant le bouton « JE REJOINS LA MÉTHODE P.O.P ». Montre « CE QUI EST INCLUS — Tout ce dont vous avez besoin pour passer à l'action » : six cartes. Rangée dans PAGE_POP.inclus.",
    retranscrite: true,
  },
  {
    page: "/achat-formationpop",
    adresse:
      "https://d1yei2z3i6k35z.cloudfront.net/9453866/670d706f007bf_LOGOEVKHABUSINESSETFORM.png",
    contexte: "Logo du pied de page.",
  },

  // /paiement-formationpopok
  {
    page: "/paiement-formationpopok",
    adresse: `${CDN}/6a33fd586856b7.97183294_LOGOEVKHABUSINESSETFORM.png`,
    contexte: "Logo de l'en-tête.",
  },
  {
    page: "/paiement-formationpopok",
    adresse: `${CDN}/6a38c0a21ff0f2.54373047_Capturedécran2026-06-22à06.55.43.png`,
    contexte:
      "CAPTURE D'ÉCRAN, 1re sous « Plus qu'une étape avant de structurer votre activité… ». Texte à retranscrire.",
  },
  {
    page: "/paiement-formationpopok",
    adresse: `${CDN}/6a38c0c173bff9.95363183_Capturedécran2026-06-22à06.55.54.png`,
    contexte: "CAPTURE D'ÉCRAN, 2e sous le titre, avant « La Méthode P.O.P ». Texte à retranscrire.",
  },
];

// ── Types partagés ──────────────────────────────────────────────────────────

export type Bouton = {
  libelle: string;
  /** `null` : le bouton du site n'a pas d'adresse (il ouvre un formulaire). */
  lien: string | null;
};

/** Le titre de l'onglet et la méta-description d'une page, TELS QUE RELEVÉS.
 *  `aReecrire` : le relevé est celui d'une AUTRE formation (copié-collé sur le
 *  site), il ne peut pas être repris pour cette page. */
export type Onglet = {
  titre: string;
  description: string;
  aReecrire: boolean;
  remarque?: string;
};

export type Question = { q: string; r: string };

/** La carte d'une formation sur le catalogue. Les trois pages de formation la
 *  relisent : c'est, pour « sociétés » et « micro », presque tout le texte qui
 *  existe hors image. */
export type CarteDeFormation = {
  cle: CleDeFormation;
  titre: string;
  sousTitre?: string;
  prix: string;
  accroche: string;
  mention?: string;
  modalites: string[];
  corps: string[];
  titreDesAcquis: string;
  acquis: string[];
  bouton: Bouton;
};

/** Un intertitre et son paragraphe (carte d'une capture d'écran). */
export type CarteTitreCorps = { titre: string; corps: string };

/** La capture « pourquoi cette formation » : deux colonnes, ce que le lecteur
 *  vit aujourd'hui (croix rouges) et ce que la formation lui apporte (coches).
 *  `surtitre` / `titre` valent `null` quand la capture n'en montre pas. */
export type Argumentaire = {
  surtitre: string | null;
  titre: string | null;
  constat: { titre: string; points: string[] };
  promesse: { titre: string; points: string[] };
};

/** Une capture faite d'un surtitre, d'un titre et d'une grille de cartes
 *  (« ce qui est inclus », « à qui s'adresse cette formation »). */
export type BlocDeCartes = {
  surtitre: string;
  titre: string;
  corps?: string;
  cartes: CarteTitreCorps[];
};

/** La capture « objectifs pédagogiques » : le rang dans `liste` est le numéro
 *  affiché (01, 02…). Ce sont des OBJECTIFS, pas les modules du programme. */
export type ObjectifsPedagogiques = {
  surtitre: string;
  titre: string;
  liste: string[];
};

/** L'ouverture telle que la capture d'écran la montre, en tête d'une page
 *  d'achat. `pastilles` : les étiquettes arrondies sous la présentation.
 *  `PAGE_SOCIETES.ouvertureEnImage` a cette forme, plus deux champs à elle. */
export type OuvertureEnImage = {
  etiquette: string;
  titre: string;
  accroche: string;
  corps: string;
  pastilles: string[];
};

/** Mention commune aux trois captures « ce qui est inclus ».
 *
 *  À FAIRE CONFIRMER AVANT AFFICHAGE : « Qualiopi » est une certification
 *  réglementée. Aucun texte relevé du site (pages légales comprises) ne dit
 *  qu'EVKHA la détient ; seules ces trois images emploient le mot. */
const ATTESTATION_QUALIOPI = "Attestation Qualiopi";

// ── Ce que les trois formations ont en commun ───────────────────────────────

/** Bloc « NOS FORMATIONS ONT : » de `/formation` : la méthode, les outils
 *  fournis, l'accès à vie. Dans le relevé, le titre et le texte de chaque
 *  point tiennent sur une seule ligne ; ils sont séparés ici.
 *
 *  ATTENTION, CONTRADICTION À FAIRE TRANCHER : « Un accès à vie » ici (et
 *  « illimité dans le temps » dans les questions), mais les CGV du même site,
 *  article 4, disent : « Les formations en ligne sont accessibles pendant
 *  toute leur période de commercialisation active. » */
export const ATOUTS_DES_FORMATIONS = {
  titre: "NOS FORMATIONS ONT :",
  methode: {
    titre: "Une méthode éprouvée, pas du contenu générique",
    corps:
      "Nos formations s'appuient sur la méthodologie propriétaire EVKHA qui couvre toutes les étapes : validation d'idée, positionnement, statut juridique, prévisionnel financier, stratégie commerciale, communication. RIEN N'EST LAISSÉ AU HASARD.",
  },
  outils: {
    titre: "Des outils opérationnels prêts à l'emploi",
    corps:
      "Templates, checklists, modèles de business plan, calculateurs, scripts de prospection. Vous ne repartez pas avec des théories : vous repartez avec une vraie boîte à outils que vous utiliserez dès le lendemain.",
  },
  acces: {
    titre: "Un accès à vie",
    corps:
      "Vous avancez à votre rythme. Vous revenez sur les modules autant que vous le souhaitez. Vous bénéficiez des mises à jour. La formation grandit avec votre projet, et reste votre référence dans la durée.",
  },
};

/** Les formations en présentiel (bloc de `/formation`), avec la fenêtre
 *  d'inscription aux prochaines dates qu'ouvre son bouton. */
export const PRESENTIEL = {
  surtitre: "VOUS PRÉFÉREZ L'HUMAIN ?",
  titre: "Nos formations en présentiel",
  corps:
    "Pour celles et ceux qui apprennent mieux en groupe, en interaction directe, avec un cadre, un rythme et un accompagnement sur place.",
  lieux: "Sessions limitées en effectif sur LILLE ou PARIS",
  points: [
    "Sessions à dates fixes sur deux jours ou une journée (POP), en petit groupe",
    "Cadre, rythme et ambiance d'apprentissage",
    "Échanges et mises en pratique sur place",
    ORGANISME_DE_FORMATION.financement.presentiel,
  ],
  bouton: {
    libelle: "Je veux être informé(e) des prochaines sessions !",
    lien: LIENS_FORMATIONS.sessionsEnPresentiel,
  } as Bouton,
  /** La fenêtre surgissante : une inscription par e-mail. */
  inscription: {
    titre:
      "INSCRIVEZ-VOUS GRATUITEMENT POUR RECEVOIR NOS PROCHAINES DATES EN PRESENTIEL",
    rassurance: "Je HAIS le spam. Votre email ne sera jamais partagée.",
    consentement:
      "En souscrivant, vous acceptez de recevoir des emails et informations de EVKHA.",
  },
};

/** Les cinq questions de `/formation`. Les pages de formation n'ont pas de
 *  questions propres : elles reprennent celles-ci.
 *
 *  À FAIRE TRANCHER :
 *   - « Chaque formation inclut un accès à un assistant IA » — mais seule la
 *     carte P.O.P l'annonce, et la parenthèse parle d'« organisation et
 *     productivité », le sujet de la P.O.P ;
 *   - la dernière réponse promet « une solution adaptée », quand les CGV
 *     écrivent que les formations en ligne « ne sont ni échangeables ni
 *     remboursables ». */
export const QUESTIONS_DES_FORMATIONS = {
  surtitre: "QUESTIONS FRÉQUENTES",
  titre: "On répond à vos questions",
  liste: [
    {
      q: "Quelle formation choisir si je débute totalement ?",
      r: "Si vous savez déjà que vous voulez démarrer en micro ou en société, vous pouvez aller directement sur le parcours complet correspondant. Sinon n'hésitez pas à nous contacter pour que je vous oriente sur la formation la plus adaptée.",
    },
    {
      q: "Pendant combien de temps ai-je accès à la formation ?",
      r: "L'accès à la plateforme est illimité dans le temps. Vous pouvez revenir sur les modules, les exercices et les bonus aussi souvent que vous le souhaitez.",
    },
    {
      q: "Comment fonctionne l'assistant IA ?",
      r: "Chaque formation inclut un accès à un assistant IA spécialisé, formé sur la méthode EVKHA (organisation et productivité). Laissez-le vous guider et recevez vos recommandations personnalisées.",
    },
    {
      q: ORGANISME_DE_FORMATION.financement.question,
      r: ORGANISME_DE_FORMATION.financement.reponse,
    },
    {
      q: "Et si la formation ne me convient pas ?",
      r: "Nous tenons à ce que chaque participant soit satisfait. Contactez-nous par mail pour échanger sur votre situation, nous trouverons une solution adaptée.",
    },
  ] as Question[],
};

/** Le bloc « POURQUOI CETTE FORMATION ? », identique sur les trois pages
 *  `/achat-formation*`. Ce qui suit ces deux lignes sur le site est une
 *  capture d'écran PROPRE À CHAQUE FORMATION : les situations ne sont donc pas
 *  ici, mais dans `pourQui.situations` de chaque page (retranscrites le
 *  19/11/2026). */
export const POURQUOI_CETTE_FORMATION = {
  surtitre: "POURQUOI CETTE FORMATION ?",
  titre: "Si vous vous reconnaissez là-dedans, vous êtes au bon endroit",
};

/** Ce que les trois tunnels de paiement écrivent autour du bouton de
 *  commande : les conditions de vente telles que la cliente les fait accepter.
 *  Le paiement lui-même sera celui de la plateforme. */
export const COMMANDE_D_UNE_FORMATION = {
  codeDeReduction: "Ajout d'un code de réduction sur la page suivante",
  acceptationDesConditions:
    "Oui, je certifie accepter les Conditions générales de vente et d'utilisation",
  consentementAuxCourriels:
    "Oui, je consens à recevoir des emails et newsletter d'EVKHA.fr",
};

/** L'onglet des trois tunnels de paiement, relevé à l'identique sur les
 *  trois — y compris sur ceux des formations « sociétés » et « micro », où il
 *  est faux. Conservé pour mémoire ; le paiement de la plateforme a ses
 *  propres titres. */
export const ONGLET_DES_TUNNELS_DE_PAIEMENT: Onglet = {
  titre: "PAGE DE PAIEMENT METHODE POP BOOSTÉE IA",
  description:
    "Vous êtes à un clic de transformer votre business! Finalisez votre inscription à la formation la METHODE pop boostée à l'ia et obtenez un accès immédiat et illimité à tous les modules. vous allez vous organisez, planifier et produire un max!",
  aReecrire: true,
  remarque:
    "Titre et description identiques sur les trois tunnels ; ils ne décrivent que la Méthode P.O.P. Non corrigés : à ne pas reprendre.",
};

/** L'onglet relevé sur les trois pages `/achat-formation*`. Il n'est juste
 *  que pour la Méthode P.O.P. */
const ONGLET_RELEVE_SUR_LES_PAGES_D_ACHAT = {
  titre:
    "Formation Méthode P.O.P Boostée à l’IA – Organise ton business comme une pro",
  description:
    "Structure ton business avec la méthode P.O.P : planification, outils, IA, automatisation. Formation actionnable, rapide, sans blabla.",
};

// ── Les trois cartes du catalogue ───────────────────────────────────────────

/** La présentation de chaque formation, écrite à l'identique sur la carte du
 *  catalogue et dans la capture d'ouverture de sa page d'achat (pour la
 *  micro-entreprise, la capture enchaîne les deux phrases en un paragraphe). */
const PRESENTATION_SOCIETES =
  "Le parcours premium pour celles et ceux qui veulent créer une vraie société ou passer un cap. Choix du statut, prévisionnel financier complet, business plan crédible, immatriculation, protection INPI, stratégie commerciale : tout est traité avec la profondeur exigée par un projet ambitieux.";
const PRESENTATION_MICRO =
  "Le parcours complet pour lancer sereinement votre micro-entreprise : comprendre le régime, valider votre idée, construire votre prévisionnel, vous immatriculer et trouver vos premiers clients.";
const PRESENTATION_MICRO_SUITE =
  "Avec un accompagnement individuel premium pour passer à l'action.";
const ACCROCHE_MICRO =
  "De l'idée à votre première facture, sans rien laisser au hasard.";

export const CARTE_SOCIETES: CarteDeFormation = {
  cle: "societes",
  titre: "Créer son entreprise de A à Z",
  prix: prixAffiche("societes"),
  accroche:
    "EI, EURL, SARL, SASU, SAS = la formation qui couvre tous les statuts hors micro.",
  mention: "Formation complète avec outils personnalisables",
  modalites: [
    `Format : 100 % en ligne ${DUREES_SOCIETES.heuresEnLigne} HEURES À VOTRE RYTHME`,
    `${DUREES_SOCIETES.heuresDeCoaching} HEURES D'accompagnements individuels pour travailler sur VOTRE projet.`,
  ],
  corps: [PRESENTATION_SOCIETES],
  titreDesAcquis: "Ce que vous allez maîtriser :",
  acquis: [
    "Choisir entre EI, EURL, SARL, SASU, SAS en connaissance de cause",
    "Construire une étude de marché, documents administratifs et comptables, business plan bancable, prévisionnel financier…",
    "Arbitrer entre IR / IS et entre TNS / assimilé salarié",
    "Immatriculer votre société, protéger votre marque à l'INPI",
    "Identifier les aides (ACRE, ARCE, BPI, prêts d'honneur…)",
  ],
  bouton: {
    libelle: "Je découvre la formation\u00a0→",
    lien: LIENS_FORMATIONS.decouvrirSocietes,
  },
};

/** Sur le site, cette carte n'a NI ligne de format NI durée : `modalites` est
 *  vide parce que la page n'en dit rien, pas par oubli. */
export const CARTE_MICRO: CarteDeFormation = {
  cle: "micro",
  titre: "Créer sa micro-entreprise de A à Z",
  prix: prixAffiche("micro"),
  accroche: ACCROCHE_MICRO,
  mention: "Formation complète avec outils",
  modalites: [],
  corps: [PRESENTATION_MICRO, PRESENTATION_MICRO_SUITE],
  titreDesAcquis: "Ce que vous allez maîtriser :",
  acquis: [
    "Comprendre le régime micro-entrepreneur (juridique, fiscal et social)",
    "Construire son projet étape par étape (Étude de marché, business plan, prévisionnel, KPI)",
    "Réaliser les démarches administratives (Guichet unique, formalités INPI, protection.)",
    "Organiser et gérer son activité (cible, gestion, obligations du micro-entrepreneur, posture de dirigeant)",
    "Développer son activité dans la durée (Stratégies, évolution, vision.)",
  ],
  bouton: {
    libelle: "Je découvre la formation\u00a0→",
    lien: LIENS_FORMATIONS.decouvrirMicro,
  },
};

export const CARTE_POP: CarteDeFormation = {
  cle: "pop",
  titre: "Formation P.O.P",
  sousTitre: "Gestion-Productivité",
  prix: prixAffiche("pop"),
  accroche: "Planifiez. Organisez. Produisez !",
  modalites: [
    `Durée : ${DUREES_POP.heuresEnLigne}h 00`,
    "Format : 100 % en ligne et flexible",
    "Un assistant IA P.O.P dédié",
  ],
  corps: [
    "La méthode pour structurer votre activité, reprendre le contrôle de votre temps et gagner en rentabilité. Pour les entrepreneurs qui veulent arrêter de courir après leurs journées et passer enfin à un pilotage clair, simple et durable.",
  ],
  titreDesAcquis: "Ce que vous allez maîtriser :",
  acquis: [
    "La méthode P.O.P appliquée à votre activité réelle",
    "Organiser et atteindre vos objectifs professionnels",
    "Définir des objectifs alignés avec vos vraies priorités",
    "Les outils IA et d'automatisation pour gagner du temps",
    "Réduire votre charge mentale et augmenter vos résultats",
    "Gérer votre temps sans stress, avec plus de clarté",
    "Un système de pilotage avec KPI simples et exploitables.",
  ],
  bouton: {
    libelle: "Je découvre la Méthode P.O.P\u00a0→",
    lien: LIENS_FORMATIONS.decouvrirPop,
  },
};

// ── Page 1 : le catalogue des formations (`/formation`) ─────────────────────

export const PAGE_CATALOGUE = {
  onglet: {
    titre:
      "Formations en création d’entreprise & gestion productivité – EVKHA",
    description:
      "Des formations concrètes pour créer, structurer et booster son entreprise. Méthode P.O.P, micro-entreprise – 100 % action.",
    aReecrire: false,
  } as Onglet,

  ouverture: {
    surtitre: "Formations en création d’entreprise :",
    titre: "De l’idée au succès !",
    corps:
      "Apprenez à élaborer un business plan solide, à gérer l’administratif et à optimiser votre stratégie de développement. Nos programmes vous offrent les compétences clés pour piloter efficacement votre projet.",
    preuve: "Plus de 500 entrepreneurs formés et accompagnés avec succès",
  },

  /** « Plus de 15 ans » ici ; l'accueil du même site écrit « 16 ans », et le
   *  tunnel de la P.O.P « 15 ans d'expérience ». Non tranché par la cliente
   *  (point 4 des questions ouvertes du plan de refonte). */
  pourquoi: {
    titre: "Pourquoi choisir nos formations ?",
    paragraphes: [
      "Parce que créer une entreprise, ça ne s'apprend pas dans un PDF. Ça se construit avec une méthode, des outils, de l'expérience terrain et quelqu'un qui sait où il met les pieds.",
      "Depuis plus de 15 ans, j'accompagne des créateurs d'entreprise. J'ai formé plus de 500 entrepreneurs, suivi de nombreuses formations et certifications et ainsi j'ai pu accompagner des dizaines de projets de l'idée au lancement.",
      "Je sais clairement ce qui fait passer de l'envie à l'action.",
      "C'est tout ce vécu qui est condensé dans nos formations en ligne.",
    ],
    atouts: ATOUTS_DES_FORMATIONS,
  },

  formations: {
    titre: "Accédez aux Formations Complètes dès Maintenant",
    cartes: [CARTE_SOCIETES, CARTE_MICRO, CARTE_POP],
  },

  presentiel: PRESENTIEL,

  /** Cinq profils, dans l'ordre de la page. Quatre illustrations seulement
   *  (voir `IMAGES_FORMATIONS_A_RAPATRIER`) : « Entrepreneurs » n'en a pas. */
  pourQui: {
    titre: "À qui ça s'adresse ?",
    profils: [
      "Porteurs de projet",
      "En reconversion PRO",
      "Freelances",
      "Demandeurs d'emploi",
      "Entrepreneurs",
    ],
  },

  financement: ORGANISME_DE_FORMATION,

  questions: QUESTIONS_DES_FORMATIONS,

  /** Neuf avis, tous en IMAGE sur le site (`avis01` à `avis09`). Leur texte
   *  est déjà retranscrit mot pour mot dans `contenuAccueil.AVIS`. */
  avis: {
    surtitre: "Témoignages",
    titre: "Nos avis clients",
  },
};

// ── Page 2 : « Créer son entreprise de A à Z » (sociétés) ───────────────────

/** La capture « pourquoi cette formation » de `/achat-formationsociete`, mot
 *  pour mot. « 1500 € » est le coût d'un expert-comptable cité en exemple, pas
 *  un prix d'offre : il n'a pas sa place dans `TARIFS_FORMATIONS`. */
const ARGUMENTAIRE_SOCIETES: Argumentaire = {
  surtitre: "POURQUOI CETTE FORMATION",
  titre: "Créer une vraie société, ça ne s'improvise pas",
  constat: {
    titre: "Les vraies difficultés du hors micro",
    points: [
      "Vous hésitez entre EI, EURL, SARL, SASU, SAS sans savoir vraiment trancher",
      "Vous ne maîtrisez pas les arbitrages IR/IS et leurs conséquences réelles",
      "Vous ne savez pas comment vous rémunérer ni à quel niveau de charges sociales",
      "Vous craignez de présenter un prévisionnel financier qui ne tient pas la route devant un banquier",
      "Vous payez 1500\u00a0€ à un expert-comptable juste pour rédiger vos statuts",
      "Vous ne savez pas quelles aides mobiliser (ACRE, ARCE, BPI, prêts d'honneur…)",
    ],
  },
  promesse: {
    titre: "Avec cette formation, vous allez :",
    points: [
      "Comparer les 5 statuts en connaissance de cause grâce à des cas pratiques",
      "Arbitrer IR/IS et TNS/assimilé salarié selon votre stratégie",
      "Construire un business plan bancable et un prévisionnel financier complet",
      "Maîtriser amortissements, BFR, plan de trésorerie mensuel, seuil de rentabilité",
      "Immatriculer en autonomie et protéger votre marque à l'INPI",
      "Identifier toutes les aides à la création disponibles selon votre profil",
    ],
  },
};

/** Sources : la carte du catalogue, `/achat-formationsociete` (deux lignes de
 *  texte et six captures d'écran, retranscrites le 19/11/2026) et
 *  `/paiement-formationsociete`. */
export const PAGE_SOCIETES = {
  onglet: {
    ...ONGLET_RELEVE_SUR_LES_PAGES_D_ACHAT,
    aReecrire: true,
    remarque:
      "Relevé sur /achat-formationsociete : c'est le titre de la Méthode P.O.P, copié tel quel. La page n'a ni titre ni description à elle.",
  } as Onglet,

  /** La carte du catalogue : titre, prix, accroche, présentation, acquis. */
  ouverture: CARTE_SOCIETES,

  /** L'ouverture telle que la page d'achat la montre (1re capture). L'accroche
   *  diffère de celle du catalogue (« = la formation qui couvre tous les
   *  statuts hors micro »).
   *
   *  CONTRADICTION NON TRANCHÉE : la capture porte une quatrième pastille,
   *  « 9 modules ». Le tunnel de paiement écrit « Les 10 modules du parcours »
   *  (`NOMBRE_DE_MODULES.societes`). Elle est tenue HORS de `pastilles` pour
   *  qu'aucune page n'affiche un nombre que la cliente n'a pas confirmé. */
  ouvertureEnImage: {
    etiquette: "PARCOURS PREMIUM",
    titre: CARTE_SOCIETES.titre,
    accroche: "EI, EURL, SARL, SASU, SAS — tout sauf la micro.",
    corps: PRESENTATION_SOCIETES,
    /** Les cinq pastilles dorées, entre la présentation et les durées. */
    statuts: ["EI", "EURL", "SARL", "SASU", "SAS"],
    pastilles: [
      `${DUREES_SOCIETES.heuresEnLigne}h de formation`,
      `+ ${DUREES_SOCIETES.heuresDeCoaching}h accompagnement`,
      "Outils financiers avancés",
    ],
    /** Placée, dans la capture, entre « + 2h accompagnement » et « Outils
     *  financiers avancés ». */
    pastilleContredite: {
      texteDeLaCapture: "9 modules",
      nombreLu: 9,
      nombreDeLaConstante: NOMBRE_DE_MODULES.societes,
    },
  },

  /** Les deux lignes de texte de la page, puis sa capture (2e de la page) :
   *  `situations` est la colonne des difficultés, celle où le lecteur « se
   *  reconnaît » ; `argumentaire` porte la capture entière. */
  pourQui: {
    ...POURQUOI_CETTE_FORMATION,
    situations: ARGUMENTAIRE_SOCIETES.constat.points,
    argumentaire: ARGUMENTAIRE_SOCIETES,
    /** Les quatre profils : capture du TUNNEL DE PAIEMENT
     *  (`/paiement-formationsociete`), lue le 19/11/2026 — elle ne figure pas
     *  sur la page d'achat. Même gabarit que `PAGE_MICRO.pourQui.aQui`. */
    aQui: {
      surtitre: "À QUI S'ADRESSE CETTE FORMATION",
      titre: "Pour les porteurs de projet qui veulent voir grand",
      corps:
        "Si vous visez une vraie société, une protection patrimoniale solide ou des associés, cette formation est pensée pour vous.",
      cartes: [
        {
          titre: "Porteurs de projet ambitieux",
          corps:
            "Vous visez un statut sociétal d'emblée pour un projet structurant.",
        },
        {
          titre: "Créateurs d'entreprise",
          corps:
            "Vous voulez créer une SASU, EURL, SARL ou SAS, seul ou à plusieurs.",
        },
        {
          titre: "Salariés en reconversion",
          corps:
            "Vous quittez le salariat pour un projet qui nécessite un cadre solide.",
        },
        {
          titre: "Micro-entrepreneurs en évolution",
          corps:
            "Vous voulez passer de la micro à une structure plus solide et fiscalement optimisée.",
        },
      ],
    } satisfies BlocDeCartes,
  },

  /** Le tunnel annonce le nombre de modules et ce que chacun combine. Leurs
   *  INTITULÉS ne figurent dans AUCUNE des six captures de la page d'achat
   *  (lues le 19/11/2026) : la capture placée avant ce titre sur le tunnel
   *  montre les objectifs pédagogiques (`objectifs`), pas les modules.
   *  `modules` reste VIDE — ne pas les déduire des acquis ni des objectifs. */
  programme: {
    surtitre: "Formez-vous avec",
    titre: `Les ${NOMBRE_DE_MODULES.societes} modules du parcours`,
    corps: [
      "Un parcours progressif, du diagnostic de votre projet à votre stratégie commerciale.",
      "Chaque module combine vidéos, quiz, études de cas, outils, IA et fichiers téléchargeables.",
    ],
    modules: [] as string[],
  },

  /** Les cinq formes juridiques : bloc propre à cette formation. `surtitre`,
   *  `titre` et `corps` viennent du texte du tunnel de paiement ; `formes` et
   *  `phraseDeLaCapture` de la 3e capture de la page d'achat.
   *
   *  DEUX ÉCARTS, non tranchés :
   *   - la capture écrit « tableau CMA », le tunnel « tableau comparatif »
   *     (même phrase par ailleurs) ; son surtitre s'arrête à « TOUS LES
   *     STATUTS HORS MICRO », sans « sont étudiés » ;
   *   - le titre annonce 5 formes, la capture montre QUATRE cartes : SASU et
   *     SAS partagent la dernière. */
  statuts: {
    surtitre: "TOUS LES STATUTS HORS MICRO sont étudiés",
    titre: "5 formes juridiques, expliquées et comparées",
    corps: [
      "Le parcours premium pour celles et ceux qui veulent créer une vraie société ou passer un cap: Choix du statut, prévisionnel financier complet, business plan crédible, immatriculation, protection INPI, stratégie commerciale : tout est traité avec la profondeur exigée par un projet ambitieux.",
      "Vous apprenez à choisir en connaissance de cause, avec un panorama complet basé sur le tableau comparatif et des cas pratiques concrets.",
    ],
    phraseDeLaCapture:
      "Vous apprenez à choisir en connaissance de cause, avec un panorama complet basé sur le tableau CMA et des cas pratiques concrets.",
    formes: [
      {
        sigle: "EI",
        nom: "ENTREPRISE INDIVIDUELLE",
        points: [
          "Séparation patrimoine pro / perso depuis 2022",
          "IR par défaut, option IS possible",
          "Dirigeant TNS",
          "Très simple à gérer",
        ],
      },
      {
        sigle: "EURL",
        nom: "ENTREPRISE UNIPERSONNELLE À RESP. LIMITÉE",
        points: [
          "Un seul associé",
          "Capital libre",
          "IR ou IS au choix",
          "Gérant TNS si associé unique",
        ],
      },
      {
        sigle: "SARL",
        nom: "SOCIÉTÉ À RESPONSABILITÉ LIMITÉE",
        points: [
          "2 à 100 associés",
          "Fonctionnement formalisé",
          "IS (option IR limitée)",
          "Gérant TNS ou assimilé selon majorité",
        ],
      },
      {
        sigle: "SASU / SAS",
        nom: "SOCIÉTÉ PAR ACTIONS SIMPLIFIÉE",
        points: [
          "Liberté statutaire maximale",
          "Capital libre",
          "IS (option IR temporaire)",
          "Président = assimilé salarié",
        ],
      },
    ] as { sigle: string; nom: string; points: string[] }[],
  },

  /** 4e capture de la page d'achat : six cartes. La dernière carte est à
   *  faire confirmer (voir `ATTESTATION_QUALIOPI`). */
  inclus: {
    surtitre: "CE QUI EST INCLUS",
    titre: "Tout ce qu'il faut pour créer et piloter votre société",
    cartes: [
      {
        titre: `${DUREES_SOCIETES.heuresEnLigne}h de formation digitale`,
        corps:
          "Vidéos courtes, slides pédagogiques, exercices et activités guidées, accessibles 24h/24.",
      },
      {
        titre: `${DUREES_SOCIETES.heuresDeCoaching}h d'accompagnement premium`,
        corps:
          "Coaching individuel en visio : analyse projet, lecture business plan, conseils statutaires, plan d'action.",
      },
      {
        titre: "Modules IA intégrés",
        corps:
          "Analyse de marché, business plan, pitch, stratégie digitale : l'IA appliquée à chaque étape.",
      },
      {
        titre: "Outils financiers avancés",
        corps:
          "Plan de financement, compte de résultat, trésorerie mensuelle, BFR, seuil de rentabilité.",
      },
      {
        titre: "Modèles juridiques",
        corps:
          "Statuts simplifiés EURL/SASU, modèle de dépôt INPI, CGV, charte RGPD, contrats.",
      },
      {
        titre: ATTESTATION_QUALIOPI,
        corps:
          "Quiz, traçabilité complète, attestations générées automatiquement, suivi formateur sous 24-48h.",
      },
    ],
  } satisfies BlocDeCartes,

  modalites: {
    format: CARTE_SOCIETES.modalites,
    /** `surtitre`, `titre`, `corps` : le texte du tunnel de paiement.
     *  `captureDAchat` et `points` : la 5e capture de la page d'achat, qui
     *  titre autrement le même bloc et, elle, détaille les séances. La
     *  capture ne redit pas « 2 séances d'1 heure ». */
    coaching: {
      surtitre: "LE + DE CETTE FORMATION",
      titre: "Un accompagnement individuel premium inclus",
      corps: [
        "Ce qui distingue cette formation des autres :",
        "un vrai temps de coaching humain, en visio, pour ancrer la méthode sur votre projet réel.",
        `${DUREES_SOCIETES.heuresDeCoaching}H D'accompagnement individuel en visio, réparties en ${DUREES_SOCIETES.seancesDeCoaching} séances d'${DUREES_SOCIETES.heuresParSeance} heure.`,
      ],
      captureDAchat: {
        surtitre: "ACCOMPAGNEMENT INDIVIDUEL PREMIUM",
        titre: "Un coaching humain, sur votre projet réel",
        introduction:
          "Au-delà du contenu, ce qui fait la différence : un temps de coaching personnalisé pour ancrer la méthode sur votre projet, votre statut, vos chiffres.",
        /** Le grand « 2H » doré et la phrase qu'il commence. */
        corps: `${DUREES_SOCIETES.heuresDeCoaching}H D'accompagnement individuel premium en visio. Pour transformer votre projet en plan d'action solide, avec quelqu'un qui sait où il met les pieds.`,
      },
      /** Les cinq points de la capture (le début de chacun y est en gras). */
      points: [
        "Analyse de votre projet et de sa cohérence stratégique",
        "Lecture de votre business plan et conseils ciblés",
        "Conseils statutaires selon votre activité et vos ambitions",
        "Validation du prévisionnel et arbitrages financiers",
        "Plan d'action personnalisé pour passer à l'immatriculation",
      ],
    },
  },

  /** 6e capture de la page d'achat (la même figure sur le tunnel de
   *  paiement) : huit objectifs. */
  objectifs: {
    surtitre: "OBJECTIFS PÉDAGOGIQUES",
    titre: "Ce que vous saurez faire à la fin de la formation",
    liste: [
      "Comprendre les différences entre EI, EURL, SARL, SASU, SAS et choisir la structure adaptée",
      "Réaliser une étude de marché complète et construire votre analyse SWOT",
      "Élaborer un business plan structuré, crédible et bancable",
      "Construire un prévisionnel financier complet : investissements, amortissements, charges, CA, seuil de rentabilité, trésorerie",
      "Immatriculer votre société en ligne et maîtriser statuts, pactes, annonces légales et dépôt INPI",
      "Identifier vos obligations sociales, fiscales et juridiques selon votre statut",
      "Construire votre stratégie commerciale, de communication et votre plan d'action 30/60/90 jours",
      "Utiliser l'IA pour générer analyses, pitch, messages commerciaux et simplifier les tâches",
    ],
  } satisfies ObjectifsPedagogiques,

  outils: ATOUTS_DES_FORMATIONS,

  financement: ORGANISME_DE_FORMATION,

  presentiel: PRESENTIEL,

  questions: QUESTIONS_DES_FORMATIONS,

  appelFinal: {
    /** Bouton de `/achat-formationsociete`, vers le tunnel. */
    bouton: {
      libelle: "JE REJOINS LA FORMATION !",
      lien: LIENS_FORMATIONS.paiementSocietes,
    } as Bouton,
  },

  commande: {
    titre:
      "Plus qu'une étape avant de vous former parfaitement pour créer votre Entreprise !",
    ...COMMANDE_D_UNE_FORMATION,
    bouton: "Je choisis la formation \"Créer son entreprise\"",
  },
};

// ── Page 3 : « Créer sa micro-entreprise de A à Z » ─────────────────────────

/** La capture « pourquoi cette formation » de `/achat-formationmicro`, mot
 *  pour mot. */
const ARGUMENTAIRE_MICRO: Argumentaire = {
  surtitre: "POURQUOI CETTE FORMATION",
  titre: "Créer sa micro, ce n'est pas juste cliquer sur \"Je m'immatricule\"",
  constat: {
    titre: "Les pièges classiques de la micro",
    points: [
      "Vous vous perdez entre les sites officiels, les forums et les conseils contradictoires",
      "Vous ne savez pas si la micro est vraiment le bon statut pour vous",
      "Vous craignez de mal déclarer votre chiffre d'affaires et vos cotisations",
      "Vous ne savez pas comment fixer vos prix sans vous brader",
      "Vous repoussez votre lancement parce que tout vous semble flou",
      "Vous n'avez personne pour vous dire si votre projet tient la route",
    ],
  },
  promesse: {
    titre: "Avec cette formation, vous allez :",
    points: [
      "Comprendre le régime micro de A à Z, sans jargon",
      "Valider votre idée avec une vraie étude de marché",
      "Construire un prévisionnel financier réaliste",
      "Maîtriser vos obligations fiscales et sociales",
      "Vous immatriculer en toute autonomie",
      `Bénéficier d'un accompagnement humain individuel de ${DUREES_MICRO.heuresDeCoaching}h`,
    ],
  },
};

/** Sources : la carte du catalogue, `/achat-formationmicro` (deux lignes de
 *  texte et six captures d'écran, retranscrites le 19/11/2026) et
 *  `/paiement-formationmicro`. */
export const PAGE_MICRO = {
  onglet: {
    ...ONGLET_RELEVE_SUR_LES_PAGES_D_ACHAT,
    aReecrire: true,
    remarque:
      "Relevé sur /achat-formationmicro : c'est le titre de la Méthode P.O.P, copié tel quel. La page n'a ni titre ni description à elle.",
  } as Onglet,

  /** La carte du catalogue. */
  ouverture: CARTE_MICRO,

  /** L'ouverture telle que la page d'achat la montre (1re capture). Titre,
   *  accroche et présentation sont ceux de la carte du catalogue ; la capture
   *  y ajoute l'étiquette et cinq pastilles. « 9 modules » y est conforme à
   *  `NOMBRE_DE_MODULES.micro`. */
  ouvertureEnImage: {
    etiquette: "PARCOURS COMPLET",
    titre: CARTE_MICRO.titre,
    accroche: ACCROCHE_MICRO,
    corps: `${PRESENTATION_MICRO} ${PRESENTATION_MICRO_SUITE}`,
    pastilles: [
      `${DUREES_MICRO.heuresEnLigne}h de formation`,
      `+ ${DUREES_MICRO.heuresDeCoaching}h en visio`,
      `${NOMBRE_DE_MODULES.micro} modules`,
      "Agent IA inclus",
      "Accès à vie",
    ],
  } satisfies OuvertureEnImage,

  /** Les deux lignes de texte de la page, puis ses captures : `situations`
   *  est la colonne des pièges (2e capture), `argumentaire` la capture
   *  entière, `aQui` les quatre profils (3e capture). */
  pourQui: {
    ...POURQUOI_CETTE_FORMATION,
    situations: ARGUMENTAIRE_MICRO.constat.points,
    argumentaire: ARGUMENTAIRE_MICRO,
    aQui: {
      surtitre: "À QUI S'ADRESSE CETTE FORMATION",
      titre: "Pour celles et ceux qui veulent démarrer en micro",
      corps:
        "Une formation pensée pour tous les profils qui veulent lancer leur activité sous le régime de la micro-entreprise, avec ou sans expérience préalable.",
      cartes: [
        {
          titre: "Porteurs de projet",
          corps:
            "Vous avez une idée et voulez la concrétiser sans vous tromper sur les fondamentaux.",
        },
        {
          titre: "Salariés en reconversion",
          corps:
            "Vous quittez le salariat et voulez démarrer votre activité en toute sérénité.",
        },
        {
          titre: "Demandeurs d'emploi",
          corps:
            "Vous voulez créer votre activité en mobilisant les aides disponibles (ACRE, ARE…).",
        },
        {
          titre: "Futurs créateurs",
          corps:
            "Vous voulez tester un projet en activité secondaire avant un engagement total.",
        },
      ],
    } satisfies BlocDeCartes,
  },

  /** Même remarque que pour les sociétés : le nombre est écrit (tunnel et
   *  capture d'ouverture), mais les INTITULÉS des modules ne figurent dans
   *  AUCUNE des six captures de la page d'achat. `modules` reste VIDE. Les
   *  deux phrases d'introduction sont IDENTIQUES à celles du tunnel
   *  « sociétés », y compris « à votre stratégie commerciale ». */
  programme: {
    surtitre: "Formez-vous avec",
    titre: `Les ${NOMBRE_DE_MODULES.micro} modules du parcours`,
    corps: [
      "Un parcours progressif, du diagnostic de votre projet à votre stratégie commerciale.",
      "Chaque module combine vidéos, quiz, études de cas, outils, IA et fichiers téléchargeables.",
    ],
    modules: [] as string[],
  },

  /** 4e capture de la page d'achat : six cartes.
   *
   *  À RELIRE AVANT AFFICHAGE, trois mentions qui décrivent l'ANCIEN site :
   *  « (Canva) », « traçabilité complète Systeme.io », et la carte
   *  « Attestation Qualiopi » (voir `ATTESTATION_QUALIOPI`). Retranscrites
   *  telles quelles ; la plateforme n'est plus Systeme.io. */
  inclus: {
    surtitre: "CE QUI EST INCLUS",
    titre: "Une formation pensée pour vous mener jusqu'au lancement",
    cartes: [
      {
        titre: `${DUREES_MICRO.heuresEnLigne}h de formation digitale`,
        corps:
          "Vidéos courtes (Canva), slides pédagogiques, accessibles 24h/24 depuis ordinateur ou tablette.",
      },
      {
        titre: `${DUREES_MICRO.heuresDeCoaching}h d'accompagnement visio`,
        corps: `Coaching individuel en ${DUREES_MICRO.seancesDeCoaching} séances d'${DUREES_MICRO.heuresParSeance}h : analyse projet, prévisionnel, plan d'action.`,
      },
      {
        titre: "Modules IA intégrés",
        corps:
          "Analyse de marché, pitch client, stratégie réseaux sociaux, prévisionnel auto.",
      },
      {
        titre: "Fichiers téléchargeables",
        corps:
          "Checklists, modèles, fiches pratiques, templates : tout votre kit créateur.",
      },
      {
        titre: "Quiz et études de cas",
        corps:
          "Quiz interactifs auto-correctifs à chaque module, études de cas concrètes, évaluation finale.",
      },
      {
        titre: ATTESTATION_QUALIOPI,
        corps:
          "Attestation de réalisation automatisée, traçabilité complète Systeme.io, suivi formateur sous 24-48h.",
      },
    ],
  } satisfies BlocDeCartes,

  modalites: {
    /** Vide : la CARTE du catalogue n'a ni ligne de format ni durée. Les
     *  durées de cette formation sont écrites dans `ouvertureEnImage.pastilles`
     *  et dans `inclus` (captures de la page d'achat). */
    format: CARTE_MICRO.modalites,
    /** Texte du tunnel de paiement. La 5e capture de la page d'achat le
     *  répète MOT POUR MOT (surtitre, titre, phrases, cinq points) : elle
     *  n'ajoute rien. */
    coaching: {
      surtitre: "LE + DE CETTE FORMATION",
      titre: "Un accompagnement individuel premium inclus",
      corps: [
        "Ce qui distingue cette formation des autres :",
        "un vrai temps de coaching humain, en visio, pour ancrer la méthode sur votre projet réel.",
        `${DUREES_MICRO.heuresDeCoaching}H D'accompagnement individuel en visio, réparties en ${DUREES_MICRO.seancesDeCoaching} séances d'${DUREES_MICRO.heuresParSeance} heure.`,
        "Pour passer du contenu à l'action, sur votre projet à vous.",
      ],
      points: [
        "Analyse de votre projet et de sa cohérence avec le statut micro",
        "Relecture de votre étude de marché et conseils ciblés",
        "Aide sur les calculs de votre prévisionnel financier",
        "Conseil sur le statut, vos obligations, votre organisation",
        `Mini-plan d'action personnalisé sur ${JOURS_DU_PLAN_D_ACTION_MICRO} jours`,
      ],
    },
  },

  /** 6e capture de la page d'achat : huit objectifs. Même gabarit que la
   *  capture « sociétés », texte propre à la micro-entreprise. */
  objectifs: {
    surtitre: "OBJECTIFS PÉDAGOGIQUES",
    titre: "Ce que vous saurez faire à la fin de la formation",
    liste: [
      "Comprendre le régime micro-entrepreneur et ses caractéristiques en profondeur",
      "Identifier toutes vos obligations fiscales, sociales et administratives",
      "Réaliser une étude de marché solide et exploitable pour valider votre projet",
      "Construire un prévisionnel financier adapté au format micro-entreprise",
      "Utiliser l'IA pour structurer votre projet et automatiser certaines démarches",
      "Effectuer en autonomie toutes les démarches d'immatriculation",
      "Concevoir une stratégie de lancement et trouver vos premiers clients",
      "Identifier les risques, limites et évolutions possibles du statut micro",
    ],
  } satisfies ObjectifsPedagogiques,

  outils: ATOUTS_DES_FORMATIONS,

  financement: ORGANISME_DE_FORMATION,

  presentiel: PRESENTIEL,

  questions: QUESTIONS_DES_FORMATIONS,

  appelFinal: {
    /** Bouton de `/achat-formationmicro`, vers le tunnel. */
    bouton: {
      libelle: "JE REJOINS LA FORMATION !",
      lien: LIENS_FORMATIONS.paiementMicro,
    } as Bouton,
  },

  commande: {
    titre:
      "Plus qu'une étape avant de vous former parfaitement pour créer votre micro-entreprise !",
    ...COMMANDE_D_UNE_FORMATION,
    bouton: "Je choisis la formation MICRO !",
  },
};

// ── Page 4 : la Méthode P.O.P ───────────────────────────────────────────────

/** La 1re capture de `/achat-formationpop`, mot pour mot. Elle n'a ni
 *  surtitre ni titre d'ensemble : elle suit directement les deux lignes
 *  « POURQUOI CETTE FORMATION ? » de la page. */
const ARGUMENTAIRE_POP: Argumentaire = {
  surtitre: null,
  titre: null,
  constat: {
    titre: "Aujourd'hui, vous vivez peut-être ça",
    points: [
      "Vos journées défilent sans que vous ayez vraiment avancé",
      "Vous travaillez beaucoup, mais votre chiffre d'affaires ne suit pas",
      "La charge mentale est constante, le stress aussi",
      "Vous savez ce qu'il faudrait faire, sans jamais arriver à le mettre en place",
      "Vous testez des outils, des méthodes… rien ne tient sur la durée",
      "Vous avez l'impression d'éteindre des feux plutôt que de piloter",
    ],
  },
  promesse: {
    titre: "Avec la Méthode P.O.P, vous allez :",
    points: [
      "Reprendre la main sur vos priorités et votre planning",
      "Identifier ce qui génère vraiment du chiffre dans votre activité",
      "Mettre en place une routine durable et simple à tenir",
      "Réduire la charge mentale grâce à un système clair",
      "Gagner du temps avec les bons outils et l'IA",
      "Piloter votre activité avec des indicateurs concrets",
    ],
  },
};

/** Sources : `/achat-formationpop` (texte et quatre captures d'écran,
 *  retranscrites le 19/11/2026), la carte du catalogue et
 *  `/paiement-formationpopok`. Elle n'a ni programme module par module ni
 *  coaching individuel : le site n'en annonce pas, les captures non plus. */
export const PAGE_POP = {
  onglet: {
    ...ONGLET_RELEVE_SUR_LES_PAGES_D_ACHAT,
    aReecrire: false,
    remarque:
      "Le titre et la description tutoient (« Organise ton business », « Structure ton business ») ; le corps de la page vouvoie.",
  } as Onglet,

  ouverture: {
    constat:
      "Vous avez l’impression que vos journées vous échappent ou que vos priorités ne sont jamais atteintes ?",
    promesse:
      "Vous voulez reprendre le contrôle, mieux gérer votre temps et atteindre vos objectifs avec clarté et sérénité.",
    titreDesApprentissages: "La méthode P.O.P vous apprendra à :",
    apprentissages: [
      "Structurer vos priorités grâce à des techniques éprouvées (Matrice Eisenhower, Loi de Pareto).",
      "Planifier efficacement vos tâches avec le Pomodoro, le Time Blocking, et des outils modernes.",
      "Passer à l’action avec une organisation optimisée et des routines productives.",
      "Automatiser et simplifier vos processus pour gagner en efficacité.",
      "Découvrir la puissance de L'IA avec un assistant entièrement personnalisé qui vous guidera dans l'accomplissement de vos objectifs professionnels",
    ],
    /** Relevé comme dernier point de la liste, en une ligne séparée par des
     *  barres : « 7h de formation / 100% e-learning / Accès à vie / Agent IA
     *  dédié ». */
    enBref: [
      `${DUREES_POP.heuresEnLigne}h de formation`,
      "100% e-learning",
      "Accès à vie",
      "Agent IA dédié",
    ],
    titre:
      "Planifiez, Organisez, Produisez : Boostez votre productivité avec la méthode P.O.P",
    sousTitre:
      "Transformez votre quotidien grâce à une méthode pragmatique, simple et efficace.",
  },

  pourQui: {
    ...POURQUOI_CETTE_FORMATION,
    /** La colonne des constats de la 1re capture ; `argumentaire` porte la
     *  capture entière. */
    situations: ARGUMENTAIRE_POP.constat.points,
    argumentaire: ARGUMENTAIRE_POP,
    /** La seule phrase écrite qui nomme le public (tunnel de paiement). */
    public:
      `La formation P.O.P en ${DUREES_POP.heuresEnLigne} heures est une expérience immersive et concrète, conçue pour les porteurs de projet, entrepreneurs et indépendants qui veulent enfin maîtriser leur temps, leurs priorités et leurs résultats.`,
    /** « 15 ans d'expérience » : voir la remarque sur l'ancienneté dans
     *  `PAGE_CATALOGUE.pourquoi`. */
    promesse:
      "Pas de blabla, pas de théorie inutile : vous repartez avec des outils pratiques et une méthode éprouvée (15 ans d'expérience) pour booster votre efficacité au quotidien !",
  },

  /** 2e capture de la page d'achat : six objectifs. */
  objectifs: {
    surtitre: "OBJECTIFS PÉDAGOGIQUES",
    titre: "Ce que vous saurez faire à la fin de la formation",
    liste: [
      "Structurer votre activité avec un système clair : P.O.P (Planifiez – Organisez – Produisez)",
      "Définir des objectifs entrepreneuriaux alignés avec vos priorités réelles",
      "Mettre en place une organisation quotidienne qui réduit la charge mentale et augmente l'efficacité opérationnelle",
      "Utiliser des outils modernes et simples pour automatiser et optimiser votre travail",
      "Identifier les actions à forte valeur ajoutée qui améliorent directement votre rentabilité",
      "Suivre votre progression et ajuster votre plan d'action pour maintenir une dynamique durable",
    ],
  } satisfies ObjectifsPedagogiques,

  /** 3e capture de la page d'achat : les trois lettres de la méthode. */
  methode: {
    surtitre: "LE CŒUR DE LA MÉTHODE",
    titre: "P.O.P : trois lettres, un système complet",
    corps:
      "Une méthode propriétaire EVKHA, pensée pour les entrepreneurs solo et les petites structures qui veulent un cadre simple mais puissant.",
    lettres: [
      {
        lettre: "P",
        verbe: "Planifiez",
        corps:
          "Définir des objectifs réalistes et mesurables. Construire une vision annuelle, mensuelle et hebdomadaire. Identifier ce qui augmente réellement votre rentabilité.",
      },
      {
        lettre: "O",
        verbe: "Organisez",
        corps:
          "Structurer votre semaine pour maximiser la valeur produite. Mettre en place les bons outils. Réduire la charge mentale pour libérer votre énergie.",
      },
      {
        lettre: "P",
        verbe: "Produisez",
        corps:
          "Vous concentrer sur les actions génératrices de valeur. Appliquer les techniques de productivité entrepreneuriales. Installer un rythme efficace et durable.",
      },
    ] as { lettre: string; verbe: string; corps: string }[],
  },

  /** 4e capture de la page d'achat : six cartes. Proche de
   *  `modalites.contenu` (tunnel de paiement), mais rédigé autrement. La
   *  dernière carte est à faire confirmer (voir `ATTESTATION_QUALIOPI`) : le
   *  tunnel, lui, écrit seulement « Attestation de fin de formation ». */
  inclus: {
    surtitre: "CE QUI EST INCLUS",
    titre: "Tout ce dont vous avez besoin pour passer à l'action",
    cartes: [
      {
        titre: `${DUREES_POP.heuresEnLigne}h de formation digitale`,
        corps:
          "Vidéos pédagogiques structurées, accessibles à votre rythme depuis ordinateur ou tablette.",
      },
      {
        titre: "Exercices guidés",
        corps:
          "Mises en pratique à chaque étape, pour appliquer la méthode à votre activité réelle.",
      },
      {
        titre: "Agent IA dédié",
        corps:
          "Un assistant IA spécialement formé pour vous accompagner vers l'atteinte de vos objectifs.",
      },
      {
        titre: "Templates P.O.P",
        corps:
          "Tableaux de bord, modèles, fiches pratiques et bonus réutilisables pour piloter votre activité.",
      },
      {
        titre: "Quiz & validation",
        corps:
          "Quiz de validation par module, quiz final, et plan d'action P.O.P personnalisé à compléter.",
      },
      {
        titre: ATTESTATION_QUALIOPI,
        corps:
          "Attestation de fin de formation générée automatiquement et suivi de progression complet.",
      },
    ],
  } satisfies BlocDeCartes,

  /** La présentation de la carte du catalogue : prix, accroche, acquis. */
  presentation: CARTE_POP,

  /** Ce que la formation contient, tel que le tunnel de paiement le liste
   *  (une seule ligne dans le relevé, découpée ici en ses huit éléments).
   *  « Agent IA » ici, « assistant IA » sur le catalogue : le site emploie les
   *  deux mots. « Accès illimité à la plateforme » ici, « Accès à vie » plus
   *  haut. */
  modalites: {
    titre: "La Méthode P.O.P",
    format: CARTE_POP.modalites,
    contenu: [
      "Planifiez. Organisez. Produisez.",
      `${DUREES_POP.heuresEnLigne}h de formation digitale`,
      "Exercices guidés à chaque étape",
      "Templates et tableaux de bord P.O.P",
      "Accès à un agent IA dédié",
      "Quiz et plan d'action",
      "Attestation de fin de formation",
      "Accès illimité à la plateforme",
    ],
  },

  outils: ATOUTS_DES_FORMATIONS,

  financement: ORGANISME_DE_FORMATION,

  presentiel: PRESENTIEL,

  questions: QUESTIONS_DES_FORMATIONS,

  appelFinal: {
    /** Bouton de `/achat-formationpop`, vers le tunnel. */
    bouton: {
      libelle: "JE REJOINS LA MÉTHODE P.O.P",
      lien: LIENS_FORMATIONS.paiementPop,
    } as Bouton,
  },

  commande: {
    titre:
      "Plus qu'une étape avant de structurer votre activité avec la Méthode P.O.P !",
    ...COMMANDE_D_UNE_FORMATION,
    bouton: "Je choisis la formation P.O.P",
  },
};

// ════════════════════════════════════════════════════════════════════════════
// ARTICULATION — ce que les pages de la plateforme (`Formations.tsx`) AJOUTENT
// au texte relevé, et ce qu'elles en AFFICHENT autrement.
//
// Tout ce qui précède est le relevé du site, mot pour mot. Ce qui suit, écrit
// le 19/11/2026 pour la refonte, est de deux sortes :
//
//  1. des textes COURTS d'articulation (surtitres, intitulés de boutons,
//     objets de courriel, la passerelle vers les packs et les études, les
//     titres d'onglet des pages qui n'en avaient pas de juste) — à faire
//     valider par la cliente ;
//  2. des VUES du relevé : où un titre se coupe pour que sa fin passe en
//     italique, et les quatre retouches d'affichage décidées pour la refonte
//     (attestation, outillage interne, ancienneté, assistant IA). Chaque vue
//     PART du texte relevé et LÈVE une erreur au chargement si ce texte a
//     changé : une retouche qui ne trouve plus sa cible ne doit pas passer
//     pour appliquée (règle 1).
//
// Aucun prix ici : ils se lisent dans `TARIFS_FORMATIONS`.
// ════════════════════════════════════════════════════════════════════════════

// ── Routes de la plateforme ─────────────────────────────────────────────────

/** Les pages de la nouvelle plateforme. Les boutons « Je découvre… » du
 *  catalogue y mènent ; les boutons d'ACHAT, eux, mènent encore aux tunnels
 *  de paiement du site actuel (`LIENS_FORMATIONS.paiement*`). */
export const ROUTES_FORMATIONS = {
  catalogue: "/formations",
  societes: "/formations/creer-son-entreprise",
  micro: "/formations/creer-sa-micro-entreprise",
  pop: "/formations/methode-pop",
  packs: "/packs",
  etudes: "/etudes",
} as const;

/** Le tunnel de paiement de chaque formation. */
export const PAIEMENT_DES_FORMATIONS: Record<CleDeFormation, string> = {
  societes: LIENS_FORMATIONS.paiementSocietes,
  micro: LIENS_FORMATIONS.paiementMicro,
  pop: LIENS_FORMATIONS.paiementPop,
};

// ── Outils des vues ─────────────────────────────────────────────────────────

/** Remplace `avant` par `apres` dans un texte relevé. Si `avant` n'y est
 *  plus, le module lève une erreur : la retouche n'a pas eu lieu, et le texte
 *  d'origine ne doit pas s'afficher à sa place sans que personne le sache. */
function retouche(texte: string, avant: string, apres: string): string {
  if (avant === "" || !texte.includes(avant)) {
    throw new Error(
      `contenuFormations : « ${avant} » est introuvable dans « ${texte} »`,
    );
  }
  return texte.replace(avant, apres);
}

export type TitreEnDeuxTemps = { avant: string; fin: string };

/** Un titre relevé, coupé en deux pour que sa fin passe en italique
 *  (Fraunces), comme sur l'accueil et la page des études. Le titre n'est PAS
 *  réécrit : on désigne seulement où il se coupe. Un titre qui ne se termine
 *  plus par l'accent attendu lève une erreur au chargement. */
function enDeuxTemps(titre: string, accent: string): TitreEnDeuxTemps {
  if (accent === "" || !titre.endsWith(accent) || titre.length === accent.length) {
    throw new Error(
      `contenuFormations : le titre « ${titre} » ne se termine pas par « ${accent} »`,
    );
  }
  return { avant: titre.slice(0, -accent.length).trimEnd(), fin: accent };
}

/** Le libellé d'un bouton relevé, sans sa flèche finale : le bouton de la
 *  plateforme dessine la sienne. */
export function sansFleche(libelle: string): string {
  return libelle.replace(/\s*→\s*$/, "");
}

/** « 2 h », « 18 h » : une durée en grand chiffre. */
export function dureeEnHeures(heures: number): string {
  return `${heures}\u00a0h`;
}

// ── Les titres, en deux temps ───────────────────────────────────────────────

export const TITRES_COMMUNS = {
  pourquoi: enDeuxTemps(POURQUOI_CETTE_FORMATION.titre, "vous êtes au bon endroit"),
  presentiel: enDeuxTemps(PRESENTIEL.titre, "en présentiel"),
  financement: enDeuxTemps(
    ORGANISME_DE_FORMATION.financement.question,
    "à un financement ?",
  ),
  questions: enDeuxTemps(QUESTIONS_DES_FORMATIONS.titre, "à vos questions"),
};

export const TITRES_DU_CATALOGUE = {
  ouverture: enDeuxTemps(PAGE_CATALOGUE.ouverture.titre, "au succès !"),
  pourquoi: enDeuxTemps(PAGE_CATALOGUE.pourquoi.titre, "nos formations ?"),
  formations: enDeuxTemps(PAGE_CATALOGUE.formations.titre, "dès Maintenant"),
  pourQui: enDeuxTemps(PAGE_CATALOGUE.pourQui.titre, "ça s'adresse ?"),
  avis: enDeuxTemps(PAGE_CATALOGUE.avis.titre, "avis clients"),
};

export const TITRES_SOCIETES = {
  ouverture: enDeuxTemps(PAGE_SOCIETES.ouvertureEnImage.titre, "de A à Z"),
  aQui: enDeuxTemps(PAGE_SOCIETES.pourQui.aQui.titre, "qui veulent voir grand"),
  objectifs: enDeuxTemps(PAGE_SOCIETES.objectifs.titre, "à la fin de la formation"),
  programme: enDeuxTemps(PAGE_SOCIETES.programme.titre, "du parcours"),
  statuts: enDeuxTemps(PAGE_SOCIETES.statuts.titre, "expliquées et comparées"),
  inclus: enDeuxTemps(PAGE_SOCIETES.inclus.titre, "créer et piloter votre société"),
  coaching: enDeuxTemps(PAGE_SOCIETES.modalites.coaching.titre, "premium inclus"),
};

export const TITRES_MICRO = {
  ouverture: enDeuxTemps(PAGE_MICRO.ouvertureEnImage.titre, "de A à Z"),
  aQui: enDeuxTemps(PAGE_MICRO.pourQui.aQui.titre, "qui veulent démarrer en micro"),
  objectifs: enDeuxTemps(PAGE_MICRO.objectifs.titre, "à la fin de la formation"),
  programme: enDeuxTemps(PAGE_MICRO.programme.titre, "du parcours"),
  inclus: enDeuxTemps(PAGE_MICRO.inclus.titre, "jusqu'au lancement"),
  coaching: enDeuxTemps(PAGE_MICRO.modalites.coaching.titre, "premium inclus"),
};

export const TITRES_POP = {
  ouverture: enDeuxTemps(PAGE_POP.ouverture.titre, "avec la méthode P.O.P"),
  objectifs: enDeuxTemps(PAGE_POP.objectifs.titre, "à la fin de la formation"),
  methode: enDeuxTemps(PAGE_POP.methode.titre, "un système complet"),
  inclus: enDeuxTemps(PAGE_POP.inclus.titre, "passer à l'action"),
};

// ── Les onglets ─────────────────────────────────────────────────────────────

/** Le titre d'onglet et la méta-description de chaque page de la plateforme.
 *
 *  - Catalogue : ceux du relevé, justes.
 *  - Sociétés et micro-entreprise : le relevé est celui de la Méthode P.O.P,
 *    copié sur le site (`aReecrire: true`). Titre ÉCRIT ici ; la description
 *    est la présentation relevée de la formation.
 *  - Méthode P.O.P : le relevé est juste mais TUTOIE (« Organise ton
 *    business ») quand toute la page vouvoie. Titre écrit ici ; la description
 *    est la phrase relevée sous le titre de la page. */
export const ONGLETS_DES_PAGES = {
  catalogue: {
    titre: PAGE_CATALOGUE.onglet.titre,
    description: PAGE_CATALOGUE.onglet.description,
  },
  societes: {
    titre: `Formation « ${CARTE_SOCIETES.titre} » – EVKHA`,
    description: CARTE_SOCIETES.corps.join(" "),
  },
  micro: {
    titre: `Formation « ${CARTE_MICRO.titre} » – EVKHA`,
    description: CARTE_MICRO.corps.join(" "),
  },
  pop: {
    titre: "Formation Méthode P.O.P : planifiez, organisez, produisez – EVKHA",
    description: PAGE_POP.ouverture.sousTitre,
  },
};

// ── Ce qui est inclus : trois retouches d'affichage ─────────────────────────

/** Ce que la plateforme écrit à la place d'« Attestation Qualiopi », tant que
 *  la cliente n'a pas confirmé la certification : la formulation du tunnel de
 *  la Méthode P.O.P, relevée (`PAGE_POP.modalites.contenu`). */
export const ATTESTATION_AFFICHEE = "Attestation de fin de formation";

if (!PAGE_POP.modalites.contenu.includes(ATTESTATION_AFFICHEE)) {
  throw new Error(
    `contenuFormations : « ${ATTESTATION_AFFICHEE} » n'est plus dans le relevé du tunnel P.O.P`,
  );
}

/** Les mentions d'outillage interne de l'ANCIEN site, retirées de l'affichage
 *  (le sens reste : « Vidéos courtes », « traçabilité complète »). Chacune
 *  doit être trouvée au moins une fois dans les cartes relevées. */
const OUTILLAGE_INTERNE = [" (Canva)", " Systeme.io"];

/** Ce qu'aucune carte affichée ne doit plus porter, quelle que soit la
 *  formation — la classe du défaut, pas les deux cartes d'aujourd'hui. */
const INTERDIT_A_L_AFFICHAGE = /qualiopi|canva|systeme\.io/i;

function inclusAffiche(cartes: CarteTitreCorps[]): CarteTitreCorps[] {
  const affichees = cartes.map((carte) => ({
    titre: carte.titre === ATTESTATION_QUALIOPI ? ATTESTATION_AFFICHEE : carte.titre,
    corps: OUTILLAGE_INTERNE.reduce(
      (corps, mention) => corps.replace(mention, ""),
      carte.corps,
    ),
  }));
  for (const carte of affichees) {
    if (INTERDIT_A_L_AFFICHAGE.test(`${carte.titre} ${carte.corps}`)) {
      throw new Error(
        `contenuFormations : la carte « ${carte.titre} » porte encore une mention à ne pas afficher`,
      );
    }
  }
  return affichees;
}

for (const mention of OUTILLAGE_INTERNE) {
  if (!PAGE_MICRO.inclus.cartes.some((carte) => carte.corps.includes(mention))) {
    throw new Error(
      `contenuFormations : la mention « ${mention} » n'est plus dans les cartes relevées`,
    );
  }
}

/** Les cartes « ce qui est inclus » TELLES QUE LES PAGES LES AFFICHENT.
 *
 *  1. « Attestation Qualiopi » (les trois formations) devient
 *     `ATTESTATION_AFFICHEE` : la certification est réglementée et reste à
 *     confirmer par la cliente. Le corps de la carte n'est pas touché.
 *  2. Micro-entreprise : « (Canva) » et « Systeme.io », qui nomment l'outillage
 *     de l'ancien site, sont retirés. Rien d'autre ne change.
 *
 *  Le relevé (`PAGE_*.inclus.cartes`) reste intact pour le jour où la cliente
 *  confirme : il suffira de lire le relevé à la place de cette vue. */
export const INCLUS_AFFICHE: Record<CleDeFormation, CarteTitreCorps[]> = {
  societes: inclusAffiche(PAGE_SOCIETES.inclus.cartes),
  micro: inclusAffiche(PAGE_MICRO.inclus.cartes),
  pop: inclusAffiche(PAGE_POP.inclus.cartes),
};

// ── Ancienneté ──────────────────────────────────────────────────────────────

/** La promesse de la Méthode P.O.P, avec l'ancienneté RETENUE pour la refonte :
 *  « plus de 15 ans », comme le catalogue (le tunnel écrit « 15 ans
 *  d'expérience », l'accueil de l'ancien site « 16 ans »). */
export const PROMESSE_POP_AFFICHEE = retouche(
  PAGE_POP.pourQui.promesse,
  "(15 ans d'expérience)",
  "(plus de 15 ans d'expérience)",
);

// ── Questions fréquentes, page par page ─────────────────────────────────────

/** Les formations dont le CONTENU RELEVÉ annonce un assistant ou un agent IA :
 *  la micro-entreprise (pastille « Agent IA inclus ») et la Méthode P.O.P
 *  (« Agent IA dédié »). La formation « sociétés » parle de « modules IA » et
 *  d'usage de l'IA, jamais d'un assistant : on ne lui en attribue pas. */
const FORMATIONS_AVEC_ASSISTANT: CleDeFormation[] = ["micro", "pop"];

const QUESTION_DE_L_ASSISTANT = "Comment fonctionne l'assistant IA ?";

export type PageDeFormations = "catalogue" | CleDeFormation;

/** Les questions qu'une page affiche dans sa liste.
 *
 *  - La question du financement n'y est pas : chaque page la pose en titre de
 *    sa section « financement », avec la même réponse, juste au-dessus.
 *  - La question de l'assistant IA n'est affichée que sur les pages des
 *    formations qui en annoncent un, et sa réponse y commence par « Cette
 *    formation inclut » au lieu de « Chaque formation inclut », qui
 *    l'attribuait aux trois. Le catalogue et la page « sociétés » ne la
 *    posent pas. */
export function questionsAffichees(page: PageDeFormations): Question[] {
  const liste = QUESTIONS_DES_FORMATIONS.liste;
  if (!liste.some((question) => question.q === QUESTION_DE_L_ASSISTANT)) {
    throw new Error(
      `contenuFormations : la question « ${QUESTION_DE_L_ASSISTANT} » n'est plus dans le relevé`,
    );
  }
  const avecAssistant =
    page !== "catalogue" && FORMATIONS_AVEC_ASSISTANT.includes(page);
  return liste
    .filter((question) => question.q !== ORGANISME_DE_FORMATION.financement.question)
    .filter((question) => question.q !== QUESTION_DE_L_ASSISTANT || avecAssistant)
    .map((question) =>
      question.q === QUESTION_DE_L_ASSISTANT
        ? {
            q: question.q,
            r: retouche(question.r, "Chaque formation inclut", "Cette formation inclut"),
          }
        : question,
    );
}

// ── Les cartes du catalogue ─────────────────────────────────────────────────

/** Les repères (durée, format) de chaque carte du catalogue. Pour la
 *  micro-entreprise, dont la carte relevée n'en porte aucun, ce sont les
 *  pastilles de l'ouverture de sa page d'achat. */
export const REPERES_DES_CARTES: Record<CleDeFormation, string[]> = {
  societes: CARTE_SOCIETES.modalites,
  micro: PAGE_MICRO.ouvertureEnImage.pastilles,
  pop: CARTE_POP.modalites,
};

// ── Les textes courts écrits pour la plateforme ─────────────────────────────

export const ARTICULATION = {
  /** Le visuel de l'ouverture du catalogue (`public/accueil/formations.webp`,
   *  1080 × 1080) : ses dimensions donnent le RATIO, la feuille la taille. */
  image: {
    src: "/accueil/formations.webp",
    largeur: 1080,
    hauteur: 1080,
    alt: "Un ordinateur portable affiche la couverture de la formation « Créer sa micro-entreprise », animée par Evangeline Khaili.",
  },

  ouverture: {
    /** Bouton de l'ouverture du catalogue : mène aux trois cartes. */
    boutonDuCatalogue: "Voir les trois formations",
    /** Au-dessus du prix, dans la section « En pratique ». */
    etiquetteDuPrix: "Tarif de la formation",
  },

  cartes: {
    /** Nom accessible de la liste des trois cartes. */
    nomDeLaListe: "Les trois formations en ligne",
  },

  pourQui: { surtitre: "Pour qui" },

  programme: {
    /** Sous le grand chiffre lu dans `NOMBRE_DE_MODULES`. */
    unite: "modules",
  },

  coaching: {
    /** Sous le grand chiffre lu dans `DUREES_*`. */
    unite: "de coaching individuel, en visio",
  },

  /** La section qui rassemble format, tarif et bouton d'achat. */
  modalites: {
    surtitre: "En pratique",
    titre: { avant: "La formation,", fin: "en pratique." } as TitreEnDeuxTemps,
  },

  /** La section des atouts communs, sur les trois pages de formation. */
  outils: {
    titre: {
      avant: "Ce que toutes nos formations",
      fin: "ont en commun.",
    } as TitreEnDeuxTemps,
  },

  financement: {
    surtitre: "Financement",
    /** Devant le numéro lu dans `ORGANISME_DE_FORMATION.nda`. */
    etiquetteDuNumero: "Numéro de déclaration d'activité (NDA) de l'organisme de formation",
    bouton: "Écrire pour étudier mon financement",
    objetDuCourriel: "Financement d'une formation EVKHA",
  },

  presentiel: {
    objetDuCourriel: "Prochaines sessions de formation en présentiel",
  },

  /** Avant l'appel final : les deux autres façons d'avancer. SANS PRIX. */
  passerelle: {
    surtitre: "Autrement",
    titre: { avant: "Se former n'est pas", fin: "la seule voie." } as TitreEnDeuxTemps,
    corps:
      "Vous préférez être accompagné, ou vous voulez seulement votre dossier ? Deux autres portes.",
    portes: [
      {
        surtitre: "Être accompagné",
        titre: "Les packs d'accompagnement",
        corps:
          "Vos documents de création rédigés pour vous, et des appels d'accompagnement pour avancer pas à pas.",
        bouton: "Voir les packs",
        lien: ROUTES_FORMATIONS.packs,
      },
      {
        surtitre: "Seulement le dossier",
        titre: "Les études à l'unité",
        corps:
          "Étude de marché, étude de concurrence, business plan ou stratégie : commandez uniquement le document dont vous avez besoin.",
        bouton: "Voir les études",
        lien: ROUTES_FORMATIONS.etudes,
      },
    ],
  },

  /** L'appel final du catalogue : aucune phrase du relevé ne le porte. Il
   *  reprend l'invitation de la première question fréquente (« n'hésitez pas
   *  à nous contacter pour que je vous oriente »). */
  finDuCatalogue: {
    titre: { avant: "Vous hésitez", fin: "entre deux formations ?" } as TitreEnDeuxTemps,
    corps:
      "Écrivez-nous ou réservez un appel : nous vous orientons vers la formation la plus adaptée à votre projet.",
    boutonAppel: "Réserver un appel",
    boutonCourriel: "Écrire à EVKHA",
    objetDuCourriel: "Quelle formation choisir ?",
  },
};
