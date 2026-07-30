import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Box, Flex, Badge, Table, Text, Select, Spinner, Callout,
} from "@radix-ui/themes";
import { api, type CustomerSummary } from "../api";
import { TIER_LABELS_SHORT, tierColor } from "../constants/tiers";

export function Clients() {
  const [typeFilter, setTypeFilter] = useState("all");

  const { data, isLoading } = useQuery<CustomerSummary[]>({
    queryKey: ["customers", typeFilter],
    queryFn: () => api.customers(typeFilter === "all" ? undefined : typeFilter),
    refetchInterval: 30_000,
  });

  return (
    <Box>
      {/* Aucun titre ici : la coquille d'administration le rend déjà, depuis sa
          table ENTETES. Deux en-têtes pour une même page affichaient le titre
          en double sur tout l'espace. Une seule source par vérité (règle 5). */}
      {isLoading && (
        <Flex justify="end" align="center" mb="4">
          <Spinner size="2" />
        </Flex>
      )}

      <Flex align="center" gap="3" mb="4">
        <Select.Root value={typeFilter} onValueChange={setTypeFilter} size="2">
          <Select.Trigger placeholder="Tous les types" />
          <Select.Content>
            <Select.Item value="all">Tous les types</Select.Item>
            <Select.Item value="b2c">B2C — achats unitaires</Select.Item>
            <Select.Item value="b2b">B2B — abonnements</Select.Item>
          </Select.Content>
        </Select.Root>
      </Flex>

      {data?.length === 0 && (
        <Callout.Root color="gray" mb="4">
          <Callout.Text>Aucun client{typeFilter !== "all" ? " pour ce type" : ""} pour l'instant.</Callout.Text>
        </Callout.Root>
      )}

      {data && data.length > 0 && (
        <Table.Root variant="surface">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeaderCell>Client</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Type</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Abonnement</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Inscrit le</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell />
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {data.map((c) => (
              <Table.Row key={c.id}>
                <Table.Cell>
                  <Text size="2" weight="medium">{c.email}</Text>
                  {(c.first_name || c.last_name || c.company_name) && (
                    <Text size="1" color="gray" as="p">
                      {[c.first_name, c.last_name].filter(Boolean).join(" ")}
                      {c.company_name ? ` · ${c.company_name}` : ""}
                    </Text>
                  )}
                </Table.Cell>
                <Table.Cell>
                  <Badge color={c.customer_type === "b2b" ? "blue" : "gray"} variant="soft" size="1">
                    {c.customer_type.toUpperCase()}
                  </Badge>
                </Table.Cell>
                <Table.Cell>
                  {c.active_subscription ? (
                    <Badge color={tierColor(c.active_subscription.tier)} variant="soft" size="1">
                      {TIER_LABELS_SHORT[c.active_subscription.tier] ?? c.active_subscription.tier} — Actif
                    </Badge>
                  ) : (
                    <Text size="1" color="gray">—</Text>
                  )}
                </Table.Cell>
                <Table.Cell>
                  <Text size="1" color="gray" className="mono">
                    {new Date(c.created_at).toLocaleDateString("fr-FR")}
                  </Text>
                </Table.Cell>
                <Table.Cell>
                  <Link
                    to="/admin/clients/$clientId"
                    params={{ clientId: c.id }}
                    style={{ color: "var(--accent-9)", textDecoration: "none", fontSize: 13 }}
                  >
                    Voir →
                  </Link>
                </Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      )}
    </Box>
  );
}
