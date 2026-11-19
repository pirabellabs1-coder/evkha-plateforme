/** Les crochets et les calculs que les pages publiques refondues partagent.
 *
 * Tout ce qui suit vivait dans `Accueil.tsx`. La page des études s'en sert à
 * son tour : plutôt que de le recopier, les deux pages l'importent d'ici
 * (règle 5). Chaque crochet défait ce qu'il a branché.
 *
 * Pas de composant dans ce fichier — ils sont dans `PiecesSite.tsx`,
 * `EnTeteSite.tsx` et `PiedSite.tsx` — pour que le rechargement à chaud de
 * Vite garde l'état des pages.
 */
import {
  useCallback,
  useEffect,
  useState,
  useSyncExternalStore,
  type CSSProperties,
  type MouseEvent,
  type RefObject,
} from "react";

import {
  ACCUEIL,
  type EntreeDeNavigation,
  type Rubrique,
} from "./contenuSite";

// ── Chargement d'un catalogue ───────────────────────────────────────────────

/** L'état d'un appel. Trois cas distincts, jamais une liste vide par défaut :
 *  c'est elle qui fait passer une panne pour « rien à vendre ». */
export type Chargement<T> =
  | { etat: "attente" }
  | { etat: "recu"; donnees: T }
  | { etat: "panne" };

/** `charger` doit être une fonction stable (définie hors du composant) :
 *  elle est la dépendance de l'effet. */
export function useChargement<T>(charger: () => Promise<T>): Chargement<T> {
  const [chargement, setChargement] = useState<Chargement<T>>({
    etat: "attente",
  });

  useEffect(() => {
    let vivant = true;
    charger()
      .then((donnees) => {
        if (vivant) setChargement({ etat: "recu", donnees });
      })
      .catch(() => {
        if (vivant) setChargement({ etat: "panne" });
      });
    return () => {
      vivant = false;
    };
  }, [charger]);

  return chargement;
}

// ── Les prix, calculés sur ce que l'API rend ────────────────────────────────

/** Ce qu'un emplacement de prix affiche : un montant connu, ou la raison pour
 *  laquelle il n'y en a pas. */
export type Tarif =
  | { etat: "connu"; texte: string }
  | { etat: "attente" | "panne" | "absent" };

/** Un montant qu'on peut afficher : un nombre fini et STRICTEMENT positif.
 *  Une offre créée à zéro (brouillon, erreur de saisie) n'a pas de prix : la
 *  laisser passer écrirait « dès 0 € par mois » sur une page de vente. */
export function lisible(cents: unknown): cents is number {
  return typeof cents === "number" && Number.isFinite(cents) && cents > 0;
}

/** Le plus petit et le plus grand montant d'une liste, ou `null` si elle ne
 *  porte aucun montant lisible. `Math.min()` d'une liste vide vaut l'infini :
 *  formaté, il s'afficherait « ∞ € ». */
export function bornes(cents: unknown[]): { bas: number; haut: number } | null {
  const lisibles = cents.filter(lisible);
  if (lisibles.length === 0) return null;
  return { bas: Math.min(...lisibles), haut: Math.max(...lisibles) };
}

export function tarifDe<T>(
  chargement: Chargement<T>,
  calcul: (donnees: T) => string | null,
): Tarif {
  if (chargement.etat !== "recu") return { etat: chargement.etat };
  const texte = calcul(chargement.donnees);
  return texte === null ? { etat: "absent" } : { etat: "connu", texte };
}

// ── Petits outils ───────────────────────────────────────────────────────────

/** Propriétés personnalisées posées en ligne (`--i`, `--n`…) : React les
 *  accepte, son type `CSSProperties` ne les connaît pas. */
export function variables(valeurs: Record<string, string | number>): CSSProperties {
  return valeurs as CSSProperties;
}

/** Le visiteur a-t-il demandé moins de mouvement ? Lu au moment de brancher
 *  un effet, pas au rendu : jsdom n'a pas de `matchMedia`. */
export function mouvementReduit(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/** Une requête de média, suivie en direct. Sans `matchMedia` : faux. */
export function useMedia(requete: string): boolean {
  const abonner = useCallback(
    (rappel: () => void) => {
      if (typeof window.matchMedia !== "function") return () => undefined;
      const media = window.matchMedia(requete);
      media.addEventListener("change", rappel);
      return () => media.removeEventListener("change", rappel);
    },
    [requete],
  );
  return useSyncExternalStore(
    abonner,
    () =>
      typeof window.matchMedia === "function" &&
      window.matchMedia(requete).matches,
    () => false,
  );
}

// ── Navigation : où l'on est, où mène une entrée ────────────────────────────

/** Le chemin de la page affichée, sans barre oblique finale (`/etudes/` et
 *  `/etudes` sont la même page). */
export function cheminCourant(): string {
  return window.location.pathname.replace(/\/+$/, "") || ACCUEIL;
}

/** L'adresse d'une entrée de navigation, vue depuis la page `ici`.
 *
 *  Une entrée `ancre` désigne une section de l'ACCUEIL : sur l'accueil elle
 *  reste une ancre, et la page défile ; ailleurs elle mène à l'accueil, à
 *  cette section. Écrire `#contact` en dur sur une page qui n'a pas de section
 *  « contact » ferait un lien qui ne mène nulle part. */
export function adresseDe(entree: EntreeDeNavigation, ici: string): string {
  if (entree.lien !== undefined) return entree.lien;
  return ici === ACCUEIL ? `#${entree.ancre}` : `${ACCUEIL}#${entree.ancre}`;
}

/** L'entrée est-elle la page affichée ? Seul un lien interne peut l'être : une
 *  ancre désigne une section, une adresse externe un autre site. */
export function estCourante(entree: EntreeDeNavigation, ici: string): boolean {
  return entree.lien !== undefined && estLaPage(entree.lien, ici);
}

/** Cette adresse est-elle EXACTEMENT la page affichée ? Une adresse qui porte
 *  une ancre (`/etudes#comment-ca-marche`) désigne une section : elle n'est
 *  pas « la page », sinon les six liens d'un même panneau se diraient tous
 *  courants à la fois. */
export function estLaPage(lien: string, ici: string): boolean {
  return lien.startsWith("/") && (lien.replace(/\/+$/, "") || ACCUEIL) === ici;
}

/** Le chemin d'une adresse INTERNE, sans ancre ni barre oblique finale ;
 *  `null` pour une adresse externe (Calendly, un réseau). */
export function cheminDe(lien: string): string | null {
  if (!lien.startsWith("/")) return null;
  return lien.split("#")[0].replace(/\/+$/, "") || ACCUEIL;
}

/** La page affichée est-elle dans cette rubrique du menu ? Vrai quand l'un de
 *  ses liens — carte de mise en avant comprise — mène à cette page, à l'une de
 *  ses sections, ou à une page au-dessus d'elle (`/boutique` pour
 *  `/boutique/une-etude`). Déduit du chemin, jamais écrit dans les données.
 *
 *  La comparaison se fait segment par segment : `/etudes-de-cas` n'est pas
 *  sous `/etudes`. L'accueil n'est « au-dessus » de rien, sinon toute page
 *  serait dans la rubrique qui y mène. */
export function contientLaPage(rubrique: Rubrique, ici: string): boolean {
  return [...rubrique.liens, rubrique.enAvant].some(({ lien }) => {
    const chemin = cheminDe(lien);
    if (chemin === null) return false;
    if (chemin === ici) return true;
    return chemin !== ACCUEIL && ici.startsWith(`${chemin}/`);
  });
}

// ── Le titre de l'onglet et la description ──────────────────────────────────

/** Le gabarit HTML annonce « EVKHA — Espace client » et sa description parle
 *  de l'espace connecté : justes pour lui, faux pour une page publique que
 *  l'on partage par lien et que les moteurs indexent. Les deux sont rendus en
 *  partant. */
export function useTitreDePage(titre: string, description: string): void {
  useEffect(() => {
    const titreDAvant = document.title;
    const balise = document.querySelector<HTMLMetaElement>(
      'meta[name="description"]',
    );
    const descriptionDAvant = balise?.content;
    document.title = titre;
    if (balise) balise.content = description;
    return () => {
      document.title = titreDAvant;
      if (balise && descriptionDAvant !== undefined) {
        balise.content = descriptionDAvant;
      }
    };
  }, [titre, description]);
}

// ── Le menu plein écran ─────────────────────────────────────────────────────

/** L'état du menu, partagé entre la page et `EnTeteSite` : la page en a besoin
 *  pour rendre inerte ce qui est derrière le menu ouvert.
 *
 *  Que des valeurs et des fonctions, pas de référence à un élément : le
 *  bouton du menu appartient à `EnTeteSite`, qui lui rend le focus à la
 *  fermeture par Échap. */
export type Menu = {
  ouvert: boolean;
  basculer: () => void;
  fermer: () => void;
  /** Un clic sur un lien — de la barre comme du menu — referme le menu : sans
   *  cela, « Me contacter » faisait défiler la page DERRIÈRE le menu resté
   *  ouvert, et le visiteur ne voyait rien bouger. */
  fermerSurUnLien: (evenement: MouseEvent<HTMLElement>) => void;
};

/** Menu plein écran : la page derrière ne défile plus, et repasser en grand
 *  écran le referme — la barre montre alors les mêmes rubriques. Échap referme
 *  aussi : c'est `EnTeteSite` qui l'écoute, pour rendre le focus à son
 *  bouton. */
export function useMenu(): Menu {
  const [ouvert, setOuvert] = useState(false);
  const fermer = useCallback(() => setOuvert(false), []);

  useEffect(() => {
    if (!ouvert) return undefined;
    const racine = document.documentElement;
    const debordement = racine.style.overflow;
    racine.style.overflow = "hidden";

    const grandEcran =
      typeof window.matchMedia === "function"
        ? window.matchMedia("(min-width: 1001px)")
        : null;
    grandEcran?.addEventListener("change", fermer);
    return () => {
      racine.style.overflow = debordement;
      grandEcran?.removeEventListener("change", fermer);
    };
  }, [ouvert, fermer]);

  const basculer = useCallback(() => setOuvert((etat) => !etat), []);
  const fermerSurUnLien = useCallback(
    (evenement: MouseEvent<HTMLElement>) => {
      if ((evenement.target as Element).closest("a")) setOuvert(false);
    },
    [],
  );

  return { ouvert, basculer, fermer, fermerSurUnLien };
}

// ── La pause ────────────────────────────────────────────────────────────────

/** L'état des boutons de pause d'une page : un seul, quel que soit le nombre
 *  de boutons. La page pose `acc-fige` sur sa racine quand il est vrai, et la
 *  feuille arrête alors tout ce qui boucle (WCAG 2.2.2). */
export function usePause(): { fige: boolean; basculer: () => void } {
  const [fige, setFige] = useState(false);
  const basculer = useCallback(() => setFige((etat) => !etat), []);
  return { fige, basculer };
}

// ── Boutons aimantés ────────────────────────────────────────────────────────

/** Boutons aimantés : seulement avec une vraie souris, jamais sous mouvement
 *  réduit. Un seul écouteur sur la page (délégation) plutôt qu'un par bouton :
 *  les boutons montés après coup restent couverts. */
export function useAimants(page: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const racine = page.current;
    if (!racine || mouvementReduit()) return undefined;
    if (
      typeof window.matchMedia !== "function" ||
      !window.matchMedia("(hover: hover) and (pointer: fine)").matches
    ) {
      return undefined;
    }

    let aimante: HTMLElement | null = null;
    function relacher() {
      if (aimante) aimante.style.translate = "";
      aimante = null;
    }
    function auDeplacement(evenement: PointerEvent) {
      const cible =
        evenement.target instanceof Element
          ? evenement.target.closest<HTMLElement>("a.acc-btn")
          : null;
      if (cible !== aimante) relacher();
      if (!cible) return;
      aimante = cible;
      const r = cible.getBoundingClientRect();
      const x = (evenement.clientX - r.left - r.width / 2) * 0.16;
      const y = (evenement.clientY - r.top - r.height / 2) * 0.26;
      cible.style.translate = `${x}px ${y}px`;
    }
    racine.addEventListener("pointermove", auDeplacement);
    racine.addEventListener("pointerleave", relacher);
    return () => {
      racine.removeEventListener("pointermove", auDeplacement);
      racine.removeEventListener("pointerleave", relacher);
      relacher();
    };
  }, [page]);
}
