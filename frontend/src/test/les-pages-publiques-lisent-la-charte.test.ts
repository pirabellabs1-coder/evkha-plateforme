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
 * 2. AUCUNE couleur littérale (hexadécimale, `rgb()`, `rgba()`) hors
 *    commentaire — c'est la CLASSE du défaut (règle 4). Un `#fff` posé demain
 *    serait attrapé sans qu'on ait à allonger la liste.
 *
 * Contre-épreuve (règle 6) : ce qu'une feuille DOIT contenir — des jetons et
 * des `color-mix()` sur jetons — ne déclenche pas le verrou ; et ce qu'elle ne
 * doit pas contenir le déclenche bien.
 *
 * Rejoué sur le CSS d'avant (`git checkout ded4cdf -- <feuilles>`) : rouge sur
 * les quatre feuilles, vert sur celui-ci.
 *
 * jsdom ne calcule aucune mise en page : on lit les déclarations elles-mêmes,
 * comme `un-bouton-ne-rogne-pas-son-libelle`.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const DOSSIER = join(process.cwd(), "src", "public");
const FEUILLES = [
  "Partenaires.css",
  "Boutique.css",
  "Acheter.css",
  "NosEtudes.css",
] as const;

/** Les valeurs qui doublonnaient la charte, telles que trouvées dans le CSS
 *  d'avant. Comparées en minuscules et sans espaces : `rgba(248, 197, 28,
 *  0.35)` et `RGBA(248,197,28,.35)` sont la même couleur. */
const DOUBLONS: Record<string, string[]> = {
  or: [
    "#f8c51c",
    "#e8b923",
    "#b8901a",
    "#b8890a",
    "#f0c93a",
    "rgba(248,197,28",
  ],
  noir: [
    "#0b0b0b",
    "#000000",
    "#111111",
    "rgba(0,0,0",
    "rgba(11,11,11",
    "rgba(17,17,17",
  ],
  fond: ["#f8f4f4", "#f7f3e8", "#faf7f0", "#faf9f6", "#fdf6df"],
};

/** Une couleur écrite en dur : `#abc`, `#aabbcc`, `#aabbccdd`, `rgb(`, `rgba(`.
 *  Le `(?![\w-])` épargne les identifiants (`#formules`, `#catalogue`) : un
 *  `#` suivi de lettres qui se trouvent être hexadécimales n'est pas une
 *  couleur si le mot continue. */
const COULEUR_LITTERALE = /#[0-9a-f]{3,8}(?![\w-])|\brgba?\(/i;

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

describe("les pages publiques lisent la charte", () => {
  // Règle 1 : un contrôle qui n'a rien à comparer est un échec, pas un
  // succès. Si le dossier était vide, chaque test ci-dessous passerait.
  it("trouve les quatre feuilles, et aucune n'est vide", () => {
    for (const feuille of FEUILLES) {
      expect(sansCommentaires(lire(feuille)).trim().length, feuille).toBeGreaterThan(
        200,
      );
    }
  });

  for (const feuille of FEUILLES) {
    it(`${feuille} ne recopie ni l'or, ni le noir, ni le fond de la charte`, () => {
      const css = normalise(lire(feuille));
      for (const [famille, valeurs] of Object.entries(DOUBLONS)) {
        for (const valeur of valeurs) {
          expect(css, `${feuille} écrit ${famille} en dur : ${valeur}`).not.toContain(
            valeur,
          );
        }
      }
    });

    it(`${feuille} n'écrit aucune couleur littérale hors commentaire`, () => {
      const css = sansCommentaires(lire(feuille));
      const trouvee = css.match(COULEUR_LITTERALE);
      expect(trouvee, `${feuille} : ${trouvee?.[0] ?? ""}`).toBeNull();
    });

    it(`${feuille} lit les jetons de la charte`, () => {
      expect(lire(feuille)).toMatch(/var\(--(evkha|verre|texte|halo|ombre)-/);
    });
  }

  it("contre-épreuve : les jetons et color-mix() passent, une couleur en dur non", () => {
    const juste =
      "color: var(--evkha-or); background: color-mix(in srgb, var(--evkha-noir) 8%, transparent); #formules { scroll-margin-top: 6.5rem }";
    expect(juste).not.toMatch(COULEUR_LITTERALE);
    expect("color: #F8C51C").toMatch(COULEUR_LITTERALE);
    expect("color: #111").toMatch(COULEUR_LITTERALE);
    expect("box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2)").toMatch(COULEUR_LITTERALE);
    expect(normalise("background: RGBA(248, 197, 28, .35)")).toContain(
      "rgba(248,197,28",
    );
  });
});
