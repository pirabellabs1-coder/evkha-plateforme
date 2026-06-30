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
  total_cost_eur: string;
  budget_eur: string;
  chapters_done: number;
  chapters_total: number;
  started_at: string | null;
  completed_at: string | null;
  order_id: string;
  error_message: string | null;
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
  jobRelaunch:        (id: string) => post<GenerateResponse>(`/jobs/${id}/relaunch/`, {}),
  incidents:          () => get<Incident[]>("/incidents/"),
  incidentResolve:    (id: string) => post<{ id: string; status: string }>(`/incidents/${id}/resolve/`, {}),
  system:             () => get<SystemStatus>("/system/"),
  generate:           (req: GenerateRequest) => post<GenerateResponse>("/generate/", req),
  customers:          (type?: string) => get<CustomerSummary[]>("/customers/", type ? { type } : undefined),
  customer:           (id: string) => get<CustomerDetail>(`/customers/${id}/`),
  orders:             (params?: Record<string, string>) => get<OrderSummary[]>("/orders/", params),
};
