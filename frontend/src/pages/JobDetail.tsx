import { useState } from "react";
import { useParams } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Box, Flex, Heading, Badge, Card, Table, Text, Callout, Spinner, Button,
} from "@radix-ui/themes";
import { api, type Chapter, type JobDetail as JobDetailType, type Artifact } from "../api";

const STATUS_ICON: Record<string, string> = {
  done: "✓", running: "⚡", failed: "✗", pending: "○", skipped: "—",
};

const STATUS_LABELS: Record<string, string> = {
  done: "Terminé", running: "En cours", failed: "Échec", pending: "En attente", skipped: "Ignoré",
};

const DELIVERABLE_LABELS: Record<string, string> = {
  market_study: "Étude de marché",
  competitor_study: "Étude de concurrence",
  business_plan: "Business Plan",
  business_strategy: "Stratégie Business",
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

  const deliverySent   = job.delivery?.status === "sent";
  const deliveryFailed = job.delivery?.status === "failed";
  const genDone        = job.status === "done";

  // Assemblage PDF : en cours si gen terminée mais livraison pas encore envoyée
  const pdfStatus = deliverySent ? "done"
    : deliveryFailed ? "failed"
    : genDone ? "running"
    : "pending";
  const pdfIcon = deliverySent ? "✓" : deliveryFailed ? "✗" : genDone ? "⚡" : "○";

  // Email envoyé : uniquement quand le batch est confirmé SENT
  const emailStatus = deliverySent ? "done" : deliveryFailed ? "failed" : "pending";
  const emailIcon   = deliverySent ? "✓" : deliveryFailed ? "✗" : "○";

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
      status: pdfStatus as "done" | "running" | "failed" | "pending",
      icon: pdfIcon,
    },
    {
      key: "email", label: "Email envoyé",
      sub: deliverySent ? (job.customer_email ?? null) : null,
      status: emailStatus as "done" | "failed" | "pending",
      icon: emailIcon,
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

function ArtifactSection({ artifacts }: { artifacts: Artifact[] }) {
  const ready = artifacts.filter((a) => a.status === "ready" && a.download_url);
  if (ready.length === 0) return null;

  const KIND_LABELS: Record<string, string> = {
    pdf: "PDF",
    docx: "Word (DOCX)",
    gamma_pdf: "Gamma PDF",
    gamma_pptx: "Gamma PPTX",
    link: "Lien",
  };

  return (
    <Card mb="4" style={{ borderColor: "var(--green-7)", background: "var(--green-1)" }}>
      <Flex align="center" justify="between" wrap="wrap" gap="3">
        <Text size="2" weight="medium" style={{ color: "var(--green-11)" }}>
          Document prêt — télécharger le livrable
        </Text>
        <Flex gap="2" wrap="wrap">
          {ready.map((a) => (
            <a
              key={a.id}
              href={a.download_url}
              target="_blank"
              rel="noreferrer"
              style={{ textDecoration: "none" }}
            >
              <Button size="2" variant="soft" color="green">
                Télécharger {KIND_LABELS[a.kind] ?? a.kind}
              </Button>
            </a>
          ))}
        </Flex>
      </Flex>
    </Card>
  );
}

function RelaunchButton({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => api.jobRelaunch(jobId),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  return (
    <Flex direction="column" align="end" gap="1">
      <Button size="2" variant="soft" color="orange" loading={mutation.isPending} onClick={() => mutation.mutate()}>
        Relancer la génération
      </Button>
      {error && <Text size="1" color="red">{error}</Text>}
    </Flex>
  );
}

function SendEmailButton({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [queued, setQueued] = useState(false);

  const mutation = useMutation({
    mutationFn: () => api.jobSendEmail(jobId),
    onSuccess: () => {
      setError(null);
      setQueued(true);
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      }, 8_000);
    },
    onError: (err: Error) => setError(err.message),
  });

  return (
    <Flex direction="column" align="end" gap="1">
      <Button
        size="2"
        variant="soft"
        color="blue"
        loading={mutation.isPending}
        disabled={queued}
        onClick={() => mutation.mutate()}
      >
        {queued ? "Email en cours…" : "Envoyer par email"}
      </Button>
      {error && <Text size="1" color="red">{error}</Text>}
    </Flex>
  );
}

export function JobDetail() {
  const { jobId } = useParams({ from: "/jobs/$jobId" });
  const { data, isLoading, error } = useQuery<JobDetailType>({
    queryKey: ["job", jobId],
    queryFn: () => api.job(jobId),
    refetchInterval: (q) => (q.state.data === undefined || q.state.data.status === "running") ? 5_000 : false,
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
  const canRelaunch  = data.status === "failed" || data.status === "cancelled";
  const canSendEmail = data.status === "done";

  return (
    <Box>
      <Flex align="center" gap="2" mb="3">
        <Link
          to="/jobs"
          style={{ color: "var(--gray-9)", textDecoration: "none", fontSize: 13 }}
        >
          ← Livrables
        </Link>
      </Flex>

      <Flex align="center" justify="between" gap="3" mb="5" wrap="wrap">
        <Flex align="center" gap="3">
          <Heading size="6">{data.offer_name}</Heading>
          <Badge color={statusColor(data.status)} variant="soft" size="2">
            {STATUS_ICON[data.status] ?? data.status}{" "}
            {STATUS_LABELS[data.status] ?? data.status}
          </Badge>
        </Flex>
        {canRelaunch  && <RelaunchButton jobId={jobId} />}
        {canSendEmail && <SendEmailButton jobId={jobId} />}
      </Flex>

      <Pipeline job={data} />

      {/* Artéfacts téléchargeables */}
      {data.artifacts && <ArtifactSection artifacts={data.artifacts} />}

      <Card mb="4">
        <Flex wrap="wrap" gap="4">
          <Text size="2" color="gray">
            Client :{" "}
            <Link
              to="/clients/$clientId"
              params={{ clientId: data.customer_id }}
              style={{ color: "var(--accent-9)", textDecoration: "none" }}
            >
              {data.customer_email}
            </Link>
          </Text>
          <Text size="2" color="gray">
            Livrable :{" "}
            <Text as="span" style={{ color: "var(--gray-12)" }}>
              {DELIVERABLE_LABELS[data.deliverable_type] ?? data.deliverable_type}
            </Text>
          </Text>
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
