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
  // Le menu replie sur mobile. Sept entrees sur deux lignes ne tiennent pas
  // sous 860 px : elles defilaient horizontalement, ce qui coupait les
  // libelles et allongeait la page. Le site en fait autant — la page doit lui
  // ressembler sur telephone comme sur ordinateur.
  const [deplie, setDeplie] = useState(false);
  const barre = useRef<HTMLElement>(null);

  // Un clic ailleurs referme, et Échap aussi : sans cela, le déroulant reste
  // ouvert par-dessus la page et masque le contenu qu'on vient chercher.
  useEffect(() => {
    if (ouvert === null && !deplie) return undefined;

    function auClic(evenement: MouseEvent) {
      if (barre.current?.contains(evenement.target as Node)) return;
      setOuvert(null);
      setDeplie(false);
    }
    function auClavier(evenement: KeyboardEvent) {
      if (evenement.key !== "Escape") return;
      setOuvert(null);
      setDeplie(false);
    }
    document.addEventListener("mousedown", auClic);
    document.addEventListener("keydown", auClavier);
    return () => {
      document.removeEventListener("mousedown", auClic);
      document.removeEventListener("keydown", auClavier);
    };
  }, [ouvert, deplie]);

  // L'appel a l'action est rendu HORS de la file qui defile : place dedans,
  // il sortait de l'ecran des que les entrees ne tenaient plus, et c'est
  // precisement le lien qu'on ne veut jamais voir disparaitre.
  const entrees = MENU_SITE.filter((e) => !e.appel);
  const appel = MENU_SITE.find((e) => e.appel);

  // L'entrée courante se DÉDUIT du chemin, elle n'est plus écrite dans les
  // données. Deux pages publiques partagent ce menu — partenaires et nos
  // études — et un drapeau figé annonçait « vous êtes ici » sur celle où
  // l'on n'était pas. Seuls les liens internes peuvent être courants : une
  // adresse du site vitrine ne désigne jamais la page affichée.
  const ici = window.location.pathname.replace(/\/+$/, "") || "/";
  const estCourante = (lien: string) =>
    lien.startsWith("/") && lien.replace(/\/+$/, "") === ici;

  return (
    <nav className="pp-menu" aria-label="Navigation du site EVKHA" ref={barre}>
      <div className="pp-menu-barre">
        <a className="pp-menu-logo" href="https://www.evkha.fr/">
          <img src={LOGO_SITE} alt="EVKHA — Business et formations" />
        </a>

        <button
          type="button"
          className="pp-menu-bouton"
          aria-expanded={deplie}
          aria-controls="menu-site-evkha"
          aria-label={deplie ? "Fermer le menu" : "Ouvrir le menu"}
          onClick={() => {
            setDeplie((etat) => !etat);
            setOuvert(null);
          }}
        >
          <span className="pp-menu-traits" aria-hidden="true" />
        </button>

        <ul
          id="menu-site-evkha"
          className={deplie ? "pp-menu-entrees deplie" : "pp-menu-entrees"}
        >
          {entrees.map((entree) => {
            if (!entree.enfants) {
              return (
                <li key={entree.lien}>
                  <a
                    href={entree.lien}
                    className={
                      estCourante(entree.lien) ? "pp-menu-courant" : undefined
                    }
                    aria-current={estCourante(entree.lien) ? "page" : undefined}
                  >
                    {entree.libelle}
                  </a>
                </li>
              );
            }

            const deplie = ouvert === entree.libelle;
            // Un déroulant est courant si l'on est sur SON lien ou sur celui
            // d'une de ses sous-entrées. Ne regarder que le lien du parent
            // laissait « Etude de marché & Livrables » non signalé sur la page
            // même où il mène — le seul cas où le repère sert vraiment.
            const courant =
              estCourante(entree.lien) ||
              entree.enfants.some((enfant) => estCourante(enfant.lien));
            return (
              <li key={entree.lien} className="pp-menu-deroulant">
                <button
                  type="button"
                  className={courant ? "pp-menu-courant" : undefined}
                  aria-current={courant ? "page" : undefined}
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
