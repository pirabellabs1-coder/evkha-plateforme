import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Box, Flex, Heading, Badge, Table, Text, Callout, Spinner } from "@radix-ui/themes";
import { api, type Incident } from "../api";

type RadixColor = "red" | "amber" | "green" | "gray";

function severityColor(severity: string): RadixColor {
  const map: Record<string, RadixColor> = {
    critical: "red", high: "red", medium: "amber", low: "green",
  };
  return map[severity] ?? "gray";
}

function IncidentTable({ incidents }: { incidents: Incident[] }) {
  return (
    <Table.Root variant="surface">
      <Table.Header>
        <Table.Row>
          <Table.ColumnHeaderCell>Titre</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Sévérité</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Créé le</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Job</Table.ColumnHeaderCell>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {incidents.map((inc) => (
          <Table.Row key={inc.id}>
            <Table.Cell>
              <Text size="2">{inc.title}</Text>
            </Table.Cell>
            <Table.Cell>
              <Badge
                color={severityColor(inc.severity)}
                variant={inc.severity === "critical" ? "solid" : "soft"}
                size="1"
              >
                {inc.severity}
              </Badge>
            </Table.Cell>
            <Table.Cell>
              <Text size="2" color="gray">{inc.status}</Text>
            </Table.Cell>
            <Table.Cell>
              <Text size="1" color="gray" className="mono">
                {new Date(inc.created_at).toLocaleString("fr-FR")}
              </Text>
            </Table.Cell>
            <Table.Cell>
              {inc.job_id ? (
                <Link to="/jobs/$jobId" params={{ jobId: inc.job_id }}
                  style={{ color: "var(--accent-9)", textDecoration: "none", fontSize: 13 }}>
                  Voir →
                </Link>
              ) : (
                <Text size="2" color="gray">—</Text>
              )}
            </Table.Cell>
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
  const resolved = data?.filter((i) => i.status !== "open") ?? [];

  return (
    <Box>
      <Flex justify="between" align="center" mb="5">
        <Heading size="6">Incidents opérationnels</Heading>
        {isLoading && <Spinner size="2" />}
      </Flex>

      {!isLoading && open.length === 0 && (
        <Callout.Root color="green" mb="5">
          <Callout.Text>Aucun incident ouvert ✓</Callout.Text>
        </Callout.Root>
      )}

      {open.length > 0 && (
        <Box mb="6">
          <Heading size="4" color="red" mb="3">
            Ouverts ({open.length})
          </Heading>
          <IncidentTable incidents={open} />
        </Box>
      )}

      {resolved.length > 0 && (
        <Box>
          <Heading size="4" mb="3">Résolus récemment</Heading>
          <IncidentTable incidents={resolved} />
        </Box>
      )}
    </Box>
  );
}
