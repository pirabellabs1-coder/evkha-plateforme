/** Création de compte depuis la page partenaires.
 *
 * Le visiteur arrive avec sa formule dans l'adresse (`/inscription?formule=pro`).
 * La page la lui **rappelle avec son prix** : un formulaire qui ne dit pas ce
 * qu'on souscrit oblige à revenir en arrière pour vérifier, et c'est là qu'on
 * perd les gens.
 *
 * Elle n'annonce PAS de reprise de contact par EVKHA : le produit est un
 * SaaS, personne ne doit passer par un humain pour souscrire ni pour générer.
 * Le paiement en libre-service arrive plus tard ; d'ici là, l'activation reste
 * manuelle côté administration, mais ce n'est pas au visiteur d'en connaître
 * la mécanique interne.
 *
 * La mise en page est celle de `Portail`, partagée avec la connexion : les
 * deux pages sont deux portes du même endroit, elles doivent se ressembler.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { jeton } from "../espace/api";
import { BoutonGoogle } from "./BoutonGoogle";
import { Portail } from "./Portail";
import {
  chargerFormules,
  euros,
  inscrire,
  RefusInscription,
  type FormulePublique,
} from "./donnees";

/** Formule visée, lue dans l'adresse.
 *
 * `URLSearchParams` plutôt que le routeur : la page est atteinte depuis un
 * lien externe (systeme.io, un e-mail), et le paramètre doit être lu même
 * quand la navigation ne vient pas de l'application.
 */
function formuleDemandee(): string {
  return new URLSearchParams(window.location.search).get("formule") ?? "";
}

export function Inscription() {
  const naviguer = useNavigate();
  const [code] = useState(formuleDemandee);
  const [formules, setFormules] = useState<FormulePublique[] | null>(null);

  const [raisonSociale, setRaisonSociale] = useState("");
  const [prenom, setPrenom] = useState("");
  const [nom, setNom] = useState("");
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");

  const [erreur, setErreur] = useState("");
  const [champFautif, setChampFautif] = useState("");
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    let vivant = true;
    chargerFormules()
      .then((liste) => vivant && setFormules(liste))
      // Le catalogue n'est qu'un RAPPEL : s'il ne charge pas, l'inscription
      // reste possible. Bloquer le formulaire parce qu'un prix n'a pas pu
      // s'afficher serait disproportionné.
      .catch(() => vivant && setFormules([]));
    return () => {
      vivant = false;
    };
  }, []);

  const formule = (formules ?? []).find((f) => f.code === code);

  function entrer(jetonSession: string) {
    jeton.ecrire(jetonSession);
    void naviguer({ to: "/espace" });
  }

  async function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();
    setErreur("");
    setChampFautif("");
    setEnvoi(true);
    try {
      const ouvert = await inscrire({
        raison_sociale: raisonSociale,
        email,
        mot_de_passe: motDePasse,
        prenom,
        nom,
        formule: code,
      });
      // La session est ouverte par le serveur : on entre directement dans
      // l'espace, sans redemander les identifiants qu'on vient de choisir.
      entrer(ouvert.jeton);
    } catch (cause) {
      if (cause instanceof RefusInscription) {
        setErreur(cause.message);
        setChampFautif(cause.code);
      } else {
        setErreur("Inscription impossible. Vérifiez votre connexion.");
      }
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <Portail
      titre="Créer votre espace partenaire"
      onglet="inscription"
      sousTitre={
        formule ? (
          <p className="prt-sous-titre">
            Formule <b>{formule.libelle}</b> —{" "}
            {euros(formule.prix_mensuel_cents)} / mois,{" "}
            {formule.credits_par_echeance} crédit
            {formule.credits_par_echeance > 1 ? "s" : ""} par mois.{" "}
            <a href="/partenaires">Changer</a>
          </p>
        ) : (
          <p className="prt-sous-titre">
            Quelques informations, et votre espace est ouvert.
          </p>
        )
      }
      panneau={{
        image: "/partenaires/reunion.jpg",
        alt: "",
        titre: "Vos études, sous votre marque, sans y passer vos soirées.",
        arguments: [
          "Vos couleurs et votre logo sur chaque document",
          "Réception rapide sous 24 h : PDF + version éditable",
          "Vous restez l'interlocuteur de votre client",
        ],
      }}
      enfants={
        <>
          <BoutonGoogle
            // La raison sociale est lue AU CLIC : elle change pendant que la
            // personne tape, et une valeur figée à l'affichage serait vide.
            extras={() => ({ raison_sociale: raisonSociale, formule: code })}
            onSession={(session) => entrer(session.jeton)}
            onErreur={(message, codeErreur) => {
              setErreur(message);
              setChampFautif(codeErreur);
            }}
          />

          <form onSubmit={soumettre} noValidate>
            <label>
              Raison sociale
              <input
                value={raisonSociale}
                onChange={(e) => setRaisonSociale(e.target.value)}
                autoComplete="organization"
                aria-invalid={champFautif === "raison_sociale_manquante"}
                required
              />
            </label>

            <div className="insc-duo">
              <label>
                Prénom
                <input
                  value={prenom}
                  onChange={(e) => setPrenom(e.target.value)}
                  autoComplete="given-name"
                />
              </label>
              <label>
                Nom
                <input
                  value={nom}
                  onChange={(e) => setNom(e.target.value)}
                  autoComplete="family-name"
                />
              </label>
            </div>

            <label>
              Adresse e-mail
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                aria-invalid={
                  champFautif === "email_invalide" ||
                  champFautif === "deja_membre"
                }
                required
              />
            </label>

            <label>
              Mot de passe
              <input
                type="password"
                value={motDePasse}
                onChange={(e) => setMotDePasse(e.target.value)}
                autoComplete="new-password"
                aria-invalid={
                  champFautif === "mot_de_passe_faible" ||
                  champFautif === "mot_de_passe_manquant"
                }
                required
              />
              <small>Au moins douze signes, et pas seulement des chiffres.</small>
            </label>

            {erreur && (
              <p className="insc-erreur" role="alert">
                {erreur}
                {champFautif === "deja_membre" && (
                  <>
                    {" "}
                    <a href="/espace/connexion">Se connecter</a>
                  </>
                )}
              </p>
            )}

            <button type="submit" disabled={envoi}>
              {envoi ? "Création en cours…" : "Créer mon compte"}
            </button>
          </form>
        </>
      }
    />
  );
}
