/**
 * « Votre paiement, lui, est bien enregistré » ne se dit que si le serveur l'a
 * constaté.
 *
 * ## Le défaut
 *
 * `RetourPaiement` ajoutait cette phrase sous TOUTE erreur : une session que
 * le prestataire ne connaît pas, un plafond atteint, une panne de réseau, un
 * paiement jamais terminé. Elle rassurait donc quelqu'un qui n'avait rien
 * payé, ou dont on ne savait rien.
 *
 * ## La règle
 *
 * Une liste de ce qu'on SAIT (`CODES_PAIEMENT_ENREGISTRE`) et non de ce qu'on
 * exclut : seuls `achat_inexploitable` (encaissé, non livré) et
 * `paiement_en_attente` (la banque doit confirmer) disent qu'un paiement
 * existe. Chaque cas ci-dessous échoue sur la page d'avant, sauf les deux
 * contre-épreuves.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "./server";

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => () => undefined,
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

// Importé APRÈS le simulacre du routeur : la page le lit.
const { RetourPaiement } = await import("../public/RetourPaiement");

const RETOUR = `${window.location.origin}/api/public/acheter/retour/`;
const ENREGISTRE = /est bien enregistré chez notre/;

function revenir(statut: number, code: string, erreur: string) {
  window.history.pushState({}, "", "/acheter/retour?session=cs_test_1");
  server.use(
    http.post(RETOUR, () => HttpResponse.json({ erreur, code }, { status: statut })),
  );
  return render(<RetourPaiement />);
}

describe("le retour de paiement ne dit « enregistré » que ce qui l'est", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    window.history.pushState({}, "", "/");
  });

  it.each([
    [409, "paiement_non_abouti", "Ce paiement n'est pas allé au bout."],
    [503, "session_illisible", "Ce paiement n'a pas pu être vérifié."],
    [429, "trop_de_tentatives", "Trop de vérifications de paiement."],
    [409, "achat_autre", "Ce paiement ne concerne pas un livrable."],
    [400, "session_absente", "Paiement introuvable."],
  ])("refus %i « %s » : la phrase du serveur, sans promesse en plus", async (statut, code, erreur) => {
    revenir(statut, code, erreur);

    expect(await screen.findByRole("alert")).toHaveTextContent(erreur);
    expect(screen.queryByText(ENREGISTRE)).toBeNull();
  });

  it("panne de réseau : on ne sait rien, on n'affirme rien", async () => {
    window.history.pushState({}, "", "/acheter/retour?session=cs_test_1");
    server.use(http.post(RETOUR, () => HttpResponse.error()));
    render(<RetourPaiement />);

    await screen.findByRole("alert");
    expect(screen.queryByText(ENREGISTRE)).toBeNull();
  });

  it("sans session dans l'adresse : rien n'est dit enregistré", async () => {
    window.history.pushState({}, "", "/acheter/retour");
    render(<RetourPaiement />);

    await screen.findByRole("alert");
    expect(screen.queryByText(ENREGISTRE)).toBeNull();
  });

  // ── Contre-épreuves : ce qui EST enregistré continue d'être dit ───────────

  it.each([
    ["achat_inexploitable", "Votre paiement a bien été reçu, mais votre espace n'a pas pu être ouvert."],
    ["paiement_en_attente", "Votre paiement est enregistré, et votre banque doit encore le confirmer."],
  ])("refus « %s » : le paiement existe, la page le redit", async (code, erreur) => {
    revenir(409, code, erreur);

    expect(await screen.findByRole("alert")).toHaveTextContent(erreur);
    expect(screen.getByText(ENREGISTRE)).toBeInTheDocument();
  });
});
