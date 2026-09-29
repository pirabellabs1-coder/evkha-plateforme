/** La colonne « Fichiers » dit ce que le serveur sait — jamais « En préparation » par défaut.
 *
 * 29/09/2026, capture de l'utilisateur : l'espace d'Evangéline affichait
 * « En préparation » sur des études livrées en août (fichiers supprimés au
 * terme de leur conservation) et sur une stratégie annulée.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { EtatDesFichiers } from "../espace/api";
import { CelluleFichiers } from "../espace/composants/EtatDesFichiers";
import { dureeDeConservation } from "../espace/format";

function cellule(etat: EtatDesFichiers | undefined, fichiers: { kind: string; statut: string; url: string }[] = []) {
  return render(
    <CelluleFichiers livrable={{ fichiers, fichiers_etat: etat }} classeBouton="bouton" />,
  );
}

describe("la bibliothèque dit où sont ses fichiers", () => {
  it("des fichiers présents se téléchargent", () => {
    cellule({ etat: "disponibles", supprimes_le: null }, [
      { kind: "pdf", statut: "ready", url: "https://api.exemple/media/x.pdf?s=d1:a:b" },
    ]);
    expect(screen.getByRole("link", { name: "PDF" })).toHaveAttribute("href", expect.stringContaining("x.pdf"));
  });

  it("des fichiers supprimés le disent, avec leur date", () => {
    cellule({ etat: "supprimes", supprimes_le: "2026-08-25T16:54:00+00:00" });
    expect(screen.getByText(/Supprimés le 25 août 2026/)).toBeInTheDocument();
    expect(screen.queryByText(/En préparation/)).toBeNull();
  });

  it("une étude annulée ou en échec n'est pas « en préparation »", () => {
    cellule({ etat: "aucun", supprimes_le: null });
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText(/En préparation/)).toBeNull();
  });

  it("seule une étude en production est « en préparation »", () => {
    cellule({ etat: "en_preparation", supprimes_le: null });
    expect(screen.getByText("En préparation")).toBeInTheDocument();
  });

  it("une réponse sans état (serveur d'avant) ne ment pas non plus", () => {
    cellule(undefined);
    expect(screen.queryByText(/En préparation/)).toBeNull();
  });

  it("la durée de conservation se lit", () => {
    expect(dureeDeConservation(365)).toBe("un an");
    expect(dureeDeConservation(90)).toBe("3 mois");
    expect(dureeDeConservation(7)).toBe("7 jours");
  });
});
