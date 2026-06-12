import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { api, type OverviewData, type JobSummary, type SystemStatus } from "../api";

const DELIVERABLE_LABELS: Record<string, string> = {
  market_study: "Étude de marché",
  competitor_study: "Étude de concurrence",
  business_plan: "Business Plan",
  business_strategy: "Stratégie Business",
};

function StatCard({
  label,
  value,
  sub,
  alert,
}: {
  label: string;
  value: string | number;
  sub?: string;
  alert?: boolean;
}) {
  return (
    <div className={`stat-card${alert ? " stat-card--alert" : ""}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

function MiniPipeline({ job }: { job: JobSummary }) {
  const isRunning = job.status === "running";
  const isDone = job.status === "done";
  const isFailed = job.status === "failed";

  const stages = [
    "done",
    isDone ? "done" : isFailed ? "failed" : isRunning ? "running" : "pending",
    isDone ? "done" : "pending",
    isDone ? "done" : "pending",
  ];

  return (
    <div className="mini-pipeline">
      {stages.map((s, i) => (
        <span key={i}>
          <span className={`mp-dot mp-dot--${s}`} />
          {i < stages.length - 1 && <span className="mp-arrow">›</span>}
        </span>
      ))}
    </div>
  );
}

function RecentJobs({ jobs }: { jobs: JobSummary[] }) {
  const recent = jobs.slice(0, 5);

  return (
    <div className="recent-jobs">
      {recent.length === 0 && (
        <p className="recent-jobs__empty">Aucun livrable pour l'instant.</p>
      )}
      {recent.map((job) => (
        <div key={job.id} className="recent-job-row">
          <span className="recent-job-type">
            {DELIVERABLE_LABELS[job.deliverable_type] ?? job.deliverable_type}
          </span>
          <MiniPipeline job={job} />
          <span className={`badge badge--${job.status}`}>
            {job.status === "running"
              ? "En cours ⚡"
              : job.status === "done"
                ? "Terminé ✓"
                : job.status === "failed"
                  ? "Échec ✗"
                  : "En attente"}
          </span>
          {job.status === "running" && (
            <span className="recent-job-progress">
              {job.chapters_done}/{job.chapters_total} ch.
            </span>
          )}
          {job.status === "done" && (
            <span className="recent-job-cost mono">
              {parseFloat(job.total_cost_eur).toFixed(4)} €
            </span>
          )}
          <Link to="/jobs/$jobId" params={{ jobId: job.id }} className="recent-job-link">
            →
          </Link>
        </div>
      ))}
    </div>
  );
}

function ConfigStatus({ system }: { system: SystemStatus }) {
  const items = [
    {
      label: "API EVKHA",
      ok: system.api === "ok",
      okText: "En ligne",
      warnText: "Hors ligne",
    },
    {
      label: "Email — Brevo",
      ok: !system.email_stub,
      okText: "Actif",
      warnText: "STUB — BREVO_API_KEY requise",
    },
    {
      label: "IA — Anthropic",
      ok: !system.ai_stub,
      okText: "Actif",
      warnText: "STUB — ANTHROPIC_API_KEY requise",
    },
    {
      label: "PDF — WeasyPrint",
      ok: true,
      okText: "Actif",
      warnText: "",
    },
  ];

  return (
    <div className="config-card">
      {items.map((item) => (
        <div key={item.label} className="config-row">
          <span className={`config-dot ${item.ok ? "config-dot--ok" : "config-dot--warn"}`} />
          <span className="config-label">{item.label}</span>
          <span className={`config-status ${item.ok ? "config-status--ok" : "config-status--warn"}`}>
            {item.ok ? item.okText : item.warnText}
          </span>
        </div>
      ))}
    </div>
  );
}

function SetupGuide() {
  const steps = [
    { done: true, text: "API déployée", sub: "evkha.82-165-31-105.nip.io" },
    { done: true, text: "Dashboard opérationnel", sub: null },
    { done: false, text: "Activer email Brevo", sub: "En attente BREVO_API_KEY d'Evangeline" },
    { done: false, text: "Activer IA Anthropic", sub: "En attente ANTHROPIC_API_KEY d'Evangeline" },
    { done: false, text: "Configurer webhooks Systeme.io + Tally", sub: "URLs dans ACCES-EVKHA.md" },
    { done: false, text: "Basculer vers evkha.fr", sub: "DNS IONOS → 82.165.31.105" },
  ];

  return (
    <div className="guide-card">
      {steps.map((step, i) => (
        <div key={i} className="guide-step">
          <span className={`guide-num ${step.done ? "guide-num--done" : ""}`}>
            {step.done ? "✓" : i + 1}
          </span>
          <span className="guide-text">
            {step.text}
            {step.sub && <small>{step.sub}</small>}
          </span>
        </div>
      ))}
    </div>
  );
}

export function Dashboard() {
  const overviewQ = useQuery<OverviewData>({
    queryKey: ["overview"],
    queryFn: api.overview,
    refetchInterval: 30_000,
  });

  const jobsQ = useQuery<JobSummary[]>({
    queryKey: ["jobs"],
    queryFn: () => api.jobs(),
    refetchInterval: 15_000,
  });

  const systemQ = useQuery<SystemStatus>({
    queryKey: ["system"],
    queryFn: api.system,
    refetchInterval: 60_000,
  });

  const data = overviewQ.data;
  const isLoading = overviewQ.isLoading;

  return (
    <div className="page">
      <div className="page-topbar">
        <h1>Vue d'ensemble</h1>
        {systemQ.data && (
          <span className={`health-badge ${systemQ.data.api === "ok" ? "health-badge--ok" : "health-badge--down"}`}>
            <span className="health-dot" />
            {systemQ.data.api === "ok" ? "API en ligne" : "API hors ligne"}
          </span>
        )}
      </div>

      {isLoading && <p className="loading">Chargement…</p>}

      {data && (
        <>
          <div className="stat-grid">
            <StatCard label="Total livrables" value={data.jobs.total} />
            <StatCard label="Aujourd'hui" value={data.jobs.today} />
            <StatCard
              label="En cours"
              value={data.jobs.running}
              sub={data.jobs.running > 0 ? "⚡ actifs" : undefined}
              alert={data.jobs.running > 0}
            />
            <StatCard
              label="Échecs"
              value={data.jobs.failed}
              sub={data.jobs.failed > 0 ? "à vérifier" : undefined}
              alert={data.jobs.failed > 0}
            />
            <StatCard
              label="Coût IA / 30j"
              value={`${parseFloat(data.cost_30d_eur).toFixed(4)} €`}
              sub="plafond : 2 € / dossier"
            />
            <StatCard
              label="Incidents"
              value={data.incidents.open}
              sub={`dont ${data.incidents.critical_or_high} critiques`}
              alert={data.incidents.critical_or_high > 0}
            />
          </div>

          <div className="section-header">
            <h2>Derniers livrables</h2>
            <Link to="/jobs">Voir tous →</Link>
          </div>
          {jobsQ.data ? (
            <RecentJobs jobs={jobsQ.data} />
          ) : (
            <p className="loading">Chargement…</p>
          )}
        </>
      )}

      <div className="dashboard-bottom-grid">
        <div>
          <div className="section-header" style={{ marginTop: "20px" }}>
            <h2>Configuration système</h2>
          </div>
          {systemQ.data ? (
            <ConfigStatus system={systemQ.data} />
          ) : (
            <p className="loading">Chargement…</p>
          )}
        </div>
        <div>
          <div className="section-header" style={{ marginTop: "20px" }}>
            <h2>Prochaines étapes</h2>
          </div>
          <SetupGuide />
        </div>
      </div>
    </div>
  );
}
