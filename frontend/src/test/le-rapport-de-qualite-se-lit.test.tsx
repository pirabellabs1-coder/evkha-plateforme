/** Le rapport interne de qualité se lit : chapitres, motifs, études.
 *
 * 29/09/2026 : ce que la production corrige en route ne s'affiche jamais au
 * client ; l'administrateur le lit ici pour corriger les causes à la source.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`. Les
 * gestionnaires MSW visent `window.location.origin` (jsdom : localhost:3000).
 */
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { QualiteAdmin } from "../admin/pages/Qualite";
import { server } from "./server";

const DASH = `${window.location.origin}/api/dashboard`;

function rendre() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <QualiteAdmin />
    </QueryClientProvider>,
  );
}

describe("le rapport de qualité se lit", () => {
  it("montre les chapitres qui reprennent le plus", async () => {
    server.use(
      http.get(`${DASH}/qualite/`, () =>
        HttpResponse.json({
          dossiers: [{
            id: "cb59cede-0000", type: "business_plan", statut: "done", qa_status: "passed",
            cree_le: "2026-09-29T15:00:00Z", memoire: true, chapitres_controles: 21,
            motifs: 3, replis: 1, reperes: 66, constats_pdf: 1, cout_eur: "5.98",
          }],
          chapitres: [{
            type: "business_plan", chapitre: 16, titre: "Prévisionnel financier",
            passages: 1, motifs: 3, replis: 1,
          }],
          familles_de_motifs: [{ famille: "Chiffre écrit en clair", occurrences: 2 }],
          constats_pdf: [{ controle: "entete_trop_long", occurrences: 1 }],
        }),
      ),
    );
    rendre();
    expect(await screen.findByText("16 — Prévisionnel financier")).toBeInTheDocument();
    expect(screen.getByText("Chiffre écrit en clair")).toBeInTheDocument();
    expect(screen.getByText("PDF — entete_trop_long")).toBeInTheDocument();
  });

  it("dit clairement quand il est vide", async () => {
    server.use(
      http.get(`${DASH}/qualite/`, () =>
        HttpResponse.json({ dossiers: [], chapitres: [], familles_de_motifs: [], constats_pdf: [] }),
      ),
    );
    rendre();
    expect(await screen.findByText("Aucune étude contrôlée pour l'instant")).toBeInTheDocument();
  });
});
