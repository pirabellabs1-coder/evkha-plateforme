/** « Tout marquer résolu » annonce le vrai nombre et ne solde qu'après accord.
 *
 * La liste ne montre que les 50 derniers incidents : le bouton demande
 * d'abord une SIMULATION au serveur pour annoncer le vrai compte (477 le
 * 26/09/2026) et les verrous de livraison conservés, puis ne solde que si
 * l'on confirme. Un refus ne doit rien écrire.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique. Les gestionnaires MSW
 * visent `window.location.origin` (jsdom : http://localhost:3000).
 */
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Incidents } from "../pages/Incidents";
import { server } from "./server";

const DASH = `${window.location.origin}/api/dashboard`;

const OUVERT = {
  id: "inc-1",
  title: "Gate qualité (recontrôle) : toujours bloqué",
  severity: "high",
  status: "open",
  created_at: "2026-09-26T10:00:00Z",
  resolved_at: null,
  job_id: null,
  order_id: null,
  details: {},
};

function rendre() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Incidents />
    </QueryClientProvider>,
  );
}

/** Serveur simulé : note les appels réels (hors simulation). */
function serveurDeSolde(appelsReels: unknown[]) {
  server.use(
    http.get(`${DASH}/incidents/`, () => HttpResponse.json([OUVERT])),
    http.post(`${DASH}/incidents/resoudre-tout/`, async ({ request }) => {
      const corps = (await request.json()) as { simulation?: boolean };
      if (!corps.simulation) appelsReels.push(corps);
      return HttpResponse.json({
        simulation: Boolean(corps.simulation),
        a_resoudre: 477,
        resolus: corps.simulation ? 0 : 477,
        par_gravite: { high: 195, medium: 282 },
        verrous_conserves: [],
        identifiants: [],
      });
    }),
  );
}

describe("les incidents se soldent sur confirmation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("annonce le vrai nombre, puis solde après accord", async () => {
    const appelsReels: unknown[] = [];
    serveurDeSolde(appelsReels);
    const confirmation = vi.spyOn(window, "confirm").mockReturnValue(true);
    rendre();

    fireEvent.click(await screen.findByRole("button", { name: /Tout marquer résolu/ }));

    expect(await screen.findByText(/477 incident\(s\) marqué\(s\) résolu\(s\)/)).toBeInTheDocument();
    expect(confirmation).toHaveBeenCalledTimes(1);
    expect(String(confirmation.mock.calls[0][0])).toMatch(/477 incidents/);
    expect(appelsReels).toHaveLength(1);
  });

  it("contre-épreuve : un refus ne solde rien", async () => {
    const appelsReels: unknown[] = [];
    serveurDeSolde(appelsReels);
    vi.spyOn(window, "confirm").mockReturnValue(false);
    rendre();

    fireEvent.click(await screen.findByRole("button", { name: /Tout marquer résolu/ }));
    // Laisser la simulation revenir et la mutation se terminer.
    await screen.findByRole("button", { name: /Tout marquer résolu/ });
    await new Promise((r) => setTimeout(r, 50));

    expect(appelsReels).toHaveLength(0);
    expect(screen.queryByText(/marqué\(s\) résolu\(s\)/)).toBeNull();
  });

  it("sans incident à solder, le bouton n'apparaît pas", async () => {
    server.use(http.get(`${DASH}/incidents/`, () => HttpResponse.json([])));
    rendre();
    expect(await screen.findByText(/Aucun incident ouvert/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Tout marquer résolu/ })).toBeNull();
  });
});
