import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { api, estRelancable, type JobSummary } from "../api";
import * as f from "../espace/format";
import {
  Carte,
  ErreurDeChargement,
  Pastille,
  Squelette,
  Vide,
} from "../espace/composants/Interface";
import "../admin/console.css";

const DELIVERABLE_LABELS: Record<string, string> = {
  market_study: "Étude de marché",
  competitor_study: "Étude de concurrence",
  business_plan: "Business Plan",
  business_strategy: "Stratégie Business",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "En attente",
  running: "En cours ⚡",
  done: "Terminé ✓",
  failed: "Échec ✗",
  cancelled: "Annulé",
};

// Le ton de chaque statut vient de la table unique de `Pastille`
// (`espace/composants/Interface.tsx`) : pending et cancelled neutres, running
// en information, done en succès, failed en échec — la correspondance exacte
// des anciennes couleurs Radix (gray, blue, green, red, gray).

/**
 * Bouton « Relancer » posé sur la LIGNE, et pas seulement sur la fiche.
 *
 * Le 09/08/2026, la génération d'une cliente a été tuée par un déploiement et
 * son dossier est resté « en cours » soixante-seize minutes, à deux chapitres
 * sur vingt-trois. La relancer a demandé une requête HTTP écrite à la main :
 * le bouton existait sur la fiche, mais sa condition d'affichage
 * (`failed || cancelled`) était plus stricte que ce que le backend accepte, et
 * il était donc caché exactement dans ce cas-là.
 *
 * Ici, la condition vient du backend (`job.interrompue`) — voir `estRelancable`.
 */
function BoutonRelancer({ job }: { job: JobSummary }) {
  const queryClient = useQueryClient();
  const [erreur, setErreur] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => api.jobRelaunch(job.id),
    onSuccess: () => {
      setErreur(null);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["job", job.id] });
    },
    // Le message vient du backend : « ce dossier progresse encore », « les
    // crédits ont été restitués ». L'écraser par un « Erreur » générique
    // priverait de la seule information qui dit quoi faire ensuite.
    onError: (err: Error) => setErreur(err.message),
  });

  const silence = job.minutes_sans_progression;
  const titre =
    job.status === "running" && silence !== null
      ? `Aucun chapitre depuis ${silence} min — relancer au dernier chapitre écrit`
      : "Relancer la génération";

  // `disabled` suit l'envoi, comme le faisait le `loading` de Radix (qui
  // désactivait le bouton tant qu'on ne lui passait pas `disabled`).
  return (
    <div className="console-pile">
      <button
        type="button"
        className={
          mutation.isPending
            ? "bouton bouton-principal bouton-sm bouton-chargement"
            : "bouton bouton-principal bouton-sm"
        }
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
        title={titre}
      >
        ↻ Relancer
      </button>
      {erreur && (
        <p className="console-message console-message-echec" role="alert">
          {erreur}
        </p>
      )}
    </div>
  );
}

function JobRowActions({ job }: { job: JobSummary }) {
  const queryClient = useQueryClient();
  const [emailQueued, setEmailQueued] = useState(false);

  const emailMutation = useMutation({
    mutationFn: () => api.jobSendEmail(job.id),
    onSuccess: () => {
      setEmailQueued(true);
      const timer = setInterval(() => {
        queryClient.invalidateQueries({ queryKey: ["jobs"] });
      }, 3_000);
      setTimeout(() => clearInterval(timer), 60_000);
    },
  });

  const hasPdf = !!job.pdf_download_url;
  const deliverySent = job.delivery_status === "sent";
  const pendingConfirmation = emailQueued && !deliverySent;

  // L'envoi est AUTOMATIQUE depuis le 12/09/2026, ici comme en page de détail
  // — ne le changer que sur une des deux pages en ferait une décoration :
  // l'autre bouton envoie le même document, au même client, en un clic
  // (règle 4 — viser la classe, pas l'endroit observé).
  //
  // Le bouton ne sert donc plus qu'à RÉPARER un envoi qui a échoué.
  const envoiEnEchec = job.delivery_status === "failed";

  return (
    <div className="console-gestes">
      {hasPdf ? (
        <a
          className="bouton bouton-contour bouton-sm"
          href={job.pdf_download_url!}
          target="_blank"
          rel="noreferrer"
        >
          ↓ PDF
        </a>
      ) : (
        <button type="button" className="bouton bouton-contour bouton-sm" disabled>
          ↓ PDF
        </button>
      )}
      {envoiEnEchec && (
        <button
          type="button"
          className={
            emailMutation.isPending
              ? "bouton bouton-contour bouton-sm bouton-chargement"
              : "bouton bouton-contour bouton-sm"
          }
          disabled={!hasPdf || emailMutation.isPending || pendingConfirmation}
          onClick={() => emailMutation.mutate()}
          title="L'envoi a échoué : réessayer."
          aria-label="L'envoi a échoué : réessayer l'envoi"
        >
          {pendingConfirmation ? "…" : "✉ !"}
        </button>
      )}
    </div>
  );
}

export function Jobs() {
  const [statusFilter, setStatusFilter] = useState("all");

  const { data, isLoading, isError, isRefetchError, error } = useQuery<JobSummary[]>({
    queryKey: ["jobs", statusFilter],
    queryFn: () => api.jobs(statusFilter === "all" ? undefined : statusFilter),
    refetchInterval: 15_000,
  });

  // Titre de page rendu par la coquille d'administration — voir Clients.tsx.
  // La carte, elle, compte ce qu'elle montre.
  return (
    <Carte
      titre={
        data
          ? `${f.nombre(data.length)} génération${data.length > 1 ? "s" : ""}`
          : "Générations"
      }
      action={
        <div className="console-filtres">
          <label className="champ">
            <span className="visuellement-cache">Filtrer par statut</span>
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
      {isError && (
        <ErreurDeChargement quoi="les générations" erreur={error} perimees={isRefetchError} />
      )}

      {data && data.length > 0 && (
        <div className="tableau-cadre tableau-defile">
          <table className="tableau">
            <thead>
              <tr>
                <th scope="col">Livrable</th>
                <th scope="col">Statut</th>
                <th scope="col">Progression</th>
                <th scope="col" style={{ textAlign: "right" }}>Coût</th>
                <th scope="col">Terminé le</th>
                <th scope="col">Actions</th>
                <th scope="col">
                  <span className="visuellement-cache">Détail</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((job) => {
                const pourcentage = job.chapters_total > 0
                  ? Math.round((job.chapters_done / job.chapters_total) * 100)
                  : 0;
                return (
                  <tr
                    key={job.id}
                    className={job.status === "failed" ? "console-ligne-echec" : undefined}
                  >
                    <td>{DELIVERABLE_LABELS[job.deliverable_type] ?? job.deliverable_type}</td>
                    <td>
                      <div className="console-pile">
                        <Pastille
                          statut={job.status}
                          texte={STATUS_LABELS[job.status] ?? job.status}
                        />
                        {/* Un dossier « en cours » qui ne l'est plus doit se VOIR.
                            C'est ce qui manquait le 09/08/2026 : rien ne distinguait
                            une génération qui travaille d'une génération morte. */}
                        {job.interrompue && (
                          <span
                            className="pastille pastille-alerte"
                            title="Aucun chapitre produit depuis longtemps"
                          >
                            interrompu
                            {job.minutes_sans_progression !== null
                              ? ` · ${job.minutes_sans_progression} min`
                              : ""}
                          </span>
                        )}
                        {/* Le badge « non envoyé » a disparu le 12/09/2026 avec
                            tout ce qui racontait la fabrication : l'envoi est
                            automatique, et un dossier terminé n'attend plus rien.
                            S'il reste un envoi en échec, le bouton de la colonne
                            d'actions le dit et le répare. */}
                      </div>
                    </td>
                    <td>
                      <div className="console-avancement">
                        {/* La jauge de l'espace client : le remplissage fait
                            toute la largeur et se décale de ce qui manque. */}
                        <div
                          className="jauge"
                          role="progressbar"
                          aria-valuenow={pourcentage}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-valuetext={`${job.chapters_done} chapitres sur ${job.chapters_total}`}
                          aria-label="Chapitres rédigés"
                        >
                          <span
                            className="jauge-remplissage"
                            style={{ transform: `translateX(-${100 - pourcentage}%)` }}
                          />
                        </div>
                        <span className="carte-note console-tabulaire">
                          {job.chapters_done}/{job.chapters_total}
                        </span>
                      </div>
                    </td>
                    <td className="nombre">
                      {f.coutApi(job.total_cost_eur)}
                    </td>
                    <td className="console-tabulaire">
                      {job.completed_at
                        ? new Date(job.completed_at).toLocaleDateString("fr-FR")
                        : "—"}
                    </td>
                    <td>
                      {/* UN DOCUMENT PRODUIT SE TÉLÉCHARGE, MÊME SI LE DOSSIER
                          A ÉCHOUÉ.

                          « Les documents échoués ne sont pas téléchargeables et
                          restent rouges, pourtant je les ai reçus par mail »
                          (cliente, 13/08/2026). Elle a raison : un dossier arrêté
                          au dernier chapitre a bel et bien produit son PDF, et
                          l'email est parti. Le cacher ici oblige à rouvrir le
                          détail, ou à retrouver le mail.

                          Le critère devient donc « le PDF EXISTE-t-il ? », et non
                          « le dossier s'est-il terminé ? ». Le statut rouge reste :
                          il dit la vérité sur la génération, pas sur le document. */}
                      <div className="console-pile">
                        {(job.status === "done" || job.pdf_download_url) && (
                          <JobRowActions job={job} />
                        )}
                        {estRelancable(job) && <BoutonRelancer job={job} />}
                      </div>
                    </td>
                    <td>
                      <Link
                        to="/admin/jobs/$jobId"
                        params={{ jobId: job.id }}
                        className="console-lien"
                      >
                        Détail{"\u00a0"}<span aria-hidden="true">→</span>
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {data?.length === 0 && (
        <Vide
          icone="▤"
          titre={`Aucun livrable${statusFilter !== "all" ? " pour ce statut" : ""}.`}
        />
      )}
    </Carte>
  );
}
