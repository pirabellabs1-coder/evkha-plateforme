import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Box, Flex, Heading, Badge, Table, Text, Select, Spinner, Callout,
} from "@radix-ui/themes";
import { api, type OrderSummary } from "../api";

const STATUS_LABELS: Record<string, string> = {
  received: "Reçue",
  waiting_intake: "En attente formulaire",
  processing: "En traitement",
  delivered: "Livrée",
  failed: "Échec",
  cancelled: "Annulée",
};

const KIND_LABELS: Record<string, string> = {
  all: "Toutes",
  b2c: "B2C — achat unitaire",
  parent: "Abonnements (parent)",
  ticket: "Tickets de crédit",
};

const DELIVERABLE_LABELS: Record<string, string> = {
  market_study: "EM",
  competitor_study: "EC",
  business_plan: "BP",
  business_strategy: "STR",
};

type RadixColor = "gray" | "blue" | "green" | "amber" | "red";

function statusColor(status: string): RadixColor {
  const map: Record<string, RadixColor> = {
    received: "gray",
    waiting_intake: "amber",
    processing: "blue",
    delivered: "green",
    failed: "red",
    cancelled: "gray",
  };
  return map[status] ?? "gray";
}

export function Orders() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [kindFilter, setKindFilter] = useState("all");

  const params: Record<string, string> = {};
  if (statusFilter !== "all") params.status = statusFilter;
  if (kindFilter !== "all") params.kind = kindFilter;

  const { data, isLoading } = useQuery<OrderSummary[]>({
    queryKey: ["orders", statusFilter, kindFilter],
    queryFn: () => api.orders(Object.keys(params).length ? params : undefined),
    refetchInterval: 30_000,
  });

  return (
    <Box>
      <Flex justify="between" align="center" mb="5">
        <Box>
          <Heading size="6">Commandes</Heading>
          <Text size="2" color="gray" as="p" mt="1">
            Toutes les commandes B2C, abonnements et tickets de crédit
          </Text>
        </Box>
        {isLoading && <Spinner size="2" />}
      </Flex>

      <Flex align="center" gap="3" mb="4" wrap="wrap">
        <Select.Root value={kindFilter} onValueChange={setKindFilter} size="2">
          <Select.Trigger placeholder="Type" />
          <Select.Content>
            {Object.entries(KIND_LABELS).map(([k, v]) => (
              <Select.Item key={k} value={k}>{v}</Select.Item>
            ))}
          </Select.Content>
        </Select.Root>

        <Select.Root value={statusFilter} onValueChange={setStatusFilter} size="2">
          <Select.Trigger placeholder="Statut" />
          <Select.Content>
            <Select.Item value="all">Tous les statuts</Select.Item>
            {Object.entries(STATUS_LABELS).map(([k, v]) => (
              <Select.Item key={k} value={k}>{v}</Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </Flex>

      {data?.length === 0 && (
        <Callout.Root color="gray">
          <Callout.Text>Aucune commande pour ces filtres.</Callout.Text>
        </Callout.Root>
      )}

      {data && data.length > 0 && (
        <Table.Root variant="surface">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeaderCell>Commande</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Client</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Type</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Période</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Date</Table.ColumnHeaderCell>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {data.map((order) => {
              const isTicket = !!order.parent_order_id;
              const badge = isTicket
                ? "Ticket"
                : order.is_subscription
                  ? "Abonnement"
                  : order.is_extra_credit
                    ? "Crédit supp."
                    : "B2C";
              const badgeColor: RadixColor = isTicket
                ? "amber"
                : order.is_subscription
                  ? "blue"
                  : order.is_extra_credit
                    ? "green"
                    : "gray";

              return (
                <Table.Row
                  key={order.id}
                  style={order.status === "failed" ? { background: "var(--red-2)" } : undefined}
                >
                  <Table.Cell>
                    <Text size="2">{order.offer_name}</Text>
                    {order.deliverable_type && (
                      <Text size="1" color="gray" as="p">
                        {DELIVERABLE_LABELS[order.deliverable_type] ?? order.deliverable_type}
                      </Text>
                    )}
                  </Table.Cell>
                  <Table.Cell>
                    <Link
                      to="/clients/$clientId"
                      params={{ clientId: order.customer_id }}
                      style={{ color: "var(--accent-9)", textDecoration: "none", fontSize: 13 }}
                    >
                      {order.customer_email}
                    </Link>
                  </Table.Cell>
                  <Table.Cell>
                    <Badge color={badgeColor} variant="soft" size="1">{badge}</Badge>
                  </Table.Cell>
                  <Table.Cell>
                    <Badge color={statusColor(order.status)} variant="soft" size="1">
                      {STATUS_LABELS[order.status] ?? order.status}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell>
                    <Text size="1" color="gray" className="mono">
                      {order.period_year_month || "—"}
                    </Text>
                  </Table.Cell>
                  <Table.Cell>
                    <Text size="1" color="gray" className="mono">
                      {new Date(order.created_at).toLocaleDateString("fr-FR")}
                    </Text>
                  </Table.Cell>
                </Table.Row>
              );
            })}
          </Table.Body>
        </Table.Root>
      )}
    </Box>
  );
}
