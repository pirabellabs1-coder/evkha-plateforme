/** Création de compte depuis la page partenaires.
 *
 * Le visiteur arrive ici avec sa formule dans l'adresse
 * (`/inscription?formule=pro`). La page la lui **rappelle avec son prix** :
 * un formulaire qui ne dit pas ce qu'on souscrit oblige à revenir en arrière
 * pour vérifier, et c'est là qu'on perd les gens.
 *
 * Elle annonce aussi, sans détour, ce qui ne se passera pas : aucun paiement
 * n'est demandé et aucun crédit n'est délivré. Laisser croire à un abonnement
 * actif ferait découvrir la vérité au moment de commander — trop tard.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { jeton } from "../espace/api";
import {
  chargerFormules,
  euros,
  inscrire,
  RefusInscription,
  type FormulePublique,
} from "./donnees";
import "./Partenaires.css";
import "./Inscription.css";

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
    const precedent = document.title;
    document.title = "Créer mon compte partenaire — EVKHA";
    return () => {
      document.title = precedent;
    };
  }, []);

  useEffect(() => {
    let vivant = true;
    chargerFormules()
      .then((liste) => vivant && setFormules(liste))
      // Le catalogue n'est qu'un RAPPEL : s'il ne charge pas, l'inscription
      // reste possible. Bloquer le formulaire parce qu'un prix n'a pas pu
      // s'afficher serait disproportionne.
      .catch(() => vivant && setFormules([]));
    return () => {
      vivant = false;
    };
  }, []);

  const formule = (formules ?? []).find((f) => f.code === code);

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
      jeton.ecrire(ouvert.jeton);
      await naviguer({ to: "/espace" });
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
    <div className="pp insc">
      <div className="insc-carte">
        <h1>Créer mon compte partenaire</h1>

        {formule ? (
          <div className="insc-formule">
            <div className="insc-formule-nom">
              Formule {formule.libelle}
              <span>
                {euros(formule.prix_mensuel_cents)} / mois ·{" "}
                {formule.credits_par_echeance} crédit
                {formule.credits_par_echeance > 1 ? "s" : ""} par mois
              </span>
            </div>
            <a className="insc-changer" href="/partenaires">
              Changer
            </a>
          </div>
        ) : (
          code && (
            <p className="insc-note">
              Formule « {code} » — le détail n'a pas pu être chargé, votre
              demande sera bien enregistrée.
            </p>
          )
        )}

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
                champFautif === "email_invalide" || champFautif === "deja_membre"
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

        {/* Dit ce qui ne se passera PAS. Un formulaire de souscription qui
            n'annonce pas l'absence de paiement laisse croire a un abonnement
            actif, et la verite se decouvre au moment de commander. */}
        <p className="insc-avertissement">
          Aucun paiement ne vous est demandé à cette étape et aucun crédit n'est
          délivré. Votre demande de formule est enregistrée : EVKHA vous
          recontacte pour l'activer.
        </p>

        <p className="insc-deja">
          Vous avez déjà un compte ? <a href="/espace/connexion">Se connecter</a>
        </p>
      </div>
    </div>
  );
}
