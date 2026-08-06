/** Écran qui remplace l'espace tant que la souscription n'est pas réglée.
 *
 * Il ne « masque » rien : le serveur refuse déjà chaque vue de l'espace par un
 * 402 `souscription_requise`. Cet écran existe pour que le refus soit lisible.
 * Sans lui, la personne verrait une succession d'erreurs sans savoir laquelle
 * agir — et la première chose qu'elle a faite après son inscription serait un
 * échec.
 *
 * Le retour de Stripe est traité ici, et c'est la partie subtile : `?paiement=ok`
 * n'est **pas** une preuve de paiement. C'est le navigateur qui revient, et
 * n'importe qui peut taper cette adresse. Ce qui ouvre l'espace, c'est le
 * webhook signé reçu par le serveur — donc on interroge le serveur jusqu'à ce
 * qu'il le dise, plutôt que de croire l'URL.
 */
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { espaceApi, ErreurApi, jeton, type Moi } from "./api";
import { CLE_MOI } from "./useMoi";
import * as f from "./format";

/** Le paiement vient d'aboutir côté navigateur ? */
function retourDeStripe(): "ok" | "abandon" | "" {
  const valeur = new URLSearchParams(window.location.search).get("paiement");
  return valeur === "ok" || valeur === "abandon" ? valeur : "";
}

/** Combien de fois redemander l'état avant de renoncer, et à quel rythme.
 *
 *  Le webhook arrive en général en une à deux secondes, mais il traverse le
 *  réseau de Stripe : promettre l'ouverture immédiate serait mentir un jour sur
 *  dix. Vingt tentatives à une seconde laissent une marge confortable sans
 *  laisser tourner une page indéfiniment. */
const TENTATIVES_MAX = 20;

export function Souscription({ moi }: { moi: Moi }) {
  const cache = useQueryClient();
  const retour = retourDeStripe();
  const [attente, setAttente] = useState(retour === "ok");
  const [tentatives, setTentatives] = useState(0);
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  const { data: catalogue } = useQuery({
    queryKey: ["espace", "formules"],
    queryFn: espaceApi.formules,
  });

  const attendue = moi.souscription_en_attente;
  const [choisie, setChoisie] = useState(attendue?.code ?? "");
  const formules = catalogue?.formules ?? [];
  // La formule choisie à l'inscription est présélectionnée ; à défaut, celle
  // que la page partenaires met en avant n'est pas connue ici, donc on ne
  // choisit rien plutôt que de choisir à la place de la personne.
  const code = choisie || attendue?.code || "";
  const detail = formules.find((formule) => formule.code === code);

  // Interrogation du serveur après le retour de Stripe. C'est LUI qui décide,
  // pas l'adresse : `acces_ouvert` ne devient vrai qu'une fois le webhook signé
  // reçu et l'abonnement ouvert.
  useEffect(() => {
    if (!attente) return;
    if (tentatives >= TENTATIVES_MAX) {
      setAttente(false);
      setErreur(
        "Votre paiement est bien enregistré chez Stripe, mais son " +
          "enregistrement chez nous tarde. Rechargez la page dans une minute — " +
          "si l'espace reste fermé, écrivez-nous : rien n'est perdu.",
      );
      return;
    }
    const minuteur = window.setTimeout(() => {
      cache.invalidateQueries({ queryKey: CLE_MOI });
      setTentatives((n) => n + 1);
    }, 1000);
    return () => window.clearTimeout(minuteur);
  }, [attente, tentatives, cache]);

  async function payer() {
    if (!code) {
      setErreur("Choisissez une formule pour continuer.");
      return;
    }
    setErreur("");
    setEnvoi(true);
    try {
      const { adresse } = await espaceApi.ouvrirLePaiement(code);
      // Redirection pleine page vers Stripe : le paiement n'est pas encadré
      // dans notre site, et il ne doit pas l'être. La page de paiement doit
      // afficher son propre domaine dans la barre d'adresse — c'est ce qui
      // permet à la personne de vérifier à qui elle donne sa carte.
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

  async function deconnecter() {
    try {
      await espaceApi.deconnexion();
    } finally {
      jeton.effacer();
      window.location.href = "/espace/connexion";
    }
  }

  if (attente) {
    return (
      <div className="souscription">
        <div className="souscription-carte">
          <h1>Nous enregistrons votre paiement…</h1>
          <p className="souscription-sous">
            Stripe nous confirme la souscription à l'instant. Cet écran s'ouvrira
            tout seul&nbsp;: inutile de recharger.
          </p>
          <div className="souscription-attente" role="status" aria-live="polite">
            <span className="souscription-point" aria-hidden="true" />
            Vérification en cours ({tentatives}/{TENTATIVES_MAX})
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="souscription">
      <div className="souscription-carte">
        <div className="souscription-marque">
          <span className="espace-sceau" aria-hidden="true">
            E
          </span>
          <div>
            <div className="espace-marque-nom">EVKHA</div>
            <div className="espace-marque-sous">Espace client</div>
          </div>
        </div>

        <h1>Il ne manque que le règlement</h1>
        <p className="souscription-sous">
          Bonjour {moi.utilisateur.prenom || moi.utilisateur.email}, le compte de{" "}
          <b>{moi.organisation.raison_sociale}</b> est créé. Votre espace s'ouvre
          dès que l'abonnement est réglé, et vos crédits y sont déposés
          immédiatement.
        </p>

        {retour === "abandon" && (
          <p className="souscription-note">
            Paiement interrompu&nbsp;: rien n'a été débité. Vous pouvez reprendre
            quand vous voulez.
          </p>
        )}
        {erreur && (
          <p className="souscription-erreur" role="alert">
            {erreur}
          </p>
        )}

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
          numéro de carte. Résiliable à tout moment depuis votre espace.
        </p>

        <button type="button" className="souscription-sortir" onClick={deconnecter}>
          Se déconnecter
        </button>
      </div>
    </div>
  );
}
