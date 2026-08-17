/** Client d'API vers le backend Django (dashboard endpoints). */

import { clearToken, getToken } from "./auth";

const BASE = import.meta.env.VITE_API_URL ?? "";

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE}/api/dashboard${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }
  const token = getToken();
  const res = await fetch(url.toString(), {
    headers: {
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: "include",
  });
  if (res.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${path} → ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const url = new URL(`${BASE}/api/dashboard${path}`, window.location.origin);
  const token = getToken();
  const res = await fetch(url.toString(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (res.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { error?: string }).error ?? `Erreur ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// --- Types -------------------------------------------------------------------

export interface OverviewData {
  jobs: {
    total: number;
    today: number;
    running: number;
    failed: number;
  };
  cost_30d_eur: string;
  incidents: {
    open: number;
    critical_or_high: number;
  };
  customers: { total: number };
  subscriptions: { active: number };
  orders: { waiting_intake: number };
}

export interface JobSummary {
  id: string;
  deliverable_type: string;
  status: string;
  /**
   * Le dossier se dit « en cours » alors que plus personne ne travaille dessus.
   *
   * Calculé par le backend, jamais déduit ici : la règle (aucun chapitre touché
   * depuis vingt minutes) vit dans `generation.services`. La redécider en
   * TypeScript ferait deux sources pour la même vérité — et c'est exactement ce
   * qui s'était produit sur le bouton « Relancer », dont la condition front
   * `failed || cancelled` était plus stricte que le backend. Il était donc
   * caché précisément dans le cas qui l'a fait écrire.
   */
  interrompue: boolean;
  /** Minutes écoulées depuis le dernier chapitre touché. `null` hors « en cours ». */
  minutes_sans_progression: number | null;
  /**
   * Verdict du gate qualité : `pending`, `running`, `passed`, `failed`, `blocked`.
   *
   * `blocked` veut dire que le document n'est PAS parti automatiquement. La
   * livraison reste possible à la main — c'est une dérogation prévue, « décision
   * humaine assumée » selon `generation/gate.py`. Encore faut-il que l'humain
   * la voie : le backend sérialisait ce champ depuis toujours et AUCUN écran ne
   * le lisait. Trois dossiers bloqués sont partis chez la cliente le
   * 10/08/2026, étude de marché comprise, avec le même bouton et aucun
   * avertissement. On n'assume pas une décision qu'on ne voit pas.
   */
  qa_status: string;
  total_cost_eur: string;
  budget_eur: string;
  chapters_done: number;
  chapters_total: number;
  started_at: string | null;
  completed_at: string | null;
  order_id: string;
  error_message: string | null;
  pdf_download_url: string | null;
  delivery_status: string | null;
}

/**
 * Une livraison RETENUE : le gate a refusé, et le document n'est pas parti.
 *
 * ## Pourquoi la livraison entre dans la condition
 *
 * Un dossier déjà envoyé n'est plus « bloqué » : la décision est prise, le
 * client a son document. Continuer à l'afficher en rouge, c'est alarmer sur
 * une chose qu'aucun geste ne peut changer — et c'était contradictoire à
 * lire : « Qualité : bloqué » à côté de « ✓ Email envoyé ».
 *
 * L'avertissement ne vaut que là où il est ACTIONNABLE : avant l'envoi, quand
 * on peut encore relire, recontrôler ou renoncer. C'est aussi ce qui lui rend
 * son sens — un badge qui crie sur des dossiers réglés finit ignoré, et le
 * jour où il dit vrai personne ne le regarde.
 *
 * La règle vit ici et nulle part ailleurs, pour la raison qui a déjà piégé le
 * bouton « Relancer » : deux conditions écrites à deux endroits finissent par
 * diverger, et celle du front était plus stricte que celle du back exactement
 * dans le cas qu'elle devait couvrir.
 */
export function livraisonBloquee(
  job: Pick<JobSummary, "qa_status" | "delivery_status">,
): boolean {
  return job.qa_status === "blocked" && job.delivery_status !== "sent";
}

/**
 * Un dossier relançable : échoué, annulé, interrompu — ou TERMINÉ avec un trou.
 *
 * Le dernier cas est arrivé après les autres. Un chapitre qui coince ne tue
 * plus l'étude : le dossier se termine avec un trou nommé, ce qui vaut mieux
 * que de perdre vingt-deux chapitres corrects. Mais sans ce bouton, le trou
 * devenait DÉFINITIF — stratégie `0f9fb13a` (11/08/2026), chapitre 0 perdu
 * sur un encadré d'une ligne de trop, vingt chapitres livrés, rien à faire.
 *
 * La relance ne réécrit que les chapitres en échec : la dépense se limite au
 * trou.
 */
export function estRelancable(
  job: Pick<JobSummary, "status" | "interrompue" | "chapters_done" | "chapters_total">,
): boolean {
  const trouAcombler =
    job.status === "done" && job.chapters_done < job.chapters_total;
  return (
    job.status === "failed" ||
    job.status === "cancelled" ||
    job.interrompue ||
    trouAcombler
  );
}

export interface Chapter {
  number: number;
  title: string;
  prompt_key: string;
  status: string;
  cost_eur: string;
  input_tokens: number;
  output_tokens: number;
  retry_count: number;
  error_message: string | null;
}

export interface Artifact {
  id: string;
  kind: string;
  status: string;
  download_url: string;
}

export interface JobDetail extends JobSummary {
  chapters: Chapter[];
  artifacts: Artifact[];
  customer_email: string;
  customer_id: string;
  offer_name: string;
  delivery: {
    status: string;
    sent_at: string | null;
  } | null;
  /** Ce que le dernier contrôle qualité a reproché au document.
   *
   * Vide quand rien n'a été retenu. Sans cette liste, l'écran affichait un
   * statut sans raison — et un statut sans raison ne se corrige pas. */
  qa_motifs?: { check: string; chapitre: number | null; detail: string }[];
}

export interface Incident {
  id: string;
  title: string;
  severity: string;
  status: string;
  created_at: string;
  resolved_at: string | null;
  job_id: string | null;
  order_id: string | null;
  details: Record<string, unknown>;
}

export interface SystemStatus {
  api: string;
  email_stub: boolean;
  ai_stub: boolean;
}

export interface GenerateRequest {
  deliverable_type: string;
  customer_email: string;
  first_name?: string;
  last_name?: string;
  company_name?: string;
  SECTEUR: string;
  PAYS: string;
  PROJET: string;
  ZONE: string;
  ELEMENTS_A_RETENIR?: string;
  DEMANDES_SPECIFIQUES?: string;
  CONCURRENTS?: string;
  CAPITAL_INITIAL?: string;
  FORME_JURIDIQUE?: string;
  MODELE_REVENUS?: string;
  EQUIPE?: string;
  OBJECTIF_STRATEGIQUE?: string;
  HORIZON_PLANIFICATION?: string;
  NOM_ENTREPRISE?: string;
  LOGO_URL?: string;
  COULEUR_PRINCIPALE?: string;
  COULEUR_SECONDAIRE?: string;
}

export interface GenerateResponse {
  job_id: string;
  status: string;
}

export interface CustomerSummary {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  company_name: string;
  customer_type: string;
  created_at: string;
  active_subscription: {
    tier: string;
    status: string;
    systeme_subscription_id: string;
  } | null;
}

export interface CustomerDetail extends CustomerSummary {
  subscriptions: {
    id: string;
    tier: string;
    status: string;
    systeme_subscription_id: string;
    starts_at: string | null;
    ends_at: string | null;
    created_at: string;
  }[];
  orders: OrderSummary[];
  credits_available: number;
  /** Abonnement B2B du lot 4. `null` si le contact n'appartient à aucune
   *  organisation. Distinct de `subscriptions`, qui décrit l'ancien flux
   *  Systeme.io : deux systèmes de crédits coexistent, et cet écran n'en
   *  connaissait qu'un. */
  organisation: {
    id: string;
    raison_sociale: string;
    statut: string;
    role: string;
    formule: string | null;
    credits_par_echeance: number;
    solde: number;
    solde_abonnement: number;
    solde_achete: number;
  } | null;
}

export interface OrderSummary {
  id: string;
  systeme_order_id: string;
  status: string;
  offer_name: string;
  offer_slug: string;
  deliverable_type: string;
  is_subscription: boolean;
  is_extra_credit: boolean;
  parent_order_id: string | null;
  period_year_month: string;
  customer_email: string;
  customer_id: string;
  purchased_at: string | null;
  created_at: string;
}

// --- API calls ---------------------------------------------------------------

export const api = {
  overview:           () => get<OverviewData>("/overview/"),
  jobs:               (status?: string) => get<JobSummary[]>("/jobs/", status ? { status } : undefined),
  job:                (id: string) => get<JobDetail>(`/jobs/${id}/`),
  jobCancel:          (id: string) => post<{ job_id: string; status: string }>(`/jobs/${id}/cancel/`, {}),
  jobRelaunch:        (id: string) => post<GenerateResponse>(`/jobs/${id}/relaunch/`, {}),
  jobRedeliver:       (id: string) => post<{ job_id: string; status: string }>(`/jobs/${id}/redeliver/`, {}),
  jobReverifier:      (id: string) => post<{ job_id: string; qa_status: string; passed: boolean; echecs: number }>(`/jobs/${id}/reverifier/`, {}),
  jobSendEmail:       (id: string) => post<{ job_id: string; status: string }>(`/jobs/${id}/send-email/`, {}),
  incidents:          () => get<Incident[]>("/incidents/"),
  incidentResolve:    (id: string) => post<{ id: string; status: string }>(`/incidents/${id}/resolve/`, {}),
  system:             () => get<SystemStatus>("/system/"),
  generate:           (req: GenerateRequest) => post<GenerateResponse>("/generate/", req),
  customers:          (type?: string) => get<CustomerSummary[]>("/customers/", type ? { type } : undefined),
  customer:           (id: string) => get<CustomerDetail>(`/customers/${id}/`),
  orders:             (params?: Record<string, string>) => get<OrderSummary[]>("/orders/", params),
};
