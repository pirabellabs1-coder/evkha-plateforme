/** Connexion à l'espace client.
 *
 * Remplace l'ancienne page, qui portait la charte de l'application : quelqu'un
 * qui arrivait de la page partenaires changeait d'univers visuel en un clic.
 * Elle partage désormais la coquille de l'inscription — deux portes du même
 * endroit doivent se ressembler.
 */
import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { ErreurApi, espaceApi, jeton } from "../espace/api";
import { BoutonGoogle } from "./BoutonGoogle";
import { Portail } from "./Portail";

export function Connexion() {
  const naviguer = useNavigate();
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  function entrer(jetonSession: string) {
    jeton.ecrire(jetonSession);
    void naviguer({ to: "/espace" });
  }

  async function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();
    setErreur("");
    setEnvoi(true);
    try {
      const reponse = await espaceApi.connexion(email, motDePasse);
      entrer(reponse.jeton);
    } catch (cause) {
      // Le serveur ne distingue pas « e-mail inconnu » de « mot de passe
      // faux » ; l'interface ne doit pas non plus le faire.
      setErreur(
        cause instanceof ErreurApi
          ? cause.message
          : "Connexion impossible. Vérifiez votre réseau.",
      );
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <Portail
      titre="Accéder à votre espace"
      onglet="connexion"
      sousTitre={
        <p className="prt-sous-titre">
          Vos livrables, vos crédits et votre marque.
        </p>
      }
      panneau={{
        image: "/partenaires/reunion.jpg",
        alt: "",
        titre: "Vos dossiers vous attendent.",
        arguments: [
          "Suivez vos générations en cours",
          "Retrouvez tous vos livrables produits",
          "Gérez vos crédits et votre équipe",
        ],
      }}
      enfants={
        <>
          <BoutonGoogle
            // Aucun extra : sur cette page, on se connecte. Si l'adresse
            // Google est inconnue, le serveur refuse faute de raison sociale
            // et le message renvoie vers la création de compte.
            onSession={(session) => entrer(session.jeton)}
            onErreur={(message) => setErreur(message)}
          />

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

            <label>
              Mot de passe
              <input
                type="password"
                value={motDePasse}
                onChange={(e) => setMotDePasse(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>

            {erreur && (
              <p className="insc-erreur" role="alert">
                {erreur}
                {/* Une adresse Google inconnue arrive ici : on nomme la sortie
                    au lieu de laisser la personne chercher. */}
                {erreur.includes("raison sociale") && (
                  <>
                    {" "}
                    <a href="/inscription">Créer un compte</a>
                  </>
                )}
              </p>
            )}

            <button type="submit" disabled={envoi}>
              {envoi ? "Connexion en cours…" : "Se connecter"}
            </button>
          </form>
        </>
      }
    />
  );
}
