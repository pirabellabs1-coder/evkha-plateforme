/** L'arrêt d'un abonnement ne se promet pas « en un clic ».
 *
 * Audit du 19/11/2026. `arreter_l_abonnement` (`backend/organisations/
 * vues_espace.py`) refuse TOUJOURS l'arrêt en libre-service : il se fait sur
 * demande auprès d'EVKHA, avec un engagement minimum de `MOIS_ENGAGEMENT`
 * mois — décision de la cliente du 07/08/2026. La page Abonnement le disait.
 * Trois autres textes de l'espace promettaient l'inverse, dont un juste
 * au-dessus du bouton qui prélève :
 *
 * - « s'arrête depuis votre espace en un clic, sans préavis ni justification » ;
 * - « vous pouvez l'arrêter quand vous voulez depuis la page Abonnement » ;
 * - « Arrêt possible à tout moment », sur chaque carte de formule.
 *
 * Deux défauts voisins des mêmes écrans sont verrouillés ici :
 *
 * - quand la confirmation du paiement tarde, la page réaffichait le formulaire
 *   de paiement, actif, sous la phrase « rien ne sera prélevé deux fois » ;
 * - sans formule active, la page Abonnement annonçait « 0 € le crédit, au
 *   tarif de votre formule ».
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { jeton } from "../espace/api";
import { ARRET_EN_UNE_LIGNE, ARRET_EN_UNE_PHRASE, ENGAGEMENT_MINIMUM } from "../espace/engagement";
import { server } from "./server";

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => () => undefined,
  Link: ({ children }: { children: React.ReactNode }) => <a href="#">{children}</a>,
}));

// Importés APRÈS le simulacre du routeur.
const { Abonnement } = await import("../espace/pages/Abonnement");
const { Souscription } = await import("../espace/pages/Souscription");

const ESPACE = `${window.location.origin}/api/espace`;

/** Ce que l'espace n'a plus le droit de promettre sur l'arrêt. */
const PROMESSES_FAUSSES =
  /en un clic|sans préavis|sans justification|quand vous voulez depuis|à tout moment/i;

const ABONNEMENT = {
  formule: "Pro",
  code: "pro",
  credits_par_echeance: 5,
  prix_mensuel_cents: 18900,
  devise: "EUR",
  debut_le: "2026-10-01T00:00:00Z",
  derniere_periode_dotee: "2026-11",
  report_credits: "aucun",
  plafond_report: 0,
  renouvellement_actif: true,
  fin_de_periode_le: "2026-12-01T00:00:00Z",
  pilote_par_carte: true,
  prix_credit_supplementaire_cents: 5900,
};

function moi(abonnement: typeof ABONNEMENT | null) {
  return {
    acces_ouvert: abonnement !== null,
    assistance: false,
    utilisateur: {
      email: "eva@exemple.fr",
      prenom: "Eva",
      nom: "",
      role: "proprietaire",
      droits: ["commander", "consulter_livrables", "gerer_abonnement"],
    },
    organisation: {
      id: "org-1",
      raison_sociale: "Cabinet Eva",
      statut: "active",
      marque_blanche: true,
      validation_socle_par_client: false,
      type_de_compte: "abonne",
    },
    credits: { solde: 3, seuil_alerte: 1, alerte: false },
    abonnement,
    souscription_en_attente: null,
  };
}

const FORMULES = {
  code_actuel: "",
  formules: [
    {
      code: "pro",
      libelle: "Pro",
      credits_par_echeance: 5,
      prix_mensuel_cents: 18900,
      devise: "EUR",
      cout_par_livrable_cents: 3780,
      report_credits: "aucun",
      regenerations_offertes: 1,
      actuelle: false,
    },
  ],
};

function servir(abonnement: typeof ABONNEMENT | null) {
  server.use(
    http.get(`${ESPACE}/moi/`, () => HttpResponse.json(moi(abonnement))),
    http.get(`${ESPACE}/formules/`, () => HttpResponse.json(FORMULES)),
    http.get(`${ESPACE}/demandes/`, () => HttpResponse.json({ demandes: [] })),
  );
}

function rendre(ecran: React.ReactElement, adresse: string) {
  window.history.pushState({}, "", adresse);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ecran}</QueryClientProvider>);
}

describe("l'arrêt d'un abonnement ne se promet pas en un clic", () => {
  beforeEach(() => {
    localStorage.clear();
    jeton.ecrire("jeton-de-session");
  });

  afterEach(() => {
    vi.useRealTimers();
    window.history.pushState({}, "", "/");
  });

  // ── Les mots de l'arrêt ───────────────────────────────────────────────────

  it("les mots partagés disent l'engagement et l'arrêt sur demande, sans promesse", () => {
    for (const texte of [ARRET_EN_UNE_LIGNE, ARRET_EN_UNE_PHRASE]) {
      expect(texte).toContain(ENGAGEMENT_MINIMUM);
      expect(texte).toMatch(/sur (simple )?demande/);
      expect(texte).not.toMatch(PROMESSES_FAUSSES);
    }
  });

  it("la page de paiement dit les conditions d'arrêt AVANT la carte bancaire", async () => {
    servir(null);
    const { container } = rendre(<Souscription />, "/espace/souscription?formule=pro");

    expect(await screen.findByRole("button", { name: /Régler 189/ })).toBeInTheDocument();
    expect(container.textContent).toContain(ARRET_EN_UNE_PHRASE);
    expect(container.textContent).not.toMatch(PROMESSES_FAUSSES);
  });

  it("la confirmation d'abonnement ne promet pas l'arrêt « quand vous voulez »", async () => {
    servir(ABONNEMENT);
    const { container } = rendre(<Souscription />, "/espace/souscription");

    expect(await screen.findByText(/Votre abonnement est actif/)).toBeInTheDocument();
    expect(container.textContent).toContain(`engagement minimum de ${ENGAGEMENT_MINIMUM}`);
    expect(container.textContent).toMatch(/sur demande/);
    expect(container.textContent).not.toMatch(PROMESSES_FAUSSES);
  });

  it("une carte de formule dit l'engagement, pas « Arrêt possible à tout moment »", async () => {
    servir(null);
    const { container } = rendre(<Abonnement />, "/espace/abonnement");

    expect(await screen.findByText(ARRET_EN_UNE_LIGNE)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(PROMESSES_FAUSSES);
  });

  // La classe, pas les trois phrases trouvées : aucun fichier de l'espace ne
  // promet un arrêt libre. Les commentaires sont retirés — ils CITENT les
  // promesses pour raconter leur retrait.
  it("aucun écran de l'espace ne promet un arrêt libre de l'abonnement", () => {
    const racine = join(process.cwd(), "src", "espace");
    const fichiers = (dossier: string): string[] =>
      readdirSync(dossier).flatMap((entree) => {
        const chemin = join(dossier, entree);
        if (statSync(chemin).isDirectory()) return fichiers(chemin);
        return /\.tsx?$/.test(chemin) ? [chemin] : [];
      });
    const sources = fichiers(racine);
    expect(sources.length).toBeGreaterThan(10);

    const promesse =
      /(arr[êe]t|arr[êe]ter|s'arr[êe]te|r[ée]sili\w*)[^.]{0,80}(en un clic|sans préavis|à tout moment|quand vous voulez)/i;
    for (const chemin of sources) {
      const visible = readFileSync(chemin, "utf-8")
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/\/\/.*$/gm, "");
      expect(visible.match(promesse)?.[0], chemin).toBeUndefined();
    }
    // Contre-épreuve : le détecteur voit bien les trois phrases d'avant.
    for (const avant of [
      "L'abonnement se reconduit chaque mois et s'arrête depuis votre espace en un clic, sans préavis ni justification.",
      "vous pouvez l'arrêter quand vous voulez depuis la page Abonnement.",
      "<li>Arrêt possible à tout moment</li>",
    ]) {
      expect(promesse.test(avant), avant).toBe(true);
    }
    // … et laisse passer ce qui n'est pas une promesse d'arrêt.
    expect(promesse.test("Téléchargeables à tout moment, autant de fois que vous le souhaitez.")).toBe(false);
    expect(promesse.test(ARRET_EN_UNE_PHRASE)).toBe(false);
  });

  // ── La confirmation qui tarde ─────────────────────────────────────────────

  it("quand la confirmation tarde, le formulaire de paiement ne revient pas sous « rien ne sera prélevé deux fois »", async () => {
    // Les vingt tentatives sont espacées d'une seconde : on avance l'horloge.
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    servir(null);
    rendre(<Souscription />, "/espace/souscription?paiement=ok");

    for (let seconde = 0; seconde < 24; seconde += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
      });
    }

    expect(screen.getByText(/Confirmation en retard/)).toBeInTheDocument();
    expect(screen.getByText(/rien ne sera prélevé deux\s+fois/)).toBeInTheDocument();
    // Aucun moyen de payer une seconde fois depuis cet écran.
    expect(screen.queryByRole("button", { name: /Régler|Choisissez une formule/ })).toBeNull();
    expect(screen.queryByRole("radio")).toBeNull();
    // Ce qui reste : revérifier.
    expect(screen.getByRole("button", { name: /Vérifier à nouveau/ })).toBeInTheDocument();
  });

  it("contre-épreuve : un paiement abandonné retrouve, lui, son formulaire", async () => {
    servir(null);
    rendre(<Souscription />, "/espace/souscription?paiement=abandon&formule=pro");

    expect(await screen.findByText(/Paiement interrompu/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Régler 189/ })).toBeInTheDocument();
  });

  // ── Les crédits additionnels ──────────────────────────────────────────────

  it("sans formule active, aucune carte n'annonce un crédit à « 0 € »", async () => {
    servir(null);
    const { container } = rendre(<Abonnement />, "/espace/abonnement");

    await screen.findByText(ARRET_EN_UNE_LIGNE);
    expect(screen.queryByText(/Crédits additionnels/)).toBeNull();
    expect(container.textContent).not.toMatch(/0\s€ le crédit/);
  });

  it("contre-épreuve : avec une formule, la carte annonce le tarif du crédit", async () => {
    servir(ABONNEMENT);
    const { container } = rendre(<Abonnement />, "/espace/abonnement");

    expect(await screen.findByText(/Crédits additionnels/)).toBeInTheDocument();
    expect(container.textContent).toMatch(/59\s€ le crédit/);
  });
});
