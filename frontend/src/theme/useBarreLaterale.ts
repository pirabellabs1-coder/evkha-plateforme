/** Ouverture et fermeture de la barre latérale, pour LES DEUX espaces.
 *
 * Écrit une seule fois et importé par les deux coquilles. Deux implémentations
 * de la même mécanique finiraient par ne plus se comporter pareil, et
 * l'utilisateur le verrait en passant d'un espace à l'autre (règle 5).
 *
 * ## Deux gestes, un seul bouton
 *
 * Sur grand écran la barre occupe une colonne de la grille : la replier rend
 * cette place au contenu, et la préférence est **mémorisée** — quelqu'un qui
 * travaille au large ne veut pas la replier à chaque page.
 *
 * Sur petit écran elle est un tiroir posé par-dessus le contenu. Là, l'état
 * n'est pas mémorisé : rouvrir l'application sur un tiroir ouvert masquerait la
 * page qu'on vient de demander.
 *
 * Le seuil est lu dans le CSS via `matchMedia`, avec la même valeur que la
 * requête média de `espace.css`. C'est la seule duplication qui reste, et elle
 * est signalée des deux côtés.
 */
import { useCallback, useEffect, useState } from "react";

/** Doit rester aligné sur la requête média de `espace.css` (max-width: 900px). */
const ECRAN_LARGE = "(min-width: 901px)";

const CLE_REPLIEE = "evkha_barre_repliee";

function estLarge(): boolean {
  return window.matchMedia(ECRAN_LARGE).matches;
}

export interface BarreLaterale {
  /** La barre est-elle visible ? Sert aussi à `aria-expanded`. */
  visible: boolean;
  /** Vrai sur grand écran : la barre replie la grille au lieu de se superposer. */
  large: boolean;
  /** Ouvre ou ferme, selon la taille d'écran courante. */
  basculer: () => void;
  /**
   * Referme le tiroir mobile. **Sans effet sur grand écran**, et c'est le point
   * important : cette fonction est branchée sur le voile et sur chaque lien de
   * navigation. Si elle repliait aussi la barre au large, cliquer sur un lien
   * la ferait disparaître à chaque page.
   */
  fermer: () => void;
}

export function useBarreLaterale(): BarreLaterale {
  const [large, setLarge] = useState(estLarge);
  const [repliee, setRepliee] = useState(
    () => localStorage.getItem(CLE_REPLIEE) === "1",
  );
  const [tiroirOuvert, setTiroirOuvert] = useState(false);

  // On s'abonne au changement de taille au lieu de lire la largeur à chaque
  // rendu : sans cela, `aria-expanded` restait faux après une rotation d'écran.
  useEffect(() => {
    const requete = window.matchMedia(ECRAN_LARGE);
    const surChangement = (evenement: MediaQueryListEvent) => {
      setLarge(evenement.matches);
    };
    requete.addEventListener("change", surChangement);
    return () => requete.removeEventListener("change", surChangement);
  }, []);

  const visible = large ? !repliee : tiroirOuvert;

  const basculer = useCallback(() => {
    // La taille est relue ici plutôt que prise dans l'état : le clic est le
    // seul moment où la décision compte, et c'est le plus fiable.
    if (estLarge()) {
      setRepliee((valeur) => {
        const suivante = !valeur;
        localStorage.setItem(CLE_REPLIEE, suivante ? "1" : "0");
        return suivante;
      });
    } else {
      setTiroirOuvert((ouvert) => !ouvert);
    }
  }, []);

  const fermer = useCallback(() => {
    setTiroirOuvert(false);
  }, []);

  // Échap ferme le tiroir. Sans cela, quelqu'un au clavier doit tabuler toute
  // la navigation pour en sortir. Sur grand écran on ne replie pas à Échap :
  // la barre ne masque rien, et la touche servirait à autre chose.
  useEffect(() => {
    if (large || !tiroirOuvert) return;
    const surTouche = (evenement: KeyboardEvent) => {
      if (evenement.key === "Escape") setTiroirOuvert(false);
    };
    window.addEventListener("keydown", surTouche);
    return () => window.removeEventListener("keydown", surTouche);
  }, [large, tiroirOuvert]);

  return { visible, large, basculer, fermer };
}
