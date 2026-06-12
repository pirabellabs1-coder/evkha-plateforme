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

const STATUS_LABELS: Record<string, string> = {
  done: "Terminé",
  running: "En cours",
  failed: "Échec",
  pending: "En attente",
  skipped: "Ignoré",
};

function Pipeline({ job }: { job: JobDetailType }) {
  const genStatus =
    job.status === "done"
      ? "done"
      : job.status === "failed"
        ? "failed"
        : job.status === "running"
          ? "running"
          : "pending";

  const stages = [
    {
      key: "order",
      label: "Commande reçue",
      sub: job.order_id ? `#${job.order_id.slice(0, 8)}` : null,
      status: "done" as const,
      icon: "✓",
    },
    {
      key: "gen",
      label: "Génération IA",
      sub: `${job.chapters_done}/${job.chapters_total} chapitres`,
      status: genStatus as "done" | "running" | "failed" | "pending",
      icon:
        genStatus === "done"
          ? "✓"
          : genStatus === "running"
            ? "⚡"
            : genStatus === "failed"
              ? "✗"
              : "○",
    },
    {
      key: "pdf",
      label: "Assemblage PDF",
      sub: null,
      status: (job.status === "done" ? "done" : "pending") as "done" | "pending",
      icon: job.status === "done" ? "✓" : "○",
    },
    {
      key: "email",
      label: "Email envoyé",
      sub: job.customer_email ? job.customer_email : null,
      status: (job.status === "done" ? "done" : "pending") as "done" | "pending",
      icon: job.status === "done" ? "✓" : "○",
    },
  ];

  return (
    <div className="pipeline">
      {stages.map((stage, i) => (
        <div key={stage.key} className="pipeline-stage-wrapper">
          <div className={`pipeline-step pipeline-step--${stage.status}`}>
            <div className="pipeline-circle">{stage.icon}</div>
            <div className="pipeline-name">{stage.label}</div>
            {stage.sub && <div className="pipeline-sub">{stage.sub}</div>}
          </div>
          {i < stages.length - 1 && (
            <div className={`pipeline-connector pipeline-connector--${stage.status}`} />
          )}
        </div>
      ))}
    </div>
  );
}

function ChapterRow({ chapter }: { chapter: Chapter }) {
  return (
    <tr className={chapter.status === "failed" ? "row--error" : ""}>
      <td className="mono">{String(chapter.number).padStart(2, "0")}</td>
      <td>{chapter.title}</td>
      <td>
        <span className={`badge badge--${chapter.status}`}>
          {STATUS_ICON[chapter.status] ?? chapter.status}{" "}
          {STATUS_LABELS[chapter.status] ?? chapter.status}
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

function duration(start: string | null, end: string | null): string {
  if (!start) return "—";
  const from = new Date(start).getTime();
  const to = end ? new Date(end).getTime() : Date.now();
  const s = Math.round((to - from) / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}min ${rem}s`;
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
    0,
  );
  const overBudget =
    parseFloat(data.total_cost_eur) > parseFloat(data.budget_eur);

  return (
    <div className="page">
      <h1>
        {data.offer_name}
        <span className={`badge badge--${data.status} ml-2`}>
          {STATUS_ICON[data.status] ?? data.status}{" "}
          {STATUS_LABELS[data.status] ?? data.status}
        </span>
      </h1>

      <Pipeline job={data} />

      <div className="detail-meta">
        <span>Client : {data.customer_email}</span>
        <span>Durée : {duration(data.started_at, data.completed_at)}</span>
        <span>
          Coût : {parseFloat(data.total_cost_eur).toFixed(4)} €
          {overBudget && <strong className="text-error"> ⚠ Dépassé</strong>}
        </span>
        <span>Budget : {parseFloat(data.budget_eur).toFixed(2)} €</span>
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
