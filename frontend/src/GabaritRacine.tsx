/** Racine du routeur : les deux espaces portent chacun leur propre coquille.
 *
 * Il n'y a que **deux** espaces — client et administration — et chacun a la
 * sienne (`espace/Coquille.tsx`, `admin/Coquille.tsx`). La racine ne fait donc
 * que rendre l'emplacement de sortie ; c'est la coquille de l'espace concerné
 * qui habille la page.
 *
 * Le fichier reste séparé de `router.tsx` parce qu'un module qui exporte à la
 * fois un composant et autre chose casse le rafraîchissement à chaud de Vite.
 */
import { Outlet } from "@tanstack/react-router";

export function GabaritRacine() {
  return <Outlet />;
}
