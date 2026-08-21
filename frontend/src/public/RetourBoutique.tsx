/** Le retour du paiement d'une étude de boutique.
 *
 * Cette page CONSTITUE l'achat elle-même : elle ne se contente pas de
 * l'annoncer. Le webhook du prestataire fait la même chose de son côté, sans
 * ordre garanti entre les deux — le traitement est idempotent, celui qui
 * arrive d'abord livre, l'autre ne fait rien.
 *
 * Faire patienter quelqu'un qui vient de payer devant un écran de chargement,
 * en espérant qu'un serveur tiers se manifeste, serait le pire moment du
 * parcours pour lui demander de la confiance.
 */
import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";

import { MenuSite } from "./MenuSite";
import { confirmerLAchat } from "./catalogue";
import { jeton } from "../espace/api";
import "./Partenaires.css";
import "./Boutique.css";

type Achat = {
  titre: string;
  telechargement: string;
  editable: string;
};

export function RetourBoutique() {
  const [achat, setAchat] = useState<Achat | null>(null);
  const [erreur, setErreur] = useState("");
  // La confirmation ne part qu'UNE fois. En mode strict, React monte deux fois
  // chaque composant : sans ce garde-fou, la page ouvrirait deux confirmations
  // concurrentes du même paiement.
  const lance = useRef(false);

  useEffect(() => {
    if (lance.current) return;
    lance.current = true;

    const session = new URLSearchParams(window.location.search).get("session");
    if (!session) {
      // Le refus passe par une promesse deja resolue plutot que par un appel
      // synchrone : poser l'etat dans le corps de l'effet declenche un rendu
      // en cascade.
      queueMicrotask(() => setErreur("Paiement introuvable."));
      return;
    }

    confirmerLAchat(session)
      .then((resultat) => {
        // La session est ouverte : la personne retrouvera son achat dans son
        // espace sans avoir à choisir un mot de passe maintenant.
        jeton.ecrire(resultat.jeton);
        setAchat({
          titre: resultat.titre,
          telechargement: resultat.telechargement,
          editable: resultat.editable,
        });
      })
      .catch((cause: unknown) => {
        setErreur(
          cause instanceof Error
            ? cause.message
            : "Votre paiement a bien été reçu, mais votre accès n'a pas pu être ouvert. Écrivez-nous à contact@evkha.fr.",
        );
      });
  }, []);

  return (
    <div className="pp bq">
      <MenuSite />

      <main className="pp-large">
        <div className="bq-retour-paiement">
          {erreur ? (
            <>
              <h1>Un instant</h1>
              <p role="alert">{erreur}</p>
              <div className="bq-liens">
                <Link className="bq-bouton" to="/boutique">
                  Revenir à la boutique
                </Link>
              </div>
            </>
          ) : !achat ? (
            <>
              <h1>Nous confirmons votre paiement…</h1>
              <p>Quelques secondes, ne fermez pas cette page.</p>
            </>
          ) : (
            <>
              <div className="bq-pastille" aria-hidden="true">
                ✓
              </div>
              <h1>Merci, votre étude est à vous</h1>
              <p>
                <b>{achat.titre}</b> — vous la retrouverez à tout moment dans
                votre espace, et un e-mail vient de vous être envoyé.
              </p>
              <div className="bq-liens">
                {achat.telechargement && (
                  <a className="bq-bouton" href={achat.telechargement}>
                    Télécharger le PDF
                  </a>
                )}
                {achat.editable && (
                  <a className="bq-bouton" href={achat.editable}>
                    Télécharger la version Word
                  </a>
                )}
                <Link className="bq-extrait" to="/espace/achats">
                  Voir mes achats
                </Link>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
