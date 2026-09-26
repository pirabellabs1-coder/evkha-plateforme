import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { api, type CustomerSummary } from "../api";
import { TIER_LABELS_SHORT, tierTon } from "../constants/tiers";
import * as f from "../espace/format";
import {
  Carte,
  ErreurDeChargement,
  Squelette,
  Vide,
} from "../espace/composants/Interface";
import "../admin/console.css";

export function Clients() {
  const [typeFilter, setTypeFilter] = useState("all");

  const { data, isLoading, isError, error } = useQuery<CustomerSummary[]>({
    queryKey: ["customers", typeFilter],
    queryFn: () => api.customers(typeFilter === "all" ? undefined : typeFilter),
    refetchInterval: 30_000,
  });

  // Aucun titre de page ici : la coquille d'administration le rend déjà,
  // depuis sa table ENTETES. Deux en-têtes pour une même page affichaient le
  // titre en double sur tout l'espace. Une seule source par vérité (règle 5).
  // La carte, elle, compte ce qu'elle montre.
  return (
    <Carte
      titre={
        data
          ? `${f.nombre(data.length)} client${data.length > 1 ? "s" : ""}`
          : "Clients"
      }
      action={
        <div className="console-filtres">
          <label className="champ">
            <span className="visuellement-cache">Type de client</span>
            <select
              className="champ-saisie"
              value={typeFilter}
              onChange={(evenement) => setTypeFilter(evenement.target.value)}
            >
              <option value="all">Tous les types</option>
              <option value="b2c">B2C — achats unitaires</option>
              <option value="b2b">B2B — abonnements</option>
            </select>
          </label>
        </div>
      }
    >
      {isLoading && <Squelette lignes={5} />}
      {isError && <ErreurDeChargement quoi="les clients" erreur={error} />}

      {data?.length === 0 && (
        <Vide
          icone="◉"
          titre={`Aucun client${typeFilter !== "all" ? " pour ce type" : ""} pour l'instant.`}
        />
      )}

      {data && data.length > 0 && (
        <div className="tableau-cadre tableau-defile">
          <table className="tableau">
            <thead>
              <tr>
                <th scope="col">Client</th>
                <th scope="col">Type</th>
                <th scope="col">Abonnement</th>
                <th scope="col">Inscrit le</th>
                <th scope="col">
                  <span className="visuellement-cache">Fiche</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((c) => (
                <tr key={c.id}>
                  <td>
                    <strong>{c.email}</strong>
                    {(c.first_name || c.last_name || c.company_name) && (
                      <div className="carte-note">
                        {[c.first_name, c.last_name].filter(Boolean).join(" ")}
                        {c.company_name ? ` · ${c.company_name}` : ""}
                      </div>
                    )}
                  </td>
                  <td>
                    {/* B2B en information, B2C neutre : les anciens bleu et
                        gris de Radix. */}
                    <span
                      className={
                        c.customer_type === "b2b"
                          ? "pastille pastille-info"
                          : "pastille pastille-neutre"
                      }
                    >
                      {c.customer_type.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    {c.active_subscription ? (
                      <span className={`pastille pastille-${tierTon(c.active_subscription.tier)}`}>
                        {TIER_LABELS_SHORT[c.active_subscription.tier] ?? c.active_subscription.tier} — Actif
                      </span>
                    ) : (
                      <span className="carte-note">—</span>
                    )}
                  </td>
                  <td className="console-tabulaire">
                    {new Date(c.created_at).toLocaleDateString("fr-FR")}
                  </td>
                  <td>
                    <Link
                      to="/admin/clients/$clientId"
                      params={{ clientId: c.id }}
                      className="console-lien"
                    >
                      Voir{"\u00a0"}<span aria-hidden="true">→</span>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Carte>
  );
}
