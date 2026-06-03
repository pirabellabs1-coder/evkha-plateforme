import { useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api, type Chapter, type JobDetail as JobDetailType } from "../api";

const STATUS_ICON: Record<string, string> = {
  done: "✓",
  running: "⚡",
  failed: "✗",
  pending: "○",
  skipped: "—",
};

function ChapterRow({ chapter }: { chapter: Chapter }) {
  return (
    <tr className={chapter.status === "failed" ? "row--error" : ""}>
      <td className="mono">{String(chapter.number).padStart(2, "0")}</td>
      <td>{chapter.title}</td>
      <td>
        <span className={`badge badge--${chapter.status}`}>
          {STATUS_ICON[chapter.status] ?? chapter.status} {chapter.status}
        </span>
      </td>
      <td className="mono">{chapter.input_tokens.toLocaleString()}</td>
      <td className="mono">{chapter.output_tokens.toLocaleString()}</td>
      <td className="mono">{parseFloat(chapter.cost_eur).toFixed(4)} €</td>
      {chapter.error_message && (
        <td className="text-error text-sm" colSpan={1}>
          {chapter.error_message}
        </td>
      )}
    </tr>
  );
}

export function JobDetail() {
  const { jobId } = useParams({ from: "/jobs/$jobId" });
  const { data, isLoading, error } = useQuery<JobDetailType>({
    queryKey: ["job", jobId],
    queryFn: () => api.job(jobId),
    refetchInterval: (q) =>
      q.state.data?.status === "running" ? 5_000 : false,
  });

  if (isLoading) return <p className="loading">Chargement…</p>;
  if (error || !data) return <p className="error">Job introuvable.</p>;

  const totalTokens = data.chapters.reduce(
    (acc, c) => acc + c.input_tokens + c.output_tokens,
    0
  );

  return (
    <div className="page">
      <h1>
        {data.offer_name}
        <span className={`badge badge--${data.status} ml-2`}>
          {data.status}
        </span>
      </h1>

      <div className="detail-meta">
        <span>Client : {data.customer_email}</span>
        <span>Coût total : {parseFloat(data.total_cost_eur).toFixed(4)} €</span>
        <span>
          Budget : {parseFloat(data.budget_eur).toFixed(2)} €{" "}
          {parseFloat(data.total_cost_eur) > parseFloat(data.budget_eur) && (
            <strong className="text-error">⚠ Dépassé</strong>
          )}
        </span>
        <span>Tokens : {totalTokens.toLocaleString()}</span>
        {data.started_at && (
          <span>
            Démarré : {new Date(data.started_at).toLocaleString("fr-FR")}
          </span>
        )}
        {data.completed_at && (
          <span>
            Terminé : {new Date(data.completed_at).toLocaleString("fr-FR")}
          </span>
        )}
      </div>

      {data.error_message && (
        <div className="alert alert--error">{data.error_message}</div>
      )}

      <h2>
        Chapitres — {data.chapters_done}/{data.chapters_total} terminés
      </h2>

      <table className="data-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Titre</th>
            <th>Statut</th>
            <th>Tokens in</th>
            <th>Tokens out</th>
            <th>Coût</th>
          </tr>
        </thead>
        <tbody>
          {data.chapters.map((c) => (
            <ChapterRow key={c.number} chapter={c} />
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={5} className="text-right mono">
              Total
            </td>
            <td className="mono">
              {parseFloat(data.total_cost_eur).toFixed(4)} €
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
