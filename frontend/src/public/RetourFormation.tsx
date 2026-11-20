/** Le retour du paiement d'une formation.
 *
 * Décliné de `RetourBoutique`, dont il reprend le cadre, les classes et les
 * trois états. Comme lui, cette page CONSTITUE l'achat elle-même
 * (`POST /api/public/formations/retour/`) sans attendre le webhook du
 * prestataire : les deux arrivent sans ordre garanti, le traitement est
 * rejouable, celui qui arrive d'abord livre.
 *
 * ## Trois états
 *
 * - ATTENTE : la confirmation est partie, la réponse n'est pas arrivée.
 * - REFUS (`role="alert"`) : pas de session dans l'adresse, un refus du
 *   serveur (409 : ce paiement n'est pas celui d'une formation, ou n'est pas
 *   payé), ou une panne. Toujours avec une porte de sortie : les formations,
 *   et l'adresse de contact.
 * - CONFIRMÉ : la formation est à l'acheteur. Son programme ne se lit PAS
 *   ici — le serveur ne rend sur cette route aucun contenu de leçon : la page
 *   mène à l'espace.
 *
 * ## La session suit le compte
 *
 * `accueillirUnRetourDePaiement` décide, comme pour les deux autres retours :
 * une session DÉJÀ ouverte dans ce navigateur n'est jamais remplacée ; un
 * jeton reçu ouvre la session du compte né de ce paiement ; un jeton nul
 * n'ouvre rien, et la page propose la connexion.
 *
 * La page demande à ne pas être indexée (`useSansIndexation`) : son adresse
 * porte un identifiant de paiement, et elle n'a rien à dire à un moteur.
 */
import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";

import { accueillirUnRetourDePaiement } from "../espace/api";
import { MES_FORMATIONS } from "./achat";
import { CadreDeBoutique } from "./Boutique";
import { CONTACT_EMAIL } from "./contenu";
import { CHEMINS } from "./contenuSite";
import { confirmerLAchatDUneFormation, RefusInscription } from "./donnees";
import { titreDOnglet, useSansIndexation, useTitreDePage } from "./site";
// Le socle d'abord, la feuille du lot ensuite.
import "./Site.css";
import "./Boutique.css";

type Achat = {
  titre: string;
  slug: string;
  /** Personne n'est connecté dans ce navigateur, et le serveur n'a ouvert
   *  aucune session : l'espace se retrouve par la connexion. */
  connexionRequise: boolean;
};

// ── Le texte de la page ─────────────────────────────────────────────────────

const ONGLET = {
  titre: titreDOnglet("Votre formation"),
  description:
    "La confirmation de votre inscription à une formation EVKHA, et l'accès " +
    "à votre programme.",
};

const TEXTES = {
  sansSession: "Paiement introuvable.",
  /** Le serveur n'a pas répondu, ou pas lisiblement. On ne sait PAS si le
   *  paiement a abouti : la phrase ne l'affirme pas. */
  panne:
    "Nous n'avons pas pu confirmer votre paiement pour le moment. S'il a bien été débité, votre formation vous attend dans votre espace\u00a0: rechargez cette page dans un instant, ou écrivez-nous.",
  refusTitre: "Un instant",
  formations: "Revenir aux formations",
  ecrire: "Écrire à",
  attenteTitre: "Nous confirmons votre paiement…",
  attente: "Quelques secondes, ne fermez pas cette page.",
  merci: { avant: "Merci, votre formation", fin: "est à vous" },
  dansLEspace:
    "vous attend dans votre espace, où vous la retrouverez à tout moment. Un courriel de confirmation vient de vous être envoyé.",
  rattachee:
    "est rattachée au compte de l'adresse e-mail utilisée pour payer.",
  /** Juste dans les DEUX cas : le compte existait (il a son mot de passe, et
   *  aucun courriel n'est parti pour en choisir un) ou il vient de naître de
   *  ce paiement. L'ancienne phrase affirmait le courriel à tout le monde. */
  motDePasse:
    "Connectez-vous pour y accéder. Si vous n'avez pas encore de mot de passe, un courriel vient de vous être envoyé pour le choisir.",
  paiementRecu: "Votre paiement est bien reçu.",
  acceder: "Accéder à ma formation",
  connexion: "Me connecter",
  /** Quand le serveur n'a pas rendu de titre : la phrase reste juste. */
  sansTitre: "Votre formation",
};

export function RetourFormation() {
  const [achat, setAchat] = useState<Achat | null>(null);
  const [erreur, setErreur] = useState("");
  const page = useRef<HTMLDivElement>(null);
  // La confirmation ne part qu'UNE fois. En mode strict, React monte deux fois
  // chaque composant : sans ce garde-fou, la page ouvrirait deux confirmations
  // concurrentes du même paiement.
  const lance = useRef(false);

  useTitreDePage(ONGLET.titre, ONGLET.description);
  useSansIndexation();

  useEffect(() => {
    if (lance.current) return;
    lance.current = true;

    const session = new URLSearchParams(window.location.search).get("session");
    if (!session) {
      // Le refus passe par une microtâche plutôt que par un appel synchrone :
      // poser l'état dans le corps de l'effet déclenche un rendu en cascade.
      queueMicrotask(() => setErreur(TEXTES.sansSession));
      return;
    }

    confirmerLAchatDUneFormation(session)
      .then((resultat) => {
        // Trois issues, décidées à un seul endroit : la session s'ouvre (le
        // compte vient de naître de ce paiement), la session déjà présente
        // est gardée, ou la connexion est à proposer. Un jeton nul n'est
        // jamais écrit.
        const suite = accueillirUnRetourDePaiement(resultat);
        setAchat({
          titre: resultat.titre,
          slug: resultat.slug,
          connexionRequise: suite === "connexion_requise",
        });
      })
      .catch((cause: unknown) => {
        // La phrase du serveur quand il en a écrit une ; sinon la nôtre — un
        // « Failed to fetch » ne dit rien à quelqu'un qui vient de payer.
        setErreur(
          cause instanceof RefusInscription && cause.message
            ? cause.message
            : TEXTES.panne,
        );
      });
  }, []);

  return (
    <CadreDeBoutique racine={page} classe="bou-retour-page">
      <div className="acc-w bou-etat">
        <div className="bou-retour-carte">
          {erreur ? (
            <>
              <h1>{TEXTES.refusTitre}</h1>
              <p className="bou-erreur" role="alert">
                {erreur}
              </p>
              <div className="bou-liens">
                <Link className="acc-btn acc-btn-noir" to={CHEMINS.formations}>
                  {TEXTES.formations}
                  <span className="acc-btn-fleche" aria-hidden="true">
                    →
                  </span>
                </Link>
                <a className="bou-lien" href={`mailto:${CONTACT_EMAIL}`}>
                  {TEXTES.ecrire} {CONTACT_EMAIL}
                </a>
              </div>
            </>
          ) : !achat ? (
            <>
              <h1>{TEXTES.attenteTitre}</h1>
              <p role="status">{TEXTES.attente}</p>
            </>
          ) : (
            <>
              <div className="bou-pastille" aria-hidden="true">
                ✓
              </div>
              <h1>
                {TEXTES.merci.avant}{" "}
                <span className="acc-s">{TEXTES.merci.fin}</span>
              </h1>
              {achat.connexionRequise ? (
                <>
                  <p role="status">
                    {TEXTES.paiementRecu} <b>{achat.titre || TEXTES.sansTitre}</b>{" "}
                    {TEXTES.rattachee}
                  </p>
                  <p>{TEXTES.motDePasse}</p>
                </>
              ) : (
                <p role="status">
                  <b>{achat.titre || TEXTES.sansTitre}</b> {TEXTES.dansLEspace}
                </p>
              )}
              <div className="bou-liens">
                {achat.connexionRequise ? (
                  <Link className="acc-btn acc-btn-noir" to={CHEMINS.espaceClient}>
                    {TEXTES.connexion}
                    <span className="acc-btn-fleche" aria-hidden="true">
                      →
                    </span>
                  </Link>
                ) : (
                  <Link
                    className="acc-btn acc-btn-noir bou-bouton-souple"
                    to={`${MES_FORMATIONS}/$slug`}
                    params={{ slug: achat.slug }}
                  >
                    {TEXTES.acceder}
                    <span className="acc-btn-fleche" aria-hidden="true">
                      →
                    </span>
                  </Link>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </CadreDeBoutique>
  );
}
