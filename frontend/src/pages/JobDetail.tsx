import { useState } from "react";
import { useParams } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  api, estRelancable,
  type Chapter, type JobDetail as JobDetailType,
} from "../api";
import { Bandeau, Carte, Pastille, Squelette } from "../espace/composants/Interface";
import "../admin/console.css";

const STATUS_ICON: Record<string, string> = {
  done: "✓", running: "⚡", failed: "✗", pending: "○", skipped: "—",
};

const STATUS_LABELS: Record<string, string> = {
  done: "Terminé", running: "En cours", failed: "Échec", pending: "En attente", skipped: "Ignoré",
};

const DELIVERABLE_LABELS: Record<string, string> = {
  market_study: "Étude de marché",
  competitor_study: "Étude de concurrence",
  business_plan: "Business Plan",
  business_strategy: "Stratégie Business",
};

// Le ton de chaque statut (génération ET chapitre) vient de la table unique de
// `Pastille` : pending et skipped neutres, running en information, done en
// succès, failed en échec — la correspondance des anciennes couleurs Radix.

/** L'état d'une étape de la chaîne, dit en toutes lettres aux lecteurs
 *  d'écran : la puce n'en montre que la couleur et le glyphe. */
const ETAT_ETAPE: Record<"done" | "running" | "failed" | "pending", string> = {
  done: "terminée",
  running: "en cours",
  failed: "en échec",
  pending: "en attente",
};

function Pipeline({ job }: { job: JobDetailType }) {
  const genStatus =
    job.status === "done" ? "done"
    : job.status === "failed" ? "failed"
    : job.status === "running" ? "running"
    : "pending";

  const deliverySent   = job.delivery?.status === "sent";
  const deliveryFailed = job.delivery?.status === "failed";
  const genDone        = job.status === "done";

  // ASSEMBLAGE PDF : ce que disent les ARTEFACTS, pas la livraison.
  //
  // « Pourquoi ceci n'a pas changé ? » (cliente, 13/08/2026, capture a l'appui).
  // Le document venait d'etre assemble — deux artefacts prets — et l'etape
  // restait rouge. Elle ne regardait pas les documents : elle recopiait l'etat
  // de la LIVRAISON. Un envoi en echec peignait donc en rouge un assemblage
  // parfaitement reussi, et aucun assemblage ne pouvait jamais s'afficher vert
  // tant que l'email n'etait pas parti.
  //
  // Deux etapes distinctes doivent lire deux faits distincts : le PDF existe,
  // et l'email est parti. Les confondre, c'est mentir sur l'une des deux
  // (regle 1).
  const pdfPret = (job.artifacts ?? []).some(
    (a) => (a.kind === "pdf" || a.kind === "gamma_pdf" || a.kind === "docx")
      && a.status === "ready",
  );
  const pdfStatus = pdfPret ? "done"
    : deliveryFailed ? "failed"
    : genDone ? "running"
    : "pending";
  const pdfIcon = pdfPret ? "✓" : deliveryFailed ? "✗" : genDone ? "⚡" : "○";

  // Relecture du document assemblé : elle a tourné dès qu'elle a laissé sa
  // trace. « Aucun chapitre réécrit » est un résultat, pas une absence.
  const controle = job.controle_final ?? null;
  const controleStatus = controle ? (controle.passes ? "done" : "failed")
    : pdfPret ? "running"
    : "pending";
  const controleIcon = controle ? (controle.passes ? "✓" : "✗")
    : pdfPret ? "⚡" : "○";

  // Email envoyé : uniquement quand le batch est confirmé SENT
  const emailStatus = deliverySent ? "done" : deliveryFailed ? "failed" : "pending";
  const emailIcon   = deliverySent ? "✓" : deliveryFailed ? "✗" : "○";

  const stages = [
    {
      key: "order", label: "Commande reçue",
      sub: job.order_id ? `#${job.order_id.slice(0, 8)}` : null,
      status: "done" as const, icon: "✓",
    },
    {
      key: "gen", label: "Génération IA",
      sub: `${job.chapters_done}/${job.chapters_total} chapitres`,
      status: genStatus as "done" | "running" | "failed" | "pending",
      icon: genStatus === "done" ? "✓" : genStatus === "running" ? "⚡" : genStatus === "failed" ? "✗" : "○",
    },
    {
      key: "pdf", label: "Assemblage PDF", sub: null,
      status: pdfStatus as "done" | "running" | "failed" | "pending",
      icon: pdfIcon,
    },
    {
      // « On doit voir l'agent contrôleur ici » (12/09/2026). L'étape tournait
      // déjà entre l'assemblage et l'envoi, sans rien montrer : un document
      // relu et corrigé se présentait comme un document jamais relu.
      key: "controle", label: "Contrôle du document",
      sub: controle
        ? (controle.chapitres_reecrits.length
            ? `${controle.chapitres_reecrits.length} chapitre(s) corrigé(s)`
            : controle.anomalies_restantes
              ? `${controle.anomalies_restantes} point(s) signalé(s)`
              : "document propre")
        : null,
      status: controleStatus as "done" | "running" | "failed" | "pending",
      icon: controleIcon,
    },
    {
      key: "email", label: "Email envoyé",
      sub: deliverySent ? (job.customer_email ?? null) : null,
      status: emailStatus as "done" | "failed" | "pending",
      icon: emailIcon,
    },
  ];

  return (
    <ol className="console-chaine" aria-label="Chaîne de production">
      {stages.map((stage) => (
        <li
          key={stage.key}
          className={`console-chaine-etape console-chaine-${stage.status}`}
        >
          <span className="console-chaine-puce" aria-hidden="true">{stage.icon}</span>
          <span className="console-chaine-texte">
            <span className="console-chaine-nom">
              {stage.label}
              <span className="visuellement-cache"> : {ETAT_ETAPE[stage.status]}</span>
            </span>
            {stage.sub && <span className="console-chaine-detail">{stage.sub}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}

function ChapterRow({ chapter }: { chapter: Chapter }) {
  return (
    <tr className={chapter.status === "failed" ? "console-ligne-echec" : undefined}>
      <td className="console-tabulaire">{String(chapter.number).padStart(2, "0")}</td>
      <td>
        {chapter.title}
        {chapter.error_message && (
          <p className="console-message console-message-echec">{chapter.error_message}</p>
        )}
      </td>
      <td>
        <Pastille
          statut={chapter.status}
          texte={`${STATUS_ICON[chapter.status] ?? chapter.status} ${STATUS_LABELS[chapter.status] ?? chapter.status}`}
        />
      </td>
      <td className="nombre">{chapter.input_tokens.toLocaleString()}</td>
      <td className="nombre">{chapter.output_tokens.toLocaleString()}</td>
      <td className="nombre">{parseFloat(chapter.cost_eur).toFixed(4)} €</td>
    </tr>
  );
}

function duration(start: string | null, end: string | null): string {
  if (!start) return "—";
  const from = new Date(start).getTime();
  const to = end ? new Date(end).getTime() : Date.now();
  const s = Math.round((to - from) / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}min ${s % 60}s`;
}

/** Classe d'un bouton de la charte, avec le balayage de chargement pendant
 *  l'envoi. Le balayage ne décide RIEN : `disabled` reste écrit à la main sur
 *  chaque bouton, exactement comme il l'était. */
function classeBouton(variante: string, enCours: boolean): string {
  return enCours ? `bouton ${variante} bouton-chargement` : `bouton ${variante}`;
}

function JobActions({ job, jobId, pdfOnly = false }: { job: JobDetailType; jobId: string; pdfOnly?: boolean }) {
  const queryClient = useQueryClient();
  const [emailQueued, setEmailQueued] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [redeliverQueued, setRedeliverQueued] = useState(false);
  const [redeliverError, setRedeliverError] = useState<string | null>(null);

  const readyPdf = job.artifacts?.find(
    (a) => (a.kind === "pdf" || a.kind === "gamma_pdf") && a.status === "ready" && a.download_url,
  );
  const hasPdf = !!readyPdf;

  const redeliverMutation = useMutation({
    mutationFn: () => api.jobRedeliver(jobId),
    onSuccess: () => {
      setRedeliverError(null);
      setRedeliverQueued(true);
      const timer = setInterval(() => {
        queryClient.invalidateQueries({ queryKey: ["job", jobId] });
        queryClient.invalidateQueries({ queryKey: ["jobs"] });
      }, 5_000);
      setTimeout(() => clearInterval(timer), 120_000);
    },
    onError: (err: Error) => setRedeliverError(err.message),
  });

  const emailMutation = useMutation({
    mutationFn: () => api.jobSendEmail(jobId),
    onSuccess: () => {
      setEmailError(null);
      setEmailQueued(true);
      const timer = setInterval(() => {
        queryClient.invalidateQueries({ queryKey: ["job", jobId] });
        queryClient.invalidateQueries({ queryKey: ["jobs"] });
      }, 3_000);
      setTimeout(() => clearInterval(timer), 60_000);
    },
    onError: (err: Error) => setEmailError(err.message),
  });

  // Le bouton « Recontrôler » a disparu le 12/09/2026 avec le panneau des
  // motifs : le contrôle du document tourne en arrière-plan et corrige de
  // lui-même. La route `jobReverifier` reste, pour nous, hors de l'écran.

  const emailSent = job.delivery?.status === "sent";
  const pendingConfirmation = emailQueued && !emailSent;

  // Le gate a refusé ce document. L'envoyer reste permis — c'est la dérogation
  // prévue par `generation/gate.py` — mais elle doit être VOULUE. Jusqu'ici le
  // bouton était identique à celui d'un dossier validé : trois documents
  // bloqués sont partis chez la cliente le 10/08/2026 sans que personne ne le
  // sache. Un premier clic arme, un second envoie.
  // L'envoi est AUTOMATIQUE depuis le 12/09/2026 : « lorsque le contrôle du
  // document est terminé, le mail doit être envoyé automatiquement ; je ne
  // veux plus voir les boutons envoyer ». Le bouton ne reparaît donc que
  // lorsque l'envoi a ÉCHOUÉ — là, il ne demande pas une décision, il répare.
  const envoiEnEchec = job.delivery?.status === "failed";

  return (
    <div className="console-pile console-pile-fin">
      {pdfOnly && (
        <p className="console-message console-message-alerte">⚠ Budget dépassé — PDF admin uniquement (pas d'email client)</p>
      )}

      <div className="console-gestes-fiche">
        {!hasPdf && (
          <button
            type="button"
            className={classeBouton("bouton-principal", redeliverMutation.isPending || redeliverQueued)}
            disabled={redeliverMutation.isPending || redeliverQueued}
            onClick={() => redeliverMutation.mutate()}
          >
            {redeliverQueued ? "Génération en cours…" : "Générer le PDF"}
          </button>
        )}
        {hasPdf ? (
          <a
            className="bouton bouton-contour"
            href={readyPdf.download_url}
            target="_blank"
            rel="noreferrer"
          >
            Télécharger le PDF
          </a>
        ) : (
          <button type="button" className="bouton bouton-contour" disabled>
            Télécharger le PDF
          </button>
        )}
        {!pdfOnly && envoiEnEchec && (
          <button
            type="button"
            className={classeBouton("bouton-contour", emailMutation.isPending)}
            disabled={!hasPdf || emailMutation.isPending || pendingConfirmation}
            onClick={() => emailMutation.mutate()}
          >
            {emailMutation.isPending ? "Envoi…" : "Réessayer l'envoi"}
          </button>
        )}
      </div>
      {redeliverError && <p className="console-message console-message-echec" role="alert">{redeliverError}</p>}
      {emailError && <p className="console-message console-message-echec" role="alert">{emailError}</p>}
    </div>
  );
}

function CancelButton({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => api.jobCancel(jobId),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const handleClick = () => {
    if (!window.confirm("Annuler ce job ? Le chapitre en cours finira, puis la génération s'arrêtera.")) return;
    mutation.mutate();
  };

  // `disabled` suit l'envoi, comme le faisait le `loading` de Radix (qui
  // désactivait le bouton tant qu'on ne lui passait pas `disabled`).
  return (
    <div className="console-pile console-pile-fin">
      <button
        type="button"
        className={classeBouton("bouton-echec", mutation.isPending)}
        disabled={mutation.isPending}
        onClick={handleClick}
      >
        Annuler le job
      </button>
      {error && <p className="console-message console-message-echec" role="alert">{error}</p>}
    </div>
  );
}

function RelaunchButton({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => api.jobRelaunch(jobId),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  return (
    <div className="console-pile console-pile-fin">
      <button
        type="button"
        className={classeBouton("bouton-principal", mutation.isPending)}
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        Relancer la génération
      </button>
      {error && <p className="console-message console-message-echec" role="alert">{error}</p>}
    </div>
  );
}


export function JobDetail() {
  const { jobId } = useParams({ from: "/admin/jobs/$jobId" });
  const { data, isLoading, error } = useQuery<JobDetailType>({
    queryKey: ["job", jobId],
    queryFn: () => api.job(jobId),
    refetchInterval: (q) => (q.state.data === undefined || q.state.data.status === "running") ? 5_000 : false,
  });

  if (isLoading) return <Squelette lignes={6} />;
  if (error || !data) return <Bandeau ton="echec">Job introuvable.</Bandeau>;

  const totalTokens = data.chapters.reduce(
    (acc, c) => acc + c.input_tokens + c.output_tokens, 0,
  );
  const overBudget = parseFloat(data.total_cost_eur) > parseFloat(data.budget_eur);
  // `estRelancable` relit ce que le backend a decide (`interrompue`) au lieu de
  // le rededuire ici. La version precedente ecrivait `failed || cancelled` — une
  // regle plus stricte que celle du serveur, donc un bouton cache exactement
  // dans le cas ou l'on en a besoin : une generation tuee par un deploiement,
  // restee « en cours ». Le 09/08/2026, il a fallu une requete HTTP a la main.
  const canRelaunch = estRelancable(data);
  const canCancel = data.status === "running" || data.status === "pending";
  // Job FAILED avec au moins un chapitre terminé : PDF admin téléchargeable, sans email
  const hasAnyDoneChapter = data.chapters.some((c) => c.status === "done");
  const showPdfOnly = data.status === "failed" && hasAnyDoneChapter;

  return (
    <>
      <div>
        <Link to="/admin/jobs" className="bouton bouton-discret bouton-sm">
          <span aria-hidden="true">←</span> Générations
        </Link>
      </div>

      {/* La carte d'en-tête porte le nom de l'offre, son état, les gestes
          possibles et la chaîne de production : tout ce qui dit où en est le
          dossier, d'un seul regard. Écrite à la main plutôt que par `Carte`,
          dont le titre n'accepte que du texte : la pastille d'état doit se
          lire à côté du nom. */}
      <section className="carte">
        <header className="carte-entete">
          <div className="console-titre">
            <h2 className="carte-titre">{data.offer_name}</h2>
            <Pastille
              statut={data.status}
              texte={`${STATUS_ICON[data.status] ?? data.status} ${STATUS_LABELS[data.status] ?? data.status}`}
            />
            {/* Un dossier RETENU doit se voir, au même endroit que son statut :
                sans ce badge il serait en tous points identique à un dossier
                validé. Mais il disparaît dès l'envoi — un document parti n'est
                plus retenu, et l'afficher en rouge à côté de « ✓ Email envoyé »
                alarmait sur ce qu'aucun geste ne pouvait changer. */}
            {/* Le badge « N points non résolus » a disparu le 12/09/2026, avec
                le panneau des motifs : il annonçait un travail que personne ne
                pouvait faire. L'état d'un dossier terminé, c'est son document. */}
          </div>
          <div className="console-gestes-fiche">
            {canCancel && <CancelButton jobId={jobId} />}
            {canRelaunch && <RelaunchButton jobId={jobId} />}
            {data.status === "done" && <JobActions job={data} jobId={jobId} />}
            {showPdfOnly && <JobActions job={data} jobId={jobId} pdfOnly />}
          </div>
        </header>

        <Pipeline job={data} />
      </section>

      {/* LES MOTIFS NE S'AFFICHENT PLUS ICI. Décision du 12/09/2026 :
          « ce que le contrôle qualité a retenu, on ne veut plus avoir ça ;
          ce sont des choses qui doivent tourner en arrière-plan uniquement.
          S'il y a des erreurs, tout doit être corrigé, et quand ça se termine
          le mail doit être envoyé automatiquement. »

          Le raisonnement tient : l'administrateur ne réécrit pas un document.
          Lui présenter une liste de points qu'il ne peut pas corriger ne
          produisait qu'une attente. Ce qui reste après le contrôle du document
          vit dans les incidents, pour nous, et le document part. */}

      <Carte titre="Dossier">
        <dl className="compte-identite">
          <div>
            <dt>Client</dt>
            <dd>
              <Link
                to="/admin/clients/$clientId"
                params={{ clientId: data.customer_id }}
                className="console-lien"
              >
                {data.customer_email}
              </Link>
            </dd>
          </div>
          <div>
            <dt>Livrable</dt>
            <dd>{DELIVERABLE_LABELS[data.deliverable_type] ?? data.deliverable_type}</dd>
          </div>
          <div>
            <dt>Durée</dt>
            <dd className="console-tabulaire">{duration(data.started_at, data.completed_at)}</dd>
          </div>
          <div>
            <dt>Coût</dt>
            <dd className={overBudget ? "console-tabulaire console-depasse" : "console-tabulaire"}>
              {parseFloat(data.total_cost_eur).toFixed(4)} €{overBudget ? " ⚠ Dépassé" : ""}
            </dd>
          </div>
          <div>
            <dt>Budget</dt>
            <dd className="console-tabulaire">{parseFloat(data.budget_eur).toFixed(2)} €</dd>
          </div>
          <div>
            <dt>Tokens</dt>
            <dd className="console-tabulaire">{totalTokens.toLocaleString()}</dd>
          </div>
          {data.started_at && (
            <div>
              <dt>Démarré</dt>
              <dd className="console-tabulaire">{new Date(data.started_at).toLocaleString("fr-FR")}</dd>
            </div>
          )}
          {data.completed_at && (
            <div>
              <dt>Terminé</dt>
              <dd className="console-tabulaire">{new Date(data.completed_at).toLocaleString("fr-FR")}</dd>
            </div>
          )}
        </dl>
      </Carte>

      {/* NI LE DÉTAIL DU CONTRÔLE, NI LES DOCUMENTS LUS, NI LE MOTIF DE
          RETENUE ne s'affichent ici. Décision du 12/09/2026 : « rien ne doit
          être visible du tout, ça n'a aucune importance ».

          Elle est cohérente avec tout ce que cet écran a désappris cette
          semaine. Ces trois blocs racontaient la FABRICATION du document —
          combien de points restaient, quels fichiers avaient été lus, pourquoi
          un livrable avait été retenu. Or celui qui regarde ce dossier ne
          fabrique pas : il attend un document. Ce qu'il peut faire tient en
          deux gestes, et ils sont plus haut — télécharger, réessayer un envoi
          qui a échoué.

          Rien n'est perdu pour autant : le contrôle du document, les documents
          lus et les motifs de retenue vivent dans les incidents et dans
          `GenerationJob.controle_final`, lus par l'API. C'est notre matière de
          travail, pas la sienne. */}

      <Carte titre={`Chapitres — ${data.chapters_done}/${data.chapters_total} terminés`}>
        <div className="tableau-cadre tableau-defile">
          <table className="tableau">
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Titre</th>
                <th scope="col">Statut</th>
                <th scope="col" style={{ textAlign: "right" }}>Tokens in</th>
                <th scope="col" style={{ textAlign: "right" }}>Tokens out</th>
                <th scope="col" style={{ textAlign: "right" }}>Coût</th>
              </tr>
            </thead>
            <tbody>
              {data.chapters.map((c) => (
                <ChapterRow key={c.number} chapter={c} />
              ))}
              <tr>
                <td colSpan={5} className="nombre">Total</td>
                <td className="nombre">
                  {parseFloat(data.total_cost_eur).toFixed(4)} €
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Carte>
    </>
  );
}
