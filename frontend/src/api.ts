/** Client d'API vers le backend Django (dashboard endpoints). */

const BASE = import.meta.env.VITE_API_URL ?? "";

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE}/api/dashboard${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }
  const res = await fetch(url.toString(), {
    headers: { Accept: "application/json" },
    credentials: "include",
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${path} → ${res.status}: ${body}`);
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

export interface JobDetail extends JobSummary {
  chapters: Chapter[];
  customer_email: string;
  offer_name: string;
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

// --- API calls ---------------------------------------------------------------

export const api = {
  overview: () => get<OverviewData>("/overview/"),
  jobs: (status?: string) => get<JobSummary[]>("/jobs/", status ? { status } : undefined),
  job: (id: string) => get<JobDetail>(`/jobs/${id}/`),
  incidents: () => get<Incident[]>("/incidents/"),
};
