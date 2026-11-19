/** Les petites pièces que les pages publiques refondues partagent : le
 * bouton-pilule et le bouton de pause.
 *
 * Elles vivaient dans `Accueil.tsx` ; la page des études les réutilise au lieu
 * de les recopier (règle 5). Leur habillage est dans `Site.css`.
 *
 * Aucune pièce d'ici ne pose l'attribut de révélation : un bloc à révéler
 * naît effacé, et c'est le fichier qui le pose qui doit appeler le crochet
 * de `reveler.ts` — `la-revelation-n-oublie-aucun-bloc` le verrouille fichier
 * par fichier. L'introduction d'une section, qui est révélée, reste donc dans
 * chaque page ; seul son habillage (`.acc-intro`) est commun.
 */
import type { ReactNode } from "react";

import { PAUSE } from "./contenuSite";

export type Aspect = "noir" | "or" | "clair";

/** Le bouton-pilule de la maquette, avec sa flèche dans un disque. La flèche
 *  est décorative : le libellé dit déjà où l'on va.
 *
 *  `inactif` : l'offre n'est pas au catalogue. Le bouton reste à sa place
 *  (la carte ne change pas de forme) mais ce n'est plus un lien : il ne
 *  prend ni le clic ni le focus, et il se dit indisponible. */
export function Bouton({
  lien,
  aspect,
  inactif = false,
  externe = false,
  className = "",
  children,
}: {
  lien: string;
  aspect: Aspect;
  inactif?: boolean;
  /** Un lien qui sort de la plateforme vers un site tiers. */
  externe?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const classes = `acc-btn acc-btn-${aspect} ${className}`.trim();
  if (inactif) {
    return (
      <span className={`${classes} acc-btn-inactif`} aria-disabled="true">
        {children}
        <span className="acc-btn-fleche" aria-hidden="true">
          →
        </span>
      </span>
    );
  }
  return (
    <a className={classes} href={lien} rel={externe ? "noopener" : undefined}>
      {children}
      <span className="acc-btn-fleche" aria-hidden="true">
        →
      </span>
    </a>
  );
}

/** Le bouton de pause. Plusieurs exemplaires possibles sur une page, un seul
 *  état : chacun arrête et relance TOUT ce qui boucle. */
export function BoutonPause({
  fige,
  basculer,
  className = "",
}: {
  fige: boolean;
  basculer: () => void;
  className?: string;
}) {
  return (
    <button
      className={`acc-pause ${className}`.trim()}
      type="button"
      aria-pressed={fige}
      onClick={basculer}
    >
      {fige ? PAUSE.relancer : PAUSE.arreter}
    </button>
  );
}
