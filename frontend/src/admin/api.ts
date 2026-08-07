/** Client d'API de l'espace administrateur (`/api/dashboard/`).
 *
 * Jeton PARTAGÉ entre les administrateurs EVKHA — c'est l'état actuel, et c'est
 * la limite connue de cet espace : il ne distingue pas encore le profil
 * d'exploitation du profil de direction (§12). Voir `docs/`.
 */
import { clearToken, getToken } from "../auth";

const BASE = import.meta.env.VITE_API_URL ?? "";

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
  if (!reponse.ok) throw new Error(`API ${chemin} → ${reponse.status}`);
  return (await reponse.json()) as T;
}

// ── Types de supervision ────────────────────────────────────────────────────

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
  objet: "abonnement" | "credits";
  objet_libelle: string;
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
    const charge = (await reponse.json().catch(() => ({}))) as { error?: string };
    throw new Error(charge.error ?? `Erreur ${reponse.status}`);
  }
  return (await reponse.json()) as T;
}

export const adminApi = {
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
  traiterDemande: (
    demandeId: string,
    corps: { decision: "accorder" | "refuser"; reponse?: string; auteur?: string },
  ) =>
    post<{ id: string; statut: string; solde: number }>(
      `/supervision/demandes/${demandeId}/traiter/`,
      corps,
    ),
};
