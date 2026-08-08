/** « Continuer avec Google », affiché seulement s'il peut fonctionner.
 *
 * Tant que l'identifiant OAuth n'est pas posé côté serveur, le composant ne
 * rend **rien**. Un bouton qui échoue faute de réglage est pire que pas de
 * bouton : il fait douter du reste de la page (règle 1).
 *
 * Il sert la connexion ET l'inscription, parce que le serveur n'a qu'un point
 * d'entrée pour les deux : au moment du clic, personne ne sait encore si le
 * compte existe.
 */
import { useEffect, useRef, useState } from "react";
import {
  brancherBouton,
  chargerReglages,
  ouvrirSessionGoogle,
  RefusGoogle,
  type SessionGoogle,
} from "./google";

export function BoutonGoogle({
  extras,
  onSession,
  onErreur,
}: {
  /** Envoyés au serveur, utiles seulement si le compte doit être créé. */
  extras?: () => { raison_sociale?: string; formule?: string };
  onSession: (session: SessionGoogle) => void;
  onErreur: (message: string, code: string) => void;
}) {
  const conteneur = useRef<HTMLDivElement>(null);
  const [actif, setActif] = useState(false);
  const [enCours, setEnCours] = useState(false);

  // Les rappels changent à chaque rendu ; les garder dans une référence évite
  // de rebrancher le bouton Google à chaque frappe dans le formulaire.
  //
  // La référence est mise à jour dans un effet, pas pendant le rendu : écrire
  // un ref pendant le rendu casse les rendus concurrents de React, qui peut
  // rejouer un rendu abandonné.
  const dernier = useRef({ extras, onSession, onErreur });
  useEffect(() => {
    dernier.current = { extras, onSession, onErreur };
  });

  useEffect(() => {
    let vivant = true;

    chargerReglages()
      .then((reglages) => {
        if (!vivant || !reglages.google.actif || !conteneur.current) return;
        setActif(true);
        return brancherBouton(
          conteneur.current,
          reglages.google.client_id,
          (jetonGoogle) => {
            setEnCours(true);
            ouvrirSessionGoogle(jetonGoogle, dernier.current.extras?.() ?? {})
              .then((session) => dernier.current.onSession(session))
              .catch((cause: unknown) => {
                if (cause instanceof RefusGoogle) {
                  dernier.current.onErreur(cause.message, cause.code);
                } else {
                  dernier.current.onErreur(
                    "Connexion Google impossible. Réessayez.",
                    "",
                  );
                }
              })
              .finally(() => setEnCours(false));
          },
        );
      })
      // Google injoignable : on n'affiche simplement pas le bouton. Le mot de
      // passe reste un chemin valide, et c'est tout l'intérêt de ne pas
      // dépendre d'un seul fournisseur d'identité.
      .catch(() => vivant && setActif(false));

    return () => {
      vivant = false;
    };
  }, []);

  return (
    <>
      <div ref={conteneur} style={{ display: actif ? "block" : "none" }} />
      {actif && enCours && (
        <p className="prt-sous-titre" role="status">
          Connexion en cours…
        </p>
      )}
      {actif && <div className="prt-ou">ou</div>}
    </>
  );
}
