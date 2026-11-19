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
import { messageDuRefusDePaiement, payerUneEtude } from "./achat";
import { BoutonGoogle } from "./BoutonGoogle";
import { FlecheDEnvoi, Portail } from "./Portail";
import {
  chargerFormules,
  chargerLivrables,
  euros,
  inscrire,
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

/** Code d'erreur LOCAL : le compte est créé, c'est son paiement qui n'a pas pu
 *  s'ouvrir. Il range ce cas à côté des codes du serveur (`deja_membre`…),
 *  pour que le message porte la bonne sortie — l'espace, où le paiement se
 *  reprend — et non une invitation à recommencer l'inscription. */
const PAIEMENT_A_REPRENDRE = "paiement_a_reprendre";

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

  /** Le compte existe, sa session est écrite : on part payer l'étude.
   *
   *  UN chemin pour les deux portes — le formulaire et le bouton Google. Ce
   *  dernier ouvrait son paiement de son côté, sans rien rattraper : un refus
   *  du prestataire ne s'affichait nulle part, et la personne restait devant
   *  un formulaire muet, avec un compte créé qu'elle ne savait pas avoir.
   *
   *  `courriel` ne sert que si la session vient à manquer (`payerUneEtude`
   *  retombe alors sur la route publique). Le bouton Google n'en passe pas :
   *  l'adresse tapée dans le formulaire n'est pas forcément celle du compte
   *  Google, et c'est elle qui ouvrait un second espace. */
  async function partirPayer(slug: string, courriel = "") {
    try {
      window.location.href = await payerUneEtude(slug, courriel);
    } catch (cause) {
      // Le COMPTE est créé : ce n'est pas l'inscription qui a échoué, et le
      // dire ferait recommencer un formulaire que le serveur refuserait
      // (« déjà membre »). On dit ce qui a échoué, et où reprendre.
      setErreur(
        `Votre compte est créé, mais le paiement n'a pas pu être ouvert. ${messageDuRefusDePaiement(
          cause,
          "Réessayez dans un instant.",
        )}`,
      );
      setChampFautif(PAIEMENT_A_REPRENDRE);
    }
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
      // Le jeton est écrit AVANT de partir chez Stripe, pour deux raisons.
      //
      // La session, d'abord : au retour, le serveur n'en ouvre AUCUNE pour un
      // compte qui a déjà son mot de passe — c'est celle-ci que la page de
      // retour retrouve, et garde. Et si la personne renonce puis revient par
      // un lien, elle retrouve son espace au lieu d'un écran de connexion
      // pour un compte qu'elle vient de créer.
      //
      // Le paiement, ensuite : c'est parce que la session existe qu'il part
      // par la route de l'ESPACE (`payerUneEtude`), qui porte l'organisation
      // jusqu'à Stripe. Il partait par la route publique, qui rattache l'achat
      // à l'adresse saisie CHEZ Stripe : corrigée là-bas, elle ouvrait un
      // second espace, et le crédit y attendait quelqu'un qui n'y viendrait
      // jamais (audit du 19/11/2026).
      if (ouvert.livrable_demande) {
        jeton.ecrire(ouvert.jeton);
        await partirPayer(ouvert.livrable_demande, email);
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
      accent={slugEtude ? "votre espace" : "espace partenaire"}
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
              // vide. Deux portes, un seul parcours — `partirPayer`.
              if (session.livrable_demande) {
                jeton.ecrire(session.jeton);
                void partirPayer(session.livrable_demande);
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
                aria-describedby={
                  champFautif === "raison_sociale_manquante"
                    ? "prt-erreur"
                    : undefined
                }
                required
              />
            </label>

            <div className="prt-duo">
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
                aria-describedby={
                  champFautif === "email_invalide" ||
                  champFautif === "deja_membre"
                    ? "prt-erreur"
                    : undefined
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
                aria-describedby={
                  champFautif === "mot_de_passe_faible" ||
                  champFautif === "mot_de_passe_manquant"
                    ? "prt-erreur"
                    : undefined
                }
                required
              />
              <small>Au moins douze signes, et pas seulement des chiffres.</small>
            </label>

            {/* Le champ que le serveur désigne (`aria-invalid`) est relié à
                ce message par `aria-describedby` : un lecteur d'écran le lit
                en arrivant sur le champ fautif. */}
            {erreur && (
              <p className="prt-erreur" id="prt-erreur" role="alert">
                {erreur}
                {champFautif === "deja_membre" && (
                  <>
                    {" "}
                    <a href="/espace/connexion">Se connecter</a>
                  </>
                )}
                {champFautif === PAIEMENT_A_REPRENDRE && (
                  <>
                    {" "}
                    <a href="/espace">Reprendre depuis mon espace</a>
                  </>
                )}
              </p>
            )}

            {/* Le bouton dit ce qui va se passer. « Créer mon compte » sur un
                parcours d'achat cacherait que le clic suivant est un paiement
                — et une personne surprise par une page de carte bancaire
                abandonne. Le montant y figure, comme sur la carte qu'elle
                vient de cliquer. */}
            <button
              type="submit"
              className="acc-btn acc-btn-or prt-envoi"
              disabled={envoi}
            >
              {envoi
                ? etude
                  ? "Ouverture du paiement…"
                  : "Création en cours…"
                : etude
                  ? `Créer mon compte et payer ${euros(etude.prix_cents)}`
                  : "Créer mon compte"}
              <FlecheDEnvoi />
            </button>
          </form>
        </>
      }
    />
  );
}
