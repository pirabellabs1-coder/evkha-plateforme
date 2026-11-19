/** Le retour de Stripe : on confirme, puis on entre — ou on se connecte.
 *
 * Stripe redirige ici avec l'identifiant de session dans l'adresse. Cette page
 * le présente au serveur, qui vérifie chez Stripe que le paiement est bien
 * passé, verse le crédit, et dit s'il ouvre une session.
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
 * ## Qui entre sans mot de passe, et qui se connecte
 *
 * Cette page disait « c'est Stripe qui a prouvé son identité », et entrait
 * dans tous les cas. Stripe prouve qu'une carte a été encaissée — pas que le
 * payeur possède l'adresse qu'il a saisie (audit du 19/11/2026). Le serveur
 * ne délivre donc un jeton que pour le compte que CE paiement vient de créer,
 * une seule fois. Pour un compte qui existait, il rend `"jeton": null` et
 * `"connexion_requise": true` : l'achat est livré, et la personne entre par
 * sa connexion habituelle.
 *
 * Trois issues, décidées par `accueillirUnRetourDePaiement` et nulle part
 * ailleurs : la session est ouverte, la session déjà présente est gardée, ou
 * la connexion est proposée. Un jeton nul n'est jamais écrit, et une session
 * existante n'est jamais remplacée.
 */
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";

import { accueillirUnRetourDePaiement } from "../espace/api";
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
  // L'achat est livré sur un compte qui existait déjà, et personne n'est
  // connecté dans ce navigateur. On garde le nom de l'étude pour le redire :
  // « votre achat » sans dire lequel laisse douter que ce soit le bon.
  const [aRetrouver, setARetrouver] = useState<{ libelle: string } | null>(null);
  // React 18 monte deux fois en développement. Sans ce garde-fou, la
  // confirmation partirait en double — inoffensif côté serveur, qui est
  // idempotent, mais la seconde réponse ne porterait plus de jeton : le
  // serveur n'en délivre qu'un par compte né d'un paiement.
  const lance = useRef(false);

  useEffect(() => {
    if (lance.current || !session) return;
    lance.current = true;

    confirmerLePaiement(session)
      .then((achat) => {
        if (accueillirUnRetourDePaiement(achat) === "connexion_requise") {
          setARetrouver({ libelle: achat.libelle });
          return;
        }
        // Session ouverte à l'instant, ou déjà là : dans les deux cas, droit
        // sur le formulaire de commande, avec le bon livrable pré-sélectionné.
        // La personne vient d'acheter UNE étude précise, lui faire rechoisir
        // son type serait lui redemander ce qu'elle a déjà dit.
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
          ) : aRetrouver ? (
            <>
              <h1>Paiement reçu</h1>
              <p role="status">
                Votre paiement est bien enregistré
                {aRetrouver.libelle ? (
                  <>
                    {" "}
                    pour <b>{aRetrouver.libelle}</b>
                  </>
                ) : null}
                . Votre achat est rattaché au compte de l'adresse e-mail
                utilisée pour payer.
              </p>
              <p>
                Ce compte existait déjà : par sécurité, sa session ne s'ouvre
                pas depuis une page de paiement. Connectez-vous pour lancer
                votre étude.
              </p>
              <Link
                to="/espace/connexion"
                className="bouton bouton-principal ach-bouton"
              >
                Se connecter
              </Link>
              <p className="ach-rassurance">
                Pas encore de mot de passe, ou oublié&nbsp;?{" "}
                <Link to="/mot-de-passe-oublie">Recevoir un lien par e-mail</Link>
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
