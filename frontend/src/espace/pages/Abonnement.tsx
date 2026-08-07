/** Formules, changement d'abonnement, arrêt, et achat de crédits (§9.6).
 *
 * ## Ce qui a changé le 06/08/2026
 *
 * Cette page a longtemps enregistré des DEMANDES qu'un humain d'EVKHA devait
 * accorder — faute de prestataire de paiement. Stripe étant branché, elle agit :
 * changer de formule et arrêter l'abonnement se font ici, tout de suite, sans
 * l'intervention de personne.
 *
 * Le changement de formule ne se contentait d'ailleurs pas d'attendre un
 * humain : une fois accordé, il ne touchait pas Stripe. Le prélèvement suivant
 * repartait sur l'ancien tarif et le changement se défaisait tout seul à
 * l'échéance, sans que rien ne le signale.
 *
 * L'achat de crédits additionnels reste une demande, et c'est assumé : il
 * suppose un paiement à l'unité que rien n'encaisse encore. Le bandeau le dit
 * pour ce seul cas, au lieu d'annoncer que la plateforme entière ne prend pas
 * la carte.
 */
import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ErreurApi, espaceApi, type FormuleOffre } from "../api";
import * as f from "../format";
import { CLE_MOI, peut, useMoi } from "../useMoi";
import {
  Bandeau,
  Carte,
  Pastille,
  Squelette,
  Vide,
} from "../composants/Interface";

/** Ce que fait le bouton d'une formule, et donc ce qu'il doit annoncer.
 *
 * Trois situations, trois verbes. Elles disaient toutes « Demander cette
 * formule », y compris à quelqu'un qui n'a aucun abonnement et pour qui le
 * paiement est à un clic : on lui faisait ouvrir une demande, donc attendre un
 * appel qui ne viendrait pas.
 */
type Geste = "payer" | "changer" | "demander";

const LIBELLE_DU_GESTE: Record<Geste, string> = {
  payer: "Choisir cette formule",
  changer: "Passer à cette formule",
  demander: "Demander cette formule",
};

function CarteFormule({
  formule,
  peutEngager,
  enCours,
  geste,
  onChoisir,
}: {
  formule: FormuleOffre;
  peutEngager: boolean;
  enCours: boolean;
  geste: Geste;
  onChoisir: (code: string) => void;
}) {
  return (
    <div
      className={formule.actuelle ? "formule actuelle" : "formule"}
      aria-current={formule.actuelle ? "true" : undefined}
    >
      {formule.actuelle && (
        <span className="formule-ruban">Votre formule</span>
      )}
      <h3 className="formule-nom">{formule.libelle}</h3>
      <p className="formule-prix">
        {f.montant(formule.prix_mensuel_cents, formule.devise)}
        <span className="formule-periode"> / mois</span>
      </p>
      <ul className="formule-liste">
        <li>
          <strong>{f.credits(formule.credits_par_echeance)}</strong> inclus chaque
          mois
        </li>
        <li>
          Soit {f.montant(formule.cout_par_livrable_cents, formule.devise)} par
          livrable inclus
        </li>
        <li>{f.reportCredits(formule.report_credits)}</li>
        <li>
          {formule.regenerations_offertes} régénération
          {formule.regenerations_offertes > 1 ? "s" : ""} offerte
          {formule.regenerations_offertes > 1 ? "s" : ""}
        </li>
        {/* Dit AVANT le choix, pas après. Quelqu'un qui hésite à s'engager a
            besoin de savoir qu'il pourra s'arrêter — le lui apprendre une fois
            abonné, c'est le rassurer trop tard. */}
        <li>Arrêt possible à tout moment</li>
      </ul>
      {formule.actuelle ? (
        <span className="carte-note">Formule active</span>
      ) : (
        <button
          type="button"
          className="bouton bouton-noir bouton-sm"
          disabled={!peutEngager || enCours}
          title={
            peutEngager
              ? undefined
              : "Seul un propriétaire peut engager l'organisation."
          }
          onClick={() => onChoisir(formule.code)}
        >
          {LIBELLE_DU_GESTE[geste]}
        </button>
      )}
    </div>
  );
}

/** L'adresse à laquelle un abonné demande l'arrêt de son abonnement. */
const CONTACT = "contact@evkha.fr";

export function Abonnement() {
  const { data: moi } = useMoi();
  const cache = useQueryClient();
  const naviguer = useNavigate();
  const [erreur, setErreur] = useState("");

  const peutEngager = peut(moi, "gerer_abonnement");

  const { data: catalogue, isPending } = useQuery({
    queryKey: ["espace", "formules"],
    queryFn: espaceApi.formules,
  });
  const { data: suivi } = useQuery({
    queryKey: ["espace", "demandes"],
    queryFn: espaceApi.demandes,
  });

  const envoyer = useMutation({
    mutationFn: espaceApi.creerDemande,
    onSuccess: () => {
      setErreur("");
      void cache.invalidateQueries({ queryKey: ["espace", "demandes"] });
    },
    onError: (cause) =>
      setErreur(
        cause instanceof ErreurApi ? cause.message : "Demande impossible.",
      ),
  });

  // Les trois gestes qui ne passent plus par personne. Chacun réinvalide `moi`
  // ET le catalogue : la formule en cours est marquée dans les deux, et n'en
  // rafraîchir qu'un laisserait la page se contredire elle-même.
  const rafraichir = () => {
    void cache.invalidateQueries({ queryKey: CLE_MOI });
    void cache.invalidateQueries({ queryKey: ["espace", "formules"] });
  };
  const surEchec = (defaut: string) => (cause: unknown) =>
    setErreur(cause instanceof ErreurApi ? cause.message : defaut);

  const reprise = useMutation({
    mutationFn: espaceApi.reprendreAbonnement,
    onSuccess: () => {
      setErreur("");
      rafraichir();
    },
    onError: surEchec("Reprise impossible."),
  });

  const changement = useMutation({
    mutationFn: (code: string) => espaceApi.changerDeFormule(code),
    onSuccess: () => {
      setErreur("");
      rafraichir();
    },
    onError: surEchec("Changement de formule impossible."),
  });

  const demandes = suivi?.demandes ?? [];
  const ouverte = (type: string) =>
    demandes.some((d) => d.type === type && d.statut === "ouverte");

  const abonnement = moi?.abonnement ?? null;
  // Tarif du credit a l'unite, lu sur l'abonnement : le recopier ici en
  // ferait une seconde verite, et l'ecran finirait par annoncer un prix que
  // la caisse ne pratique pas.
  const tarifCredit = abonnement?.prix_credit_supplementaire_cents ?? 0;
  const parCarte = abonnement?.pilote_par_carte ?? false;
  // Sans abonnement on paie ; abonné par carte on change ; abonné à la main on
  // demande. Le verbe affiché sur le bouton suit ce geste (voir `CarteFormule`).
  const geste: Geste = !abonnement ? "payer" : parCarte ? "changer" : "demander";

  return (
    <>
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}

      {/* L'état de l'abonnement AVANT les formules : c'est la première chose
          qu'on vient vérifier ici, et c'est là que se prend la décision
          d'arrêter. */}
      {abonnement && (
        <Carte
          titre={
            abonnement.renouvellement_actif
              ? "Votre abonnement se reconduit chaque mois"
              : "Votre abonnement s'arrête à la fin de la période"
          }
          note={
            abonnement.renouvellement_actif
              ? `Formule ${abonnement.formule} — ${f.montant(
                  abonnement.prix_mensuel_cents,
                )} par mois, ${abonnement.credits_par_echeance} crédit${
                  abonnement.credits_par_echeance > 1 ? "s" : ""
                } déposés à chaque échéance.`
              : abonnement.fin_de_periode_le
                ? `Vous gardez votre accès et vos crédits jusqu'au ${f.date(
                    abonnement.fin_de_periode_le,
                  )}. Aucun prélèvement ne suivra.`
                : "Vous gardez votre accès et vos crédits jusqu'au terme de la période déjà réglée. Aucun prélèvement ne suivra."
          }
        >
          {!parCarte && (
            <p className="carte-note">
              Cet abonnement a été ouvert directement par EVKHA, sans carte
              enregistrée. Écrivez-nous pour le modifier.
            </p>
          )}
          {/* L'arrêt ne se fait plus d'un clic.
              La cliente a tranché le 07/08/2026 : « l'annulation doit se faire
              manuellement, donc la personne doit la contacter ». Elle traite
              ces demandes elle-même, au moins au début — c'est aussi
              l'occasion de retenir un abonné qui part.
              On le DIT ici, plutôt que de laisser un bouton qui échouerait :
              un abonné qui veut partir et se heurte à une erreur technique
              part quand même, en plus mécontent. */}
          {parCarte && peutEngager && abonnement.renouvellement_actif && (
            <p className="carte-note">
              Pour arrêter votre abonnement, écrivez-nous à{" "}
              <a href={`mailto:${CONTACT}`}>{CONTACT}</a> : nous nous en
              occupons et vous confirmons l'arrêt par retour. L'engagement
              minimum est de trois mois à compter de votre souscription.
            </p>
          )}
          {parCarte && peutEngager && !abonnement.renouvellement_actif && (
            <button
              type="button"
              className="bouton"
              onClick={() => reprise.mutate()}
              disabled={reprise.isPending}
            >
              {reprise.isPending ? "Reprise en cours…" : "Reprendre mon abonnement"}
            </button>
          )}
        </Carte>
      )}

      <Carte
        titre="Les formules"
        note={
          parCarte
            ? "Un crédit correspond à un livrable produit. Le changement prend effet immédiatement ; Stripe calcule la différence au prorata."
            : "Un crédit correspond à un livrable produit."
        }
      >
        {isPending ? (
          <Squelette lignes={4} />
        ) : (
          <div className="grille-formules">
            {(catalogue?.formules ?? []).map((formule) => (
              <CarteFormule
                key={formule.code}
                formule={formule}
                peutEngager={peutEngager}
                enCours={changement.isPending || envoyer.isPending}
                geste={geste}
                onChoisir={(code) => {
                  if (geste === "payer") {
                    // Aucun abonnement : le paiement est à un clic. Ouvrir une
                    // demande ici ferait attendre un appel qui ne viendra pas.
                    void naviguer({
                      to: "/espace/souscription",
                      search: { formule: code },
                    });
                  } else if (geste === "changer") {
                    changement.mutate(code);
                  } else {
                    // Abonnement ouvert à la main : aucun prélèvement à
                    // modifier, on retombe sur la demande écrite.
                    envoyer.mutate({ type: "changement_formule", formule: code });
                  }
                }}
              />
            ))}
          </div>
        )}
        {!parCarte && ouverte("changement_formule") && (
          <p className="carte-note" style={{ marginTop: "var(--e-4)" }}>
            Une demande de changement est déjà en cours de traitement.
          </p>
        )}

      </Carte>

      {/* Les crédits additionnels s'ACHÈTENT, ils ne se demandent plus.
          Ce bloc ouvrait une demande écrite — « EVKHA vous recontacte pour le
          règlement » — parce que rien n'encaissait un paiement ponctuel. Ce
          n'est plus vrai : l'achat passe par Stripe, à l'unité, au tarif de la
          formule. Faire patienter quelqu'un qui veut payer tout de suite lui
          fait perdre l'envie, et fait perdre la vente. */}
      <Carte
        titre="Crédits additionnels"
        note={`${f.montant(tarifCredit)} le crédit, au tarif de votre formule. Ces crédits-là n'expirent pas.`}
        action={
          <Link to="/espace/credits" className="bouton bouton-contour bouton-sm">
            Acheter des crédits
          </Link>
        }
      >
        <p className="carte-note">
          Le paiement est immédiat et n'affecte pas votre abonnement. Les
          crédits achetés à l'unité restent acquis&nbsp;: contrairement à la
          dotation mensuelle, ils n'expirent pas à la fin du mois.
        </p>
      </Carte>

      <Carte titre="Vos demandes" note="Historique et statut de traitement.">
        {demandes.length === 0 ? (
          <Vide
            icone="◇"
            titre="Aucune demande"
            texte="Vos demandes de changement de formule et d'achat de crédits apparaîtront ici."
          />
        ) : (
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Demande</th>
                  <th scope="col">Détail</th>
                  <th scope="col">Statut</th>
                </tr>
              </thead>
              <tbody>
                {demandes.map((demande) => (
                  <tr key={demande.id}>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {f.dateHeure(demande.date)}
                    </td>
                    <td>{f.typeDemande(demande.type)}</td>
                    <td>
                      {demande.formule_visee ||
                        (demande.quantite
                          ? f.credits(demande.quantite)
                          : "—")}
                      {demande.reponse && (
                        <div className="carte-note">{demande.reponse}</div>
                      )}
                    </td>
                    <td>
                      <Pastille
                        statut={
                          demande.statut === "traitee"
                            ? "done"
                            : demande.statut === "refusee"
                              ? "failed"
                              : "pending"
                        }
                        texte={
                          demande.statut === "traitee"
                            ? "Traitée"
                            : demande.statut === "refusee"
                              ? "Refusée"
                              : "En traitement"
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Carte>
    </>
  );
}
