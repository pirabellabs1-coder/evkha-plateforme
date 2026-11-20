/** L'emplacement d'actions de l'en-tête de page, et ce qui le remplit.
 *
 * L'en-tête est rendu par la coquille (`Coquille.tsx`) : fil d'Ariane, titre,
 * phrase d'aide — et, à droite, une place pour les gestes de l'écran courant
 * (une période à choisir, « Rédiger une annonce », « Ajouter une étude »).
 * L'écran ne rend pas l'en-tête ; il y DÉPOSE ses actions :
 *
 *     <ActionsDePage>
 *       <button type="button" className="bouton bouton-principal">Ajouter</button>
 *     </ActionsDePage>
 *
 * Un portail, pas un contexte de valeurs : l'écran garde la main sur ses
 * boutons (leur état, leurs gestionnaires, leur `disabled`), et React les
 * dessine simplement ailleurs. Rien n'est copié, rien n'est à resynchroniser.
 *
 * Sans coquille autour — un écran rendu seul dans un test, ou réutilisé hors
 * de l'administration —, les actions s'affichent SUR PLACE, alignées à droite.
 * Les faire disparaître faute d'emplacement cacherait le geste principal de
 * l'écran sans que rien ne le dise (règle 1).
 */
import { type ReactNode, useContext } from "react";
import { createPortal } from "react-dom";

import { EmplacementDesActions } from "./emplacement";

export function ActionsDePage({ children }: { children: ReactNode }) {
  const emplacement = useContext(EmplacementDesActions);
  // Hors de la coquille : sur place.
  if (emplacement === undefined) {
    return <div className="console-actions-sur-place">{children}</div>;
  }
  // Dans la coquille, en-tête pas encore monté : on attend (un seul rendu,
  // rejoué avant que le navigateur ne peigne).
  if (emplacement === null) return null;
  return createPortal(children, emplacement);
}
