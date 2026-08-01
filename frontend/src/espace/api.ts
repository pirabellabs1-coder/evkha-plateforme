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
    if (!surConnexion) {
      // Le jeton est mort : l'effacer ici évite une boucle de requêtes 401 sur
      // chaque écran monté.
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
  mois: { mois: string; libelle: string; recus: number; consommes: number }[];
  total_recu: number;
  total_consomme: number;
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

export interface Suivi {
  id: string;
  type: string;
  statut: string;
  message: string;
  progression: number;
  en_production: boolean;
  duree_estimee_minutes: [number, number] | null;
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
  inviter: (corps: { email: string; role: Role; prenom?: string; nom?: string }) =>
    appel<{ id: string; email: string; role: Role; compte_a_creer: boolean }>(
      "/equipe/inviter/",
      { method: "POST", body: JSON.stringify(corps) },
    ),
  revoquer: (id: string) =>
    appel<{ id: string; actif: boolean }>(`/equipe/${id}/revoquer/`, {
      method: "POST",
    }),
  equipe: () =>
    appel<{
      membres: Membre[];
      roles_disponibles: { code: Role; libelle: string }[];
    }>("/equipe/"),
};
