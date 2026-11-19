/** Tableau de bord de supervision (§10.1).
 *
 * EVKHA ne produit plus les documents : cet écran ne lance rien, il **observe**.
 * Volumes produits, consommation de crédits, revenu récurrent, coût de
 * production, classement des organisations.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { adminApi } from "../api";
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

  return (
    <>
      <div className="admin-periodes" role="group" aria-label="Période observée">
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

      {/* Les chiffres n'existent que si la synthèse a été REÇUE : un zéro est
          une réponse, et celui-là décide de ce qu'on croit de l'activité. */}
      {synthese && (
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
      )}

      {/* Un chiffre dont on ignore la nature est un chiffre faux. Le tableau de
          bord dit ce que le revenu EST. */}
      {synthese?.revenu.avertissement && (
        <Bandeau titre="Ce que « revenu récurrent » signifie ici">
          {synthese.revenu.avertissement}
        </Bandeau>
      )}

      {(synthese?.incidents.graves ?? 0) > 0 && (
        <Bandeau ton="echec" titre="Incidents graves ouverts">
          {f.nombre(synthese?.incidents.graves ?? 0)} incident(s) de gravité haute
          ou critique attendent une intervention.{" "}
          <Link to="/admin/incidents">Voir les incidents</Link>
        </Bandeau>
      )}

      {/* Les trois graphiques lisent la même série. Si elle a échoué, ils
          n'attendent plus rien : un squelette qui pulse indéfiniment sous un
          bandeau d'erreur se lirait « ça charge encore ». */}
      {(evolution || !lectureEvolution.isError) && (
      <>
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

      <Carte
        titre="Revenu encaissé et coût de production"
        note="Ce qui est réellement rentré, en regard de ce que la production a coûté. L'écart est la marge brute."
      >
        {evolution ? (
          <Colonnes
            abscisses={evolution.mois}
            series={[serieEnEuros("encaisse"), serieEnEuros("cout")]}
            unite="\u00a0€"
          />
        ) : (
          <Squelette lignes={3} />
        )}
      </Carte>
      </>
      )}

      {/* « Aucune consommation » ne se dit que sur une liste REÇUE et à jour. */}
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
            icone="◍"
            titre="Aucune consommation"
            texte="Le classement apparaîtra dès qu'une organisation aura lancé une génération."
          />
        ) : (
          <BarresClassement lignes={lignes} libelleValeur="Crédits consommés" />
        )}
      </Carte>
      )}

      {synthese && (
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
      )}
    </>
  );
}
