/** Les pages publiques LISENT la charte, elles ne la recopient pas.
 *
 * `Partenaires.css` redéclarait un or (#E8B923), un noir (#111111) et deux
 * crèmes ; `Boutique.css` recopiait l'or de la charte (#F8C51C), un noir pur
 * (#000000) et trois crèmes ; `Acheter.css` et `NosEtudes.css` posaient leurs
 * blancs, leurs gris et leurs rouges. Quatre vérités pour une seule charte
 * (règle 5) : le jour où l'or de `tokens.css` bouge, les pages publiques ne
 * suivent pas, et personne ne le voit avant la cliente.
 *
 * Deux verrous, du plus précis au plus large :
 *
 * 1. la liste EXACTE des valeurs qui doublonnaient l'or, le noir et le fond,
 *    telles que trouvées dans le CSS d'avant — c'est le défaut nommé ;
 * 2. AUCUNE couleur littérale dans les VALEURS de déclaration — c'est la
 *    CLASSE du défaut (règle 4) : hexadécimal, fonction de couleur (`rgb`,
 *    `hsl`, `hwb`, `lab`, `lch`, `oklab`, `oklch`, `color()`), nom de couleur
 *    CSS (`white`, `black`…), et `%23…` dans une data-URI. `color-mix()` sur
 *    jetons, `transparent` et `currentColor` restent permis.
 *
 * Les feuilles sont DÉCOUVERTES dans `src/public`, pas énumérées : une liste
 * fermée laissait `Portail.css` — connexion, inscription, cible de chaque
 * « Souscrire » — hors du verrou (revue du 26/09/2026). Elle y est encore, en
 * exemption déclarée ; un test échoue le jour où elle n'a plus de couleur
 * littérale, pour que l'exemption rétrécisse au lieu de pourrir.
 *
 * Contre-épreuve (règle 6) en fin de fichier. Rejoué sur le CSS d'avant
 * (`ded4cdf`) : rouge sur les quatre feuilles refondues.
 *
 * jsdom ne calcule aucune mise en page : on lit les déclarations elles-mêmes,
 * comme `un-bouton-ne-rogne-pas-son-libelle`.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const DOSSIER = join(process.cwd(), "src", "public");

/** Feuilles publiques pas encore passées à la charte. À vider, jamais à
 *  allonger sans une raison écrite ici. */
const EN_ATTENTE = new Set(["Portail.css"]);

const FEUILLES = readdirSync(DOSSIER)
  .filter((f) => f.endsWith(".css"))
  .sort();
const VERROUILLEES = FEUILLES.filter((f) => !EN_ATTENTE.has(f));

/** Les valeurs qui doublonnaient la charte, telles que trouvées dans le CSS
 *  d'avant. Comparées en minuscules et sans espaces. */
const DOUBLONS: Record<string, string[]> = {
  or: ["#f8c51c", "#e8b923", "#b8901a", "#b8890a", "#f0c93a", "rgba(248,197,28"],
  noir: ["#0b0b0b", "#000000", "#111111", "rgba(0,0,0", "rgba(11,11,11", "rgba(17,17,17"],
  fond: ["#f8f4f4", "#f7f3e8", "#faf7f0", "#faf9f6", "#fdf6df"],
};

/** Les 148 noms de couleur de CSS Color 4 (sans `transparent` ni
 *  `currentColor`, qui ne sont pas des couleurs de marque). */
const NOMS = `aliceblue antiquewhite aqua aquamarine azure beige bisque black
blanchedalmond blue blueviolet brown burlywood cadetblue chartreuse chocolate
coral cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod
darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange
darkorchid darkred darksalmon darkseagreen darkslateblue darkslategray
darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey
dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold
goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory
khaki lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral
lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey lightpink
lightsalmon lightseagreen lightskyblue lightslategray lightslategrey
lightsteelblue lightyellow lime limegreen linen magenta maroon mediumaquamarine
mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue
mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream
mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered
orchid palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff
peru pink plum powderblue purple rebeccapurple red rosybrown royalblue
saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue
slategray slategrey snow springgreen steelblue tan teal thistle tomato
turquoise violet wheat white whitesmoke yellow yellowgreen`.split(/\s+/);

const NOM_DE_COULEUR = new RegExp(`(?<![\\w-])(?:${NOMS.join("|")})(?![\\w-])`, "i");
const HEXA = /#[0-9a-f]{3,8}(?![\w-])/i;
const FONCTION = /(?<![\w-])(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(/i;
const HEXA_ENCODE = /%23[0-9a-f]{3,8}(?![\w-])/i;

function lire(feuille: string): string {
  return readFileSync(join(DOSSIER, feuille), "utf-8").replace(/\r\n/g, "\n");
}

/** Un commentaire qui CITE une couleur pour expliquer son retrait n'en écrit
 *  pas une. */
function sansCommentaires(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

function normalise(css: string): string {
  return sansCommentaires(css).toLowerCase().replace(/\s+/g, "");
}

/** Les couleurs écrites en dur dans les VALEURS de déclaration. Les
 *  sélecteurs (`#formules {`) et les `url(#forme)` ne sont pas des couleurs ;
 *  les chaînes (noms de police) et les noms de propriétés personnalisées
 *  (`--texte-white`) non plus. */
function couleursLitterales(css: string): string[] {
  const texte = sansCommentaires(css);
  const trouvees: string[] = [];
  for (const uri of texte.matchAll(/url\(\s*["']?data:[^)]*\)/gi)) {
    const m = uri[0].match(HEXA_ENCODE);
    if (m) trouvees.push(m[0]);
  }
  const sansUrl = texte.replace(/url\([^)]*\)/gi, "url()");
  for (const decl of sansUrl.matchAll(/:\s*([^;{}]+)(?=[;}])/g)) {
    const valeur = decl[1]
      .replace(/"[^"]*"|'[^']*'/g, "")
      .replace(/--[\w-]+/g, "");
    for (const motif of [HEXA, FONCTION, NOM_DE_COULEUR]) {
      const m = valeur.match(motif);
      if (m) trouvees.push(m[0]);
    }
  }
  return trouvees;
}

describe("les pages publiques lisent la charte", () => {
  // Règle 1 : un contrôle qui n'a rien à comparer est un échec, pas un
  // succès. Si le dossier était vide, chaque test ci-dessous passerait.
  it("trouve les feuilles publiques, et aucune n'est vide", () => {
    expect(VERROUILLEES.length).toBeGreaterThanOrEqual(4);
    for (const feuille of FEUILLES) {
      expect(sansCommentaires(lire(feuille)).trim().length, feuille).toBeGreaterThan(200);
    }
  });

  it("l'exemption ne couvre que des feuilles qui existent et en ont besoin", () => {
    for (const feuille of EN_ATTENTE) {
      expect(FEUILLES, `${feuille} exemptée mais absente`).toContain(feuille);
      expect(
        couleursLitterales(lire(feuille)).length,
        `${feuille} n'a plus de couleur littérale : retirez-la de EN_ATTENTE`,
      ).toBeGreaterThan(0);
    }
  });

  for (const feuille of VERROUILLEES) {
    it(`${feuille} ne recopie ni l'or, ni le noir, ni le fond de la charte`, () => {
      const css = normalise(lire(feuille));
      for (const [famille, valeurs] of Object.entries(DOUBLONS)) {
        for (const valeur of valeurs) {
          expect(css, `${feuille} écrit ${famille} en dur : ${valeur}`).not.toContain(valeur);
        }
      }
    });

    it(`${feuille} n'écrit aucune couleur littérale`, () => {
      expect(couleursLitterales(lire(feuille)), feuille).toEqual([]);
    });

    it(`${feuille} lit les jetons de la charte`, () => {
      expect(sansCommentaires(lire(feuille))).toMatch(/var\(--(evkha|verre|texte|halo|ombre)-/);
    });
  }

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
});
