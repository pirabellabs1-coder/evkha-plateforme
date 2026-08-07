/** Le menu du site vitrine, reproduit sur nos pages publiques.
 *
 * Cette page a remplacé `evkha.fr/partenairespro` DANS le tunnel de vente : le
 * visiteur qui cliquait arrivait sur un autre site, sans aucune navigation, au
 * milieu d'un parcours d'achat.
 *
 * Les entrées viennent de `contenu.MENU_SITE` — seul endroit du dépôt où ce
 * menu est écrit. Ce fichier ne décide de rien : il met en forme.
 *
 * **Le déroulant s'ouvre au clic, pas au survol.** Un menu qui ne se déplie
 * qu'au survol n'existe pas sur un téléphone, où il n'y a pas de survol : ses
 * deux sous-entrées seraient inatteignables pour la moitié des visiteurs. Au
 * clic, il fonctionne partout, et l'état est annoncé aux lecteurs d'écran.
 */
import { useEffect, useRef, useState } from "react";

import { LOGO_SITE, MENU_SITE } from "./contenu";

export function MenuSite() {
  const [ouvert, setOuvert] = useState<string | null>(null);
  const barre = useRef<HTMLElement>(null);

  // Un clic ailleurs referme, et Échap aussi : sans cela, le déroulant reste
  // ouvert par-dessus la page et masque le contenu qu'on vient chercher.
  useEffect(() => {
    if (ouvert === null) return undefined;

    function auClic(evenement: MouseEvent) {
      if (!barre.current?.contains(evenement.target as Node)) setOuvert(null);
    }
    function auClavier(evenement: KeyboardEvent) {
      if (evenement.key === "Escape") setOuvert(null);
    }
    document.addEventListener("mousedown", auClic);
    document.addEventListener("keydown", auClavier);
    return () => {
      document.removeEventListener("mousedown", auClic);
      document.removeEventListener("keydown", auClavier);
    };
  }, [ouvert]);

  // L'appel a l'action est rendu HORS de la file qui defile : place dedans,
  // il sortait de l'ecran des que les entrees ne tenaient plus, et c'est
  // precisement le lien qu'on ne veut jamais voir disparaitre.
  const entrees = MENU_SITE.filter((e) => !e.appel);
  const appel = MENU_SITE.find((e) => e.appel);

  return (
    <nav className="pp-menu" aria-label="Navigation du site EVKHA" ref={barre}>
      <div className="pp-menu-barre">
        <a className="pp-menu-logo" href="https://www.evkha.fr/">
          <img src={LOGO_SITE} alt="EVKHA — Business et formations" />
        </a>

        <ul className="pp-menu-entrees">
          {entrees.map((entree) => {
            if (!entree.enfants) {
              return (
                <li key={entree.lien}>
                  <a
                    href={entree.lien}
                    className={entree.courant ? "pp-menu-courant" : undefined}
                    aria-current={entree.courant ? "page" : undefined}
                  >
                    {entree.libelle}
                  </a>
                </li>
              );
            }

            const deplie = ouvert === entree.libelle;
            return (
              <li key={entree.lien} className="pp-menu-deroulant">
                <button
                  type="button"
                  aria-expanded={deplie}
                  onClick={() => setOuvert(deplie ? null : entree.libelle)}
                >
                  {entree.libelle}
                  <span className="pp-menu-chevron" aria-hidden="true" />
                </button>
                {deplie && (
                  <ul>
                    {entree.enfants.map((enfant) => (
                      <li key={enfant.lien}>
                        <a href={enfant.lien}>{enfant.libelle}</a>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>

        {appel && (
          <a className="pp-menu-appel" href={appel.lien}>
            {appel.libelle}
          </a>
        )}
      </div>
    </nav>
  );
}
