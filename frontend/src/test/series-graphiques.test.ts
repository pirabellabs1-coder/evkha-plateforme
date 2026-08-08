/** Un graphique commence à sa première donnée, pas au bord de la fenêtre.
 *
 * Le serveur rend toujours douze mois — propriété voulue, verrouillée côté
 * serveur par `test_les_douze_mois_sont_toujours_rendus` : un axe qui change de
 * longueur d'une visite à l'autre rend deux visites incomparables.
 *
 * Mais un compte ouvert il y a six mois recevait six mois de zéros AVANT son
 * histoire. La cliente l'a photographié le 06/08/2026 : la vue « Voir les
 * données » s'ouvrait sur « sept. 0 0 / oct. 0 0 / nov. 0 0 … », et le
 * graphique dépensait la moitié de sa largeur sur du néant — donc des barres
 * deux fois plus fines pour les mois qui comptent.
 */
import { describe, it, expect } from "vitest";

import { depuisLaPremiereDonnee } from "../viz/series";

const MOIS = [
  "sept.", "oct.", "nov.", "déc.", "janv.", "févr.",
  "mars", "avr.", "mai", "juin", "juil.", "août",
];

function serie(cle: string, valeurs: number[]) {
  return { cle, libelle: cle, valeurs };
}

describe("depuisLaPremiereDonnee", () => {
  it("coupe les mois vides du début", () => {
    const recus = serie("recus", [0, 0, 0, 0, 0, 0, 3, 3, 3, 3, 3, 5]);
    const consommes = serie("consommes", [0, 0, 0, 0, 0, 0, 1, 3, 2, 3, 1, 4]);

    const { abscisses, series } = depuisLaPremiereDonnee(MOIS, [recus, consommes]);

    expect(abscisses).toEqual(["mars", "avr.", "mai", "juin", "juil.", "août"]);
    expect(series[0].valeurs).toEqual([3, 3, 3, 3, 3, 5]);
    expect(series[1].valeurs).toEqual([1, 3, 2, 3, 1, 4]);
  });

  it("une série commence dès qu'UNE seule des séries porte quelque chose", () => {
    // Un mois où l'on n'a rien reçu mais où l'on a consommé est un vrai mois.
    const recus = serie("recus", [0, 0, 3]);
    const consommes = serie("consommes", [0, 2, 1]);

    const { abscisses } = depuisLaPremiereDonnee(
      ["janv.", "févr.", "mars"],
      [recus, consommes],
    );

    expect(abscisses).toEqual(["févr.", "mars"]);
  });

  it("ne coupe RIEN au milieu : un mois creux est une information", () => {
    // C'est la contre-épreuve qui compte. Retirer les mois vides partout
    // ferait mentir la continuité de l'axe : deux mois pleins séparés par un
    // mois sans commande deviendraient contigus, et la courbe raconterait une
    // régularité qui n'a pas eu lieu.
    const recus = serie("recus", [3, 0, 3]);
    const consommes = serie("consommes", [1, 0, 2]);

    const { abscisses, series } = depuisLaPremiereDonnee(
      ["janv.", "févr.", "mars"],
      [recus, consommes],
    );

    expect(abscisses).toEqual(["janv.", "févr.", "mars"]);
    expect(series[0].valeurs).toEqual([3, 0, 3]);
  });

  it("ne coupe pas la fin non plus", () => {
    const recus = serie("recus", [3, 2, 0]);

    const { abscisses } = depuisLaPremiereDonnee(
      ["janv.", "févr.", "mars"],
      [recus],
    );

    expect(abscisses).toEqual(["janv.", "févr.", "mars"]);
  });

  it("tout à zéro : on rend tout plutôt qu'un axe vide", () => {
    // L'appelant décide d'afficher ou non — il le fait déjà sur le total.
    // Rendre un tableau vide ici ferait planter le calcul de l'échelle.
    const recus = serie("recus", [0, 0, 0]);

    const { abscisses, series } = depuisLaPremiereDonnee(
      ["janv.", "févr.", "mars"],
      [recus],
    );

    expect(abscisses).toHaveLength(3);
    expect(series[0].valeurs).toEqual([0, 0, 0]);
  });

  it("les séries d'origine ne sont pas modifiées", () => {
    // Elles servent AUSSI au calcul du rythme de consommation, qui a besoin
    // des douze mois. Les muter ferait diverger deux lectures de la même
    // réponse d'API (règle 5).
    const recus = serie("recus", [0, 0, 4]);
    const copie = [...recus.valeurs];

    depuisLaPremiereDonnee(["janv.", "févr.", "mars"], [recus]);

    expect(recus.valeurs).toEqual(copie);
  });
});
