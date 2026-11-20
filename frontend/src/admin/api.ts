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
  /** ABRÉGÉE par le serveur : de quoi reconnaître la ligne, pas le paiement. */
  reference_paiement: string;
}

/** Ce qu'envoie un changement d'accès. `motif` n'accompagne qu'un retrait. */
export interface ChangementDAcces {
  revoque: boolean;
  motif?: string;
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
