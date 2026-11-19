/** Tableau de bord de l'espace client (§9.4, §9.6). */
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { espaceApi } from "../api";
import * as f from "../format";
import { useMoi } from "../useMoi";
import {
  Carte,
  Chiffre,
  ErreurDeChargement,
  Pastille,
  Squelette,
  Vide,
} from "../composants/Interface";
import { Colonnes } from "../../viz/Graphiques";
import { Autonomie } from "../composants/Autonomie";
import { AutresEtudes } from "../composants/AutresEtudes";
import { CelluleFichiers } from "../composants/EtatDesFichiers";

/** Ce qui s'écrit à la place d'un nombre qu'on n'a pas reçu.
 *
 *  Jamais « 0 » : un zéro est une réponse. L'écran lisait `?? 0` et `?? []`
 *  sans regarder l'échec, si bien qu'une session expirée ou une panne
 *  s'affichait « 0 crédit », « Aucun abonnement actif », « Aucun document » —
 *  un compte vide, montré à quelqu'un qui a payé (audit du 19/11/2026). */
const INCONNU = "—";

export function TableauDeBord() {
  const lectureMoi = useMoi();
  const { data: moi, isPending: chargeMoi } = lectureMoi;
  const lectureLivrables = useQuery({
    queryKey: ["espace", "livrables"],
    queryFn: espaceApi.livrables,
  });
  const { data: donneesLivrables, isPending: chargeLivrables } = lectureLivrables;
  const lectureConso = useQuery({
    queryKey: ["espace", "consommation"],
    queryFn: espaceApi.consommation,
  });
  const { data: conso } = lectureConso;

  // Un graphique de douze mois vides ne dit rien et occupe la moitie de
  // l'ecran. On ne l'affiche qu'a partir du moment ou il y a quelque chose a
  // lire — sinon le guide de demarrage est plus utile.
  const aDeLHistorique =
    (conso?.total_recu ?? 0) > 0 || (conso?.total_consomme ?? 0) > 0;

  const livrables = donneesLivrables?.livrables ?? [];
  const enCours = livrables.filter((l) => l.statut === "running").length;
  const termines = livrables.filter((l) => l.statut === "done").length;
  const recents = livrables.slice(0, 5);

  // Un acheteur a l'unite n'a ni formule ni credits a racheter : les deux
  // blocs qui servent aux abonnes lui sont fermes. Sans celui-ci, son espace
  // ne lui proposerait RIEN, alors que reprendre une etude est le parcours le
  // plus frequent du public direct.
  const aLUnite = moi?.organisation.type_de_compte === "a_l_unite";

  if (chargeMoi) return <Squelette lignes={4} />;

  // « Rien » ne se dit que sur une réponse REÇUE et à jour : sans elle, on ne
  // sait rien, et l'écrire serait répondre à la place du serveur (règle 1).
  const livrablesRecus = Boolean(donneesLivrables) && !lectureLivrables.isError;

  return (
    <>
      {/* Un bandeau par lecture : chacune peut échouer seule, et « votre
          compte » n'est pas « vos documents ». `perimees` distingue ce qui
          n'a jamais été reçu de ce dont seule la mise à jour a échoué. */}
      {lectureMoi.isError && (
        <ErreurDeChargement
          quoi="votre compte"
          erreur={lectureMoi.error}
          perimees={lectureMoi.isRefetchError}
        />
      )}
      {lectureLivrables.isError && (
        <ErreurDeChargement
          quoi="vos documents"
          erreur={lectureLivrables.error}
          perimees={lectureLivrables.isRefetchError}
        />
      )}
      {lectureConso.isError && (
        <ErreurDeChargement
          quoi="votre consommation"
          erreur={lectureConso.error}
          perimees={lectureConso.isRefetchError}
        />
      )}

      <div className="grille-chiffres">
        <Chiffre
          libelle="Crédits disponibles"
          valeur={moi ? f.nombre(moi.credits.solde) : INCONNU}
          detail={
            !moi
              ? undefined
              : moi.abonnement
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
          valeur={donneesLivrables ? f.nombre(termines) : INCONNU}
          detail="Depuis l'ouverture du compte"
        />
        <Chiffre
          libelle="En production"
          valeur={donneesLivrables ? f.nombre(enCours) : INCONNU}
          detail={
            !donneesLivrables
              ? undefined
              : enCours
                ? "Progression visible dans Livrables"
                : "Rien en cours"
          }
        />
        <Chiffre
          libelle="Formule"
          valeur={
            moi?.abonnement?.formule ??
            moi?.souscription_en_attente?.formule ??
            INCONNU
          }
          detail={
            !moi
              ? undefined
              : moi.abonnement
                ? moi.abonnement.renouvellement_actif
                  ? `Depuis le ${f.date(moi.abonnement.debut_le)}`
                  : "S'arrête à la fin de la période"
                : // « En cours de validation » : personne ne valide plus rien.
                  // La formule choisie à l'inscription n'attend qu'un règlement,
                  // et le bouton est à un clic. Annoncer une validation ferait
                  // attendre un appel qui ne viendra pas.
                  (
                    <Link to="/espace/souscription">
                      {moi.souscription_en_attente
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
      {aLUnite && <AutresEtudes />}

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
          puis disparaît : une explication permanente devient du bruit.
          « Aucun document produit » se lit sur la liste REÇUE : sur un échec,
          il proposait « Commander mon premier document » à quelqu'un qui en
          a cinquante. */}
      {livrablesRecus && termines === 0 && (
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

      {/* La carte n'existe que si elle a quelque chose de vrai à montrer : un
          chargement, des lignes, ou un vide REÇU. Sur un échec, le bandeau du
          haut parle ; une carte muette sous son titre se lirait comme « rien ». */}
      {(chargeLivrables || recents.length > 0 || livrablesRecus) && (
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
                      <CelluleFichiers
                        livrable={livrable}
                        classeBouton="bouton bouton-discret bouton-sm"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Carte>
      )}
    </>
  );
}
