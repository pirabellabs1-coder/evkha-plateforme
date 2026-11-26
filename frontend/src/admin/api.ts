/** Client d'API de l'espace administrateur (`/api/dashboard/`).
 *
 * Jeton PARTAGÉ entre les administrateurs EVKHA — c'est l'état actuel, et c'est
 * la limite connue de cet espace : il ne distingue pas encore le profil
 * d'exploitation du profil de direction (§12). Voir `docs/`.
 */
import { clearToken, getToken } from "../auth";

const BASE = import.meta.env.VITE_API_URL ?? "";

/** Ce que le serveur a DIT en refusant, ou `repli` s'il n'a rien dit.
 *
 *  Les vues de `/api/dashboard/` ne nomment pas toutes leur message de la
 *  même façon : la supervision, les signalements et les générations rendent
 *  `{"error": …}` ; les annonces et la boutique, `{"erreur": …}`
 *  (`dashboard/annonces.py`, `dashboard/boutique.py`). `post` ne lisait que la
 *  première clé, `get` n'en lisait aucune : envoyer deux fois une annonce
 *  affichait « Erreur 409 » nu, à la place de la phrase que le serveur avait
 *  écrite pour l'expliquer (audit du 19/11/2026). Un motif d'échec doit
 *  rester trouvable par qui le lit (règle 2).
 *
 *  UNE lecture, pour tous les appels de ce module : cinq copies de cette
 *  lecture avaient déjà divergé — trois ne lisaient que `erreur`, une que
 *  `error`, une seule les deux (règle 5). Une réponse illisible (la page HTML
 *  d'un 502) rend le repli. */
async function messageDuRefus(reponse: Response, repli: string): Promise<string> {
  return (await lireLeRefus(reponse)).message || repli;
}

/** Tout ce qu'un refus porte : sa phrase, et — pour les vues qui les donnent
 *  (`dashboard/formations.py`) — son `code` et le `champ` en cause. C'est LA
 *  lecture du corps d'un refus ; `messageDuRefus` n'en garde que la phrase.
 *  Chaque valeur absente ou illisible est une chaîne vide. */
async function lireLeRefus(
  reponse: Response,
): Promise<{ message: string; code: string; champ: string }> {
  const charge = (await reponse.json().catch(() => ({}))) as {
    erreur?: unknown;
    error?: unknown;
    code?: unknown;
    champ?: unknown;
  } | null;
  const texte = (valeur: unknown) => (typeof valeur === "string" ? valeur : "");
  return {
    message: texte(charge?.erreur ?? charge?.error),
    code: texte(charge?.code),
    champ: texte(charge?.champ),
  };
}

async function get<T>(chemin: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE}/api/dashboard${chemin}`, window.location.origin);
  if (params) Object.entries(params).forEach(([c, v]) => url.searchParams.set(c, v));
  const reponse = await fetch(url.toString(), {
    headers: {
      Accept: "application/json",
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    },
  });
  if (reponse.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Non autorisé");
  }
  if (!reponse.ok) {
    // Le chemin et le code d'abord : c'est ce détail qu'un bandeau d'erreur
    // demande de transmettre. Puis ce que le serveur a dit, s'il a dit
    // quelque chose.
    const dit = await messageDuRefus(reponse, "");
    throw new Error(`API ${chemin} → ${reponse.status}${dit ? ` : ${dit}` : ""}`);
  }
  return (await reponse.json()) as T;
}

// ── Types de supervision ────────────────────────────────────────────────────

export type StatutSignalement = "nouveau" | "en_cours" | "traite";

/** Un problème remonté depuis un espace client, vu de l'administration. */
export interface SignalementAdmin {
  id: string;
  organisation: string;
  organisation_id: string;
  auteur: string;
  sujet: string;
  sujet_libelle: string;
  message: string;
  statut: StatutSignalement;
  statut_libelle: string;
  reponse: string;
  livrable_id: string | null;
  cree_le: string;
  traite_le: string | null;
}

export interface Synthese {
  periode: { debut: string; fin: string; jours: number };
  organisations: { total: number; actives: number; suspendues: number };
  revenu: {
    /** Contractuel : la somme des abonnements actifs, ce qui DEVRAIT rentrer. */
    recurrent_mensuel_cents: number;
    /** Réel : ce que le prestataire a rapporté payé sur la période. */
    encaisse_periode_cents: number;
    /** Réel, depuis toujours. */
    encaisse_total_cents: number;
    devise: string;
    nature: string;
    avertissement: string;
  };
  documents: {
    produits: number;
    en_echec: number;
    total: number;
    taux_echec: number;
  };
  credits: {
    consommes: number;
    restitues: number;
    solde_total_en_circulation: number;
  };
  cout_production: {
    total_cents: number;
    moyen_par_document_cents: number;
  };
  incidents: { ouverts: number; graves: number };
  clients: { total: number };
}

export interface Evolution {
  mois: string[];
  series: {
    cle: string;
    libelle: string;
    valeurs: number[];
    /** « cents » quand la série est monétaire. Absent sinon : un compte de
     *  documents et une somme d'argent ne se lisent pas de la même façon. */
    unite?: string;
  }[];
}

export interface TransactionSupervision {
  id: string;
  ouverte_le: string;
  organisation: string;
  organisation_id: string;
  contact: string;
  /** « livrable » = une étude à produire, « produit » = une étude déjà rédigée
   *  achetée en boutique. Les deux manquaient : le type n'énumérait que les
   *  deux objets du temps où l'espace ne vendait que de l'abonnement. */
  objet: "abonnement" | "credits" | "livrable" | "produit" | "formation";
  objet_libelle: string;
  /** L'étude visée, pour un achat de boutique. Vide sinon. */
  produit: string;
  /** Le titre de la formation visée, pour un achat de formation. Vide sinon
   *  — `produit` est alors vide lui aussi. Facultatif : un serveur d'avant le
   *  20/11/2026 ne rend pas la clé. */
  formation?: string;
  formule: string;
  quantite: number;
  montant_cents: number;
  devise: string;
  /** « ouverte » tant que Stripe attend, « abandonnee » passé 24 h, « payee »
   *  quand le webhook a confirmé. L'abandon est calculé, jamais reçu. */
  etat: "ouverte" | "payee" | "abandonnee";
  payee_le: string;
  relances: number;
  relancee_le: string;
}

export interface LivrableConfiguration {
  type: string;
  libelle: string;
  description: string;
  chapitres: { numero: number; titre: string; mots_max: number }[];
  socle: {
    identifiant: string;
    libelle: string;
    perimetre: string;
    unite: string;
    obligatoire: boolean;
    chapitres: number[];
    commentaire: string;
  }[];
  /** La charte ENTIÈRE reçue par le modèle. Non résumée : c'est elle qui
   *  explique ce que le document devient. */
  charte: string;
}

export interface OrganisationSupervision {
  id: string;
  raison_sociale: string;
  contact: string;
  statut: "active" | "suspendue";
  marque_blanche: boolean;
  formule: string;
  prix_mensuel_cents: number;
  credits_par_echeance: number;
  solde: number;
  credits_consommes: number;
  documents_produits: number;
  clients_finaux: number;
  membres: number;
}

export interface DemandeSupervision {
  id: string;
  organisation: string;
  organisation_id: string;
  demandeur: string;
  type: string;
  statut: string;
  formule_visee: string;
  quantite: number;
  message: string;
  date: string;
}

async function post<T>(chemin: string, corps: unknown): Promise<T> {
  const reponse = await fetch(`${BASE}/api/dashboard${chemin}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    },
    body: JSON.stringify(corps),
  });
  if (reponse.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Non autorisé");
  }
  if (!reponse.ok) {
    throw new Error(await messageDuRefus(reponse, `Erreur ${reponse.status}`));
  }
  return (await reponse.json()) as T;
}

/** Une etude de boutique, vue de l'administration. */
export interface ProduitBoutique {
  id: string;
  slug: string;
  titre: string;
  description: string;
  sommaire: string;
  theme: string;
  prix_cents: number;
  devise: string;
  pages: number;
  mise_a_jour: string;
  en_ligne: boolean;
  rang: number;
  fichier: string;
  fichier_editable: string;
  /** Aperçu : découpé du document remis, jamais téléversé. */
  apercu_actif: boolean;
  apercu_pages: number;
  image: string;
  /** Faux tant qu'il manque un prix ou le fichier a remettre. */
  publiable: boolean;
  /** Ce qui manque, en clair. Un bouton qui refuse sans expliquer se lit
   *  comme une panne. */
  manque: string[];
  ventes: number;
  recette_cents: number;
  /** Moyenne des avis publiés, 0 s'il n'y en a aucun. */
  note: number;
  avis: AvisBoutique[];
}

export interface Annonce {
  id: string;
  titre: string;
  message: string;
  lien_libelle: string;
  lien_cible: string;
  statut: "brouillon" | "envoyee";
  envoyee: boolean;
  envoyee_le: string;
  courriels_envoyes: number;
  cree_le: string;
  /** Combien de personnes l'ont ouverte dans leur espace. */
  lue_par: number;
}

export interface AvisBoutique {
  id: string;
  auteur: string;
  qualite: string;
  note: number;
  texte: string;
  publie: boolean;
  date: string;
}

/** Envoi multipart : le meme formulaire porte les textes ET les fichiers.
 *  En faire deux envois obligerait a decider lequel gagne quand le second
 *  echoue. */
async function envoyer<T>(chemin: string, donnees: FormData): Promise<T> {
  const reponse = await fetch(`${BASE}/api/dashboard${chemin}`, {
    method: "POST",
    // Pas de `Content-Type` : le navigateur pose lui-meme la frontiere du
    // multipart, et l'ecrire a la main la rendrait fausse.
    headers: {
      Accept: "application/json",
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    },
    body: donnees,
  });
  if (!reponse.ok) {
    throw new Error(await messageDuRefus(reponse, `Erreur ${reponse.status}`));
  }
  return (await reponse.json()) as T;
}

// ── Formations ──────────────────────────────────────────────────────────────

/** Les natures d'une leçon, telles que le serveur les nomme
 *  (`catalog.models.NatureDeLecon`). */
export type NatureDeLecon = "video" | "texte" | "document" | "quiz";

/** Une leçon, vue de l'administration (`dashboard/formations._vue_lecon`). */
export interface LeconAdmin {
  id: string;
  rang: number;
  titre: string;
  nature: NatureDeLecon;
  /** Vide, ou une adresse `https://`. Aucune vidéo n'est stockée au serveur. */
  adresse_video: string;
  duree_minutes: number;
  texte: string;
  /** Lien SIGNÉ vers le document, qui expire : on le relit au serveur au
   *  moment de l'ouvrir, on ne le garde pas. Vide sans document. */
  fichier: string;
  fichier_nom: string;
  en_apercu_libre: boolean;
  retire: boolean;
  retire_le: string;
}

export interface ModuleAdmin {
  id: string;
  rang: number;
  titre: string;
  description: string;
  retire: boolean;
  retire_le: string;
  /** Les présentes dans leur ordre, puis les retirées. */
  lecons: LeconAdmin[];
}

/** Une formation ENTIÈRE, programme compris (`dashboard/formations._vue`). */
export interface FormationAdmin {
  id: string;
  /** L'adresse publique. Fixée à la création, elle ne change plus. */
  slug: string;
  titre: string;
  sous_titre: string;
  accroche: string;
  description: string;
  prix_cents: number;
  devise: string;
  duree_heures: number;
  heures_de_coaching: number;
  /** Combien de mois dure l'accès donné par un achat. 0 : sans limite de
   *  durée. FACULTATIF : un serveur qui ne le rend pas n'a rien dit. */
  duree_d_acces_mois?: number;
  /** Encore rendu par le serveur. L'écran ne l'affiche ni ne l'envoie plus :
   *  une formation se vend par le paiement de la plateforme. */
  lien_d_achat: string;
  image: string;
  en_ligne: boolean;
  rang: number;
  /** Faux tant qu'il manque quelque chose pour la mettre en ligne. */
  publiable: boolean;
  /** Ce qui manque, en clair (« un prix »). */
  manque: string[];
  cree_le: string;
  modifie_le: string;
  /** Les modules présents (les retirés ne comptent pas). */
  nombre_de_modules: number;
  /** Le nombre d'achats de cette formation. FACULTATIF : un serveur qui ne
   *  le rend pas n'a rien dit, et l'écran n'affiche alors rien — surtout pas
   *  un zéro qu'il aurait inventé. */
  nombre_d_achats?: number;
  /** Les présents dans leur ordre, puis les retirés. */
  modules: ModuleAdmin[];
}

/** Un champ que le serveur a écarté SANS faire échouer l'envoi : sa valeur
 *  précédente est restée, le reste est enregistré. */
export interface ChampRefuse {
  champ: string;
  raison: string;
}

/** Ce que rend toute écriture réussie sur les formations : la fiche entière,
 *  relue en base. L'écran n'a que cette forme à connaître. */
export interface EcritureDeFormation {
  formation: FormationAdmin;
  refuses: ChampRefuse[];
  module_id?: string;
  lecon_id?: string;
}

/** Un refus du serveur, avec ce qui permet de le poser CONTRE un champ.
 *
 *  `Error` ne porte qu'une phrase ; les vues des formations disent aussi quel
 *  champ est en cause (`champ`) et pourquoi (`code`). `statut` vaut 0 quand
 *  le serveur n'a pas répondu du tout (coupure réseau). */
export class RefusDuServeur extends Error {
  readonly code: string;
  readonly champ: string;
  readonly statut: number;

  constructor(message: string, statut: number, code = "", champ = "") {
    super(message);
    this.name = "RefusDuServeur";
    this.code = code;
    this.champ = champ;
    this.statut = statut;
  }
}

/** Ce qu'une écriture envoie : des champs simples (JSON), ou un formulaire
 *  multipart — obligatoire dès qu'un fichier part (`image`, `fichier`). */
export type CorpsDeFormation = Record<string, unknown> | FormData;

/** L'achat d'une formation par une organisation, vu de l'administration
 *  (`GET /api/dashboard/formations/<id>/achats/`).
 *
 *  Un accès se RETIRE et se rétablit ; l'achat, lui, reste : ni la ligne ni
 *  son paiement ne disparaissent. */
export interface AchatDeFormationAdmin {
  id: string;
  /** La raison sociale de l'organisation qui a acheté. */
  organisation: string;
  organisation_id?: string;
  email: string;
  montant_cents: number;
  devise: string;
  achete_le: string;
  /** La date du retrait de l'accès. `null` : l'achat donne accès. */
  revoque_le: string | null;
  motif_de_revocation: string;
  /** Le DERNIER jour de l'accès (`AAAA-MM-JJ`). `null` : sans limite. */
  acces_jusqu_au?: string | null;
  /** L'état de l'accès, tel que le serveur le calcule. */
  acces?: EtatDeLAcces;
  /** ABRÉGÉE par le serveur : de quoi reconnaître la ligne, pas le paiement. */
  reference_paiement: string;
}

/** Ce qu'envoie un changement d'accès : retirer (`revoque: true`, avec son
 *  `motif`), rétablir (`revoque: false`), ou fixer le dernier jour
 *  (`acces_jusqu_au` : un jour `AAAA-MM-JJ`, ou `null` pour « sans limite »). */
export interface ChangementDAcces {
  revoque?: boolean;
  motif?: string;
  acces_jusqu_au?: string | null;
}

// ── Le suivi des élèves (`dashboard/suivi_des_formations.py`) ───────────────

/** L'état d'un accès : ouvert, échu (son dernier jour est passé) ou retiré. */
export type EtatDeLAcces = "ouvert" | "echu" | "retire";

/** Une ligne du tableau des élèves : UNE personne, pour UN achat
 *  (`GET formations/<id>/eleves/`). Un achat fait par une organisation de
 *  trois personnes donne trois lignes, qui portent le même `achat_id`. */
export interface EleveDeFormation {
  achat_id: string;
  /** `null` : l'achat n'a encore aucun élève connu — seule l'adresse
   *  collectée au paiement est là. */
  eleve_id: string | null;
  nom: string;
  email: string;
  organisation: string;
  achete_le: string;
  acces_jusqu_au: string | null;
  acces: EtatDeLAcces;
  derniere_connexion: string | null;
  derniere_activite: string | null;
  lecons_terminees: number;
  lecons_total: number;
  /** `null` : aucune leçon au programme, le pourcentage ne se calcule pas. */
  pourcent: number | null;
  minutes_en_presentiel_signees: number;
}

/** Une signature de présence, vue de l'administration. */
export interface EmargementAdmin {
  id: string;
  achat_id: string;
  eleve_id: string;
  /** Le nom de la fiche de l'élève… */
  nom: string;
  signe_le: string;
  mode: "en_ligne" | "papier";
  /** … et celui qui a été SIGNÉ : ils peuvent différer. */
  nom_signe: string;
  adresse_ip: string | null;
}

/** Une séance en présentiel, avec ses signatures. */
export interface SeanceAdmin {
  id: string;
  formation_id: string;
  intitule: string;
  debut: string;
  duree_minutes: number;
  lieu: string;
  nom_de_la_formatrice: string;
  annulee_le: string | null;
  signee_par_la_formatrice_le: string | null;
  emargements: EmargementAdmin[];
}

/** Ce que rend toute écriture réussie sur une séance : la séance RELUE en
 *  base, et les champs écartés. */
export interface EcritureDeSeance {
  seance: SeanceAdmin;
  refuses: ChampRefuse[];
}

/** Tout ce qu'il faut pour imprimer une feuille d'émargement
 *  (`GET formations/seances/<id>/feuille/`). */
export interface FeuilleDEmargement {
  formation: { id: string; titre: string };
  seance: {
    id: string;
    intitule: string;
    debut: string;
    duree_minutes: number;
    lieu: string;
    annulee_le: string | null;
  };
  formatrice: { nom: string; signee_le: string | null };
  lignes: {
    achat_id: string;
    eleve_id: string | null;
    nom: string;
    organisation: string;
    acces: EtatDeLAcces;
    signature: null | { signe_le: string; mode: "en_ligne" | "papier"; nom_signe: string };
  }[];
}

/** Une adresse de l'audience du site (`dashboard.audience._vue`). */
export interface ContactDeLAudience {
  id: string;
  email: string;
  premiere_demande_le: string;
  derniere_demande_le: string;
  /** Les libellés, dans l'ordre de la première demande : « Checklist »,
   *  « Lexique », « Lettre ». */
  demandes: string[];
  inscrit_a_la_lettre: boolean;
  lettre_le: string | null;
  desinscrit_le: string | null;
}

/** Un fichier reçu du serveur, prêt à être enregistré par le navigateur. */
export interface FichierRecu {
  blob: Blob;
  nom: string;
}

/** Le nom de fichier d'un en-tête `Content-Disposition`, ou une chaîne vide.
 *  Entre deux origines, cet en-tête n'est lisible que si le serveur l'expose :
 *  l'appelant garde donc un nom de repli. */
function nomDuFichier(enTete: string | null): string {
  const trouve = /filename="?([^";]+)"?/i.exec(enTete ?? "");
  return trouve ? trouve[1].trim() : "";
}

/** Télécharge un fichier PAR `fetch`, sous le jeton. Un simple lien
 *  n'enverrait pas l'autorisation : le serveur répondrait 401 à la gérante. */
async function telecharger(chemin: string, nomDeRepli: string): Promise<FichierRecu> {
  let reponse: Response;
  try {
    reponse = await fetch(`${BASE}/api/dashboard${chemin}`, {
      headers: {
        Accept: "text/csv",
        ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
      },
    });
  } catch {
    throw new RefusDuServeur(
      "Le serveur n'a pas répondu : le fichier n'a pas été préparé. Vérifiez votre " +
        "connexion, puis réessayez.",
      0,
    );
  }
  if (reponse.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new RefusDuServeur("Non autorisé", 401);
  }
  if (!reponse.ok) {
    const refus = await lireLeRefus(reponse);
    throw new RefusDuServeur(
      refus.message ||
        `Le serveur a refusé de préparer le fichier (erreur ${reponse.status}).`,
      reponse.status,
      refus.code,
      refus.champ,
    );
  }
  return {
    blob: await reponse.blob(),
    nom: nomDuFichier(reponse.headers.get("Content-Disposition")) || nomDeRepli,
  };
}

/** Une écriture sur les formations. Toutes sont des `POST` : rien ne se
 *  supprime, un module ou une leçon se retire (`{"retire": true}`).
 *
 *  `T` : ce que la route rend. Presque toutes rendent la fiche entière
 *  (`EcritureDeFormation`) ; le changement d'un accès rend la ligne d'achat. */
async function ecrireUneFormation<T = EcritureDeFormation>(
  chemin: string,
  corps: CorpsDeFormation,
): Promise<T> {
  const multipart = corps instanceof FormData;
  let reponse: Response;
  try {
    reponse = await fetch(`${BASE}/api/dashboard/formations/${chemin}`, {
      method: "POST",
      // Multipart : pas de `Content-Type`, le navigateur pose la frontière.
      headers: {
        ...(multipart ? {} : { "Content-Type": "application/json" }),
        Accept: "application/json",
        ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
      },
      body: multipart ? corps : JSON.stringify(corps),
    });
  } catch {
    // `fetch` ne rejette que si rien n'est revenu : le navigateur dirait
    // « Failed to fetch », en anglais, à une gérante.
    throw new RefusDuServeur(
      "Le serveur n'a pas répondu : rien n'a été enregistré. Vérifiez votre " +
        "connexion, puis réessayez — votre saisie est toujours là.",
      0,
    );
  }
  if (reponse.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new RefusDuServeur("Non autorisé", 401);
  }
  if (!reponse.ok) {
    const refus = await lireLeRefus(reponse);
    throw new RefusDuServeur(
      refus.message ||
        `Le serveur a refusé l'envoi (erreur ${reponse.status}) : rien n'a été enregistré.`,
      reponse.status,
      refus.code,
      refus.champ,
    );
  }
  return (await reponse.json()) as T;
}

/** Rapport interne de qualité (`/api/dashboard/qualite/`, 29/09/2026). */
export interface RapportQualite {
  dossiers: {
    id: string;
    type: string;
    statut: string;
    qa_status: string;
    cree_le: string;
    memoire: boolean;
    chapitres_controles: number;
    motifs: number;
    replis: number;
    reperes: number;
    constats_pdf: number;
    cout_eur: string;
  }[];
  chapitres: {
    type: string;
    chapitre: number;
    titre: string;
    passages: number;
    motifs: number;
    replis: number;
  }[];
  familles_de_motifs: { famille: string; occurrences: number }[];
  constats_pdf: { controle: string; occurrences: number }[];
}


// ── Lettre d'information ────────────────────────────────────────────────────

/** Appel JSON avec une méthode d'écriture (PUT, DELETE). `post` reste la
 *  forme courante ; celle-ci existe parce que les vues de la lettre suivent
 *  les verbes HTTP (`dashboard/lettre.py`). */
async function ecrireEnJson<T>(methode: "PUT" | "DELETE", chemin: string, corps?: unknown): Promise<T> {
  const reponse = await fetch(`${BASE}/api/dashboard${chemin}`, {
    method: methode,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    },
    body: corps === undefined ? undefined : JSON.stringify(corps),
  });
  if (reponse.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Non autorisé");
  }
  if (!reponse.ok) {
    throw new Error(await messageDuRefus(reponse, `Erreur ${reponse.status}`));
  }
  return (await reponse.json()) as T;
}

export type StatutDeLettre = "brouillon" | "programmee" | "en_cours" | "envoyee" | "annulee";
export type StatutDEnvoi = "a_envoyer" | "en_cours" | "envoye" | "echec" | "ignore";
export type Declencheur = "inscription" | "checklist" | "lexique";

/** Ce qu'on rédige : la même forme pour une lettre, un modèle et une étape. */
export interface ContenuDeLettre {
  objet: string;
  /** Le texte gris affiché par les messageries à côté de l'objet. */
  apercu: string;
  corps_html: string;
}

/** Une lettre (`dashboard.lettre._vue_lettre`). */
export interface LettreAdmin extends ContenuDeLettre {
  id: string;
  statut: StatutDeLettre;
  programmee_pour: string | null;
  lancee_le: string | null;
  terminee_le: string | null;
  cree_le: string;
  modifiee_le: string;
  envois: Record<StatutDEnvoi, number>;
  destinataires_prevus?: number;
}

export interface ModeleDeLettre extends ContenuDeLettre {
  id: string;
  nom: string;
  modifie_le: string;
}

export interface EtapeDAutomatisation extends ContenuDeLettre {
  /** Absent pour un message qui n'est pas encore enregistré. */
  id?: string;
  delai_jours: number;
  envoyes?: number;
}

export interface AutomatisationAdmin {
  id: string;
  nom: string;
  declencheur: Declencheur;
  active: boolean;
  active_depuis: string | null;
  etapes: EtapeDAutomatisation[];
}

export interface ResumeDeLaLettre {
  inscrits: number;
  en_attente_de_confirmation: number;
  desinscrits: number;
  declencheurs: { valeur: Declencheur; libelle: string }[];
}

export type EcritureDAutomatisation = Omit<AutomatisationAdmin, "id" | "active_depuis">;

export const adminApi = {
  qualite: () => get<RapportQualite>("/qualite/"),

  // ── Formations ──────────────────────────────────────────────────────────
  formations: () => get<{ formations: FormationAdmin[] }>("/formations/"),
  /** Crée une formation, HORS LIGNE. Seul le titre est obligatoire. */
  creerUneFormation: (corps: CorpsDeFormation) => ecrireUneFormation("", corps),
  /** Modifie la fiche, ou la met en ligne / hors ligne (`en_ligne`). */
  modifierLaFormation: (formationId: string, corps: CorpsDeFormation) =>
    ecrireUneFormation(`${formationId}/`, corps),
  ajouterUnModule: (formationId: string, corps: CorpsDeFormation) =>
    ecrireUneFormation(`${formationId}/modules/`, corps),
  /** Modifie un module, le retire (`retire: true`) ou le rétablit. */
  modifierLeModule: (moduleId: string, corps: CorpsDeFormation) =>
    ecrireUneFormation(`modules/${moduleId}/`, corps),
  /** `modules` : EXACTEMENT les modules présents, dans l'ordre voulu. */
  ordonnerLesModules: (formationId: string, modules: string[]) =>
    ecrireUneFormation(`${formationId}/ordre/`, { modules }),
  ajouterUneLecon: (moduleId: string, corps: CorpsDeFormation) =>
    ecrireUneFormation(`modules/${moduleId}/lecons/`, corps),
  /** Modifie une leçon, la retire (`retire: true`) ou la rétablit. */
  modifierLaLecon: (leconId: string, corps: CorpsDeFormation) =>
    ecrireUneFormation(`lecons/${leconId}/`, corps),
  /** `lecons` : EXACTEMENT les leçons présentes du module, dans l'ordre voulu. */
  ordonnerLesLecons: (moduleId: string, lecons: string[]) =>
    ecrireUneFormation(`modules/${moduleId}/ordre/`, { lecons }),
  /** Les achats d'une formation. Une réponse sans la liste attendue est une
   *  panne, pas « aucun inscrit » : l'écran ne lit jamais un vide sur une
   *  réponse qu'il n'a pas su lire (règle 1). */
  inscritsDeLaFormation: async (formationId: string) => {
    const chemin = `/formations/${formationId}/achats/`;
    const reponse = await get<{ achats?: unknown } | null>(chemin);
    if (!Array.isArray(reponse?.achats)) {
      throw new Error(`API ${chemin} : réponse sans la liste des achats`);
    }
    return { achats: reponse.achats as AchatDeFormationAdmin[] };
  },
  /** Retire l'accès à une formation (`revoque: true`, avec son motif) ou le
   *  rétablit (`revoque: false`). Le serveur rend `{"achat": <la ligne à
   *  jour>}` (`dashboard/formations.achat`) ; un 409 (`formation_rachetee`)
   *  dit que le rétablissement est impossible, avec sa phrase.
   *
   *  Rend la ligne, ou `null` si la réponse n'en porte pas de lisible :
   *  l'écran relit alors la liste plutôt que de déduire un état. */
  changerLAccesALaFormation: async (
    achatId: string,
    corps: ChangementDAcces,
  ): Promise<AchatDeFormationAdmin | null> => {
    const reponse = await ecrireUneFormation<{ achat?: AchatDeFormationAdmin | null } | null>(
      `achats/${achatId}/`,
      { ...corps },
    );
    const ligne = reponse?.achat;
    return ligne !== null && typeof ligne === "object" && typeof ligne.id === "string"
      ? ligne
      : null;
  },

  // ── Le suivi des élèves ─────────────────────────────────────────────────
  /** Le tableau des élèves d'une formation. Une réponse sans la liste
   *  attendue est une panne, pas « aucun élève » (règle 1). */
  elevesDeLaFormation: async (formationId: string) => {
    const chemin = `/formations/${formationId}/eleves/`;
    const reponse = await get<{ eleves?: unknown; lecons_total?: unknown } | null>(chemin);
    if (!Array.isArray(reponse?.eleves)) {
      throw new Error(`API ${chemin} : réponse sans la liste des élèves`);
    }
    return {
      eleves: reponse.eleves as EleveDeFormation[],
      lecons_total: typeof reponse.lecons_total === "number" ? reponse.lecons_total : null,
    };
  },
  /** Le même tableau, en fichier pour l'auditeur. `slug` ne sert qu'au nom
   *  de repli, quand l'en-tête du serveur n'est pas lisible. */
  exporterLesEleves: (formationId: string, slug: string) =>
    telecharger(`/formations/${formationId}/eleves.csv`, `eleves-${slug}.csv`),
  /** Les séances en présentiel d'une formation, annulées comprises. */
  seancesDeLaFormation: async (formationId: string) => {
    const chemin = `/formations/${formationId}/seances/`;
    const reponse = await get<{ seances?: unknown } | null>(chemin);
    if (!Array.isArray(reponse?.seances)) {
      throw new Error(`API ${chemin} : réponse sans la liste des séances`);
    }
    return { seances: reponse.seances as SeanceAdmin[] };
  },
  creerUneSeance: (formationId: string, corps: Record<string, unknown>) =>
    ecrireUneFormation<EcritureDeSeance>(`${formationId}/seances/`, corps),
  /** Modifie une séance, l'annule (`annulee`), la signe (`signer`) ou y note
   *  une signature recueillie sur papier (`emargement_papier`). */
  modifierLaSeance: (seanceId: string, corps: Record<string, unknown>) =>
    ecrireUneFormation<EcritureDeSeance>(`seances/${seanceId}/`, corps),
  feuilleDEmargement: async (seanceId: string) => {
    const chemin = `/formations/seances/${seanceId}/feuille/`;
    const reponse = await get<{ feuille?: FeuilleDEmargement | null } | null>(chemin);
    const feuille = reponse?.feuille;
    if (!feuille || !Array.isArray(feuille.lignes) || !feuille.seance || !feuille.formation) {
      throw new Error(`API ${chemin} : réponse sans la feuille`);
    }
    return feuille;
  },

  produitsBoutique: () =>
    get<{ produits: ProduitBoutique[] }>("/boutique/"),
  ventesBoutique: () =>
    get<{
      ventes: {
        id: string;
        produit: string;
        slug: string;
        organisation: string;
        email: string;
        montant_cents: number;
        achete_le: string;
      }[];
    }>("/boutique/ventes/"),
  creerUnProduit: (donnees: FormData) =>
    envoyer<{ produit: ProduitBoutique }>("/boutique/", donnees),
  modifierLeProduit: (id: string, donnees: FormData) =>
    envoyer<{ produit: ProduitBoutique }>(`/boutique/${id}/`, donnees),
  supprimerLeProduit: async (id: string) => {
    const reponse = await fetch(`${BASE}/api/dashboard/boutique/${id}/`, {
      method: "DELETE",
      headers: {
        Accept: "application/json",
        ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
      },
    });
    if (!reponse.ok) {
      throw new Error(await messageDuRefus(reponse, `Erreur ${reponse.status}`));
    }
    return (await reponse.json()) as { supprime: string };
  },
  annonces: () =>
    get<{
      annonces: Annonce[];
      destinations: { cible: string; libelle: string }[];
      destinataires: number;
    }>("/annonces/"),
  redigerUneAnnonce: (annonce: {
    titre: string;
    message: string;
    lien_libelle: string;
    lien_cible: string;
  }) => post<{ annonce: Annonce }>("/annonces/", annonce),
  modifierUneAnnonce: (
    id: string,
    annonce: Partial<{
      titre: string;
      message: string;
      lien_libelle: string;
      lien_cible: string;
    }>,
  ) => post<{ annonce: Annonce }>(`/annonces/${id}/`, annonce),
  envoyerUneAnnonce: (id: string) =>
    post<{ annonce: Annonce; destinataires: number; courriels_envoyes: number }>(
      `/annonces/${id}/envoyer/`,
      {},
    ),
  supprimerUneAnnonce: async (id: string) => {
    const reponse = await fetch(`${BASE}/api/dashboard/annonces/${id}/`, {
      method: "DELETE",
      headers: {
        Accept: "application/json",
        ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
      },
    });
    if (!reponse.ok) {
      throw new Error(await messageDuRefus(reponse, `Erreur ${reponse.status}`));
    }
    return (await reponse.json()) as { supprimee: string };
  },
  ajouterUnAvis: (produitId: string, donnees: FormData) =>
    envoyer<{ produit: ProduitBoutique }>(`/boutique/${produitId}/avis/`, donnees),
  publierUnAvis: (avisId: string, publie: boolean) => {
    const donnees = new FormData();
    donnees.set("publie", publie ? "true" : "false");
    return envoyer<{ produit: ProduitBoutique }>(`/boutique/avis/${avisId}/`, donnees);
  },
  supprimerUnAvis: async (avisId: string) => {
    const reponse = await fetch(`${BASE}/api/dashboard/boutique/avis/${avisId}/`, {
      method: "DELETE",
      headers: {
        Accept: "application/json",
        ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
      },
    });
    if (!reponse.ok) {
      throw new Error(await messageDuRefus(reponse, `Erreur ${reponse.status}`));
    }
    return (await reponse.json()) as { produit: ProduitBoutique };
  },
  synthese: (jours = 30) => get<Synthese>("/supervision/synthese/", { jours: String(jours) }),
  evolution: (mois = 12) =>
    get<Evolution>("/supervision/evolution/", { mois: String(mois) }),
  transactions: (etat = "") =>
    get<{
      transactions: TransactionSupervision[];
      resume: {
        en_cours: number;
        abandonnees: number;
        payees: number;
        manque_a_gagner_cents: number;
        encaisse_cents: number;
      };
    }>("/supervision/transactions/", etat ? { etat } : undefined),
  relancerLaTransaction: (id: string) =>
    post<{ relances: number }>(`/supervision/transactions/${id}/relancer/`, {}),
  livrables: () =>
    get<{
      livrables: LivrableConfiguration[];
      figures: {
        quota: number | null;
        completion_jusqu_a: number;
      };
      modifiable: boolean;
      pourquoi: string;
    }>("/supervision/livrables/"),
  organisations: () =>
    get<{ organisations: OrganisationSupervision[] }>("/supervision/organisations/"),
  demandes: () =>
    get<{ demandes: DemandeSupervision[]; ouvertes: number }>("/supervision/demandes/"),
  formules: () =>
    get<{
      formules: {
        code: string;
        libelle: string;
        credits_par_echeance: number;
        prix_mensuel_cents: number;
      }[];
    }>("/supervision/formules/"),
  doter: (organisationId: string, corps: { quantite: number; motif: string; auteur?: string }) =>
    post<{ id: string; quantite: number; solde: number }>(
      `/supervision/organisations/${organisationId}/doter/`,
      corps,
    ),
  basculerStatut: (
    organisationId: string,
    corps: { action: "suspendre" | "reactiver"; motif?: string; auteur?: string },
  ) =>
    post<{ id: string; statut: string }>(
      `/supervision/organisations/${organisationId}/statut/`,
      corps,
    ),
  /**
   * Met fin à l'abonnement d'une organisation.
   *
   * Aucun crédit n'est repris : le mois en cours est payé. La réserve expirera
   * à la bascule de période.
   */
  resilierAbonnement: (
    organisationId: string,
    corps: { motif: string; auteur?: string },
  ) =>
    post<{ id: string; abonnements_resilies: number }>(
      `/supervision/organisations/${organisationId}/resilier/`,
      corps,
    ),
  traiterDemande: (
    demandeId: string,
    corps: { decision: "accorder" | "refuser"; reponse?: string; auteur?: string },
  ) =>
    post<{ id: string; statut: string; solde: number }>(
      `/supervision/demandes/${demandeId}/traiter/`,
      corps,
    ),

  // ── Audience du site ────────────────────────────────────────────────────
  audience: () =>
    get<{ contacts: ContactDeLAudience[]; total: number; inscrits_a_la_lettre: number }>(
      "/audience/",
    ),
  /** `lettre` : les seuls inscrits à la lettre, le fichier à importer dans
   *  l'outil d'envoi. Sans lui, toutes les adresses, téléchargeurs compris. */
  exporterLAudience: (lettre = false) =>
    lettre
      ? telecharger("/audience.csv?lettre=1", "newsletter-evkha-inscrits.csv")
      : telecharger("/audience.csv", "audience-evkha.csv"),
  desinscrireDeLaLettre: (contactId: string) =>
    post<{ contact: ContactDeLAudience }>(`/audience/${contactId}/desinscrire/`, {}),
  /** Efface un contact et ses demandes, à sa demande (RGPD). Irréversible. */
  effacerUnContact: (contactId: string) =>
    post<{ supprime: boolean }>(`/audience/${contactId}/supprimer/`, {}),

  // ── Lettre d'information ────────────────────────────────────────────────
  resumeDeLaLettre: () => get<ResumeDeLaLettre>("/lettre/"),
  lettres: () => get<{ lettres: LettreAdmin[]; inscrits: number }>("/lettre/lettres/"),
  lettre: (id: string) => get<LettreAdmin>(`/lettre/lettres/${id}/`),
  creerUneLettre: (contenu: ContenuDeLettre) => post<LettreAdmin>("/lettre/lettres/", contenu),
  modifierUneLettre: (id: string, contenu: ContenuDeLettre) =>
    ecrireEnJson<LettreAdmin>("PUT", `/lettre/lettres/${id}/`, contenu),
  supprimerUneLettre: (id: string) =>
    ecrireEnJson<{ supprimee: boolean }>("DELETE", `/lettre/lettres/${id}/`),
  /** `quand` nul : la lettre part à la prochaine minute. */
  programmerUneLettre: (id: string, quand: string | null) =>
    post<LettreAdmin>(`/lettre/lettres/${id}/programmer/`, { quand }),
  annulerUneLettre: (id: string) => post<LettreAdmin>(`/lettre/lettres/${id}/annuler/`, {}),
  apercuDeLettre: (contenu: ContenuDeLettre) => post<{ html: string }>("/lettre/apercu/", contenu),
  essaiDeLettre: (contenu: ContenuDeLettre, email: string) =>
    post<{ envoye: boolean; adresse: string }>("/lettre/essai/", { ...contenu, email }),
  /** Rend l'adresse ABSOLUE et publique de l'image, à poser dans le texte. */
  televerserUneImage: (image: File) => {
    const donnees = new FormData();
    donnees.set("image", image);
    return envoyer<{ url: string }>("/lettre/images/", donnees);
  },
  /** Inscrit directement les adresses trouvées dans `texte` (liste collée,
   *  export CSV). `consentement` : la gérante atteste leur accord. */
  ajouterDesAbonnes: (texte: string, provenance: string, consentement: boolean) =>
    post<{
      ajoutees: number;
      deja_inscrites: number;
      desinscrites_non_reinscrites: number;
      lignes_ecartees: number;
      invalides: string[];
      invalides_total: number;
      inscrits: number;
    }>("/lettre/abonnes/", { texte, provenance, consentement }),
  modelesDeLettre: () => get<{ modeles: ModeleDeLettre[] }>("/lettre/modeles/"),
  creerUnModele: (modele: Omit<ModeleDeLettre, "id" | "modifie_le">) =>
    post<ModeleDeLettre>("/lettre/modeles/", modele),
  modifierUnModele: (id: string, modele: Omit<ModeleDeLettre, "id" | "modifie_le">) =>
    ecrireEnJson<ModeleDeLettre>("PUT", `/lettre/modeles/${id}/`, modele),
  supprimerUnModele: (id: string) =>
    ecrireEnJson<{ supprime: boolean }>("DELETE", `/lettre/modeles/${id}/`),
  automatisations: () =>
    get<{ automatisations: AutomatisationAdmin[] }>("/lettre/automatisations/"),
  creerUneAutomatisation: (automatisation: EcritureDAutomatisation) =>
    post<AutomatisationAdmin>("/lettre/automatisations/", automatisation),
  modifierUneAutomatisation: (id: string, automatisation: EcritureDAutomatisation) =>
    ecrireEnJson<AutomatisationAdmin>("PUT", `/lettre/automatisations/${id}/`, automatisation),
  supprimerUneAutomatisation: (id: string) =>
    ecrireEnJson<{ supprimee: boolean }>("DELETE", `/lettre/automatisations/${id}/`),

  // ── Signalements et assistance ──────────────────────────────────────────
  signalements: () =>
    get<{
      signalements: SignalementAdmin[];
      a_traiter: number;
      statuts: { code: string; libelle: string }[];
    }>("/signalements/"),
  traiterSignalement: (
    signalementId: string,
    corps: { statut?: StatutSignalement; reponse?: string },
  ) => post<SignalementAdmin>(`/signalements/${signalementId}/traiter/`, corps),
  /** Efface un signalement. Irréversible — le contenu part au journal du
   *  serveur avant l'effacement, et c'est la seule trace qui en reste. */
  supprimerSignalement: (signalementId: string) =>
    post<{ supprime: boolean }>(`/signalements/${signalementId}/supprimer/`, {}),
  /** Ouvre une session sur l'espace de ce client, et rend le jeton.
   *
   *  Le jeton est marqué « assistance » côté serveur : il refuse toute route
   *  qui engage une dépense. Ce n'est pas l'interface qui protège — masquer un
   *  bouton n'empêche personne d'appeler la route. */
  ouvrirAssistance: (organisationId: string) =>
    post<{ jeton: string; organisation: string; compte: string }>(
      `/organisations/${organisationId}/assistance/`,
      {},
    ),
  assistances: () =>
    get<{
      assistances: {
        id: string;
        compte: string;
        ouvert_par: string;
        ouvert_le: string;
        derniere_utilisation: string | null;
      }[];
    }>("/signalements/assistances/"),
  fermerAssistance: (jetonId: string) =>
    post<{ ferme: boolean }>(
      `/signalements/assistances/${jetonId}/fermer/`,
      {},
    ),
};
