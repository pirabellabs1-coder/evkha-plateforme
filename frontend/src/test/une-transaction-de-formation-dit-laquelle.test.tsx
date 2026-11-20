/** Le suivi des paiements de l'administration nomme la FORMATION d'un panier.
 *
 * Depuis le 20/11/2026, une formation se paie sur la plateforme, et son
 * panier arrive dans `GET /api/dashboard/supervision/transactions/` avec
 * `objet: "formation"`, `objet_libelle: "Achat d'une formation"` et une clé
 * `formation` (le titre) ; `produit` y vaut "". L'écran n'affichait que
 * `produit` : la ligne disait « Achat d'une formation » sans dire laquelle —
 * or c'est le panier qui vaut le plus d'être relancé, et une relance ne
 * s'écrit pas sans savoir de quoi elle parle.
 *
 * La charge servie a la forme que `dashboard.supervision.transactions` écrit.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { TransactionsAdmin } from "../admin/pages/Transactions";
import { server } from "./server";

const TRANSACTIONS_API = `${window.location.origin}/api/dashboard/supervision/transactions/`;

function tentative(id: string, surcharges: Record<string, unknown>) {
  return {
    id,
    ouverte_le: "2026-11-20T09:00:00+00:00",
    organisation: "Visiteur",
    organisation_id: "",
    contact: `${id}@exemple.fr`,
    produit: "",
    formation: "",
    objet: "produit",
    objet_libelle: "Achat d'une étude",
    formule: "",
    quantite: 0,
    montant_cents: 8900,
    devise: "EUR",
    etat: "abandonnee",
    payee_le: "",
    relances: 0,
    derniere_relance_le: "",
    relancable: true,
    ...surcharges,
  };
}

const RESUME = {
  en_cours: 0,
  abandonnees: 2,
  payees: 0,
  manque_a_gagner_cents: 157900,
  encaisse_cents: 0,
};

function servir(transactions: object[]) {
  server.use(http.get(TRANSACTIONS_API, () => HttpResponse.json({ transactions, resume: RESUME })));
}

function monter() {
  const requetes = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={requetes}>
      <TransactionsAdmin />
    </QueryClientProvider>,
  );
}

/** La ligne du tableau qui porte ce contact. */
async function ligneDe(contact: string): Promise<HTMLElement> {
  const cellule = await screen.findByText(contact);
  return cellule.closest("tr") as HTMLElement;
}

afterEach(() => cleanup());

describe("une transaction de formation dit laquelle", () => {
  it("le panier d'une formation affiche son libellé ET le titre de la formation", async () => {
    servir([
      tentative("formation", {
        objet: "formation",
        objet_libelle: "Achat d'une formation",
        formation: "Créer sa micro-entreprise de A à Z",
        montant_cents: 149000,
      }),
    ]);
    monter();

    const ligne = await ligneDe("formation@exemple.fr");
    expect(within(ligne).getByText("Achat d'une formation")).toBeInTheDocument();
    expect(within(ligne).getByText("Créer sa micro-entreprise de A à Z")).toBeInTheDocument();
  });

  it("contre-épreuve : une étude de boutique garde son titre, et n'affiche rien pour une formation vide", async () => {
    servir([
      tentative("boutique", { produit: "Le marché des foodtrucks" }),
      tentative("formation", {
        objet: "formation",
        objet_libelle: "Achat d'une formation",
        formation: "Méthode P.O.P",
      }),
    ]);
    monter();

    const boutique = await ligneDe("boutique@exemple.fr");
    expect(within(boutique).getByText("Le marché des foodtrucks")).toBeInTheDocument();
    // Le titre d'une formation ne déborde pas sur la ligne voisine.
    expect(within(boutique).queryByText("Méthode P.O.P")).toBeNull();
    // Une clé vide ne produit pas de ligne vide : libellé + titre de l'étude.
    const objet = boutique.querySelectorAll("td")[2];
    expect(objet.querySelectorAll(".carte-note")).toHaveLength(1);
  });

  it("un serveur d'avant, qui ne rend pas la clé, n'affiche ni « undefined » ni ligne vide", async () => {
    const ancienne = tentative("ancienne", { produit: "Le marché des foodtrucks" }) as Record<string, unknown>;
    delete ancienne.formation;
    servir([ancienne]);
    monter();

    const ligne = await ligneDe("ancienne@exemple.fr");
    expect(ligne.textContent).not.toMatch(/undefined|null/);
    expect(ligne.querySelectorAll("td")[2].querySelectorAll(".carte-note")).toHaveLength(1);
  });
});
