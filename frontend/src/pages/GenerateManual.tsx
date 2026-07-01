import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  Box, Heading, Text, Card, Flex, Separator, Button,
} from "@radix-ui/themes";
import { api, type GenerateRequest } from "../api";

const TYPES = [
  { value: "market_study",      label: "Étude de marché" },
  { value: "competitor_study",  label: "Étude de concurrence" },
  { value: "business_plan",     label: "Business Plan" },
  { value: "business_strategy", label: "Stratégie Business" },
];

const OPTIONAL_BY_TYPE: Record<string, { key: string; label: string; placeholder: string }[]> = {
  competitor_study: [
    { key: "CONCURRENTS", label: "Concurrents identifiés", placeholder: "Ex : Décathlon, Go Sport, Intersport" },
  ],
  business_plan: [
    { key: "CAPITAL_INITIAL",   label: "Capital initial",      placeholder: "Ex : 10 000 €" },
    { key: "FORME_JURIDIQUE",   label: "Forme juridique",      placeholder: "Ex : SAS, SARL, auto-entrepreneur" },
    { key: "MODELE_REVENUS",    label: "Modèle de revenus",    placeholder: "Ex : abonnement mensuel, vente directe" },
    { key: "EQUIPE",            label: "Équipe / associés",    placeholder: "Ex : 2 associés, 1 salarié" },
  ],
  business_strategy: [
    { key: "OBJECTIF_STRATEGIQUE",   label: "Objectif stratégique",    placeholder: "Ex : atteindre 500 clients en 12 mois" },
    { key: "HORIZON_PLANIFICATION",  label: "Horizon de planification", placeholder: "Ex : 3 ans" },
  ],
};

function Field({
  label, id, value, onChange, placeholder, required, textarea,
}: {
  label: string; id: string; value: string;
  onChange: (v: string) => void; placeholder?: string;
  required?: boolean; textarea?: boolean;
}) {
  const inputStyle: React.CSSProperties = {
    width: "100%", padding: "8px 10px", borderRadius: 6,
    border: "1px solid var(--gray-6)", background: "var(--color-background)",
    color: "var(--gray-12)", fontSize: 14, fontFamily: "inherit",
    resize: textarea ? "vertical" : undefined,
    minHeight: textarea ? 80 : undefined,
  };
  return (
    <Box mb="3">
      <Text as="label" htmlFor={id} size="2" weight="medium">
        {label}{required && <Text color="red"> *</Text>}
      </Text>
      <Box mt="1">
        {textarea
          ? <textarea id={id} style={inputStyle} value={value} placeholder={placeholder}
              onChange={e => onChange(e.target.value)} rows={3} />
          : <input id={id} type="text" style={inputStyle} value={value}
              placeholder={placeholder} onChange={e => onChange(e.target.value)} />}
      </Box>
    </Box>
  );
}

type FormData = Omit<GenerateRequest, "deliverable_type"> & { deliverable_type: string };

const EMPTY: FormData = {
  deliverable_type: "market_study",
  customer_email: "", first_name: "", last_name: "", company_name: "",
  SECTEUR: "", PAYS: "", PROJET: "", ZONE: "",
  ELEMENTS_A_RETENIR: "", DEMANDES_SPECIFIQUES: "", CONCURRENTS: "",
  CAPITAL_INITIAL: "", FORME_JURIDIQUE: "", MODELE_REVENUS: "", EQUIPE: "",
  OBJECTIF_STRATEGIQUE: "", HORIZON_PLANIFICATION: "",
  NOM_ENTREPRISE: "", LOGO_URL: "", COULEUR_PRINCIPALE: "", COULEUR_SECONDAIRE: "",
};

export function GenerateManual() {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormData>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (key: keyof FormData) => (v: string) =>
    setForm(prev => ({ ...prev, [key]: v }));

  const optionalFields = OPTIONAL_BY_TYPE[form.deliverable_type] ?? [];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { job_id } = await api.generate(form as GenerateRequest);
      await navigate({ to: "/jobs/$jobId", params: { jobId: job_id } });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box>
      <Heading size="6" mb="1">Générer un livrable</Heading>
      <Text size="2" color="gray" as="p" mb="5">
        Pour tes ventes ComeUp ou toute génération sans passer par le site
      </Text>

      <form onSubmit={handleSubmit}>
        <Card mb="4">
          <Heading size="3" mb="3">Client</Heading>
          <Field id="email" label="Email du client" value={form.customer_email}
            onChange={set("customer_email")} placeholder="client@example.com" required />
          <Flex gap="3">
            <Box style={{ flex: 1 }}>
              <Field id="first_name" label="Prénom" value={form.first_name ?? ""}
                onChange={set("first_name")} placeholder="Marie" />
            </Box>
            <Box style={{ flex: 1 }}>
              <Field id="last_name" label="Nom" value={form.last_name ?? ""}
                onChange={set("last_name")} placeholder="Dupont" />
            </Box>
          </Flex>
          <Field id="company_name" label="Société" value={form.company_name ?? ""}
            onChange={set("company_name")} placeholder="ACME SAS" />
        </Card>

        <Card mb="4">
          <Heading size="3" mb="3">Type de livrable</Heading>
          <Box mb="2">
            <Text as="label" size="2" weight="medium">
              Type d'étude<Text color="red"> *</Text>
            </Text>
          </Box>
          <Flex gap="2" wrap="wrap" mb="2">
            {TYPES.map(t => (
              <button key={t.value} type="button"
                onClick={() => set("deliverable_type")(t.value)}
                style={{
                  padding: "6px 14px", borderRadius: 20, fontSize: 13, cursor: "pointer",
                  border: form.deliverable_type === t.value
                    ? "2px solid var(--accent-9)" : "2px solid var(--gray-5)",
                  background: form.deliverable_type === t.value
                    ? "var(--accent-3)" : "transparent",
                  color: form.deliverable_type === t.value
                    ? "var(--accent-11)" : "var(--gray-11)",
                  fontWeight: form.deliverable_type === t.value ? 600 : 400,
                }}>
                {t.label}
              </button>
            ))}
          </Flex>
        </Card>

        <Card mb="4">
          <Heading size="3" mb="3">Paramètres de l'étude</Heading>
          <Field id="SECTEUR" label="Secteur d'activité" value={form.SECTEUR}
            onChange={set("SECTEUR")} placeholder="Ex : restauration, cosmétique, e-commerce" required />
          <Field id="PAYS" label="Pays / Marché cible" value={form.PAYS}
            onChange={set("PAYS")} placeholder="Ex : France, Belgique, Sénégal" required />
          <Field id="ZONE" label="Zone géographique" value={form.ZONE}
            onChange={set("ZONE")} placeholder="Ex : Paris 11e, Grand Lyon, National" required />
          <Field id="PROJET" label="Description du projet" value={form.PROJET}
            onChange={set("PROJET")} textarea
            placeholder="Décris le projet en quelques phrases : ce que propose le client, à qui, comment." required />

          {optionalFields.length > 0 && (
            <>
              <Separator size="4" my="3" />
              {optionalFields.map(f => (
                <Field key={f.key} id={f.key} label={f.label}
                  value={(form as Record<string, string>)[f.key] ?? ""}
                  onChange={set(f.key as keyof FormData)}
                  placeholder={f.placeholder} />
              ))}
            </>
          )}

          <Separator size="4" my="3" />

          <Field id="ELEMENTS_A_RETENIR" label="Éléments importants à retenir (optionnel)"
            value={form.ELEMENTS_A_RETENIR ?? ""} onChange={set("ELEMENTS_A_RETENIR")} textarea
            placeholder="Points spécifiques que l'IA doit absolument mentionner ou approfondir." />
          <Field id="DEMANDES_SPECIFIQUES" label="Demandes spécifiques (optionnel)"
            value={form.DEMANDES_SPECIFIQUES ?? ""} onChange={set("DEMANDES_SPECIFIQUES")} textarea
            placeholder="Angles particuliers, ton souhaité, sections à prioriser, etc." />
        </Card>

        <Card mb="4">
          <Heading size="3" mb="1">Branding PDF (optionnel)</Heading>
          <Text size="2" color="gray" as="p" mb="3">
            Ces champs personnalisent la page de garde et les couleurs du document généré.
          </Text>
          <Field id="LOGO_URL" label="URL du logo" value={form.LOGO_URL ?? ""}
            onChange={set("LOGO_URL")}
            placeholder="https://example.com/logo.png (PNG ou SVG, fond transparent)" />
          <Field id="NOM_ENTREPRISE" label="Nom de l'entreprise" value={form.NOM_ENTREPRISE ?? ""}
            onChange={set("NOM_ENTREPRISE")} placeholder="Ex : EVKHA, Synapses Conseil…" />
          <Flex gap="3">
            <Box style={{ flex: 1 }}>
              <Field id="COULEUR_PRINCIPALE" label="Couleur principale" value={form.COULEUR_PRINCIPALE ?? ""}
                onChange={set("COULEUR_PRINCIPALE")} placeholder="#1A1A1A" />
            </Box>
            <Box style={{ flex: 1 }}>
              <Field id="COULEUR_SECONDAIRE" label="Couleur secondaire (accent)" value={form.COULEUR_SECONDAIRE ?? ""}
                onChange={set("COULEUR_SECONDAIRE")} placeholder="#C9A227" />
            </Box>
          </Flex>
        </Card>

        {error && (
          <Card mb="4" style={{ borderColor: "var(--red-7)", background: "var(--red-2)" }}>
            <Text color="red" size="2">{error}</Text>
          </Card>
        )}

        <Flex justify="end" gap="3">
          <Button type="submit" size="3" disabled={loading}>
            {loading ? "Génération en cours…" : "Lancer la génération"}
          </Button>
        </Flex>
      </form>
    </Box>
  );
}
