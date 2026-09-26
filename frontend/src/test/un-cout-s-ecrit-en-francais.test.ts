/** Un coût s'écrit en français, et « € » ou une flèche ne quittent jamais
 *  leur voisin.
 *
 * La console écrivait les coûts d'API `toFixed(4) + " €"` : point décimal à
 * l'anglaise et espace SÉCABLE — dans la colonne Coût des générations, « € »
 * partait seul à la ligne ; « Détail → » perdait sa flèche de même (contrôle
 * navigateur du 26/09/2026). Tout montant passe par `espace/format.ts`
 * (règle 5 : une seule source).
 *
 * Le premier verrou ne visait que `toFixed(n) €` et les flèches dans un
 * `<span aria-hidden>` : il laissait passer `unite=" €"`, « Voir l'étude → »,
 * « ← Toutes les études » (revue du 26/09/2026). Il vise maintenant la
 * CLASSE (règle 4) : une espace ordinaire (U+0020) entre un mot, un nombre ou
 * une expression JSX et « € » ou une flèche, dans le code affiché —
 * commentaires retirés, messages d'erreur techniques (`new Error(`) exclus.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { coutApi } from "../espace/format";

/** Espace insécable ou fine insécable, selon la version d'ICU. */
const INSECABLE = /[\u00a0\u202f]/;

/** Une espace sécable collée à « € » ou à une flèche. */
const ESPACE_SECABLE = new RegExp(
  [
    String.raw`[\p{L}\p{N}})"'\]] [€→↗↓]`, // « 149 € », « Voir → », unite=" €"
    String.raw`[←] [\p{L}\p{N}]`, // « ← Toutes »
    String.raw`[→←↗↓]</span> [\p{L}\p{N}]`, // flèche décorative puis libellé
    String.raw`[\p{L}\p{N}] <span aria-hidden="true">[→←↗↓]</span>`, // libellé puis flèche
  ].join("|"),
  "u",
);

function sources(dossier: string): string[] {
  return readdirSync(dossier, { withFileTypes: true }).flatMap((e) => {
    const chemin = join(dossier, e.name);
    if (e.isDirectory()) return e.name === "test" ? [] : sources(chemin);
    return /\.tsx?$/.test(e.name) ? [chemin] : [];
  });
}

/** Ce qui est affiché, pas ce qui est expliqué : commentaires retirés. */
function codeAffiche(source: string): string[] {
  const sansBlocs = source
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    .replace(/\/\*[\s\S]*?\*\//g, "");
  return sansBlocs
    .split("\n")
    .map((l) => l.replace(/(^|[^:"'`])\/\/.*$/, "$1"))
    .filter((l) => !/new Error\(/.test(l));
}

function fautes(): string[] {
  return sources(join(process.cwd(), "src")).flatMap((f) =>
    codeAffiche(readFileSync(f, "utf-8").replace(/\r\n/g, "\n"))
      .filter((l) => ESPACE_SECABLE.test(l) || /toFixed\(\d\)\}?\s*€/.test(l))
      .map((l) => `${f} : ${l.trim()}`),
  );
}

describe("un coût s'écrit en français", () => {
  it("virgule décimale, quatre décimales, espace insécable avant €", () => {
    const texte = coutApi("1.4724");
    expect(texte.replace(INSECABLE, " ")).toBe("1,4724 €");
    expect(texte).toMatch(INSECABLE);
    expect(coutApi(0.018)).toMatch(/^0,0180[\u00a0\u202f]€$/);
  });

  it("aucune espace sécable n'est collée à « € » ou à une flèche dans le code affiché", () => {
    expect(fautes()).toEqual([]);
  });

  it("contre-épreuve : le motif voit la faute et laisse passer le juste", () => {
    for (const faute of [
      '{parseFloat(x).toFixed(4)} €',
      'unite=" €"',
      "<span>Voir l'étude →</span>",
      "← Toutes les études",
      'Détail <span aria-hidden="true">→</span>',
      '<span aria-hidden="true">←</span> Générations',
      "`baissera de ${somme} €/mois`",
    ]) {
      expect(ESPACE_SECABLE.test(faute) || /toFixed\(\d\)\}?\s*€/.test(faute), faute).toBe(true);
    }
    for (const juste of [
      'Détail{"\\u00a0"}<span aria-hidden="true">→</span>',
      'unite="\\u00a0€"',
      "{f.coutApi(job.total_cost_eur)}",
      "const x = a → b;".replace("→", "=>"),
    ]) {
      expect(ESPACE_SECABLE.test(juste), juste).toBe(false);
    }
    expect(codeAffiche("// 149 € en commentaire")).toEqual([""]);
    expect(codeAffiche("throw new Error(`API ${p} → ${s}`);")).toEqual([]);
  });
});
