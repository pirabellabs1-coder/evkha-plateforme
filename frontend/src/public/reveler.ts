/** Révélation à l'entrée dans la fenêtre, pour les pages publiques.
 *
 * Les blocs marqués `data-reveal` naissent effacés (voir `Partenaires.css`)
 * et s'allument quand ils entrent dans la fenêtre — une fois, jamais au
 * retour. Un `IntersectionObserver`, et non un écouteur de défilement : le
 * second s'exécute à chaque image pendant tout le défilement et fait tomber
 * un téléphone sous 60 i/s ; le premier ne parle que quand un bloc franchit
 * le bord.
 *
 * Trois cas où l'on n'attend rien :
 * - sans `IntersectionObserver` (vieux navigateur, jsdom), tout est visible
 *   tout de suite — un bloc qui resterait effacé serait une page cassée ;
 * - sous `prefers-reduced-motion`, la feuille de style rend déjà tout
 *   visible ; la classe est posée quand même pour n'avoir qu'un seul état ;
 * - un bloc déjà dans la fenêtre au montage est révélé au premier passage de
 *   l'observateur, qui signale toujours l'état initial.
 *
 * `cle` : une valeur dont le changement fait monter de nouveaux blocs (les
 * formules chargées après coup, par exemple). L'effet se rejoue alors, et
 * n'observe que ce qui n'est pas encore révélé.
 */
import { useEffect, type RefObject } from "react";

const REVELE = "est-revele";

export function useReveler(
  racine: RefObject<HTMLElement | null>,
  cle?: unknown,
): void {
  useEffect(() => {
    const conteneur = racine.current;
    if (!conteneur) return undefined;
    const blocs = Array.from(
      conteneur.querySelectorAll<HTMLElement>(`[data-reveal]:not(.${REVELE})`),
    );
    if (blocs.length === 0) return undefined;

    const sansMouvement =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (typeof IntersectionObserver === "undefined" || sansMouvement) {
      for (const bloc of blocs) bloc.classList.add(REVELE);
      return undefined;
    }

    const observateur = new IntersectionObserver(
      (entrees) => {
        for (const entree of entrees) {
          if (!entree.isIntersecting) continue;
          entree.target.classList.add(REVELE);
          observateur.unobserve(entree.target);
        }
      },
      // Un bloc est « entré » dès son premier pixel au-dessus d'une ligne
      // placée à six pour cent de la hauteur de fenêtre avant le bord bas :
      // il s'allume en arrivant, pas une fois qu'on l'a déjà lu. Seuil 0 et
      // non 0,1 : un bloc plus haut que dix fenêtres (une description saisie
      // en texte libre) n'atteindrait jamais un dixième visible.
      { threshold: 0, rootMargin: "0px 0px -6% 0px" },
    );
    for (const bloc of blocs) observateur.observe(bloc);
    return () => observateur.disconnect();
  }, [racine, cle]);
}
