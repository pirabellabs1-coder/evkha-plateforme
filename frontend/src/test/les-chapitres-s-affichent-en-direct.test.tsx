/** La liste des chapitres suit le plan du type d'étude, en mots positifs.
 *
 * 29/09/2026 : une seule étape « Rédaction des chapitres » pendant une
 * demi-heure. La liste affiche chaque chapitre annoncé (22, 9, 21 ou 20 selon
 * l'étude) avec son étape — jamais « erreur », jamais « échec ».
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ChapitreEnDirect } from "../espace/api";
import { ChapitresEnDirect } from "../espace/composants/ChapitresEnDirect";

function plan(n: number): ChapitreEnDirect[] {
  return Array.from({ length: n }, (_, i) => ({
    numero: i + 1,
    titre: `Chapitre ${i + 1}`,
    etape: i < 3 ? "valide" : i === 3 ? "verification" : "",
    ajuste: i === 1,
  }));
}

describe("les chapitres s'affichent en direct", () => {
  it.each([22, 9, 21, 20])("une ligne par chapitre annoncé (%i)", (n) => {
    render(<ChapitresEnDirect chapitres={plan(n)} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(n);
    expect(screen.getByText(`3 chapitres validés sur ${n}`)).toBeInTheDocument();
  });

  it("dit l'étape de chaque chapitre, en mots positifs", () => {
    const { container } = render(<ChapitresEnDirect chapitres={plan(6)} />);
    expect(screen.getByText("Vérifié et ajusté")).toBeInTheDocument();
    expect(screen.getByText("Vérification en cours")).toBeInTheDocument();
    expect(screen.getAllByText("À venir")).toHaveLength(2);
    expect(container.textContent).not.toMatch(/erreur|échec|à revoir/i);
  });

  it("se tait sans chapitres", () => {
    const { container } = render(<ChapitresEnDirect chapitres={[]} />);
    expect(container.textContent).toBe("");
  });
});
