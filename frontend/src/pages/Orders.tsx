import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { api, type OrderSummary } from "../api";
import { ORDER_STATUS_LABELS as STATUS_LABELS } from "../constants/orders";
import * as f from "../espace/format";
import {
  Carte,
  ErreurDeChargement,
  Pastille,
  Squelette,
  Vide,
} from "../espace/composants/Interface";
import "../admin/console.css";

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

// Le ton de chaque statut de commande vient de la table unique de `Pastille` :
// reçue et annulée neutres, formulaire attendu en alerte, en traitement en
// information, livrée en succès, échec en échec — exactement les anciennes
// couleurs Radix (gray, amber, blue, green, red, gray).

export function Orders() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [kindFilter, setKindFilter] = useState("all");

  const params: Record<string, string> = {};
  if (statusFilter !== "all") params.status = statusFilter;
  if (kindFilter !== "all") params.kind = kindFilter;

  const { data, isLoading, isError, error } = useQuery<OrderSummary[]>({
    queryKey: ["orders", statusFilter, kindFilter],
    queryFn: () => api.orders(Object.keys(params).length ? params : undefined),
    refetchInterval: 30_000,
  });

  // Titre de page rendu par la coquille d'administration — voir Clients.tsx.
  return (
    <Carte
      titre={
        data
          ? `${f.nombre(data.length)} commande${data.length > 1 ? "s" : ""}`
          : "Commandes"
      }
      action={
        <div className="console-filtres">
          <label className="champ">
            <span className="visuellement-cache">Type de commande</span>
            <select
              className="champ-saisie"
              value={kindFilter}
              onChange={(evenement) => setKindFilter(evenement.target.value)}
            >
              {Object.entries(KIND_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </label>

          <label className="champ">
            <span className="visuellement-cache">Statut</span>
            <select
              className="champ-saisie"
              value={statusFilter}
              onChange={(evenement) => setStatusFilter(evenement.target.value)}
            >
              <option value="all">Tous les statuts</option>
              {Object.entries(STATUS_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </label>
        </div>
      }
    >
      {isLoading && <Squelette lignes={5} />}
      {isError && <ErreurDeChargement quoi="les commandes" erreur={error} />}

      {data?.length === 0 && (
        <Vide icone="◐" titre="Aucune commande pour ces filtres." />
      )}

      {data && data.length > 0 && (
        <div className="tableau-cadre tableau-defile">
          <table className="tableau">
            <thead>
              <tr>
                <th scope="col">Commande</th>
                <th scope="col">Client</th>
                <th scope="col">Type</th>
                <th scope="col">Statut</th>
                <th scope="col">Période</th>
                <th scope="col">Date</th>
              </tr>
            </thead>
            <tbody>
              {data.map((order) => {
                const isTicket = !!order.parent_order_id;
                const badge = isTicket
                  ? "Ticket"
                  : order.is_subscription
                    ? "Abonnement"
                    : order.is_extra_credit
                      ? "Crédit supp."
                      : "B2C";
                // Les anciennes couleurs Radix, ton pour ton : amber → alerte,
                // blue → information, green → succès, gray → neutre.
                const badgeTon = isTicket
                  ? "pastille-alerte"
                  : order.is_subscription
                    ? "pastille-info"
                    : order.is_extra_credit
                      ? "pastille-succes"
                      : "pastille-neutre";

                return (
                  <tr
                    key={order.id}
                    className={order.status === "failed" ? "console-ligne-echec" : undefined}
                  >
                    <td>
                      {order.offer_name}
                      {order.deliverable_type && (
                        <div className="carte-note">
                          {DELIVERABLE_LABELS[order.deliverable_type] ?? order.deliverable_type}
                        </div>
                      )}
                    </td>
                    <td>
                      <Link
                        to="/admin/clients/$clientId"
                        params={{ clientId: order.customer_id }}
                        className="console-lien"
                      >
                        {order.customer_email}
                      </Link>
                    </td>
                    <td>
                      <span className={`pastille ${badgeTon}`}>{badge}</span>
                    </td>
                    <td>
                      <Pastille
                        statut={order.status}
                        texte={STATUS_LABELS[order.status] ?? order.status}
                      />
                    </td>
                    <td className="console-tabulaire">
                      {order.period_year_month || "—"}
                    </td>
                    <td className="console-tabulaire">
                      {new Date(order.created_at).toLocaleDateString("fr-FR")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Carte>
  );
}
