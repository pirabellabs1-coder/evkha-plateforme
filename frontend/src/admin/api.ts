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
  /** « livrable » = une étude à produire, « produit » = une étude déjà rédigée
   *  achetée en boutique. Les deux manquaient : le type n'énumérait que les
   *  deux objets du temps où l'espace ne vendait que de l'abonnement. */
  objet: "abonnement" | "credits" | "livrable" | "produit";
  objet_libelle: string;
  /** L'étude visée, pour un achat de boutique. Vide sinon. */
  produit: string;
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
    const charge = (await reponse.json().catch(() => ({}))) as { error?: string };
    throw new Error(charge.error ?? `Erreur ${reponse.status}`);
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
  extrait: string;
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
    const charge = (await reponse.json().catch(() => ({}))) as {
      erreur?: string;
      error?: string;
    };
    throw new Error(charge.erreur ?? charge.error ?? `Erreur ${reponse.status}`);
  }
  return (await reponse.json()) as T;
}

export const adminApi = {
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
      const charge = (await reponse.json().catch(() => ({}))) as { erreur?: string };
      throw new Error(charge.erreur ?? `Erreur ${reponse.status}`);
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
      const charge = (await reponse.json().catch(() => ({}))) as { erreur?: string };
      throw new Error(charge.erreur ?? `Erreur ${reponse.status}`);
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
      const charge = (await reponse.json().catch(() => ({}))) as { erreur?: string };
      throw new Error(charge.erreur ?? `Erreur ${reponse.status}`);
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
        plancher: number;
        plafond: number;
        demandees_au_modele: number;
        formes_minimum: number;
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
};
