/** Formules, changement d'abonnement et achat de crédits (§9.6).
 *
 * Aucun encaissement : le prestataire de paiement n'est pas branché. Un bouton
 * qui prétendrait débiter une carte serait un mensonge, un bouton inerte une
 * impasse. La demande est donc **enregistrée** et EVKHA la traite — ce que
 * l'interface annonce explicitement, sans laisser croire à un paiement.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ErreurApi, espaceApi, type FormuleOffre } from "../api";
import * as f from "../format";
import { peut, useMoi } from "../useMoi";
import {
  Bandeau,
  Carte,
  Champ,
  Pastille,
  Squelette,
  Vide,
} from "../composants/Interface";

function CarteFormule({
  formule,
  peutEngager,
  enCours,
  onChoisir,
}: {
  formule: FormuleOffre;
  peutEngager: boolean;
  enCours: boolean;
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
          Demander cette formule
        </button>
      )}
    </div>
  );
}

export function Abonnement() {
  const { data: moi } = useMoi();
  const cache = useQueryClient();
  const [quantite, setQuantite] = useState("1");
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

  const demandes = suivi?.demandes ?? [];
  const ouverte = (type: string) =>
    demandes.some((d) => d.type === type && d.statut === "ouverte");

  return (
    <>
      <Bandeau titre="Comment fonctionne le paiement">
        Le règlement par carte n'est pas encore activé sur la plateforme. Vos
        demandes de changement de formule et d'achat de crédits sont
        <strong> enregistrées ici</strong>, et EVKHA vous recontacte pour les
        finaliser. Vous suivez leur avancement en bas de page.
      </Bandeau>

      <Carte
        titre="Les formules"
        note="Un crédit correspond à un livrable produit."
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
                enCours={ouverte("changement_formule") || envoyer.isPending}
                onChoisir={(code) =>
                  envoyer.mutate({ type: "changement_formule", formule: code })
                }
              />
            ))}
          </div>
        )}
        {ouverte("changement_formule") && (
          <p className="carte-note" style={{ marginTop: "var(--e-4)" }}>
            Une demande de changement est déjà en cours de traitement.
          </p>
        )}
      </Carte>

      <Carte
        titre="Crédits additionnels"
        note="Hors abonnement, au tarif de votre formule en cours."
      >
        {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
        <form
          onSubmit={(evenement) => {
            evenement.preventDefault();
            envoyer.mutate({
              type: "credits_additionnels",
              quantite: Number(quantite),
            });
          }}
          style={{
            display: "flex",
            gap: "var(--e-4)",
            alignItems: "flex-end",
            flexWrap: "wrap",
          }}
        >
          <div style={{ maxWidth: 200 }}>
            <Champ
              libelle="Nombre de crédits"
              name="quantite"
              type="number"
              min={1}
              max={50}
              required
              value={quantite}
              onChange={(evenement) => setQuantite(evenement.target.value)}
              aide="Un crédit = un livrable."
            />
          </div>
          <button
            type="submit"
            className="bouton bouton-principal"
            disabled={
              !peutEngager || ouverte("credits_additionnels") || envoyer.isPending
            }
            title={
              peutEngager
                ? undefined
                : "Seul un propriétaire peut engager l'organisation."
            }
          >
            {envoyer.isPending ? "Envoi…" : "Demander ces crédits"}
          </button>
        </form>
        {!peutEngager && (
          <p className="carte-note" style={{ marginTop: "var(--e-4)" }}>
            Votre rôle ne permet pas d'engager l'organisation. Demandez à un
            propriétaire de votre équipe.
          </p>
        )}
        {ouverte("credits_additionnels") && (
          <p className="carte-note" style={{ marginTop: "var(--e-4)" }}>
            Une demande d'achat est déjà en cours de traitement.
          </p>
        )}
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
