/** Crédits et abonnement (§9.6) : solde, formule, consommation ligne par ligne. */
import { useQuery } from "@tanstack/react-query";
import { espaceApi, type Mouvement } from "../api";
import * as f from "../format";
import { useMoi } from "../useMoi";
import { Carte, Chiffre, Squelette, Vide } from "../composants/Interface";

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

      {moi?.abonnement && (
        <Carte titre="Votre formule" note="Modifiable en nous contactant.">
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
            <div>
              <div className="chiffre-libelle">Report des crédits</div>
              <div style={{ fontWeight: 600, marginTop: "var(--e-1)" }}>
                Aucun
              </div>
              <div className="carte-note">
                Les crédits non consommés expirent à l'échéance.
              </div>
            </div>
          </div>
        </Carte>
      )}

      <Carte
        titre="Consommation"
        note="Chaque mouvement est enregistré : date, motif, document concerné."
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
