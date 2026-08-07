/** Crédits et abonnement (§9.6) : solde, formule, consommation ligne par ligne. */
import { useQuery } from "@tanstack/react-query";
import { espaceApi, type Mouvement } from "../api";
import * as f from "../format";
import { useMoi } from "../useMoi";
import { Carte, Chiffre, Squelette, Vide } from "../composants/Interface";
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
                )} HT par mois`
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
            <div>
              <div className="chiffre-libelle">Report des crédits</div>
              <div style={{ fontWeight: 600, marginTop: "var(--e-1)" }}>
                {f.reportCredits(moi.abonnement.report_credits)}
              </div>
              <div className="carte-note">
                {/* Lu sur la formule, jamais écrit en dur : ce paragraphe
                    parle de l'argent du client, et il affirmait « Aucun » quel
                    que soit son abonnement réel. */}
                {moi.abonnement.report_credits === "aucun"
                  ? "Les crédits non consommés expirent à l'échéance."
                  : moi.abonnement.report_credits === "plafonne"
                    ? `Jusqu'à ${moi.abonnement.plafond_report} crédits non consommés sont conservés à l'échéance.`
                    : "Vos crédits non consommés sont conservés d'un mois sur l'autre."}
              </div>
            </div>
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
