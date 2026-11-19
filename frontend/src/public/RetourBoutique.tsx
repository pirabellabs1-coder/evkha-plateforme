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
 *
 * ## Le fichier suit le paiement, la session suit le compte
 *
 * Les liens de téléchargement sont ceux du fichier ACHETÉ : le serveur les
 * rend dans tous les cas, et cette page les affiche dans tous les cas. La
 * session, elle, n'est ouverte que pour un compte né de ce paiement. Pour un
 * compte qui existait, le serveur rend `"jeton": null` et
 * `"connexion_requise": true` (audit du 19/11/2026) : l'étude est rangée dans
 * cet espace, et la personne y entre par sa connexion habituelle. Écrire ce
 * `null` le faisait garder sous la forme « null » — une session qui se
 * croyait ouverte, et un lien « Voir mes achats » qui menait à des refus.
 */
import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";

import { MenuSite } from "./MenuSite";
import { confirmerLAchat } from "./catalogue";
import { accueillirUnRetourDePaiement } from "../espace/api";
import "./Partenaires.css";
import "./Boutique.css";

type Achat = {
  titre: string;
  telechargement: string;
  editable: string;
  /** Personne n'est connecté dans ce navigateur, et le serveur n'a ouvert
   *  aucune session : l'espace se retrouve par la connexion. */
  connexionRequise: boolean;
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
        // Trois issues, décidées à un seul endroit : la session s'ouvre (le
        // compte vient de naître de ce paiement), la session déjà présente
        // est gardée, ou la connexion est à proposer. Un jeton nul n'est
        // jamais écrit.
        const suite = accueillirUnRetourDePaiement(resultat);
        setAchat({
          titre: resultat.titre,
          telechargement: resultat.telechargement,
          editable: resultat.editable,
          connexionRequise: suite === "connexion_requise",
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
                <Link className="bouton bouton-noir bq-bouton" to="/boutique">
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
              {achat.connexionRequise ? (
                <p role="status">
                  Votre paiement est bien reçu. <b>{achat.titre}</b> est
                  rattachée au compte de l'adresse e-mail utilisée pour payer,
                  et un e-mail a été envoyé à cette adresse. Ce compte existait
                  déjà : connectez-vous pour la retrouver à tout moment dans
                  votre espace.
                </p>
              ) : (
                <p>
                  <b>{achat.titre}</b> — vous la retrouverez à tout moment dans
                  votre espace, et un e-mail vient de vous être envoyé.
                </p>
              )}
              <div className="bq-liens">
                {achat.telechargement && (
                  <a className="bouton bouton-noir bq-bouton" href={achat.telechargement}>
                    Télécharger le PDF
                  </a>
                )}
                {achat.editable && (
                  <a className="bouton bouton-noir bq-bouton" href={achat.editable}>
                    Télécharger la version Word
                  </a>
                )}
                {achat.connexionRequise ? (
                  <Link className="bq-extrait" to="/espace/connexion">
                    Se connecter à mon espace
                  </Link>
                ) : (
                  <Link className="bq-extrait" to="/espace/achats">
                    Voir mes achats
                  </Link>
                )}
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
