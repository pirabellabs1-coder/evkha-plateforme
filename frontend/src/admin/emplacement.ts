/** Le nœud de l'en-tête où les écrans déposent leurs actions.
 *
 * La coquille le fournit (`Coquille.tsx`), `ActionsDePage` le lit. Trois
 * valeurs, et la différence entre les deux dernières compte :
 *
 * - un élément : l'emplacement est prêt, les actions y sont dessinées ;
 * - `null` : on est DANS la coquille, mais l'en-tête n'est pas encore monté
 *   (le tout premier rendu). Les actions attendent — les afficher sur place
 *   un instant, puis les déplacer, ferait sauter la page ;
 * - `undefined` : aucune coquille autour (un écran rendu seul). Les actions
 *   s'affichent sur place.
 *
 * Dans son propre fichier, sans composant : un module qui exporte à la fois un
 * contexte et un composant ne se recharge pas à chaud proprement
 * (`react-refresh/only-export-components`).
 */
import { createContext } from "react";

export const EmplacementDesActions = createContext<HTMLElement | null | undefined>(undefined);
