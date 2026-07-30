import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Card, Grid, Flex, Box, Text, Heading, Badge, Separator, Spinner, Callout,
} from "@radix-ui/themes";
import { api, type OverviewData, type JobSummary, type SystemStatus } from "../api";

const DELIVERABLE_LABELS: Record<string, string> = {
  market_study:       "Étude de marché",
  competitor_study:   "Étude de concurrence",
  business_plan:      "Business Plan",
  business_strategy:  "Stratégie Business",
};

type RadixColor = "gray" | "blue" | "green" | "red" | "amber" | "orange";

function statusColor(status: string): RadixColor {
  const map: Record<string, RadixColor> = {
    pending: "gray", running: "blue", done: "green", failed: "red", cancelled: "gray",
  };
  return map[status] ?? "gray";
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending:   "En attente",
    running:   "Génération en cours ⚡",
    done:      "Livrable prêt ✓",
    failed:    "Échec",
    cancelled: "Annulé",
  };
  return map[status] ?? status;
}

function relativeDate(iso: string | null): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60_000);
  if (m < 1)  return "à l'instant";
  if (m < 60) return `il y a ${m} min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `il y a ${h} h`;
  return `il y a ${Math.floor(h / 24)} j`;
}

// ─── Stat card ───────────────────────────────────────────────────────────────

function StatCard({ label, value, description, alert, link }: {
  label: string; value: string | number; description?: string; alert?: boolean; link?: string;
}) {
  const card = (
    <Card
      size="2"
      style={{
        borderColor: alert ? "var(--orange-7)" : undefined,
        cursor: link ? "pointer" : undefined,
      }}
    >
      <Text
        size="1"
        color="gray"
        weight="medium"
        style={{ display: "block", textTransform: "uppercase", letterSpacing: "0.05em" }}
      >
        {label}
      </Text>
      <Heading size="6" mt="1" color={alert ? "orange" : undefined}>{value}</Heading>
      {description && <Text size="1" color="gray" as="p" mt="1">{description}</Text>}
    </Card>
  );
  if (link) {
    return (
      <Link to={link as never} style={{ textDecoration: "none", color: "inherit" }}>
        {card}
      </Link>
    );
  }
  return card;
}

// ─── Bannière système ─────────────────────────────────────────────────────────

function SystemBanner({ system }: { system: SystemStatus }) {
  const issues: string[] = [];
  if (system.api !== "ok")  issues.push("L'API est hors ligne.");
  if (system.email_stub)    issues.push("Les emails ne sont pas activés.");
  if (system.ai_stub)       issues.push("L'IA n'est pas activée.");

  if (issues.length === 0) {
    return (
      <Callout.Root color="green" mb="5">
        <Callout.Text>
          Tout est opérationnel — l'IA génère, les emails partent, le serveur répond.
        </Callout.Text>
      </Callout.Root>
    );
  }
  return (
    <Callout.Root color="amber" mb="5">
      <Callout.Text>{issues.join(" ")}</Callout.Text>
    </Callout.Root>
  );
}

// ─── Liste des livrables ──────────────────────────────────────────────────────

function RecentJobs({ jobs }: { jobs: JobSummary[] }) {
  if (jobs.length === 0) {
    return (
      <Card>
        <Flex align="center" justify="center" py="6" direction="column" gap="2">
          <Text size="3" color="gray">Aucun livrable généré pour l'instant.</Text>
          <Text size="2" color="gray" style={{ textAlign: "center", maxWidth: 420 }}>
            Dès qu'un client passera commande et remplira le questionnaire, son livrable apparaîtra ici.
          </Text>
        </Flex>
      </Card>
    );
  }

  return (
    <Card style={{ padding: 0 }}>
      {jobs.slice(0, 8).map((job, idx, arr) => (
        <Box key={job.id}>
          <Flex align="center" gap="3" px="4" py="3">
            <Box style={{ flex: 1, minWidth: 0 }}>
              <Text size="2" weight="medium">
                {DELIVERABLE_LABELS[job.deliverable_type] ?? job.deliverable_type}
              </Text>
              {job.status === "running" && (
                <Text size="1" color="blue" as="p">
                  {job.chapters_done} / {job.chapters_total} chapitres rédigés
                </Text>
              )}
              {job.error_message && (
                <Text size="1" color="red" as="p" style={{
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 320,
                }}>
                  {job.error_message}
                </Text>
              )}
            </Box>
            <Text size="1" color="gray" style={{ whiteSpace: "nowrap", flexShrink: 0 }}>
              {relativeDate(job.completed_at ?? job.started_at)}
            </Text>
            <Badge color={statusColor(job.status)} variant="soft" size="1" style={{ flexShrink: 0 }}>
              {statusLabel(job.status)}
            </Badge>
            <Link to="/admin/jobs/$jobId" params={{ jobId: job.id }}
              style={{ color: "var(--accent-9)", textDecoration: "none", fontSize: 13, flexShrink: 0 }}>
              Voir →
            </Link>
          </Flex>
          {idx < arr.length - 1 && <Separator size="4" />}
        </Box>
      ))}
    </Card>
  );
}

// ─── Détail des services ──────────────────────────────────────────────────────

function ServiceDetails({ system }: { system: SystemStatus }) {
  const services = [
    {
      label:  "Génération IA des documents",
      detail: system.ai_stub
        ? "Non activé — configure la clé Anthropic dans Coolify"
        : "Actif — modèle Claude Sonnet",
      ok: !system.ai_stub,
    },
    {
      label:  "Envoi des livrables par email",
      detail: system.email_stub
        ? "Non activé — configure la clé Brevo dans Coolify"
        : "Actif — expéditeur contact@evkha.fr",
      ok: !system.email_stub,
    },
    {
      label:  "Création des PDF",
      detail: "Actif — WeasyPrint",
      ok: true,
    },
    {
      label:  "Serveur API",
      detail: system.api === "ok" ? "En ligne — app.evkha.fr" : "Hors ligne",
      ok: system.api === "ok",
    },
  ];

  return (
    <Card style={{ padding: 0 }}>
      {services.map((s, idx) => (
        <Box key={s.label}>
          <Flex align="center" gap="3" px="4" py="3">
            <Box style={{
              width: 10, height: 10, borderRadius: "50%", flexShrink: 0,
              background: s.ok ? "var(--green-9)" : "var(--amber-9)",
            }} />
            <Box style={{ flex: 1 }}>
              <Text size="2" weight="medium">{s.label}</Text>
              <Text size="1" color="gray" as="p">{s.detail}</Text>
            </Box>
            <Badge color={s.ok ? "green" : "amber"} variant="soft" size="1">
              {s.ok ? "Opérationnel" : "Attention"}
            </Badge>
          </Flex>
          {idx < services.length - 1 && <Separator size="4" />}
        </Box>
      ))}
    </Card>
  );
}

// ─── Page principale ──────────────────────────────────────────────────────────

export function Dashboard() {
  const overviewQ = useQuery<OverviewData>({
    queryKey: ["overview"],
    queryFn:  api.overview,
    refetchInterval: 30_000,
  });
  const jobsQ = useQuery<JobSummary[]>({
    queryKey: ["jobs"],
    queryFn:  () => api.jobs(),
    refetchInterval: 15_000,
  });
  const systemQ = useQuery<SystemStatus>({
    queryKey: ["system"],
    queryFn:  api.system,
    refetchInterval: 60_000,
  });

  const data = overviewQ.data;

  return (
    <Box>
      {/* En-tête */}
      <Flex justify="between" align="start" mb="5">
        <Box>
          <Heading size="6">Tableau de bord EVKHA</Heading>
          <Text size="2" color="gray" as="p" mt="1">
            Pilotage complet de votre activité
          </Text>
        </Box>
        {systemQ.data && (
          <div className={`health-badge health-badge--${systemQ.data.api === "ok" ? "ok" : "down"}`}>
            <span className="health-dot" />
            {systemQ.data.api === "ok" ? "Système opérationnel" : "Système hors ligne"}
          </div>
        )}
      </Flex>

      {/* Bannière d'état global */}
      {systemQ.data && <SystemBanner system={systemQ.data} />}

      {/* Chiffres clés — Activité */}
      {overviewQ.isLoading && (
        <Flex align="center" gap="2" mb="5">
          <Spinner size="2" /><Text color="gray">Chargement…</Text>
        </Flex>
      )}
      {data && (
        <>
          <Text size="1" color="gray" weight="medium" mb="2"
            style={{ display: "block", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Livrables
          </Text>
          <Grid columns={{ initial: "2", sm: "4" }} gap="3" mb="4">
            <StatCard
              label="Total"
              value={data.jobs.total}
              description="Depuis le lancement"
              link="/jobs"
            />
            <StatCard
              label="Aujourd'hui"
              value={data.jobs.today}
              description="Générés ce jour"
              link="/jobs"
            />
            <StatCard
              label="En cours"
              value={data.jobs.running}
              description={data.jobs.running > 0 ? "L'IA travaille en ce moment" : "Aucun en cours"}
              alert={data.jobs.running > 0}
              link="/jobs"
            />
            <StatCard
              label="Échecs"
              value={data.jobs.failed}
              description={data.jobs.failed > 0 ? "À relancer" : "Aucun problème"}
              alert={data.jobs.failed > 0}
              link="/jobs"
            />
          </Grid>

          <Text size="1" color="gray" weight="medium" mb="2"
            style={{ display: "block", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Clients & commandes
          </Text>
          <Grid columns={{ initial: "2", sm: "4" }} gap="3" mb="6">
            <StatCard
              label="Clients"
              value={data.customers.total}
              description="Inscrits au total"
              link="/clients"
            />
            <StatCard
              label="Abonnements actifs"
              value={data.subscriptions.active}
              description="B2B en cours"
              link="/clients"
            />
            <StatCard
              label="Crédits en attente"
              value={data.orders.waiting_intake}
              description="Formulaires non remplis"
              alert={data.orders.waiting_intake > 0}
              link="/orders"
            />
            <StatCard
              label="Incidents ouverts"
              value={data.incidents.open}
              description={data.incidents.critical_or_high > 0 ? `${data.incidents.critical_or_high} critique(s)/haute(s)` : "Aucun critique"}
              alert={data.incidents.critical_or_high > 0}
              link="/incidents"
            />
          </Grid>
        </>
      )}

      {/* Coûts 30 jours */}
      {data && (
        <Card mb="6">
          <Flex align="center" justify="between">
            <Box>
              <Text size="1" color="gray" weight="medium"
                style={{ textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Coût IA — 30 derniers jours
              </Text>
              <Heading size="5" mt="1">
                {parseFloat(data.cost_30d_eur).toFixed(4)} €
              </Heading>
            </Box>
            <Text size="1" color="gray">via Anthropic Claude</Text>
          </Flex>
        </Card>
      )}

      {/* Livrables récents */}
      <Box mb="6">
        <Flex justify="between" align="baseline" mb="3">
          <Box>
            <Heading size="4">Livrables récents</Heading>
            <Text size="1" color="gray" as="p" mt="1">
              Les derniers documents générés pour vos clients
            </Text>
          </Box>
          <Link to="/admin/jobs" style={{ color: "var(--accent-9)", fontSize: 13 }}>
            Voir tous →
          </Link>
        </Flex>
        {jobsQ.isLoading
          ? <Flex align="center" gap="2"><Spinner size="2" /><Text color="gray" size="2">Chargement…</Text></Flex>
          : jobsQ.data
            ? <RecentJobs jobs={jobsQ.data} />
            : null}
      </Box>

      {/* État des services */}
      <Box>
        <Heading size="4" mb="1">État des services</Heading>
        <Text size="1" color="gray" as="p" mb="3">
          Tous ces services doivent être opérationnels pour que le système fonctionne
        </Text>
        {systemQ.isLoading
          ? <Flex align="center" gap="2"><Spinner size="2" /><Text color="gray" size="2">Chargement…</Text></Flex>
          : systemQ.data
            ? <ServiceDetails system={systemQ.data} />
            : null}
      </Box>
    </Box>
  );
}
