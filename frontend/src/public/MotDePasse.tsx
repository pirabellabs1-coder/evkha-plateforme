/** Définir son mot de passe, et le redemander quand on l'a perdu.
 *
 *  Ces deux écrans n'existaient pas. Le collaborateur invité recevait — enfin,
 *  aurait dû recevoir — un lien qui ne menait nulle part, et quiconque perdait
 *  son mot de passe était enfermé dehors : aucune route ne permettait d'en
 *  poser un nouveau.
 *
 *  Un seul écran pour les deux parcours d'activation et de réinitialisation :
 *  c'est le même geste, et le jeton reçu porte déjà la distinction. En faire
 *  deux ferait diverger les messages et les contrôles.
 */
import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { jeton as sessionJeton } from "../espace/api";
import { definirLeMotDePasse, demanderUnLien, RefusInscription } from "./donnees";
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

/** Écran d'activation / réinitialisation, atteint par le lien du courriel. */
export function DefinirMotDePasse() {
  const naviguer = useNavigate();
  const [motDePasse, setMotDePasse] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  // Lus dans l'URL et non dans un état de route : la personne arrive depuis sa
  // boîte mail, l'application n'a aucun contexte antérieur.
  const parametres = new URLSearchParams(window.location.search);
  const id = parametres.get("id") ?? "";
  const jetonLien = parametres.get("jeton") ?? "";

  const lienIncomplet = !id || !jetonLien;

  async function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();
    setErreur("");

    // Vérifié ici ET côté serveur pour la solidité du mot de passe ; la
    // concordance des deux saisies, elle, n'a de sens que devant l'écran.
    if (motDePasse !== confirmation) {
      setErreur("Les deux mots de passe ne sont pas identiques.");
      return;
    }

    setEnvoi(true);
    try {
      const session = await definirLeMotDePasse({
        id,
        jeton: jetonLien,
        mot_de_passe: motDePasse,
      });
      sessionJeton.ecrire(session.jeton);
      void naviguer({ to: "/espace" });
    } catch (cause) {
      setErreur(
        cause instanceof RefusInscription
          ? cause.message
          : "Impossible de définir le mot de passe. Vérifiez votre réseau.",
      );
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <Portail
      titre="Choisir votre mot de passe"
      onglet="connexion"
      sousTitre={
        <p className="prt-sous-titre">
          Vous seul le connaîtrez — pas même la personne qui vous a invité.
        </p>
      }
      panneau={PANNEAU}
      enfants={
        lienIncomplet ? (
          <p className="insc-erreur" role="alert">
            Ce lien est incomplet. Ouvrez-le depuis le courriel reçu, ou{" "}
            <a href="/mot-de-passe-oublie">demandez-en un nouveau</a>.
          </p>
        ) : (
          <form onSubmit={soumettre} noValidate>
            <label>
              Nouveau mot de passe
              <input
                type="password"
                value={motDePasse}
                onChange={(e) => setMotDePasse(e.target.value)}
                autoComplete="new-password"
                required
              />
            </label>

            <label>
              Confirmer le mot de passe
              <input
                type="password"
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                autoComplete="new-password"
                required
              />
            </label>

            {erreur && (
              <p className="insc-erreur" role="alert">
                {erreur}
                {/* Un lien périmé est le cas le plus fréquent : on nomme la
                    sortie au lieu de laisser la personne chercher. */}
                {erreur.includes("plus valable") && (
                  <>
                    {" "}
                    <a href="/mot-de-passe-oublie">Demander un nouveau lien</a>
                  </>
                )}
              </p>
            )}

            <button type="submit" disabled={envoi}>
              {envoi ? "Enregistrement…" : "Définir mon mot de passe et entrer"}
            </button>
          </form>
        )
      }
    />
  );
}

/** Demande d'un lien de réinitialisation. */
export function MotDePasseOublie() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  async function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();
    setErreur("");
    setEnvoi(true);
    try {
      setMessage(await demanderUnLien(email));
    } catch (cause) {
      setErreur(
        cause instanceof RefusInscription
          ? cause.message
          : "Demande impossible. Vérifiez votre réseau.",
      );
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <Portail
      titre="Mot de passe oublié"
      onglet="connexion"
      sousTitre={
        <p className="prt-sous-titre">
          Nous vous envoyons un lien pour en choisir un nouveau.
        </p>
      }
      panneau={PANNEAU}
      enfants={
        message ? (
          // Le serveur répond la MÊME chose que l'adresse existe ou non :
          // l'interface ne doit rien laisser deviner de plus.
          <p role="status">{message}</p>
        ) : (
          <form onSubmit={soumettre} noValidate>
            <label>
              Adresse e-mail
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
            </label>

            {erreur && (
              <p className="insc-erreur" role="alert">
                {erreur}
              </p>
            )}

            <button type="submit" disabled={envoi}>
              {envoi ? "Envoi en cours…" : "Recevoir un lien"}
            </button>
          </form>
        )
      }
    />
  );
}
