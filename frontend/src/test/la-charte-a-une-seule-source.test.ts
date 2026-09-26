/** La charte a UNE source : `theme/tokens.css`. Aucune autre feuille de
 * `src` n'écrit une couleur.
 *
 * `les-pages-publiques-lisent-la-charte` ne regardait que `src/public`. Hors
 * de ce dossier, `theme/espace.css` écrivait quinze couleurs en dur et
 * `admin/pages/BoutiqueAdmin.css` trois — chacune sous un en-tête qui
 * promettait « aucune couleur en dur ici ». Une promesse écrite en
 * commentaire n'est pas un verrou.
 *
 * Trois verrous :
 *
 * 1. les feuilles sont DÉCOUVERTES sous `src`, sous-dossiers compris ; seule
 *    `theme/tokens.css` est exclue, parce qu'elle EST la source ;
 * 2. aucune n'écrit de couleur littérale (détection de `charte.ts`, la même
 *    que pour les pages publiques). Une couleur étrangère à la charte — le
 *    bouton Google, le bandeau d'assistance — n'est pas une exception : elle
 *    a son jeton nommé dans `tokens.css`, à sa valeur exacte ;
 * 3. chaque jeton de couleur qu'une feuille lit (`--evkha-*`, `--google-*`,
 *    `--portail-*`, `--assistance-*`, familles réservées à `tokens.css`) y est
 *    déclaré. Un nom mal orthographié invalide la déclaration entière : la
 *    couleur disparaît sans un mot, et le verrou 2 resterait vert.
 *
 * Contre-épreuve (règle 6) en fin de fichier. Rejoué sur les feuilles de
 * `4c88e22` (sauvegarde, `git show`, restauration) : rouge sur
 * `public/Portail.css`, `theme/espace.css` et `admin/pages/BoutiqueAdmin.css`.
 */
import { describe, expect, it } from "vitest";
import { couleursLitterales, feuillesSous, lireFeuille, sansCommentaires, SOURCE } from "./charte";

const TOUTES = feuillesSous();
const FEUILLES = TOUTES.filter((f) => f !== SOURCE);

/** Les familles de jetons que seule `tokens.css` déclare. */
const FAMILLES = ["evkha", "google", "portail", "assistance"];
const LU = new RegExp(`var\\(\\s*(--(?:${FAMILLES.join("|")})-[\\w-]+)`, "g");

/** Les noms de propriétés personnalisées déclarés dans une feuille. */
function declares(css: string): Set<string> {
  return new Set([...sansCommentaires(css).matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]));
}

/** Les jetons des familles réservées qu'une feuille lit sans qu'ils soient
 *  déclarés dans `connus`. */
function jetonsInconnus(css: string, connus: Set<string>): string[] {
  const lus = new Set([...sansCommentaires(css).matchAll(LU)].map((m) => m[1]));
  return [...lus].filter((nom) => !connus.has(nom)).sort();
}

describe("la charte a une seule source", () => {
  const source = lireFeuille(SOURCE);
  const jetons = declares(source);

  // Règle 1 : un contrôle qui n'a rien à comparer est un échec, pas un
  // succès. Une découverte qui ne descendrait plus dans les sous-dossiers
  // laisserait passer chaque test ci-dessous.
  it("découvre les feuilles de tout src, sous-dossiers compris", () => {
    expect(TOUTES).toContain(SOURCE);
    expect(FEUILLES).toContain("theme/espace.css");
    expect(FEUILLES).toContain("public/Portail.css");
    expect(
      FEUILLES.filter((f) => f.startsWith("admin/")),
      "aucune feuille de admin/ découverte",
    ).not.toEqual([]);
    for (const feuille of FEUILLES) {
      expect(sansCommentaires(lireFeuille(feuille)).trim(), feuille).not.toBe("");
    }
  });

  it("la source, elle, écrit ses couleurs, et déclare chaque famille réservée", () => {
    // Un détecteur devenu aveugle ne verrait rien nulle part : il doit voir
    // les couleurs là où elles ont le droit d'être.
    expect(couleursLitterales(source).length).toBeGreaterThan(20);
    for (const famille of FAMILLES) {
      expect(
        [...jetons].some((nom) => nom.startsWith(`--${famille}-`)),
        `aucun jeton --${famille}-* dans ${SOURCE}`,
      ).toBe(true);
    }
  });

  for (const feuille of FEUILLES) {
    it(`${feuille} n'écrit aucune couleur littérale`, () => {
      expect(couleursLitterales(lireFeuille(feuille)), feuille).toEqual([]);
    });
  }

  it("chaque jeton de couleur lu par une feuille est déclaré dans tokens.css", () => {
    let lus = 0;
    const inconnus: string[] = [];
    for (const feuille of FEUILLES) {
      const css = lireFeuille(feuille);
      lus += [...sansCommentaires(css).matchAll(LU)].length;
      for (const nom of jetonsInconnus(css, jetons)) inconnus.push(`${feuille} : ${nom}`);
    }
    expect(lus).toBeGreaterThan(100);
    expect(inconnus).toEqual([]);
  });

  it("contre-épreuve : ce qui est une couleur est vu, ce qui n'en est pas une ne l'est pas", () => {
    for (const faute of [
      ".a { color: #F8C51C; }",
      ".a { color: #111 }",
      ".a { box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2); }",
      ".a { background: white; }",
      ".a { color: Black }",
      ".a { color: hsl(45 90% 55%); }",
      ".a { color: oklch(.8 .1 90); }",
      ".a { background: url(\"data:image/svg+xml,%3Csvg fill='%23000'%3E\"); }",
      ".a { color: var(--portail-appoint, #6b6a65); }",
    ]) {
      expect(couleursLitterales(faute), faute).not.toEqual([]);
    }
    for (const juste of [
      ".a { color: var(--evkha-or); background: color-mix(in srgb, var(--evkha-noir) 8%, transparent); }",
      "#faded { color: var(--evkha-or); }",
      "#formules { scroll-margin-top: 6.5rem }",
      ".a { mask: url(#forme); }",
      ".a { border-color: currentColor; background: transparent; }",
      ".a { font-family: \"Playfair Display\", serif; }",
      ".a { color: var(--texte-white-ish); }",
      ".a:hover { color: var(--texte); }",
      "@media (max-width: 600px) { .a { color: var(--texte); } }",
    ]) {
      expect(couleursLitterales(juste), juste).toEqual([]);
    }
  });

  it("contre-épreuve : un jeton mal nommé est vu, un jeton déclaré ou local non", () => {
    const connus = new Set(["--evkha-or", "--google-texte"]);
    expect(jetonsInconnus(".a { color: var(--evkha-orr); border-color: var( --portail-filet) }", connus)).toEqual([
      "--evkha-orr",
      "--portail-filet",
    ]);
    expect(jetonsInconnus(".a { color: var(--evkha-or); background: var(--google-texte) }", connus)).toEqual([]);
    // Hors des familles réservées : une propriété locale (`.pp`) n'est pas
    // un jeton de la charte.
    expect(jetonsInconnus(".a { background: var(--pp-verre-or-haut) }", connus)).toEqual([]);
    expect(declares(":root { --a: 1px; /* --b: 2px; */ } .c { --d:red }")).toEqual(new Set(["--a", "--d"]));
  });
});
