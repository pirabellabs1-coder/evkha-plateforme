/** Demandes commerciales venues des espaces clients (§10.2).
 *
 * Sans cet écran, une demande enregistrée resterait invisible — c'est-à-dire ne
 * servirait à rien.
 *
 * Accorder applique RÉELLEMENT la décision : la formule est souscrite, les
 * crédits sont crédités. Marquer « traitee » sans rien faire donnerait à EVKHA
 * une liste propre et au client rien du tout.
 *
 * L'encaissement, lui, reste manuel tant que le prestataire de paiement n'est
 * pas branché — et l'écran le dit, plutôt que de laisser croire au contraire.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "../api";
import * as f from "../../espace/format";
import {
  Bandeau,
  Carte,
  Pastille,
  Squelette,
  Vide,
} from "../../espace/composants/Interface";

export function DemandesAdmin() {
  const cache = useQueryClient();
  const [erreur, setErreur] = useState("");
  const [motifRefus, setMotifRefus] = useState<Record<string, string>>({});

  const { data, isPending } = useQuery({
    queryKey: ["admin", "demandes"],
    queryFn: adminApi.demandes,
  });

  const traiter = useMutation({
    mutationFn: ({
      id,
      decision,
      reponse,
    }: {
      id: string;
      decision: "accorder" | "refuser";
      reponse?: string;
    }) => adminApi.traiterDemande(id, { decision, reponse }),
    onSuccess: () => {
      setErreur("");
      // Accorder crédite ou change la formule pour de vrai : le solde et les
      // organisations changent aussi.
      void cache.invalidateQueries({ queryKey: ["admin"] });
    },
    onError: (cause) =>
      setErreur(cause instanceof Error ? cause.message : "Traitement impossible."),
  });

  const demandes = data?.demandes ?? [];
  const ouvertes = demandes.filter((demande) => demande.statut === "ouverte");
  const traitees = demandes.filter((demande) => demande.statut !== "ouverte");

  return (
    <>
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
      {ouvertes.length > 0 && (
        <Bandeau titre={`${ouvertes.length} demande(s) en attente`}>
          Accorder applique <strong>réellement</strong> le changement de formule
          ou crédite le compte. L'encaissement, lui, reste à faire de votre côté
          tant que le prestataire de paiement n'est pas branché.
        </Bandeau>
      )}

      <Carte
        titre="À traiter"
        note="Par ordre d'arrivée, les plus anciennes d'abord."
      >
        {isPending ? (
          <Squelette lignes={3} />
        ) : ouvertes.length === 0 ? (
          <Vide
            icone="✓"
            titre="Rien en attente"
            texte="Les demandes de changement de formule et d'achat de crédits apparaîtront ici."
          />
        ) : (
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Reçue le</th>
                  <th scope="col">Organisation</th>
                  <th scope="col">Demande</th>
                  <th scope="col">Détail</th>
                  <th scope="col">
                    <span className="visuellement-cache">Décision</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {ouvertes.map((demande) => (
                  <tr key={demande.id}>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {f.dateHeure(demande.date)}
                    </td>
                    <td>
                      <strong>{demande.organisation}</strong>
                      {demande.demandeur && (
                        <div className="carte-note">{demande.demandeur}</div>
                      )}
                    </td>
                    <td>{f.typeDemande(demande.type)}</td>
                    <td>
                      {demande.formule_visee ||
                        (demande.quantite ? f.credits(demande.quantite) : "—")}
                      {demande.message && (
                        <div className="carte-note">{demande.message}</div>
                      )}
                    </td>
                    <td>
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "var(--e-2)",
                          minWidth: 210,
                        }}
                      >
                        <button
                          type="button"
                          className="bouton bouton-principal bouton-sm"
                          disabled={traiter.isPending}
                          onClick={() =>
                            traiter.mutate({ id: demande.id, decision: "accorder" })
                          }
                        >
                          Accorder
                        </button>
                        <input
                          className="champ-saisie"
                          placeholder="Raison du refus…"
                          aria-label="Raison du refus"
                          value={motifRefus[demande.id] ?? ""}
                          onChange={(evenement) =>
                            setMotifRefus((precedent) => ({
                              ...precedent,
                              [demande.id]: evenement.target.value,
                            }))
                          }
                        />
                        <button
                          type="button"
                          className="bouton bouton-contour bouton-sm"
                          disabled={
                            traiter.isPending || !(motifRefus[demande.id] ?? "").trim()
                          }
                          title={
                            (motifRefus[demande.id] ?? "").trim()
                              ? undefined
                              : "La raison du refus est affichée au client : elle est obligatoire."
                          }
                          onClick={() =>
                            traiter.mutate({
                              id: demande.id,
                              decision: "refuser",
                              reponse: motifRefus[demande.id],
                            })
                          }
                        >
                          Refuser
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Carte>

      {traitees.length > 0 && (
        <Carte titre="Historique" note="Demandes traitées ou refusées.">
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Organisation</th>
                  <th scope="col">Demande</th>
                  <th scope="col">Statut</th>
                </tr>
              </thead>
              <tbody>
                {traitees.map((demande) => (
                  <tr key={demande.id}>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {f.dateHeure(demande.date)}
                    </td>
                    <td>{demande.organisation}</td>
                    <td>{f.typeDemande(demande.type)}</td>
                    <td>
                      <Pastille
                        statut={demande.statut === "traitee" ? "done" : "failed"}
                        texte={
                          demande.statut === "traitee" ? "Traitée" : "Refusée"
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Carte>
      )}
    </>
  );
}
