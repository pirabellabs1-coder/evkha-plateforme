/** Chaque mouvement de l'espace lit sa durée dans `tokens.css`.
 *
 * Le bloc `prefers-reduced-motion` de `tokens.css` remet les jetons de durée à
 * 0 ms : c'est ce qui arrête d'un coup toutes les animations qui les lisent.
 * Une durée écrite EN DUR lui échappe. Jusqu'au 26/09/2026, neuf animations et
 * deux transitions de `espace.css` étaient dans ce cas (`1.3s`, `1.6s`,
 * `2.8s`, `2.6s`, `2.2s`, `1.1s` deux fois, `520ms`, `0.22s`, `600ms`,
 * `0.12s`) : chacune ne s'arrêtait que si quelqu'un avait pensé à lui écrire
 * une règle `animation: none` nommée — et la transition de `transform` des
 * étoiles d'avis n'en avait aucune.
 *
 * Trois verrous, de la feuille aux jetons :
 *
 * 1. aucune déclaration de mouvement de `espace.css` (`animation`,
 *    `transition`, leurs `-duration` et `-delay`) n'écrit un temps littéral —
 *    la CLASSE du défaut (règle 4), pas la liste des onze valeurs ; et chaque
 *    `animation`/`transition` active lit un jeton de durée ;
 * 2. chaque jeton `--duree-*` du `:root` de `tokens.css` — et tout autre jeton
 *    dont la valeur est un temps, `--transition` ou `--decalage-reveal` — est
 *    remis à 0 dans son bloc de mouvement réduit. Un jeton ajouté sans sa
 *    remise à zéro rouvrirait le défaut par l'autre bout ;
 * 3. chaque `var(--duree-…)` lu par `espace.css` est déclaré : un nom mal
 *    orthographié invalide la déclaration entière, et l'animation disparaît
 *    sans un mot.
 *
 * Contre-épreuve (règle 6) : les détecteurs laissent passer un jeton, une
 * courbe `cubic-bezier()` ou un nom d'images clés chiffré, et attrapent bien un
 * temps en dur ou un jeton oublié.
 *
 * Rejoué sur les feuilles de `bdbd6e5` (sauvegarde, `git show`, restauration) :
 * rouge ; sur celles-ci : vert.
 *
 * jsdom ne calcule aucune mise en page ni aucune animation : on lit les
 * déclarations elles-mêmes, comme `un-bouton-ne-rogne-pas-son-libelle`.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const THEME = join(process.cwd(), "src", "theme");

function lire(feuille: string): string {
  return readFileSync(join(THEME, feuille), "utf-8").replace(/\r\n/g, "\n");
}

/** Un commentaire qui CITE une durée pour raconter son retrait n'en écrit pas
 *  une. */
function sansCommentaires(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

/** Une déclaration de mouvement : `animation`, `transition`, et leurs
 *  `-duration` / `-delay`, préfixe `-webkit-` compris. `animation-name` n'en
 *  est pas une — il ne porte pas de temps. */
const MOUVEMENT =
  /(?<![\w-])(?:-webkit-)?((?:animation|transition)(?:-duration|-delay)?)\s*:\s*([^;{}]*)/g;

/** Un temps écrit en dur : `1.3s`, `520ms`, `.5s`. Les bornes écartent les
 *  identifiants (`frise-2s`) et les nombres sans unité de temps
 *  (`cubic-bezier(0.22, 1, 0.36, 1)`, `12px`). */
const TEMPS_LITTERAL = /(?<![\w.-])\d*\.?\d+m?s(?![\w-])/g;

/** Un jeton qui porte une durée remise à zéro sous mouvement réduit. */
const JETON_DE_DUREE = /var\(\s*--(?:duree-[\w-]+|transition)\s*[,)]/;

interface Declaration {
  propriete: string;
  valeur: string;
}

function mouvements(css: string): Declaration[] {
  return [...sansCommentaires(css).matchAll(MOUVEMENT)].map((m) => ({
    propriete: m[1],
    valeur: m[2].replace(/\s+/g, " ").trim(),
  }));
}

function tempsLitteraux(valeur: string): string[] {
  return valeur.match(TEMPS_LITTERAL) ?? [];
}

/** Les jetons d'un bloc `:root`, nom → valeur. */
function jetons(bloc: string): Map<string, string> {
  const resultat = new Map<string, string>();
  for (const m of bloc.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    resultat.set(m[1], m[2].replace(/\s+/g, " ").trim());
  }
  return resultat;
}

/** Le `:root` de base de `tokens.css` : celui qui précède tout `@media`. */
function racine(css: string): Map<string, string> {
  const avantMedia = sansCommentaires(css).split("@media")[0];
  const bloc = avantMedia.match(/:root\s*\{([^}]*)\}/);
  if (!bloc) throw new Error(":root introuvable dans tokens.css");
  return jetons(bloc[1]);
}

/** Le `:root` du bloc `prefers-reduced-motion: reduce` de `tokens.css`. */
function reduction(css: string): Map<string, string> {
  const bloc = sansCommentaires(css).match(
    /@media\s*\(\s*prefers-reduced-motion:\s*reduce\s*\)\s*\{\s*:root\s*\{([^}]*)\}/,
  );
  if (!bloc) throw new Error("bloc prefers-reduced-motion introuvable dans tokens.css");
  return jetons(bloc[1]);
}

/** Les jetons de durée qui ne tombent PAS à zéro sous mouvement réduit : tout
 *  `--duree-*`, et tout jeton dont la valeur est un temps. */
function jetonsNonRemisAZero(css: string): string[] {
  const reduits = reduction(css);
  const fautifs: string[] = [];
  for (const [nom, valeur] of racine(css)) {
    const estUneDuree = nom.startsWith("--duree-") || tempsLitteraux(valeur).length > 0;
    if (!estUneDuree) continue;
    const remis = reduits.get(nom);
    if (remis === undefined || !/^(?:0+|0*\.0+)(?:ms|s)?$/.test(remis)) {
      fautifs.push(`${nom}: ${valeur} → ${remis ?? "absent du bloc"}`);
    }
  }
  return fautifs;
}

describe("les mouvements de l'espace lisent leurs durées", () => {
  const espace = lire("espace.css");
  const tokens = lire("tokens.css");
  const declarations = mouvements(espace);

  // Règle 1 : un contrôle qui n'a rien à comparer est un échec, pas un
  // succès. Si l'analyse ne trouvait aucune déclaration, tout passerait.
  it("trouve les déclarations de mouvement et les jetons de durée", () => {
    expect(declarations.length).toBeGreaterThan(20);
    const duree = [...racine(tokens).keys()].filter((n) => n.startsWith("--duree-"));
    expect(duree.length).toBeGreaterThanOrEqual(3);
    expect(reduction(tokens).size).toBeGreaterThanOrEqual(duree.length);
  });

  it("espace.css n'écrit aucun temps en dur dans un mouvement", () => {
    const fautives = declarations
      .filter((d) => tempsLitteraux(d.valeur).length > 0)
      .map((d) => `${d.propriete}: ${d.valeur}`);
    expect(fautives).toEqual([]);
  });

  it("chaque animation et chaque transition active lit un jeton de durée", () => {
    const sansJeton = declarations
      .filter((d) => !d.propriete.endsWith("-delay"))
      .filter((d) => d.valeur !== "none")
      .filter((d) => !JETON_DE_DUREE.test(d.valeur))
      .map((d) => `${d.propriete}: ${d.valeur}`);
    expect(sansJeton).toEqual([]);
  });

  it("chaque jeton de durée de tokens.css tombe à 0 sous mouvement réduit", () => {
    expect(jetonsNonRemisAZero(tokens)).toEqual([]);
  });

  it("chaque var(--duree-…) lu par espace.css est déclaré dans tokens.css", () => {
    const declares = racine(tokens);
    const lus = new Set(
      [...sansCommentaires(espace).matchAll(/var\(\s*(--duree-[\w-]+)/g)].map((m) => m[1]),
    );
    expect(lus.size).toBeGreaterThan(0);
    const inconnus = [...lus].filter((nom) => !declares.has(nom));
    expect(inconnus).toEqual([]);
  });

  it("contre-épreuve : un jeton passe, un temps en dur ou un jeton oublié non", () => {
    // Ce qui est juste ne déclenche rien.
    expect(tempsLitteraux("bouton-balayage var(--duree-balayage) var(--ease-doux) infinite")).toEqual([]);
    expect(tempsLitteraux("transform var(--duree-micro) cubic-bezier(0.22, 1, 0.36, 1)")).toEqual([]);
    expect(tempsLitteraux("frise-2s-coulee var(--duree-coulee) steps(4) 12px")).toEqual([]);
    expect(JETON_DE_DUREE.test("grid-template-columns var(--transition)")).toBe(true);

    // Ce qui est faux est attrapé, sous toutes ses formes d'écriture.
    expect(tempsLitteraux("bouton-balayage 1.3s var(--ease-doux) infinite")).toEqual(["1.3s"]);
    expect(tempsLitteraux("frise-increment 520ms var(--ease-sortie) backwards")).toEqual(["520ms"]);
    expect(tempsLitteraux("annonce-entree .22s ease-out")).toEqual([".22s"]);
    expect(tempsLitteraux("color 0.12s, transform 0.12s")).toEqual(["0.12s", "0.12s"]);
    expect(JETON_DE_DUREE.test("souscription-battement 1s ease-in-out infinite")).toBe(false);
    expect(
      mouvements(".a { animation-name: x; animation-delay: 400ms; transition: none }"),
    ).toEqual([
      { propriete: "animation-delay", valeur: "400ms" },
      { propriete: "transition", valeur: "none" },
    ]);

    // Un jeton de durée oublié dans le bloc de réduction, ou remis à autre
    // chose que zéro, est nommé.
    const oublis = `
      :root { --duree-a: 1s; --duree-b: 2s; --pas: 4px; --decalage: 55ms; }
      @media (prefers-reduced-motion: reduce) {
        :root { --duree-a: 0ms; --duree-b: 100ms; }
      }`;
    expect(jetonsNonRemisAZero(oublis)).toEqual([
      "--duree-b: 2s → 100ms",
      "--decalage: 55ms → absent du bloc",
    ]);
    const justes = `
      :root { --duree-a: 1s; --transition: 140ms ease; --duree-b: 2s; }
      @media (prefers-reduced-motion: reduce) {
        :root { --duree-a: 0ms; --transition: 0s; --duree-b: 0; }
      }`;
    expect(jetonsNonRemisAZero(justes)).toEqual([]);
    const pasUnZero = `
      :root { --duree-a: 1s; }
      @media (prefers-reduced-motion: reduce) { :root { --duree-a: ms; } }`;
    expect(jetonsNonRemisAZero(pasUnZero)).toEqual(["--duree-a: 1s → ms"]);
  });
});
