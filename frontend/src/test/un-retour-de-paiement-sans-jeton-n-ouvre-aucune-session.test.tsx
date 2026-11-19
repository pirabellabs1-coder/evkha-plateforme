/** Un retour de paiement sans jeton n'ouvre aucune session — et le dit.
 *
 * Audit du 19/11/2026. Les deux routes de retour (`POST /api/public/acheter/
 * retour/`, `POST /api/public/boutique/retour/`) rendent désormais
 * `"jeton": null, "connexion_requise": true` quand l'adresse du paiement
 * appartient à un compte qui existait déjà : l'achat est livré sur ce compte,
 * aucune session n'est ouverte (`authentification.ouvrir_la_session_d_un_achat`).
 *
 * Les deux écrans, eux, écrivaient ce qu'ils recevaient :
 *
 * - `RetourPaiement` écrivait la chaîne VIDE — donc effaçait la session de
 *   quelqu'un de déjà connecté — puis partait vers `/espace/commander`, où la
 *   garde renvoyait à la connexion sans un mot sur le paiement ;
 * - `RetourBoutique` écrivait `null`, que le stockage garde sous la forme
 *   « null » : `jeton.present()` devenait vrai, « Voir mes achats » menait dans
 *   un espace où chaque appel répondait 401.
 *
 * Les charges ci-dessous sont celles que le serveur rend, recopiées de
 * `vues_publiques.retour_de_paiement` et `vues_boutique.retour` : les dériver
 * du client reviendrait à comparer le client à lui-même (règle 9).
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { jeton } from "../espace/api";
import { server } from "./server";

const navigations: { to: string; search?: Record<string, string> }[] = [];

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => (cible: { to: string; search?: Record<string, string> }) => {
    navigations.push(cible);
  },
  Link: ({
    to,
    className,
    children,
  }: {
    to: string;
    className?: string;
    children: React.ReactNode;
  }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

// Importés APRÈS le simulacre du routeur : les deux pages le lisent.
const { RetourPaiement } = await import("../public/RetourPaiement");
const { RetourBoutique } = await import("../public/RetourBoutique");

const PUBLIC = `${window.location.origin}/api/public`;

/** `retour_de_paiement` : compte déjà existant, donc aucun jeton. */
const ETUDE_SANS_JETON = {
  jeton: null,
  connexion_requise: true,
  livrable: "market_study",
  libelle: "Étude de marché",
};

/** `vues_boutique.retour` : les liens suivent le paiement, pas le compte. */
const PRODUIT_SANS_JETON = {
  jeton: null,
  connexion_requise: true,
  titre: "Le marché des foodtrucks",
  slug: "foodtrucks",
  telechargement: "https://api.exemple/media/boutique/foodtrucks.pdf?s=abc",
  editable: "",
};

function retourDEtude(charge: object) {
  window.history.pushState({}, "", "/acheter/retour?session=cs_test_1");
  server.use(http.post(`${PUBLIC}/acheter/retour/`, () => HttpResponse.json(charge)));
  return render(<RetourPaiement />);
}

function retourDeBoutique(charge: object) {
  window.history.pushState({}, "", "/boutique/retour?session=cs_test_2");
  server.use(http.post(`${PUBLIC}/boutique/retour/`, () => HttpResponse.json(charge)));
  return render(<RetourBoutique />);
}

describe("un retour de paiement sans jeton n'ouvre aucune session", () => {
  beforeEach(() => {
    localStorage.clear();
    navigations.length = 0;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.history.pushState({}, "", "/");
  });

  // ── L'étude à produire ────────────────────────────────────────────────────

  it("étude : sans jeton, rien n'est écrit et la connexion est proposée", async () => {
    const ecritures = vi.spyOn(Storage.prototype, "setItem");
    retourDEtude(ETUDE_SANS_JETON);

    const lien = await screen.findByRole("link", { name: /Se connecter/ });
    expect(lien).toHaveAttribute("href", "/espace/connexion");
    // Le paiement est dit reçu, et l'achat rattaché au compte de l'adresse.
    expect(screen.getByRole("heading", { name: /Paiement reçu/ })).toBeInTheDocument();
    expect(screen.getByText(/rattaché au compte/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();

    expect(ecritures).not.toHaveBeenCalled();
    expect(jeton.present()).toBe(false);
    // Personne n'est envoyé dans un espace qu'il ne peut pas ouvrir.
    expect(navigations).toEqual([]);
  });

  it("étude : une session déjà ouverte est gardée, et mène à l'espace", async () => {
    jeton.ecrire("session-existante");
    retourDEtude(ETUDE_SANS_JETON);

    await waitFor(() =>
      expect(navigations).toEqual([
        { to: "/espace/commander", search: { livrable: "market_study" } },
      ]),
    );
    expect(jeton.lire()).toBe("session-existante");
  });

  it("étude : un jeton reçu ne remplace jamais une session déjà ouverte", async () => {
    jeton.ecrire("session-existante");
    retourDEtude({ ...ETUDE_SANS_JETON, jeton: "jeton-d-un-autre-compte", connexion_requise: false });

    await waitFor(() => expect(navigations).toHaveLength(1));
    expect(jeton.lire()).toBe("session-existante");
  });

  it("contre-épreuve — étude : un compte né du paiement entre sans mot de passe", async () => {
    // Le même instrument que plus haut, sur un cas où il DOIT voir une
    // écriture : un espion qui ne verrait rien donnerait raison à tout.
    const ecritures = vi.spyOn(Storage.prototype, "setItem");
    retourDEtude({ ...ETUDE_SANS_JETON, jeton: "jeton-neuf", connexion_requise: false });

    await waitFor(() =>
      expect(navigations).toEqual([
        { to: "/espace/commander", search: { livrable: "market_study" } },
      ]),
    );
    expect(ecritures).toHaveBeenCalledWith(expect.any(String), "jeton-neuf");
    expect(jeton.lire()).toBe("jeton-neuf");
    expect(screen.queryByRole("link", { name: /Se connecter/ })).toBeNull();
  });

  // ── L'étude de boutique ───────────────────────────────────────────────────

  it("boutique : sans jeton, rien n'est écrit, les liens restent, la connexion est proposée", async () => {
    const ecritures = vi.spyOn(Storage.prototype, "setItem");
    retourDeBoutique(PRODUIT_SANS_JETON);

    // Le fichier acheté se télécharge quand même : le lien suit le paiement.
    const pdf = await screen.findByRole("link", { name: /Télécharger le PDF/ });
    expect(pdf).toHaveAttribute("href", PRODUIT_SANS_JETON.telechargement);
    expect(screen.getByText(/rattaché(e)? au compte/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Se connecter/ })).toHaveAttribute(
      "href",
      "/espace/connexion",
    );
    // « Voir mes achats » mènerait dans un espace sans session.
    expect(screen.queryByRole("link", { name: /Voir mes achats/ })).toBeNull();

    expect(ecritures).not.toHaveBeenCalled();
    expect(jeton.present()).toBe(false);
  });

  it("boutique : une session déjà ouverte est gardée, et mène aux achats", async () => {
    jeton.ecrire("session-existante");
    retourDeBoutique(PRODUIT_SANS_JETON);

    expect(await screen.findByRole("link", { name: /Voir mes achats/ })).toHaveAttribute(
      "href",
      "/espace/achats",
    );
    expect(jeton.lire()).toBe("session-existante");
    expect(screen.queryByRole("link", { name: /Se connecter/ })).toBeNull();
  });

  it("boutique : un jeton reçu ne remplace jamais une session déjà ouverte", async () => {
    jeton.ecrire("session-existante");
    retourDeBoutique({ ...PRODUIT_SANS_JETON, jeton: "jeton-d-un-autre-compte", connexion_requise: false });

    await screen.findByRole("link", { name: /Télécharger le PDF/ });
    expect(jeton.lire()).toBe("session-existante");
  });

  it("contre-épreuve — boutique : un compte né du paiement entre sans mot de passe", async () => {
    retourDeBoutique({ ...PRODUIT_SANS_JETON, jeton: "jeton-neuf", connexion_requise: false });

    expect(await screen.findByRole("link", { name: /Voir mes achats/ })).toBeInTheDocument();
    expect(jeton.lire()).toBe("jeton-neuf");
    expect(screen.queryByRole("link", { name: /Se connecter/ })).toBeNull();
  });

  // ── La porte elle-même ────────────────────────────────────────────────────

  it("le stockage refuse un jeton vide ou nul, d'où qu'il vienne", () => {
    jeton.ecrire("session-existante");
    jeton.ecrire("");
    jeton.ecrire(null as unknown as string);
    jeton.ecrire(undefined as unknown as string);
    expect(jeton.lire()).toBe("session-existante");
  });
});
