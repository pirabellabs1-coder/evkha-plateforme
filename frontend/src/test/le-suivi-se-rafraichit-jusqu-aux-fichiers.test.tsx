/** Le suivi se rafraîchit jusqu'à ce que les fichiers existent.
 *
 * Audit du 19/11/2026. Un dossier passe `done` AVANT sa relecture finale et
 * son assemblage : `suivi.en_dict` rend alors `en_production: false` et
 * `fichiers_etat.etat: "mise_en_forme"` (`organisations.suivi.etat_des_fichiers`)
 * pendant vingt à soixante minutes. L'écran ne sondait que sur
 * `en_production` : il s'arrêtait donc au moment précis où il annonçait « les
 * fichiers apparaîtront ici d'ici quelques minutes », et ils n'apparaissaient
 * jamais sans recharger la page.
 *
 * Seul `setInterval` est simulé : c'est lui que TanStack Query emploie pour
 * `refetchInterval` (`timeoutManager`). Les promesses, `fetch` et les
 * `setTimeout` restent réels, MSW répond normalement. Le test avance d'une
 * MINUTE, quelle que soit la cadence retenue par l'écran.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { attendUneSuite } from "../espace/suivi";
import { server } from "./server";

vi.mock("@tanstack/react-router", () => ({
  useParams: () => ({ jobId: "job-1" }),
  Link: ({ children }: { children: React.ReactNode }) => <a href="#">{children}</a>,
}));

// Importé APRÈS le simulacre du routeur : la page lit `useParams`.
const { SuiviLivrable } = await import("../espace/pages/SuiviLivrable");

const ADRESSE = `${window.location.origin}/api/espace/livrables/job-1/`;

/** La forme que rend `organisations.suivi.en_dict` pour une étude rédigée
 *  dont Word et PDF ne sont pas encore assemblés. */
function suivi(surcharge: Record<string, unknown> = {}) {
  return {
    id: "job-1",
    type: "business_plan",
    statut: "done",
    message: "Votre étude est rédigée. Sa mise en forme est en cours.",
    progression: 95,
    en_production: false,
    duree_estimee_minutes: null,
    fin_estimee: null,
    cree_le: "2026-11-18T09:00:00+00:00",
    demarre_le: "2026-11-18T09:00:10+00:00",
    termine_le: "2026-11-18T09:40:00+00:00",
    etapes: [
      { cle: "redaction", libelle: "Rédaction des chapitres", etat: "fait", detail: "22 chapitres sur 22" },
      { cle: "mise_en_forme", libelle: "Mise en forme", etat: "en_cours", detail: "" },
    ],
    fichiers: [],
    fichiers_etat: { etat: "mise_en_forme", supprimes_le: null },
    chapitres: [],
    ...surcharge,
  };
}

const PRETS = {
  progression: 100,
  fichiers: [
    { kind: "docx", statut: "ready", url: "https://api.exemple/media/job-1.docx?s=a" },
    { kind: "pdf", statut: "ready", url: "https://api.exemple/media/job-1.pdf?s=b" },
  ],
  fichiers_etat: { etat: "disponibles", supprimes_le: null },
};

function rendre() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SuiviLivrable />
    </QueryClientProvider>,
  );
}

/** Une minute de sondage, puis le temps réel qu'une réponse arrive. */
async function laisserPasserUneMinute() {
  await act(async () => {
    vi.advanceTimersByTime(60_000);
    await new Promise((fin) => setTimeout(fin, 120));
  });
}

describe("le suivi se rafraîchit jusqu'aux fichiers", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("continue pendant la mise en forme, puis s'arrête quand les fichiers existent", async () => {
    let appels = 0;
    server.use(
      http.get(ADRESSE, () => {
        appels += 1;
        return HttpResponse.json(appels === 1 ? suivi() : suivi(PRETS));
      }),
    );
    rendre();

    expect(await screen.findByText(/Mise en forme en cours/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Télécharger le PDF/ })).toBeNull();
    expect(appels).toBe(1);

    await laisserPasserUneMinute();
    // Sans recharger la page : c'est le sondage qui apporte les fichiers.
    expect(await screen.findByRole("link", { name: /Télécharger le PDF/ })).toBeInTheDocument();
    expect(screen.queryByText(/Mise en forme en cours/)).toBeNull();
    expect(appels).toBe(2);

    // Les fichiers sont là : interroger encore le serveur serait du bruit.
    await laisserPasserUneMinute();
    expect(appels).toBe(2);
  });

  // Les états TERMINAUX, lus dans `suivi.ETATS_DES_FICHIERS` : le correctif ne
  // doit pas faire tourner l'écran sur une étude qui n'attend plus rien.
  it.each([
    ["disponibles", PRETS],
    ["supprimes", { fichiers_etat: { etat: "supprimes", supprimes_le: "2026-08-25T16:54:00+00:00" } }],
    ["aucun", { statut: "cancelled", fichiers_etat: { etat: "aucun", supprimes_le: null } }],
  ])("contre-épreuve : des fichiers « %s » n'entretiennent aucun sondage", async (_etat, surcharge) => {
    let appels = 0;
    server.use(
      http.get(ADRESSE, () => {
        appels += 1;
        return HttpResponse.json(suivi(surcharge));
      }),
    );
    rendre();

    await screen.findByText("Où en est votre étude");
    await laisserPasserUneMinute();
    expect(appels).toBe(1);
  });

  it("contre-épreuve : une étude en production se sonde comme avant", async () => {
    let appels = 0;
    server.use(
      http.get(ADRESSE, () => {
        appels += 1;
        return HttpResponse.json(
          suivi({
            statut: "running",
            en_production: true,
            progression: 40,
            fichiers_etat: { etat: "en_preparation", supprimes_le: null },
          }),
        );
      }),
    );
    rendre();

    await screen.findByText("Où en est votre étude");
    await laisserPasserUneMinute();
    expect(appels).toBeGreaterThan(1);
  });

  // La règle, hors de l'écran : c'est elle que la page appelle.
  it("la règle : en production, ou des fichiers encore attendus", () => {
    const attendus = (etat: string, en_production = false) =>
      attendUneSuite({
        en_production,
        fichiers_etat: { etat, supprimes_le: null },
      } as Parameters<typeof attendUneSuite>[0]);

    expect(attendus("mise_en_forme")).toBe(true);
    expect(attendus("en_preparation")).toBe(true);
    expect(attendus("disponibles")).toBe(false);
    expect(attendus("supprimes")).toBe(false);
    expect(attendus("aucun")).toBe(false);
    // `en_production` suffit : un serveur d'avant `fichiers_etat` se sonde
    // comme il l'a toujours été.
    expect(attendUneSuite({ en_production: true })).toBe(true);
    expect(attendUneSuite({ en_production: false })).toBe(false);
  });
});
