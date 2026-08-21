/** Client d'API de l'espace client (`/api/espace/`).
 *
 * Distinct de `src/api.ts`, qui parle à `/api/dashboard/` avec un jeton
 * PARTAGÉ entre tous les administrateurs. Ici le jeton est nominatif : c'est
 * lui qui détermine l'organisation, et donc ce que la personne a le droit de
 * voir. Mélanger les deux clients ferait tôt ou tard passer un appel de
 * l'espace client par le jeton d'administration.
 */

const BASE = import.meta.env.VITE_API_URL ?? "";
const CLE_JETON = "evkha_espace_jeton";

export const jeton = {
  lire: (): string => localStorage.getItem(CLE_JETON) ?? "",
  ecrire: (valeur: string): void => localStorage.setItem(CLE_JETON, valeur),
  effacer: (): void => localStorage.removeItem(CLE_JETON),
  present: (): boolean => (localStorage.getItem(CLE_JETON) ?? "").length > 0,
};

export class ErreurApi extends Error {
  // Affectations explicites : `erasableSyntaxOnly` interdit les proprietes de
  // parametre de constructeur, qui ne s'effacent pas a la compilation.
  readonly statut: number;
  readonly code: string;

  constructor(message: string, statut: number, code = "") {
    super(message);
    this.statut = statut;
    this.code = code;
  }
}

async function appel<T>(chemin: string, options: RequestInit = {}): Promise<T> {
  const valeur = jeton.lire();
  const reponse = await fetch(`${BASE}/api/espace${chemin}`, {
    ...options,
    headers: {
      Accept: "application/json",
      // Pas de `Content-Type` sur un `FormData` : le navigateur doit poser
      // lui-même `multipart/form-data` AVEC la limite de séparation. L'écrire
      // à la main produit une requête que le serveur ne sait pas découper.
      ...(options.body && !(options.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(valeur ? { Authorization: `Bearer ${valeur}` } : {}),
      ...options.headers,
    },
  });

  if (reponse.status === 401) {
    // Un 401 sur la CONNEXION veut dire « identifiants invalides », pas
    // « session expirée » : il n'y avait pas de session. Réécrire le message
    // ici affichait « Session expirée » à quelqu'un qui se trompait de mot de
    // passe — ou dont le compte n'existait pas —, et l'envoyait chercher au
    // mauvais endroit. Un motif d'erreur doit désigner sa vraie cause
    // (règle 2). On laisse donc parler le serveur, qui dit « Identifiants
    // invalides ».
    const surConnexion = chemin.startsWith("/connexion");
    // On n'efface que SI le jeton refusé est encore celui du poste.
    //
    // Changer son mot de passe ferme toutes les sessions et en délivre une
    // neuve. Une requête déjà en vol au même instant porte l'ancien jeton,
    // revient en 401 — et effaçait le jeton neuf tout juste écrit. La personne
    // se retrouvait déconnectée à la seconde où elle sécurisait son compte.
    //
    // La fenêtre est étroite mais `refetchOnWindowFocus` la rend atteignable :
    // il suffit de changer de fenêtre pendant l'envoi. Comparer avant d'effacer
    // coûte une ligne et supprime la classe entière du problème — tout appel
    // dont la réponse arrive après un renouvellement de jeton (règle 4).
    if (!surConnexion && jeton.lire() === valeur) {
      jeton.effacer();
    }
    const charge = (await reponse.json().catch(() => ({}))) as {
      error?: string;
      code?: string;
    };
    throw new ErreurApi(
      charge.error ?? (surConnexion ? "Identifiants invalides." : "Session expirée."),
      401,
      charge.code ?? "unauthorized",
    );
  }
  if (reponse.status === 204) return undefined as T;
  if (!reponse.ok) {
    const charge = (await reponse.json().catch(() => ({}))) as {
      error?: string;
      code?: string;
    };
    throw new ErreurApi(
      charge.error ?? `Erreur ${reponse.status}`,
      reponse.status,
      charge.code ?? "",
    );
  }
  return (await reponse.json()) as T;
}

// ── Types ───────────────────────────────────────────────────────────────────

export type Role = "proprietaire" | "membre" | "lecture";

export interface Moi {
  /** La porte est-elle ouverte ? Décision du SERVEUR, jamais recalculée ici.
   *
   *  Tentant de l'inférer de `abonnement === null` — et faux : une organisation
   *  résiliée qui a encore des crédits ACHETÉS n'a pas d'abonnement actif et
   *  garde pourtant l'accès, ces crédits étant pérennes. L'interface lui aurait
   *  présenté un mur de paiement pour un service déjà payé. */
  acces_ouvert: boolean;
  utilisateur: {
    email: string;
    prenom: string;
    nom: string;
    role: Role;
    droits: string[];
  };
  organisation: {
    id: string;
    raison_sociale: string;
    statut: "active" | "suspendue";
    marque_blanche: boolean;
    validation_socle_par_client: boolean;
    /** Abonne mensuel, ou acheteur d'une etude a l'unite sur evkha.fr.
     *
     *  Sert a ne pas PROPOSER d'abonnement a qui n'en a pas. Ce n'est pas une
     *  mesure de securite : le serveur refuse de toute facon les routes
     *  d'abonnement pour un compte a l'unite (`espace(reserve_aux_abonnes)`).
     *  Un menu n'est pas un controle. */
    type_de_compte: "abonne" | "a_l_unite";
  };
  credits: { solde: number; seuil_alerte: number; alerte: boolean };
  abonnement: {
    formule: string;
    code: string;
    credits_par_echeance: number;
    prix_mensuel_cents: number;
    devise: string;
    debut_le: string;
    derniere_periode_dotee: string;
    /** Ce qu'il advient des crédits non consommés à l'échéance.
     *
     *  L'interface l'écrivait en dur (« Aucun »). Elle affirmait donc au
     *  client ce qu'il advient de son argent sans jamais l'avoir lu, et se
     *  serait trompée sur une formule à report plafonné. */
    report_credits: "aucun" | "integral" | "plafonne";
    plafond_report: number;
    /** L'abonnement se reconduira-t-il ? Distinct du statut : quelqu'un qui
     *  arrête le 6 pour une échéance au 20 reste actif jusqu'au 20 — il a payé
     *  ce mois-ci et garde ses crédits. */
    renouvellement_actif: boolean;
    /** Terme de la période en cours, tel que Stripe le calcule. Vide tant
     *  qu'aucun événement Stripe ne l'a fourni. */
    fin_de_periode_le: string;
    /** Faux pour un abonnement ouvert à la main depuis l'administration : il
     *  n'y a aucun prélèvement à arrêter ni à modifier. */
    pilote_par_carte: boolean;
    /** Tarif d'un crédit acheté à l'unité, en centimes. Vient de la
     *  formule : jamais recopié côté navigateur. */
    prix_credit_supplementaire_cents: number;
  } | null;
  /** Souscription demandée mais pas encore activée — le paiement n'est pas
   *  branché, EVKHA active à la main. Sans ce champ, quelqu'un qui vient de
   *  s'inscrire lit « Contactez EVKHA pour souscrire » et croit sa demande
   *  perdue. */
  souscription_en_attente: {
    formule: string;
    code: string;
    demandee_le: string;
  } | null;
}

/** Consommation agrégée, mois par mois.
 *
 * L'agrégation est faite par le SERVEUR. La refaire ici à partir du journal
 * produirait un second calcul qui finirait par contredire le solde affiché
 * juste à côté (règle 5).
 */
export interface Consommation {
  mois: {
    mois: string;
    libelle: string;
    recus: number;
    /** Crédits dépensés pour produire un document, remboursements déduits. */
    consommes: number;
    /** Crédits PERDUS à la bascule de période. Ils étaient additionnés aux
     *  consommés : un compte affichait « 40 consommés » pour 22 documents
     *  produits, et la projection d'épuisement s'appuyait sur des crédits
     *  jamais utilisés. */
    expires: number;
  }[];
  total_recu: number;
  total_consomme: number;
  total_expire: number;
  rythme: Rythme;
}

/** Rythme de consommation — ou la raison de ne pas l'annoncer.
 *
 * `epuisement_le` et `jours_restants` valent `null` dès que l'historique ne
 * permet pas de conclure ; `motif` dit alors pourquoi. L'interface doit
 * afficher cette raison, jamais une date de repli : une date inventée se croit
 * et décide d'un renouvellement.
 */
export interface Rythme {
  mensuel: number;
  mois_observes: number;
  solde: number;
  jours_restants: number | null;
  epuisement_le: string | null;
  motif:
    | ""
    | "aucun_mouvement"
    | "pas_assez_d_historique"
    | "aucune_consommation";
}

export type TypeMouvement =
  | "dotation"
  | "achat"
  | "geste"
  | "debit"
  | "remboursement"
  | "expiration";

export interface Mouvement {
  id: string;
  date: string;
  type: TypeMouvement;
  quantite: number;
  motif: string;
  reference: string;
  auteur: string;
}

/** Une etude de boutique achetee. Les liens de telechargement sont calcules
 *  a chaque affichage, jamais stockes : un lien conserve finirait par etre
 *  transmis, et resterait valable aussi longtemps qu'on le garderait. */
export interface AchatDeBoutique {
  id: string;
  titre: string;
  slug: string;
  pages: number;
  achete_le: string;
  montant_cents: number;
  theme: string;
  /** Couverture de l'étude, ou chaîne vide. */
  image: string;
  telechargement: string;
  editable: string;
}

/** Une etude de boutique proposee a l'achat depuis l'espace. */
export interface ProduitDeBoutique {
  slug: string;
  titre: string;
  theme: string;
  prix_cents: number;
  devise: string;
  pages: number;
  mise_a_jour: string;
  image: string;
}

/** Une etude vendue seule, telle que l'espace la propose au rachat. */
export interface EtudeALUnite {
  slug: string;
  libelle: string;
  /** `market_study`, `competitor_study`, `business_plan`, `business_strategy`. */
  type: string;
  prix_cents: number;
}

export interface ClientFinal {
  id: string;
  raison_sociale: string;
  secteur: string;
  pays: string;
  region: string;
  ville: string;
  contact_email: string;
  logo_url: string;
  couleur_principale: string;
  couleur_secondaire: string;
  couleur_fond: string;
  archive: boolean;
}

export interface Marque {
  raison_sociale: string;
  secteur: string;
  pays: string;
  region: string;
  ville: string;
  logo_url: string;
  couleur_principale: string;
  couleur_secondaire: string;
  couleur_fond: string;
  mention_confidentialite: string;
}

export interface Livrable {
  id: string;
  type: string;
  statut: string;
  offre: string;
  chapitres_faits: number;
  cree_le: string;
  termine_le: string | null;
  fichiers: { kind: string; statut: string; url: string }[];
}

export interface FormuleOffre {
  code: string;
  libelle: string;
  credits_par_echeance: number;
  prix_mensuel_cents: number;
  devise: string;
  cout_par_livrable_cents: number;
  report_credits: string;
  regenerations_offertes: number;
  actuelle: boolean;
}

export type TypeDemande =
  | "changement_formule"
  | "credits_additionnels"
  | "resiliation";

export interface Demande {
  id: string;
  type: TypeDemande;
  statut: "ouverte" | "traitee" | "refusee";
  formule_visee: string;
  quantite: number;
  message: string;
  reponse: string;
  date: string;
  traitee_le: string | null;
}

export interface DocumentCatalogue {
  type: string;
  libelle: string;
  description: string;
  cout_credits: number;
  questions: number;
  couvert: boolean;
}

export interface ChampFormulaire {
  identifiant: string;
  libelle: string;
  obligatoire: boolean;
  type: "texte" | "zone" | "nombres";
  aide: string;
  exemple: string;
}

export interface SectionFormulaire {
  titre: string;
  introduction: string;
  champs: ChampFormulaire[];
}

export interface FormulaireQuestionnaire {
  type: string;
  titre: string;
  note: string;
  sections: SectionFormulaire[];
}

export interface PieceJointe {
  id: string;
  categorie: "logo" | "document";
  nom: string;
  taille_octets: number;
  type_mime: string;
  date: string;
  url: string;
}

export interface EtapeSuivi {
  cle: string;
  libelle: string;
  etat: "attente" | "en_cours" | "fait" | "echec";
  detail: string;
}

/** Fin estimée d'une production, ou l'aveu qu'on ne sait pas.
 *
 *  `fondee_sur` n'est pas décoratif : `cette_etude` extrapole l'avancement
 *  RÉELLEMENT compté sur cette génération, `etudes_passees` retombe sur la
 *  durée médiane des études du même type — utile au démarrage, mais aveugle à
 *  une journée où l'API répond lentement. Afficher les deux du même ton
 *  promettrait au client une précision que la seconde n'a pas. */
export interface FinEstimee {
  minutes_restantes: number;
  fondee_sur: "cette_etude" | "etudes_passees";
  echeance: string;
}

export interface Suivi {
  id: string;
  type: string;
  statut: string;
  message: string;
  progression: number;
  en_production: boolean;
  duree_estimee_minutes: [number, number] | null;
  /** `null` dès que le serveur refuse d'extrapoler. L'écran se tait alors sur
   *  le délai plutôt que d'inventer un nombre. */
  fin_estimee: FinEstimee | null;
  cree_le: string;
  demarre_le: string | null;
  termine_le: string | null;
  etapes: EtapeSuivi[];
  fichiers: { kind: string; statut: string; url: string }[];
}

export interface Membre {
  id: string;
  email: string;
  prenom: string;
  nom: string;
  role: Role;
  actif: boolean;
  invite_le: string | null;
}

// ── Appels ──────────────────────────────────────────────────────────────────

export const espaceApi = {
  connexion: (email: string, mot_de_passe: string) =>
    appel<{ jeton: string; expire_le: string }>("/connexion/", {
      method: "POST",
      body: JSON.stringify({ email, mot_de_passe }),
    }),
  deconnexion: () => appel<void>("/deconnexion/", { method: "POST" }),
  /** Change son mot de passe, et rattrape la session au passage.
   *
   *  Le serveur révoque TOUS les jetons du compte — celui qui porte cette
   *  requête compris, puisqu'il ignore lequel est l'intrus — puis en délivre un
   *  neuf. La réécriture se fait ICI et non dans l'écran appelant : un appelant
   *  qui l'oublierait déconnecterait la personne à la seconde même où elle
   *  vient de sécuriser son compte, et l'oubli ne se verrait qu'à la requête
   *  suivante, loin de sa cause.
   *
   *  `sessions_fermees` compte la session courante, qui repart pourtant avec le
   *  jeton neuf. À l'écran de retrancher cette unité avant d'annoncer un
   *  nombre. */
  changerMotDePasse: async (corps: {
    mot_de_passe_actuel: string;
    nouveau_mot_de_passe: string;
  }) => {
    const retour = await appel<{ sessions_fermees: number; jeton: string }>(
      "/mot-de-passe/",
      { method: "POST", body: JSON.stringify(corps) },
    );
    jeton.ecrire(retour.jeton);
    return retour;
  },
  consommation: () => appel<Consommation>("/consommation/"),
  moi: () => appel<Moi>("/moi/"),
  credits: () =>
    appel<{ solde: number; mouvements: Mouvement[] }>("/credits/"),
  clientsFinaux: (archives = false) =>
    appel<{ clients: ClientFinal[] }>(
      `/clients-finaux/${archives ? "?archives=1" : ""}`,
    ),
  creerClientFinal: (donnees: Partial<ClientFinal>) =>
    appel<ClientFinal>("/clients-finaux/", {
      method: "POST",
      body: JSON.stringify(donnees),
    }),
  archiverClientFinal: (id: string) =>
    appel<ClientFinal>(`/clients-finaux/${id}/archiver/`, { method: "POST" }),
  marque: () => appel<Marque>("/marque/"),
  enregistrerMarque: (donnees: Marque) =>
    appel<Marque>("/marque/", { method: "POST", body: JSON.stringify(donnees) }),
  catalogue: () =>
    appel<{
      solde: number;
      peut_commander: boolean;
      documents: DocumentCatalogue[];
    }>("/catalogue/"),
  formulaire: (type: string) =>
    appel<FormulaireQuestionnaire>(`/formulaire/${type}/`),
  commander: (type: string, saisie: Record<string, string>) =>
    appel<{ job_id: string; statut: string; cout_credits: number }>(
      "/commander/",
      { method: "POST", body: JSON.stringify({ type, saisie }) },
    ),
  fichiers: (categorie?: string) =>
    appel<{ pieces: PieceJointe[] }>(
      `/fichiers/${categorie ? `?categorie=${categorie}` : ""}`,
    ),
  deposerFichier: (fichier: File, categorie: string) => {
    // `FormData` et non JSON : un fichier binaire encodé en base64 dans du
    // JSON pèse un tiers de plus et double la mémoire côté serveur.
    const corps = new FormData();
    corps.append("fichier", fichier);
    corps.append("categorie", categorie);
    return appel<PieceJointe>("/fichiers/", { method: "POST", body: corps });
  },
  supprimerFichier: (id: string) =>
    appel<void>(`/fichiers/${id}/supprimer/`, { method: "POST" }),
  livrables: () => appel<{ livrables: Livrable[] }>("/livrables/"),
  formules: () =>
    appel<{ code_actuel: string; formules: FormuleOffre[] }>("/formules/"),
  /** Ouvre le paiement d'une formule et rend l'adresse Stripe où aller payer.
   *
   *  On n'envoie qu'un CODE. Le montant est celui du tarif Stripe rattaché à
   *  la formule côté serveur : rien de ce que cette page transmet ne fixe un
   *  prix. */
  ouvrirLePaiement: (formule: string) =>
    appel<{ adresse: string }>("/paiement/", {
      method: "POST",
      body: JSON.stringify({ formule }),
    }),
  /** Arrête la reconduction. Le mois en cours reste dû et reste servi.
   *
   *  Ce n'était pas une action mais une DEMANDE qu'un humain d'EVKHA devait
   *  accorder — alors que l'écran de paiement promettait « résiliable à tout
   *  moment depuis votre espace » juste avant la saisie de la carte. */
  arreterAbonnement: () =>
    appel<{ renouvellement_actif: boolean; fin_de_periode_le: string }>(
      "/abonnement/arreter/",
      { method: "POST", body: "{}" },
    ),
  /** Ouvre un paiement PONCTUEL pour des crédits supplémentaires.
   *
   *  La page publique en annonce le tarif depuis le premier jour — « Crédit
   *  supplémentaire : 59 € » — et aucun chemin ne permettait de les payer.
   *
   *  Le montant n'est PAS envoyé : seul le nombre l'est. Le tarif unitaire est
   *  celui de la formule, côté serveur. Envoyer un prix depuis le navigateur
   *  reviendrait à laisser choisir combien payer. */
  acheterDesCredits: (quantite: number) =>
    appel<{ url: string }>("/credits/acheter/", {
      method: "POST",
      body: JSON.stringify({ quantite }),
    }),
  /** Les etudes achetables une par une, avec leur tarif.
   *
   *  Meme source que la page publique : la table `Offer`. Un second endroit
   *  qui deciderait des prix finirait par contredire le premier. */
  etudesALUnite: () => appel<{ etudes: EtudeALUnite[] }>("/etudes/"),
  /** Ouvre le paiement d'une etude supplementaire et rend l'adresse Stripe.
   *
   *  On n'envoie qu'un slug : le tarif est celui du catalogue. Transmettre un
   *  montant depuis le navigateur reviendrait a laisser choisir combien
   *  payer. */
  acheterUneEtude: (etude: string) =>
    appel<{ adresse: string }>("/etudes/acheter/", {
      method: "POST",
      body: JSON.stringify({ etude }),
    }),
  /** Les etudes de boutique achetees, et le reste du catalogue. */
  mesAchats: () =>
    appel<{ achats: AchatDeBoutique[]; catalogue: ProduitDeBoutique[] }>(
      "/achats/",
    ),
  /** Ouvre le paiement d'une etude de boutique depuis l'espace.
   *
   *  On n'envoie qu'un slug : le tarif est celui du catalogue. */
  acheterUnProduit: (produit: string) =>
    appel<{ adresse: string }>("/achats/acheter/", {
      method: "POST",
      body: JSON.stringify({ produit }),
    }),
  reprendreAbonnement: () =>
    appel<{ renouvellement_actif: boolean }>("/abonnement/reprendre/", {
      method: "POST",
      body: "{}",
    }),
  /** Change de formule tout de suite, chez Stripe et chez nous.
   *
   *  L'ancien chemin ouvrait une demande, et l'accorder ne touchait pas
   *  Stripe : le prélèvement suivant repartait sur l'ancien tarif, et le
   *  changement se défaisait tout seul à l'échéance. */
  changerDeFormule: (formule: string) =>
    appel<{ formule: string; libelle: string }>("/abonnement/formule/", {
      method: "POST",
      body: JSON.stringify({ formule }),
    }),
  demandes: () => appel<{ demandes: Demande[] }>("/demandes/"),
  creerDemande: (corps: {
    type: TypeDemande;
    formule?: string;
    quantite?: number;
    message?: string;
  }) =>
    appel<Demande>("/demandes/", {
      method: "POST",
      body: JSON.stringify(corps),
    }),
  suivi: (jobId: string) => appel<Suivi>(`/livrables/${jobId}/`),
  /** Renonce à une étude en échec et récupère son crédit.
   *
   *  Le crédit est débité au lancement. Sans cette route, un abonné dont
   *  l'étude échouait payait un document qu'il ne recevrait jamais, et devait
   *  ouvrir une demande traitée à la main. */
  abandonnerLivrable: (jobId: string) =>
    appel<{ job_id: string; statut: string; credits_restitues: boolean; solde: number }>(
      `/livrables/${jobId}/abandonner/`,
      { method: "POST", body: "{}" },
    ),
  /** Invite un collaborateur. Le courriel part TOUT DE SUITE, sans personne.
   *
   *  Le type déclarait `compte_a_creer`, un champ que le serveur ne renvoie
   *  pas, et taisait les deux qu'il renvoie vraiment. L'écran affichait donc
   *  « EVKHA lui transmettra ses identifiants » alors que le message était
   *  déjà parti — et, quand l'envoi échouait, il ne disait rien du tout et
   *  jetait le lien de secours. */
  inviter: (corps: { email: string; role: Role; prenom?: string; nom?: string }) =>
    appel<{
      id: string;
      email: string;
      role: Role;
      actif: boolean;
      invitation_envoyee: boolean;
      /** Vide quand l'envoi a réussi. Renseigné sinon, pour que l'invitant ait
       *  un recours immédiat plutôt qu'un collaborateur bloqué. */
      lien_activation: string;
    }>("/equipe/inviter/", { method: "POST", body: JSON.stringify(corps) }),
  revoquer: (id: string) =>
    appel<{ id: string; actif: boolean }>(`/equipe/${id}/revoquer/`, {
      method: "POST",
    }),
  equipe: () =>
    appel<{
      membres: Membre[];
      roles_disponibles: { code: Role; libelle: string }[];
    }>("/equipe/"),
  /** Corrige son prénom et son nom. Aucun droit requis, et c'est voulu.
   *
   *  Ce sont les siens : un rôle « Lecture seule » doit pouvoir écrire son
   *  propre état civil sans quémander. Aucune action du §12 n'entre en jeu —
   *  ces champs n'engagent pas l'organisation.
   *
   *  L'adresse n'a délibérément pas sa place dans ce corps : le serveur ignore
   *  un `email` envoyé ici, il ne l'honore jamais. La déclarer dans ce type
   *  ferait croire l'inverse à l'écran suivant, qui l'enverrait et croirait
   *  l'avoir changée. Voir `demanderNouvelleAdresse`. */
  modifierProfil: (corps: { prenom: string; nom: string }) =>
    appel<{ prenom: string; nom: string }>("/profil/", {
      method: "POST",
      body: JSON.stringify(corps),
    }),
  /** Ouvre un changement d'adresse de connexion. **Rien ne change ici.**
   *
   *  La réponse est un 202, pas un 200 : elle accuse réception d'une demande.
   *  L'adresse ne bougera qu'au clic dans la boîte visée — c'est ce clic seul
   *  qui prouve que cette boîte existe et appartient bien à la personne, et
   *  c'est lui qui rattrape une faute de frappe avant qu'elle n'enferme
   *  quelqu'un dehors. L'écran doit donc annoncer un envoi, jamais un
   *  changement.
   *
   *  Le mot de passe actuel est exigé en plus du jeton de session : un écran
   *  resté ouvert ne doit pas suffire à déplacer un identifiant de connexion. */
  demanderNouvelleAdresse: (corps: {
    mot_de_passe: string;
    nouvelle_adresse: string;
  }) =>
    appel<{
      adresse_visee: string;
      courriel_envoye: boolean;
      /** Vide quand le courriel est parti. Renseigné sinon — même contrat que
       *  `lien_activation` d'une invitation : une panne de messagerie ne doit
       *  pas laisser la personne attendre un message qui n'arrivera pas. */
      lien_confirmation: string;
    }>("/adresse/", { method: "POST", body: JSON.stringify(corps) }),
};
