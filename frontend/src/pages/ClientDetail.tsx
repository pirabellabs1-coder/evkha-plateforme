import { useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { api, type CustomerDetail, type OrderSummary } from "../api";
import { TIER_LABELS } from "../constants/tiers";
import { ORDER_STATUS_LABELS } from "../constants/orders";
import {
  Bandeau,
  Carte,
  ErreurDeChargement,
  Pastille,
  Squelette,
  Vide,
} from "../espace/composants/Interface";
import "../admin/console.css";

function OrderRow({ order }: { order: OrderSummary }) {
  const label = order.parent_order_id
    ? `Ticket · ${order.period_year_month || "—"}`
    : order.offer_name;

  // Ton du statut : table unique de `Pastille` — voir `constants/orders.ts`.
  return (
    <tr>
      <td>
        {label}
        {order.parent_order_id && (
          <div className="carte-note">Crédit abonnement</div>
        )}
      </td>
      <td>
        <Pastille
          statut={order.status}
          texte={ORDER_STATUS_LABELS[order.status] ?? order.status}
        />
      </td>
      <td className="console-tabulaire">
        {new Date(order.created_at).toLocaleDateString("fr-FR")}
      </td>
    </tr>
  );
}

export function ClientDetail() {
  const { clientId } = useParams({ from: "/admin/clients/$clientId" });
  const { data, isLoading, error, isRefetchError } = useQuery<CustomerDetail>({
    queryKey: ["customer", clientId],
    queryFn: () => api.customer(clientId),
    refetchInterval: 30_000,
  });

  if (isLoading) return <Squelette lignes={6} />;
  if (!data) {
    return error ? (
      <ErreurDeChargement quoi="ce client" erreur={error} />
    ) : (
      <Bandeau ton="echec">Client introuvable.</Bandeau>
    );
  }

  const activeSub = data.subscriptions.find((s) => s.status === "active");
  const parentOrders = data.orders.filter((o) => !o.parent_order_id);
  const tickets = data.orders.filter((o) => !!o.parent_order_id);

  return (
    <>
      {isRefetchError && <ErreurDeChargement quoi="ce client" erreur={error} perimees />}
      <div>
        <Link to="/admin/clients" className="bouton bouton-discret bouton-sm">
          <span aria-hidden="true">←</span>{"\u00a0"}Clients
        </Link>
      </div>

      <Carte
        titre={data.email}
        note={
          data.first_name || data.last_name || data.company_name
            ? [data.first_name, data.last_name].filter(Boolean).join(" ") +
              (data.company_name ? ` · ${data.company_name}` : "")
            : undefined
        }
      >
        <div className="console-empile">
          {/* Infos abonnement.
              L'abonnement B2B passe AVANT : il vient du portefeuille d'organisation
              du lot 4, que cet écran ignorait. Un abonné disposant d'une formule et
              de dix crédits s'affichait « Aucun abonnement actif · 0 crédit », ce
              qui laissait croire qu'il n'avait rien payé. */}
          {data.organisation ? (
            <Bandeau ton="succes">
              Abonné B2B · <strong>{data.organisation.raison_sociale}</strong>
              {" — "}
              {data.organisation.formule
                ? <>formule <strong>{data.organisation.formule}</strong></>
                : "aucune formule active"}
              {" · "}
              {data.organisation.solde} crédit{data.organisation.solde > 1 ? "s" : ""}
              {data.organisation.solde_achete > 0 && (
                <> (dont {data.organisation.solde_achete} acheté
                  {data.organisation.solde_achete > 1 ? "s" : ""})</>
              )}
            </Bandeau>
          ) : activeSub ? (
            <Bandeau ton="succes">
              Abonnement actif : <strong>{TIER_LABELS[activeSub.tier] ?? activeSub.tier}</strong>
              {" — "}{data.credits_available} crédit{data.credits_available > 1 ? "s" : ""} en attente d'utilisation
            </Bandeau>
          ) : (
            // Ni alerte ni réussite : un client qui achète à l'unité n'a pas
            // d'abonnement, et ce n'est pas un problème. D'où le bandeau
            // neutre (`console.css`) plutôt que le `Bandeau` d'alerte.
            <div className="bandeau console-bandeau-neutre" role="status">
              <span aria-hidden="true">·</span>
              <div>
                Aucun abonnement actif · {data.credits_available} crédit(s) disponible(s)
              </div>
            </div>
          )}

          <dl className="compte-identite">
            <div>
              <dt>Type</dt>
              <dd>{data.customer_type.toUpperCase()}</dd>
            </div>
            <div>
              <dt>Inscrit</dt>
              <dd className="console-tabulaire">
                {new Date(data.created_at).toLocaleDateString("fr-FR")}
              </dd>
            </div>
            <div>
              <dt>Commandes</dt>
              <dd className="console-tabulaire">{parentOrders.length}</dd>
            </div>
            <div>
              <dt>Tickets crédit</dt>
              <dd className="console-tabulaire">{tickets.length}</dd>
            </div>
          </dl>
        </div>
      </Carte>

      {/* Historique abonnements */}
      {data.subscriptions.length > 0 && (
        <Carte titre="Abonnements">
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Formule</th>
                  <th scope="col">Statut</th>
                  <th scope="col">Début</th>
                  <th scope="col">Fin</th>
                </tr>
              </thead>
              <tbody>
                {data.subscriptions.map((s) => (
                  <tr key={s.id}>
                    <td>{TIER_LABELS[s.tier] ?? s.tier}</td>
                    <td>
                      {/* Actif en succès, tout le reste neutre : l'ancienne
                          règle green / gray, recopiée telle quelle plutôt que
                          déléguée à la table de `Pastille`. */}
                      <span
                        className={
                          s.status === "active"
                            ? "pastille pastille-succes"
                            : "pastille pastille-neutre"
                        }
                      >
                        {s.status === "active" ? "Actif" : s.status === "cancelled" ? "Annulé" : "Expiré"}
                      </span>
                    </td>
                    <td className="console-tabulaire">
                      {s.starts_at ? new Date(s.starts_at).toLocaleDateString("fr-FR") : "—"}
                    </td>
                    <td className="console-tabulaire">
                      {s.ends_at ? new Date(s.ends_at).toLocaleDateString("fr-FR") : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Carte>
      )}

      {/* Commandes */}
      {parentOrders.length > 0 && (
        <Carte titre={`Commandes (${parentOrders.length})`}>
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Offre</th>
                  <th scope="col">Statut</th>
                  <th scope="col">Date</th>
                </tr>
              </thead>
              <tbody>
                {parentOrders.map((o) => <OrderRow key={o.id} order={o} />)}
              </tbody>
            </table>
          </div>
        </Carte>
      )}

      {/* Tickets de crédit */}
      {tickets.length > 0 && (
        <Carte
          titre={`Tickets de crédit (${tickets.length})`}
          action={
            data.credits_available > 0 && (
              <span className="pastille pastille-alerte">
                {data.credits_available} en attente
              </span>
            )
          }
        >
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Période</th>
                  <th scope="col">Statut</th>
                  <th scope="col">Date</th>
                </tr>
              </thead>
              <tbody>
                {tickets.map((o) => <OrderRow key={o.id} order={o} />)}
              </tbody>
            </table>
          </div>
        </Carte>
      )}

      {data.orders.length === 0 && (
        <Carte>
          <Vide
            icone="◐"
            titre="Aucune commande"
            texte="Aucune commande enregistrée pour ce client."
          />
        </Carte>
      )}
    </>
  );
}
