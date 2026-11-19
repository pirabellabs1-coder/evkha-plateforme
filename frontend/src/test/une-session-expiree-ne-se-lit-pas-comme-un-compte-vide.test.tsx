/** Dans l'espace client, une session expirée ou un chargement raté ne se lit
 *  pas comme un compte vide.
 *
 * Audit du 19/11/2026. `espace/api.ts` effaçait le jeton sur un 401 et
 * s'arrêtait là : la personne restait sur sa page, et chaque écran lisait
 * `data ?? []` ou `?? 0` sans regarder `isError`. Une session expirée — ou une
 * panne de dix secondes pendant un déploiement — s'affichait donc « 0 crédit »,
 * « Aucun abonnement actif », « Aucun document pour le moment » : un compte
 * vide, à quelqu'un qui a payé. C'est la règle 1 du dépôt (un contrôle qui n'a
 * rien à comparer ne se déclare pas satisfait) et la mémoire « un 401 se lit
 * comme 0 dossier », côté cliente cette fois.
 *
 * Trois verrous :
 *
 * 1. `appel` : un 401 hors connexion efface le jeton ET renvoie à la connexion ;
 * 2. le comportement de quatre écrans sur 401, sur 500, et sur 404 pour la
 *    fiche de suivi (qui disait « Étude introuvable. » pour toute erreur) ;
 * 3. la présence du bandeau sur CHAQUE écran de l'espace qui lit une liste ou
 *    un compteur — la classe, pas les quatre exemples (règle 4).
 *
 * Les charges 401 et 404 sont celles de `vues_espace._refus`
 * (`{"error": …, "code": …}`), recopiées du serveur.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { espaceApi, jeton } from "../espace/api";
import { server } from "./server";

vi.mock("@tanstack/react-router", () => ({
  useParams: () => ({ jobId: "job-1" }),
  useNavigate: () => () => undefined,
  Link: ({ children }: { children: React.ReactNode }) => <a href="#">{children}</a>,
}));

// Importés APRÈS le simulacre du routeur.
const { TableauDeBord } = await import("../espace/pages/TableauDeBord");
const { Livrables } = await import("../espace/pages/Livrables");
const { Credits } = await import("../espace/pages/Credits");
const { SuiviLivrable } = await import("../espace/pages/SuiviLivrable");

// Lue AVANT tout remplacement de `window.location` : c'est l'origine que MSW
// voit, les appels de l'espace étant relatifs (`/api/espace/…`).
const ORIGINE = window.location.origin;
const ESPACE = `${ORIGINE}/api/espace`;

/** Les routes que lisent les écrans rendus ici. */
const ROUTES = ["moi", "livrables", "consommation", "credits", "etudes", "livrables/job-1"];

const NON_AUTORISE = { error: "Authentification requise.", code: "unauthorized" };

function partout(reponse: () => Response) {
  server.use(...ROUTES.map((route) => http.get(`${ESPACE}/${route}/`, reponse)));
}

/** Un compte RÉELLEMENT vide, tel que le serveur le rend : la contre-épreuve. */
function compteVide() {
  server.use(
    http.get(`${ESPACE}/moi/`, () =>
      HttpResponse.json({
        acces_ouvert: false,
        assistance: false,
        utilisateur: {
          email: "eva@exemple.fr",
          prenom: "Eva",
          nom: "",
          role: "proprietaire",
          droits: ["commander", "consulter_livrables"],
        },
        organisation: {
          id: "org-1",
          raison_sociale: "Cabinet Eva",
          statut: "active",
          marque_blanche: true,
          validation_socle_par_client: false,
          type_de_compte: "abonne",
        },
        credits: { solde: 0, seuil_alerte: 1, alerte: false },
        abonnement: null,
        souscription_en_attente: null,
      }),
    ),
    http.get(`${ESPACE}/livrables/`, () => HttpResponse.json({ livrables: [] })),
    http.get(`${ESPACE}/credits/`, () => HttpResponse.json({ solde: 0, mouvements: [] })),
    http.get(`${ESPACE}/consommation/`, () =>
      HttpResponse.json({
        mois: [],
        total_recu: 0,
        total_consomme: 0,
        total_expire: 0,
        rythme: {
          mensuel: 0,
          mois_observes: 0,
          solde: 0,
          jours_restants: null,
          epuisement_le: null,
          motif: "aucun_mouvement",
        },
      }),
    ),
    http.get(`${ESPACE}/etudes/`, () => HttpResponse.json({ etudes: [] })),
  );
}

function rendre(ecran: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ecran}</QueryClientProvider>);
}

/** La valeur d'un chiffre clé, ou `null` s'il n'est pas affiché. */
function chiffre(libelle: string): string | null {
  const carte = screen.queryByText(libelle)?.closest(".chiffre");
  return carte?.querySelector(".chiffre-valeur")?.textContent ?? null;
}

/** Ce qu'un compte vide affiche, et qu'un échec ne doit jamais afficher. */
const DISCOURS_DU_VIDE =
  /Aucun abonnement actif|Aucun document|Aucun mouvement|Rien en cours|Commander mon premier document/;

// ── L'adresse du navigateur ─────────────────────────────────────────────────
// jsdom ne navigue pas : on pose une adresse qui ENREGISTRE les redirections.
// `href` reste lisible et absolu — MSW s'en sert pour résoudre les appels
// relatifs.

const adresseDOrigine = Object.getOwnPropertyDescriptor(window, "location");
let redirections: string[] = [];

function poserLAdresse(chemin: string) {
  redirections = [];
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      origin: ORIGINE,
      pathname: chemin,
      search: "",
      get href() {
        return `${ORIGINE}${chemin}`;
      },
      set href(cible: string) {
        redirections.push(cible);
      },
      assign: (cible: string) => {
        redirections.push(cible);
      },
      replace: (cible: string) => {
        redirections.push(cible);
      },
    },
  });
}

describe("une session expirée ne se lit pas comme un compte vide", () => {
  beforeEach(() => {
    localStorage.clear();
    jeton.ecrire("jeton-en-cours");
    poserLAdresse("/espace");
  });

  afterEach(() => {
    if (adresseDOrigine) Object.defineProperty(window, "location", adresseDOrigine);
  });

  // ── 1. Le client d'API ────────────────────────────────────────────────────

  it("un 401 efface le jeton ET renvoie à la connexion", async () => {
    partout(() => HttpResponse.json(NON_AUTORISE, { status: 401 }));

    await expect(espaceApi.moi()).rejects.toMatchObject({ statut: 401 });
    expect(jeton.present()).toBe(false);
    expect(redirections).toEqual(["/espace/connexion"]);
  });

  it("contre-épreuve : un mot de passe faux à la connexion ne redirige ni n'efface", async () => {
    server.use(
      http.post(`${ESPACE}/connexion/`, () =>
        HttpResponse.json(
          { error: "Identifiants invalides.", code: "identifiants_invalides" },
          { status: 401 },
        ),
      ),
    );

    await expect(espaceApi.connexion("eva@exemple.fr", "faux")).rejects.toThrow(
      /Identifiants invalides/,
    );
    expect(jeton.lire()).toBe("jeton-en-cours");
    expect(redirections).toEqual([]);
  });

  it("contre-épreuve : le 401 d'une requête partie avec l'ANCIEN jeton n'éjecte personne", async () => {
    // Changer son mot de passe délivre un jeton neuf pendant qu'une requête
    // est encore en vol avec l'ancien (voir `appel`).
    server.use(
      http.get(`${ESPACE}/moi/`, () => {
        jeton.ecrire("jeton-neuf");
        return HttpResponse.json(NON_AUTORISE, { status: 401 });
      }),
    );

    await expect(espaceApi.moi()).rejects.toMatchObject({ statut: 401 });
    expect(jeton.lire()).toBe("jeton-neuf");
    expect(redirections).toEqual([]);
  });

  it("contre-épreuve : une erreur 500 n'éjecte personne", async () => {
    partout(() => new HttpResponse("panne", { status: 500 }));

    await expect(espaceApi.moi()).rejects.toMatchObject({ statut: 500 });
    expect(jeton.lire()).toBe("jeton-en-cours");
    expect(redirections).toEqual([]);
  });

  // ── 2. Les écrans ─────────────────────────────────────────────────────────

  it("tableau de bord, 401 : renvoi à la connexion, et aucun discours de compte vide", async () => {
    partout(() => HttpResponse.json(NON_AUTORISE, { status: 401 }));
    rendre(<TableauDeBord />);

    await waitFor(() => expect(redirections).toContain("/espace/connexion"));
    expect(jeton.present()).toBe(false);
    await screen.findAllByText(/Impossible de charger/);
    expect(screen.queryByText(DISCOURS_DU_VIDE)).toBeNull();
    expect(chiffre("Crédits disponibles")).not.toBe("0");
  });

  it("tableau de bord, 500 : l'échec est dit, et ne se lit ni « 0 » ni « aucun »", async () => {
    partout(() => new HttpResponse("panne", { status: 500 }));
    rendre(<TableauDeBord />);

    expect((await screen.findAllByText(/Impossible de charger/)).length).toBeGreaterThan(0);
    // C'est bien la réponse 500 qui est affichée, pas une panne de réseau.
    expect(screen.getAllByText(/500/).length).toBeGreaterThan(0);
    expect(screen.queryByText(DISCOURS_DU_VIDE)).toBeNull();
    expect(chiffre("Crédits disponibles")).not.toBe("0");
    expect(chiffre("Documents produits")).not.toBe("0");
    expect(chiffre("En production")).not.toBe("0");
    expect(redirections).toEqual([]);
  });

  it("contre-épreuve — tableau de bord : un compte vide REÇU se dit vide", async () => {
    compteVide();
    rendre(<TableauDeBord />);

    expect(await screen.findByText(/Aucun document pour le moment/)).toBeInTheDocument();
    expect(screen.getByText(/Aucun abonnement actif/)).toBeInTheDocument();
    expect(chiffre("Crédits disponibles")).toBe("0");
    expect(chiffre("Documents produits")).toBe("0");
    expect(screen.queryByText(/Impossible de charger/)).toBeNull();
  });

  it("livrables, 401 : renvoi à la connexion, et pas « Aucun document »", async () => {
    partout(() => HttpResponse.json(NON_AUTORISE, { status: 401 }));
    rendre(<Livrables />);

    await waitFor(() => expect(redirections).toContain("/espace/connexion"));
    expect(await screen.findByText(/Impossible de charger/)).toBeInTheDocument();
    expect(screen.queryByText(DISCOURS_DU_VIDE)).toBeNull();
    expect(screen.queryByText(/^0 document/)).toBeNull();
  });

  it("livrables, 500 : l'échec est dit, et ne se lit pas « Aucun document »", async () => {
    partout(() => new HttpResponse("panne", { status: 500 }));
    rendre(<Livrables />);

    expect(await screen.findByText(/Impossible de charger/)).toBeInTheDocument();
    expect(screen.getByText(/500/)).toBeInTheDocument();
    expect(screen.queryByText(DISCOURS_DU_VIDE)).toBeNull();
    expect(screen.queryByText(/^0 document/)).toBeNull();
  });

  it("contre-épreuve — livrables : une liste vide REÇUE dit bien « Aucun document »", async () => {
    compteVide();
    rendre(<Livrables />);

    expect(await screen.findByText("Aucun document")).toBeInTheDocument();
    expect(screen.queryByText(/Impossible de charger/)).toBeNull();
  });

  it("crédits, 500 : ni « 0 » au solde, ni « Aucun mouvement », ni « Aucun abonnement »", async () => {
    partout(() => new HttpResponse("panne", { status: 500 }));
    rendre(<Credits />);

    expect((await screen.findAllByText(/Impossible de charger/)).length).toBeGreaterThan(0);
    expect(screen.queryByText(DISCOURS_DU_VIDE)).toBeNull();
    expect(chiffre("Solde")).not.toBe("0");
    expect(chiffre("Dotation mensuelle")).not.toBe("0");
  });

  it("contre-épreuve — crédits : un journal vide REÇU dit bien « Aucun mouvement »", async () => {
    compteVide();
    rendre(<Credits />);

    expect(await screen.findByText("Aucun mouvement")).toBeInTheDocument();
    expect(chiffre("Solde")).toBe("0");
    expect(screen.queryByText(/Impossible de charger/)).toBeNull();
  });

  it("suivi, 500 : une panne n'est pas « Étude introuvable »", async () => {
    partout(() => new HttpResponse("panne", { status: 500 }));
    rendre(<SuiviLivrable />);

    expect(await screen.findByText(/Impossible de charger/)).toBeInTheDocument();
    expect(screen.getByText(/500/)).toBeInTheDocument();
    expect(screen.queryByText(/introuvable/i)).toBeNull();
  });

  it("contre-épreuve — suivi, 404 : là, l'étude est bien introuvable", async () => {
    server.use(
      http.get(`${ESPACE}/livrables/job-1/`, () =>
        HttpResponse.json({ error: "Étude introuvable.", code: "introuvable" }, { status: 404 }),
      ),
    );
    rendre(<SuiviLivrable />);

    expect(await screen.findByText(/Étude introuvable/)).toBeInTheDocument();
    expect(screen.queryByText(/Impossible de charger/)).toBeNull();
  });

  // ── 3. La classe : chaque écran de l'espace ───────────────────────────────

  const PAGES = join(process.cwd(), "src", "espace", "pages");
  const lire = (page: string) => readFileSync(join(PAGES, page), "utf-8");

  it("trouve les écrans de l'espace (un contrôle sans rien à comparer échoue)", () => {
    expect(readdirSync(PAGES).filter((f) => f.endsWith(".tsx")).length).toBeGreaterThanOrEqual(14);
  });

  // Tout écran qui interroge le serveur dit l'échec de sa lecture. Découverts,
  // pas énumérés : un écran ajouté demain entre dans le verrou sans qu'on y
  // pense. `MonCompte` ne lit que `moi`, déjà en main ; il n'a pas de liste.
  for (const page of readdirSync(PAGES).filter((f) => f.endsWith(".tsx"))) {
    const source = lire(page);
    if (!/\buseQuery\(/.test(source)) continue;
    it(`${page} affiche l'échec de son chargement`, () => {
      expect(source).toMatch(/<ErreurDeChargement\b/);
    });
  }

  it("aucun écran de l'espace n'affiche une erreur par `String(…)`", () => {
    // « La restitution n'a pas abouti : Error: Session expirée. »
    for (const page of readdirSync(PAGES).filter((f) => f.endsWith(".tsx"))) {
      expect(lire(page), page).not.toMatch(/String\(\s*[\w.]*(?:error|erreur|cause)\s*\)/i);
    }
  });
});
