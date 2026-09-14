"""Un tableau de sources se reconnaît à ce qu'il porte, pas au mot « Source ».

## Le défaut mesuré

Corpus du 14/09/2026 : les SIX études de marché rendaient exactement « 3
sources extérieures, 3 sans adresse », pour 19 à 70 adresses collectées par
la recherche. Les lignes retenues par la mesure (`sources.lignes`, ajoutées le
même jour pour le savoir) étaient trois puces de la MÉTHODOLOGIE.

Le modèle validé du chapitre 21 impose des tableaux « Organisme | Publication
| Lien » et « Acteur | Usage dans l'étude | Lien ». `_sources_listees` ne
reconnaissait qu'un en-tête « Source » ou « Référence » écrit seul : les vraies
sources étaient ignorées, et la mesure — comme le contrôle de traçabilité du
gate — jugeait sur des phrases qui ne prétendent rien sourcer (règles 2 et 3).
"""
from __future__ import annotations

from generation.checks_post_rendu import _sources_listees, detecter_sources_non_tracables
from generation.mesure import mesurer_les_sources

CHAPITRE_21 = """## 21.1 Méthode appliquée

- Le marché national date de 2024 et la population cible est estimée pour 2026 : ce sont les deux
- Le porteur de projet doit relire cette étude avec les indicateurs réels.
- Aucun chiffre de marché n'est recalculé au fil des chapitres.

## 21.2 Sources principales — marché du bien-être

| Organisme | Publication | Lien |
| --- | --- | --- |
| Insee | Tableaux de l'économie française 2025 | https://www.insee.fr/fr/statistiques/1 |
| Global Wellness Institute | Wellness Monitor 2024 | https://globalwellnessinstitute.org/x |
| Xerfi | Le marché du bien-être | |

## 21.5 Sources entreprise et écosystème

| Acteur | Usage dans l'étude | Lien |
| --- | --- | --- |
| Zen Agenda | Prix observés | https://www.zenagenda.fr/ |

## 21.7 Protocole de mise à jour

| Échéance | Données à actualiser | Effet attendu |
| --- | --- | --- |
| Janvier 2027 | Population cible | Réviser le SOM |
"""


def test_les_tableaux_organisme_et_acteur_sont_les_sources() -> None:
    lignes = _sources_listees(CHAPITRE_21)
    assert len(lignes) == 4
    assert all("Méthode" not in ligne and "recalculé" not in ligne for ligne in lignes)


def test_la_mesure_compte_les_adresses_des_vraies_sources() -> None:
    mesure = mesurer_les_sources([(21, "Sources et méthodologie", CHAPITRE_21)])
    assert mesure is not None
    assert (mesure.exterieures, mesure.sans_adresse) == (4, 1), "Xerfi est cité sans lien"


def test_un_tableau_de_calendrier_n_est_pas_une_source() -> None:
    """CONTRE-ÉPREUVE : « Échéance | Données à actualiser » ne liste aucune origine."""
    assert not any("Janvier 2027" in ligne for ligne in _sources_listees(CHAPITRE_21))


def test_une_cellule_lien_plus_bas_ne_fait_pas_un_tableau_de_sources() -> None:
    """CONTRE-ÉPREUVE : seule la première ligne d'un tableau est son en-tête."""
    corps = """| Échéance | Action |
| --- | --- |
| Lien avec le projet | Revoir le SOM |
| Mars 2027 | Actualiser les prix |
"""
    assert _sources_listees(corps) == []


def test_des_sources_tracees_en_tableau_ne_sont_pas_non_tracables() -> None:
    corps = """| Organisme | Publication | Lien |
| --- | --- | --- |
| Insee | Démographie 2025 | https://www.insee.fr/a |
| Banque de France | Défaillances 2025 | https://www.banque-france.fr/b |
| Urssaf | Stat'ur 2025 | https://www.urssaf.fr/c |

- Démarche : croisement des sources publiques et des données du projet.
- Limite : aucune donnée locale sur le panier moyen.
"""
    motifs = [d.motif for d in detecter_sources_non_tracables([(20, "Sources", corps)])]
    assert "ratio_faible" not in motifs


# ── Une adresse sans « https:// », un texte de loi (corpus-20260914-1717) ────


def test_un_nom_de_domaine_et_un_texte_de_loi_sont_des_adresses() -> None:
    corps = """| Organisme | Publication | Lien |
| --- | --- | --- |
| Comptoir National de l'Or | Tarifs de rachat | gold.fr/vente-or |
| Annuaire des Entreprises | Fiche SIREN | annuaire-entreprises.data.gouv.fr |
| Code de la consommation | Droit de rétractation | Article L221-18 |
| Règlement général sur la protection des données | Collecte | Règlement UE 2016/679 |
"""
    mesure = mesurer_les_sources([(9, "Sources", corps)])
    assert mesure is not None
    assert (mesure.exterieures, mesure.sans_adresse) == (4, 0)
    assert "ratio_faible" not in [
        d.motif for d in detecter_sources_non_tracables([(9, "Sources", corps)])
    ]


def test_un_nom_d_organisme_ou_une_adresse_inventee_ne_sont_pas_des_adresses() -> None:
    """CONTRE-ÉPREUVE : « Xerfi, 2025 » ne se retrouve pas ; « example.com » ne mène nulle part."""
    corps = """| Organisme | Publication | Lien |
| --- | --- | --- |
| Xerfi | Le marché du conseil, 2025 | |
| Institut fictif | Étude | example.com/etude |
| Insee | Démographie | https://www.insee.fr/a |
"""
    mesure = mesurer_les_sources([(9, "Sources", corps)])
    assert mesure is not None
    assert (mesure.exterieures, mesure.sans_adresse) == (3, 2)
    assert "ratio_faible" in [
        d.motif for d in detecter_sources_non_tracables([(9, "Sources", corps)])
    ]
