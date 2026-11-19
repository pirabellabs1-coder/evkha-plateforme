/** Le retour du paiement d'une étude de boutique.
 *
 * Cette page CONSTITUE l'achat elle-même : elle ne se contente pas de
 * l'annoncer. Le webhook du prestataire fait la même chose de son côté, sans
 * ordre garanti entre les deux — le traitement est idempotent, celui qui
 * arrive d'abord livre, l'autre ne fait rien.
 *
 * Faire patienter quelqu'un qui vient de payer devant un écran de chargement,
 * en espérant qu'un serveur tiers se manifeste, serait le pire moment du
 * parcours pour lui demander de la confiance.
 *
 * ## Le fichier suit le paiement, la session suit le compte
 *
 * Les liens de téléchargement sont ceux du fichier ACHETÉ : le serveur les
 * rend dans tous les cas, et cette page les affiche dans tous les cas. La
 * session, elle, n'est ouverte que pour un compte né de ce paiement. Pour un
 * compte qui existait, le serveur rend `"jeton": null` et
 * `"connexion_requise": true` (audit du 19/11/2026) : l'étude est rangée dans
 * cet espace, et la personne y entre par sa connexion habituelle. Écrire ce
 * `null` le faisait garder sous la forme « null » — une session qui se
 * croyait ouverte, et un lien « Voir mes achats » qui menait à des refus.
 *
 * ## Refonte du 19/11/2026 : la forme seule
 *
 * La page passe au langage visuel de la boutique refondue (`CadreDeBoutique`,
 * `Boutique.css`) : une carte à double bord, des boutons-pilules, l'en-tête
 * et le pied du socle. Les trois états — refus, attente, achat confirmé — et
 * leurs phrases n'ont pas changé.
 */
import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";

import { accueillirUnRetourDePaiement } from "../espace/api";
import { CadreDeBoutique } from "./Boutique";
import { confirmerLAchat } from "./catalogue";
import { useTitreDePage } from "./site";
// Le socle d'abord, la feuille du lot ensuite.
import "./Site.css";
import "./Boutique.css";

type Achat = {
  titre: string;
  telechargement: string;
  editable: string;
  /** Personne n'est connecté dans ce navigateur, et le serveur n'a ouvert
   *  aucune session : l'espace se retrouve par la connexion. */
  connexionRequise: boolean;
};

// ── Le texte de la page ─────────────────────────────────────────────────────

const ONGLET = {
  titre: "Votre achat — EVKHA",
  description:
    "La confirmation de votre achat sur la boutique EVKHA, et le " +
    "téléchargement de votre étude.",
};

const TEXTES = {
  sansSession: "Paiement introuvable.",
  refus:
    "Votre paiement a bien été reçu, mais votre accès n'a pas pu être ouvert. Écrivez-nous à contact@evkha.fr.",
  refusTitre: "Un instant",
  boutique: "Revenir à la boutique",
  attenteTitre: "Nous confirmons votre paiement…",
  attente: "Quelques secondes, ne fermez pas cette page.",
  merci: { avant: "Merci, votre étude", fin: "est à vous" },
  pdf: "Télécharger le PDF",
  word: "Télécharger la version Word",
  connexion: "Se connecter à mon espace",
  achats: "Voir mes achats",
};

export function RetourBoutique() {
  const [achat, setAchat] = useState<Achat | null>(null);
  const [erreur, setErreur] = useState("");
  const page = useRef<HTMLDivElement>(null);
  // La confirmation ne part qu'UNE fois. En mode strict, React monte deux fois
  // chaque composant : sans ce garde-fou, la page ouvrirait deux confirmations
  // concurrentes du même paiement.
  const lance = useRef(false);

  useTitreDePage(ONGLET.titre, ONGLET.description);

  useEffect(() => {
    if (lance.current) return;
    lance.current = true;

    const session = new URLSearchParams(window.location.search).get("session");
    if (!session) {
      // Le refus passe par une promesse déjà résolue plutôt que par un appel
      // synchrone : poser l'état dans le corps de l'effet déclenche un rendu
      // en cascade.
      queueMicrotask(() => setErreur(TEXTES.sansSession));
      return;
    }

    confirmerLAchat(session)
      .then((resultat) => {
        // Trois issues, décidées à un seul endroit : la session s'ouvre (le
        // compte vient de naître de ce paiement), la session déjà présente
        // est gardée, ou la connexion est à proposer. Un jeton nul n'est
        // jamais écrit.
        const suite = accueillirUnRetourDePaiement(resultat);
        setAchat({
          titre: resultat.titre,
          telechargement: resultat.telechargement,
          editable: resultat.editable,
          connexionRequise: suite === "connexion_requise",
        });
      })
      .catch((cause: unknown) => {
        setErreur(cause instanceof Error ? cause.message : TEXTES.refus);
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
                <Link className="acc-btn acc-btn-noir" to="/boutique">
                  {TEXTES.boutique}
                  <span className="acc-btn-fleche" aria-hidden="true">
                    →
                  </span>
                </Link>
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
                <p role="status">
                  Votre paiement est bien reçu. <b>{achat.titre}</b> est
                  rattachée au compte de l'adresse e-mail utilisée pour payer,
                  et un e-mail a été envoyé à cette adresse. Ce compte existait
                  déjà : connectez-vous pour la retrouver à tout moment dans
                  votre espace.
                </p>
              ) : (
                <p>
                  <b>{achat.titre}</b> — vous la retrouverez à tout moment dans
                  votre espace, et un e-mail vient de vous être envoyé.
                </p>
              )}
              <div className="bou-liens">
                {achat.telechargement && (
                  <a
                    className="acc-btn acc-btn-noir bou-bouton-souple"
                    href={achat.telechargement}
                  >
                    {TEXTES.pdf}
                    <span className="acc-btn-fleche" aria-hidden="true">
                      ↓
                    </span>
                  </a>
                )}
                {achat.editable && (
                  <a
                    className="acc-btn acc-btn-clair bou-bouton-souple"
                    href={achat.editable}
                  >
                    {TEXTES.word}
                    <span className="acc-btn-fleche" aria-hidden="true">
                      ↓
                    </span>
                  </a>
                )}
                {achat.connexionRequise ? (
                  <Link className="bou-lien" to="/espace/connexion">
                    {TEXTES.connexion}
                  </Link>
                ) : (
                  <Link className="bou-lien" to="/espace/achats">
                    {TEXTES.achats}
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
