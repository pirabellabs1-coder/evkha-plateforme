/** Chaque page de l'espace client annonce son propre titre.
 *
 * L'en-tête de la coquille est dérivé de la route (`ENTETES` dans
 * `espace/Coquille.tsx`) ; une route absente de la table retombe sur
 * « Tableau de bord ». Vu le 26/09/2026 : la page de souscription s'ouvrait
 * sous le titre « Tableau de bord ». On verrouille la classe, pas l'exemple
 * (règle 4) : toute route fixe déclarée dans `espace/routes.tsx` doit avoir
 * son entrée. Les routes à paramètre (`livrables/$jobId`) ont leur repli
 * écrit à part dans la coquille.
 *
 * Ajouté le 20/11/2026, avec « Mes formations » : chaque entrée de la
 * navigation mène à une route déclarée, chaque route à paramètre a SON repli
 * (sans lui, une formation ouverte s'annonçait « Tableau de bord »), et
 * « Mes formations » se range contre « Mes achats ».
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

/** Les sections des routes à paramètre : `formations/$slug` → `formations`. */
function sectionsAParametre(): string[] {
  const source = lire("routes.tsx");
  return [...source.matchAll(/path:\s*"([^"$/]+)\/\$[^"]+"/g)].map((m) => m[1]);
}

/** Les destinations de la navigation, dans l'ordre de la barre. */
function navigation(): { vers: string; libelle: string }[] {
  const source = lire("Coquille.tsx");
  const table = source.slice(source.indexOf("const ENTREES"), source.indexOf("const ENTETES"));
  return [...table.matchAll(/\{\s*vers:\s*"([^"]+)",\s*libelle:\s*"([^"]+)"/g)].map((m) => ({
    vers: m[1],
    libelle: m[2],
  }));
}

describe("la navigation de l'espace et ses routes à paramètre", () => {
  it("trouve la navigation et les routes à paramètre", () => {
    expect(navigation().length).toBeGreaterThanOrEqual(10);
    expect(sectionsAParametre()).toEqual(expect.arrayContaining(["clients", "livrables", "formations"]));
  });

  it("chaque entrée de la navigation mène à une route déclarée", () => {
    for (const entree of navigation()) {
      expect(routesFixes(), entree.libelle).toContain(entree.vers);
    }
  });

  it("« Mes formations » est dans la navigation, juste après « Mes achats »", () => {
    const libelles = navigation().map((entree) => entree.libelle);
    expect(libelles).toContain("Mes formations");
    expect(libelles[libelles.indexOf("Mes achats") + 1]).toBe("Mes formations");
    expect(navigation().find((entree) => entree.libelle === "Mes formations")?.vers).toBe("/espace/formations");
  });

  for (const section of sectionsAParametre()) {
    it(`/espace/${section}/… a son repli d'en-tête dans la coquille`, () => {
      expect(lire("Coquille.tsx")).toContain(`chemin.startsWith("/espace/${section}`);
    });
  }

  it("contre-épreuve : une section sans repli serait vue", () => {
    expect(lire("Coquille.tsx")).not.toContain('chemin.startsWith("/espace/section-inventee');
  });
});

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
