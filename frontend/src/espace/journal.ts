/** Export du journal de crédits en CSV.
 *
 *  Une agence facture ses propres clients : elle doit pouvoir rapprocher ses
 *  consommations de sa comptabilité. Recopier un tableau à l'écran, ligne à
 *  ligne, est exactement le genre de tâche que cet espace doit éviter.
 *
 *  L'export est fabriqué à partir des mouvements **déjà chargés** : aucune
 *  seconde route, donc aucun risque que le fichier et l'écran ne racontent pas
 *  la même chose.
 */
import type { Mouvement } from "./api";
import * as f from "./format";

/** Séparateur point-virgule, et non virgule.
 *
 *  Excel en configuration française attend le point-virgule : avec une virgule
 *  il empile toute la ligne dans une seule cellule. Le fichier serait
 *  techniquement valide et concrètement inutilisable. */
const SEPARATEUR = ";";

const COLONNES = ["Date", "Nature", "Motif", "Auteur", "Crédits"] as const;

/** Neutralise une valeur avant de l'écrire dans une cellule.
 *
 *  Deux protections distinctes :
 *
 *  1. **Guillemets et sauts de ligne** — un motif contenant un `;` ou un
 *     retour à la ligne casserait la structure du fichier.
 *
 *  2. **Injection de formule.** Une cellule commençant par `=`, `+`, `-` ou
 *     `@` est interprétée comme une formule à l'ouverture. Un motif saisi
 *     ailleurs dans la plateforme deviendrait donc du code exécuté sur le poste
 *     de la personne qui ouvre l'export. On préfixe d'une apostrophe : le
 *     tableur affiche le texte tel quel et n'évalue rien.
 */
function cellule(valeur: string | number): string {
  const texte = String(valeur ?? "");

  // Un NOMBRE n'est jamais préfixé, et la distinction n'est pas cosmétique :
  // `-2` protégé devient `'-2`, que le tableur lit comme du texte. La colonne
  // Crédits cesse alors d'être sommable — or c'est précisément pour la sommer
  // qu'on exporte. La protection aurait vidé l'export de son intérêt tout en
  // paraissant fonctionner.
  //
  // Le risque d'injection porte sur les champs de texte, qui viennent de la
  // base ; les quantités, elles, sont nos propres entiers.
  if (typeof valeur === "number") {
    return `"${texte}"`;
  }

  const neutralise = /^[=+\-@\t\r]/.test(texte) ? `'${texte}` : texte;
  return `"${neutralise.replace(/"/g, '""')}"`;
}

export function versCsv(mouvements: Mouvement[]): string {
  const lignes = [
    COLONNES.join(SEPARATEUR),
    ...mouvements.map((mouvement) =>
      [
        cellule(f.dateHeure(mouvement.date)),
        cellule(f.typeMouvement(mouvement.type)),
        cellule(mouvement.motif),
        cellule(mouvement.auteur ?? ""),
        cellule(mouvement.quantite),
      ].join(SEPARATEUR),
    ),
  ];
  return lignes.join("\r\n");
}

export function telechargerJournal(mouvements: Mouvement[]): void {
  // Le BOM (U+FEFF) n'est pas une coquetterie : sans lui, Excel lit le fichier
  // en codage local et affiche « Ã‰tude » au lieu de « Étude ». Tous les motifs
  // de cette plateforme sont accentués.
  const contenu = new Blob(["\uFEFF", versCsv(mouvements)], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(contenu);
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = `credits-evkha-${new Date().toISOString().slice(0, 10)}.csv`;
  lien.click();
  // Sans révocation, le contenu reste en mémoire tant que l'onglet est ouvert.
  URL.revokeObjectURL(url);
}
