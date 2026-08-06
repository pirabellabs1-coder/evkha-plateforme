/** Tableau de bord de l'espace client (§9.4, §9.6). */
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { espaceApi } from "../api";
import * as f from "../format";
import { useMoi } from "../useMoi";
import { Carte, Chiffre, Pastille, Squelette, Vide } from "../composants/Interface";
import { Colonnes } from "../../viz/Graphiques";
import { Autonomie } from "../composants/Autonomie";

export function TableauDeBord() {
  const { data: moi, isPending: chargeMoi } = useMoi();
  const { data: donneesLivrables, isPending: chargeLivrables } = useQuery({
    queryKey: ["espace", "livrables"],
    queryFn: espaceApi.livrables,
  });
  const { data: conso } = useQuery({
    queryKey: ["espace", "consommation"],
    queryFn: espaceApi.consommation,
  });

  // Un graphique de douze mois vides ne dit rien et occupe la moitie de
  // l'ecran. On ne l'affiche qu'a partir du moment ou il y a quelque chose a
  // lire — sinon le guide de demarrage est plus utile.
  const aDeLHistorique =
    (conso?.total_recu ?? 0) > 0 || (conso?.total_consomme ?? 0) > 0;

  const livrables = donneesLivrables?.livrables ?? [];
  const enCours = livrables.filter((l) => l.statut === "running").length;
  const termines = livrables.filter((l) => l.statut === "done").length;
  const recents = livrables.slice(0, 5);

  if (chargeMoi) return <Squelette lignes={4} />;

  return (
    <>
      <div className="grille-chiffres">
        <Chiffre
          libelle="Crédits disponibles"
          valeur={f.nombre(moi?.credits.solde ?? 0)}
          detail={
            moi?.abonnement
              ? `${moi.abonnement.credits_par_echeance} par mois · ${f.montant(
                  moi.abonnement.prix_mensuel_cents,
                  moi.abonnement.devise,
                )}`
              : "Aucun abonnement actif"
          }
          accent
        />
        <Chiffre
          libelle="Documents produits"
          valeur={f.nombre(termines)}
          detail="Depuis l'ouverture du compte"
        />
        <Chiffre
          libelle="En production"
          valeur={f.nombre(enCours)}
          detail={enCours ? "Progression visible dans Livrables" : "Rien en cours"}
        />
        <Chiffre
          libelle="Formule"
          valeur={
            moi?.abonnement?.formule ??
            moi?.souscription_en_attente?.formule ??
            "—"
          }
          detail={
            moi?.abonnement
              ? moi.abonnement.renouvellement_actif
                ? `Depuis le ${f.date(moi.abonnement.debut_le)}`
                : "S'arrête à la fin de la période"
              : // « En cours de validation » : personne ne valide plus rien.
                // La formule choisie à l'inscription n'attend qu'un règlement,
                // et le bouton est à un clic. Annoncer une validation ferait
                // attendre un appel qui ne viendra pas.
                (
                  <Link to="/espace/souscription">
                    {moi?.souscription_en_attente
                      ? "À régler pour activer"
                      : "Choisir une formule"}
                  </Link>
                )
          }
        />
      </div>

      {/* La question qu'un abonné se pose vraiment : « ma formule est-elle la
          bonne ? » Le journal ligne à ligne n'y répond pas — il faut
          additionner de tête. Les colonnes la rendent lisible d'un coup d'œil.

          L'agrégation vient du serveur : la refaire ici produirait un second
          calcul qui finirait par contredire le solde affiché plus haut. */}
      {/* Placée avant le graphique : le graphique montre le passé, celle-ci
          dit ce qu'il implique. C'est la seconde qui appelle une décision. */}
      {conso && <Autonomie rythme={conso.rythme} />}

      {aDeLHistorique && conso && (
        <Carte
          titre="Vos crédits, mois par mois"
          note={
            `Sur douze mois : ${conso.total_recu} reçus, ` +
            `${conso.total_consomme} consommés.`
          }
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

      {/* Un espace client dont on ne comprend pas l'usage est un espace client
          raté. Ce guide reste affiché tant qu'aucun document n'a été produit,
          puis disparaît : une explication permanente devient du bruit. */}
      {termines === 0 && (
        <Carte
          titre="À quoi sert cet espace"
          note="Ces quatre étapes couvrent l'essentiel."
        >
          <div className="guide">
            {[
              [
                "Renseignez votre marque",
                "Votre logo et vos couleurs habillent automatiquement chaque document produit, sans les ressaisir à chaque étude.",
              ],
              [
                "Vérifiez votre solde",
                "Un crédit = un livrable. Une commande est bloquée si le solde ne la couvre pas : aucun découvert n'est possible.",
              ],
              [
                "Commandez",
                "Choisissez le livrable, répondez au questionnaire : la production démarre aussitôt et un crédit est débité.",
              ],
              [
                "Suivez la production",
                "Constitution du socle de données, puis chapitre par chapitre. Vous voyez l'avancement en temps réel.",
              ],
              [
                "Téléchargez",
                "Word et PDF, sans limite de nombre, à vos couleurs et sans mention d'EVKHA.",
              ],
            ].map(([titre, texte], index) => (
              <div className="guide-etape" key={titre}>
                <span className="guide-numero" aria-hidden="true">
                  {index + 1}
                </span>
                <div>
                  <p className="guide-titre">{titre}</p>
                  <p className="guide-texte">{texte}</p>
                </div>
              </div>
            ))}
          </div>
          <Link
            to="/espace/commander"
            className="bouton bouton-principal"
            style={{ marginTop: "var(--e-5)" }}
          >
            Commander mon premier document
          </Link>
        </Carte>
      )}

      <Carte
        titre="Derniers livrables"
        note="Les cinq documents les plus récents."
        action={
          <Link to="/espace/livrables" className="bouton bouton-contour bouton-sm">
            Tout voir
          </Link>
        }
      >
        {chargeLivrables ? (
          <Squelette />
        ) : recents.length === 0 ? (
          <Vide
            titre="Aucun document pour le moment"
            texte="Vos études apparaîtront ici dès la première commande lancée. Vous
                   pourrez les télécharger en Word et en PDF, sans limite de nombre."
          />
        ) : (
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Document</th>
                  <th scope="col">Statut</th>
                  <th scope="col">Créé le</th>
                  <th scope="col">Fichiers</th>
                </tr>
              </thead>
              <tbody>
                {recents.map((livrable) => (
                  <tr key={livrable.id}>
                    <td>
                      <Link
                        to="/espace/livrables/$jobId"
                        params={{ jobId: livrable.id }}
                        style={{ fontWeight: 600, color: "var(--texte-fort)" }}
                      >
                        {f.typeLivrable(livrable.type)}
                      </Link>
                      <div className="carte-note">{livrable.offre}</div>
                    </td>
                    <td>
                      <Pastille statut={livrable.statut} />
                    </td>
                    <td>{f.date(livrable.cree_le)}</td>
                    <td>
                      {livrable.fichiers.length === 0 ? (
                        <span className="carte-note">En préparation</span>
                      ) : (
                        livrable.fichiers.map((fichier) => (
                          <a
                            key={fichier.kind}
                            className="bouton bouton-discret bouton-sm"
                            href={fichier.url}
                          >
                            {fichier.kind.toUpperCase()}
                          </a>
                        ))
                      )}
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
