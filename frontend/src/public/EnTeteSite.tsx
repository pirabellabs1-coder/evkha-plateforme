/** L'en-tête des pages publiques refondues : le lien d'évitement, la barre
 * flottante et le menu plein écran du téléphone.
 *
 * Il vivait dans `Accueil.tsx`. L'accueil et la page des études le montent
 * tous deux : mêmes entrées, même ordre, lus dans UNE constante
 * (`contenuSite.NAVIGATION`) — la barre et le menu lisent la même liste, et
 * les deux pages le même composant (règle 5).
 *
 * ## Ce que ce composant DÉDUIT de l'adresse
 *
 * - **L'entrée courante.** Celle dont le chemin est celui de la page affichée
 *   porte `aria-current="page"`, dans la barre comme dans le menu. Elle n'est
 *   écrite nulle part : un drapeau figé dans les données annonçait « vous êtes
 *   ici » sur la mauvaise page (voir `MenuSite`, qui fait de même pour les
 *   anciennes pages).
 * - **Où mènent les ancres.** « La méthode » et « Me contacter » sont des
 *   sections de l'accueil. Sur l'accueil, ce sont des ancres ; ailleurs, des
 *   liens vers l'accueil, à cette section (`site.adresseDe`).
 *
 * L'état du menu vient de la page (`useMenu`) : c'est elle qui rend inerte ce
 * qui est derrière le menu ouvert. Le bouton du menu, lui, est d'ici : Échap
 * referme le menu et lui rend le focus.
 */
import { useEffect, useRef } from "react";

import { Bouton } from "./PiecesSite";
import {
  ACCUEIL,
  APPEL_DE_LA_BARRE,
  BARRE,
  EVITEMENT,
  ID_DU_CONTENU,
  NAVIGATION,
} from "./contenuSite";
import {
  adresseDe,
  cheminCourant,
  estCourante,
  variables,
  type Menu,
} from "./site";

export function EnTeteSite({ menu }: { menu: Menu }) {
  const { ouvert, basculer, fermer, fermerSurUnLien } = menu;
  const hamburger = useRef<HTMLButtonElement>(null);

  // Échap referme le menu et rend le focus au bouton qui l'a ouvert : sans
  // cela, le focus resterait sur un lien devenu invisible.
  useEffect(() => {
    if (!ouvert) return undefined;
    function auClavier(evenement: KeyboardEvent) {
      if (evenement.key !== "Escape") return;
      fermer();
      hamburger.current?.focus();
    }
    window.addEventListener("keydown", auClavier);
    return () => window.removeEventListener("keydown", auClavier);
  }, [ouvert, fermer]);

  const ici = cheminCourant();
  const entrees = NAVIGATION.map((entree) => ({
    entree,
    adresse: adresseDe(entree, ici),
    courante: estCourante(entree, ici) ? ("page" as const) : undefined,
  }));

  return (
    <>
      <a className="acc-saut" href={`#${ID_DU_CONTENU}`}>
        {EVITEMENT}
      </a>

      <header className="acc-entete" onClick={fermerSurUnLien}>
        <div className="acc-w acc-barre">
          <a className="acc-logo" href={ACCUEIL} aria-label={BARRE.nomDuLogo}>
            {BARRE.logo}
            <span className="acc-logo-etoile" aria-hidden="true" />
          </a>
          <nav className="acc-barre-liens" aria-label={BARRE.nomDeLaBarre}>
            {entrees.map(({ entree, adresse, courante }) => (
              <a
                key={entree.libelle}
                href={adresse}
                className={entree.compte ? "acc-compte" : undefined}
                aria-current={courante}
              >
                {entree.libelle}
              </a>
            ))}
          </nav>
          <button
            ref={hamburger}
            className="acc-hamburger"
            type="button"
            aria-expanded={ouvert}
            aria-controls="acc-menu"
            aria-label={ouvert ? BARRE.fermerLeMenu : BARRE.ouvrirLeMenu}
            onClick={basculer}
          >
            <span aria-hidden="true" />
            <span aria-hidden="true" />
          </button>
          <Bouton
            lien={adresseDe(APPEL_DE_LA_BARRE, ici)}
            aspect="noir"
            className="acc-barre-appel"
          >
            {APPEL_DE_LA_BARRE.libelle}
          </Bouton>
        </div>
      </header>

      {/* Le menu plein écran lit la MÊME liste que la barre. Fermé, il est
          `visibility: hidden` : ses liens ne prennent pas le focus. */}
      <nav
        id="acc-menu"
        className={ouvert ? "acc-menu acc-menu-ouvert" : "acc-menu"}
        aria-label={BARRE.nomDuMenu}
        onClick={fermerSurUnLien}
      >
        {entrees.map(({ entree, adresse, courante }, k) => (
          <a
            key={entree.libelle}
            href={adresse}
            style={variables({ "--i": k })}
            aria-current={courante}
          >
            <span>{entree.libelle}</span>
          </a>
        ))}
      </nav>
    </>
  );
}
