/** « Rétablir » défait une annulation faite par erreur — sur confirmation.
 *
 * 29/09/2026, business plan `cb59cede` : annulé par erreur alors qu'il
 * attendait sa relance. L'annulation rend le crédit, et une étude remboursée
 * ne se relance plus. Le bouton demande au serveur de reprendre le crédit ;
 * il ne part qu'après accord, et un refus s'affiche tel que le serveur l'écrit.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique. Les gestionnaires MSW
 * visent `window.location.origin` (jsdom : http://localhost:3000).
 */
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { server } from "./server";

vi.mock("@tanstack/react-router", () => ({
  useParams: () => ({ jobId: "cb59cede" }),
  Link: ({ children }: { children: React.ReactNode }) => <a href="#">{children}</a>,
}));

// Importé APRÈS le simulacre du routeur : la fiche lit `useParams`.
const { JobDetail } = await import("../pages/JobDetail");

const DASH = `${window.location.origin}/api/dashboard`;

function dossier(status: string, credits_restitues = true) {
  return {
    credits_restitues,
    id: "cb59cede",
    deliverable_type: "business_plan",
    status,
    interrompue: false,
    minutes_sans_progression: null,
    qa_status: "pending",
    total_cost_eur: "1.13",
    budget_eur: "8.00",
    chapters_done: 0,
    chapters_total: 22,
    started_at: "2026-09-29T14:34:47Z",
    completed_at: null,
    order_id: "cmd-1",
    error_message: "Socle non établi",
    pdf_download_url: null,
    delivery_status: null,
    chapters: [],
    artifacts: [],
    customer_email: "eva@exemple.fr",
    customer_id: "c-1",
    offer_name: "Business plan",
    delivery: null,
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

function serveur(appels: string[], refus?: string) {
  server.use(
    http.get(`${DASH}/jobs/cb59cede/`, () => HttpResponse.json(dossier("cancelled"))),
    http.post(`${DASH}/jobs/cb59cede/retablir/`, () => {
      appels.push("retablir");
      return refus
        ? HttpResponse.json({ error: refus }, { status: 409 })
        : HttpResponse.json({ job_id: "cb59cede", status: "cancelled", message: "Étude rétablie : 1 crédit(s) repris" });
    }),
  );
}

describe("une annulation par erreur se rétablit", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("rétablit après accord", async () => {
    const appels: string[] = [];
    serveur(appels);
    const confirmation = vi.spyOn(window, "confirm").mockReturnValue(true);
    rendre();

    fireEvent.click(await screen.findByRole("button", { name: /Rétablir/ }));

    await waitFor(() => expect(appels).toEqual(["retablir"]));
    expect(String(confirmation.mock.calls[0][0])).toMatch(/crédit rendu au client lui sera repris/);
    expect(await screen.findByRole("status")).toHaveTextContent(/Étude rétablie/);
  });

  it("ne fait rien sans accord", async () => {
    const appels: string[] = [];
    serveur(appels);
    vi.spyOn(window, "confirm").mockReturnValue(false);
    rendre();

    fireEvent.click(await screen.findByRole("button", { name: /Rétablir/ }));

    await new Promise((r) => setTimeout(r, 50));
    expect(appels).toEqual([]);
  });

  it("dit le refus du serveur en clair", async () => {
    const appels: string[] = [];
    serveur(appels, "Le crédit restitué a déjà été utilisé pour une autre étude.");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    rendre();

    fireEvent.click(await screen.findByRole("button", { name: /Rétablir/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/déjà été utilisé/);
  });

  it("un crédit rendu ferme la relance, même sur un dossier repassé en échec", async () => {
    server.use(
      http.get(`${DASH}/jobs/cb59cede/`, () => HttpResponse.json(dossier("failed"))),
    );
    rendre();

    expect(await screen.findByRole("button", { name: /Rétablir/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Relancer la génération/ })).toBeNull();
  });

  it("sans crédit rendu, rien à rétablir : la relance reste", async () => {
    server.use(
      http.get(`${DASH}/jobs/cb59cede/`, () => HttpResponse.json(dossier("failed", false))),
    );
    rendre();

    expect(await screen.findByRole("button", { name: /Relancer la génération/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Rétablir/ })).toBeNull();
  });
});
