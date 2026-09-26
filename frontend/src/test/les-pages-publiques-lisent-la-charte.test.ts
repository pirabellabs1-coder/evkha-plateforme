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
 * « Souscrire » — hors du verrou (revue du 26/09/2026). Elle y est entrée le
 * même jour, sans exemption : ses 23 couleurs lisent des jetons, et celles
 * qui ne sont pas de la charte (bouton Google, rouges d'erreur, filets
 * crème) ont un jeton nommé dans `tokens.css`, à leur valeur exacte.
 *
 * Le verrou 2 couvre désormais TOUTES les feuilles de `src`, pas seulement
 * les publiques : `la-charte-a-une-seule-source.test.ts`. La détection est
 * partagée (`charte.ts`) ; sa contre-épreuve (règle 6) est dans ce test
 * frère. Rejoué sur le CSS d'avant (`ded4cdf`) : rouge sur les quatre
 * feuilles refondues ; sur celui de `4c88e22` : rouge sur `Portail.css`.
 */
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { couleursLitterales, feuillesSous, lireFeuille, sansCommentaires, SRC } from "./charte";

const FEUILLES = feuillesSous(join(SRC, "public"));

/** Les valeurs qui doublonnaient la charte, telles que trouvées dans le CSS
 *  d'avant. Comparées en minuscules et sans espaces. */
const DOUBLONS: Record<string, string[]> = {
  or: ["#f8c51c", "#e8b923", "#b8901a", "#b8890a", "#f0c93a", "rgba(248,197,28"],
  noir: ["#0b0b0b", "#000000", "#111111", "rgba(0,0,0", "rgba(11,11,11", "rgba(17,17,17"],
  fond: ["#f8f4f4", "#f7f3e8", "#faf7f0", "#faf9f6", "#fdf6df"],
};

function normalise(css: string): string {
  return sansCommentaires(css).toLowerCase().replace(/\s+/g, "");
}

describe("les pages publiques lisent la charte", () => {
  // Règle 1 : un contrôle qui n'a rien à comparer est un échec, pas un
  // succès. Si le dossier était vide, chaque test ci-dessous passerait.
  it("trouve les feuilles publiques, Portail.css comprise, et aucune n'est vide", () => {
    expect(FEUILLES.length).toBeGreaterThanOrEqual(5);
    expect(FEUILLES).toContain("public/Portail.css");
    for (const feuille of FEUILLES) {
      expect(sansCommentaires(lireFeuille(feuille)).trim().length, feuille).toBeGreaterThan(200);
    }
  });

  for (const feuille of FEUILLES) {
    it(`${feuille} ne recopie ni l'or, ni le noir, ni le fond de la charte`, () => {
      const css = normalise(lireFeuille(feuille));
      for (const [famille, valeurs] of Object.entries(DOUBLONS)) {
        for (const valeur of valeurs) {
          expect(css, `${feuille} écrit ${famille} en dur : ${valeur}`).not.toContain(valeur);
        }
      }
    });

    it(`${feuille} n'écrit aucune couleur littérale`, () => {
      expect(couleursLitterales(lireFeuille(feuille)), feuille).toEqual([]);
    });

    it(`${feuille} lit les jetons de la charte`, () => {
      expect(sansCommentaires(lireFeuille(feuille))).toMatch(
        /var\(--(evkha|verre|texte|halo|ombre)-/,
      );
    });
  }
});
