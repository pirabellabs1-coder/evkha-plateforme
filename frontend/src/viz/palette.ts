/** Palette de visualisation EVKHA — validée, non choisie à l'œil.
 *
 * Les quatre teintes ont été passées au validateur de la méthode data-viz
 * (`scripts/validate_palette.js`) contre la surface réelle des cartes,
 * `#FFFFFF`, en paires adjacentes ET en toutes-paires :
 *
 *   node validate_palette.js "#C79A0F,#2A78D6,#18784A,#C2508C" \
 *        --mode light --surface "#FFFFFF" --pairs all
 *
 *   [PASS] bande de clarté        les 4 dans la bande OKLCH 0,43–0,77
 *   [PASS] plancher de chroma     les 4 >= 0,10
 *   [PASS] séparation daltonisme  pire paire ΔE 10,7 (deutan) — cible >= 8
 *   [PASS] plancher vision normale pire paire ΔE 22,2 — plancher 15
 *   [WARN] contraste sur surface  or #C79A0F à 2,61:1
 *
 * L'or de marque `#F8C51C` **ne peut pas** servir de teinte de série : mesuré à
 * 1,62:1 sur blanc et hors bande de clarté, il a échoué deux contrôles. Il
 * reste la couleur d'accent de l'interface — boutons, états actifs — tandis que
 * les séries emploient un pas plus sombre de la même teinte, `#C79A0F`.
 *
 * L'avertissement de contraste sur l'or n'est pas ignoré : il **oblige** à
 * étiqueter directement les marques et à fournir une vue tableau. Les deux sont
 * livrés (`etiquettesDirectes` dans les composants, `TableauDeDonnees`).
 *
 * Les teintes s'attribuent dans un ORDRE FIXE, jamais en cycle : une série
 * supplémentaire ne reçoit pas une teinte inventée, elle est repliée dans
 * « Autres ». L'ordre est le mécanisme de sûreté daltonienne, pas un choix
 * esthétique.
 */

export const SERIES = [
  "#C79A0F", // 1 — or (pas sombre de l'or de marque)
  "#2A78D6", // 2 — bleu
  "#18784A", // 3 — vert
  "#C2508C", // 4 — magenta
] as const;

/** Nombre maximum de séries colorées. Au-delà : repli sur « Autres ». */
export const MAX_SERIES = SERIES.length;

/** Encre et chrome du graphique. Reprend les jetons de `theme/tokens.css`. */
export const CHROME = {
  surface: "var(--fond-carte)",
  encre: "var(--texte-fort)",
  encreSecondaire: "var(--texte-doux)",
  encreTenue: "var(--texte-tenu)",
  grille: "var(--evkha-bordure)",
  axe: "var(--evkha-bordure-forte)",
} as const;

/** Teinte de la série `index`. Au-delà du maximum, retourne le gris « Autres ».
 *
 * Ne cycle PAS. Cycler ferait réapparaître l'or en cinquième position : deux
 * séries de la même couleur dans un même graphique, ce qui est indétectable
 * pour le lecteur et faux.
 */
export function couleurSerie(index: number): string {
  return index < MAX_SERIES ? SERIES[index] : "var(--evkha-gris-pale)";
}
