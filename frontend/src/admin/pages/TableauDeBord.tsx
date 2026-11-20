/** Tableau de bord de la gérante (§10.1).
 *
 * EVKHA ne produit plus les documents à la main : cet écran ne lance rien, il
 * **montre**. Il se lit de haut en bas, dans l'ordre des questions qu'on se
 * pose en arrivant le matin :
 *
 * 1. **Où en sont mes ventes ?** — les chiffres clés de la période choisie ;
 * 2. **Qu'est-ce qui m'attend ?** — demandes, signalements, incidents, chacun
 *    avec son lien, et à côté les gestes les plus fréquents ;
 * 3. **Comment ça évolue ?** — production, crédits, revenu et coût, mois par
 *    mois ;
 * 4. **Qui consomme ?** — le classement des organisations, et l'état du parc.
 *
 * Aucune donnée n'est inventée et aucun appel n'est ajouté : les chiffres
 * viennent de la synthèse, de l'évolution et des organisations, comme avant ;
 * les deux files « demandes » et « signalements » sont celles que la coquille
 * lit déjà pour ses pastilles (même clé de cache — une seule requête pour les
 * deux).
 *
 * Une lecture en panne se DIT, ligne par ligne. Elle ne s'affiche jamais
 * « 0 € », « 0 demande » ni « Rien en attente » : c'est la règle 1 du dépôt,
 * sur l'écran qui sert justement à voir que quelque chose ne va pas.
 */
import { type ReactNode, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { adminApi } from "../api";
import { ActionsDePage } from "../ActionsDePage";
import { Icone, type NomIcone } from "../icones";
import * as f from "../../espace/format";
import {
  Bandeau,
  Carte,
  Chiffre,
  ErreurDeChargement,
  Squelette,
  Vide,
} from "../../espace/composants/Interface";
import { BarresClassement, Colonnes, Courbes } from "../../viz/Graphiques";

/** Les périodes proposées. `jours` sert aux chiffres instantanés, `mois` aux
 *  séries : un même choix pilote les deux, pour qu'ils parlent du même temps. */
type Periode = { libelle: string; jours: number; mois: number };

const PERIODES: Periode[] = [
  { libelle: "30 jours", jours: 30, mois: 3 },
  { libelle: "90 jours", jours: 90, mois: 6 },
  { libelle: "12 mois", jours: 365, mois: 12 },
  { libelle: "24 mois", jours: 730, mois: 24 },
];

/** Ce qu'une file d'attente a à dire, une fois sa lecture faite — ou ratée. */
type EtatDeFile =
  | { etat: "en cours" }
  | { etat: "en panne" }
  | { etat: "lue"; nombre: number; detail: string; ton: "calme" | "attend" | "grave" };

/** Une ligne de « Ce qui vous attend » : la file, où elle en est, et le lien
 *  vers l'écran qui la traite. La ligne ENTIÈRE est le lien. */
function LigneATraiter({
  icone,
  nom,
  file,
  children,
}: {
  icone: NomIcone;
  nom: string;
  file: EtatDeFile;
  /** Le `Link` qui enveloppe la ligne : chaque écran a sa route, écrite en
   *  toutes lettres là où elle est employée. */
  children: (contenu: ReactNode, classe: string) => ReactNode;
}) {
  const ton = file.etat === "lue" ? file.ton : file.etat === "en panne" ? "en-panne" : "calme";
  const contenu = (
    <>
      <span className="console-a-traiter-medaille">
        <Icone nom={icone} />
      </span>
      <span className="console-a-traiter-texte">
        <span className="console-a-traiter-nom">{nom}</span>
        <span className="console-a-traiter-detail">
          {file.etat === "lue"
            ? file.detail
            : file.etat === "en panne"
              ? "Compte indisponible : la lecture a échoué. Ouvrez l'écran pour vérifier."
              : "Lecture en cours…"}
        </span>
      </span>
      {/* Le nombre ne s'écrit que s'il a été REÇU : pas de « 0 » de repli. */}
      {file.etat === "lue" && (
        <span className="console-a-traiter-nombre">
          {f.nombre(file.nombre)}
        </span>
      )}
      <Icone nom="chevron" />
    </>
  );
  return <li>{children(contenu, `console-a-traiter-ligne ${ton}`)}</li>;
}

export function TableauDeBordAdmin() {
  // La période gouverne À LA FOIS les chiffres du haut et les courbes. Les
  // laisser diverger — trente jours en haut, douze mois en bas — obligeait à
  // deviner à quoi chaque nombre se rapporte.
  const [periode, setPeriode] = useState<Periode>(PERIODES[2]);

  const lectureSynthese = useQuery({
    queryKey: ["admin", "synthese", periode.jours],
    queryFn: () => adminApi.synthese(periode.jours),
  });
  const { data: synthese, isPending } = lectureSynthese;
  const lectureEvolution = useQuery({
    queryKey: ["admin", "evolution", periode.mois],
    queryFn: () => adminApi.evolution(periode.mois),
  });
  const { data: evolution } = lectureEvolution;
  const lectureOrganisations = useQuery({
    queryKey: ["admin", "organisations"],
    queryFn: adminApi.organisations,
  });
  const { data: organisations } = lectureOrganisations;

  // Les deux files que la coquille lit pour ses pastilles : même clé, même
  // fonction, même fraîcheur — TanStack Query n'émet qu'une requête pour les
  // deux lecteurs.
  const lectureDemandes = useQuery({
    queryKey: ["admin", "demandes"],
    queryFn: adminApi.demandes,
    staleTime: 60_000,
  });
  const lectureSignalements = useQuery({
    queryKey: ["admin", "signalements"],
    queryFn: adminApi.signalements,
    staleTime: 60_000,
  });

  if (isPending) return <Squelette lignes={5} />;

  const serie = (cle: string) =>
    evolution?.series.find((s) => s.cle === cle) ?? {
      cle,
      libelle: cle,
      valeurs: [],
    };

  /** Une série monétaire, ramenée en euros pour l'affichage.
   *
   * Le serveur compte en centimes partout — deux unités dans une même réponse
   * seraient une source d'erreur permanente. Mais le graphique ne fait
   * qu'accoler son unité au nombre : lui passer des centimes écrirait
   * « 18900 cents » sous une colonne. La conversion se fait donc ici, au seul
   * endroit qui sait qu'on est en train d'AFFICHER. */
  const serieEnEuros = (cle: string) => {
    const brute = serie(cle);
    return {
      ...brute,
      valeurs: brute.valeurs.map((centimes) => Math.round(centimes / 100)),
    };
  };

  const lignes = (organisations?.organisations ?? [])
    .filter((o) => o.documents_produits > 0 || o.credits_consommes > 0)
    .sort((a, b) => b.credits_consommes - a.credits_consommes)
    .slice(0, 8)
    .map((o) => ({
      cle: o.id,
      libelle: o.raison_sociale,
      valeur: o.credits_consommes,
    }));

  // ── Ce qui vous attend ──────────────────────────────────────────────────
  // Trois états par file : lue, en cours de lecture, en panne. Une file dont
  // des données restent à l'écran après une mise à jour ratée est encore
  // « lue » — c'est son dernier compte connu, et la ligne mène à l'écran qui
  // dira qu'il est dépassé.
  const fileDemandes: EtatDeFile = lectureDemandes.data
    ? {
        etat: "lue",
        nombre: lectureDemandes.data.ouvertes,
        detail:
          lectureDemandes.data.ouvertes > 0
            ? "Changements de formule ou achats de crédits : votre décision est attendue."
            : "Aucune demande en attente.",
        ton: lectureDemandes.data.ouvertes > 0 ? "attend" : "calme",
      }
    : lectureDemandes.isError
      ? { etat: "en panne" }
      : { etat: "en cours" };

  const fileSignalements: EtatDeFile = lectureSignalements.data
    ? {
        etat: "lue",
        nombre: lectureSignalements.data.a_traiter,
        detail:
          lectureSignalements.data.a_traiter > 0
            ? "Des clients ont signalé un problème et attendent une réponse."
            : "Aucun signalement à traiter.",
        ton: lectureSignalements.data.a_traiter > 0 ? "attend" : "calme",
      }
    : lectureSignalements.isError
      ? { etat: "en panne" }
      : { etat: "en cours" };

  // Les incidents viennent de la synthèse, déjà lue : sans elle, la ligne dit
  // sa panne comme les deux autres.
  const fileIncidents: EtatDeFile = synthese
    ? {
        etat: "lue",
        nombre: synthese.incidents.ouverts,
        detail:
          synthese.incidents.graves > 0
            ? `Dont ${f.nombre(synthese.incidents.graves)} de gravité haute ou critique : une intervention est attendue.`
            : synthese.incidents.ouverts > 0
              ? "Aucun n'est grave. À solder quand ils sont compris."
              : "Aucun incident à traiter.",
        ton:
          synthese.incidents.graves > 0
            ? "grave"
            : synthese.incidents.ouverts > 0
              ? "attend"
              : "calme",
      }
    : { etat: "en panne" };

  return (
    <>
      {/* La période se choisit dans l'en-tête de la page : elle vaut pour tout
          l'écran, pas pour une carte. */}
      <ActionsDePage>
        <div className="console-segments" role="group" aria-label="Période observée">
          {PERIODES.map((p) => (
            <button
              key={p.libelle}
              type="button"
              className={
                p.libelle === periode.libelle
                  ? "bouton bouton-sm"
                  : "bouton bouton-contour bouton-sm"
              }
              aria-pressed={p.libelle === periode.libelle}
              onClick={() => setPeriode(p)}
            >
              {p.libelle}
            </button>
          ))}
        </div>
      </ActionsDePage>

      {/* Trois lectures, trois bandeaux — le même que sur les écrans de
          `src/pages/`. Sans eux, un échec de la synthèse affichait « 0 € » de
          revenu, « 0 » document et « 0 % » d'échec : un tableau de bord qui
          annonce une plateforme à l'arrêt quand c'est sa propre lecture qui
          a échoué (audit du 19/11/2026, règle 1). */}
      {lectureSynthese.isError && (
        <ErreurDeChargement
          quoi="la synthèse"
          erreur={lectureSynthese.error}
          perimees={lectureSynthese.isRefetchError}
        />
      )}
      {lectureEvolution.isError && (
        <ErreurDeChargement
          quoi="l'évolution mensuelle"
          erreur={lectureEvolution.error}
          perimees={lectureEvolution.isRefetchError}
        />
      )}
      {lectureOrganisations.isError && (
        <ErreurDeChargement
          quoi="les organisations"
          erreur={lectureOrganisations.error}
          perimees={lectureOrganisations.isRefetchError}
        />
      )}

      {/* ── 1. Les ventes ─────────────────────────────────────────────────
          Les chiffres n'existent que si la synthèse a été REÇUE : un zéro est
          une réponse, et celui-là décide de ce qu'on croit de l'activité. */}
      {synthese && (
        <section className="console-section" aria-labelledby="tdb-ventes">
          <h2 className="console-etiquette" id="tdb-ventes">
            Vos chiffres sur {periode.libelle}
          </h2>
          <div className="grille-chiffres">
            <Chiffre
              libelle="Revenu récurrent"
              valeur={f.montant(
                synthese.revenu.recurrent_mensuel_cents,
                synthese.revenu.devise,
              )}
              detail="Par mois, sur abonnements actifs"
              accent
            />
            <Chiffre
              libelle="Revenu encaissé"
              valeur={f.montant(
                synthese.revenu.encaisse_periode_cents,
                synthese.revenu.devise,
              )}
              detail={`${f.montant(
                synthese.revenu.encaisse_total_cents,
                synthese.revenu.devise,
              )} depuis l'ouverture`}
            />
            <Chiffre
              libelle="Documents produits"
              valeur={f.nombre(synthese.documents.produits)}
              detail={`${f.nombre(synthese.documents.total)} au total, toutes périodes`}
            />
            <Chiffre
              libelle="Crédits consommés"
              valeur={f.nombre(synthese.credits.consommes)}
              detail={`${f.nombre(
                synthese.credits.solde_total_en_circulation,
              )} en circulation`}
            />
            <Chiffre
              libelle="Coût par document"
              valeur={f.montant(synthese.cout_production.moyen_par_document_cents)}
              detail={`${f.montant(synthese.cout_production.total_cents)} au total`}
            />
          </div>
        </section>
      )}

      {/* Un chiffre dont on ignore la nature est un chiffre faux. Le tableau de
          bord dit ce que le revenu EST. */}
      {synthese?.revenu.avertissement && (
        <Bandeau titre="Ce que « revenu récurrent » signifie ici">
          {synthese.revenu.avertissement}
        </Bandeau>
      )}

      {/* ── 2. Ce qui attend, et les gestes fréquents ─────────────────────── */}
      <div className="console-duo">
        <Carte
          titre="Ce qui vous attend"
          note="Les files à traiter aujourd'hui. Chaque ligne mène à son écran."
        >
          <ul className="console-a-traiter">
            <LigneATraiter icone="demandes" nom="Demandes des clients" file={fileDemandes}>
              {(contenu, classe) => (
                <Link to="/admin/demandes" className={classe}>
                  {contenu}
                </Link>
              )}
            </LigneATraiter>
            <LigneATraiter icone="signalements" nom="Signalements" file={fileSignalements}>
              {(contenu, classe) => (
                <Link to="/admin/signalements" className={classe}>
                  {contenu}
                </Link>
              )}
            </LigneATraiter>
            <LigneATraiter icone="incidents" nom="Incidents de production" file={fileIncidents}>
              {(contenu, classe) => (
                <Link to="/admin/incidents" className={classe}>
                  {contenu}
                </Link>
              )}
            </LigneATraiter>
          </ul>
        </Carte>

        <Carte titre="Raccourcis" note="Les gestes les plus fréquents.">
          <ul className="console-raccourcis">
            <li>
              <Link to="/admin/boutique" className="console-raccourci">
                <Icone nom="boutique" />
                <span className="console-raccourci-texte">
                  <span className="console-raccourci-nom">Ajouter une étude</span>
                  <span className="console-raccourci-aide">À la boutique</span>
                </span>
              </Link>
            </li>
            <li>
              <Link to="/admin/annonces" className="console-raccourci">
                <Icone nom="annonces" />
                <span className="console-raccourci-texte">
                  <span className="console-raccourci-nom">Rédiger une annonce</span>
                  <span className="console-raccourci-aide">Pour tous vos clients</span>
                </span>
              </Link>
            </li>
            <li>
              <Link to="/admin/jobs" className="console-raccourci">
                <Icone nom="generations" />
                <span className="console-raccourci-texte">
                  <span className="console-raccourci-nom">Suivre les générations</span>
                  <span className="console-raccourci-aide">Études en cours et terminées</span>
                </span>
              </Link>
            </li>
            <li>
              <Link to="/admin/transactions" className="console-raccourci">
                <Icone nom="transactions" />
                <span className="console-raccourci-texte">
                  <span className="console-raccourci-nom">Relancer un panier</span>
                  <span className="console-raccourci-aide">Paiements abandonnés</span>
                </span>
              </Link>
            </li>
            <li>
              <Link to="/admin/organisations" className="console-raccourci">
                <Icone nom="organisations" />
                <span className="console-raccourci-texte">
                  <span className="console-raccourci-nom">Créditer un compte</span>
                  <span className="console-raccourci-aide">Organisations</span>
                </span>
              </Link>
            </li>
            <li>
              <Link to="/admin/prospection" className="console-raccourci">
                <Icone nom="prospection" />
                <span className="console-raccourci-texte">
                  <span className="console-raccourci-nom">Trouver des prospects</span>
                  <span className="console-raccourci-aide">Prospection</span>
                </span>
              </Link>
            </li>
          </ul>
        </Carte>
      </div>

      {/* ── 3. L'évolution ────────────────────────────────────────────────
          Les trois graphiques lisent la même série. Si elle a échoué, ils
          n'attendent plus rien : un squelette qui pulse indéfiniment sous un
          bandeau d'erreur se lirait « ça charge encore ». */}
      {(evolution || !lectureEvolution.isError) && (
        <section className="console-section" aria-labelledby="tdb-evolution">
          <h2 className="console-etiquette" id="tdb-evolution">
            L'évolution, mois par mois
          </h2>
          <Carte
            titre="Revenu encaissé et coût de production"
            note="Ce qui est réellement rentré, en regard de ce que la production a coûté. L'écart est la marge brute."
          >
            {evolution ? (
              <Colonnes
                abscisses={evolution.mois}
                series={[serieEnEuros("encaisse"), serieEnEuros("cout")]}
                unite={"\u00a0€"}
              />
            ) : (
              <Squelette lignes={3} />
            )}
          </Carte>

          <div className="console-duo">
            <Carte
              titre={`Production sur ${periode.mois} mois`}
              note="Documents terminés et échecs, par mois."
            >
              {evolution ? (
                <Colonnes
                  abscisses={evolution.mois}
                  series={[serie("produits"), serie("echecs")]}
                />
              ) : (
                <Squelette lignes={3} />
              )}
            </Carte>

            <Carte
              titre="Crédits attribués et consommés"
              note="Ce qui entre dans les portefeuilles, et ce qui en sort."
            >
              {evolution ? (
                <Courbes
                  abscisses={evolution.mois}
                  series={[serie("dotations"), serie("debits")]}
                />
              ) : (
                <Squelette lignes={3} />
              )}
            </Carte>
          </div>
        </section>
      )}

      {/* ── 4. Qui consomme, et l'état du parc ────────────────────────────
          « Aucune consommation » ne se dit que sur une liste REÇUE et à jour. */}
      {(lignes.length > 0 || (organisations && !lectureOrganisations.isError)) && (
        <Carte
          titre="Consommation par organisation"
          note="Les huit plus gros consommateurs de crédits."
          action={
            <Link to="/admin/organisations" className="bouton bouton-contour bouton-sm">
              Toutes les organisations
            </Link>
          }
        >
          {lignes.length === 0 ? (
            <Vide
              icone={<Icone nom="organisations" />}
              titre="Aucune consommation"
              texte="Le classement apparaîtra dès qu'une organisation aura lancé une génération."
            />
          ) : (
            <BarresClassement lignes={lignes} libelleValeur="Crédits consommés" />
          )}
        </Carte>
      )}

      {synthese && (
        <section className="console-section" aria-labelledby="tdb-parc">
          <h2 className="console-etiquette" id="tdb-parc">
            L'état du parc
          </h2>
          <div className="grille-chiffres">
            <Chiffre
              libelle="Organisations"
              valeur={f.nombre(synthese.organisations.total)}
              detail={`${f.nombre(synthese.organisations.actives)} actives, ${f.nombre(
                synthese.organisations.suspendues,
              )} suspendues`}
            />
            <Chiffre
              libelle="Taux d'échec"
              valeur={`${Math.round(synthese.documents.taux_echec * 100)} %`}
              detail={`${f.nombre(synthese.documents.en_echec)} échec(s) sur la période`}
            />
            <Chiffre
              libelle="Incidents ouverts"
              valeur={f.nombre(synthese.incidents.ouverts)}
              detail={`dont ${f.nombre(synthese.incidents.graves)} grave(s)`}
            />
            <Chiffre
              libelle="Contacts"
              valeur={f.nombre(synthese.clients.total)}
              detail="Toutes organisations confondues"
            />
          </div>
        </section>
      )}
    </>
  );
}
