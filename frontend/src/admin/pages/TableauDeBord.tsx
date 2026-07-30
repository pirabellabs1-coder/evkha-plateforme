/** Tableau de bord de supervision (§10.1).
 *
 * EVKHA ne produit plus les documents : cet écran ne lance rien, il **observe**.
 * Volumes produits, consommation de crédits, revenu récurrent, coût de
 * production, classement des organisations.
 */
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { adminApi } from "../api";
import * as f from "../../espace/format";
import {
  Bandeau,
  Carte,
  Chiffre,
  Squelette,
  Vide,
} from "../../espace/composants/Interface";
import { BarresClassement, Colonnes, Courbes } from "../../viz/Graphiques";

export function TableauDeBordAdmin() {
  const { data: synthese, isPending } = useQuery({
    queryKey: ["admin", "synthese"],
    queryFn: () => adminApi.synthese(30),
  });
  const { data: evolution } = useQuery({
    queryKey: ["admin", "evolution"],
    queryFn: adminApi.evolution,
  });
  const { data: organisations } = useQuery({
    queryKey: ["admin", "organisations"],
    queryFn: adminApi.organisations,
  });

  if (isPending) return <Squelette lignes={5} />;

  const serie = (cle: string) =>
    evolution?.series.find((s) => s.cle === cle) ?? {
      cle,
      libelle: cle,
      valeurs: [],
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
      <div className="grille-chiffres">
        <Chiffre
          libelle="Revenu récurrent"
          valeur={f.montant(
            synthese?.revenu.recurrent_mensuel_cents ?? 0,
            synthese?.revenu.devise ?? "EUR",
          )}
          detail="Par mois, sur abonnements actifs"
          accent
        />
        <Chiffre
          libelle="Documents produits"
          valeur={f.nombre(synthese?.documents.produits ?? 0)}
          detail={`Sur ${synthese?.periode.jours ?? 30} jours`}
        />
        <Chiffre
          libelle="Crédits consommés"
          valeur={f.nombre(synthese?.credits.consommes ?? 0)}
          detail={`${f.nombre(
            synthese?.credits.solde_total_en_circulation ?? 0,
          )} en circulation`}
        />
        <Chiffre
          libelle="Coût par document"
          valeur={f.montant(synthese?.cout_production.moyen_par_document_cents ?? 0)}
          detail={`${f.montant(
            synthese?.cout_production.total_cents ?? 0,
          )} au total`}
        />
      </div>

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

      <Carte
        titre="Production sur douze mois"
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

      <div className="grille-chiffres">
        <Chiffre
          libelle="Organisations"
          valeur={f.nombre(synthese?.organisations.total ?? 0)}
          detail={`${f.nombre(synthese?.organisations.actives ?? 0)} actives, ${f.nombre(
            synthese?.organisations.suspendues ?? 0,
          )} suspendues`}
        />
        <Chiffre
          libelle="Taux d'échec"
          valeur={`${Math.round((synthese?.documents.taux_echec ?? 0) * 100)} %`}
          detail={`${f.nombre(synthese?.documents.en_echec ?? 0)} échec(s) sur la période`}
        />
        <Chiffre
          libelle="Incidents ouverts"
          valeur={f.nombre(synthese?.incidents.ouverts ?? 0)}
          detail={`dont ${f.nombre(synthese?.incidents.graves ?? 0)} grave(s)`}
        />
        <Chiffre
          libelle="Contacts"
          valeur={f.nombre(synthese?.clients.total ?? 0)}
          detail="Toutes organisations confondues"
        />
      </div>
    </>
  );
}
