/** Un dossier « intervention requise » a un nom, un filtre, et se relance.
 *
 * Audit du 19/11/2026. Le serveur accepte la relance d'un dossier
 * `intervention_requise` dès qu'un de ses chapitres est en échec
 * (`job_relaunch`, `backend/dashboard/views.py`, depuis le business plan
 * `db3aa88d` du 16/11). La console, elle, ne connaissait pas ce statut : il
 * s'affichait sous sa clé brute (« intervention_requise intervention_requise »
 * en tête de fiche), ne figurait pas dans le filtre, et n'avait pas de bouton.
 * Le seul moyen de se servir du correctif restait une requête écrite à la
 * main — sur les dossiers qui attendent précisément un geste.
 *
 * Trois verrous : la règle (`estRelancable`), les deux écrans, et la CLASSE —
 * chaque statut de génération a son libellé dans les deux tables de la console.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique. Les gestionnaires MSW visent
 * `window.location.origin` (jsdom : http://localhost:3000).
 */
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { estRelancable } from "../api";
import { server } from "./server";

vi.mock("@tanstack/react-router", () => ({
  useParams: () => ({ jobId: "db3aa88d" }),
  Link: ({ children }: { children: React.ReactNode }) => <a href="#">{children}</a>,
}));

// Importés APRÈS le simulacre du routeur.
const { Jobs } = await import("../pages/Jobs");
const { JobDetail } = await import("../pages/JobDetail");

const DASH = `${window.location.origin}/api/dashboard`;

/** Les statuts d'un dossier, recopiés de `generation.models.JobStatus`. */
const STATUTS_DE_GENERATION = [
  "pending",
  "running",
  "done",
  "failed",
  "cancelled",
  "intervention_requise",
];

function chapitre(number: number, status: string) {
  return {
    number,
    title: `Chapitre ${number}`,
    prompt_key: `bp.${number}`,
    status,
    cost_eur: "0.1000",
    input_tokens: 1000,
    output_tokens: 2000,
    retry_count: 0,
    error_message: status === "failed" ? "Format de sortie invalide" : null,
  };
}

/** Le business plan `db3aa88d` : 22 chapitres, le cinquième mort. */
function dossier(surcharge: Record<string, unknown> = {}) {
  const chapters = Array.from({ length: 22 }, (_, i) =>
    chapitre(i + 1, i + 1 === 5 ? "failed" : "done"),
  );
  return {
    id: "db3aa88d",
    deliverable_type: "business_plan",
    status: "intervention_requise",
    interrompue: false,
    minutes_sans_progression: null,
    qa_status: "pending",
    total_cost_eur: "5.1200",
    budget_eur: "8.0000",
    chapters_done: 21,
    chapters_total: 22,
    started_at: "2026-11-16T09:00:00Z",
    completed_at: null,
    order_id: "cmd-1",
    error_message: "Chapitre 5 : 3 tentative(s) échouée(s).",
    pdf_download_url: null,
    delivery_status: null,
    chapters,
    artifacts: [],
    customer_email: "eva@exemple.fr",
    customer_id: "c-1",
    offer_name: "Business plan",
    delivery: null,
    credits_restitues: false,
    ...surcharge,
  };
}

function rendre(ecran: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ecran}</QueryClientProvider>);
}

describe("un dossier en intervention requise se relance", () => {
  // ── La règle ──────────────────────────────────────────────────────────────

  it("est relançable avec un chapitre en échec", () => {
    // Sur la fiche, qui connaît ses chapitres…
    expect(estRelancable(dossier())).toBe(true);
    // … et dans la liste, qui n'en a que le compte.
    expect(
      estRelancable({
        status: "intervention_requise",
        interrompue: false,
        chapters_done: 21,
        chapters_total: 22,
      }),
    ).toBe(true);
  });

  it("contre-épreuve : complet, il a été retenu au contrôle — rien à relancer", () => {
    const complet = Array.from({ length: 21 }, (_, i) => chapitre(i + 1, "done"));
    expect(
      estRelancable(dossier({ chapters_done: 21, chapters_total: 21, chapters: complet })),
    ).toBe(false);
    expect(
      estRelancable({
        status: "intervention_requise",
        interrompue: false,
        chapters_done: 21,
        chapters_total: 21,
      }),
    ).toBe(false);
  });

  it("contre-épreuve : sur la fiche, un chapitre manquant sans échec ne suffit pas", () => {
    // Le serveur exige un chapitre FAILED pour ce statut, et ne normalise rien.
    const sansEchec = Array.from({ length: 22 }, (_, i) =>
      chapitre(i + 1, i + 1 === 5 ? "skipped" : "done"),
    );
    expect(estRelancable(dossier({ chapters: sansEchec }))).toBe(false);
  });

  it("contre-épreuve : les autres statuts gardent leur règle", () => {
    const base = { interrompue: false, chapters_done: 22, chapters_total: 22 };
    expect(estRelancable({ ...base, status: "failed" })).toBe(true);
    expect(estRelancable({ ...base, status: "cancelled" })).toBe(true);
    expect(estRelancable({ ...base, status: "done" })).toBe(false);
    expect(estRelancable({ ...base, status: "done", chapters_done: 20 })).toBe(true);
    expect(estRelancable({ ...base, status: "running" })).toBe(false);
    expect(estRelancable({ ...base, status: "running", interrompue: true })).toBe(true);
    expect(estRelancable({ ...base, status: "pending" })).toBe(false);
  });

  // ── La liste ──────────────────────────────────────────────────────────────

  it("la liste le nomme, le filtre, et pose son bouton", async () => {
    server.use(
      http.get(`${DASH}/jobs/`, () => HttpResponse.json([dossier({ chapters: undefined })])),
    );
    rendre(<Jobs />);

    const ligne = (await screen.findByText("Business Plan")).closest("tr") as HTMLElement;
    expect(within(ligne).getByText("Intervention requise")).toBeInTheDocument();
    expect(within(ligne).queryByText(/intervention_requise/)).toBeNull();
    expect(within(ligne).getByRole("button", { name: /Relancer/ })).toBeInTheDocument();

    // Le filtre porte la valeur que le serveur attend (`?status=`).
    const filtre = screen.getByRole("combobox");
    const option = within(filtre).getByRole("option", { name: "Intervention requise" });
    expect(option).toHaveValue("intervention_requise");
  });

  it("contre-épreuve — la liste : un dossier retenu complet n'a pas de bouton", async () => {
    server.use(
      http.get(`${DASH}/jobs/`, () =>
        HttpResponse.json([
          dossier({ chapters: undefined, chapters_done: 21, chapters_total: 21 }),
        ]),
      ),
    );
    rendre(<Jobs />);

    const ligne = (await screen.findByText("Business Plan")).closest("tr") as HTMLElement;
    expect(within(ligne).getByText("Intervention requise")).toBeInTheDocument();
    expect(within(ligne).queryByRole("button", { name: /Relancer/ })).toBeNull();
  });

  // ── La fiche ──────────────────────────────────────────────────────────────

  it("la fiche le nomme, et propose la relance", async () => {
    server.use(http.get(`${DASH}/jobs/db3aa88d/`, () => HttpResponse.json(dossier())));
    rendre(<JobDetail />);

    expect(
      await screen.findByRole("button", { name: /Relancer la génération/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Intervention requise/)).toBeInTheDocument();
    expect(screen.queryByText(/intervention_requise/)).toBeNull();
    // La génération s'est arrêtée sur un chapitre : elle n'est pas « en attente ».
    expect(screen.getByText(/Génération IA/).textContent).toMatch(/en échec/);
  });

  it("contre-épreuve — la fiche : un crédit rendu ferme la relance, ici aussi", async () => {
    server.use(
      http.get(`${DASH}/jobs/db3aa88d/`, () =>
        HttpResponse.json(dossier({ credits_restitues: true })),
      ),
    );
    rendre(<JobDetail />);

    expect(await screen.findByRole("button", { name: /Rétablir/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Relancer la génération/ })).toBeNull();
  });

  // ── La classe : chaque statut a son nom ───────────────────────────────────

  const PAGES = join(process.cwd(), "src", "pages");

  /** Le corps d'une table `const NOM … = { … };` d'un écran. */
  function table(page: string, nom: string): string {
    const source = readFileSync(join(PAGES, page), "utf-8");
    const debut = source.indexOf(`const ${nom}`);
    expect(debut, `${page} : table ${nom} introuvable`).toBeGreaterThanOrEqual(0);
    return source.slice(debut, source.indexOf("};", debut));
  }

  for (const statut of STATUTS_DE_GENERATION) {
    it(`« ${statut} » a son libellé dans la liste et sur la fiche, et son glyphe`, () => {
      const cle = new RegExp(`\\b${statut}:\\s*"[^"]+"`);
      expect(table("Jobs.tsx", "STATUS_LABELS")).toMatch(cle);
      expect(table("JobDetail.tsx", "STATUS_LABELS")).toMatch(cle);
      expect(table("JobDetail.tsx", "STATUS_ICON")).toMatch(cle);
    });
  }
});
