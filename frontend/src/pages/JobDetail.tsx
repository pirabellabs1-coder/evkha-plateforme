import { useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Box, Flex, Heading, Badge, Card, Table, Text, Callout, Spinner,
} from "@radix-ui/themes";
import { api, type Chapter, type JobDetail as JobDetailType } from "../api";

const STATUS_ICON: Record<string, string> = {
  done: "✓", running: "⚡", failed: "✗", pending: "○", skipped: "—",
};

const STATUS_LABELS: Record<string, string> = {
  done: "Terminé", running: "En cours", failed: "Échec", pending: "En attente", skipped: "Ignoré",
};

type RadixColor = "gray" | "blue" | "green" | "red";

function statusColor(status: string): RadixColor {
  const map: Record<string, RadixColor> = {
    pending: "gray", running: "blue", done: "green", failed: "red", skipped: "gray",
  };
  return map[status] ?? "gray";
}

function Pipeline({ job }: { job: JobDetailType }) {
  const genStatus =
    job.status === "done" ? "done"
    : job.status === "failed" ? "failed"
    : job.status === "running" ? "running"
    : "pending";

  const stages = [
    {
      key: "order", label: "Commande reçue",
      sub: job.order_id ? `#${job.order_id.slice(0, 8)}` : null,
      status: "done" as const, icon: "✓",
    },
    {
      key: "gen", label: "Génération IA",
      sub: `${job.chapters_done}/${job.chapters_total} chapitres`,
      status: genStatus as "done" | "running" | "failed" | "pending",
      icon: genStatus === "done" ? "✓" : genStatus === "running" ? "⚡" : genStatus === "failed" ? "✗" : "○",
    },
    {
      key: "pdf", label: "Assemblage PDF", sub: null,
      status: (job.status === "done" ? "done" : "pending") as "done" | "pending",
      icon: job.status === "done" ? "✓" : "○",
    },
    {
      key: "email", label: "Email envoyé",
      sub: job.customer_email ?? null,
      status: (job.status === "done" ? "done" : "pending") as "done" | "pending",
      icon: job.status === "done" ? "✓" : "○",
    },
  ];

  return (
    <Card mb="4">
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
    </Card>
  );
}

function ChapterRow({ chapter }: { chapter: Chapter }) {
  return (
    <Table.Row style={chapter.status === "failed" ? { background: "var(--red-2)" } : undefined}>
      <Table.Cell>
        <Text size="1" className="mono">{String(chapter.number).padStart(2, "0")}</Text>
      </Table.Cell>
      <Table.Cell>
        <Text size="2">{chapter.title}</Text>
        {chapter.error_message && (
          <Text size="1" color="red" as="p">{chapter.error_message}</Text>
        )}
      </Table.Cell>
      <Table.Cell>
        <Badge color={statusColor(chapter.status)} variant="soft" size="1">
          {STATUS_ICON[chapter.status] ?? chapter.status}{" "}
          {STATUS_LABELS[chapter.status] ?? chapter.status}
        </Badge>
      </Table.Cell>
      <Table.Cell>
        <Text size="1" className="mono">{chapter.input_tokens.toLocaleString()}</Text>
      </Table.Cell>
      <Table.Cell>
        <Text size="1" className="mono">{chapter.output_tokens.toLocaleString()}</Text>
      </Table.Cell>
      <Table.Cell>
        <Text size="1" className="mono">{parseFloat(chapter.cost_eur).toFixed(4)} €</Text>
      </Table.Cell>
    </Table.Row>
  );
}

function duration(start: string | null, end: string | null): string {
  if (!start) return "—";
  const from = new Date(start).getTime();
  const to = end ? new Date(end).getTime() : Date.now();
  const s = Math.round((to - from) / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}min ${s % 60}s`;
}

export function JobDetail() {
  const { jobId } = useParams({ from: "/jobs/$jobId" });
  const { data, isLoading, error } = useQuery<JobDetailType>({
    queryKey: ["job", jobId],
    queryFn: () => api.job(jobId),
    refetchInterval: (q) => q.state.data?.status === "running" ? 5_000 : false,
  });

  if (isLoading) return (
    <Flex align="center" gap="2">
      <Spinner size="2" />
      <Text color="gray">Chargement…</Text>
    </Flex>
  );
  if (error || !data) return <Text color="red">Job introuvable.</Text>;

  const totalTokens = data.chapters.reduce(
    (acc, c) => acc + c.input_tokens + c.output_tokens, 0,
  );
  const overBudget = parseFloat(data.total_cost_eur) > parseFloat(data.budget_eur);

  return (
    <Box>
      <Flex align="center" gap="3" mb="5">
        <Heading size="6">{data.offer_name}</Heading>
        <Badge color={statusColor(data.status)} variant="soft" size="2">
          {STATUS_ICON[data.status] ?? data.status}{" "}
          {STATUS_LABELS[data.status] ?? data.status}
        </Badge>
      </Flex>

      <Pipeline job={data} />

      <Card mb="4">
        <Flex wrap="wrap" gap="4">
          <Text size="2" color="gray">Client : <Text as="span" weight="medium" color="gray" style={{ color: "var(--gray-12)" }}>{data.customer_email}</Text></Text>
          <Text size="2" color="gray">Durée : <Text as="span" style={{ color: "var(--gray-12)" }}>{duration(data.started_at, data.completed_at)}</Text></Text>
          <Text size="2" color="gray">
            Coût : <Text as="span" style={{ color: overBudget ? "var(--red-11)" : "var(--gray-12)" }}>
              {parseFloat(data.total_cost_eur).toFixed(4)} €{overBudget ? " ⚠ Dépassé" : ""}
            </Text>
          </Text>
          <Text size="2" color="gray">Budget : <Text as="span" style={{ color: "var(--gray-12)" }}>{parseFloat(data.budget_eur).toFixed(2)} €</Text></Text>
          <Text size="2" color="gray">Tokens : <Text as="span" style={{ color: "var(--gray-12)" }}>{totalTokens.toLocaleString()}</Text></Text>
          {data.started_at && (
            <Text size="2" color="gray">Démarré : <Text as="span" style={{ color: "var(--gray-12)" }}>{new Date(data.started_at).toLocaleString("fr-FR")}</Text></Text>
          )}
          {data.completed_at && (
            <Text size="2" color="gray">Terminé : <Text as="span" style={{ color: "var(--gray-12)" }}>{new Date(data.completed_at).toLocaleString("fr-FR")}</Text></Text>
          )}
        </Flex>
      </Card>

      {data.error_message && (
        <Callout.Root color="red" mb="4">
          <Callout.Text>{data.error_message}</Callout.Text>
        </Callout.Root>
      )}

      <Heading size="4" mb="3">
        Chapitres — {data.chapters_done}/{data.chapters_total} terminés
      </Heading>

      <Table.Root variant="surface">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>#</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Titre</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Tokens in</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Tokens out</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Coût</Table.ColumnHeaderCell>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {data.chapters.map((c) => (
            <ChapterRow key={c.number} chapter={c} />
          ))}
          <Table.Row>
            <Table.Cell colSpan={5}>
              <Text size="2" weight="bold" className="text-right">Total</Text>
            </Table.Cell>
            <Table.Cell>
              <Text size="2" weight="bold" className="mono">
                {parseFloat(data.total_cost_eur).toFixed(4)} €
              </Text>
            </Table.Cell>
          </Table.Row>
        </Table.Body>
      </Table.Root>
    </Box>
  );
}
