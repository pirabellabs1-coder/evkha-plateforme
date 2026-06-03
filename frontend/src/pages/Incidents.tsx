import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { api, type Incident } from "../api";

const SEV_CLASS: Record<string, string> = {
  critical: "badge--critical",
  high: "badge--high",
  medium: "badge--medium",
  low: "badge--low",
};

export function Incidents() {
  const { data, isLoading } = useQuery<Incident[]>({
    queryKey: ["incidents"],
    queryFn: api.incidents,
    refetchInterval: 30_000,
  });

  const open = data?.filter((i) => i.status === "open") ?? [];
  const resolved = data?.filter((i) => i.status !== "open") ?? [];

  return (
    <div className="page">
      <h1>Incidents opérationnels</h1>

      {isLoading && <p className="loading">Chargement…</p>}

      {open.length > 0 && (
        <>
          <h2 className="text-error">Ouverts ({open.length})</h2>
          <IncidentTable incidents={open} />
        </>
      )}

      {open.length === 0 && !isLoading && (
        <div className="alert alert--success">Aucun incident ouvert ✓</div>
      )}

      {resolved.length > 0 && (
        <>
          <h2>Résolus récemment</h2>
          <IncidentTable incidents={resolved} />
        </>
      )}
    </div>
  );
}

function IncidentTable({ incidents }: { incidents: Incident[] }) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Titre</th>
          <th>Sévérité</th>
          <th>Statut</th>
          <th>Créé le</th>
          <th>Job</th>
        </tr>
      </thead>
      <tbody>
        {incidents.map((inc) => (
          <tr key={inc.id}>
            <td>{inc.title}</td>
            <td>
              <span className={`badge ${SEV_CLASS[inc.severity] ?? ""}`}>
                {inc.severity}
              </span>
            </td>
            <td>{inc.status}</td>
            <td className="mono text-sm">
              {new Date(inc.created_at).toLocaleString("fr-FR")}
            </td>
            <td>
              {inc.job_id ? (
                <Link to="/jobs/$jobId" params={{ jobId: inc.job_id }}>
                  Voir →
                </Link>
              ) : (
                "—"
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
