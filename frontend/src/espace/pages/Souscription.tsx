/** Page d'activation de l'abonnement.
 *
 * ## Ce que cette page N'EST PLUS
 *
 * Elle a d'abord remplacé l'espace entier : sans abonnement, toutes les pages
 * répondaient 402 et l'interface affichait ceci à la place. La cliente l'a
 * corrigé le jour même, et elle avait raison sur les deux points.
 *
 * Le premier est une question de justice : quelqu'un dont l'abonnement s'arrête
 * doit continuer à voir les documents qu'il a commandés. Les lui cacher, c'est
 * reprendre ce qui est livré.
 *
 * Le second est une question d'utilité : la barrière ne protégeait rien que le
 * solde ne protégeait déjà. Ce qui coûte de l'argent, c'est produire une étude,
 * et cela reste tenu par le portefeuille. Fermer la lecture ajoutait de la gêne
 * sans ajouter de sûreté.
 *
 * C'est donc une page comme les autres, dans la coquille, atteignable depuis le
 * bandeau et depuis la page Abonnement.
 *
 * ## Le retour de Stripe
 *
 * `?paiement=ok` n'est **pas** une preuve de paiement : c'est le navigateur qui
 * revient, et n'importe qui peut taper cette adresse. Ce qui ouvre l'accès,
 * c'est le webhook signé reçu par le serveur. On interroge donc le serveur
 * jusqu'à ce qu'il le dise, plutôt que de croire l'URL.
 */
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { espaceApi, ErreurApi } from "../api";
import { ARRET_EN_UNE_PHRASE, CONTACT, ENGAGEMENT_MINIMUM } from "../engagement";
import { CLE_MOI, useMoi } from "../useMoi";
import {
  Bandeau,
  Carte,
  ErreurDeChargement,
  Squelette,
} from "../composants/Interface";
import * as f from "../format";

function retourDeStripe(): "ok" | "abandon" | "" {
  const valeur = new URLSearchParams(window.location.search).get("paiement");
  return valeur === "ok" || valeur === "abandon" ? valeur : "";
}

/** Formule pré-choisie dans l'adresse, si l'on vient de la page Abonnement.
 *
 * Elle n'est pas VALIDÉE ici : le code est comparé au catalogue rendu par le
 * serveur, et un code inconnu ne sélectionne simplement rien. Un paramètre
 * d'URL ne doit jamais décider seul de ce qui sera facturé — c'est le serveur
 * qui rattache le tarif Stripe au code, et lui seul. */
function formulePreChoisie(): string {
  return new URLSearchParams(window.location.search).get("formule") ?? "";
}

/** Combien de fois redemander l'état avant de renoncer, à une seconde d'écart.
 *
 *  Le webhook arrive en général en une à deux secondes, mais il traverse le
 *  réseau de Stripe : promettre l'ouverture immédiate serait mentir un jour sur
 *  dix. Vingt tentatives laissent une marge confortable sans faire tourner une
 *  page indéfiniment. */
const TENTATIVES_MAX = 20;

export function Souscription() {
  const lectureMoi = useMoi();
  const { data: moi } = lectureMoi;
  const cache = useQueryClient();
  const retour = retourDeStripe();

  const [tentatives, setTentatives] = useState(0);
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const [choisie, setChoisie] = useState(formulePreChoisie);

  const lectureFormules = useQuery({
    queryKey: ["espace", "formules"],
    queryFn: espaceApi.formules,
  });
  const { data: catalogue } = lectureFormules;

  // L'attente est DÉDUITE, pas mémorisée.
  //
  // Elle vivait dans un état que deux effets remettaient à `false` — ce que
  // `react-hooks/set-state-in-effect` signale à juste titre : un état qui ne
  // fait que recopier d'autres valeurs peut les contredire le temps d'un rendu.
  // Ici les trois conditions se lisent directement, et l'abonnement rendu par
  // le serveur reste seul juge de la fin de l'attente.
  const attente =
    retour === "ok" && !moi?.abonnement && tentatives < TENTATIVES_MAX;
  const abandonne =
    retour === "ok" && !moi?.abonnement && tentatives >= TENTATIVES_MAX;

  useEffect(() => {
    if (!attente) return;
    const minuteur = window.setTimeout(() => {
      void cache.invalidateQueries({ queryKey: CLE_MOI });
      setTentatives((n) => n + 1);
    }, 1000);
    return () => window.clearTimeout(minuteur);
  }, [attente, tentatives, cache]);

  // Sans le compte, cette page ne sait ni s'il y a un abonnement, ni lequel
  // proposer. Elle attendait indéfiniment sous un squelette quand la lecture
  // avait échoué : un échec se DIT (règle 1).
  if (!moi) {
    return lectureMoi.isError ? (
      <ErreurDeChargement quoi="votre compte" erreur={lectureMoi.error} />
    ) : (
      <Squelette lignes={4} />
    );
  }

  const formules = catalogue?.formules ?? [];
  const attendue = moi.souscription_en_attente;
  const code = choisie || attendue?.code || "";
  const detail = formules.find((formule) => formule.code === code);

  async function payer() {
    if (!code) {
      setErreur("Choisissez une formule pour continuer.");
      return;
    }
    setErreur("");
    setEnvoi(true);
    try {
      const { adresse } = await espaceApi.ouvrirLePaiement(code);
      // Redirection pleine page, et non un cadre : la page de paiement doit
      // afficher SON domaine dans la barre d'adresse. C'est ce qui permet de
      // vérifier à qui l'on donne sa carte.
      window.location.href = adresse;
    } catch (cause) {
      setEnvoi(false);
      setErreur(
        cause instanceof ErreurApi
          ? cause.message
          : "Le paiement est momentanément indisponible. Réessayez.",
      );
    }
  }

  if (moi.abonnement) {
    return (
      <Carte titre="Votre abonnement est actif">
        <p className="carte-note">
          Formule <b>{moi.abonnement.formule}</b> —{" "}
          {f.montant(moi.abonnement.prix_mensuel_cents)} par mois,{" "}
          {moi.abonnement.credits_par_echeance} crédit
          {moi.abonnement.credits_par_echeance > 1 ? "s" : ""} déposés chaque
          mois. Il se reconduit tout seul, avec un engagement minimum de{" "}
          {ENGAGEMENT_MINIMUM}. L'arrêt se fait sur demande, par e-mail à{" "}
          <a href={`mailto:${CONTACT}`}>{CONTACT}</a>&nbsp;: la page{" "}
          <Link to="/espace/abonnement" className="bandeau-lien">
            Abonnement
          </Link>{" "}
          dit où en est le vôtre.
        </p>
      </Carte>
    );
  }

  if (attente) {
    return (
      <Carte titre="Nous enregistrons votre paiement…">
        <p className="carte-note">
          Stripe nous confirme la souscription à l'instant. Cette page s'ouvrira
          toute seule&nbsp;: inutile de recharger.
        </p>
        <div className="souscription-attente" role="status" aria-live="polite">
          <span className="souscription-point" aria-hidden="true" />
          Vérification en cours ({tentatives}/{TENTATIVES_MAX})
        </div>
      </Carte>
    );
  }

  // Vingt tentatives sans confirmation. On ne dit pas « échec » : le paiement
  // est passé chez Stripe, c'est sa confirmation chez nous qui tarde. Annoncer
  // un échec ferait payer une seconde fois.
  //
  // Et c'est pour la même raison que le FORMULAIRE DE PAIEMENT NE REVIENT PAS
  // ICI. Il se réaffichait, actif, juste sous la phrase « rien ne sera prélevé
  // deux fois » : un bouton « Régler 129 € par mois » sous la promesse de ne
  // pas payer deux fois, c'est le seul endroit de la plateforme où l'écran
  // offrait lui-même le double prélèvement qu'il jurait d'éviter (audit du
  // 19/11/2026). Ce qui reste : revérifier, ou écrire.
  if (abandonne) {
    return (
      <Bandeau titre="Confirmation en retard">
        Votre paiement est bien enregistré chez Stripe, mais sa confirmation
        chez nous tarde. Rien n'est perdu, et rien ne sera prélevé deux
        fois&nbsp;: ne réglez pas une seconde fois.
        <p style={{ marginTop: "var(--e-3)" }}>
          <button
            type="button"
            className="bouton bouton-contour bouton-sm"
            onClick={() => setTentatives(0)}
          >
            Vérifier à nouveau
          </button>
        </p>
        <p style={{ marginTop: "var(--e-2)" }}>
          Si l'abonnement reste inactif dans quelques minutes, écrivez-nous à{" "}
          <a href={`mailto:${CONTACT}`}>{CONTACT}</a>.
        </p>
      </Bandeau>
    );
  }

  return (
    <>
      {retour === "abandon" && (
        <Bandeau titre="Paiement interrompu">
          Rien n'a été débité. Vous pouvez reprendre quand vous voulez.
        </Bandeau>
      )}
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
      {lectureFormules.isError && (
        <ErreurDeChargement
          quoi="les formules"
          erreur={lectureFormules.error}
          perimees={lectureFormules.isRefetchError}
        />
      )}

      {/* Sans le catalogue, pas de carte de paiement : une grille vide sous
          « Choisissez une formule » se lirait « aucune formule n'existe ». */}
      {catalogue && (
      <Carte
        titre="Activer votre abonnement"
        note="Vos crédits sont déposés dès le paiement accepté, sans attendre personne."
      >
        {/* Un groupe radio NOMMÉ : sans `fieldset` ni légende, un lecteur
            d'écran annonçait des boutons isolés, sans dire ce qu'on y
            choisissait. La légende est masquée à l'œil — le titre de la
            carte le dit déjà. */}
        <fieldset className="souscription-formules">
          <legend className="visuellement-cache">Formule d'abonnement</legend>
          <div className="souscription-grille">
            {formules.map((formule) => (
              <label
                key={formule.code}
                className={
                  formule.code === code
                    ? "souscription-formule choisie"
                    : "souscription-formule"
                }
              >
                <input
                  type="radio"
                  name="formule"
                  value={formule.code}
                  checked={formule.code === code}
                  onChange={() => setChoisie(formule.code)}
                />
                <span className="souscription-formule-nom">
                  {formule.libelle}
                </span>
                <span className="souscription-formule-prix">
                  {f.montant(formule.prix_mensuel_cents)}
                  <small> / mois</small>
                </span>
                <span className="souscription-formule-credits">
                  {formule.credits_par_echeance} crédit
                  {formule.credits_par_echeance > 1 ? "s" : ""} par mois, soit{" "}
                  {f.montant(formule.cout_par_livrable_cents)} par livrable
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        {/* Pendant l'ouverture du paiement, une lame de lumière traverse le
            bouton (`.bouton-chargement`) : le texte dit « Ouverture… », le
            balayage dit seulement que ça travaille. La flèche nichée n'est
            là que quand le bouton mène quelque part. */}
        <button
          type="button"
          className={
            envoi
              ? "bouton bouton-principal bouton-chargement souscription-payer"
              : "bouton bouton-principal souscription-payer"
          }
          onClick={payer}
          disabled={envoi || !code}
        >
          {envoi
            ? "Ouverture du paiement…"
            : detail
              ? `Régler ${f.montant(detail.prix_mensuel_cents)} par mois`
              : "Choisissez une formule"}
          {detail && !envoi && (
            <span className="bouton__icone" aria-hidden="true">
              ↗
            </span>
          )}
        </button>

        {/* Les conditions d'arrêt, dites AVANT la carte bancaire, et dans les
            mots du serveur (`engagement.ts`). Ce pied promettait un arrêt
            « en un clic, sans préavis ni justification » que
            `arreter_l_abonnement` refuse toujours. */}
        <p className="souscription-pied">
          Paiement par carte, traité par Stripe. Nous ne voyons jamais votre
          numéro de carte. {ARRET_EN_UNE_PHRASE} Un mois entamé n'est pas
          remboursé&nbsp;: vous en gardez l'accès et les crédits jusqu'à son
          terme.
        </p>
      </Carte>
      )}
    </>
  );
}
