/** L'espace client ne parle jamais de « clients finaux ».
 *
 * Cet espace est celui d'UN abonné qui gère SA marque et SES études. Il n'a pas
 * de portefeuille de clients à administrer : ce vocabulaire vient d'un modèle
 * antérieur, où l'abonné était une agence travaillant pour des tiers.
 *
 * La cliente l'a relevé DEUX FOIS, sur deux écrans différents — d'abord dans la
 * navigation, puis dans la carte « Vos droits ». Corriger la seconde occurrence
 * après la première, c'est ce que la règle 4 proscrit : viser la classe du
 * défaut, pas son exemple. Ce test la vise.
 *
 * Il ne lit que les fichiers de l'espace client. Côté serveur et côté
 * administration, `ClientFinal` reste le nom du modèle et de l'action : le
 * renommer est un autre chantier, et le faire à moitié romprait la
 * correspondance entre la clé envoyée par le serveur et le libellé affiché.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Depuis le répertoire de travail, et non depuis `import.meta.url` : sous
// Vitest ce dernier n'est pas une URL `file:`, et `.pathname` rend « /C:/… »
// sous Windows. Le premier test vérifie que ce chemin trouve bien des
// fichiers — sans quoi le reste passerait sur un dossier vide.
const RACINE_ESPACE = join(process.cwd(), "src", "espace");

/** Formulations proscrites à l'écran, insensibles à la casse et au pluriel. */
const PROSCRITES = [/clients?\s+finaux/i, /client\s+final/i];

function fichiers(dossier: string): string[] {
  return readdirSync(dossier).flatMap((entree) => {
    const chemin = join(dossier, entree);
    if (statSync(chemin).isDirectory()) return fichiers(chemin);
    return chemin.endsWith(".tsx") || chemin.endsWith(".ts") ? [chemin] : [];
  });
}

/** Retire les commentaires : un terme cité pour l'expliquer n'est pas affiché.
 *
 * Sans ce dépouillage, le commentaire qui documente le renommage déclencherait
 * le test qui le verrouille — on mesurerait son propre balisage.
 */
function sansCommentaires(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
}

describe("vocabulaire de l'espace client", () => {
  const sources = fichiers(RACINE_ESPACE);

  it("trouve bien les fichiers de l'espace client", () => {
    // Un contrôle qui n'a rien à examiner est un échec, pas un succès
    // (règle 1) : sans cette vérification, un chemin cassé rendrait le test
    // ci-dessous vert pour de mauvaises raisons.
    expect(sources.length).toBeGreaterThan(10);
  });

  it.each(sources)("%s ne dit pas « clients finaux »", (chemin) => {
    const visible = sansCommentaires(readFileSync(chemin, "utf-8"));
    const fautives = PROSCRITES.flatMap(
      (motif) => visible.match(new RegExp(motif, "gi")) ?? [],
    );
    expect(
      fautives,
      `${chemin} emploie un vocabulaire d'agence. Cet espace est celui d'un ` +
        `abonné qui gère sa propre marque : écrire « ma marque », « ma ` +
        `charte », « mes études ».`,
    ).toEqual([]);
  });

  it("détecte la formulation qu'il est censé interdire", () => {
    // Contre-épreuve : sans elle, ce test pourrait passer parce qu'il ne
    // cherche rien (règle 6).
    const avant = 'gerer_clients_finaux: "Gérer les clients finaux et les chartes",';
    const trouve = PROSCRITES.some((motif) => motif.test(sansCommentaires(avant)));
    expect(trouve).toBe(true);
  });

  it("ne signale pas un terme cité en commentaire", () => {
    const legitime = `
      // On parle ici de clients finaux pour expliquer l'ancien modèle.
      const libelle = "Modifier ma marque et ma charte";
    `;
    const fautives = PROSCRITES.flatMap(
      (motif) => sansCommentaires(legitime).match(new RegExp(motif, "gi")) ?? [],
    );
    expect(fautives).toEqual([]);
  });
});
