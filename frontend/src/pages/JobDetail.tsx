import { useState } from "react";
import { useParams } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Box, Flex, Heading, Badge, Card, Table, Text, Callout, Spinner, Button,
} from "@radix-ui/themes";
import {
  api, estRelancable, livraisonBloquee,
  type Chapter, type JobDetail as JobDetailType,
} from "../api";

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

type RadixColor = "gray" | "blue" | "green" | "red";

function statusColor(status: string): RadixColor {
  const map: Record<string, RadixColor> = {
    pending: "gray", running: "blue", done: "green", failed: "red", skipped: "gray",
  };
  return map[status] ?? "gray";
}

function Pipeline({ job }: { job: JobDetailType }) {
  const genStatus =
    job.status === "done" ? "done"
    : job.status === "failed" ? "failed"
    : job.status === "running" ? "running"
    : "pending";

  const deliverySent   = job.delivery?.status === "sent";
  const deliveryFailed = job.delivery?.status === "failed";
  const genDone        = job.status === "done";

  // Assemblage PDF : en cours si gen terminée mais livraison pas encore envoyée
  const pdfStatus = deliverySent ? "done"
    : deliveryFailed ? "failed"
    : genDone ? "running"
    : "pending";
  const pdfIcon = deliverySent ? "✓" : deliveryFailed ? "✗" : genDone ? "⚡" : "○";

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
      key: "email", label: "Email envoyé",
      sub: deliverySent ? (job.customer_email ?? null) : null,
      status: emailStatus as "done" | "failed" | "pending",
      icon: emailIcon,
    },
  ];

  return (
    <Card mb="4">
      <div className="pipeline">
        {stages.map((stage, i) => (
          <div key={stage.key} className="pipeline-stage-wrapper">
            <div className={`pipeline-step pipeline-step--${stage.status}`}>
              <div className="pipeline-circle">{stage.icon}</div>
              <div className="pipeline-name">{stage.label}</div>
              {stage.sub && <div className="pipeline-sub">{stage.sub}</div>}
            </div>
            {i < stages.length - 1 && (
              <div className={`pipeline-connector pipeline-connector--${stage.status}`} />
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function ChapterRow({ chapter }: { chapter: Chapter }) {
  return (
    <Table.Row style={chapter.status === "failed" ? { background: "var(--red-2)" } : undefined}>
      <Table.Cell>
        <Text size="1" className="mono">{String(chapter.number).padStart(2, "0")}</Text>
      </Table.Cell>
      <Table.Cell>
        <Text size="2">{chapter.title}</Text>
        {chapter.error_message && (
          <Text size="1" color="red" as="p">{chapter.error_message}</Text>
        )}
      </Table.Cell>
      <Table.Cell>
        <Badge color={statusColor(chapter.status)} variant="soft" size="1">
          {STATUS_ICON[chapter.status] ?? chapter.status}{" "}
          {STATUS_LABELS[chapter.status] ?? chapter.status}
        </Badge>
      </Table.Cell>
      <Table.Cell>
        <Text size="1" className="mono">{chapter.input_tokens.toLocaleString()}</Text>
      </Table.Cell>
      <Table.Cell>
        <Text size="1" className="mono">{chapter.output_tokens.toLocaleString()}</Text>
      </Table.Cell>
      <Table.Cell>
        <Text size="1" className="mono">{parseFloat(chapter.cost_eur).toFixed(4)} €</Text>
      </Table.Cell>
    </Table.Row>
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

  // Recontrôle : le gate rejoué sur le document existant, zéro appel IA.
  // Un blocage peut devenir faux quand le CONTRÔLE était le défaut — trois
  // contrôles réparés le 10/08/2026 après le blocage de `026fecea`. Sans ce
  // bouton, le seul choix était d'assumer une dérogation sur un verdict
  // périmé, ou de repayer 3,50 € pour un document déjà produit.
  const reverifierMutation = useMutation({
    mutationFn: () => api.jobReverifier(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const emailSent = job.delivery?.status === "sent";
  const pendingConfirmation = emailQueued && !emailSent;

  // Le gate a refusé ce document. L'envoyer reste permis — c'est la dérogation
  // prévue par `generation/gate.py` — mais elle doit être VOULUE. Jusqu'ici le
  // bouton était identique à celui d'un dossier validé : trois documents
  // bloqués sont partis chez la cliente le 10/08/2026 sans que personne ne le
  // sache. Un premier clic arme, un second envoie.
  const bloque = livraisonBloquee(job);
  const [derogation, setDerogation] = useState(false);
  const armer = bloque && !derogation && !emailSent;

  const emailLabel = emailMutation.isPending
    ? "Envoi…"
    : pendingConfirmation
    ? "Email en cours…"
    : emailSent
    ? "✓ Email envoyé"
    : armer
    ? "Envoyer sans attendre la relecture"
    : bloque
    ? "Confirmer l'envoi"
    : "Envoyer par email";

  return (
    <Flex direction="column" align="end" gap="2">
      {pdfOnly && (
        <Text size="1" color="orange">⚠ Budget dépassé — PDF admin uniquement (pas d'email client)</Text>
      )}
      {bloque && (
        <Flex align="center" gap="2" justify="end">
          <Text size="1" color="gray">
            Retenu par le contrôle qualité — rien ne partira sans votre décision.
          </Text>
          <Button
            size="1"
            variant="soft"
            color="gray"
            loading={reverifierMutation.isPending}
            disabled={reverifierMutation.isPending}
            onClick={() => reverifierMutation.mutate()}
            title="Rejoue le contrôle qualité sur ce document, sans appel IA ni dépense."
          >
            ↻ Recontrôler
          </Button>
        </Flex>
      )}
      <Flex gap="2" wrap="wrap" justify="end">
        {!hasPdf && (
          <Button
            size="2"
            variant="soft"
            color="orange"
            loading={redeliverMutation.isPending || redeliverQueued}
            disabled={redeliverMutation.isPending || redeliverQueued}
            onClick={() => redeliverMutation.mutate()}
          >
            {redeliverQueued ? "Génération en cours…" : "Générer le PDF"}
          </Button>
        )}
        {hasPdf ? (
          <Button asChild size="2" variant="soft" color="green">
            <a href={readyPdf.download_url} target="_blank" rel="noreferrer">
              Télécharger le PDF
            </a>
          </Button>
        ) : (
          <Button size="2" variant="soft" color="green" disabled>
            Télécharger le PDF
          </Button>
        )}
        {!pdfOnly && (
          <Button
            size="2"
            variant="soft"
            color={
              emailSent && !pendingConfirmation ? "green" : bloque ? "amber" : "blue"
            }
            loading={emailMutation.isPending}
            disabled={!hasPdf || emailMutation.isPending || pendingConfirmation}
            onClick={() => (armer ? setDerogation(true) : emailMutation.mutate())}
          >
            {emailLabel}
          </Button>
        )}
      </Flex>
      {redeliverError && <Text size="1" color="red">{redeliverError}</Text>}
      {emailError && <Text size="1" color="red">{emailError}</Text>}
    </Flex>
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

  return (
    <Flex direction="column" align="end" gap="1">
      <Button size="2" variant="soft" color="red" loading={mutation.isPending} onClick={handleClick}>
        Annuler le job
      </Button>
      {error && <Text size="1" color="red">{error}</Text>}
    </Flex>
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
    <Flex direction="column" align="end" gap="1">
      <Button size="2" variant="soft" color="orange" loading={mutation.isPending} onClick={() => mutation.mutate()}>
        Relancer la génération
      </Button>
      {error && <Text size="1" color="red">{error}</Text>}
    </Flex>
  );
}


export function JobDetail() {
  const { jobId } = useParams({ from: "/admin/jobs/$jobId" });
  const { data, isLoading, error } = useQuery<JobDetailType>({
    queryKey: ["job", jobId],
    queryFn: () => api.job(jobId),
    refetchInterval: (q) => (q.state.data === undefined || q.state.data.status === "running") ? 5_000 : false,
  });

  if (isLoading) return (
    <Flex align="center" gap="2">
      <Spinner size="2" />
      <Text color="gray">Chargement…</Text>
    </Flex>
  );
  if (error || !data) return <Text color="red">Job introuvable.</Text>;

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
    <Box>
      <Flex align="center" gap="2" mb="3">
        <Link
          to="/admin/jobs"
          style={{ color: "var(--gray-9)", textDecoration: "none", fontSize: 13 }}
        >
          ← Livrables
        </Link>
      </Flex>

      <Flex align="center" justify="between" gap="3" mb="5" wrap="wrap">
        <Flex align="center" gap="3">
          <Heading size="6">{data.offer_name}</Heading>
          <Badge color={statusColor(data.status)} variant="soft" size="2">
            {STATUS_ICON[data.status] ?? data.status}{" "}
            {STATUS_LABELS[data.status] ?? data.status}
          </Badge>
          {/* Un dossier RETENU doit se voir, au même endroit que son statut :
              sans ce badge il serait en tous points identique à un dossier
              validé. Mais il disparaît dès l'envoi — un document parti n'est
              plus retenu, et l'afficher en rouge à côté de « ✓ Email envoyé »
              alarmait sur ce qu'aucun geste ne pouvait changer. */}
          {/* « Ça dit en attente de relecture pourtant rien ne se passe »
              (cliente, 12/08/2026). Elle avait raison deux fois : aucune
              relecture n'est programmée — rien ne relit, rien n'arrivera — et
              l'écran ne disait pas POURQUOI le document était retenu.

              Un libellé qui annonce une étape inexistante fait attendre. On dit
              donc ce qui est vrai : le contrôle a trouvé N points, et c'est à
              un humain de décider. Les motifs sont listés plus bas. */}
          {livraisonBloquee(data) && (
            <Badge
              color="amber"
              variant="soft"
              size="2"
              title="Le contrôle qualité a retenu ce document. Rien ne partira sans votre décision."
            >
              {data.qa_motifs?.length
                ? `Contrôle qualité : ${data.qa_motifs.length} point${
                    data.qa_motifs.length > 1 ? "s" : ""
                  } à revoir`
                : "Retenu par le contrôle qualité"}
            </Badge>
          )}
        </Flex>
        {canCancel && <CancelButton jobId={jobId} />}
        {canRelaunch && <RelaunchButton jobId={jobId} />}
        {data.status === "done" && <JobActions job={data} jobId={jobId} />}
        {showPdfOnly && <JobActions job={data} jobId={jobId} pdfOnly />}
      </Flex>

      <Pipeline job={data} />

      {/* LES MOTIFS. Le statut seul faisait attendre une relecture qui
          n'arrivait jamais ; pour connaître les neuf points d'un business plan,
          il fallait interroger un incident par l'API. Ce qui est reproché au
          document se lit désormais là où on décide de l'envoyer ou non. */}
      {livraisonBloquee(data) && (data.qa_motifs?.length ?? 0) > 0 && (
        <Card mb="4">
          <Text size="2" weight="bold">
            Ce que le contrôle qualité a retenu
          </Text>
          <Text size="1" color="gray" as="p" mb="2">
            Aucune relecture automatique n'est programmée : c'est à vous de
            corriger, de relancer une passe, ou d'envoyer malgré tout.
          </Text>
          <Flex direction="column" gap="1">
            {data.qa_motifs!.map((motif, index) => (
              <Flex key={`${motif.check}-${index}`} gap="2" align="start">
                <Badge size="1" variant="soft" color="gray">
                  {motif.chapitre === null || motif.chapitre === undefined
                    ? "document"
                    : `ch. ${motif.chapitre}`}
                </Badge>
                <Text size="1">{motif.detail}</Text>
              </Flex>
            ))}
          </Flex>
        </Card>
      )}

      <Card mb="4">
        <Flex wrap="wrap" gap="4">
          <Text size="2" color="gray">
            Client :{" "}
            <Link
              to="/admin/clients/$clientId"
              params={{ clientId: data.customer_id }}
              style={{ color: "var(--accent-9)", textDecoration: "none" }}
            >
              {data.customer_email}
            </Link>
          </Text>
          <Text size="2" color="gray">
            Livrable :{" "}
            <Text as="span" style={{ color: "var(--gray-12)" }}>
              {DELIVERABLE_LABELS[data.deliverable_type] ?? data.deliverable_type}
            </Text>
          </Text>
          <Text size="2" color="gray">Durée : <Text as="span" style={{ color: "var(--gray-12)" }}>{duration(data.started_at, data.completed_at)}</Text></Text>
          <Text size="2" color="gray">
            Coût : <Text as="span" style={{ color: overBudget ? "var(--red-11)" : "var(--gray-12)" }}>
              {parseFloat(data.total_cost_eur).toFixed(4)} €{overBudget ? " ⚠ Dépassé" : ""}
            </Text>
          </Text>
          <Text size="2" color="gray">Budget : <Text as="span" style={{ color: "var(--gray-12)" }}>{parseFloat(data.budget_eur).toFixed(2)} €</Text></Text>
          <Text size="2" color="gray">Tokens : <Text as="span" style={{ color: "var(--gray-12)" }}>{totalTokens.toLocaleString()}</Text></Text>
          {data.started_at && (
            <Text size="2" color="gray">Démarré : <Text as="span" style={{ color: "var(--gray-12)" }}>{new Date(data.started_at).toLocaleString("fr-FR")}</Text></Text>
          )}
          {data.completed_at && (
            <Text size="2" color="gray">Terminé : <Text as="span" style={{ color: "var(--gray-12)" }}>{new Date(data.completed_at).toLocaleString("fr-FR")}</Text></Text>
          )}
        </Flex>
      </Card>

      {data.error_message && (
        <Callout.Root color="red" mb="4">
          <Callout.Text>{data.error_message}</Callout.Text>
        </Callout.Root>
      )}

      <Heading size="4" mb="3">
        Chapitres — {data.chapters_done}/{data.chapters_total} terminés
      </Heading>

      <Table.Root variant="surface">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>#</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Titre</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Tokens in</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Tokens out</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Coût</Table.ColumnHeaderCell>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {data.chapters.map((c) => (
            <ChapterRow key={c.number} chapter={c} />
          ))}
          <Table.Row>
            <Table.Cell colSpan={5}>
              <Text size="2" weight="bold" className="text-right">Total</Text>
            </Table.Cell>
            <Table.Cell>
              <Text size="2" weight="bold" className="mono">
                {parseFloat(data.total_cost_eur).toFixed(4)} €
              </Text>
            </Table.Cell>
          </Table.Row>
        </Table.Body>
      </Table.Root>
    </Box>
  );
}
