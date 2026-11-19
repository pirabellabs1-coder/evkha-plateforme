/** L'en-tête des pages publiques refondues : le lien d'évitement, la barre
 * flottante et son méga-menu, le menu plein écran du téléphone.
 *
 * Toutes les pages refondues le montent : mêmes rubriques, même ordre, lues
 * dans UNE constante (`contenuSite.NAVIGATION`) — la barre, le menu plein
 * écran et le pied (`PiedSite`) lisent la même liste (règle 5).
 *
 * ## Le méga-menu : des boutons de divulgation, pas un « menu »
 *
 * Chaque rubrique est un `<button aria-expanded aria-controls>` suivi de son
 * panneau, dans une liste, dans un `<nav>`. Pas de `role="menu"` : ce sont des
 * liens de navigation, et ce rôle promettrait à un lecteur d'écran un clavier
 * d'application (flèches, lettres) qu'on n'attend pas d'un site.
 *
 * - Le panneau s'ouvre AU CLIC — donc à Entrée et à Espace. Avec une souris,
 *   il s'ouvre aussi au survol, après un court délai d'intention ; un clic
 *   l'épingle alors au lieu de le refermer sous le doigt.
 * - Un seul panneau à la fois. Échap le ferme et rend le focus à son bouton ;
 *   un clic hors de la barre le ferme ; suivre un lien le ferme ; le focus qui
 *   passe à une autre rubrique le ferme.
 * - Tab parcourt les liens du panneau puis passe à la rubrique suivante : le
 *   panneau est placé juste après son bouton dans le document. Les flèches
 *   gauche et droite vont d'une rubrique à l'autre.
 * - Fermé, un panneau porte `hidden` : ses liens restent dans le document
 *   (un moteur les lit) mais ne prennent ni le focus ni la voix.
 *
 * ## Ce que ce composant DÉDUIT de l'adresse
 *
 * La rubrique qui contient la page affichée porte `aria-current="true"`, et le
 * lien qui EST cette page `aria-current="page"` — dans la barre comme dans le
 * menu plein écran. Rien de cela n'est écrit dans les données : un drapeau
 * figé annoncerait « vous êtes ici » sur la mauvaise page (`site.ts`).
 *
 * ## Deux états, deux propriétaires
 *
 * L'état du menu plein écran vient de la page (`useMenu`) : c'est elle qui
 * rend inerte ce qui est derrière. Le panneau ouvert de la barre et la
 * rubrique dépliée de l'accordéon ne regardent que l'en-tête : ils vivent ici.
 */
import {
  useEffect,
  useRef,
  useState,
  type FocusEvent,
  type KeyboardEvent as ToucheReact,
  type MouseEvent,
  type PointerEvent as PointeurReact,
} from "react";

import { Bouton } from "./PiecesSite";
import {
  ACCUEIL,
  APPEL_DE_LA_BARRE,
  BARRE,
  ESPACE_CLIENT,
  EVITEMENT,
  ID_DU_CONTENU,
  NAVIGATION,
  PIED_DU_MENU,
  type Rubrique,
} from "./contenuSite";
import {
  adresseDe,
  cheminCourant,
  contientLaPage,
  estCourante,
  estLaPage,
  variables,
  type Menu,
} from "./site";

/** Le délai d'intention du survol, en millisecondes. Ce ne sont pas des
 *  durées de mouvement (celles-là sont dans `tokens.css`) : ce sont des
 *  attentes. Ouvrir sans délai ferait claquer un panneau sous une souris qui
 *  ne fait que traverser la barre ; fermer sans délai le ferait disparaître
 *  pendant qu'elle descend vers lui en diagonale. */
const ATTENTE_AVANT_D_OUVRIR = 120;
const ATTENTE_AVANT_DE_FERMER = 280;

/** Le panneau ouvert dans la barre. `epingle` : ouvert ou confirmé par un clic
 *  (ou au clavier) — la souris qui s'éloigne ne le referme pas. */
type Ouverture = { id: string; epingle: boolean } | null;

function idDuPanneau(rubrique: Rubrique): string {
  return `acc-panneau-${rubrique.id}`;
}

function idDeLAccordeon(rubrique: Rubrique): string {
  return `acc-menu-${rubrique.id}`;
}

/** Une adresse qui sort de la plateforme (Calendly) : `rel="noopener"`. */
function sort(lien: string): boolean {
  return !lien.startsWith("/") && !lien.startsWith("#");
}

/** Le libellé d'une rubrique dans la barre. Quand elle a un libellé court, la
 *  suite est dans un `<span>` que la feuille masque tant que la barre est
 *  étroite : le nom lu par un lecteur d'écran est alors celui qu'on voit. */
function LibelleDeRubrique({ rubrique }: { rubrique: Rubrique }) {
  const { libelle, court } = rubrique;
  if (!court || !libelle.startsWith(court)) return <>{libelle}</>;
  return (
    <>
      {court}
      <span className="acc-rubrique-suite">{libelle.slice(court.length)}</span>
    </>
  );
}

export function EnTeteSite({ menu }: { menu: Menu }) {
  const { ouvert, basculer, fermer, fermerSurUnLien } = menu;
  const hamburger = useRef<HTMLButtonElement>(null);
  const barre = useRef<HTMLElement>(null);
  const attente = useRef(0);

  const [ouverture, setOuverture] = useState<Ouverture>(null);
  const [deplie, setDeplie] = useState<string | null>(null);
  const panneauOuvert = ouverture?.id ?? null;

  // Échap referme le menu plein écran et rend le focus au bouton qui l'a
  // ouvert : sans cela, le focus resterait sur un lien devenu invisible.
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

  // Tant qu'un panneau de la barre est ouvert : Échap le ferme et rend le
  // focus à son bouton ; un appui hors de la barre le ferme ; passer sous
  // 1001 px le ferme aussi — la barre laisse alors la place au menu plein
  // écran, et le panneau ne doit pas se rouvrir tout seul au retour.
  useEffect(() => {
    if (panneauOuvert === null) return undefined;
    const rubrique = panneauOuvert;
    function refermer() {
      window.clearTimeout(attente.current);
      setOuverture(null);
    }
    function auClavier(evenement: KeyboardEvent) {
      if (evenement.key !== "Escape") return;
      refermer();
      barre.current
        ?.querySelector<HTMLButtonElement>(`button[data-rubrique="${rubrique}"]`)
        ?.focus();
    }
    function aLAppui(evenement: Event) {
      const cible = evenement.target;
      if (cible instanceof Node && barre.current?.contains(cible)) return;
      refermer();
    }
    const petitEcran =
      typeof window.matchMedia === "function"
        ? window.matchMedia("(max-width: 1000px)")
        : null;
    window.addEventListener("keydown", auClavier);
    document.addEventListener("pointerdown", aLAppui);
    petitEcran?.addEventListener("change", refermer);
    return () => {
      window.removeEventListener("keydown", auClavier);
      document.removeEventListener("pointerdown", aLAppui);
      petitEcran?.removeEventListener("change", refermer);
    };
  }, [panneauOuvert]);

  // Une attente de survol ne survit pas à l'en-tête.
  useEffect(() => () => window.clearTimeout(attente.current), []);

  /** Clic, Entrée ou Espace sur une rubrique. Un panneau ouvert par le survol
   *  est ÉPINGLÉ par le clic, pas refermé : la souris est arrivée la première,
   *  et le visiteur qui clique verrait sinon le panneau lui claquer au nez. */
  function basculerLePanneau(id: string) {
    window.clearTimeout(attente.current);
    setOuverture((courante) =>
      courante?.id === id && courante.epingle ? null : { id, epingle: true },
    );
  }

  function auSurvol(id: string, evenement: PointeurReact<HTMLLIElement>) {
    if (evenement.pointerType !== "mouse") return;
    window.clearTimeout(attente.current);
    attente.current = window.setTimeout(() => {
      setOuverture((courante) =>
        courante?.id === id ? courante : { id, epingle: false },
      );
    }, ATTENTE_AVANT_D_OUVRIR);
  }

  function auDepartDeLaSouris(id: string, evenement: PointeurReact<HTMLLIElement>) {
    if (evenement.pointerType !== "mouse") return;
    window.clearTimeout(attente.current);
    attente.current = window.setTimeout(() => {
      setOuverture((courante) =>
        courante?.id === id && !courante.epingle ? null : courante,
      );
    }, ATTENTE_AVANT_DE_FERMER);
  }

  /** Le focus quitte la rubrique pour un autre élément (Tab après le dernier
   *  lien, flèche vers la rubrique voisine) : son panneau se ferme. Un focus
   *  qui ne va nulle part — clic sur une zone sans lien DU panneau, fenêtre
   *  qui perd la main — ne ferme rien : c'est l'appui hors de la barre qui
   *  s'en charge. */
  function auDepartDuFocus(id: string, evenement: FocusEvent<HTMLLIElement>) {
    const vers = evenement.relatedTarget;
    if (!(vers instanceof Node) || evenement.currentTarget.contains(vers)) return;
    setOuverture((courante) => (courante?.id === id ? null : courante));
  }

  /** Flèches gauche et droite : d'une rubrique à l'autre, en boucle. */
  function auClavierDUneRubrique(evenement: ToucheReact<HTMLButtonElement>) {
    if (evenement.key !== "ArrowRight" && evenement.key !== "ArrowLeft") return;
    const boutons = Array.from(
      barre.current?.querySelectorAll<HTMLButtonElement>("button[data-rubrique]") ??
        [],
    );
    const rang = boutons.indexOf(evenement.currentTarget);
    if (rang === -1) return;
    const pas = evenement.key === "ArrowRight" ? 1 : -1;
    evenement.preventDefault();
    boutons[(rang + pas + boutons.length) % boutons.length].focus();
  }

  /** Suivre un lien de la barre referme le panneau : sur la page des études,
   *  « Comment ça marche » fait défiler la page, et elle défilerait DERRIÈRE
   *  le panneau resté ouvert. */
  function auClicDansLaBarre(evenement: MouseEvent<HTMLElement>) {
    if (!(evenement.target as Element).closest("a")) return;
    window.clearTimeout(attente.current);
    setOuverture(null);
  }

  /** Le menu plein écran s'ouvre toujours replié. */
  function basculerLeMenu() {
    setDeplie(null);
    basculer();
  }

  const ici = cheminCourant();
  const rubriques = NAVIGATION.map((rubrique) => ({
    rubrique,
    courante: contientLaPage(rubrique, ici) ? ("true" as const) : undefined,
  }));
  const pageSi = (lien: string) =>
    estLaPage(lien, ici) ? ("page" as const) : undefined;

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
          <nav
            ref={barre}
            className="acc-barre-liens"
            aria-label={BARRE.nomDeLaBarre}
            onClick={auClicDansLaBarre}
          >
            <ul className="acc-rubriques">
              {rubriques.map(({ rubrique, courante }) => {
                const montre = panneauOuvert === rubrique.id;
                return (
                  <li
                    key={rubrique.id}
                    onPointerEnter={(e) => auSurvol(rubrique.id, e)}
                    onPointerLeave={(e) => auDepartDeLaSouris(rubrique.id, e)}
                    onBlur={(e) => auDepartDuFocus(rubrique.id, e)}
                  >
                    <button
                      type="button"
                      className="acc-rubrique"
                      data-rubrique={rubrique.id}
                      aria-expanded={montre}
                      aria-controls={idDuPanneau(rubrique)}
                      aria-current={courante}
                      onClick={() => basculerLePanneau(rubrique.id)}
                      onKeyDown={auClavierDUneRubrique}
                    >
                      <LibelleDeRubrique rubrique={rubrique} />
                      <span className="acc-rubrique-chevron" aria-hidden="true" />
                    </button>

                    {/* Le cadre extérieur est transparent : il couvre
                        l'intervalle entre la barre et le bloc blanc, pour que
                        la souris qui descend ne « sorte » pas du menu. */}
                    <div
                      id={idDuPanneau(rubrique)}
                      className="acc-panneau"
                      hidden={!montre}
                    >
                      <div className="acc-panneau-bloc">
                        <ul className="acc-panneau-liens">
                          {rubrique.liens.map((lien) => (
                            <li key={lien.lien}>
                              <a
                                className="acc-panneau-lien"
                                href={lien.lien}
                                rel={sort(lien.lien) ? "noopener" : undefined}
                                aria-current={pageSi(lien.lien)}
                              >
                                <span className="acc-panneau-titre">
                                  {lien.libelle}
                                </span>
                                <span className="acc-panneau-description">
                                  {lien.description}
                                </span>
                              </a>
                            </li>
                          ))}
                        </ul>
                        <div className="acc-panneau-avant">
                          <p className="acc-panneau-avant-titre">
                            {rubrique.enAvant.titre}
                          </p>
                          <p className="acc-panneau-avant-corps">
                            {rubrique.enAvant.corps}
                          </p>
                          {/* Le bouton-pilule de `PiecesSite`, écrit à la
                              main : `Bouton` ne sait pas porter
                              `aria-current`, et ce fichier n'est pas à
                              modifier ici. */}
                          <a
                            className="acc-btn acc-btn-noir"
                            href={rubrique.enAvant.lien}
                            rel={sort(rubrique.enAvant.lien) ? "noopener" : undefined}
                            aria-current={pageSi(rubrique.enAvant.lien)}
                          >
                            {rubrique.enAvant.bouton}
                            <span className="acc-btn-fleche" aria-hidden="true">
                              →
                            </span>
                          </a>
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })}
              <li>
                <a
                  className="acc-compte"
                  href={adresseDe(ESPACE_CLIENT, ici)}
                  aria-current={estCourante(ESPACE_CLIENT, ici) ? "page" : undefined}
                >
                  {ESPACE_CLIENT.libelle}
                </a>
              </li>
            </ul>
          </nav>
          <button
            ref={hamburger}
            className="acc-hamburger"
            type="button"
            aria-expanded={ouvert}
            aria-controls="acc-menu"
            aria-label={ouvert ? BARRE.fermerLeMenu : BARRE.ouvrirLeMenu}
            onClick={basculerLeMenu}
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

      {/* Le menu plein écran lit la MÊME liste que la barre, en accordéon :
          une rubrique dépliée à la fois. Fermé, il est `visibility: hidden` :
          ni ses boutons ni ses liens ne prennent le focus. */}
      <nav
        id="acc-menu"
        className={ouvert ? "acc-menu acc-menu-ouvert" : "acc-menu"}
        aria-label={BARRE.nomDuMenu}
        onClick={fermerSurUnLien}
      >
        <ul className="acc-menu-rubriques">
          {rubriques.map(({ rubrique, courante }, k) => {
            const montre = ouvert && deplie === rubrique.id;
            return (
              <li key={rubrique.id} style={variables({ "--i": k })}>
                <button
                  type="button"
                  className="acc-menu-rubrique"
                  aria-expanded={montre}
                  aria-controls={idDeLAccordeon(rubrique)}
                  aria-current={courante}
                  onClick={() => setDeplie(montre ? null : rubrique.id)}
                >
                  <span className="acc-menu-masque">
                    <span>{rubrique.libelle}</span>
                  </span>
                  <span className="acc-menu-signe" aria-hidden="true" />
                </button>
                <ul
                  id={idDeLAccordeon(rubrique)}
                  className="acc-menu-liens"
                  hidden={!montre}
                >
                  {rubrique.liens.map((lien) => (
                    <li key={lien.lien}>
                      <a
                        className="acc-menu-lien"
                        href={lien.lien}
                        rel={sort(lien.lien) ? "noopener" : undefined}
                        aria-current={pageSi(lien.lien)}
                      >
                        <span className="acc-menu-lien-titre">{lien.libelle}</span>
                        <span className="acc-menu-lien-description">
                          {lien.description}
                        </span>
                      </a>
                    </li>
                  ))}
                  {/* La carte de mise en avant du panneau, ramenée à son
                      lien : le bouton d'abord, le message en dessous. */}
                  <li>
                    <a
                      className="acc-menu-lien acc-menu-lien-avant"
                      href={rubrique.enAvant.lien}
                      rel={sort(rubrique.enAvant.lien) ? "noopener" : undefined}
                      aria-current={pageSi(rubrique.enAvant.lien)}
                    >
                      <span className="acc-menu-lien-titre">
                        {rubrique.enAvant.bouton}
                        <span aria-hidden="true">{"\u00a0"}→</span>
                      </span>
                      <span className="acc-menu-lien-description">
                        {rubrique.enAvant.titre}
                      </span>
                    </a>
                  </li>
                </ul>
              </li>
            );
          })}
        </ul>
        <div className="acc-menu-pied">
          {PIED_DU_MENU.map((entree) => (
            <a
              key={entree.libelle}
              className="acc-menu-acces"
              href={adresseDe(entree, ici)}
              aria-current={estCourante(entree, ici) ? "page" : undefined}
            >
              {entree.libelle}
            </a>
          ))}
        </div>
      </nav>
    </>
  );
}
