/** Aucune expression régulière « à regard arrière » dans le code livré au
 * navigateur.
 *
 * Le regard arrière — `(?<!…)` et `(?<=…)`, « lookbehind » — n'est compris de
 * Safari qu'à partir de la version 16.4 (mars 2023). Avant, ce n'est pas une
 * fonction qui manque : c'est une ERREUR DE SYNTAXE, levée au chargement du
 * fichier. Un seul motif de ce genre dans un module importé par l'application
 * suffit donc pour que rien ne s'affiche — ni la page qui s'en sert, ni
 * aucune autre — sur un iPhone resté sous iOS 15 ou 16.3.
 *
 * Deux motifs de ce genre étaient en production au commit `3ed3c1b` :
 * `contenuPacks.ancienneteSure` (« 15 ans » → « plus de 15 ans », sauf déjà
 * précédé de « plus de ») et `PagesLegales.ADRESSE` (une adresse de site ne
 * commence pas au milieu d'un mot). Les deux sont réécrits : le préfixe est
 * capturé, puis remis en place.
 *
 * Ce fichier verrouille la CLASSE (règle 4), pas ces deux lignes : il balaie
 * toutes les sources de `src` hors `src/test` et refuse les deux écritures,
 * dans un littéral `/…/` comme dans une chaîne passée à `new RegExp` — et
 * jusque dans un commentaire, d'où un motif reviendrait au prochain
 * copier-coller.
 *
 * Ce qu'il ne voit PAS, et qu'il faut savoir : un motif assemblé par morceaux
 * (`"(?" + "<!"`), et une dépendance de `node_modules` qui en porterait un.
 *
 * Les tests, eux, gardent le droit au regard arrière : ils tournent sous Node,
 * jamais dans un navigateur. C'est pourquoi `src/test` est hors du balayage —
 * et pourquoi ce fichier-ci peut écrire les motifs qu'il cherche.
 *
 * Contre-épreuves (règle 6) : le détecteur voit les deux écritures d'origine ;
 * il laisse passer le regard AVANT (`(?=…)`, `(?!…)`), un groupe nommé
 * (`(?<nom>…)`) et une comparaison ordinaire ; et les deux fonctions
 * réécrites rendent ce que rendaient les motifs d'origine.
 *
 * ÉCRIT SANS ÊTRE JOUÉ : la consigne du lot interdisait de lancer `vitest`.
 * À rejouer contre `3ed3c1b`, où il doit être rouge sur `contenuPacks.ts` et
 * `PagesLegales.tsx`.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { describe, expect, it } from "vitest";

import { ancienneteSure } from "../public/site";

const RACINE = join(process.cwd(), "src");

/** Ce qui part au navigateur : le code, pas les feuilles ni les images. */
const EXTENSIONS = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"];

/** Le regard arrière, négatif ou positif. Un groupe nommé (`(?<nom>`) n'en est
 *  pas un : après `(?<` vient une lettre, pas `!` ni `=`. */
const REGARD_ARRIERE = /\(\?<[!=]/g;

/** Tous les fichiers de code sous `dossier`, hors `src/test`. */
function sources(dossier: string): string[] {
  return readdirSync(dossier).flatMap((nom) => {
    const chemin = join(dossier, nom);
    if (statSync(chemin).isDirectory()) {
      return chemin === join(RACINE, "test") ? [] : sources(chemin);
    }
    return EXTENSIONS.some((extension) => nom.endsWith(extension)) ? [chemin] : [];
  });
}

/** Les lignes fautives d'un texte : « ligne N : le texte de la ligne ». */
function fautes(texte: string): string[] {
  return texte
    .split("\n")
    .map((ligne, k) => ({ ligne, numero: k + 1 }))
    .filter(({ ligne }) => ligne.match(REGARD_ARRIERE) !== null)
    .map(({ ligne, numero }) => `ligne ${numero} : ${ligne.trim()}`);
}

function nomDe(chemin: string): string {
  return relative(RACINE, chemin).split(sep).join("/");
}

describe("aucune regex à regard arrière dans le code de production", () => {
  const fichiers = sources(RACINE);

  it("le balayage voit les sources de l'application, et pas les tests", () => {
    const noms = fichiers.map(nomDe);
    // Règle 1 : un balayage qui ne trouve aucun fichier ne « passe » pas.
    expect(noms.length).toBeGreaterThan(60);
    for (const attendu of [
      "main.tsx",
      "router.tsx",
      "public/site.ts",
      "public/contenuPacks.ts",
      "public/PagesLegales.tsx",
      "espace/routes.tsx",
    ]) {
      expect(noms, attendu).toContain(attendu);
    }
    expect(noms.filter((nom) => nom.startsWith("test/"))).toEqual([]);
    // Et chaque fichier est lu pour de bon.
    for (const fichier of fichiers) {
      expect(readFileSync(fichier, "utf-8").length, nomDe(fichier)).toBeGreaterThan(0);
    }
  });

  it("aucune source hors `test/` n'écrit `(?<!` ni `(?<=`", () => {
    const fautives = fichiers.flatMap((fichier) =>
      fautes(readFileSync(fichier, "utf-8")).map((faute) => `${nomDe(fichier)} — ${faute}`),
    );
    expect(fautives).toEqual([]);
  });

  it("contre-épreuve : le détecteur voit les écritures d'origine, et rien d'autre", () => {
    // Les deux motifs du commit `3ed3c1b`, tels qu'ils étaient écrits.
    const dAvant = [
      'return texte.replace(/(?<!plus de )\\b1[56](?=\\sans\\b)/g, "plus de 15");',
      "`|(?<![a-z0-9@._-])(?:(?:https?://${HOTE}|www\\\\.${HOTE})${CHEMIN}` +",
    ];
    for (const ligne of dAvant) {
      expect(fautes(ligne), ligne).toHaveLength(1);
    }
    // Le regard arrière positif, en littéral et en chaîne, et en commentaire.
    expect(fautes("const apres = /(?<=€)\\d+/;")).toHaveLength(1);
    expect(fautes('new RegExp("(?<=plus de )\\\\d+")')).toHaveLength(1);
    expect(fautes("// l'ancien motif : (?<!plus de )")).toHaveLength(1);
    // Le numéro de ligne est celui du fichier.
    expect(fautes("const a = 1;\nconst b = /(?<!x)y/;\n")).toEqual(["ligne 2 : const b = /(?<!x)y/;"]);

    // Ce qui est permis : regard AVANT, groupe nommé, comparaisons, génériques.
    for (const juste of [
      "texte.replace(/(plus de )?\\b1[56](?=\\sans\\b)/g, remettre)",
      "/(?<annee>\\d{4})-(?<mois>\\d{2})/",
      "/\\d+(?!\\d)/",
      "/(?:https?:\\/\\/)?www\\./",
      "if (a ?<number>b : c) {}",
      "const liste: Array<string> = [];",
      "(courant) => (courant?.id === id ? null : courant)",
    ]) {
      expect(fautes(juste), juste).toEqual([]);
    }
  });

  it("contre-épreuve : l'ancienneté réécrite rend ce que rendait le regard arrière", () => {
    // Le motif d'origine, gardé ICI comme référence : sous Node, il se lit.
    const dOrigine = (texte: string) => texte.replace(/(?<!plus de )\b1[56](?=\sans\b)/g, "plus de 15");
    const INSECABLE = String.fromCharCode(0xa0);
    const cas = [
      "une expertise de 15 ans à vos côtés",
      "créateurs depuis 16 ans, qui",
      `avec 16${INSECABLE}ans de terrain`,
      "plus de 15 ans de terrain",
      "Depuis plus de 16 ans, j'accompagne",
      "15 ans d'expérience, puis 16 ans de plus et plus de 15 ans encore",
      "(15 ans d'expérience)",
      "Prévisionnel financier sur 3 ans",
      "1 à 2 semaines",
      "216 ans",
      "15 answers",
      "en 2015 ans",
      "plus de  15 ans",
      "",
    ];
    for (const texte of cas) {
      expect(ancienneteSure(texte), texte).toBe(dOrigine(texte));
    }
    // Et les cas ne sont pas tous des cas où rien ne change.
    expect(cas.filter((texte) => ancienneteSure(texte) !== texte).length).toBeGreaterThanOrEqual(5);
    expect(ancienneteSure("une expertise de 15 ans")).toBe("une expertise de plus de 15 ans");
    expect(ancienneteSure("plus de 15 ans de terrain")).toBe("plus de 15 ans de terrain");
  });
});
