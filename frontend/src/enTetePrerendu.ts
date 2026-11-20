/** L'en-tête d'une page PRÉ-RENDUE, rendu à l'état du gabarit avant que
 * l'application ne monte.
 *
 * Une page pré-rendue (`scripts/prerendre.mjs`) arrive avec, dans son
 * `<head>`, tout ce que la page y pose d'ordinaire elle-même : son titre, sa
 * description, son adresse canonique, ses blocs de données structurées. C'est
 * ce qu'un robot sans JavaScript doit lire.
 *
 * Mais l'application, en montant, repose tout cela de son côté
 * (`site.useTitreDePage`, `useDonneesStructurees`). Mesuré le 20/11/2026 dans
 * un navigateur, sur l'image construite : la page des études portait alors
 * DEUX blocs `Service` et DEUX blocs `FAQPage`. Et ses crochets, qui rendent
 * en partant « ce qu'il y avait avant », auraient rendu le titre et l'adresse
 * canonique de la page pré-rendue à la page suivante — l'espace client
 * annoncé sous l'adresse des études.
 *
 * Le pré-rendu MARQUE donc ce qu'il a écrit, et cette fonction le défait :
 *
 *   - `data-prerendu` : une balise que la page a AJOUTÉE (adresse canonique,
 *     bloc de données structurées…) — elle est retirée ;
 *   - `data-origine` : une balise du gabarit dont la page a CHANGÉ la valeur
 *     (le titre, la description…) — elle retrouve la valeur du gabarit, que
 *     l'attribut porte.
 *
 * Les feuilles de style et le script préchargé de la page ne sont pas
 * marqués : ils restent.
 *
 * Les deux noms d'attribut sont écrits ici ET dans `scripts/prerendre.mjs`,
 * qui n'est pas du TypeScript et ne peut pas les importer : le test
 * `le-plan-du-site-n-oublie-aucune-page` verrouille qu'ils sont les mêmes
 * (règle 5 — à défaut d'une source unique, un contrôle qui les tient
 * d'accord).
 */
export const MARQUE_AJOUTEE = "data-prerendu";
export const MARQUE_CHANGEE = "data-origine";

export function rendreLEnTeteAuGabarit(document: Document): void {
  for (const balise of document.head.querySelectorAll(`[${MARQUE_AJOUTEE}]`)) {
    balise.remove();
  }
  for (const balise of document.head.querySelectorAll(`[${MARQUE_CHANGEE}]`)) {
    const origine = balise.getAttribute(MARQUE_CHANGEE) ?? "";
    if (balise.tagName === "TITLE") balise.textContent = origine;
    else balise.setAttribute("content", origine);
    balise.removeAttribute(MARQUE_CHANGEE);
  }
}
