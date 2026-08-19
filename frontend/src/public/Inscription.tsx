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
  chargerLivrables,
  euros,
  inscrire,
  ouvrirLePaiement,
  RefusInscription,
  type FormulePublique,
  type LivrablePublic,
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

/** Étude achetée à l'unité, lue dans l'adresse (`/inscription?livrable=…`).
 *
 * Jumelle de `formuleDemandee`, et lue de la même façon : la page est atteinte
 * depuis un lien de la page `/etudes`, et le paramètre doit valoir même quand
 * la navigation ne vient pas du routeur.
 *
 * Les deux ne coexistent jamais : on souscrit une formule OU on achète une
 * étude. Si les deux figurent dans l'adresse, l'étude gagne — c'est le
 * parcours le plus court et celui où l'argent est le plus proche.
 */
function livrableDemande(): string {
  return new URLSearchParams(window.location.search).get("livrable") ?? "";
}

export function Inscription() {
  const naviguer = useNavigate();
  const [code] = useState(formuleDemandee);
  const [slugEtude] = useState(livrableDemande);
  const [formules, setFormules] = useState<FormulePublique[] | null>(null);
  const [etudes, setEtudes] = useState<LivrablePublic[] | null>(null);

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

  useEffect(() => {
    if (!slugEtude) return;
    let vivant = true;
    chargerLivrables()
      // Même tolérance que pour les formules : le catalogue n'est qu'un
      // RAPPEL. Bloquer la création de compte parce qu'un prix n'a pas pu
      // s'afficher serait disproportionné — et le tarif appliqué au paiement
      // vient du serveur, pas de cet affichage.
      .then((liste) => vivant && setEtudes(liste))
      .catch(() => vivant && setEtudes([]));
    return () => {
      vivant = false;
    };
  }, [slugEtude]);

  const formule = (formules ?? []).find((f) => f.code === code);
  const etude = (etudes ?? []).find((e) => e.slug === slugEtude);

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
        livrable: slugEtude,
      });

      // Achat d'une étude : le compte existe, on enchaîne sur le paiement sans
      // passer par l'espace. L'y déposer d'abord donnerait un écran de plus,
      // et un espace vide au moment précis où la personne veut payer.
      //
      // Le jeton est écrit AVANT de partir chez Stripe : au retour, la page de
      // confirmation en délivrera un neuf, mais si la personne renonce et
      // revient par un lien, elle retrouve sa session au lieu d'un écran de
      // connexion pour un compte qu'elle vient de créer.
      if (ouvert.livrable_demande) {
        jeton.ecrire(ouvert.jeton);
        const adresse = await ouvrirLePaiement(ouvert.livrable_demande, email);
        window.location.href = adresse;
        return;
      }

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
      titre={slugEtude ? "Créer votre espace" : "Créer votre espace partenaire"}
      onglet="inscription"
      sousTitre={
        etude ? (
          <p className="prt-sous-titre">
            <b>{etude.libelle}</b> — {euros(etude.prix_cents)} TTC, paiement
            unique. <a href="/etudes">Changer d'étude</a>
          </p>
        ) : formule ? (
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
      // Le panneau parle au visiteur qu'on a en face. Celui qui achète UNE
      // étude n'a ni clients à servir, ni marque à appliquer : lui promettre
      // « vos couleurs sur chaque document » lui vendrait ce qu'il n'a pas
      // acheté, et lui ferait douter d'être au bon endroit.
      panneau={
        slugEtude
          ? {
              image: "/partenaires/reunion.jpg",
              alt: "",
              titre: "Votre étude, produite sur votre projet.",
              arguments: [
                "Un questionnaire, et la production démarre",
                "Vous suivez l'avancement étape par étape",
                "Livrée en Word et en PDF, prête à présenter",
              ],
            }
          : {
              image: "/partenaires/reunion.jpg",
              alt: "",
              titre: "Vos études, sous votre marque, sans y passer vos soirées.",
              arguments: [
                "Vos couleurs et votre logo sur chaque document",
                "Réception rapide sous 24 h : PDF + version éditable",
                "Vous restez l'interlocuteur de votre client",
              ],
            }
      }
      enfants={
        <>
          <BoutonGoogle
            // La raison sociale est lue AU CLIC : elle change pendant que la
            // personne tape, et une valeur figée à l'affichage serait vide.
            extras={() => ({
              raison_sociale: raisonSociale,
              formule: code,
              livrable: slugEtude,
            })}
            onSession={(session) => {
              // Même enchaînement que le formulaire : un compte ouvert pour
              // acheter une étude part payer, il n'atterrit pas dans un espace
              // vide. Deux portes, un seul parcours.
              if (session.livrable_demande) {
                jeton.ecrire(session.jeton);
                void ouvrirLePaiement(session.livrable_demande, email).then(
                  (adresse) => {
                    window.location.href = adresse;
                  },
                );
                return;
              }
              entrer(session.jeton);
            }}
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

            {/* Le bouton dit ce qui va se passer. « Créer mon compte » sur un
                parcours d'achat cacherait que le clic suivant est un paiement
                — et une personne surprise par une page de carte bancaire
                abandonne. Le montant y figure, comme sur la carte qu'elle
                vient de cliquer. */}
            <button type="submit" disabled={envoi}>
              {envoi
                ? etude
                  ? "Ouverture du paiement…"
                  : "Création en cours…"
                : etude
                  ? `Créer mon compte et payer ${euros(etude.prix_cents)}`
                  : "Créer mon compte"}
            </button>
          </form>
        </>
      }
    />
  );
}
