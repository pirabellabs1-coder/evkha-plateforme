import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Box, Flex, Heading, Badge, Table, Progress, Text, Select, Spinner, Button,
} from "@radix-ui/themes";
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

type RadixColor = "gray" | "blue" | "green" | "red";

function statusColor(status: string): RadixColor {
  const map: Record<string, RadixColor> = {
    pending: "gray", running: "blue", done: "green", failed: "red", cancelled: "gray",
  };
  return map[status] ?? "gray";
}

function JobRowActions({ job }: { job: JobSummary }) {
  const queryClient = useQueryClient();
  const [emailQueued, setEmailQueued] = useState(false);

  const emailMutation = useMutation({
    mutationFn: () => api.jobSendEmail(job.id),
    onSuccess: () => {
      setEmailQueued(true);
      const timer = setInterval(() => {
        queryClient.invalidateQueries({ queryKey: ["jobs"] });
      }, 3_000);
      setTimeout(() => clearInterval(timer), 60_000);
    },
  });

  const hasPdf = !!job.pdf_download_url;
  const deliverySent = job.delivery_status === "sent";
  const pendingConfirmation = emailQueued && !deliverySent;

  return (
    <Flex gap="1" align="center">
      {hasPdf ? (
        <Button asChild size="1" variant="ghost" color="green">
          <a href={job.pdf_download_url!} target="_blank" rel="noreferrer">
            ↓ PDF
          </a>
        </Button>
      ) : (
        <Button size="1" variant="ghost" color="green" disabled>
          ↓ PDF
        </Button>
      )}
      <Button
        size="1"
        variant="ghost"
        color={deliverySent && !pendingConfirmation ? "green" : "blue"}
        disabled={!hasPdf || emailMutation.isPending || pendingConfirmation}
        loading={emailMutation.isPending}
        onClick={() => emailMutation.mutate()}
        title={deliverySent ? "Email envoyé — renvoyer ?" : "Envoyer par email"}
      >
        {pendingConfirmation ? "…" : deliverySent ? "✓" : "✉"}
      </Button>
    </Flex>
  );
}

export function Jobs() {
  const [statusFilter, setStatusFilter] = useState("all");

  const { data, isLoading } = useQuery<JobSummary[]>({
    queryKey: ["jobs", statusFilter],
    queryFn: () => api.jobs(statusFilter === "all" ? undefined : statusFilter),
    refetchInterval: 15_000,
  });

  return (
    <Box>
      <Heading size="6" mb="5">Livrables</Heading>

      <Flex align="center" gap="3" mb="4">
        <Select.Root value={statusFilter} onValueChange={setStatusFilter} size="2">
          <Select.Trigger placeholder="Tous les statuts" />
          <Select.Content>
            <Select.Item value="all">Tous les statuts</Select.Item>
            {Object.entries(STATUS_LABELS).map(([k, v]) => (
              <Select.Item key={k} value={k}>{v}</Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
        {isLoading && <Spinner size="2" />}
      </Flex>

      {data && (
        <Table.Root variant="surface">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeaderCell>Livrable</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Progression</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Coût</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Terminé le</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Actions</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell />
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {data.map((job) => (
              <Table.Row
                key={job.id}
                style={job.status === "failed" ? { background: "var(--red-2)" } : undefined}
              >
                <Table.Cell>
                  <Text size="2">{DELIVERABLE_LABELS[job.deliverable_type] ?? job.deliverable_type}</Text>
                </Table.Cell>
                <Table.Cell>
                  <Badge color={statusColor(job.status)} variant="soft">
                    {STATUS_LABELS[job.status] ?? job.status}
                  </Badge>
                </Table.Cell>
                <Table.Cell>
                  <Flex align="center" gap="2">
                    <Progress
                      value={job.chapters_total > 0
                        ? Math.round((job.chapters_done / job.chapters_total) * 100)
                        : 0}
                      size="1"
                      style={{ width: 80 }}
                    />
                    <Text size="1" color="gray" className="mono">
                      {job.chapters_done}/{job.chapters_total}
                    </Text>
                  </Flex>
                </Table.Cell>
                <Table.Cell>
                  <Text size="2" className="mono">
                    {parseFloat(job.total_cost_eur).toFixed(4)} €
                  </Text>
                </Table.Cell>
                <Table.Cell>
                  <Text size="1" color="gray" className="mono">
                    {job.completed_at
                      ? new Date(job.completed_at).toLocaleDateString("fr-FR")
                      : "—"}
                  </Text>
                </Table.Cell>
                <Table.Cell>
                  {job.status === "done" && <JobRowActions job={job} />}
                </Table.Cell>
                <Table.Cell>
                  <Link to="/jobs/$jobId" params={{ jobId: job.id }}
                    style={{ color: "var(--accent-9)", textDecoration: "none", fontSize: 13 }}>
                    Détail →
                  </Link>
                </Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      )}

      {data?.length === 0 && (
        <Text color="gray" size="2" style={{ fontStyle: "italic" }}>
          Aucun livrable{statusFilter !== "all" ? " pour ce statut" : ""}.
        </Text>
      )}
    </Box>
  );
}
