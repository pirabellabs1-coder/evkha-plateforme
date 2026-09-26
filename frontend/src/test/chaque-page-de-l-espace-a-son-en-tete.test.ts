/** Chaque page de l'espace client annonce son propre titre.
 *
 * L'en-tête de la coquille est dérivé de la route (`ENTETES` dans
 * `espace/Coquille.tsx`) ; une route absente de la table retombe sur
 * « Tableau de bord ». Vu le 26/09/2026 : la page de souscription s'ouvrait
 * sous le titre « Tableau de bord ». On verrouille la classe, pas l'exemple
 * (règle 4) : toute route fixe déclarée dans `espace/routes.tsx` doit avoir
 * son entrée. Les routes à paramètre (`livrables/$jobId`) ont leur repli
 * écrit à part dans la coquille.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const ESPACE = join(process.cwd(), "src", "espace");

function lire(fichier: string): string {
  return readFileSync(join(ESPACE, fichier), "utf-8").replace(/\r\n/g, "\n");
}

/** Chemins complets des routes enfants de `/espace`, sans paramètre. */
function routesFixes(): string[] {
  const source = lire("routes.tsx");
  const chemins = [...source.matchAll(/path:\s*"([^"]+)"/g)].map((m) => m[1]);
  return chemins
    .filter((c) => !c.startsWith("/") || c === "/")
    .filter((c) => !c.includes("$"))
    .map((c) => (c === "/" ? "/espace" : `/espace/${c}`));
}

function entetes(): string[] {
  const source = lire("Coquille.tsx");
  const table = source.slice(source.indexOf("const ENTETES"), source.indexOf("export function Coquille"));
  return [...table.matchAll(/^\s*"(\/espace[^"]*)":\s*\{/gm)].map((m) => m[1]);
}

describe("chaque page de l'espace a son en-tête", () => {
  it("trouve les routes et la table (un contrôle sans rien à comparer échoue)", () => {
    expect(routesFixes().length).toBeGreaterThanOrEqual(8);
    expect(entetes().length).toBeGreaterThanOrEqual(8);
  });

  for (const route of routesFixes()) {
    it(`${route} a son entrée dans ENTETES`, () => {
      expect(entetes()).toContain(route);
    });
  }
});
