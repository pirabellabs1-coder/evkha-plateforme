import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { api, type JobSummary } from "../api";

const DELIVERABLE_LABELS: Record<string, string> = {
  market_study: "Étude de marché",
  competitor_study: "Étude de concurrence",
  business_plan: "Business Plan",
  business_strategy: "Stratégie Business",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "En attente",
  running: "En cours ⚡",
  done: "Terminé ✓",
  failed: "Échec ✗",
  cancelled: "Annulé",
};

function ProgressBar({ done, total }: { done: number; total: number }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div className="progress-bar" title={`${done}/${total} chapitres`}>
      <div className="progress-fill" style={{ width: `${pct}%` }} />
      <span className="progress-label">
        {done}/{total}
      </span>
    </div>
  );
}

export function Jobs() {
  const [statusFilter, setStatusFilter] = useState("");
  const { data, isLoading } = useQuery<JobSummary[]>({
    queryKey: ["jobs", statusFilter],
    queryFn: () => api.jobs(statusFilter || undefined),
    refetchInterval: 15_000,
  });

  return (
    <div className="page">
      <h1>Livrables</h1>
      <div className="toolbar">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">Tous les statuts</option>
          {Object.entries(STATUS_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </div>

      {isLoading && <p className="loading">Chargement…</p>}

      {data && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Livrable</th>
              <th>Statut</th>
              <th>Progression</th>
              <th>Coût</th>
              <th>Terminé le</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.map((job) => (
              <tr
                key={job.id}
                className={job.status === "failed" ? "row--error" : ""}
              >
                <td>
                  {DELIVERABLE_LABELS[job.deliverable_type] ??
                    job.deliverable_type}
                </td>
                <td>
                  <span className={`badge badge--${job.status}`}>
                    {STATUS_LABELS[job.status] ?? job.status}
                  </span>
                </td>
                <td>
                  <ProgressBar
                    done={job.chapters_done}
                    total={job.chapters_total}
                  />
                </td>
                <td className="mono">
                  {parseFloat(job.total_cost_eur).toFixed(4)} €
                </td>
                <td className="mono text-sm">
                  {job.completed_at
                    ? new Date(job.completed_at).toLocaleDateString("fr-FR")
                    : "—"}
                </td>
                <td>
                  <Link to="/jobs/$jobId" params={{ jobId: job.id }}>
                    Détail →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
