/** Le retour de Stripe : on confirme, on entre.
 *
 * Stripe redirige ici avec l'identifiant de session dans l'adresse. Cette page
 * le présente au serveur, qui vérifie chez Stripe que le paiement est bien
 * passé, ouvre l'espace, verse le crédit et rend un jeton de session.
 *
 * ## Pourquoi on n'attend pas le webhook
 *
 * Stripe redirige le navigateur ET poste son événement, en parallèle, sans
 * ordre garanti. Faire patienter quelqu'un qui vient de payer devant un écran
 * de chargement, en espérant qu'un serveur tiers se manifeste, serait le pire
 * moment du parcours pour lui demander de la confiance. Le serveur traite les
 * deux appels de façon idempotente : celui qui arrive d'abord livre, l'autre
 * ne fait rien.
 *
 * ## Pourquoi la personne entre sans mot de passe
 *
 * C'est Stripe qui a prouvé son identité — il a encaissé une carte et collecté
 * son adresse. Lui demander de choisir un mot de passe MAINTENANT ajouterait
 * un écran entre son paiement et son étude. Elle en choisira un depuis le
 * courriel qu'elle vient de recevoir, quand elle voudra revenir.
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";

import { jeton } from "../espace/api";
import { confirmerLePaiement, RefusInscription } from "./donnees";
import "./Partenaires.css";
import "./Acheter.css";

function sessionDansLAdresse(): string {
  return new URLSearchParams(window.location.search).get("session") ?? "";
}

/** Message d'une arrivée sans identifiant de paiement.
 *
 *  Il est posé à l'INITIALISATION de l'état, pas depuis l'effet : l'absence de
 *  session se lit dans l'adresse, donc au premier rendu. La déduire dans un
 *  effet ferait un rendu de plus, et afficherait « ce sera très court » à
 *  quelqu'un dont on sait déjà que ça ne marchera pas.
 */
const SANS_SESSION =
  "Nous n'avons pas retrouvé votre paiement. Si vous avez été débité, " +
  "écrivez-nous à contact@evkha.fr : nous ouvrons votre espace immédiatement.";

export function RetourPaiement() {
  const naviguer = useNavigate();
  const [session] = useState(sessionDansLAdresse);
  const [erreur, setErreur] = useState(() => (session ? "" : SANS_SESSION));
  // React 18 monte deux fois en développement. Sans ce garde-fou, la
  // confirmation partirait en double — inoffensif côté serveur, qui est
  // idempotent, mais deux jetons seraient émis pour une seule arrivée.
  const lance = useRef(false);

  useEffect(() => {
    if (lance.current || !session) return;
    lance.current = true;

    confirmerLePaiement(session)
      .then((achat) => {
        jeton.ecrire(achat.jeton);
        // Directement sur le formulaire de commande, avec le bon livrable
        // pré-sélectionné : la personne vient d'acheter UNE étude précise, lui
        // faire rechoisir son type serait lui redemander ce qu'elle a déjà dit.
        naviguer({
          to: "/espace/commander",
          search: { livrable: achat.livrable },
        });
      })
      .catch((cause) => {
        setErreur(
          cause instanceof RefusInscription
            ? cause.message
            : "Votre paiement n'a pas pu être confirmé. Écrivez-nous à " +
                "contact@evkha.fr, nous réglons cela tout de suite.",
        );
      });
  }, [naviguer, session]);

  return (
    <div className="pp ach">
      <main className="ach-corps">
        <section className="ach-carte ach-retour">
          {erreur ? (
            <>
              <h1>Un instant</h1>
              <p className="ach-erreur" role="alert">
                {erreur}
              </p>
              <p>
                Votre paiement, lui, est bien enregistré chez notre prestataire.
                Rien n'est perdu.
              </p>
            </>
          ) : (
            <>
              <h1>Paiement reçu</h1>
              <p role="status">
                Nous ouvrons votre espace, ce sera très court…
              </p>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
