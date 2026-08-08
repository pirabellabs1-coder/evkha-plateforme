/** Le journal exporté ne doit pas exécuter de code chez le comptable.
 *
 *  Une agence exporte ses crédits pour les rapprocher de sa comptabilité. Le
 *  fichier s'ouvre dans Excel ou LibreOffice — et ces deux-là **évaluent** toute
 *  cellule qui commence par `=`, `+`, `-` ou `@`.
 *
 *  Or les motifs viennent de la plateforme : un motif de dotation est saisi par
 *  l'équipe, un motif d'étude porte le sujet demandé par le client. Un texte
 *  commençant par `=` deviendrait donc une formule exécutée sur le poste de
 *  quelqu'un qui n'a rien demandé — sans qu'aucune alerte ne le signale.
 *
 *  C'est la même classe de défaut que le jeton en paramètre d'URL : une donnée
 *  qui voyage dans un contexte où elle change de nature.
 */
import { describe, expect, it } from "vitest";
import { versCsv } from "../espace/journal";
import type { Mouvement } from "../espace/api";

function mouvement(champs: Partial<Mouvement>): Mouvement {
  return {
    id: "m-1",
    date: "2026-07-15T10:00:00+02:00",
    type: "debit",
    quantite: -1,
    motif: "Étude de marché",
    auteur: "",
    ...champs,
  } as Mouvement;
}

describe("export du journal", () => {
  it("neutralise une cellule qui commencerait par un signe égal", () => {
    // Le test qui échoue sur un export naïf : sans préfixe, Excel évalue.
    const csv = versCsv([
      mouvement({ motif: "=1+1" }),
    ]);
    expect(csv).toContain(`"'=1+1"`);
    expect(csv).not.toContain(`"=1+1"`);
  });

  it("neutralise les autres amorces de formule", () => {
    // Viser la CLASSE, pas le seul `=` : les quatre amorces sont évaluées.
    for (const amorce of ["+", "-", "@"]) {
      const csv = versCsv([mouvement({ motif: `${amorce}SOMME(A1)` })]);
      expect(csv).toContain(`"'${amorce}SOMME(A1)"`);
    }
  });

  it("laisse intact un motif ordinaire", () => {
    // Contre-épreuve : la protection ne doit pas défigurer le cas courant.
    const csv = versCsv([mouvement({ motif: "Étude de marché — Paris" })]);
    expect(csv).toContain(`"Étude de marché — Paris"`);
    expect(csv).not.toContain("'Étude");
  });

  it("protège la structure quand le motif contient le séparateur", () => {
    // Un point-virgule dans un motif décalerait toutes les colonnes suivantes.
    const csv = versCsv([mouvement({ motif: "Vente auto ; Paris" })]);
    const lignes = csv.split("\r\n");
    expect(lignes).toHaveLength(2);
    expect(lignes[1]).toContain(`"Vente auto ; Paris"`);
  });

  it("double les guillemets présents dans un motif", () => {
    const csv = versCsv([mouvement({ motif: 'Étude "Rivage"' })]);
    expect(csv).toContain(`"Étude ""Rivage"""`);
  });

  it("écrit un en-tête et une ligne par mouvement", () => {
    const csv = versCsv([
      mouvement({ id: "a" }),
      mouvement({ id: "b", type: "dotation", quantite: 3 }),
    ]);
    const lignes = csv.split("\r\n");
    expect(lignes[0]).toBe("Date;Nature;Motif;Auteur;Crédits");
    expect(lignes).toHaveLength(3);
  });

  it("conserve le signe des quantités", () => {
    // Le signe EST l'information : un débit sans signe se lit comme une entrée.
    const csv = versCsv([mouvement({ quantite: -2 })]);
    expect(csv).toContain(`"-2"`);
  });
});
