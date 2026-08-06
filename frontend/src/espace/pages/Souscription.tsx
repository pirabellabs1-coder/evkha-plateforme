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
import { espaceApi, ErreurApi } from "../api";
import { CLE_MOI, useMoi } from "../useMoi";
import { Bandeau, Carte, Squelette } from "../composants/Interface";
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
  const { data: moi } = useMoi();
  const cache = useQueryClient();
  const retour = retourDeStripe();

  const [tentatives, setTentatives] = useState(0);
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const [choisie, setChoisie] = useState(formulePreChoisie);

  const { data: catalogue } = useQuery({
    queryKey: ["espace", "formules"],
    queryFn: espaceApi.formules,
  });

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

  if (!moi) return <Squelette lignes={4} />;

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
          mois. Il se reconduit tout seul&nbsp;; vous pouvez l'arrêter quand
          vous voulez depuis la page Abonnement.
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

  return (
    <>
      {retour === "abandon" && (
        <Bandeau titre="Paiement interrompu">
          Rien n'a été débité. Vous pouvez reprendre quand vous voulez.
        </Bandeau>
      )}
      {/* Vingt tentatives sans confirmation. On ne dit pas « échec » : le
          paiement est passé chez Stripe, c'est sa confirmation chez nous qui
          tarde. Annoncer un échec ferait payer une seconde fois. */}
      {abandonne && (
        <Bandeau titre="Confirmation en retard">
          Votre paiement est bien enregistré chez Stripe, mais sa confirmation
          chez nous tarde. Rechargez la page dans une minute — si l'abonnement
          reste inactif, écrivez-nous&nbsp;: rien n'est perdu, et rien ne sera
          prélevé deux fois.
        </Bandeau>
      )}
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}

      <Carte
        titre="Activer votre abonnement"
        note="Vos crédits sont déposés dès le paiement accepté, sans attendre personne."
      >
        <div className="souscription-formules">
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
              <span className="souscription-formule-nom">{formule.libelle}</span>
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

        <button
          type="button"
          className="souscription-payer"
          onClick={payer}
          disabled={envoi || !code}
        >
          {envoi
            ? "Ouverture du paiement…"
            : detail
              ? `Régler ${f.montant(detail.prix_mensuel_cents)} par mois`
              : "Choisissez une formule"}
        </button>

        <p className="souscription-pied">
          Paiement par carte, traité par Stripe. Nous ne voyons jamais votre
          numéro de carte. L'abonnement se reconduit chaque mois et s'arrête dès
          que vous le demandez, sans préavis ni justification.
        </p>
      </Carte>
    </>
  );
}
