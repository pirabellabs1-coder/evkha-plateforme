import { useQuery } from "@tanstack/react-query";
import { api, type OverviewData } from "../api";

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

export function Dashboard() {
  const { data, isLoading, error } = useQuery<OverviewData>({
    queryKey: ["overview"],
    queryFn: api.overview,
    refetchInterval: 30_000,
  });

  if (isLoading) return <p className="loading">Chargement…</p>;
  if (error || !data) return <p className="error">Impossible de charger le tableau de bord.</p>;

  const { jobs, cost_30d_eur, incidents } = data;

  return (
    <div className="page">
      <h1>Vue d'ensemble</h1>
      <div className="stat-grid">
        <StatCard label="Livrables générés (total)" value={jobs.total} />
        <StatCard label="Créés aujourd'hui" value={jobs.today} />
        <StatCard
          label="En cours"
          value={jobs.running}
          alert={jobs.running > 0}
        />
        <StatCard
          label="En échec"
          value={jobs.failed}
          alert={jobs.failed > 0}
        />
        <StatCard
          label="Coût IA (30 j)"
          value={`${parseFloat(cost_30d_eur).toFixed(4)} €`}
          sub="plafond : 2 € / dossier"
        />
        <StatCard
          label="Incidents ouverts"
          value={incidents.open}
          sub={`dont ${incidents.critical_or_high} critiques / high`}
          alert={incidents.critical_or_high > 0}
        />
      </div>
    </div>
  );
}
