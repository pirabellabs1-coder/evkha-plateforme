/** Crédits et abonnement (§9.6) : solde, formule, consommation ligne par ligne. */
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { espaceApi, type Mouvement } from "../api";
import * as f from "../format";
import { useMoi } from "../useMoi";
import { Bandeau, Carte, Chiffre, Squelette, Vide } from "../composants/Interface";
import { Autonomie } from "../composants/Autonomie";
import { telechargerJournal } from "../journal";
import { Colonnes } from "../../viz/Graphiques";

/** Un mouvement d'entrée se lit en vert, une sortie en rouge — mais le SIGNE
 *  porte déjà l'information. La couleur n'est qu'un renfort : sans elle, le
 *  tableau reste lisible. */
function Quantite({ mouvement }: { mouvement: Mouvement }) {
  const entree = mouvement.quantite > 0;
  return (
    <td className={`nombre ${entree ? "positif" : "negatif"}`}>
      {f.quantiteSignee(mouvement.quantite)}
    </td>
  );
}

export function Credits() {
  const { data: moi } = useMoi();
  const { data, isPending } = useQuery({
    queryKey: ["espace", "credits"],
    queryFn: espaceApi.credits,
  });
  const { data: conso } = useQuery({
    queryKey: ["espace", "consommation"],
    queryFn: espaceApi.consommation,
  });

  // Achat de credits a l'unite. Le tarif est celui de la formule, cote
  // serveur : on n'envoie que le NOMBRE. Envoyer un prix depuis ici
  // reviendrait a laisser choisir combien payer.
  const [quantite, setQuantite] = useState(1);
  const [erreurAchat, setErreurAchat] = useState("");
  const achat = useMutation({
    mutationFn: () => espaceApi.acheterDesCredits(quantite),
    // On ne remplace pas la page : Stripe s'ouvre, et le retour repasse par
    // `/espace/credits`. Les credits n'arrivent qu'au webhook, jamais au retour
    // du navigateur — celui-ci peut etre tape a la main par n'importe qui.
    onSuccess: (reponse) => {
      window.location.href = reponse.url;
    },
    onError: (cause: unknown) =>
      setErreurAchat(
        cause instanceof Error ? cause.message : "Achat impossible pour l'instant.",
      ),
  });

  const tarif = moi?.abonnement?.prix_credit_supplementaire_cents ?? 0;
  const abonne = Boolean(moi?.abonnement);

  const mouvements = data?.mouvements ?? [];
  const consommes = mouvements
    .filter((m) => m.type === "debit")
    .reduce((total, m) => total + Math.abs(m.quantite), 0);
  const rembourses = mouvements
    .filter((m) => m.type === "remboursement")
    .reduce((total, m) => total + m.quantite, 0);

  return (
    <>
      <div className="grille-chiffres">
        <Chiffre
          libelle="Solde"
          valeur={f.nombre(data?.solde ?? moi?.credits.solde ?? 0)}
          detail="Aucun découvert possible"
          accent
        />
        <Chiffre
          libelle="Consommés"
          valeur={f.nombre(consommes)}
          detail="Sur les mouvements affichés"
        />
        <Chiffre
          libelle="Restitués"
          valeur={f.nombre(rembourses)}
          detail="Études abandonnées définitivement"
        />
        <Chiffre
          libelle="Dotation mensuelle"
          valeur={f.nombre(moi?.abonnement?.credits_par_echeance ?? 0)}
          detail={
            moi?.abonnement
              ? `${f.montant(
                  moi.abonnement.prix_mensuel_cents,
                  moi.abonnement.devise,
                )} par mois`
              : "Aucun abonnement actif"
          }
        />
      </div>

      {conso && <Autonomie rythme={conso.rythme} />}

      {/* Le journal répond à « qu'ai-je consommé le 12 mars ». Il ne répond pas
          à « est-ce que je consomme plus qu'avant » : il faudrait additionner
          de tête, mois par mois. Les colonnes le montrent d'un coup d'œil.

          L'agrégation vient du serveur, comme l'autonomie ci-dessus : la
          refaire ici ferait deux calculs, et deux occasions de se contredire. */}
      {/* Le tarif du credit supplementaire figure sur la page publique depuis
          le premier jour. Il n'y avait aucun moyen d'en acheter : un abonne a
          court de credits en milieu de mois n'avait qu'a attendre le suivant. */}
      {abonne && tarif > 0 && (
        <Carte
          titre="Besoin de crédits supplémentaires ?"
          note={`${f.montant(tarif)} le crédit, au tarif de votre formule. Ces crédits-là n'expirent pas.`}
        >
          {erreurAchat && (
            <Bandeau ton="echec" titre="Achat impossible">
              {erreurAchat}
            </Bandeau>
          )}
          <div className="achat-credits">
            <label htmlFor="quantite-credits">Nombre de crédits</label>
            <input
              id="quantite-credits"
              type="number"
              min={1}
              max={50}
              value={quantite}
              onChange={(evenement) =>
                setQuantite(Math.max(1, Math.min(50, Number(evenement.target.value) || 1)))
              }
            />
            <span className="achat-credits-total">
              soit {f.montant(tarif * quantite)}
            </span>
            <button
              type="button"
              className="bouton"
              onClick={() => {
                setErreurAchat("");
                achat.mutate();
              }}
              disabled={achat.isPending}
            >
              {achat.isPending ? "Ouverture du paiement…" : "Acheter"}
            </button>
          </div>
        </Carte>
      )}

      {conso && (conso.total_recu > 0 || conso.total_consomme > 0) && (
        <Carte
          titre="Douze derniers mois"
          note={`${conso.total_recu} crédits reçus, ${conso.total_consomme} consommés.`}
        >
          <Colonnes
            abscisses={conso.mois.map((m) => m.libelle)}
            series={[
              {
                cle: "recus",
                libelle: "Reçus",
                valeurs: conso.mois.map((m) => m.recus),
              },
              {
                cle: "consommes",
                libelle: "Consommés",
                valeurs: conso.mois.map((m) => m.consommes),
              },
              // Affichée seulement s'il y a eu des pertes : une troisième série
              // constamment à zéro encombrerait la légende sans rien apprendre.
              // Quand elle apparaît, elle est le meilleur argument pour changer
              // de formule — et la masquer reviendrait à cacher au client ce
              // qu'il perd.
              ...(conso.total_expire > 0
                ? [
                    {
                      cle: "expires",
                      libelle: "Perdus",
                      valeurs: conso.mois.map((m) => m.expires),
                    },
                  ]
                : []),
            ]}
            unite="crédits"
          />
        </Carte>
      )}

      {moi?.abonnement && (
        <Carte
          titre="Votre formule"
          note="Modifiable depuis la page Abonnement."
        >
          <div className="grille-chiffres">
            <div>
              <div className="chiffre-libelle">Formule</div>
              <div style={{ fontWeight: 600, marginTop: "var(--e-1)" }}>
                {moi.abonnement.formule}
              </div>
            </div>
            <div>
              <div className="chiffre-libelle">Coût par livrable inclus</div>
              <div style={{ fontWeight: 600, marginTop: "var(--e-1)" }}>
                {moi.abonnement.credits_par_echeance > 0
                  ? f.montant(
                      Math.round(
                        moi.abonnement.prix_mensuel_cents /
                          moi.abonnement.credits_par_echeance,
                      ),
                      moi.abonnement.devise,
                    )
                  : "—"}
              </div>
            </div>
            {/* Le report des crédits n'est plus affiché.
                Il annonçait « Aucun report — les crédits non consommés
                expirent à l'échéance ». C'est exact, mais le dire sur l'écran
                des crédits, c'est rappeler une perte à quelqu'un qui vient
                consulter son solde. La cliente l'a retiré : « on n'a pas du
                tout besoin de ceci ou de le dire ».
                La règle, elle, ne change pas — l'expiration reste appliquée par
                `credits.py`. On cesse de l'afficher, pas de la respecter. */}
          </div>
        </Carte>
      )}

      <Carte
        titre="Consommation"
        note="Chaque mouvement est enregistré : date, motif, document concerné."
        action={
          mouvements.length > 0 ? (
            <button
              type="button"
              className="bouton bouton-contour bouton-sm"
              onClick={() => telechargerJournal(mouvements)}
            >
              Exporter en CSV
            </button>
          ) : undefined
        }
      >
        {isPending ? (
          <Squelette lignes={5} />
        ) : mouvements.length === 0 ? (
          <Vide
            icone="◐"
            titre="Aucun mouvement"
            texte="Votre journal se remplira à la première dotation puis à chaque
                   génération lancée."
          />
        ) : (
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Nature</th>
                  <th scope="col">Motif</th>
                  <th scope="col" style={{ textAlign: "right" }}>
                    Crédits
                  </th>
                </tr>
              </thead>
              <tbody>
                {mouvements.map((mouvement) => (
                  <tr key={mouvement.id}>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {f.dateHeure(mouvement.date)}
                    </td>
                    <td>{f.typeMouvement(mouvement.type)}</td>
                    <td>
                      {mouvement.motif}
                      {mouvement.auteur && (
                        <div className="carte-note">Par {mouvement.auteur}</div>
                      )}
                    </td>
                    <Quantite mouvement={mouvement} />
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
