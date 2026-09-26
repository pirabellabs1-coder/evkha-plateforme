/** Un chargement raté ne se lit pas comme un vide.
 *
 * La console des incidents affichait « Aucun incident ouvert ✓ » quand l'API
 * répondait 500 ou ne répondait pas : la liste vide par défaut passait pour
 * une réponse. C'est la règle 1 du dépôt — un contrôle qui n'a rien à
 * comparer ne doit pas se déclarer satisfait — et c'est exactement le piège
 * de la mémoire « un 401 se lit comme 0 dossier ». Relevé par l'agent qui a
 * sorti la console de Radix (26/09/2026).
 *
 * Deux verrous : le comportement de la page qui mentait (rendu réel, API
 * simulée par MSW), et la présence du bandeau sur les quatre listes de la
 * console qui n'en avaient pas.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { Incidents } from "../pages/Incidents";
import { server } from "./server";

// L'adresse que `api.ts` construit réellement : `window.location.origin` de
// jsdom (http://localhost:3000), et non l'origine fixe de `server.ts` — une
// requête qui ne correspond à aucun gestionnaire part sur le réseau et échoue
// en « fetch failed », ce qui aurait fait passer le premier cas pour une
// mauvaise raison.
const DASH = `${window.location.origin}/api/dashboard`;

function rendreIncidents() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Incidents />
    </QueryClientProvider>,
  );
}

describe("un chargement raté ne se lit pas comme un vide", () => {
  it("une erreur serveur s'affiche, et ne se lit pas « aucun incident »", async () => {
    server.use(http.get(`${DASH}/incidents/`, () => new HttpResponse("panne", { status: 500 })));
    rendreIncidents();
    expect(await screen.findByText(/Impossible de charger les incidents/)).toBeInTheDocument();
    // C'est bien la réponse 500 qui est affichée, pas une panne de réseau.
    expect(screen.getByText(/500/)).toBeInTheDocument();
    expect(screen.queryByText(/Aucun incident ouvert/)).toBeNull();
  });

  it("contre-épreuve : une liste vide REÇUE dit bien « aucun incident »", async () => {
    server.use(http.get(`${DASH}/incidents/`, () => HttpResponse.json([])));
    rendreIncidents();
    expect(await screen.findByText(/Aucun incident ouvert/)).toBeInTheDocument();
    expect(screen.queryByText(/Impossible de charger/)).toBeNull();
  });

  // Le cas de chaque redéploiement : une première réponse est arrivée, puis
  // le rafraîchissement échoue. Les données restent à l'écran ; le bandeau
  // doit dire « mise à jour impossible », et « aucun incident » ne doit pas
  // s'afficher sous un échec (revue du 26/09/2026).
  it("un rafraîchissement raté dit que les données sont dépassées, et se tait sur « aucun incident »", async () => {
    server.use(http.get(`${DASH}/incidents/`, () => HttpResponse.json([])));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <Incidents />
      </QueryClientProvider>,
    );
    expect(await screen.findByText(/Aucun incident ouvert/)).toBeInTheDocument();

    server.use(http.get(`${DASH}/incidents/`, () => new HttpResponse("panne", { status: 500 })));
    await act(async () => {
      await client.refetchQueries({ queryKey: ["incidents"] });
    });
    expect(await screen.findByText(/Mise à jour impossible/)).toBeInTheDocument();
    expect(screen.getByText(/dernier chargement réussi/)).toBeInTheDocument();
    expect(screen.queryByText(/Aucun incident ouvert/)).toBeNull();
    expect(screen.queryByText(/rien n'a été reçu/)).toBeNull();
  });

  // Les listes de la console qui se taisaient sur une erreur de chargement,
  // et qui doivent distinguer « rien reçu » de « mise à jour ratée ».
  for (const page of ["Jobs", "Incidents", "Orders", "Clients"]) {
    it(`${page} affiche l'échec de son chargement`, () => {
      const source = readFileSync(join(process.cwd(), "src", "pages", `${page}.tsx`), "utf-8");
      expect(source).toMatch(/isError\s*&&\s*\(?\s*<ErreurDeChargement[^>]*perimees=\{isRefetchError\}/);
    });
  }

  // Les fiches remplaçaient TOUTE erreur par « introuvable » : un 502 pendant
  // un déploiement masquait Annuler et Relancer derrière « Job introuvable. ».
  for (const page of ["JobDetail", "ClientDetail"]) {
    it(`${page} ne confond pas une erreur avec « introuvable »`, () => {
      const source = readFileSync(join(process.cwd(), "src", "pages", `${page}.tsx`), "utf-8");
      expect(source).not.toMatch(/error\s*\|\|\s*!data/);
      expect(source).toMatch(/<ErreurDeChargement[^>]*erreur=\{error\}/);
      expect(source).toMatch(/isRefetchError\s*&&/);
    });
  }
});
