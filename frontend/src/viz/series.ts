/** Mise en forme des séries avant tracé.
 *
 * Dans son propre fichier et non dans `Graphiques.tsx` : un module qui exporte
 * à la fois des composants et des fonctions casse le rafraîchissement à chaud
 * de Vite — c'est la règle `react-refresh/only-export-components`, et elle a
 * refusé la première version de ce code.
 */

/** Une série de valeurs, telle que les graphiques la consomment. */
export interface Serie {
  cle: string;
  libelle: string;
  valeurs: number[];
}

/** Coupe les périodes vides du DÉBUT d'une série.
 *
 * Le serveur rend toujours douze mois, et il a raison : un axe qui change de
 * longueur d'une visite à l'autre rend deux visites incomparables. La propriété
 * est verrouillée côté serveur par
 * `test_consommation_mensuelle::test_les_douze_mois_sont_toujours_rendus`.
 *
 * Mais un compte ouvert il y a six mois reçoit six mois de zéros AVANT son
 * histoire, et ils coûtent deux fois : le graphique dépense la moitié de sa
 * largeur sur du néant — donc des barres deux fois plus fines pour les mois qui
 * comptent —, et la vue tabulaire s'ouvre sur six lignes de « 0 0 ». C'est
 * exactement ce que la cliente a photographié.
 *
 * **On ne coupe qu'au début.** Un mois vide ENTRE deux mois pleins est une
 * information — c'est un mois sans commande — et le retirer ferait mentir la
 * continuité de l'axe. Le premier mois utile, lui, ne cache rien : avant, il
 * n'y avait pas de compte.
 *
 * Le découpage est fait côté interface et non côté serveur : c'est une décision
 * d'affichage, et la même réponse d'API sert aussi à calculer un rythme de
 * consommation, qui a besoin des douze mois.
 */
export function depuisLaPremiereDonnee(
  abscisses: string[],
  series: Serie[],
): { abscisses: string[]; series: Serie[] } {
  const debut = abscisses.findIndex((_, position) =>
    series.some((serie) => (serie.valeurs[position] ?? 0) !== 0),
  );
  // `-1` : aucune donnée nulle part. `0` : la série commence déjà à sa première
  // donnée. Dans les deux cas on rend tout, plutôt qu'un axe vide — l'appelant
  // décide d'afficher ou non, et il le fait déjà sur le total.
  if (debut <= 0) return { abscisses, series };
  return {
    abscisses: abscisses.slice(debut),
    series: series.map((serie) => ({
      ...serie,
      valeurs: serie.valeurs.slice(debut),
    })),
  };
}
