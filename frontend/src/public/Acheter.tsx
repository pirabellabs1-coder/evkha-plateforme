/** Acheter UNE étude, sans compte préalable.
 *
 * C'est la destination des quatre boutons de `evkha.fr/etudedemarche`. Le
 * visiteur arrive avec son livrable dans l'adresse (`/acheter/etude-marche`),
 * lit ce qu'il achète et à quel prix, et part payer.
 *
 * ## Trois décisions, et leurs raisons
 *
 * **Le prix vient du serveur.** Aucune page ne l'écrit en dur : la table
 * `Offer` le porte, le paiement s'y réfère, cette page l'affiche. Annoncer
 * 149 € et prélever 189 € est le pire défaut possible sur un parcours d'achat,
 * et c'est exactement ce que produit une seconde source (règle 5).
 *
 * **Rien n'est affiché tant que le tarif n'est pas chargé.** Un prix de repli
 * en attendant l'API serait un prix faux montré à qui a une connexion lente.
 *
 * **Un seul champ avant le paiement.** L'adresse, et elle est facultative :
 * Stripe la collecte de toute façon, et c'est la sienne qui fait foi au
 * retour. Chaque champ ajouté ici se paie en abandons.
 */
import { useEffect, useState } from "react";
import { useParams } from "@tanstack/react-router";

import {
  chargerLivrables,
  euros,
  ouvrirLePaiement,
  RefusInscription,
  type LivrablePublic,
} from "./donnees";
import { MenuSite } from "./MenuSite";
import "./Partenaires.css";
import "./Acheter.css";

/** Ce que chaque étude apporte, en une phrase.
 *
 * Éditorial, donc ici et non en base : la table porte le nom et le tarif, qui
 * engagent la plateforme. Une accroche commerciale se réécrit sans migration.
 */
const ACCROCHES: Record<string, string> = {
  market_study:
    "Votre marché est-il vraiment porteur ? Taille, croissance, clients types, risques — chiffré et sourcé.",
  competitor_study:
    "Qui sont vos concurrents, ce qu'ils font, ce qui vous en différencie. Nommés un par un, pas décrits en profils.",
  business_plan:
    "Le dossier que votre banque attend : marché, prévisionnel financier, plan d'action, rédigé en français clair.",
  business_strategy:
    "Une stratégie claire et rentable en quatre piliers, adaptée à vos contraintes et orientée résultats.",
};

/** Le paiement est-il abandonné ? Stripe nous renvoie ici dans ce cas. */
function paiementAbandonne(): boolean {
  return new URLSearchParams(window.location.search).get("paiement") === "abandon";
}

export function Acheter() {
  const { livrable } = useParams({ strict: false }) as { livrable?: string };
  const [catalogue, setCatalogue] = useState<LivrablePublic[] | null>(null);
  const [email, setEmail] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState("");
  const [abandon] = useState(paiementAbandonne);

  useEffect(() => {
    chargerLivrables()
      .then(setCatalogue)
      .catch(() => setCatalogue([]));
  }, []);

  const offre = catalogue?.find((o) => o.slug === livrable) ?? null;

  useEffect(() => {
    if (offre) {
      document.title = `${offre.libelle} — EVKHA`;
    }
  }, [offre]);

  async function payer() {
    if (!offre) return;
    setEnvoi(true);
    setErreur("");
    try {
      const adresse = await ouvrirLePaiement(offre.slug, email.trim());
      // Remplacement et non ouverture d'onglet : le paiement EST la suite du
      // parcours. Un nouvel onglet laisse derrière soi une page morte à
      // laquelle la personne revient, et où elle recliquera.
      window.location.href = adresse;
    } catch (cause) {
      setErreur(
        cause instanceof RefusInscription
          ? cause.message
          : "Le paiement n'a pas pu être ouvert. Réessayez dans un instant.",
      );
      setEnvoi(false);
    }
  }

  return (
    <div className="pp ach">
      <MenuSite />

      <main className="ach-corps">
        {catalogue === null && (
          <p className="ach-attente">Chargement…</p>
        )}

        {catalogue !== null && offre === null && (
          <section className="ach-carte">
            <h1>Cette étude n'est pas disponible</h1>
            <p>
              Le lien que vous avez suivi ne correspond à aucune de nos études.
              Écrivez-nous à <a href="mailto:contact@evkha.fr">contact@evkha.fr</a>{" "}
              et nous vous orientons.
            </p>
          </section>
        )}

        {offre !== null && (
          <section className="ach-carte">
            {abandon && (
              <p className="ach-avis" role="status">
                Paiement interrompu — rien n'a été prélevé. Vous pouvez
                reprendre quand vous voulez.
              </p>
            )}

            <p className="ach-surtitre">Commande d'une étude</p>
            <h1>{offre.libelle}</h1>
            <p className="ach-accroche">{ACCROCHES[offre.type] ?? ""}</p>

            <p className="ach-prix">
              {euros(offre.prix_cents)} <span>TTC · paiement unique</span>
            </p>

            <ol className="ach-etapes">
              <li>Vous payez votre étude.</li>
              <li>Votre espace s'ouvre aussitôt, sans inscription à remplir.</li>
              <li>Vous décrivez votre projet et lancez la production.</li>
              <li>Vous suivez l'avancement et téléchargez votre document.</li>
            </ol>

            <label className="ach-champ" htmlFor="ach-email">
              Votre adresse e-mail
              <span className="ach-facultatif">facultatif</span>
            </label>
            <input
              id="ach-email"
              type="email"
              autoComplete="email"
              placeholder="vous@exemple.fr"
              value={email}
              onChange={(evenement) => setEmail(evenement.target.value)}
            />
            <p className="ach-aide">
              Pour pré-remplir la page de paiement. Vous pourrez la corriger.
            </p>

            {erreur && (
              <p className="ach-erreur" role="alert">
                {erreur}
              </p>
            )}

            <button
              type="button"
              className="ach-bouton"
              onClick={payer}
              disabled={envoi}
            >
              {envoi ? "Ouverture du paiement…" : `Payer ${euros(offre.prix_cents)}`}
            </button>

            <p className="ach-rassurance">
              Paiement sécurisé par Stripe. EVKHA ne voit jamais votre numéro
              de carte.
            </p>
          </section>
        )}
      </main>
    </div>
  );
}
