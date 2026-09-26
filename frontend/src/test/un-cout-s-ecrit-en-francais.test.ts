/** Un coût s'écrit en français, et « € » ne quitte jamais son nombre.
 *
 * La console écrivait les coûts d'API `toFixed(4) + " €"` : point décimal à
 * l'anglaise et espace SÉCABLE — dans la colonne Coût des générations, « € »
 * partait seul à la ligne (vu au contrôle navigateur du 26/09/2026). La
 * classe du défaut : un nombre formaté à la main puis collé à « € ». Tout
 * montant passe par `espace/format.ts` (règle 5 : une seule source).
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { coutApi } from "../espace/format";

/** Espace insécable ou fine insécable, selon la version d'ICU. */
const INSECABLE = /[\u00a0\u202f]/;

function sources(dossier: string): string[] {
  return readdirSync(dossier, { withFileTypes: true }).flatMap((e) => {
    const chemin = join(dossier, e.name);
    if (e.isDirectory()) return e.name === "test" ? [] : sources(chemin);
    return /\.tsx?$/.test(e.name) ? [chemin] : [];
  });
}

describe("un coût s'écrit en français", () => {
  it("virgule décimale, quatre décimales, espace insécable avant €", () => {
    const texte = coutApi("1.4724");
    expect(texte.replace(INSECABLE, " ")).toBe("1,4724 €");
    expect(texte).toMatch(INSECABLE);
    expect(coutApi(0.018)).toMatch(/^0,0180[\u00a0\u202f]€$/);
  });

  it("aucun nombre formaté à la main n'est collé à « € » dans le code", () => {
    const fautes = sources(join(process.cwd(), "src")).flatMap((f) =>
      readFileSync(f, "utf-8")
        .split("\n")
        .filter((l) => /toFixed\(\d\)\}?\s*€/.test(l))
        .map((l) => `${f} : ${l.trim()}`),
    );
    expect(fautes).toEqual([]);
  });
});

describe("une flèche ne quitte pas son libellé", () => {
  // « Détail → » et « Voir → » : l'espace sécable laissait la flèche seule à
  // la ligne dans les colonnes étroites de la console (26/09/2026).
  it("aucun libellé n'est séparé de sa flèche par une espace sécable", () => {
    const fautes = sources(join(process.cwd(), "src")).flatMap((f) =>
      readFileSync(f, "utf-8")
        .split("\n")
        .filter((l) => /[\p{L}] <span aria-hidden="true">[→←↗↓]<\/span>/u.test(l))
        .map((l) => `${f} : ${l.trim()}`),
    );
    expect(fautes).toEqual([]);
  });
});
