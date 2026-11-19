/** L'administration ne lit pas « zéro » sur un chargement raté.
 *
 * Audit du 19/11/2026. Les six écrans de `src/pages/` disent l'échec de leur
 * chargement depuis le 26/09 (`un-chargement-rate-ne-se-lit-pas-comme-un-vide`).
 * Ceux de `src/admin/pages/` — la supervision — n'avaient pas suivi : un 500
 * ou une coupure s'y affichait « 0 € » de revenu récurrent, « 0 organisation »,
 * « Rien en attente », « Aucune transaction », « 0 destinataire ». C'est la
 * règle 1 du dépôt, sur les écrans qui servent justement à voir que quelque
 * chose ne va pas.
 *
 * Et `admin/api.ts` taisait ce que le serveur disait : `post` ne lisait que
 * `error`, alors que les annonces et la boutique rendent `{"erreur": …}`
 * (`dashboard/annonces.py`, `dashboard/boutique.py`) — d'où « Erreur 409 » nu.
 *
 * Trois verrous : le client d'API, le comportement de trois écrans (rendu
 * réel, API simulée par MSW), et la présence du bandeau sur CHAQUE écran de
 * supervision qui interroge le serveur.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique. Les gestionnaires MSW visent
 * `window.location.origin` (jsdom : http://localhost:3000).
 */
import React from "react";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { adminApi } from "../admin/api";
import { server } from "./server";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children }: { children: React.ReactNode }) => <a href="#">{children}</a>,
}));

// Importés APRÈS le simulacre du routeur.
const { TableauDeBordAdmin } = await import("../admin/pages/TableauDeBord");
const { OrganisationsAdmin } = await import("../admin/pages/Organisations");
const { DemandesAdmin } = await import("../admin/pages/Demandes");

const DASH = `${window.location.origin}/api/dashboard`;

function rendre(ecran: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ecran}</QueryClientProvider>);
}

/** Toute la supervision en panne : chaque lecture rend 500. */
function supervisionEnPanne() {
  server.use(
    http.get(`${DASH}/supervision/*`, () => new HttpResponse("panne", { status: 500 })),
  );
}

/** La valeur d'un chiffre clé, ou `null` s'il n'est pas affiché. */
function chiffre(libelle: string): string | null {
  const carte = screen.queryByText(libelle)?.closest(".chiffre");
  return carte?.querySelector(".chiffre-valeur")?.textContent ?? null;
}

/** La synthèse d'une plateforme qui n'a encore rien vendu : de VRAIS zéros. */
const SYNTHESE_A_ZERO = {
  periode: { debut: "2025-11-19", fin: "2026-11-19", jours: 365 },
  organisations: { total: 0, actives: 0, suspendues: 0 },
  revenu: {
    recurrent_mensuel_cents: 0,
    encaisse_periode_cents: 0,
    encaisse_total_cents: 0,
    devise: "EUR",
    nature: "contractuel",
    avertissement: "",
  },
  documents: { produits: 0, en_echec: 0, total: 0, taux_echec: 0 },
  credits: { consommes: 0, restitues: 0, solde_total_en_circulation: 0 },
  cout_production: { total_cents: 0, moyen_par_document_cents: 0 },
  incidents: { ouverts: 0, graves: 0 },
  clients: { total: 0 },
};

describe("l'administration ne lit pas zéro sur un échec", () => {
  // ── 1. Le client d'API ────────────────────────────────────────────────────

  it("un refus des annonces arrive avec la phrase du serveur (clé « erreur »)", async () => {
    server.use(
      http.post(`${DASH}/annonces/a-1/envoyer/`, () =>
        HttpResponse.json(
          { erreur: "Cette annonce a déjà été envoyée.", code: "deja_envoyee" },
          { status: 409 },
        ),
      ),
    );

    await expect(adminApi.envoyerUneAnnonce("a-1")).rejects.toThrow(
      "Cette annonce a déjà été envoyée.",
    );
  });

  it("contre-épreuve : la clé « error » de la supervision est toujours lue", async () => {
    server.use(
      http.post(`${DASH}/supervision/demandes/d-1/traiter/`, () =>
        HttpResponse.json({ error: "Demande déjà traitée." }, { status: 409 }),
      ),
    );

    await expect(
      adminApi.traiterDemande("d-1", { decision: "accorder" }),
    ).rejects.toThrow("Demande déjà traitée.");
  });

  it("contre-épreuve : sans phrase du serveur, le repli garde le code", async () => {
    server.use(
      http.post(`${DASH}/annonces/a-1/envoyer/`, () =>
        new HttpResponse("<html>Bad Gateway</html>", { status: 502 }),
      ),
    );

    await expect(adminApi.envoyerUneAnnonce("a-1")).rejects.toThrow("Erreur 502");
  });

  it("une lecture refusée dit le chemin, le code, et ce que le serveur a dit", async () => {
    server.use(
      http.get(`${DASH}/annonces/`, () =>
        HttpResponse.json({ erreur: "Annonces indisponibles." }, { status: 503 }),
      ),
    );

    const refus = await adminApi.annonces().catch((cause: unknown) => cause);
    expect(String((refus as Error).message)).toMatch(/\/annonces\/ → 503/);
    expect(String((refus as Error).message)).toMatch(/Annonces indisponibles\./);
  });

  // ── 2. Les écrans ─────────────────────────────────────────────────────────

  it("tableau de bord : une synthèse en panne ne s'affiche pas « 0 € » ni « 0 % »", async () => {
    supervisionEnPanne();
    rendre(<TableauDeBordAdmin />);

    expect((await screen.findAllByText(/Impossible de charger/)).length).toBeGreaterThan(0);
    // C'est bien la réponse 500 qui est affichée, pas une panne de réseau.
    expect(screen.getAllByText(/500/).length).toBeGreaterThan(0);
    for (const libelle of [
      "Revenu récurrent",
      "Revenu encaissé",
      "Documents produits",
      "Crédits consommés",
      "Taux d'échec",
      "Incidents ouverts",
    ]) {
      expect(chiffre(libelle), libelle).toBeNull();
    }
    expect(screen.queryByText(/Aucune consommation/)).toBeNull();
  });

  it("contre-épreuve — tableau de bord : de vrais zéros REÇUS s'affichent", async () => {
    server.use(
      http.get(`${DASH}/supervision/synthese/`, () => HttpResponse.json(SYNTHESE_A_ZERO)),
      http.get(`${DASH}/supervision/evolution/`, () =>
        HttpResponse.json({ mois: [], series: [] }),
      ),
      http.get(`${DASH}/supervision/organisations/`, () =>
        HttpResponse.json({ organisations: [] }),
      ),
    );
    rendre(<TableauDeBordAdmin />);

    expect(await screen.findByText(/Aucune consommation/)).toBeInTheDocument();
    expect(chiffre("Documents produits")).toBe("0");
    expect(chiffre("Taux d'échec")).toBe("0 %");
    expect(screen.queryByText(/Impossible de charger/)).toBeNull();
  });

  it("organisations : une panne ne se lit ni « 0 organisation » ni « Aucune organisation »", async () => {
    supervisionEnPanne();
    rendre(<OrganisationsAdmin />);

    expect(await screen.findByText(/Impossible de charger les organisations/)).toBeInTheDocument();
    expect(screen.getByText(/500/)).toBeInTheDocument();
    expect(screen.queryByText(/Aucune organisation/)).toBeNull();
    expect(screen.queryByText(/^0 organisation/)).toBeNull();
    expect(chiffre("Revenu récurrent")).toBeNull();
    expect(chiffre("Crédits en circulation")).toBeNull();
  });

  it("contre-épreuve — organisations : une liste vide REÇUE dit « Aucune organisation »", async () => {
    server.use(
      http.get(`${DASH}/supervision/organisations/`, () =>
        HttpResponse.json({ organisations: [] }),
      ),
    );
    rendre(<OrganisationsAdmin />);

    expect(await screen.findByText("Aucune organisation")).toBeInTheDocument();
    expect(chiffre("Organisations")).toBe("0");
    expect(screen.queryByText(/Impossible de charger/)).toBeNull();
  });

  it("demandes : une panne ne se lit pas « Rien en attente »", async () => {
    supervisionEnPanne();
    rendre(<DemandesAdmin />);

    expect(await screen.findByText(/Impossible de charger les demandes/)).toBeInTheDocument();
    expect(screen.queryByText(/Rien en attente/)).toBeNull();
  });

  it("contre-épreuve — demandes : une liste vide REÇUE dit « Rien en attente »", async () => {
    server.use(
      http.get(`${DASH}/supervision/demandes/`, () =>
        HttpResponse.json({ demandes: [], ouvertes: 0 }),
      ),
    );
    rendre(<DemandesAdmin />);

    expect(await screen.findByText("Rien en attente")).toBeInTheDocument();
    expect(screen.queryByText(/Impossible de charger/)).toBeNull();
  });

  // ── 3. La classe : chaque écran de supervision ────────────────────────────

  const PAGES = join(process.cwd(), "src", "admin", "pages");
  const ecrans = readdirSync(PAGES).filter((f) => f.endsWith(".tsx"));

  /** Écrans tenus HORS du verrou, chacun avec sa raison. Une exemption se
   *  nomme : une liste fermée d'écrans vérifiés en laisserait passer un
   *  onzième sans que rien ne le dise (règle 4). */
  const EXEMPTES: Record<string, string> = {
    // Écran en cours de réécriture par un autre lot le jour de l'audit
    // (19/11/2026). À faire entrer ici dès qu'il est stabilisé.
    "Prospection.tsx": "refonte en cours le 19/11/2026",
  };

  it("trouve les écrans de supervision (un contrôle sans rien à comparer échoue)", () => {
    expect(ecrans.length).toBeGreaterThanOrEqual(10);
    for (const exempte of Object.keys(EXEMPTES)) {
      expect(existsSync(join(PAGES, exempte)), `exemption sans objet : ${exempte}`).toBe(true);
    }
  });

  for (const ecran of ecrans) {
    if (ecran in EXEMPTES) continue;
    const source = readFileSync(join(PAGES, ecran), "utf-8");
    if (!/\buseQuery\(/.test(source)) continue;
    it(`${ecran} affiche l'échec de son chargement, et distingue une mise à jour ratée`, () => {
      // Le même bandeau que `src/pages/` : posé sur `isError`, et qui sait
      // dire « dépassé » plutôt que « rien reçu » quand des données restent.
      expect(source).toMatch(
        /isError\s*&&\s*\(?\s*<ErreurDeChargement[^>]*perimees=\{[\w.]*isRefetchError\}/,
      );
    });
  }
});
