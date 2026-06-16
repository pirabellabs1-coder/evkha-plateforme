import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Card, Grid, Flex, Box, Text, Heading, Badge, Separator, Spinner,
} from "@radix-ui/themes";
import { api, type OverviewData, type JobSummary, type SystemStatus } from "../api";

const DELIVERABLE_LABELS: Record<string, string> = {
  market_study: "Étude de marché",
  competitor_study: "Étude de concurrence",
  business_plan: "Business Plan",
  business_strategy: "Stratégie Business",
};

type RadixColor = "gray" | "blue" | "green" | "red" | "amber" | "orange";

function statusColor(status: string): RadixColor {
  const map: Record<string, RadixColor> = {
    pending: "gray", running: "blue", done: "green", failed: "red", cancelled: "gray",
  };
  return map[status] ?? "gray";
}

function StatCard({ label, value, sub, alert }: {
  label: string; value: string | number; sub?: string; alert?: boolean;
}) {
  return (
    <Card size="2" style={alert ? { borderColor: "var(--orange-7)" } : undefined}>
      <Text size="1" color="gray" weight="medium"
        style={{ display: "block", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </Text>
      <Heading size="6" mt="1" color={alert ? "orange" : undefined}>{value}</Heading>
      {sub && <Text size="1" color="gray" as="p" mt="1">{sub}</Text>}
    </Card>
  );
}

function MiniPipeline({ job }: { job: JobSummary }) {
  const isRunning = job.status === "running";
  const isDone = job.status === "done";
  const isFailed = job.status === "failed";
  const stages = [
    "done",
    isDone ? "done" : isFailed ? "failed" : isRunning ? "running" : "pending",
    isDone ? "done" : "pending",
    isDone ? "done" : "pending",
  ];
  return (
    <div className="mini-pipeline">
      {stages.map((s, i) => (
        <span key={i}>
          <span className={`mp-dot mp-dot--${s}`} />
          {i < stages.length - 1 && <span className="mp-arrow">›</span>}
        </span>
      ))}
    </div>
  );
}

function RecentJobs({ jobs }: { jobs: JobSummary[] }) {
  const recent = jobs.slice(0, 5);
  if (recent.length === 0) {
    return (
      <Card>
        <Text size="2" color="gray" style={{ fontStyle: "italic" }}>
          Aucun livrable pour l'instant.
        </Text>
      </Card>
    );
  }
  return (
    <Card style={{ padding: 0 }}>
      {recent.map((job, idx) => (
        <Box key={job.id}>
          <Flex align="center" gap="3" px="4" py="3">
            <Text size="2" weight="medium" style={{ flex: 1 }}>
              {DELIVERABLE_LABELS[job.deliverable_type] ?? job.deliverable_type}
            </Text>
            <MiniPipeline job={job} />
            <Badge color={statusColor(job.status)} variant="soft">
              {job.status === "running" ? "En cours ⚡"
                : job.status === "done" ? "Terminé ✓"
                : job.status === "failed" ? "Échec ✗"
                : "En attente"}
            </Badge>
            {job.status === "running" && (
              <Text size="1" color="gray" className="mono">
                {job.chapters_done}/{job.chapters_total} ch.
              </Text>
            )}
            {job.status === "done" && (
              <Text size="1" color="gray" className="mono">
                {parseFloat(job.total_cost_eur).toFixed(4)} €
              </Text>
            )}
            <Link to="/jobs/$jobId" params={{ jobId: job.id }}
              style={{ color: "var(--accent-9)", textDecoration: "none", fontSize: 13 }}>
              →
            </Link>
          </Flex>
          {idx < recent.length - 1 && <Separator size="4" />}
        </Box>
      ))}
    </Card>
  );
}

function ConfigStatus({ system }: { system: SystemStatus }) {
  const items = [
    { label: "API EVKHA",      ok: system.api === "ok",  okText: "En ligne", warnText: "Hors ligne" },
    { label: "Email — Brevo",  ok: !system.email_stub,   okText: "Actif",    warnText: "STUB — BREVO_API_KEY requise" },
    { label: "IA — Anthropic", ok: !system.ai_stub,      okText: "Actif",    warnText: "STUB — ANTHROPIC_API_KEY requise" },
    { label: "PDF — WeasyPrint", ok: true,               okText: "Actif",    warnText: "" },
  ];
  return (
    <Card style={{ padding: 0 }}>
      {items.map((item, idx) => (
        <Box key={item.label}>
          <Flex align="center" gap="3" px="4" py="3">
            <Box style={{
              width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
              background: item.ok ? "var(--green-9)" : "var(--amber-9)",
            }} />
            <Text size="2" style={{ flex: 1 }}>{item.label}</Text>
            <Badge color={item.ok ? "green" : "amber"} variant="soft" size="1">
              {item.ok ? item.okText : item.warnText}
            </Badge>
          </Flex>
          {idx < items.length - 1 && <Separator size="4" />}
        </Box>
      ))}
    </Card>
  );
}

function SetupGuide() {
  const steps = [
    { done: true,  text: "API déployée",                         sub: "evkha.fr" },
    { done: true,  text: "Dashboard opérationnel",               sub: "dashboard.evkha.fr" },
    { done: true,  text: "Email Brevo activé",                   sub: "contact@evkha.fr" },
    { done: true,  text: "IA Anthropic activée",                 sub: "claude-sonnet-4-6" },
    { done: false, text: "Configurer webhooks Systeme.io + Tally", sub: "URLs dans ACCES-EVKHA.md" },
    { done: true,  text: "Domaine evkha.fr actif",               sub: "DNS IONOS → 82.165.31.105" },
  ];
  return (
    <Card style={{ padding: 0 }}>
      {steps.map((step, i) => (
        <Box key={i}>
          <Flex align="start" gap="3" px="4" py="3">
            <Box style={{
              width: 20, height: 20, borderRadius: "50%", flexShrink: 0, marginTop: 1,
              background: step.done ? "var(--green-9)" : "var(--gray-5)",
              color: step.done ? "white" : "var(--gray-9)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 10, fontWeight: 700,
            }}>
              {step.done ? "✓" : i + 1}
            </Box>
            <Box>
              <Text size="2">{step.text}</Text>
              {step.sub && <Text size="1" color="gray" as="p">{step.sub}</Text>}
            </Box>
          </Flex>
          {i < steps.length - 1 && <Separator size="4" />}
        </Box>
      ))}
    </Card>
  );
}

export function Dashboard() {
  const overviewQ = useQuery<OverviewData>({
    queryKey: ["overview"],
    queryFn: api.overview,
    refetchInterval: 30_000,
  });
  const jobsQ = useQuery<JobSummary[]>({
    queryKey: ["jobs"],
    queryFn: () => api.jobs(),
    refetchInterval: 15_000,
  });
  const systemQ = useQuery<SystemStatus>({
    queryKey: ["system"],
    queryFn: api.system,
    refetchInterval: 60_000,
  });

  const data = overviewQ.data;

  return (
    <Box>
      <Flex justify="between" align="center" mb="6">
        <Heading size="6">Vue d'ensemble</Heading>
        {systemQ.data && (
          <div className={`health-badge health-badge--${systemQ.data.api === "ok" ? "ok" : "down"}`}>
            <span className="health-dot" />
            {systemQ.data.api === "ok" ? "API en ligne" : "API hors ligne"}
          </div>
        )}
      </Flex>

      {overviewQ.isLoading && (
        <Flex align="center" gap="2">
          <Spinner size="2" />
          <Text color="gray">Chargement…</Text>
        </Flex>
      )}

      {data && (
        <>
          <Grid columns={{ initial: "2", sm: "3", lg: "6" }} gap="3" mb="6">
            <StatCard label="Total livrables" value={data.jobs.total} />
            <StatCard label="Aujourd'hui" value={data.jobs.today} />
            <StatCard label="En cours" value={data.jobs.running}
              sub={data.jobs.running > 0 ? "⚡ actifs" : undefined}
              alert={data.jobs.running > 0} />
            <StatCard label="Échecs" value={data.jobs.failed}
              sub={data.jobs.failed > 0 ? "à vérifier" : undefined}
              alert={data.jobs.failed > 0} />
            <StatCard label="Coût IA / 30j"
              value={`${parseFloat(data.cost_30d_eur).toFixed(4)} €`}
              sub="plafond : 2 € / dossier" />
            <StatCard label="Incidents" value={data.incidents.open}
              sub={`dont ${data.incidents.critical_or_high} critiques`}
              alert={data.incidents.critical_or_high > 0} />
          </Grid>

          <Flex justify="between" align="center" mb="3">
            <Heading size="4">Derniers livrables</Heading>
            <Link to="/jobs" style={{ color: "var(--accent-9)", fontSize: 13 }}>
              Voir tous →
            </Link>
          </Flex>
          {jobsQ.data ? <RecentJobs jobs={jobsQ.data} /> : <Spinner size="2" />}
        </>
      )}

      <Grid columns={{ initial: "1", md: "2" }} gap="5" mt="6">
        <Box>
          <Heading size="4" mb="3" mt="2">Configuration système</Heading>
          {systemQ.data ? <ConfigStatus system={systemQ.data} /> : <Spinner size="2" />}
        </Box>
        <Box>
          <Heading size="4" mb="3" mt="2">Prochaines étapes</Heading>
          <SetupGuide />
        </Box>
      </Grid>
    </Box>
  );
}
