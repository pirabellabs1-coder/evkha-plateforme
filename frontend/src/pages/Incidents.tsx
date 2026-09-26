import { useId, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { api, type Incident } from "../api";
import {
  Bandeau,
  Carte,
  ErreurDeChargement,
  Squelette,
} from "../espace/composants/Interface";
import "../admin/console.css";

/** Sévérité → classes de pastille (`theme/espace.css`), comme `TONS` dans
 *  `admin/pages/Transactions.tsx` : une sévérité n'est pas un statut, elle n'a
 *  pas sa place dans la table de `Pastille`.
 *
 *  Critique et haute partagent le rouge, comme avant ; la critique est PLEINE
 *  (l'ancien `variant="solid"`) pour qu'on les distingue sans lire. Moyenne en
 *  alerte, faible en succès ; toute sévérité inconnue retombe au neutre. */
const PASTILLE_PAR_SEVERITE: Record<string, string> = {
  critical: "pastille-echec console-pastille-pleine",
  high: "pastille-echec",
  medium: "pastille-alerte",
  low: "pastille-succes",
};

const SEVERITY_LABELS: Record<string, string> = {
  critical: "Critique", high: "Haute", medium: "Moyenne", low: "Faible",
};

/** Le détail brut d'un incident, dans un `<dialog>` natif.
 *
 *  `showModal()` fait ce que faisait le `Dialog` de Radix : le reste de la page
 *  devient inerte, Échap ferme, et le focus revient au bouton « Détails » à la
 *  fermeture. Un clic sur le voile ferme aussi : le rembourrage vit sur le
 *  corps de la fenêtre (`console.css`), un clic qui atteint la fenêtre
 *  elle-même est donc un clic hors du corps. */
function DetailsDialog({ details }: { details: Record<string, unknown> }) {
  const fenetre = useRef<HTMLDialogElement>(null);
  const idTitre = useId();
  if (!details || Object.keys(details).length === 0) return null;
  return (
    <>
      <button
        type="button"
        className="bouton bouton-discret bouton-sm"
        aria-haspopup="dialog"
        onClick={() => fenetre.current?.showModal()}
      >
        Détails
      </button>
      <dialog
        ref={fenetre}
        className="console-fenetre"
        aria-labelledby={idTitre}
        onClick={(evenement) => {
          if (evenement.target === evenement.currentTarget) evenement.currentTarget.close();
        }}
      >
        <div className="console-fenetre-corps">
          <h2 id={idTitre} className="carte-titre">Détails de l'incident</h2>
          <pre className="console-code">
            <code>{JSON.stringify(details, null, 2)}</code>
          </pre>
          <div className="console-fenetre-pied">
            <button
              type="button"
              className="bouton bouton-contour"
              onClick={() => fenetre.current?.close()}
            >
              Fermer
            </button>
          </div>
        </div>
      </dialog>
    </>
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

  // `disabled` suit l'envoi, comme le faisait le `loading` de Radix (qui
  // désactivait le bouton tant qu'on ne lui passait pas `disabled`).
  return (
    <div className="console-pile">
      <button
        type="button"
        className={
          mutation.isPending
            ? "bouton bouton-contour bouton-sm bouton-chargement"
            : "bouton bouton-contour bouton-sm"
        }
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        Résoudre
      </button>
      {error && <p className="console-message console-message-echec" role="alert">{error}</p>}
    </div>
  );
}

function IncidentTable({ incidents, canResolve }: { incidents: Incident[]; canResolve?: boolean }) {
  const queryClient = useQueryClient();

  return (
    <div className="tableau-cadre tableau-defile">
      <table className="tableau">
        <thead>
          <tr>
            <th scope="col">Titre</th>
            <th scope="col">Sévérité</th>
            <th scope="col">Créé le</th>
            <th scope="col">Job</th>
            <th scope="col">Détails</th>
            {canResolve && <th scope="col">Action</th>}
          </tr>
        </thead>
        <tbody>
          {incidents.map((inc) => (
            <tr key={inc.id}>
              <td>
                <strong>{inc.title}</strong>
              </td>
              <td>
                <span className={`pastille ${PASTILLE_PAR_SEVERITE[inc.severity] ?? "pastille-neutre"}`}>
                  {SEVERITY_LABELS[inc.severity] ?? inc.severity}
                </span>
              </td>
              <td className="console-tabulaire">
                {new Date(inc.created_at).toLocaleString("fr-FR")}
                {inc.resolved_at && (
                  <p className="console-message console-message-succes">
                    Résolu {new Date(inc.resolved_at).toLocaleString("fr-FR")}
                  </p>
                )}
              </td>
              <td>
                {inc.job_id ? (
                  <Link
                    to="/admin/jobs/$jobId"
                    params={{ jobId: inc.job_id }}
                    className="console-lien"
                  >
                    Voir <span aria-hidden="true">→</span>
                  </Link>
                ) : (
                  <span className="carte-note">—</span>
                )}
              </td>
              <td>
                <DetailsDialog details={inc.details} />
              </td>
              {canResolve && (
                <td>
                  <ResolveButton
                    incident={inc}
                    onResolved={() => {
                      queryClient.invalidateQueries({ queryKey: ["incidents"] });
                      queryClient.invalidateQueries({ queryKey: ["overview"] });
                    }}
                  />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Incidents() {
  const { data, isLoading, isError, error } = useQuery<Incident[]>({
    queryKey: ["incidents"],
    queryFn: api.incidents,
    refetchInterval: 30_000,
  });

  const open = data?.filter((i) => i.status === "open") ?? [];
  const inProgress = data?.filter((i) => i.status === "acknowledged") ?? [];
  const resolved = data?.filter((i) => i.status === "resolved") ?? [];

  return (
    <>
      {/* Titre rendu par la coquille d'administration — voir Clients.tsx. */}
      {isLoading && <Squelette lignes={4} />}

      {isError && <ErreurDeChargement quoi="les incidents" erreur={error} />}

      {/* « Aucun incident » ne se dit que sur une réponse REÇUE : sans `data`,
          on ne sait rien, et le dire serait mentir. */}
      {data && open.length === 0 && inProgress.length === 0 && (
        <Bandeau ton="succes">Aucun incident ouvert ✓</Bandeau>
      )}

      {/* Les incidents ouverts sont ce qui demande une intervention : leur
          carte prend le verre teinté d'échec, comme leur titre était rouge. */}
      {open.length > 0 && (
        <Carte titre={`Ouverts (${open.length})`} ton="echec">
          <IncidentTable incidents={open} canResolve />
        </Carte>
      )}

      {inProgress.length > 0 && (
        <Carte titre={`Pris en compte (${inProgress.length})`}>
          <IncidentTable incidents={inProgress} canResolve />
        </Carte>
      )}

      {resolved.length > 0 && (
        <Carte titre={`Résolus récemment (${resolved.length})`}>
          <IncidentTable incidents={resolved} />
        </Carte>
      )}
    </>
  );
}
