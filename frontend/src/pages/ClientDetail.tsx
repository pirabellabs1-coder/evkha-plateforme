import { useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Box, Flex, Heading, Badge, Card, Table, Text, Callout, Spinner,
} from "@radix-ui/themes";
import { api, type CustomerDetail, type OrderSummary } from "../api";
import { TIER_LABELS } from "../constants/tiers";
import { ORDER_STATUS_LABELS, orderStatusColor } from "../constants/orders";

function OrderRow({ order }: { order: OrderSummary }) {
  const label = order.parent_order_id
    ? `Ticket · ${order.period_year_month || "—"}`
    : order.offer_name;

  return (
    <Table.Row>
      <Table.Cell>
        <Text size="2">{label}</Text>
        {order.parent_order_id && (
          <Text size="1" color="gray" as="p">Crédit abonnement</Text>
        )}
      </Table.Cell>
      <Table.Cell>
        <Badge color={orderStatusColor(order.status)} variant="soft" size="1">
          {ORDER_STATUS_LABELS[order.status] ?? order.status}
        </Badge>
      </Table.Cell>
      <Table.Cell>
        <Text size="1" color="gray" className="mono">
          {new Date(order.created_at).toLocaleDateString("fr-FR")}
        </Text>
      </Table.Cell>
    </Table.Row>
  );
}

export function ClientDetail() {
  const { clientId } = useParams({ from: "/admin/clients/$clientId" });
  const { data, isLoading, error } = useQuery<CustomerDetail>({
    queryKey: ["customer", clientId],
    queryFn: () => api.customer(clientId),
    refetchInterval: 30_000,
  });

  if (isLoading) return (
    <Flex align="center" gap="2">
      <Spinner size="2" />
      <Text color="gray">Chargement…</Text>
    </Flex>
  );
  if (error || !data) return <Text color="red">Client introuvable.</Text>;

  const activeSub = data.subscriptions.find((s) => s.status === "active");
  const parentOrders = data.orders.filter((o) => !o.parent_order_id);
  const tickets = data.orders.filter((o) => !!o.parent_order_id);

  return (
    <Box>
      <Flex align="center" gap="3" mb="1">
        <Link
          to="/admin/clients"
          style={{ color: "var(--gray-9)", textDecoration: "none", fontSize: 13 }}
        >
          ← Clients
        </Link>
      </Flex>

      <Heading size="6" mt="3" mb="1">{data.email}</Heading>
      {(data.first_name || data.last_name || data.company_name) && (
        <Text size="2" color="gray" as="p" mb="5">
          {[data.first_name, data.last_name].filter(Boolean).join(" ")}
          {data.company_name ? ` · ${data.company_name}` : ""}
        </Text>
      )}

      {/* Infos abonnement */}
      {activeSub ? (
        <Callout.Root color="green" mb="5">
          <Callout.Text>
            Abonnement actif : <strong>{TIER_LABELS[activeSub.tier] ?? activeSub.tier}</strong>
            {" — "}{data.credits_available} crédit{data.credits_available > 1 ? "s" : ""} en attente d'utilisation
          </Callout.Text>
        </Callout.Root>
      ) : (
        <Callout.Root color="gray" mb="5">
          <Callout.Text>Aucun abonnement actif · {data.credits_available} crédit(s) disponible(s)</Callout.Text>
        </Callout.Root>
      )}

      {/* Méta */}
      <Card mb="5">
        <Flex wrap="wrap" gap="4">
          <Text size="2" color="gray">
            Type : <Text as="span" weight="medium" style={{ color: "var(--gray-12)" }}>
              {data.customer_type.toUpperCase()}
            </Text>
          </Text>
          <Text size="2" color="gray">
            Inscrit : <Text as="span" style={{ color: "var(--gray-12)" }}>
              {new Date(data.created_at).toLocaleDateString("fr-FR")}
            </Text>
          </Text>
          <Text size="2" color="gray">
            Commandes : <Text as="span" style={{ color: "var(--gray-12)" }}>
              {parentOrders.length}
            </Text>
          </Text>
          <Text size="2" color="gray">
            Tickets crédit : <Text as="span" style={{ color: "var(--gray-12)" }}>
              {tickets.length}
            </Text>
          </Text>
        </Flex>
      </Card>

      {/* Historique abonnements */}
      {data.subscriptions.length > 0 && (
        <Box mb="6">
          <Heading size="4" mb="3">Abonnements</Heading>
          <Table.Root variant="surface">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeaderCell>Formule</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Début</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Fin</Table.ColumnHeaderCell>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {data.subscriptions.map((s) => (
                <Table.Row key={s.id}>
                  <Table.Cell>
                    <Text size="2">{TIER_LABELS[s.tier] ?? s.tier}</Text>
                  </Table.Cell>
                  <Table.Cell>
                    <Badge
                      color={s.status === "active" ? "green" : "gray"}
                      variant="soft"
                      size="1"
                    >
                      {s.status === "active" ? "Actif" : s.status === "cancelled" ? "Annulé" : "Expiré"}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell>
                    <Text size="1" color="gray" className="mono">
                      {s.starts_at ? new Date(s.starts_at).toLocaleDateString("fr-FR") : "—"}
                    </Text>
                  </Table.Cell>
                  <Table.Cell>
                    <Text size="1" color="gray" className="mono">
                      {s.ends_at ? new Date(s.ends_at).toLocaleDateString("fr-FR") : "—"}
                    </Text>
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </Box>
      )}

      {/* Commandes */}
      {parentOrders.length > 0 && (
        <Box mb="6">
          <Heading size="4" mb="3">Commandes ({parentOrders.length})</Heading>
          <Table.Root variant="surface">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeaderCell>Offre</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Date</Table.ColumnHeaderCell>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {parentOrders.map((o) => <OrderRow key={o.id} order={o} />)}
            </Table.Body>
          </Table.Root>
        </Box>
      )}

      {/* Tickets de crédit */}
      {tickets.length > 0 && (
        <Box mb="6">
          <Heading size="4" mb="3">
            Tickets de crédit ({tickets.length})
            {data.credits_available > 0 && (
              <Badge color="amber" variant="soft" size="1" ml="3">
                {data.credits_available} en attente
              </Badge>
            )}
          </Heading>
          <Table.Root variant="surface">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeaderCell>Période</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Date</Table.ColumnHeaderCell>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {tickets.map((o) => <OrderRow key={o.id} order={o} />)}
            </Table.Body>
          </Table.Root>
        </Box>
      )}

      {data.orders.length === 0 && (
        <Callout.Root color="gray">
          <Callout.Text>Aucune commande enregistrée pour ce client.</Callout.Text>
        </Callout.Root>
      )}
    </Box>
  );
}
