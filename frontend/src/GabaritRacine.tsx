/** Racine du routeur : les deux espaces portent chacun leur propre coquille.
 *
 * Deux espaces connectés — client et administration — ont chacun la leur
 * (`espace/Coquille.tsx`, `admin/Coquille.tsx`). La page partenaires, elle,
 * est publique et porte sa propre charte (`public/Partenaires.css`) : elle
 * doit ressembler au site vitrine, pas à l'application. La racine ne fait donc
 * que rendre l'emplacement de sortie ; l'habillage appartient à chaque page.
 *
 * Le fichier reste séparé de `router.tsx` parce qu'un module qui exporte à la
 * fois un composant et autre chose casse le rafraîchissement à chaud de Vite.
 */
import { Outlet } from "@tanstack/react-router";

export function GabaritRacine() {
  return <Outlet />;
}
