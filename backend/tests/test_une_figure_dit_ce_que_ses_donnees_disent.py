"""Une figure dit ce que ses données disent : les sept règles du client du 30/09/2026.

## Le défaut, mesuré

Business plan ÉCLORE `28a257bf` (30/09/2026) : le gate listait des conversions
comme « Structure du chiffre d'affaires par univers, 2027 et 2029 :
barres_empilees → barres (une seule dimension) ». Chaque conversion était
juste ; le TITRE, lui, promettait un découpage que la figure ne portait pas.
Rien ne comparait un titre à ses données, ni deux grandeurs entre elles au-delà
de leur unité.

Règles du client, verbatim :

1. même unité et même ordre de grandeur (rapport max/min inférieur à 1 000) ;
2. pas d'aires empilées ni d'anneaux qui additionnent des grandeurs non
   additives (résultat + trésorerie, revenu mensuel + trésorerie cumulée,
   marché + apport) ;
3. le titre correspond aux données (« par univers », « répartition ») ;
4. pas de graphique à deux barres égales ;
5. les légendes indiquent la bonne période ;
6. si le projet figure dans le titre ou la légende, il est dans les séries ;
7. libellés non tronqués.

Si un graphique échoue : régénération depuis la spec, puis tableau.

Chaque règle a son test, qui échoue sur le code d'avant, et sa contre-épreuve.
Données fictives uniquement : un atelier de céramique, « Atelier Brume ».
"""
from __future__ import annotations

from datetime import date
from typing import Any, cast

import pytest

from generation.chapitres.schema import (
    BlocGraphique,
    ChapitrePayload,
    Graphique,
    TypeGraphique,
)
from generation.rendu_word import assemblage, secteurs
from generation.rendu_word.donnees_graphiques import (
    etiquette_de,
    etiquettes_de,
    nature_de,
    resoudre,
    series_par_perimetre,
)
from generation.rendu_word.specification_figures import ecarts_de_specification
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import (
    Concurrent,
    Critere,
    DonneeSocle,
    NoteConcurrent,
    Socle,
    Zone,
)

PROJET = "Atelier Brume"


def _d(
    identifiant: str,
    libelle: str,
    valeur: float,
    unite: str = "EUR",
    annee: int = 2027,
    perimetre: Perimetre = Perimetre.ENTREPRISE,
    derivee_de: list[str] | None = None,
) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant, libelle=libelle, valeur=valeur, unite=unite, annee=annee,
        perimetre=perimetre, fiabilite=Fiabilite.SCENARIO,
        derivee_de=derivee_de or [],
    )


def _socle(*donnees: DonneeSocle, **champs: Any) -> Socle:
    return Socle(
        secteur="atelier de céramique", zone=Zone(pays="France"),
        date_socle=date(2026, 9, 30), donnees=list(donnees), **champs,
    )


def _previsionnel() -> list[DonneeSocle]:
    ca = "Chiffre d'affaires prévisionnel — exercice"
    return [
        _d("ca_previsionnel_an1", f"{ca} 1", 180_000, annee=2027),
        _d("ca_previsionnel_an2", f"{ca} 2", 240_000, annee=2028),
        _d("ca_previsionnel_an3", f"{ca} 3", 310_000, annee=2029),
        _d("resultat_net_an1", "Résultat net — exercice 1", -8_000, annee=2027),
        _d("resultat_net_an2", "Résultat net — exercice 2", 21_000, annee=2028),
        _d("resultat_net_an3", "Résultat net — exercice 3", 46_000, annee=2029),
        _d("tresorerie_fin_an1", "Trésorerie de clôture — exercice 1", 12_000, annee=2027),
        _d("tresorerie_fin_an2", "Trésorerie de clôture — exercice 2", 30_000, annee=2028),
        _d("tresorerie_fin_an3", "Trésorerie de clôture — exercice 3", 71_000, annee=2029),
    ]


def _poser(
    socle: Socle, graphique: Graphique,
) -> tuple[list[dict[str, Any]], assemblage.RapportAssemblage]:
    rapport = assemblage.RapportAssemblage()
    blocs = assemblage._blocs_graphique(
        socle, [graphique], secteurs.profil_du_secteur(socle.secteur), rapport, "Chapitre 16",
    )
    return blocs, rapport


def _figure(type_: TypeGraphique, titre: str, *ids: str, commentaire: str = "") -> Graphique:
    return Graphique(
        type_graphique=type_, titre=titre, donnees_ids=list(ids), commentaire=commentaire,
    )


# ── Règle 1 : même unité, même ordre de grandeur ─────────────────────────────


def test_un_marche_en_milliards_et_un_panier_en_euros_ne_partagent_pas_un_axe() -> None:
    """Sur le code d'avant : `_harmoniser` passait tout en Md€, le panier valait 0."""
    socle = _socle(
        _d("marche_national_taille", "Taille du marché national", 2.4, "MdEUR",
           perimetre=Perimetre.NATIONAL),
        _d("panier_moyen", "Panier moyen visé", 48.0),
    )

    resolution = resoudre(socle, "barres", ["marche_national_taille", "panier_moyen"])

    assert not resolution.retenu
    assert "ordres de grandeur" in resolution.motif
    assert "1 000" in resolution.motif


def test_une_courbe_ne_pose_pas_un_marche_a_cote_d_un_chiffre_d_affaires() -> None:
    socle = _socle(
        _d("marche_national_taille", "Taille du marché national", 4.0, "MdEUR",
           annee=2027, perimetre=Perimetre.NATIONAL),
        _d("marche_national_projection", "Taille projetée du marché national", 4.6,
           "MdEUR", annee=2029, perimetre=Perimetre.NATIONAL),
        _d("ca_previsionnel_an1", "Chiffre d'affaires prévisionnel — exercice 1", 180_000),
        _d("ca_previsionnel_an3", "Chiffre d'affaires prévisionnel — exercice 3", 310_000,
           annee=2029),
    )

    resolution = resoudre(socle, "courbes", [
        "marche_national_taille", "marche_national_projection",
        "ca_previsionnel_an1", "ca_previsionnel_an3",
    ])

    assert not resolution.retenu
    assert "ordres de grandeur" in resolution.motif


def test_la_reparation_dessine_ce_qui_partage_un_axe_et_imprime_le_reste() -> None:
    """Régénération depuis la spec : les deux chiffres d'affaires se dessinent,
    le marché part en tableau sous la figure — aucun chiffre perdu."""
    socle = _socle(
        _d("marche_national_taille", "Taille du marché national", 2.4, "MdEUR",
           perimetre=Perimetre.NATIONAL),
        *_previsionnel()[:2],
    )

    blocs, rapport = _poser(socle, _figure(
        TypeGraphique.BARRES, "Le marché et les deux premiers exercices",
        "marche_national_taille", "ca_previsionnel_an1", "ca_previsionnel_an2",
    ))

    assert [bloc["type"] for bloc in blocs] == ["graphique", "tableau"]
    assert rapport.identifiants_rendus == {"ca_previsionnel_an1", "ca_previsionnel_an2"}
    assert [ligne[0] for ligne in blocs[1]["lignes"]] == ["Taille du marché national"]


def test_contre_epreuve_des_valeurs_du_meme_ordre_restent_une_figure() -> None:
    socle = _socle(*_previsionnel())
    resolution = resoudre(socle, "barres", ["ca_previsionnel_an1", "ca_previsionnel_an3"])
    assert resolution.retenu, resolution.motif


def test_contre_epreuve_un_resultat_qui_traverse_zero_reste_a_cote_du_chiffre_d_affaires() -> None:
    """Ce sont les SÉRIES qui se comparent, pas leurs points.

    Un résultat de −100 € au premier exercice est petit par construction : il
    passe de la perte au bénéfice. Comparé point à point à 310 000 €, il
    faisait refuser « CA et résultat sur trois exercices » (rapport de 3 100).
    """
    donnees = _previsionnel()
    donnees[3] = _d("resultat_net_an1", "Résultat net — exercice 1", -100, annee=2027)
    resolution = resoudre(_socle(*donnees), "courbes", [
        "ca_previsionnel_an1", "ca_previsionnel_an2", "ca_previsionnel_an3",
        "resultat_net_an1", "resultat_net_an2", "resultat_net_an3",
    ])
    assert resolution.retenu, resolution.motif
    assert len(resolution.donnees["series"]) == 2  # type: ignore[index]


def test_contre_epreuve_l_entonnoir_du_marche_garde_ses_six_ordres_de_grandeur() -> None:
    """Un entonnoir n'a pas d'axe commun : chaque marche porte sa propre échelle."""
    socle = _socle(
        _d("tam", "Marché total théorique", 1.2, "MdEUR", perimetre=Perimetre.NATIONAL),
        _d("sam", "Marché adressable", 240.0, "MEUR", perimetre=Perimetre.NATIONAL),
        _d("som", "Marché atteignable", 1_800.0),
    )
    assert resoudre(socle, "entonnoir", ["tam", "sam", "som"]).retenu


# ── Règle 2 : on n'additionne que l'additionnable ────────────────────────────


def test_des_aires_empilees_ne_somment_pas_un_resultat_et_une_tresorerie() -> None:
    """Le premier exemple du client. Sur le code d'avant : des aires, empilées."""
    socle = _socle(*_previsionnel())

    resolution = resoudre(socle, "aires", [
        "resultat_net_an1", "resultat_net_an2", "resultat_net_an3",
        "tresorerie_fin_an1", "tresorerie_fin_an2", "tresorerie_fin_an3",
    ])

    assert resolution.retenu, resolution.motif
    assert resolution.type_graphique == "courbes"
    assert resolution.converti
    assert "natures différentes" in resolution.motif


def test_des_barres_empilees_ne_somment_pas_un_chiffre_d_affaires_et_un_resultat() -> None:
    socle = _socle(*_previsionnel())

    # Exercices 2 et 3 : la perte de l'exercice 1 serait refusée plus tôt,
    # par la règle des valeurs négatives — ce n'est pas celle qu'on teste.
    resolution = resoudre(socle, "barres_empilees", [
        "ca_previsionnel_an2", "ca_previsionnel_an3",
        "resultat_net_an2", "resultat_net_an3",
    ])

    assert resolution.type_graphique == "barres_groupees"
    assert resolution.converti


def test_un_anneau_ne_somme_pas_un_marche_et_un_apport() -> None:
    """Le troisième exemple, à un ordre de grandeur près pour isoler la règle."""
    socle = _socle(
        _d("marche_regional_taille", "Taille du marché sur la zone", 1.6, "MEUR",
           perimetre=Perimetre.REGIONAL),
        _d("apport", "Apport personnel du porteur", 40_000),
    )

    resolution = resoudre(socle, "anneau", ["marche_regional_taille", "apport"])

    assert resolution.type_graphique == "barres"
    assert resolution.converti
    assert "natures différentes" in resolution.motif


def test_un_anneau_ne_somme_pas_un_revenu_mensuel_et_une_tresorerie() -> None:
    """Le deuxième exemple : un flux compté au mois, un stock de fin d'exercice."""
    socle = _socle(
        _d("ca_activite_1", "Revenu mensuel des cours collectifs", 6_500),
        _d("tresorerie_fin_an1", "Trésorerie de clôture — exercice 1", 12_000),
    )

    resolution = resoudre(socle, "anneau", ["ca_activite_1", "tresorerie_fin_an1"])

    assert resolution.type_graphique == "barres"
    assert "comptés au mois" in resolution.motif


def test_un_total_et_sa_composante_ne_sont_pas_deux_parts() -> None:
    """`derivee_de` dit l'emboîtement : l'additionner le compterait deux fois."""
    socle = _socle(
        _d("charge_poste_1", "Loyer de l'atelier", 14_000),
        _d("charge_poste_2", "Charges de structure", 32_000, derivee_de=["charge_poste_1"]),
    )
    resolution = resoudre(socle, "camembert", ["charge_poste_1", "charge_poste_2"])
    assert resolution.type_graphique == "barres"
    assert "deux fois" in resolution.motif


@pytest.mark.parametrize("forme", ["anneau", "camembert"])
def test_contre_epreuve_de_vraies_parts_restent_un_anneau(forme: str) -> None:
    socle = _socle(
        _d("apport", "Apport personnel du porteur", 30_000),
        _d("emprunt", "Emprunt bancaire sollicité", 60_000),
        _d("autres_ressources", "Prêt d'honneur", 10_000),
    )
    resolution = resoudre(socle, forme, ["apport", "emprunt", "autres_ressources"])
    assert resolution.type_graphique == forme
    assert not resolution.converti


def test_contre_epreuve_deux_activites_s_empilent() -> None:
    socle = _socle(
        _d("ca_cours_an1", "Chiffre d'affaires des cours — exercice 1", 60_000),
        _d("ca_cours_an2", "Chiffre d'affaires des cours — exercice 2", 75_000, annee=2028),
        _d("ca_boutique_an1", "Chiffre d'affaires de la boutique — exercice 1", 40_000),
        _d("ca_boutique_an2", "Chiffre d'affaires de la boutique — exercice 2", 52_000,
           annee=2028),
    )
    resolution = resoudre(socle, "aires", [
        "ca_cours_an1", "ca_cours_an2", "ca_boutique_an1", "ca_boutique_an2",
    ])
    assert resolution.type_graphique == "aires"
    assert not resolution.converti


def test_chaque_identifiant_du_referentiel_a_une_nature() -> None:
    """Le garde-fou de la règle : un identifiant ajouté sans nature ne passe pas.

    La nature se lit sur l'identifiant du référentiel fermé ; si un nouvel
    identifiant n'en reçoit aucune, les parts qui le contiennent ne seraient
    plus jugées — une règle qui n'a rien à comparer n'est pas un succès.
    """
    from generation.socle.referentiel import _PAR_LIVRABLE
    from generation.socle.schema import unites_autorisees

    sans_nature = []
    for definitions in _PAR_LIVRABLE.values():
        for definition in definitions:
            donnee = _d(
                definition.identifiant, definition.libelle, 1.0,
                unites_autorisees(definition.famille_unite)[0],
            )
            if nature_de(donnee) is None:
                sans_nature.append(definition.identifiant)
    assert sans_nature == []


def test_les_natures_s_accordent_avec_les_flux_de_la_memoire() -> None:
    """Une seule vérité : la mémoire tient déjà la liste des FLUX annuels."""
    from generation.memoire.faits import FLUX

    for serie in FLUX:
        nature = nature_de(_d(f"{serie}_an1", serie, 1.0))
        assert nature in {"produit", "charge", "solde"}, (serie, nature)
    for stock in ("tresorerie_fin", "dette_residuelle"):
        assert nature_de(_d(f"{stock}_an1", stock, 1.0)) == "position"


# ── Règle 3 : le titre correspond aux données ────────────────────────────────


def test_une_structure_par_gamme_sur_un_seul_chiffre_d_affaires_part_en_tableau() -> None:
    """LA forme relevée sur ÉCLORE : un seul chiffre d'affaires, à deux dates,
    sous un titre qui en promet la structure « par univers ».

    Sur le code d'avant : barres_empilees → barres, dessinées sous ce titre.
    """
    socle = _socle(*_previsionnel())

    blocs, rapport = _poser(socle, _figure(
        TypeGraphique.BARRES_EMPILEES,
        "Structure du chiffre d'affaires par gamme, 2027 et 2029",
        "ca_previsionnel_an1", "ca_previsionnel_an3",
    ))

    assert [bloc["type"] for bloc in blocs] == ["tableau"]
    # Le titre jugé faux n'est pas repris en légende du tableau.
    assert blocs[0]["titre"] == ""
    assert rapport.graphiques_rendus == 0
    assert len(rapport.graphiques_en_tableau) == 1
    assert "découpage" in rapport.graphiques_en_tableau[0]
    # Là où le rapport interne lit les motifs de figures.
    diagnostic = rapport.diagnostic_des_abandons[0]
    specification = cast(list[dict[str, str]], diagnostic["specification"])
    assert [e["regle"] for e in specification] == ["titre"]
    from generation.verification import controles

    anomalies = controles.controler_visuels(
        rapport.graphiques_demandes, rapport.graphiques_rendus,
        rapport.graphiques_abandonnes, rapport.graphiques_convertis,
    )
    assert any("découpage" in anomalie.detail for anomalie in anomalies)


def test_une_repartition_en_anneau_de_deux_parts_est_redessinee_en_barres() -> None:
    """« ≥ 3 pour un anneau » : régénération depuis la spec, le titre reste."""
    socle = _socle(
        _d("apport", "Apport personnel du porteur", 30_000),
        _d("emprunt", "Emprunt bancaire sollicité", 60_000),
    )

    blocs, rapport = _poser(socle, _figure(
        TypeGraphique.ANNEAU, "Répartition des ressources de financement",
        "apport", "emprunt",
    ))

    assert [bloc["type"] for bloc in blocs] == ["graphique"]
    assert blocs[0]["graphique"] == "barres"
    assert blocs[0]["titre"] == "Répartition des ressources de financement"
    assert len(rapport.graphiques_convertis) == 1
    assert "trois parts" in rapport.graphiques_convertis[0]


def test_contre_epreuve_un_vrai_decoupage_reste_dessine() -> None:
    socle = _socle(
        _d("ca_cours", "Chiffre d'affaires des cours", 60_000),
        _d("ca_boutique", "Chiffre d'affaires de la boutique", 40_000),
        _d("ca_commandes", "Chiffre d'affaires des commandes", 25_000),
    )
    blocs, rapport = _poser(socle, _figure(
        TypeGraphique.ANNEAU, "Répartition du chiffre d'affaires par activité",
        "ca_cours", "ca_boutique", "ca_commandes",
    ))
    assert [bloc["graphique"] for bloc in blocs] == ["anneau"]
    assert rapport.graphiques_convertis == []


def test_contre_epreuve_un_taux_par_visiteur_n_est_pas_un_decoupage() -> None:
    """« par X » décrit ici la grandeur (son libellé le dit), pas un découpage."""
    socle = _socle(
        _d("depense_visiteur_an1", "Dépense moyenne par visiteur — exercice 1", 34.0),
        _d("depense_visiteur_an2", "Dépense moyenne par visiteur — exercice 2", 38.0,
           annee=2028),
    )
    blocs, _ = _poser(socle, _figure(
        TypeGraphique.COURBES, "Dépense moyenne par visiteur, 2027-2028",
        "depense_visiteur_an1", "depense_visiteur_an2",
    ))
    assert [bloc["type"] for bloc in blocs] == ["graphique"]


def _payload(graphique: Graphique) -> ChapitrePayload:
    return ChapitrePayload(
        chapitre=16, titre="Prévisionnel", accroche="",
        blocs=[BlocGraphique(graphique=graphique)],
        donnees_utilisees=list(graphique.donnees_ids),
        resume="Résumé du chapitre, assez long pour tenir le contrat de forme.",
    )


def test_le_chapitre_apprend_que_son_titre_trahit_ses_donnees() -> None:
    """Le motif part avec une reprise décidée ailleurs ; seul, il ne coûte rien."""
    from generation.chapitres.runner import _motifs_de_figure

    socle = _socle(*_previsionnel())
    trahie = _figure(
        TypeGraphique.BARRES, "Structure du chiffre d'affaires par gamme",
        "ca_previsionnel_an1", "ca_previsionnel_an3",
    )

    motifs = _motifs_de_figure(_payload(trahie), socle)
    assert len(motifs) == 1 and "découpage" in motifs[0]
    # Au dernier essai, jamais de reprise pour une figure : elle ira en tableau.
    assert _motifs_de_figure(_payload(trahie), socle, derniere_tentative=True) == []
    # CONTRE-ÉPREUVE : un titre fidèle ne reproche rien.
    fidele = _figure(
        TypeGraphique.BARRES, "Chiffre d'affaires prévisionnel, exercices 1 et 3",
        "ca_previsionnel_an1", "ca_previsionnel_an3",
    )
    assert _motifs_de_figure(_payload(fidele), socle) == []


# ── Règle 4 : pas deux barres égales ─────────────────────────────────────────


def test_deux_barres_egales_partent_en_tableau() -> None:
    """« Budget 5 000 € contre apport 5 000 € » : dessinées sur le code d'avant."""
    socle = _socle(
        _d("investissement_total", "Budget d'équipement", 5_000),
        _d("apport", "Apport personnel du porteur", 5_000),
    )

    blocs, rapport = _poser(socle, _figure(
        TypeGraphique.BARRES, "Budget et apport", "investissement_total", "apport",
    ))

    assert [bloc["type"] for bloc in blocs] == ["tableau"]
    # Le titre n'est pas en cause : il reste en légende du tableau.
    assert blocs[0]["titre"] == "Budget et apport"
    assert "égales" in rapport.graphiques_en_tableau[0]


def test_contre_epreuve_une_egalite_parmi_trois_valeurs_reste_une_figure() -> None:
    socle = _socle(
        _d("charge_poste_1", "Loyer", 5_000),
        _d("charge_poste_2", "Énergie", 5_000),
        _d("charge_poste_3", "Assurances", 1_200),
    )
    resolution = resoudre(socle, "barres", ["charge_poste_1", "charge_poste_2", "charge_poste_3"])
    assert resolution.retenu, resolution.motif


# ── Règle 5 : la bonne période ───────────────────────────────────────────────


def test_une_annee_du_titre_absente_des_donnees_part_en_tableau() -> None:
    socle = _socle(*_previsionnel())

    blocs, rapport = _poser(socle, _figure(
        TypeGraphique.COURBES, "Chiffre d'affaires prévisionnel 2026-2029",
        "ca_previsionnel_an1", "ca_previsionnel_an2", "ca_previsionnel_an3",
    ))

    assert [bloc["type"] for bloc in blocs] == ["tableau"]
    assert blocs[0]["titre"] == ""
    assert "le titre cite 2026" in rapport.graphiques_en_tableau[0]


def test_la_legende_d_une_serie_ne_la_date_pas_d_une_seule_annee() -> None:
    """« Taille du marché national 2024 » légendait une courbe 2024-2028."""
    donnees = [
        _d("marche_national_taille", "Taille du marché national 2024", 3.1, "MdEUR",
           annee=2024, perimetre=Perimetre.NATIONAL),
        _d("marche_national_projection", "Taille du marché national en 2028", 3.6,
           "MdEUR", annee=2028, perimetre=Perimetre.NATIONAL),
    ]

    series = series_par_perimetre(donnees, [3.1, 3.6], [2024, 2028])

    assert [nom for nom, _ in series] == ["Taille du marché national"]


def test_une_frise_qui_annonce_une_annee_absente_ne_laisse_pas_de_tableau() -> None:
    """La frise dessine les tendances, pas les identifiants cités : refusée, elle
    ne laisse pas un tableau de chiffres sans rapport avec elle."""
    from generation.socle.schema import Tendance

    socle = _socle(
        *_previsionnel(),
        tendances=[
            Tendance(intitule="Céramique d'usage", horizon="2027"),
            Tendance(intitule="Ateliers partagés", horizon="2028"),
        ],
    )

    blocs, rapport = _poser(socle, _figure(
        TypeGraphique.CHRONOLOGIE, "Les tendances du métier à l'horizon 2035",
        "ca_previsionnel_an1",
    ))

    assert blocs == []
    assert "2035" in rapport.graphiques_abandonnes[0]
    assert rapport.graphiques_en_tableau == []


def test_contre_epreuve_la_bonne_periode_et_l_annee_d_une_source_passent() -> None:
    """Le commentaire s'imprime à la place de la source : « Insee 2024 » y est
    l'année de la source, pas la période de la figure."""
    socle = _socle(*_previsionnel())
    blocs, _ = _poser(socle, _figure(
        TypeGraphique.COURBES, "Chiffre d'affaires prévisionnel 2027-2029",
        "ca_previsionnel_an1", "ca_previsionnel_an2", "ca_previsionnel_an3",
        commentaire="Hypothèses de fréquentation calées sur l'enquête Insee 2024.",
    ))
    assert [bloc["type"] for bloc in blocs] == ["graphique"]


# ── Règle 6 : le projet nommé est dans les séries ────────────────────────────

CRITERES = [
    Critere(code="prix", intitule="Prix", note_1="cher", note_5="accessible"),
    Critere(code="offre", intitule="Offre", note_1="étroite", note_5="large"),
    Critere(code="accueil", intitule="Accueil", note_1="froid", note_5="chaleureux"),
]


def _acteur(nom: str, type_: str, *notes: int) -> Concurrent:
    return Concurrent(
        nom=nom, type=type_,
        notes=[
            NoteConcurrent(critere=critere.code, note=note)
            for critere, note in zip(CRITERES, notes, strict=False)
        ],
    )


def _socle_concurrentiel(*, projet_note_partout: bool = True) -> Socle:
    notes_du_projet = (4, 5, 4) if projet_note_partout else (4, 5)
    return _socle(
        _d("ca_previsionnel_an1", "Chiffre d'affaires prévisionnel — exercice 1", 180_000),
        grille_notation=CRITERES,
        concurrents=[
            *(_acteur(f"Atelier {lettre}", "direct", 3, 2, 4) for lettre in "ABCDEF"),
            _acteur(PROJET, "projet", *notes_du_projet),
        ],
    )


def test_le_plafond_du_radar_ne_coupe_plus_le_projet() -> None:
    """Six directs, puis le projet : le plafond de cinq le coupait en silence."""
    resolution = resoudre(_socle_concurrentiel(), "radar", ["prix", "offre", "accueil", "directs"])

    assert resolution.donnees is not None
    noms = [nom for nom, _ in resolution.donnees["series"]]
    assert PROJET in noms
    assert len(noms) == 5


def test_un_radar_qui_nomme_le_projet_sans_pouvoir_le_montrer_part_en_tableau() -> None:
    """Le projet n'est pas noté sur l'accueil : le radar ne peut pas le tracer.

    Sur le code d'avant : le radar des directs, sans lui, sous son nom.
    """
    blocs, rapport = _poser(_socle_concurrentiel(projet_note_partout=False), _figure(
        TypeGraphique.RADAR, f"{PROJET} face aux ateliers concurrents",
        "prix", "offre", "accueil", "directs",
    ))

    assert [bloc["type"] for bloc in blocs] == ["tableau"]
    assert blocs[0]["entetes"] == ["Acteur", "Prix", "Offre", "Accueil"]
    # La note absente se dit, elle ne s'invente pas.
    assert [PROJET, "4/5", "5/5", "—"] in blocs[0]["lignes"]
    assert blocs[0]["titre"] == ""
    assert "nomme le projet" in rapport.graphiques_en_tableau[0]


def test_contre_epreuve_un_radar_qui_ne_nomme_pas_le_projet_reste_dessine() -> None:
    blocs, _ = _poser(_socle_concurrentiel(projet_note_partout=False), _figure(
        TypeGraphique.RADAR, "Les ateliers concurrents sur trois critères",
        "prix", "offre", "accueil", "directs",
    ))
    assert [bloc["graphique"] for bloc in blocs] == ["radar"]


# ── Règle 7 : des libellés entiers ───────────────────────────────────────────


def test_une_etiquette_tres_longue_se_replie_sans_jamais_etre_coupee() -> None:
    """Au-delà de deux lignes, `textwrap` finissait l'étiquette par « … »."""
    libelle = (
        "Chiffre affaires prévisionnel consolidé des ateliers de céramique "
        "contemporaine installés en zone rurale"
    )
    etiquette = etiquette_de(_d("ca_actuel", libelle, 1.0))

    assert "…" not in etiquette
    assert etiquette.replace("\n", " ") == libelle


def test_deux_exercices_du_meme_chiffre_ne_portent_pas_la_meme_etiquette() -> None:
    """La tête « Chiffre d'affaires prévisionnel » effaçait l'exercice."""
    etiquettes = etiquettes_de(_previsionnel()[:3])
    assert len(set(etiquettes)) == 3
    assert all("exercice" in etiquette for etiquette in etiquettes)


def test_le_nom_d_un_acteur_sur_la_carte_n_est_plus_coupe() -> None:
    from generation.rendu_word.graphiques import _replier_le_nom

    nom = "Comptoir des Arts de la Table et du Feu"
    replie = _replier_le_nom(nom)

    assert "…" not in replie
    assert replie.replace("\n", " ") == nom


def test_un_libelle_tronque_venu_des_donnees_est_signale() -> None:
    """Le garde-fou : un « … » qui atteindrait la figure se voit au contrôle."""
    socle = _socle(
        _d("charge_poste_1", "Loyer de l'atelier…", 14_000),
        _d("charge_poste_2", "Énergie des fours", 9_000),
    )
    resolution = resoudre(socle, "barres", ["charge_poste_1", "charge_poste_2"])

    ecarts = ecarts_de_specification(
        socle, resolution, identifiants=["charge_poste_1", "charge_poste_2"],
        titre="Deux postes de charges",
    )

    assert [ecart.regle for ecart in ecarts] == ["libelle"]


def test_contre_epreuve_des_libelles_courts_et_distincts_ne_disent_rien() -> None:
    socle = _socle(
        _d("charge_poste_1", "Loyer de l'atelier", 14_000),
        _d("charge_poste_2", "Énergie des fours", 9_000),
    )
    resolution = resoudre(socle, "barres", ["charge_poste_1", "charge_poste_2"])
    assert ecarts_de_specification(
        socle, resolution, identifiants=["charge_poste_1", "charge_poste_2"],
        titre="Deux postes de charges",
    ) == []


# ── Revue du 30/09/2026 : ce que la première version prenait à tort ──────────
#
# Chaque test ci-dessous échoue sur `f823b06` (la première version de ce
# contrôle) : une figure juste y partait en tableau, ou une figure fausse y
# était posée. Les contre-épreuves disent que la règle mord toujours.

TRAJECTOIRE = ("ca_previsionnel_an1", "ca_previsionnel_an2", "ca_previsionnel_an3")


def _socle_avec_projet(*donnees: DonneeSocle) -> Socle:
    return _socle(
        *donnees, grille_notation=CRITERES,
        concurrents=[_acteur(PROJET, "projet", 4, 5, 4)],
    )


@pytest.mark.parametrize("titre", [
    "Chiffre d'affaires généré par le projet, 2027-2029",
    f"Chiffre d'affaires réalisé par {PROJET}, 2027-2029",
    "Chiffre d'affaires estimé par l'Insee, 2027-2029",
    "Chiffre d'affaires moyen par mois, 2027-2029",
])
def test_un_complement_d_agent_ou_un_taux_n_est_pas_un_decoupage(titre: str) -> None:
    """« par le projet », « par l'Insee » disent QUI, « par mois » un taux :
    aucun ne promet de découpage. La trajectoire reste une figure."""
    blocs, _ = _poser(
        _socle_avec_projet(*_previsionnel()), _figure(TypeGraphique.COURBES, titre, *TRAJECTOIRE),
    )
    assert [bloc["type"] for bloc in blocs] == ["graphique"], titre


def test_des_charges_de_structure_ne_sont_pas_une_structure() -> None:
    """« Charges de structure » = charges fixes : une grandeur, pas un découpage."""
    socle = _socle(*(
        _d(f"charges_fixes_an{n}", f"Charges fixes — exercice {n}", 40_000 + 5_000 * n,
           annee=2026 + n)
        for n in (1, 2, 3)
    ))
    blocs, _ = _poser(socle, _figure(
        TypeGraphique.COURBES, "Évolution des charges de structure sur trois exercices",
        "charges_fixes_an1", "charges_fixes_an2", "charges_fixes_an3",
    ))
    assert [bloc["type"] for bloc in blocs] == ["graphique"]


@pytest.mark.parametrize("titre", [
    "Évolution de la structure du chiffre d'affaires",
    "Chiffre d'affaires par gamme",
])
def test_contre_epreuve_un_vrai_decoupage_sur_une_seule_serie_reste_refuse(titre: str) -> None:
    blocs, _ = _poser(_socle(*_previsionnel()), _figure(
        TypeGraphique.COURBES, titre, *TRAJECTOIRE,
    ))
    assert [bloc["type"] for bloc in blocs] == ["tableau"], titre


def _completer(titre_du_chapitre: str) -> assemblage.RapportAssemblage:
    from types import SimpleNamespace

    socle = _socle(*_previsionnel())
    # La complétion ne lit que ces trois attributs du chapitre.
    payload: Any = SimpleNamespace(
        chapitre=5, titre=titre_du_chapitre,
        donnees_utilisees=["ca_previsionnel_an1", "ca_previsionnel_an2"],
    )
    rapport = assemblage.RapportAssemblage()
    assemblage._completer_les_figures(
        [{"numero": 5, "titre": titre_du_chapitre, "blocs": []}], [payload],
        socle, secteurs.profil_du_secteur(socle.secteur), rapport,
    )
    return rapport


def test_la_completion_ne_pose_pas_une_figure_sous_un_titre_faux() -> None:
    """Son titre est fait du nôtre : « Répartition des revenus par canal —
    repères chiffrés » sur un seul chiffre d'affaires mentirait comme un autre."""
    assert _completer("Répartition des revenus par canal").graphiques_completes == []


def test_contre_epreuve_la_completion_pose_une_figure_sous_un_titre_neutre() -> None:
    assert len(_completer("Lecture économique").graphiques_completes) == 1


def test_une_carte_des_risques_n_est_pas_jugee_sur_les_annees_des_chiffres_cites() -> None:
    """Elle dessine les RISQUES : l'année des identifiants cités ne la date pas."""
    from generation.socle.schema import Risque

    socle = _socle(*_previsionnel(), risques=[
        Risque(intitule="Retard des travaux", probabilite=3, impact=4),
        Risque(intitule="Hausse de l'énergie", probabilite=4, impact=3),
    ])
    blocs, _ = _poser(socle, _figure(
        TypeGraphique.MATRICE_POSITIONNEMENT, "Risques du lancement, 2028",
        "ca_previsionnel_an1",
    ))
    assert [bloc["graphique"] for bloc in blocs] == ["matrice_positionnement"]


def test_une_annee_au_milieu_d_une_legende_est_retiree_aussi() -> None:
    """Légende écrite par notre code : elle ne doit coûter son titre à personne."""
    donnees = [
        _d("marche_national_taille", "Taille du marché national en 2024 selon Xerfi", 3.1,
           "MdEUR", annee=2024, perimetre=Perimetre.NATIONAL),
        _d("marche_national_projection", "Taille projetée du marché national", 3.6,
           "MdEUR", annee=2028, perimetre=Perimetre.NATIONAL),
    ]
    nom = series_par_perimetre(donnees, [3.1, 3.6], [2024, 2028])[0][0]
    assert "2024" not in nom and "Xerfi" in nom.replace("\n", " ")


def test_contre_epreuve_une_legende_sans_periode_garde_ses_mots() -> None:
    """« an » au bout d'un mot n'est pas une année : « du plan 2 » reste entier."""
    donnees = [
        _d("ca_plan_an1", "Chiffre d'affaires du plan 2", 10_000),
        _d("ca_plan_an2", "Chiffre d'affaires du plan 2", 12_000, annee=2028),
    ]
    nom = series_par_perimetre(donnees, [10_000, 12_000], [2027, 2028])[0][0]
    assert nom.replace("\n", " ") == "Chiffre d'affaires du plan 2"


def test_le_catalogue_propose_la_trajectoire_entiere_quand_elle_part_de_presque_rien() -> None:
    """Le résolveur compare les SÉRIES ; le catalogue coupait la trajectoire
    point par point (50 € puis 70 000 € : rapport de 1 400)."""
    from generation.rendu_word.catalogue_figures import figures_possibles

    socle = _socle(*(
        _d(f"tresorerie_fin_an{n}", f"Trésorerie de clôture — exercice {n}", valeur,
           annee=2026 + n)
        for n, valeur in ((1, 50), (2, 30_000), (3, 70_000))
    ))
    groupes = {p.identifiants for p in figures_possibles(socle)}
    assert ("tresorerie_fin_an1", "tresorerie_fin_an2", "tresorerie_fin_an3") in groupes


def test_une_figure_reparee_puis_refusee_le_dit_au_diagnostic() -> None:
    socle = _socle(*_previsionnel(), _d("abonnes", "Abonnés", 140, "unite"))
    _, rapport = _poser(socle, _figure(
        TypeGraphique.BARRES, "Structure du chiffre d'affaires par gamme",
        "ca_previsionnel_an1", "ca_previsionnel_an3", "abonnes",
    ))
    assert str(rapport.diagnostic_des_abandons[0]["reparation"]).startswith("réussie")


def test_le_modele_n_est_pas_renvoye_a_son_titre_pour_un_libelle_tronque() -> None:
    from generation.chapitres.runner import _motifs_de_figure

    socle = _socle(
        _d("charge_poste_1", "Loyer de l'atelier…", 14_000),
        _d("charge_poste_2", "Énergie des fours", 9_000),
    )
    motifs = _motifs_de_figure(_payload(_figure(
        TypeGraphique.BARRES, "Deux postes de charges", "charge_poste_1", "charge_poste_2",
    )), socle)
    assert len(motifs) == 1 and "titre aux données" not in motifs[0]


@pytest.mark.parametrize("titre", [
    "Chiffre d'affaires sous la norme RE2020, 2027-2029",
    "Chiffre d'affaires et Plan France 2030, 2027-2029",
])
def test_un_nom_propre_date_n_est_pas_une_periode(titre: str) -> None:
    blocs, _ = _poser(_socle(*_previsionnel()), _figure(TypeGraphique.COURBES, titre, *TRAJECTOIRE))
    assert [bloc["type"] for bloc in blocs] == ["graphique"], titre


def test_une_pile_avec_une_perte_se_groupe_au_lieu_d_etre_refusee() -> None:
    resolution = resoudre(_socle(*_previsionnel()), "barres_empilees", [
        "ca_previsionnel_an1", "ca_previsionnel_an2", "resultat_net_an1", "resultat_net_an2",
    ])
    assert resolution.type_graphique == "barres_groupees"
    assert "négative" in resolution.motif
