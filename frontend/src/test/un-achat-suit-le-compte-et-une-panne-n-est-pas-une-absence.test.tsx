/** Sur les pages de vente : un achat fait par quelqu'un de connecté suit son
 *  COMPTE, et une panne n'est pas une étude introuvable.
 *
 * Audit du 19/11/2026, deux défauts des mêmes écrans.
 *
 * ## 1. L'achat partait toujours par la route publique
 *
 * Y compris juste après l'inscription, session ouverte, et depuis la boutique
 * atteinte par « Mes achats ». La route publique rattache l'achat à l'ADRESSE
 * collectée par Stripe, qui la laisse modifier : une adresse corrigée chez le
 * prestataire ouvrait un SECOND espace, où le crédit attendait quelqu'un qui
 * n'y viendrait jamais. Les routes de l'espace (`acheter_une_etude`,
 * `acheter_un_produit`, `backend/organisations/vues_espace.py`) portent
 * l'organisation ; `acheterUnProduit` n'avait aucun appelant.
 *
 * Les corps attendus ci-dessous sont ceux que ces vues LISENT (`etude`,
 * `produit`), et les réponses celles qu'elles rendent (`adresse`) — recopiés
 * du serveur, pas du client.
 *
 * ## 2. « Cette étude n'est pas disponible » pour toute erreur
 *
 * `Acheter` remplaçait un catalogue en échec par une liste vide ; `FicheProduit`
 * disait « pas disponible » sur n'importe quel refus. Un 500 annonçait donc à
 * quelqu'un qui venait payer que son lien ne menait nulle part.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ErreurApi, jeton } from "../espace/api";
import { AdresseDePaiementRefusee, payerUnProduit, payerUneEtude } from "../public/achat";
import { server } from "./server";

const parametres = { livrable: "etude-de-marche", slug: "foodtrucks" };

vi.mock("@tanstack/react-router", () => ({
  useParams: () => parametres,
  useNavigate: () => () => undefined,
  Link: ({ children, to }: { children: React.ReactNode; to?: string }) => (
    <a href={to ?? "#"}>{children}</a>
  ),
}));

// Importés APRÈS le simulacre du routeur.
const { Acheter } = await import("../public/Acheter");
const { FicheProduit } = await import("../public/FicheProduit");
const { Inscription } = await import("../public/Inscription");

// Lue AVANT tout remplacement de `window.location`.
const ORIGINE = window.location.origin;
const API = `${ORIGINE}/api`;

// L'hôte est le VRAI : `achat.ts` ne rend qu'une adresse de Stripe Checkout
// (`adresseDePaiementSure`, 20/11/2026). L'hôte inventé d'avant
// (`checkout.stripe.exemple`) serait refusé.
const STRIPE = "https://checkout.stripe.com/c/pay/cs_test_1";

/** Ce qui est parti au serveur, route par route. */
type Appel = { corps: Record<string, unknown>; autorisation: string | null };
let appels: Record<"espaceEtude" | "espaceProduit" | "publicEtude" | "publicProduit", Appel[]>;

function brancherLesPaiements(espace: () => Response = () => HttpResponse.json({ adresse: STRIPE })) {
  const noter = (cle: keyof typeof appels) =>
    async ({ request }: { request: Request }) => {
      appels[cle].push({
        corps: (await request.clone().json()) as Record<string, unknown>,
        autorisation: request.headers.get("Authorization"),
      });
    };
  server.use(
    http.post(`${API}/espace/etudes/acheter/`, async (info) => {
      await noter("espaceEtude")(info);
      return espace();
    }),
    http.post(`${API}/espace/achats/acheter/`, async (info) => {
      await noter("espaceProduit")(info);
      return espace();
    }),
    http.post(`${API}/public/acheter/`, async (info) => {
      await noter("publicEtude")(info);
      return HttpResponse.json({ adresse: STRIPE });
    }),
    http.post(`${API}/public/boutique/acheter/`, async (info) => {
      await noter("publicProduit")(info);
      return HttpResponse.json({ adresse: STRIPE });
    }),
  );
}

const FICHE = {
  produit: {
    slug: "foodtrucks",
    titre: "Le marché des foodtrucks",
    theme: "Restauration",
    prix_cents: 8900,
    devise: "EUR",
    pages: 42,
    mise_a_jour: "2026-10-01",
    image: "",
    note: 0,
    nombre_d_avis: 0,
    description: "Une étude déjà rédigée.",
    sommaire: ["Le marché", "Les acteurs"],
    apercu: null,
    editable: false,
    avis: [],
  },
  proches: [],
};

const CATALOGUE = {
  livrables: [
    { slug: "etude-de-marche", libelle: "Étude de marché", type: "market_study", prix_cents: 14900 },
  ],
};

// ── L'adresse du navigateur ─────────────────────────────────────────────────
// jsdom ne navigue pas : on pose une adresse qui ENREGISTRE les départs.

const adresseDOrigine = Object.getOwnPropertyDescriptor(window, "location");
let departs: string[] = [];

function poserLAdresse(chemin: string, recherche = "") {
  departs = [];
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      origin: ORIGINE,
      pathname: chemin,
      search: recherche,
      get href() {
        return `${ORIGINE}${chemin}${recherche}`;
      },
      set href(cible: string) {
        departs.push(cible);
      },
    },
  });
}

describe("un achat suit le compte, et une panne n'est pas une absence", () => {
  beforeEach(() => {
    localStorage.clear();
    appels = { espaceEtude: [], espaceProduit: [], publicEtude: [], publicProduit: [] };
    poserLAdresse("/boutique/foodtrucks");
  });

  afterEach(() => {
    if (adresseDOrigine) Object.defineProperty(window, "location", adresseDOrigine);
  });

  // ── 1. La règle ───────────────────────────────────────────────────────────

  it("étude : avec une session, le paiement part par l'espace, sous le jeton", async () => {
    brancherLesPaiements();
    jeton.ecrire("jeton-de-session");

    await expect(payerUneEtude("etude-de-marche", "autre@exemple.fr")).resolves.toBe(STRIPE);
    // Le corps que `acheter_une_etude` lit : `etude`, et rien qui fixe un prix
    // ou une adresse.
    expect(appels.espaceEtude).toEqual([
      { corps: { etude: "etude-de-marche" }, autorisation: "Bearer jeton-de-session" },
    ]);
    expect(appels.publicEtude).toEqual([]);
  });

  it("produit : avec une session, le paiement part par l'espace, sous le jeton", async () => {
    brancherLesPaiements();
    jeton.ecrire("jeton-de-session");

    await expect(payerUnProduit("foodtrucks")).resolves.toBe(STRIPE);
    // Le corps que `acheter_un_produit` lit : `produit`.
    expect(appels.espaceProduit).toEqual([
      { corps: { produit: "foodtrucks" }, autorisation: "Bearer jeton-de-session" },
    ]);
    expect(appels.publicProduit).toEqual([]);
  });

  it("contre-épreuve : un visiteur paie par la route publique, comme avant", async () => {
    brancherLesPaiements();

    await expect(payerUneEtude("etude-de-marche", "eva@exemple.fr")).resolves.toBe(STRIPE);
    await expect(payerUnProduit("foodtrucks", "eva@exemple.fr")).resolves.toBe(STRIPE);
    expect(appels.publicEtude).toEqual([
      { corps: { livrable: "etude-de-marche", email: "eva@exemple.fr" }, autorisation: null },
    ]);
    expect(appels.publicProduit).toEqual([
      { corps: { produit: "foodtrucks", email: "eva@exemple.fr" }, autorisation: null },
    ]);
    expect(appels.espaceEtude).toEqual([]);
    expect(appels.espaceProduit).toEqual([]);
  });

  it("une session périmée (401) retombe en visiteur, sans arracher à la page de vente", async () => {
    brancherLesPaiements(() =>
      HttpResponse.json({ error: "Authentification requise.", code: "unauthorized" }, { status: 401 }),
    );
    jeton.ecrire("jeton-perime");

    await expect(payerUnProduit("foodtrucks", "eva@exemple.fr")).resolves.toBe(STRIPE);
    expect(appels.espaceProduit).toHaveLength(1);
    expect(appels.publicProduit).toHaveLength(1);
    // Le jeton mort est effacé, mais personne n'est renvoyé à la connexion :
    // cette page est publique.
    expect(jeton.present()).toBe(false);
    expect(departs).toEqual([]);
  });

  it("un refus de l'espace (403) n'est PAS contourné par la route publique", async () => {
    brancherLesPaiements(() =>
      HttpResponse.json(
        {
          error:
            "Une session d'assistance ne peut engager aucune dépense au nom du client. " +
            "Quittez l'assistance pour agir depuis votre propre compte.",
          code: "assistance_sans_depense",
        },
        { status: 403 },
      ),
    );
    jeton.ecrire("jeton-d-assistance");

    const refus = await payerUneEtude("etude-de-marche").catch((cause: unknown) => cause);
    expect(refus).toBeInstanceOf(ErreurApi);
    expect((refus as ErreurApi).message).toMatch(/session d'assistance/);
    expect(appels.publicEtude).toEqual([]);
    expect(jeton.lire()).toBe("jeton-d-assistance");
  });

  // ── 2. Les écrans qui paient ──────────────────────────────────────────────

  it("fiche de boutique : connecté, « Acheter » passe par l'espace et ne demande pas d'adresse", async () => {
    brancherLesPaiements();
    server.use(http.get(`${API}/public/boutique/foodtrucks/`, () => HttpResponse.json(FICHE)));
    jeton.ecrire("jeton-de-session");
    render(<FicheProduit />);

    fireEvent.click(await screen.findByRole("button", { name: /Acheter/ }));

    await waitFor(() => expect(departs).toEqual([STRIPE]));
    expect(appels.espaceProduit).toHaveLength(1);
    expect(appels.publicProduit).toEqual([]);
    expect(screen.queryByLabelText(/adresse e-mail/i)).toBeNull();
    expect(screen.getByText(/rangée dans votre espace/)).toBeInTheDocument();
  });

  it("contre-épreuve — fiche de boutique : en visiteur, l'adresse est demandée et part avec l'achat", async () => {
    brancherLesPaiements();
    server.use(http.get(`${API}/public/boutique/foodtrucks/`, () => HttpResponse.json(FICHE)));
    render(<FicheProduit />);

    fireEvent.change(await screen.findByLabelText(/adresse e-mail/i), {
      target: { value: "eva@exemple.fr" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Acheter/ }));

    await waitFor(() => expect(departs).toEqual([STRIPE]));
    expect(appels.publicProduit[0].corps).toEqual({ produit: "foodtrucks", email: "eva@exemple.fr" });
    expect(appels.espaceProduit).toEqual([]);
  });

  it("page d'achat : connecté, « Payer » passe par l'espace", async () => {
    poserLAdresse("/acheter/etude-de-marche");
    brancherLesPaiements();
    server.use(http.get(`${API}/public/livrables/`, () => HttpResponse.json(CATALOGUE)));
    jeton.ecrire("jeton-de-session");
    render(<Acheter />);

    fireEvent.click(await screen.findByRole("button", { name: /Payer/ }));

    await waitFor(() => expect(departs).toEqual([STRIPE]));
    expect(appels.espaceEtude[0].corps).toEqual({ etude: "etude-de-marche" });
    expect(appels.publicEtude).toEqual([]);
    expect(screen.queryByLabelText(/adresse e-mail/i)).toBeNull();
  });

  it("inscription : le compte créé part payer par l'espace, sous le jeton qu'il vient de recevoir", async () => {
    poserLAdresse("/inscription", "?livrable=etude-de-marche");
    brancherLesPaiements();
    server.use(
      http.get(`${API}/public/formules/`, () => HttpResponse.json({ formules: [] })),
      http.get(`${API}/public/livrables/`, () => HttpResponse.json(CATALOGUE)),
      http.get(`${API}/public/reglages/`, () =>
        HttpResponse.json({ google: { actif: false, client_id: "" } }),
      ),
      http.post(`${API}/public/inscription/`, () =>
        HttpResponse.json(
          {
            jeton: "jeton-du-compte-neuf",
            organisation: { id: "org-1", raison_sociale: "Cabinet Eva" },
            formule_demandee: null,
            livrable_demande: "etude-de-marche",
            abonnement_actif: false,
            demande_id: null,
          },
          { status: 201 },
        ),
      ),
    );
    render(<Inscription />);

    fireEvent.change(screen.getByLabelText(/Raison sociale/), { target: { value: "Cabinet Eva" } });
    fireEvent.change(screen.getByLabelText(/Adresse e-mail/), { target: { value: "eva@exemple.fr" } });
    fireEvent.change(screen.getByLabelText(/Mot de passe/), { target: { value: "un mot de passe long" } });
    fireEvent.click(screen.getByRole("button", { name: /Créer mon compte/ }));

    await waitFor(() => expect(departs).toEqual([STRIPE]));
    expect(appels.espaceEtude).toEqual([
      { corps: { etude: "etude-de-marche" }, autorisation: "Bearer jeton-du-compte-neuf" },
    ]);
    expect(appels.publicEtude).toEqual([]);
  });

  it("inscription : si le paiement ne s'ouvre pas, l'écran dit que le COMPTE est créé, et où reprendre", async () => {
    poserLAdresse("/inscription", "?livrable=etude-de-marche");
    brancherLesPaiements(() =>
      HttpResponse.json(
        { error: "Le paiement est momentanément indisponible.", code: "paiement_indisponible" },
        { status: 503 },
      ),
    );
    server.use(
      http.get(`${API}/public/formules/`, () => HttpResponse.json({ formules: [] })),
      http.get(`${API}/public/livrables/`, () => HttpResponse.json(CATALOGUE)),
      http.get(`${API}/public/reglages/`, () =>
        HttpResponse.json({ google: { actif: false, client_id: "" } }),
      ),
      http.post(`${API}/public/inscription/`, () =>
        HttpResponse.json(
          { jeton: "jeton-du-compte-neuf", livrable_demande: "etude-de-marche" },
          { status: 201 },
        ),
      ),
    );
    render(<Inscription />);

    fireEvent.change(screen.getByLabelText(/Raison sociale/), { target: { value: "Cabinet Eva" } });
    fireEvent.change(screen.getByLabelText(/Adresse e-mail/), { target: { value: "eva@exemple.fr" } });
    fireEvent.change(screen.getByLabelText(/Mot de passe/), { target: { value: "un mot de passe long" } });
    fireEvent.click(screen.getByRole("button", { name: /Créer mon compte/ }));

    const alerte = await screen.findByRole("alert");
    expect(alerte).toHaveTextContent(/Votre compte est créé/);
    expect(alerte).toHaveTextContent(/momentanément indisponible/);
    expect(screen.getByRole("link", { name: /Reprendre depuis mon espace/ })).toHaveAttribute(
      "href",
      "/espace",
    );
    expect(departs).toEqual([]);
    // Le refus de l'espace n'est pas contourné par la route publique.
    expect(appels.publicEtude).toEqual([]);
  });

  // ── 2 bis. L'adresse de paiement est celle de Stripe ──────────────────────
  //
  // 20/11/2026. Les pages suivaient l'adresse rendue par le serveur sans
  // regarder où elle menait. `payerUneEtude` et `payerUnProduit` ne rendent
  // plus qu'une adresse de Stripe Checkout, hôte comparé exactement.

  const RESSEMBLANT = "https://checkout.stripe.com.evil.tld/c/pay/cs_test_1";
  const PANNE_DE_PAIEMENT = "Le paiement n'a pas pu être ouvert. Réessayez dans un instant.";

  it("étude et produit : une adresse qui ressemble à Stripe est refusée, pas rendue", async () => {
    brancherLesPaiements(() => HttpResponse.json({ adresse: RESSEMBLANT }));
    jeton.ecrire("jeton-de-session");

    await expect(payerUneEtude("etude-de-marche")).rejects.toBeInstanceOf(AdresseDePaiementRefusee);
    await expect(payerUnProduit("foodtrucks")).rejects.toBeInstanceOf(AdresseDePaiementRefusee);
    // Le serveur a bien été interrogé : c'est SA réponse qui est refusée.
    expect(appels.espaceEtude).toHaveLength(1);
    expect(appels.espaceProduit).toHaveLength(1);
    // Et le refus n'est pas contourné par la route publique.
    expect(appels.publicEtude).toEqual([]);
    expect(appels.publicProduit).toEqual([]);
  });

  it("fiche de boutique : une adresse hors de Stripe n'est pas suivie, la panne de paiement se dit", async () => {
    brancherLesPaiements(() => HttpResponse.json({ adresse: RESSEMBLANT }));
    server.use(http.get(`${API}/public/boutique/foodtrucks/`, () => HttpResponse.json(FICHE)));
    jeton.ecrire("jeton-de-session");
    render(<FicheProduit />);

    const acheter = await screen.findByRole("button", { name: /Acheter/ });
    fireEvent.click(acheter);

    expect(await screen.findByRole("alert")).toHaveTextContent(PANNE_DE_PAIEMENT);
    expect(appels.espaceProduit).toHaveLength(1);
    expect(departs).toEqual([]);
    expect(document.body.innerHTML).not.toContain("evil.tld");
    // On peut réessayer.
    expect(acheter).not.toBeDisabled();
  });

  it("page d'achat : une adresse en http: n'est pas suivie, la panne de paiement se dit", async () => {
    poserLAdresse("/acheter/etude-de-marche");
    brancherLesPaiements(() =>
      HttpResponse.json({ adresse: "http://checkout.stripe.com/c/pay/cs_test_1" }),
    );
    server.use(http.get(`${API}/public/livrables/`, () => HttpResponse.json(CATALOGUE)));
    jeton.ecrire("jeton-de-session");
    render(<Acheter />);

    fireEvent.click(await screen.findByRole("button", { name: /Payer/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(PANNE_DE_PAIEMENT);
    expect(appels.espaceEtude).toHaveLength(1);
    expect(departs).toEqual([]);
  });

  // La contre-épreuve — la vraie adresse de Stripe est suivie — est jouée par
  // les quatre écrans du bloc 2, qui attendent tous `departs = [STRIPE]`.

  // ── 3. Une panne n'est pas une absence ────────────────────────────────────

  it("fiche de boutique, 500 : une panne, « Réessayer » — et pas « n'est pas disponible »", async () => {
    let tentatives = 0;
    server.use(
      http.get(`${API}/public/boutique/foodtrucks/`, () => {
        tentatives += 1;
        return tentatives === 1
          ? new HttpResponse("panne", { status: 500 })
          : HttpResponse.json(FICHE);
      }),
    );
    render(<FicheProduit />);

    const reessayer = await screen.findByRole("button", { name: /Réessayer/ });
    expect(screen.getByRole("alert")).toHaveTextContent(/panne passagère/);
    expect(screen.queryByText(/n'est pas disponible/)).toBeNull();

    // Et « Réessayer » recharge vraiment.
    fireEvent.click(reessayer);
    expect(await screen.findByRole("heading", { name: "Le marché des foodtrucks" })).toBeInTheDocument();
    expect(tentatives).toBe(2);
  });

  it("contre-épreuve — fiche de boutique, 404 : là, l'étude n'est pas disponible", async () => {
    server.use(
      http.get(`${API}/public/boutique/foodtrucks/`, () =>
        HttpResponse.json(
          { erreur: "Cette étude n'est pas disponible.", code: "produit_inconnu" },
          { status: 404 },
        ),
      ),
    );
    render(<FicheProduit />);

    expect(await screen.findByText(/Cette étude n'est pas disponible/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Réessayer/ })).toBeNull();
  });

  it("page d'achat, 500 : une panne, « Réessayer » — et pas « n'est pas disponible »", async () => {
    poserLAdresse("/acheter/etude-de-marche");
    let tentatives = 0;
    server.use(
      http.get(`${API}/public/livrables/`, () => {
        tentatives += 1;
        return tentatives === 1
          ? new HttpResponse("panne", { status: 500 })
          : HttpResponse.json(CATALOGUE);
      }),
    );
    render(<Acheter />);

    const reessayer = await screen.findByRole("button", { name: /Réessayer/ });
    expect(screen.getByRole("alert")).toHaveTextContent(/panne passagère/);
    expect(screen.queryByText(/n'est pas disponible/)).toBeNull();

    fireEvent.click(reessayer);
    expect(await screen.findByRole("heading", { name: "Étude de marché" })).toBeInTheDocument();
    expect(tentatives).toBe(2);
  });

  it("contre-épreuve — page d'achat : une étude absente du catalogue REÇU n'est pas disponible", async () => {
    poserLAdresse("/acheter/etude-de-marche");
    server.use(
      http.get(`${API}/public/livrables/`, () =>
        HttpResponse.json({
          livrables: [
            { slug: "business-plan", libelle: "Business plan", type: "business_plan", prix_cents: 24900 },
          ],
        }),
      ),
    );
    render(<Acheter />);

    expect(await screen.findByText(/Cette étude n'est pas disponible/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Réessayer/ })).toBeNull();
  });
});
