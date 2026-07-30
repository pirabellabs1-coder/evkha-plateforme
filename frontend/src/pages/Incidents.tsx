import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Box, Flex, Heading, Badge, Table, Text, Callout, Spinner, Button, Dialog, Code,
} from "@radix-ui/themes";
import { api, type Incident } from "../api";

type RadixColor = "red" | "amber" | "green" | "gray";

function severityColor(severity: string): RadixColor {
  const map: Record<string, RadixColor> = {
    critical: "red", high: "red", medium: "amber", low: "green",
  };
  return map[severity] ?? "gray";
}

const SEVERITY_LABELS: Record<string, string> = {
  critical: "Critique", high: "Haute", medium: "Moyenne", low: "Faible",
};

function DetailsDialog({ details }: { details: Record<string, unknown> }) {
  if (!details || Object.keys(details).length === 0) return null;
  return (
    <Dialog.Root>
      <Dialog.Trigger>
        <Button variant="ghost" size="1" color="gray">Détails</Button>
      </Dialog.Trigger>
      <Dialog.Content maxWidth="600px">
        <Dialog.Title>Détails de l'incident</Dialog.Title>
        <Box
          style={{
            background: "var(--gray-2)",
            borderRadius: 6,
            padding: 16,
            maxHeight: 400,
            overflow: "auto",
          }}
        >
          <Code size="1" style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
            {JSON.stringify(details, null, 2)}
          </Code>
        </Box>
        <Flex justify="end" mt="4">
          <Dialog.Close>
            <Button variant="soft" color="gray">Fermer</Button>
          </Dialog.Close>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

function ResolveButton({ incident, onResolved }: {
  incident: Incident;
  onResolved: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => api.incidentResolve(incident.id),
    onSuccess: () => {
      setError(null);
      onResolved();
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  return (
    <Flex direction="column" align="start" gap="1">
      <Button
        size="1"
        variant="soft"
        color="green"
        loading={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        Résoudre
      </Button>
      {error && <Text size="1" color="red">{error}</Text>}
    </Flex>
  );
}

function IncidentTable({ incidents, canResolve }: { incidents: Incident[]; canResolve?: boolean }) {
  const queryClient = useQueryClient();

  return (
    <Table.Root variant="surface">
      <Table.Header>
        <Table.Row>
          <Table.ColumnHeaderCell>Titre</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Sévérité</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Créé le</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Job</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Détails</Table.ColumnHeaderCell>
          {canResolve && <Table.ColumnHeaderCell>Action</Table.ColumnHeaderCell>}
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {incidents.map((inc) => (
          <Table.Row key={inc.id}>
            <Table.Cell>
              <Text size="2" weight="medium">{inc.title}</Text>
            </Table.Cell>
            <Table.Cell>
              <Badge
                color={severityColor(inc.severity)}
                variant={inc.severity === "critical" ? "solid" : "soft"}
                size="1"
              >
                {SEVERITY_LABELS[inc.severity] ?? inc.severity}
              </Badge>
            </Table.Cell>
            <Table.Cell>
              <Text size="1" color="gray" className="mono">
                {new Date(inc.created_at).toLocaleString("fr-FR")}
              </Text>
              {inc.resolved_at && (
                <Text size="1" color="green" as="p" className="mono">
                  Résolu {new Date(inc.resolved_at).toLocaleString("fr-FR")}
                </Text>
              )}
            </Table.Cell>
            <Table.Cell>
              {inc.job_id ? (
                <Link
                  to="/admin/jobs/$jobId"
                  params={{ jobId: inc.job_id }}
                  style={{ color: "var(--accent-9)", textDecoration: "none", fontSize: 13 }}
                >
                  Voir →
                </Link>
              ) : (
                <Text size="2" color="gray">—</Text>
              )}
            </Table.Cell>
            <Table.Cell>
              <DetailsDialog details={inc.details} />
            </Table.Cell>
            {canResolve && (
              <Table.Cell>
                <ResolveButton
                  incident={inc}
                  onResolved={() => {
                    queryClient.invalidateQueries({ queryKey: ["incidents"] });
                    queryClient.invalidateQueries({ queryKey: ["overview"] });
                  }}
                />
              </Table.Cell>
            )}
          </Table.Row>
        ))}
      </Table.Body>
    </Table.Root>
  );
}

export function Incidents() {
  const { data, isLoading } = useQuery<Incident[]>({
    queryKey: ["incidents"],
    queryFn: api.incidents,
    refetchInterval: 30_000,
  });

  const open = data?.filter((i) => i.status === "open") ?? [];
  const inProgress = data?.filter((i) => i.status === "acknowledged") ?? [];
  const resolved = data?.filter((i) => i.status === "resolved") ?? [];

  return (
    <Box>
      <Flex justify="between" align="center" mb="5">
        <Box>
          <Heading size="6">Incidents opérationnels</Heading>
          <Text size="2" color="gray" as="p" mt="1">
            Cliquez sur "Résoudre" pour clôturer un incident
          </Text>
        </Box>
        {isLoading && <Spinner size="2" />}
      </Flex>

      {!isLoading && open.length === 0 && inProgress.length === 0 && (
        <Callout.Root color="green" mb="5">
          <Callout.Text>Aucun incident ouvert ✓</Callout.Text>
        </Callout.Root>
      )}

      {open.length > 0 && (
        <Box mb="6">
          <Heading size="4" color="red" mb="3">
            Ouverts ({open.length})
          </Heading>
          <IncidentTable incidents={open} canResolve />
        </Box>
      )}

      {inProgress.length > 0 && (
        <Box mb="6">
          <Heading size="4" color="amber" mb="3">
            Pris en compte ({inProgress.length})
          </Heading>
          <IncidentTable incidents={inProgress} canResolve />
        </Box>
      )}

      {resolved.length > 0 && (
        <Box>
          <Heading size="4" mb="3">Résolus récemment ({resolved.length})</Heading>
          <IncidentTable incidents={resolved} />
        </Box>
      )}
    </Box>
  );
}
