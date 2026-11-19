/** La fiche d'un dossier suit la relecture finale — et ne livre pas à sa place.
 *
 * Audit du 19/11/2026, trois états faux sur le même écran de la console.
 *
 * 1. **« En échec » pour une relecture en cours.** La relecture finale ouvre
 *    sa trace AVANT sa première passe — `passes: 0, motif_d_arret: "en cours"`
 *    (`generation.controle_final.relire_et_corriger`) — pour qu'un processus
 *    tué laisse la preuve qu'il avait commencé. L'écran lisait
 *    `passes ? "done" : "failed"` : rouge pendant vingt à soixante minutes.
 *
 * 2. **Une fiche figée.** Elle ne se rafraîchissait que sur `running` : un
 *    dossier relancé (`pending`) restait « en attente », et une relecture en
 *    cours ne bougeait plus sans recharger la page.
 *
 * 3. **« Générer le PDF » envoyait le courriel au client.** Sur un dossier
 *    terminé, `job_redeliver` relance une LIVRAISON COMPLÈTE. Le bouton
 *    s'affichait dès qu'aucun PDF n'était prêt — donc pendant toute la
 *    relecture, qui précède l'assemblage : un clic « pour voir le PDF »
 *    envoyait au client le document en cours de correction.
 *
 * Seul `setInterval` est simulé (c'est lui qui porte `refetchInterval`) ; MSW
 * et les promesses restent réels.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "./server";

vi.mock("@tanstack/react-router", () => ({
  useParams: () => ({ jobId: "9e38eb81" }),
  Link: ({ children }: { children: React.ReactNode }) => <a href="#">{children}</a>,
}));

// Importé APRÈS le simulacre du routeur : la fiche lit `useParams`.
const { JobDetail } = await import("../pages/JobDetail");

const DASH = `${window.location.origin}/api/dashboard`;
const FICHE = `${DASH}/jobs/9e38eb81/`;

/** La trace telle que `_inscrire` l'écrit à l'OUVERTURE de la relecture. */
const TRACE_OUVERTE = {
  type: "relecture_finale",
  passes: 0,
  anomalies_au_depart: 0,
  anomalies_restantes: 0,
  chapitres_reecrits: [],
  chapitres_rattrapes: [],
  chapitres_perdus: [],
  restantes: [],
  motif_d_arret: "en cours",
};

/** La trace d'une relecture allée au bout, deux chapitres repris. */
const TRACE_RENDUE = {
  ...TRACE_OUVERTE,
  passes: 2,
  anomalies_au_depart: 5,
  anomalies_restantes: 0,
  chapitres_reecrits: [4, 12],
  motif_d_arret: "aucune anomalie réparable par une réécriture de chapitre",
};

/** La trace d'une relecture qui n'a PAS pu s'exécuter. */
const TRACE_EN_PANNE = {
  ...TRACE_OUVERTE,
  motif_d_arret: "relecture impossible (RuntimeError : gate illisible)",
};

const PDF_PRET = {
  id: "a-1",
  kind: "pdf",
  status: "ready",
  download_url: "https://api.exemple/media/9e38eb81.pdf?s=x",
};

function dossier(surcharge: Record<string, unknown> = {}) {
  return {
    id: "9e38eb81",
    deliverable_type: "business_plan",
    status: "done",
    interrompue: false,
    minutes_sans_progression: null,
    qa_status: "pending",
    total_cost_eur: "5.1200",
    budget_eur: "8.0000",
    chapters_done: 22,
    chapters_total: 22,
    started_at: "2026-11-18T09:00:00Z",
    completed_at: "2026-11-18T09:40:00Z",
    order_id: "cmd-1",
    error_message: null,
    pdf_download_url: null,
    delivery_status: null,
    chapters: [],
    artifacts: [],
    customer_email: "eva@exemple.fr",
    customer_id: "c-1",
    offer_name: "Business plan",
    delivery: null,
    credits_restitues: false,
    controle_final: null,
    ...surcharge,
  };
}

function rendre() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <JobDetail />
    </QueryClientProvider>,
  );
}

function servir(charge: () => object) {
  const appels = { nombre: 0, relivraisons: 0 };
  server.use(
    http.get(FICHE, () => {
      appels.nombre += 1;
      return HttpResponse.json(charge());
    }),
    http.post(`${FICHE}redeliver/`, () => {
      appels.relivraisons += 1;
      return HttpResponse.json({ job_id: "9e38eb81", status: "delivery_queued" }, { status: 202 });
    }),
  );
  return appels;
}

/** L'état d'une étape de la chaîne, tel qu'un lecteur d'écran l'entend. */
function etape(nom: RegExp): string {
  return screen.getByText(nom).closest("li")?.textContent ?? "";
}

async function laisserPasserUneMinute() {
  await act(async () => {
    vi.advanceTimersByTime(60_000);
    await new Promise((fin) => setTimeout(fin, 120));
  });
}

describe("la fiche d'un dossier suit la relecture finale", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  // ── 1. La chaîne de production ────────────────────────────────────────────

  it("une relecture ouverte se lit « en cours », pas « en échec »", async () => {
    servir(() => dossier({ controle_final: TRACE_OUVERTE }));
    rendre();

    await screen.findByText("Contrôle du document");
    expect(etape(/^Contrôle du document$/)).toMatch(/en cours/);
    expect(etape(/^Contrôle du document$/)).not.toMatch(/en échec|terminée|document propre/);
  });

  it("contre-épreuve : une relecture rendue se lit « terminée », avec ce qu'elle a fait", async () => {
    servir(() => dossier({ controle_final: TRACE_RENDUE }));
    rendre();

    await screen.findByText("Contrôle du document");
    expect(etape(/^Contrôle du document$/)).toMatch(/terminée/);
    expect(etape(/^Contrôle du document$/)).toMatch(/2 chapitre\(s\) corrigé\(s\)/);
  });

  it("contre-épreuve : une relecture qui n'a pas pu s'exécuter reste « en échec »", async () => {
    servir(() => dossier({ controle_final: TRACE_EN_PANNE }));
    rendre();

    await screen.findByText("Contrôle du document");
    expect(etape(/^Contrôle du document$/)).toMatch(/en échec/);
  });

  it("contre-épreuve : une trace restée ouverte sur un document DÉJÀ envoyé n'est plus « en cours »", async () => {
    // La relecture a été tuée, le gardien a livré le document tel quel.
    servir(() =>
      dossier({
        controle_final: TRACE_OUVERTE,
        artifacts: [PDF_PRET],
        delivery: { status: "sent", sent_at: "2026-11-18T10:30:00Z" },
        delivery_status: "sent",
      }),
    );
    rendre();

    await screen.findByText("Contrôle du document");
    expect(etape(/^Contrôle du document$/)).not.toMatch(/en cours/);
  });

  // ── 2. Le rafraîchissement ────────────────────────────────────────────────

  it("un dossier en attente se rafraîchit, jusqu'à ce qu'il démarre", async () => {
    const appels = servir(() =>
      dossier({ status: appels.nombre <= 1 ? "pending" : "running", chapters_done: 0, completed_at: null }),
    );
    rendre();

    expect(await screen.findByText(/En attente/)).toBeInTheDocument();
    expect(appels.nombre).toBe(1);
    await laisserPasserUneMinute();
    expect(await screen.findByText(/En cours/)).toBeInTheDocument();
    expect(appels.nombre).toBeGreaterThan(1);
  });

  it("une relecture en cours se rafraîchit, jusqu'à ce qu'elle rende sa trace", async () => {
    const appels = servir(() =>
      dossier({ controle_final: appels.nombre <= 1 ? TRACE_OUVERTE : TRACE_RENDUE }),
    );
    rendre();

    await screen.findByText("Contrôle du document");
    expect(etape(/^Contrôle du document$/)).toMatch(/en cours/);
    await laisserPasserUneMinute();
    await waitFor(() => expect(etape(/^Contrôle du document$/)).toMatch(/terminée/));
    expect(appels.nombre).toBe(2);
  });

  it("contre-épreuve : un dossier terminé et relu ne se sonde plus", async () => {
    const appels = servir(() =>
      dossier({
        controle_final: TRACE_RENDUE,
        artifacts: [PDF_PRET],
        delivery: { status: "sent", sent_at: "2026-11-18T10:30:00Z" },
      }),
    );
    rendre();

    await screen.findByText("Contrôle du document");
    await laisserPasserUneMinute();
    expect(appels.nombre).toBe(1);
  });

  // ── 3. Le bouton de livraison ─────────────────────────────────────────────

  it("pendant la relecture, aucun bouton ne propose de livrer", async () => {
    servir(() => dossier({ controle_final: TRACE_OUVERTE }));
    rendre();

    await screen.findByText("Contrôle du document");
    expect(screen.queryByRole("button", { name: /Générer le PDF/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /livraison/i })).toBeNull();
    // Et l'écran dit pourquoi : la livraison part d'elle-même.
    expect(screen.getByText(/Contrôle final en cours/)).toBeInTheDocument();
  });

  it("avant toute trace de relecture, aucun bouton ne propose de livrer", async () => {
    servir(() => dossier({ controle_final: null }));
    rendre();

    await screen.findByText("Contrôle du document");
    expect(screen.queryByRole("button", { name: /Générer le PDF/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /livraison/i })).toBeNull();
  });

  it("relecture rendue : le bouton dit qu'il envoie le courriel, et attend un accord", async () => {
    const appels = servir(() => dossier({ controle_final: TRACE_RENDUE }));
    const accord = vi.spyOn(window, "confirm").mockReturnValue(false);
    rendre();

    const bouton = await screen.findByRole("button", { name: /Relancer la livraison/ });
    expect(bouton).toHaveTextContent(/courriel au client/);
    expect(screen.queryByRole("button", { name: /Générer le PDF/ })).toBeNull();

    // Un refus n'envoie rien.
    fireEvent.click(bouton);
    await new Promise((fin) => setTimeout(fin, 60));
    expect(String(accord.mock.calls[0][0])).toMatch(/courriel de livraison partira chez le client/);
    expect(appels.relivraisons).toBe(0);

    // Un accord relance la livraison.
    accord.mockReturnValue(true);
    fireEvent.click(bouton);
    await waitFor(() => expect(appels.relivraisons).toBe(1));
  });

  it("contre-épreuve : sur un dossier en ÉCHEC, « Générer le PDF » reste — il n'envoie rien au client", async () => {
    const appels = servir(() =>
      dossier({
        status: "failed",
        chapters_done: 1,
        chapters: [
          {
            number: 1,
            title: "Chapitre 1",
            prompt_key: "bp.1",
            status: "done",
            cost_eur: "0.1000",
            input_tokens: 10,
            output_tokens: 20,
            retry_count: 0,
            error_message: null,
          },
        ],
      }),
    );
    const accord = vi.spyOn(window, "confirm").mockReturnValue(false);
    rendre();

    const bouton = await screen.findByRole("button", { name: "Générer le PDF" });
    fireEvent.click(bouton);
    await waitFor(() => expect(appels.relivraisons).toBe(1));
    // Aucun accord demandé : ce geste ne part pas chez le client.
    expect(accord).not.toHaveBeenCalled();
  });
});
