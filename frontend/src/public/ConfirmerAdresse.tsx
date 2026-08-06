/** Confirmer sa nouvelle adresse de connexion, depuis le lien reçu.
 *
 *  **Publique**, et il le faut : on clique depuis sa boîte mail, souvent sur un
 *  autre appareil que celui où la session est ouverte. Exiger un jeton rendrait
 *  le lien inutilisable pour ceux qui en ont le plus besoin — précisément ceux
 *  qui n'ont plus accès à l'ancienne adresse. Le lien EST la preuve : il a fallu
 *  le mot de passe actuel pour l'obtenir, il est signé, et il ne vaut que trois
 *  jours.
 *
 *  La confirmation part toute seule à l'ouverture, sans bouton à presser :
 *  cliquer dans le courriel EST la décision, la redemander ici la ferait
 *  prendre deux fois.
 *
 *  Même coquille que la connexion et l'inscription : quelqu'un qui vient de
 *  changer d'identifiant doit reconnaître l'endroit, pas se demander où le lien
 *  l'a mené.
 */
import { useEffect, useRef, useState } from "react";
import { confirmerLAdresse, RefusInscription } from "./donnees";
import { Portail } from "./Portail";

const PANNEAU = {
  image: "/partenaires/reunion.jpg",
  alt: "",
  titre: "Votre espace vous attend.",
  arguments: [
    "Vos livrables, téléchargeables sans limite",
    "Vos crédits et leur historique",
    "Votre marque appliquée à chaque document",
  ],
};

export function ConfirmerAdresse() {
  const [adresse, setAdresse] = useState("");
  const [erreur, setErreur] = useState("");

  // Lu dans l'URL et non dans l'état de route : la personne arrive depuis sa
  // boîte mail, l'application n'a aucun contexte antérieur.
  const jetonDuLien = new URLSearchParams(window.location.search).get("jeton") ?? "";

  // Le jeton ne sert QU'UNE FOIS — il signe l'ancienne adresse, qui ne
  // correspond plus à rien une fois le changement appliqué. Or `StrictMode`
  // monte, démonte et remonte chaque écran en développement : sans ce
  // garde-fou, le second appel arrivait après le premier et affichait « lien
  // invalide » sur un changement qui venait pourtant de réussir.
  const lance = useRef(false);

  useEffect(() => {
    if (!jetonDuLien || lance.current) return;
    lance.current = true;
    confirmerLAdresse(jetonDuLien)
      .then(setAdresse)
      .catch((cause: unknown) =>
        setErreur(
          cause instanceof RefusInscription
            ? cause.message
            : "Confirmation impossible. Vérifiez votre réseau.",
        ),
      );
  }, [jetonDuLien]);

  return (
    <Portail
      titre="Votre nouvelle adresse"
      onglet="connexion"
      sousTitre={
        <p className="prt-sous-titre">
          Ce lien applique le changement demandé depuis votre espace.
        </p>
      }
      panneau={PANNEAU}
      enfants={
        jetonDuLien === "" ? (
          <p className="insc-erreur" role="alert">
            Ce lien est incomplet. Ouvrez-le depuis le courriel reçu.
          </p>
        ) : erreur ? (
          <>
            <p className="insc-erreur" role="alert">
              {erreur}
            </p>
            {/* Le motif le plus fréquent est un lien déjà utilisé ou périmé :
                on nomme la sortie plutôt que de laisser chercher. La demande se
                relance depuis « Mon compte », sous la session en cours. */}
            <p className="prt-appoint">
              <a href="/espace/mon-compte">
                Demander un nouveau lien depuis votre espace
              </a>
            </p>
          </>
        ) : adresse ? (
          <>
            <p role="status">
              C'est fait&nbsp;: vous vous connectez désormais avec {adresse}.
              Votre mot de passe, lui, n'a pas changé.
            </p>
            <p className="prt-appoint">
              <a href="/espace/connexion">Se connecter avec cette adresse</a>
            </p>
          </>
        ) : (
          <p role="status">Confirmation en cours…</p>
        )
      }
    />
  );
}
