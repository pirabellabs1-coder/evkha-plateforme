/** Acheter UNE étude, sans compte préalable.
 *
 * C'est la destination des quatre boutons de l'ancienne page des études du
 * site de la cliente. Le visiteur arrive avec son livrable dans l'adresse
 * (`/acheter/etude-marche`), lit ce qu'il achète et à quel prix, et part payer.
 *
 * ## Une page du socle (19/11/2026)
 *
 * L'ancien menu renvoyait vers l'ancien site, logo compris : au milieu d'un
 * paiement, un clic sortait de la plateforme. La page a d'abord reçu
 * `EnTeteSite` et `PiedSite`, montés à part autour d'une carte restée dans
 * l'ancienne charte des pages publiques. Elle est maintenant tout entière
 * sous UNE racine `.acc`, comme la boutique : carte à double bord,
 * bouton-pilule, étiquette à pastille, prix en Fraunces. Ce que le socle
 * remet à zéro pour toute la page (marges des paragraphes, soulignement des
 * liens), `Acheter.css` le rend à la carte, classe par classe.
 *
 * Seule la forme a changé : mêmes états, mêmes phrases, même champ, même
 * appel de paiement.
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
  achatRattacheALEspace,
  messageDuRefusDePaiement,
  payerUneEtude,
} from "./achat";
import { ID_DU_CONTENU } from "./contenuSite";
import { chargerLivrables, euros, type LivrablePublic } from "./donnees";
import { EnTeteSite } from "./EnTeteSite";
import { PiedSite } from "./PiedSite";
import { useMenu } from "./site";
// Le socle d'abord, la feuille de la page ensuite.
import "./Site.css";
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
  // Une PANNE n'est pas une étude introuvable. L'échec du catalogue le
  // remplaçait par une liste vide : un 500, ou dix secondes de coupure,
  // s'affichait « Cette étude n'est pas disponible — le lien que vous avez
  // suivi ne correspond à aucune de nos études », à quelqu'un dont le lien
  // était bon et qui venait payer (audit du 19/11/2026). « Pas disponible »
  // ne se dit plus que sur un catalogue REÇU où l'étude ne figure pas.
  const [panne, setPanne] = useState(false);
  // Incrémenté par « Réessayer » : il relance le chargement sans recharger
  // la page.
  const [tentative, setTentative] = useState(0);
  // Lu une fois, à l'arrivée : un espace est-il ouvert dans ce navigateur ?
  // L'achat part alors par l'espace et suit le compte (`achat.ts`).
  const [rattache] = useState(achatRattacheALEspace);
  // L'état du menu plein écran : la page rend inerte ce qui est derrière.
  const menu = useMenu();

  useEffect(() => {
    let vivant = true;
    chargerLivrables()
      .then((liste) => {
        if (!vivant) return;
        setPanne(false);
        setCatalogue(liste);
      })
      .catch(() => {
        if (vivant) setPanne(true);
      });
    return () => {
      vivant = false;
    };
  }, [tentative]);

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
      // Par l'espace si une session y est ouverte — l'achat suit alors le
      // compte —, sinon en visiteur. La règle vit dans `achat.ts`.
      const adresse = await payerUneEtude(offre.slug, email.trim());
      // Remplacement et non ouverture d'onglet : le paiement EST la suite du
      // parcours. Un nouvel onglet laisse derrière soi une page morte à
      // laquelle la personne revient, et où elle recliquera.
      window.location.href = adresse;
    } catch (cause) {
      setErreur(
        messageDuRefusDePaiement(
          cause,
          "Le paiement n'a pas pu être ouvert. Réessayez dans un instant.",
        ),
      );
      setEnvoi(false);
    }
  }

  return (
    <div className="acc ach">
      <EnTeteSite menu={menu} />

      {/* `tabIndex={-1}` : la cible du lien d'évitement doit pouvoir recevoir
          le focus. */}
      <main
        id={ID_DU_CONTENU}
        className="ach-corps"
        tabIndex={-1}
        inert={menu.ouvert}
      >
        {catalogue === null && !panne && (
          <p className="ach-attente">Chargement…</p>
        )}

        {panne && (
          <section className="ach-carte acc-entre">
            {/* Le mot d'accent est dans le titre, pas à côté : le nom du
                titre reste « Un instant ». */}
            <h1>
              Un <span className="acc-s">instant</span>
            </h1>
            <p className="ach-erreur" role="alert">
              Nos études n'ont pas pu être chargées. Votre lien est bon : c'est
              une panne passagère de notre côté.
            </p>
            <button
              type="button"
              className="acc-btn acc-btn-noir ach-bouton"
              onClick={() => {
                setPanne(false);
                setTentative((n) => n + 1);
              }}
            >
              Réessayer
              <span className="acc-btn-fleche" aria-hidden="true">
                →
              </span>
            </button>
            <p className="ach-rassurance">
              Si cela persiste, écrivez-nous à{" "}
              <a href="mailto:contact@evkha.fr">contact@evkha.fr</a>.
            </p>
          </section>
        )}

        {!panne && catalogue !== null && offre === null && (
          <section className="ach-carte acc-entre">
            <h1>Cette étude n'est pas disponible</h1>
            <p className="ach-texte">
              Le lien que vous avez suivi ne correspond à aucune de nos études.
              Écrivez-nous à <a href="mailto:contact@evkha.fr">contact@evkha.fr</a>{" "}
              et nous vous orientons.
            </p>
          </section>
        )}

        {!panne && offre !== null && (
          <section className="ach-carte acc-entre">
            {abandon && (
              <p className="ach-avis" role="status">
                Paiement interrompu — rien n'a été prélevé. Vous pouvez
                reprendre quand vous voulez.
              </p>
            )}

            <span className="acc-tag">Commande d'une étude</span>
            <h1>{offre.libelle}</h1>
            <p className="ach-accroche">{ACCROCHES[offre.type] ?? ""}</p>

            <p className="ach-prix">
              {euros(offre.prix_cents)} <span>TTC · paiement unique</span>
            </p>

            {/* La deuxième étape promettait « votre espace s'ouvre aussitôt »
                à tout le monde. C'est vrai d'un compte né du paiement ; pour
                une adresse qui a déjà un compte, le serveur n'ouvre plus de
                session depuis le retour de paiement, et la personne se
                connecte (`RetourPaiement`). On dit les deux. */}
            <ol className="ach-etapes">
              <li>Vous payez votre étude.</li>
              <li>
                {rattache
                  ? "Elle arrive dans votre espace, déjà ouvert dans ce navigateur."
                  : "Votre espace s'ouvre aussitôt, sans inscription à remplir — ou vous vous y connectez, si vous en avez déjà un."}
              </li>
              <li>Vous décrivez votre projet et lancez la production.</li>
              <li>Vous suivez l'avancement et téléchargez votre document.</li>
            </ol>

            {/* Avec un espace ouvert, l'achat suit le COMPTE : le serveur
                n'utilise pas d'adresse saisie ici. La demander quand même
                ferait croire qu'on peut l'envoyer ailleurs. */}
            {!rattache && (
              <>
                <label className="ach-champ" htmlFor="ach-email">
                  Votre adresse e-mail
                  <span className="ach-facultatif">facultatif</span>
                </label>
                {/* `.champ-saisie` (espace.css) : le champ de la charte, 16 px
                    au moins, anneau or au focus autour d'un bord noir —
                    `Acheter.css` le porte à 52 px de haut. */}
                <input
                  id="ach-email"
                  className="champ-saisie"
                  type="email"
                  autoComplete="email"
                  placeholder="vous@exemple.fr"
                  value={email}
                  onChange={(evenement) => setEmail(evenement.target.value)}
                  aria-describedby={erreur ? "ach-aide ach-erreur" : "ach-aide"}
                />
                <p className="ach-aide" id="ach-aide">
                  Pour pré-remplir la page de paiement. Vous pourrez la corriger.
                </p>
              </>
            )}

            {erreur && (
              <p className="ach-erreur" id="ach-erreur" role="alert">
                {erreur}
              </p>
            )}

            {/* Pendant l'ouverture du paiement, une lame de lumière traverse le
                bouton (`.bouton-chargement`, espace.css) : le texte dit
                « Ouverture… », le balayage dit seulement que ça travaille. */}
            <button
              type="button"
              className={
                envoi
                  ? "acc-btn acc-btn-noir ach-bouton bouton-chargement"
                  : "acc-btn acc-btn-noir ach-bouton"
              }
              onClick={payer}
              disabled={envoi}
            >
              {envoi ? "Ouverture du paiement…" : `Payer ${euros(offre.prix_cents)}`}
              <span className="acc-btn-fleche" aria-hidden="true">
                →
              </span>
            </button>

            <p className="ach-rassurance">
              Paiement sécurisé par Stripe. EVKHA ne voit jamais votre numéro
              de carte.
            </p>
          </section>
        )}
      </main>

      <PiedSite inerte={menu.ouvert} />
    </div>
  );
}
