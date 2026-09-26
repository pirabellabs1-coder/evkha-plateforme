/** Ce que les verrous de la charte partagent : la découverte des feuilles de
 * `src` et la détection d'une couleur écrite en dur.
 *
 * Une seule définition, importée par `les-pages-publiques-lisent-la-charte`,
 * `la-charte-a-une-seule-source` et `les-mouvements-lisent-leurs-durees` :
 * deux copies du détecteur finiraient par diverger, et un verrou laisserait
 * passer ce que l'autre attrape (règle 5). La contre-épreuve de la détection
 * (règle 6) est dans `la-charte-a-une-seule-source.test.ts`.
 *
 * jsdom ne calcule aucune mise en page : on lit les déclarations elles-mêmes,
 * comme `un-bouton-ne-rogne-pas-son-libelle`.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join, relative, sep } from "node:path";

/** La racine des sources du frontend. */
export const SRC = join(process.cwd(), "src");

/** La seule feuille qui a le droit d'écrire une couleur ou une durée. */
export const SOURCE = "theme/tokens.css";

/** Toutes les feuilles `.css` sous `dossier`, sous-dossiers compris, en
 *  chemins relatifs à `src` écrits avec `/` (`admin/pages/Annonces.css`),
 *  triées. DÉCOUVERTES, pas énumérées : une liste fermée laisse dehors la
 *  feuille qu'on ajoutera demain. */
export function feuillesSous(dossier: string = SRC): string[] {
  return readdirSync(dossier, { encoding: "utf-8", recursive: true })
    .filter((f) => f.endsWith(".css"))
    .map((f) => relative(SRC, join(dossier, f)).split(sep).join("/"))
    .sort();
}

/** Une feuille, par son chemin relatif à `src`, fins de ligne normalisées. */
export function lireFeuille(chemin: string): string {
  return readFileSync(join(SRC, chemin), "utf-8").replace(/\r\n/g, "\n");
}

/** Un commentaire qui CITE une couleur ou une durée pour expliquer son
 *  retrait n'en écrit pas une. */
export function sansCommentaires(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

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

/** Les couleurs écrites en dur dans les VALEURS de déclaration :
 *  hexadécimal, fonction de couleur (`rgb`, `hsl`, `hwb`, `lab`, `lch`,
 *  `oklab`, `oklch`, `color()`), nom de couleur CSS, et `%23…` dans une
 *  data-URI. `color-mix()` sur jetons, `transparent` et `currentColor`
 *  restent permis. Les sélecteurs (`#formules {`) et les `url(#forme)` ne
 *  sont pas des couleurs ; les chaînes (noms de police) et les noms de
 *  propriétés personnalisées (`--texte-white`) non plus. */
export function couleursLitterales(css: string): string[] {
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
