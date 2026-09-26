/** La console parle la charte : plus rien de Radix Themes dans `src`.
 *
 * Six écrans de l'administration — générations, fiche d'une génération,
 * incidents, commandes, clients, fiche client — étaient composés en Radix
 * Themes (`Table`, `Badge`, `Button`, `Callout`…), avec les gris, les verts et
 * les rouges de Radix, lus par `var(--gray-9)`, `var(--accent-9)`,
 * `var(--red-2)` jusque dans les styles en ligne. Les huit autres écrans de la
 * même console étaient en verre : on changeait de charte en changeant d'onglet.
 * Et tant qu'un seul écran importait Radix, l'enveloppe `<Theme>` et ses
 * 27 000 lignes de CSS restaient chargées sur TOUTES les pages, publiques
 * comprises.
 *
 * Quatre verrous, du plus précis au plus large :
 *
 * 1. aucun fichier de `src` n'importe `@radix-ui/themes` (module ou feuille) ;
 * 2. aucun `.tsx` ni `.css` ne lit une variable de Radix — `--gray-*`,
 *    `--accent-*`, `--color-*`, mais aussi la CLASSE du défaut (règle 4) : les
 *    échelles numérotées (`--red-2`, `--sand-a3`), les tailles numérotées
 *    (`--space-3`, `--radius-2`), les réglages par défaut (`--font-mono`,
 *    `--default-*`, `--focus-*`). La charte n'a aucun nom de cette forme ;
 * 3. aucun `.tsx` ni `.css` ne pose une classe `rt-*` ni ne vise
 *    `.radix-themes` : sans l'enveloppe, ces sélecteurs ne visent plus rien ;
 * 4. `body` (`index.css`) fournit, en jetons, ce que l'enveloppe donnait en
 *    héritage — police, encre, interligne, taille de base, fond. Sans lui,
 *    `.pp` (pages publiques) perdait sa taille de base, et tout ce qui
 *    s'affiche hors des trois racines tombait en Times noir sur blanc.
 *
 * Les commentaires sont retirés avant lecture : un commentaire qui CITE
 * `--gray-12` pour raconter son retrait n'en lit pas un.
 *
 * Contre-épreuve (règle 6) en fin de fichier. Rejoué sur les sources de
 * `4c88e22` (sauvegarde, `git show`, restauration vérifiée par `cmp`) : rouge
 * sur les verrous 1, 2 et 4 ; vert ici.
 *
 * jsdom ne calcule aucun style : on lit les sources, comme
 * `les-pages-publiques-lisent-la-charte`.
 */
import { readFileSync, readdirSync } from "node:fs";
import { basename, join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(process.cwd(), "src");

/** Ce fichier cite les motifs qu'il cherche : il ne se lit pas lui-même. */
const CE_FICHIER = "la-console-parle-la-charte.test.ts";

function fichiersDe(dossier: string, extensions: string[]): string[] {
  return readdirSync(dossier, { withFileTypes: true }).flatMap((entree) => {
    const chemin = join(dossier, entree.name);
    if (entree.isDirectory()) return fichiersDe(chemin, extensions);
    if (entree.name === CE_FICHIER) return [];
    return extensions.some((e) => entree.name.endsWith(e)) ? [chemin] : [];
  });
}

function lire(chemin: string): string {
  return readFileSync(chemin, "utf-8").replace(/\r\n/g, "\n");
}

/** Retire les commentaires `/* … *\/` (CSS, TS, et `{/* … *\/}` en JSX) et
 *  `// …` (TS). Le `//` précédé de `:` est épargné : c'est une URL. */
function sansCommentaires(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(?<![:\\])\/\/[^\n]*/g, "");
}

/** Chemin lisible dans un message d'échec. */
function nom(chemin: string): string {
  return relative(SRC, chemin).replace(/\\/g, "/");
}

// ── Détecteurs ────────────────────────────────────────────────────────────

/** `import … from "@radix-ui/themes"`, `import "@radix-ui/themes/styles.css"`,
 *  `import("@radix-ui/themes")`, `require(…)`, et `@import` en CSS. */
const IMPORT_RADIX =
  /(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*|@import\s+(?:url\(\s*)?)["']?@radix-ui\/themes(?:\/[^"')\s;]*)?/;

const ECHELLES =
  "gray|mauve|slate|sage|olive|sand|tomato|red|ruby|crimson|pink|plum|purple|" +
  "violet|iris|indigo|blue|cyan|teal|jade|green|grass|bronze|gold|brown|orange|" +
  "amber|yellow|lime|mint|sky|black|white";

/** Une variable de l'espace de noms de Radix. `(?<![\w-])` : `--anneau-focus`
 *  ou `--texte-gray` ne sont pas des variables Radix. */
const VARIABLE_RADIX = new RegExp(
  "(?<![\\w-])--(?:" +
    [
      "(?:gray|accent|color|focus|default|cursor)-[\\w-]*",
      `(?:${ECHELLES})-a?\\d{1,2}(?![\\w-])`,
      "(?:space|radius|font-size|line-height|letter-spacing|shadow)-\\d(?![\\w-])",
      "font-(?:mono|weight-[\\w-]+)(?![\\w-])",
      "scaling(?![\\w-])",
    ].join("|") +
    ")",
);

/** Une classe `rt-*` de Radix, ou l'enveloppe `.radix-themes`. `\p{L}` : le
 *  « rt- » de « départ-… » n'en est pas une. */
const CLASSE_RADIX = /(?<![\p{L}\p{N}_-])(?:rt-[\p{L}\p{N}]|\.?radix-themes(?![\w-]))/u;

function trouve(fichiers: string[], motif: RegExp): string[] {
  const global = new RegExp(motif.source, motif.flags.includes("g") ? motif.flags : `${motif.flags}g`);
  return fichiers.flatMap((chemin) =>
    [...sansCommentaires(lire(chemin)).matchAll(global)].map(
      (m) => `${nom(chemin)} : ${m[0]}`,
    ),
  );
}

// ── Les sources ───────────────────────────────────────────────────────────

const CODE = fichiersDe(SRC, [".ts", ".tsx", ".css"]);
const RENDU = fichiersDe(SRC, [".tsx", ".css"]);

/** Les six écrans convertis, et le point d'entrée qui portait l'enveloppe. */
const CONVERTIS = [
  "pages/Jobs.tsx",
  "pages/JobDetail.tsx",
  "pages/Incidents.tsx",
  "pages/Orders.tsx",
  "pages/Clients.tsx",
  "pages/ClientDetail.tsx",
  "main.tsx",
];

/** Corps de la règle dont le sélecteur est EXACTEMENT `selecteur`. */
function regle(css: string, selecteur: string): string | undefined {
  for (const m of sansCommentaires(css).matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (m[1].trim() === selecteur) return m[2];
  }
  return undefined;
}

function valeur(corps: string, propriete: string): string | undefined {
  return corps
    .match(new RegExp(`(?:^|[;\\s])${propriete}\\s*:\\s*([^;]+)`))?.[1]
    ?.trim();
}

describe("la console parle la charte", () => {
  // Règle 1 : un contrôle qui n'a rien à comparer est un échec. Si la
  // découverte des fichiers se taisait, chaque verrou ci-dessous passerait.
  it("lit bien les sources : les écrans convertis, main.tsx, les feuilles", () => {
    const lus = CODE.map(nom);
    for (const fichier of CONVERTIS) expect(lus, fichier).toContain(fichier);
    expect(lus).toContain("index.css");
    expect(lus).toContain("theme/espace.css");
    expect(RENDU.filter((c) => c.endsWith(".css")).length).toBeGreaterThanOrEqual(8);
    expect(RENDU.filter((c) => c.endsWith(".tsx")).length).toBeGreaterThanOrEqual(40);
    expect(CODE.map((c) => basename(c))).not.toContain(CE_FICHIER);
  });

  it("aucun fichier de src n'importe @radix-ui/themes", () => {
    expect(trouve(CODE, IMPORT_RADIX)).toEqual([]);
  });

  it("aucun .tsx ni .css de src ne lit une variable de Radix", () => {
    expect(trouve(RENDU, VARIABLE_RADIX)).toEqual([]);
  });

  it("aucun .tsx ni .css de src ne pose une classe ni ne vise l'enveloppe de Radix", () => {
    expect(trouve(RENDU, CLASSE_RADIX)).toEqual([]);
  });

  it("body fournit, en jetons, ce que l'enveloppe Radix donnait en héritage", () => {
    const corps = regle(lire(join(SRC, "index.css")), "body");
    expect(corps, "index.css : aucune règle `body`").toBeDefined();
    const attendu: Record<string, RegExp> = {
      "font-family": /^var\(--police-corps\)$/,
      // 1rem : 16 px par défaut, mais qui suit le réglage du navigateur.
      "font-size": /^1rem$/,
      "line-height": /^var\(--interligne\)$/,
      color: /^var\(--texte(?:-[\w-]+)?\)$/,
      background: /^var\(--fond-[\w-]+\)$/,
    };
    for (const [propriete, motif] of Object.entries(attendu)) {
      expect(valeur(corps ?? "", propriete), `body { ${propriete} }`).toMatch(motif);
    }
  });

  it("contre-épreuve : ce qui est Radix est vu, ce qui est la charte ne l'est pas", () => {
    for (const faute of [
      'import { Theme } from "@radix-ui/themes";',
      'import "@radix-ui/themes/styles.css";',
      "import {\n  Box, Flex,\n} from '@radix-ui/themes';",
      'const t = await import("@radix-ui/themes");',
      '@import "@radix-ui/themes/tokens.css";',
    ]) {
      expect(IMPORT_RADIX.test(faute), faute).toBe(true);
    }
    for (const juste of [
      'import { Link } from "@tanstack/react-router";',
      'import * as Dialog from "@radix-ui/react-dialog";',
      "// on importait @radix-ui/themes ici",
    ]) {
      expect(IMPORT_RADIX.test(sansCommentaires(juste)), juste).toBe(false);
    }

    for (const faute of [
      "color: var(--gray-12);",
      "border-right: 1px solid var(--gray-6);",
      "color: var(--accent-9);",
      'style={{ background: "var(--red-2)" }}',
      "background: var(--color-panel-solid);",
      "background: var(--color-background);",
      "background: var(--sand-a3);",
      "font-family: var(--font-mono);",
      "border-radius: var(--radius-2);",
      "padding: var(--space-3);",
      "outline-color: var(--focus-8);",
    ]) {
      expect(VARIABLE_RADIX.test(faute), faute).toBe(true);
    }
    for (const juste of [
      "color: var(--evkha-or);",
      "box-shadow: var(--anneau-focus);",
      "padding: var(--e-4);",
      "font-size: var(--t-2xl);",
      "border-radius: var(--rayon-md);",
      "color: var(--gris);",
      "font-family: var(--police-mono);",
      "animation: x var(--duree-micro) var(--ease-doux);",
      "color: var(--prt-encre-tenue);",
      "/* l'encre était `--gray-12` */ color: var(--texte);",
    ]) {
      expect(VARIABLE_RADIX.test(sansCommentaires(juste)), juste).toBe(false);
    }

    for (const faute of [
      'className="rt-Button rt-variant-soft"',
      ".rt-Text { color: red; }",
      ".radix-themes { font-family: serif; }",
      'document.querySelector(".radix-themes")',
    ]) {
      expect(CLASSE_RADIX.test(faute), faute).toBe(true);
    }
    for (const juste of [
      'className="bouton bouton-sm"',
      'className="depart-rapide"',
      "le départ-arrivée",
      ".console-chaine-etape:not(:last-child)::after {}",
      "background: url(https://exemple.fr/start-x.png);",
    ]) {
      expect(CLASSE_RADIX.test(sansCommentaires(juste)), juste).toBe(false);
    }

    // Le lecteur de règles ne se laisse pas prendre par un sélecteur voisin.
    const css = "body.x { color: red; }\nbody { font-size: 1rem; color: var(--texte); }";
    expect(valeur(regle(css, "body") ?? "", "font-size")).toBe("1rem");
    expect(regle("html { color: red; }", "body")).toBeUndefined();
  });
});
